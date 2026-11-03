"""Post-hoc reviewer follow-up for A01 using frozen evidence only.

This script is intentionally read-only with respect to the frozen A01 study.
It consumes the Phase 1.5 validation-evidence bundle and the Phase 2 final-
evidence bundle and writes a separate exploratory result package.

It does not train models, refit thresholds, change frozen policies, or overwrite
confirmatory A01 results.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np

CONFIDENCE_THRESHOLDS = (0.85, 0.90, 0.95)
AGREEMENT_THRESHOLDS = (0.70, 0.80, 0.90)
STD_THRESHOLDS = (0.10, 0.15, 0.20)
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20_260_902


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def validation_analyses(validation_root: Path) -> list[tuple[str, str, Path, dict[str, Any]]]:
    records: list[tuple[str, str, Path, dict[str, Any]]] = []
    projects = validation_root / "projects"
    for path in sorted(projects.glob("*/*/analyses/stability-analyses/*.json")):
        if path.name == "active-analysis.json":
            continue
        dataset_id = path.parts[-5]
        model_family = path.parts[-4]
        analysis = read_json(path)
        if analysis.get("applicability") != "APPLICABLE" or analysis.get("validation_alignment_status") != "EXACT_MATCH":
            continue
        records.append((dataset_id, model_family, path, analysis))
    return records


def case_confidence(case: dict[str, Any]) -> float:
    p = float(case["selected_run_probability"])
    return max(p, 1.0 - p)


def hcir(cases: list[dict[str, Any]], confidence_threshold: float, agreement_threshold: float) -> dict[str, Any]:
    high = [case for case in cases if case_confidence(case) >= confidence_threshold]
    unstable = [case for case in high if float(case["selected_run_agreement"]) < agreement_threshold]
    return {
        "high_confidence_n": len(high),
        "unstable_n": len(unstable),
        "hcir": None if not high else len(unstable) / len(high),
    }


def poisson_binomial_cdf(probabilities: Iterable[float], max_successes: int) -> float:
    """P(S <= max_successes) for independent Bernoulli trials."""
    probs = list(float(p) for p in probabilities)
    dist = np.zeros(len(probs) + 1, dtype=float)
    dist[0] = 1.0
    for p in probs:
        next_dist = dist * (1.0 - p)
        next_dist[1:] += dist[:-1] * p
        dist = next_dist
    return float(dist[: max_successes + 1].sum())


def independent_hcir_reference(analysis: dict[str, Any], agreement_threshold: float = 0.80, confidence_threshold: float = 0.90) -> dict[str, Any]:
    """Expected HCIR under an independence reference preserving run marginals.

    The selected run and its case-level confidence/class remain fixed. For each
    of the other runs, only that run's marginal positive-class frequency is
    retained; case-specific correspondence is removed. This is the analytical
    analogue of independently shuffling each non-selected run's labels across
    validation cases.
    """
    cases = analysis["cases"]
    selected_run_id = str(analysis["selected_run_id"])
    run_ids = [str(value) for value in analysis["run_ids"]]
    other_run_ids = [run_id for run_id in run_ids if run_id != selected_run_id]
    if len(run_ids) != 20 or len(other_run_ids) != 19:
        raise ValueError("A01 independence reference expects exactly 20 runs.")

    positive_rate: dict[str, float] = {}
    for run_id in other_run_ids:
        positive_rate[run_id] = float(np.mean([int(case["run_labels"][run_id]) for case in cases]))

    max_total_agreements = math.ceil(agreement_threshold * len(run_ids)) - 1
    max_other_agreements = max_total_agreements - 1

    unstable_probability_by_selected_class = {}
    for selected_class in (0, 1):
        probs = [q if selected_class == 1 else 1.0 - q for q in positive_rate.values()]
        unstable_probability_by_selected_class[str(selected_class)] = poisson_binomial_cdf(probs, max_other_agreements)

    high = [case for case in cases if case_confidence(case) >= confidence_threshold]
    if not high:
        expected_hcir = None
        counts = {"0": 0, "1": 0}
    else:
        counts = {
            "0": sum(int(case["selected_run_class"]) == 0 for case in high),
            "1": sum(int(case["selected_run_class"]) == 1 for case in high),
        }
        expected_hcir = sum(
            counts[label] * unstable_probability_by_selected_class[label] for label in ("0", "1")
        ) / len(high)

    observed = hcir(cases, confidence_threshold, agreement_threshold)
    return {
        "confidence_threshold": confidence_threshold,
        "agreement_threshold": agreement_threshold,
        "high_confidence_n": len(high),
        "high_confidence_selected_class_counts": counts,
        "run_positive_rates": positive_rate,
        "unstable_probability_by_selected_class": unstable_probability_by_selected_class,
        "expected_hcir_under_independence": expected_hcir,
        "observed_hcir": observed["hcir"],
        "observed_minus_expected": None if observed["hcir"] is None or expected_hcir is None else observed["hcir"] - expected_hcir,
        "reference_definition": (
            "Selected-run class/confidence fixed; each of the other 19 runs replaced by an independent Bernoulli label "
            "with that run's observed validation positive-class frequency. This preserves run-level class marginals "
            "while removing case-specific cross-run correspondence."
        ),
    }


def gate_coverage(cases: list[dict[str, Any]], std_threshold: float) -> dict[str, Any]:
    accepted = [
        case for case in cases
        if case_confidence(case) >= 0.90
        and float(case["selected_run_agreement"]) >= 0.80
        and float(case["std_probability"]) <= std_threshold
    ]
    return {"accepted_n": len(accepted), "total_n": len(cases), "coverage": len(accepted) / len(cases) if cases else 0.0}


def accepted_fnr(truth: np.ndarray, pred: np.ndarray, accepted: np.ndarray) -> dict[str, Any]:
    positives = accepted & (truth == 1)
    denom = int(positives.sum())
    fn = int((positives & (pred == 0)).sum())
    return {"accepted_positive_n": denom, "false_negative_n": fn, "fnr": None if denom == 0 else fn / denom}


def bank_dt_posthoc(final_root: Path) -> dict[str, Any]:
    result = read_json(final_root / "phase2_final" / "A01_FINAL_RESULTS.json")
    cell = next(
        item for item in result["cells"]
        if item["dataset_id"] == "uci_bank_marketing" and item["model_family"] == "decision_tree"
    )
    evidence_path = next((final_root / "product_final_test_evidence" / "uci_bank_marketing" / "decision_tree").glob("*.json"))
    evidence = read_json(evidence_path)
    rows = {int(row["source_row"]): row for row in evidence["prediction_rows"]}
    cases = evidence["stability_gate_evidence"]["cases"]

    truth = np.asarray([int(case["target"]) for case in cases], dtype=int)
    pred = np.asarray([int(case["selected_run_class"]) for case in cases], dtype=int)
    prob = np.asarray([float(case["selected_run_probability"]) for case in cases], dtype=float)
    stability_accept = np.asarray([case["disposition"] == "ACCEPT" for case in cases], dtype=bool)
    confidence = np.maximum(prob, 1.0 - prob)
    confidence_accept = confidence >= float(cell["confidence_cutoff"])
    no_review = np.ones(len(cases), dtype=bool)

    for case in cases:
        row = rows[int(case["source_row"])]
        if int(row["target"]) != int(case["target"]) or int(row["predicted_label"]) != int(case["selected_run_class"]):
            raise ValueError("Final evidence alignment mismatch in Bank Marketing Decision Tree.")

    summaries = {
        "no_review": accepted_fnr(truth, pred, no_review),
        "confidence_only": accepted_fnr(truth, pred, confidence_accept),
        "stability_aware": accepted_fnr(truth, pred, stability_accept),
    }
    observed_delta = summaries["stability_aware"]["fnr"] - summaries["confidence_only"]["fnr"]

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    deltas: list[float] = []
    for _ in range(BOOTSTRAP_REPLICATES):
        idx = rng.integers(0, len(truth), size=len(truth))
        left = accepted_fnr(truth[idx], pred[idx], stability_accept[idx])["fnr"]
        right = accepted_fnr(truth[idx], pred[idx], confidence_accept[idx])["fnr"]
        if left is not None and right is not None:
            deltas.append(float(left - right))
    ci = [float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))]
    frozen_ci = cell["bootstrap"]["delta_fnr"]["percentile_ci_95"]
    if not np.allclose(ci, frozen_ci, atol=1e-12, rtol=0):
        raise ValueError(f"Post-hoc Bank FNR bootstrap does not replay frozen case bootstrap: {ci} vs {frozen_ci}")

    return {
        "role": "POST_HOC_DESCRIPTIVE",
        "dataset_id": "uci_bank_marketing",
        "model_family": "decision_tree",
        "final_test_id": cell["final_test_id"],
        "confidence_cutoff": float(cell["confidence_cutoff"]),
        "coverage": {
            "no_review": float(no_review.mean()),
            "confidence_only": float(confidence_accept.mean()),
            "stability_aware": float(stability_accept.mean()),
        },
        "fnr": summaries,
        "delta_fnr_stability_minus_confidence": observed_delta,
        "paired_bootstrap": {
            "replicates": BOOTSTRAP_REPLICATES,
            "seed": BOOTSTRAP_SEED,
            "valid_replicates": len(deltas),
            "percentile_ci_95": ci,
            "matches_frozen_generic_bootstrap": True,
        },
        "interpretation_boundary": (
            "Bank Marketing FNR was not pre-specified as a confirmatory endpoint. This calculation is post-hoc and "
            "descriptive. The two policies also retain different final-test coverage, so the FNR difference is not a "
            "causal effect of cross-run disagreement at equal coverage."
        ),
    }


def _svg_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def maybe_make_figures(output: Path, hcir_rows: list[dict[str, Any]], bank: dict[str, Any]) -> list[str]:
    """Write a compact dependency-free SVG for the reviewer sensitivity check."""
    confidence_values = list(CONFIDENCE_THRESHOLDS)
    agreement = 0.80
    candidates: list[tuple[str, list[float]]] = []
    keys = sorted({(r["dataset_id"], r["model_family"]) for r in hcir_rows})
    for dataset_id, model_family in keys:
        values = []
        for confidence in confidence_values:
            row = next(
                r for r in hcir_rows
                if r["dataset_id"] == dataset_id
                and r["model_family"] == model_family
                and r["confidence_threshold"] == confidence
                and r["agreement_threshold"] == agreement
            )
            values.append(float(row["hcir"] or 0.0))
        if any(value > 0 for value in values):
            candidates.append((f"{dataset_id} / {model_family}", values))

    width, height = 900, 560
    left, right, top, bottom = 95, 250, 60, 75
    plot_w, plot_h = width - left - right, height - top - bottom
    ymax = max(max(values) for _, values in candidates) * 1.15 if candidates else 0.01
    ymax = max(ymax, 0.01)
    x = [left + index * plot_w / (len(confidence_values) - 1) for index in range(len(confidence_values))]

    def y(value: float) -> float:
        return top + plot_h - (value / ymax) * plot_h

    line_styles = ["#111111", "#444444", "#777777", "#999999", "#222222", "#666666"]
    dashes = ["", "8,4", "3,3", "10,3,2,3", "5,2", "2,2"]
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#111} .small{font-size:13px}.axis{stroke:#222;stroke-width:1.2}</style>',
        '<text x="450" y="30" text-anchor="middle" font-size="22">HCIR sensitivity to confidence threshold</text>',
        f'<text x="450" y="50" text-anchor="middle" class="small">agreement threshold = {agreement:.2f}; validation data</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" class="axis"/>',
        f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" class="axis"/>',
    ]
    for tick in range(0, 6):
        value = ymax * tick / 5
        yy = y(value)
        svg.append(f'<line x1="{left-5}" y1="{yy:.1f}" x2="{left+plot_w}" y2="{yy:.1f}" stroke="#dddddd" stroke-width="1"/>')
        svg.append(f'<text x="{left-10}" y="{yy+4:.1f}" text-anchor="end" class="small">{100*value:.1f}%</text>')
    for xx, confidence in zip(x, confidence_values):
        svg.append(f'<line x1="{xx:.1f}" y1="{top+plot_h}" x2="{xx:.1f}" y2="{top+plot_h+5}" class="axis"/>')
        svg.append(f'<text x="{xx:.1f}" y="{top+plot_h+25}" text-anchor="middle" class="small">{confidence:.2f}</text>')
    svg.append(f'<text x="{left+plot_w/2:.1f}" y="{height-18}" text-anchor="middle" class="small">High-confidence threshold</text>')
    svg.append(f'<text x="22" y="{top+plot_h/2:.1f}" text-anchor="middle" class="small" transform="rotate(-90 22 {top+plot_h/2:.1f})">HCIR</text>')

    legend_x = left + plot_w + 25
    legend_y = top + 10
    for index, (label, values) in enumerate(candidates):
        stroke = line_styles[index % len(line_styles)]
        dash = dashes[index % len(dashes)]
        points = " ".join(f"{xx:.1f},{y(value):.1f}" for xx, value in zip(x, values))
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        svg.append(f'<polyline points="{points}" fill="none" stroke="{stroke}" stroke-width="2.2"{dash_attr}/>')
        for xx, value in zip(x, values):
            svg.append(f'<circle cx="{xx:.1f}" cy="{y(value):.1f}" r="3.5" fill="white" stroke="{stroke}" stroke-width="2"/>')
        yy = legend_y + index * 48
        svg.append(f'<line x1="{legend_x}" y1="{yy}" x2="{legend_x+28}" y2="{yy}" stroke="{stroke}" stroke-width="2.2"{dash_attr}/>')
        svg.append(f'<text x="{legend_x+36}" y="{yy+4}" class="small">{_svg_escape(label)}</text>')
    svg.append("</svg>")
    path = output / "E01_hcir_confidence_sensitivity.svg"
    path.write_text("\n".join(svg) + "\n", encoding="utf-8")
    return [path.name]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation-root", type=Path, required=True)
    parser.add_argument("--final-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validation-bundle-sha256", default=None)
    parser.add_argument("--final-bundle-sha256", default=None)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    analyses = validation_analyses(args.validation_root)
    if len(analyses) != 15:
        raise ValueError(f"Expected 15 applicable A01 validation cells, found {len(analyses)}.")

    hcir_rows: list[dict[str, Any]] = []
    null_rows: list[dict[str, Any]] = []
    std_rows: list[dict[str, Any]] = []

    for dataset_id, model_family, path, analysis in analyses:
        cases = analysis["cases"]
        for confidence in CONFIDENCE_THRESHOLDS:
            for agreement in AGREEMENT_THRESHOLDS:
                result = hcir(cases, confidence, agreement)
                hcir_rows.append({
                    "dataset_id": dataset_id,
                    "model_family": model_family,
                    "confidence_threshold": confidence,
                    "agreement_threshold": agreement,
                    **result,
                })
        baseline = hcir(cases, 0.90, 0.80)
        if baseline["high_confidence_n"] != int(analysis["high_confidence_case_count"]):
            raise ValueError(f"Frozen high-confidence count replay failed for {dataset_id}/{model_family}.")
        if baseline["unstable_n"] != int(analysis["high_confidence_unstable_case_count"]):
            raise ValueError(f"Frozen unstable count replay failed for {dataset_id}/{model_family}.")
        persisted_hcir = analysis.get("high_confidence_instability_rate")
        if persisted_hcir is None:
            if baseline["hcir"] is not None:
                raise ValueError(f"Frozen HCIR replay failed for {dataset_id}/{model_family}.")
        elif baseline["hcir"] is None or abs(float(persisted_hcir) - float(baseline["hcir"])) > 1e-15:
            raise ValueError(f"Frozen HCIR replay failed for {dataset_id}/{model_family}.")

        ref = independent_hcir_reference(analysis)
        null_rows.append({
            "dataset_id": dataset_id,
            "model_family": model_family,
            "observed_hcir": ref["observed_hcir"],
            "expected_hcir_under_independence": ref["expected_hcir_under_independence"],
            "observed_minus_expected": ref["observed_minus_expected"],
            "high_confidence_n": ref["high_confidence_n"],
            "high_confidence_selected_class_0_n": ref["high_confidence_selected_class_counts"]["0"],
            "high_confidence_selected_class_1_n": ref["high_confidence_selected_class_counts"]["1"],
            "null_p_unstable_selected_0": ref["unstable_probability_by_selected_class"]["0"],
            "null_p_unstable_selected_1": ref["unstable_probability_by_selected_class"]["1"],
        })
        for std_threshold in STD_THRESHOLDS:
            cov = gate_coverage(cases, std_threshold)
            std_rows.append({
                "dataset_id": dataset_id,
                "model_family": model_family,
                "std_threshold": std_threshold,
                **cov,
            })

    bank = bank_dt_posthoc(args.final_root)

    write_csv(
        args.output / "T09_hcir_threshold_sensitivity.csv",
        hcir_rows,
        ["dataset_id", "model_family", "confidence_threshold", "agreement_threshold", "high_confidence_n", "unstable_n", "hcir"],
    )
    write_csv(
        args.output / "T10_hcir_independence_reference.csv",
        null_rows,
        [
            "dataset_id", "model_family", "observed_hcir", "expected_hcir_under_independence", "observed_minus_expected",
            "high_confidence_n", "high_confidence_selected_class_0_n", "high_confidence_selected_class_1_n",
            "null_p_unstable_selected_0", "null_p_unstable_selected_1",
        ],
    )
    write_csv(
        args.output / "T11_probability_std_sensitivity.csv",
        std_rows,
        ["dataset_id", "model_family", "std_threshold", "accepted_n", "total_n", "coverage"],
    )
    write_json(args.output / "T12_bank_marketing_dt_fnr_posthoc.json", bank)

    grid_summary = []
    for confidence in CONFIDENCE_THRESHOLDS:
        for agreement in AGREEMENT_THRESHOLDS:
            rows = [r for r in hcir_rows if r["confidence_threshold"] == confidence and r["agreement_threshold"] == agreement]
            grid_summary.append({
                "confidence_threshold": confidence,
                "agreement_threshold": agreement,
                "nonzero_hcir_cells": sum((r["hcir"] or 0.0) > 0 for r in rows),
                "max_hcir": max((r["hcir"] or 0.0) for r in rows),
            })

    baseline_rows = [r for r in hcir_rows if r["confidence_threshold"] == 0.90 and r["agreement_threshold"] == 0.80]
    baseline_nonzero = sorted(
        [r for r in baseline_rows if (r["hcir"] or 0.0) > 0],
        key=lambda r: r["hcir"], reverse=True,
    )
    null_nonzero = sorted(
        [r for r in null_rows if (r["observed_hcir"] or 0.0) > 0],
        key=lambda r: r["observed_hcir"], reverse=True,
    )

    ranges = []
    for dataset_id, model_family, _, _ in analyses:
        rows = [r for r in std_rows if r["dataset_id"] == dataset_id and r["model_family"] == model_family]
        vals = [r["coverage"] for r in rows]
        ranges.append({"dataset_id": dataset_id, "model_family": model_family, "coverage_range": max(vals) - min(vals), "min": min(vals), "max": max(vals)})
    ranges.sort(key=lambda r: r["coverage_range"], reverse=True)

    figures = maybe_make_figures(args.output, hcir_rows, bank)

    summary = {
        "schema_version": 1,
        "role": "POST_HOC_EXPLORATORY_REVIEWER_FOLLOWUP",
        "frozen_confirmatory_results_modified": False,
        "training_performed": False,
        "threshold_or_policy_refitting_performed": False,
        "additional_final_test_opening_performed": False,
        "validation_cell_count": len(analyses),
        "validation_bundle_sha256": args.validation_bundle_sha256,
        "final_bundle_sha256": args.final_bundle_sha256,
        "hcir_grid": grid_summary,
        "baseline_nonzero_hcir_cells": baseline_nonzero,
        "independence_reference_for_baseline_nonzero_cells": null_nonzero,
        "largest_probability_std_coverage_ranges": ranges[:5],
        "bank_marketing_decision_tree_fnr_posthoc": bank,
        "figures": figures,
    }
    write_json(args.output / "A01_REVIEWER_FOLLOWUP_RESULTS.json", summary)

    def pct(value: float | None) -> str:
        return "NA" if value is None else f"{100 * value:.3f}%"

    report = [
        "# A01 reviewer follow-up — post-hoc exploratory analyses",
        "",
        "## Status and scientific boundary",
        "",
        "This package is **post hoc / exploratory**. It reads frozen A01 evidence only. It does not retrain a model, refit a threshold or policy, alter `A01_FINAL_RESULTS.json`, or reopen the final test.",
        "",
        f"- Validation evidence bundle SHA-256: `{args.validation_bundle_sha256 or 'not supplied'}`",
        f"- Final evidence bundle SHA-256: `{args.final_bundle_sha256 or 'not supplied'}`",
        f"- Validation cells inspected: {len(analyses)}",
        "",
        "## 1. HCIR threshold sensitivity on validation data",
        "",
        "The original A01 point is confidence >= 0.90 and selected-run agreement < 0.80. The grid below changes only the descriptive thresholds on the already frozen validation case evidence.",
        "",
        "| confidence | agreement | cells with non-zero HCIR | maximum HCIR |",
        "|---:|---:|---:|---:|",
    ]
    for row in grid_summary:
        report.append(f"| {row['confidence_threshold']:.2f} | {row['agreement_threshold']:.2f} | {row['nonzero_hcir_cells']}/15 | {pct(row['max_hcir'])} |")
    report += ["", "At the original 0.90/0.80 point, the non-zero cells are:", ""]
    for row in baseline_nonzero:
        report.append(f"- `{row['dataset_id']} / {row['model_family']}`: {row['unstable_n']}/{row['high_confidence_n']} = {pct(row['hcir'])}.")

    report += [
        "",
        "## 2. HCIR independence reference on validation data",
        "",
        "For each cell, the selected-run class and confidence are kept fixed. Each of the other 19 runs is replaced by an independent label source with the same validation positive-class frequency as that run. This preserves run-level class marginals but removes case-specific agreement. The resulting value is a descriptive independence reference, not a confirmatory null test.",
        "",
        "| dataset / model | observed HCIR | independence reference | observed - reference |",
        "|---|---:|---:|---:|",
    ]
    for row in null_nonzero:
        report.append(
            f"| {row['dataset_id']} / {row['model_family']} | {pct(row['observed_hcir'])} | "
            f"{pct(row['expected_hcir_under_independence'])} | {pct(row['observed_minus_expected'])} |"
        )

    report += [
        "",
        "## 3. Probability-dispersion threshold sensitivity on validation data",
        "",
        "The Stability Gate is recomputed descriptively from frozen case evidence with confidence >= 0.90 and agreement >= 0.80 while changing only the maximum probability standard deviation (0.10, 0.15, 0.20). No policy is refit or persisted.",
        "",
        "Largest coverage ranges across the tested standard-deviation thresholds:",
        "",
    ]
    for row in ranges[:5]:
        report.append(f"- `{row['dataset_id']} / {row['model_family']}`: {pct(row['min'])} to {pct(row['max'])} (range {pct(row['coverage_range'])}).")

    b = bank
    report += [
        "",
        "## 4. Bank Marketing Decision Tree FNR — post-hoc descriptive final-test readout",
        "",
        f"- No review: {b['fnr']['no_review']['false_negative_n']}/{b['fnr']['no_review']['accepted_positive_n']} = {pct(b['fnr']['no_review']['fnr'])}.",
        f"- Confidence-only: {b['fnr']['confidence_only']['false_negative_n']}/{b['fnr']['confidence_only']['accepted_positive_n']} = {pct(b['fnr']['confidence_only']['fnr'])}.",
        f"- Stability-aware: {b['fnr']['stability_aware']['false_negative_n']}/{b['fnr']['stability_aware']['accepted_positive_n']} = {pct(b['fnr']['stability_aware']['fnr'])}.",
        f"- Delta FNR (stability - confidence): {b['delta_fnr_stability_minus_confidence']:+.6f}; paired bootstrap 95% CI [{b['paired_bootstrap']['percentile_ci_95'][0]:+.6f}, {b['paired_bootstrap']['percentile_ci_95'][1]:+.6f}].",
        f"- Final-test coverage: confidence-only {pct(b['coverage']['confidence_only'])}; stability-aware {pct(b['coverage']['stability_aware'])}.",
        "",
        "This endpoint was not pre-specified for Bank Marketing. Because final-test coverage differs between the two policies, the FNR difference is descriptive and does not identify a causal effect of the stability signal at equal coverage.",
        "",
        "## Article-use boundary",
        "",
        "These analyses may be reported as reviewer-requested post-hoc/exploratory checks. They must not be described as part of the frozen confirmatory protocol or used to retroactively redefine the primary A01 hypotheses.",
    ]
    (args.output / "A01_REVIEWER_FOLLOWUP.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    receipt = {
        "schema_version": 1,
        "role": "POST_HOC_EXPLORATORY_REVIEWER_FOLLOWUP",
        "output_files": {
            p.name: sha256(p) for p in sorted(args.output.iterdir()) if p.is_file() and p.name != "A01_REVIEWER_FOLLOWUP_RECEIPT.json"
        },
    }
    write_json(args.output / "A01_REVIEWER_FOLLOWUP_RECEIPT.json", receipt)
    print(canonical_json(summary))


if __name__ == "__main__":
    main()
