"""Independent, read-only scientific audit of the frozen A01 Phase 1 state.

The audit loads persisted objects directly.  It never calls a trainer or a
final-test service; any disagreement with frozen Phase 1 facts fails closed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from research.a01_stability_aware_review.core import CONFIG, ROOT, canonical_json, load_json, sha256_file
from research.a01_stability_aware_review.statistics import validation_matched_confidence_cutoff

PHASE1 = ROOT / "results" / "phase1_validation"
RESULTS = ROOT / "results" / "phase1_5_audit"
PROJECTS = ROOT / "artifacts" / "phase1-projects"
EPS = 1e-12


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _project(binding: dict[str, Any]) -> Path:
    return PROJECTS / binding["dataset_id"] / binding["model_family"]


def _load(root: Path, area: str, identifier: str) -> dict[str, Any]:
    return json.loads((root / area / f"{identifier}.json").read_text(encoding="utf-8"))


def _f1(target: np.ndarray, predicted: np.ndarray) -> float:
    tp = int(np.sum((target == 1) & (predicted == 1)))
    fp = int(np.sum((target == 0) & (predicted == 1)))
    fn = int(np.sum((target == 1) & (predicted == 0)))
    return 0.0 if (2 * tp + fp + fn) == 0 else 2 * tp / (2 * tp + fp + fn)


def _confusion(target: np.ndarray, predicted: np.ndarray) -> dict[str, int]:
    return {
        "true_negative": int(np.sum((target == 0) & (predicted == 0))),
        "false_positive": int(np.sum((target == 0) & (predicted == 1))),
        "false_negative": int(np.sum((target == 1) & (predicted == 0))),
        "true_positive": int(np.sum((target == 1) & (predicted == 1))),
    }


def _h2(analysis: dict[str, Any]) -> dict[str, Any]:
    cases = analysis["cases"]
    high = [case for case in cases if max(float(case["selected_run_probability"]), 1 - float(case["selected_run_probability"])) >= .9]
    unstable = [case for case in high if float(case["selected_run_agreement"]) < .8]
    denominator, numerator = len(high), len(unstable)
    return {
        "high_confidence_denominator": denominator,
        "high_confidence_unstable_numerator": numerator,
        "hcir": None if denominator == 0 else numerator / denominator,
        "h2_status": "NOT_ASSESSABLE" if denominator == 0 else ("PATTERN_OBSERVED" if numerator else "PATTERN_NOT_OBSERVED"),
        "reason": "ZERO_HIGH_CONFIDENCE_DENOMINATOR" if denominator == 0 else None,
    }


def _flat_nf(binding: dict[str, Any]) -> dict[str, Any]:
    root = _project(binding)
    evaluation = _load(root, "analyses/evaluations", binding["evaluation_id"])
    threshold = _load(root, "analyses/thresholds", binding["threshold_id"])
    rows = evaluation["prediction_preview"]
    truth = np.asarray([int(row["target"]) for row in rows], dtype=int)
    probability = np.asarray([float(row["probability"]) for row in rows], dtype=float)
    default_prediction = (probability >= .5).astype(int)
    candidates = np.arange(.01, 1.0, .01)
    scores = [{"threshold": round(float(value), 2), "f1": _f1(truth, (probability >= value).astype(int))} for value in candidates]
    best = max(scores, key=lambda row: (row["f1"], -abs(row["threshold"] - .5), -row["threshold"]))
    frozen = (probability >= float(threshold["selected_threshold"])).astype(int)
    # The orientation check is intentionally a semantic check, not a result
    # optimization: the persisted threshold's f1 must match its persisted
    # selection result, while its complement must not be silently substituted.
    frozen_f1 = _f1(truth, frozen)
    complement_f1 = _f1(truth, 1 - frozen)
    return {
        "dataset_id": binding["dataset_id"], "model_family": binding["model_family"],
        "positive_class_identity": 1, "probability_column_semantics": "raw probability of class 1",
        "run_metric_f1_at_default_0_50": _f1(truth, default_prediction),
        "frozen_selected_threshold": threshold["selected_threshold"],
        "frozen_threshold_f1": frozen_f1, "frozen_threshold_confusion_matrix": _confusion(truth, frozen),
        "threshold_selection_result": threshold["selection_result"], "threshold_sweep_maximum": best,
        "orientation_check": "PASS" if abs(frozen_f1 - float(threshold["selection_result"])) <= EPS and frozen_f1 >= complement_f1 else "FAIL",
        "probability_quantiles": {str(q): float(np.quantile(probability, q)) for q in (.0, .05, .25, .5, .75, .95, 1.0)},
        "positive_truth_probability_quantiles": {str(q): float(np.quantile(probability[truth == 1], q)) for q in (.0, .5, 1.0)},
        "negative_truth_probability_quantiles": {str(q): float(np.quantile(probability[truth == 0], q)) for q in (.0, .5, 1.0)},
        "default_class_1_count": int(default_prediction.sum()), "candidate_f1_curve": scores,
    }


def audit() -> dict[str, Any]:
    bindings = load_json(PHASE1 / "selected_runs.json")
    frozen_observations = {(row["dataset_id"], row["model_family"]): row for row in load_json(PHASE1 / "validation_observations.json")}
    h2_rows, corrected_h1, comparator_rows, artifacts, flat_rows = [], [], [], [], []
    for binding in bindings:
        key = (binding["dataset_id"], binding["model_family"])
        root = _project(binding)
        study = _load(root, "studies", binding["study_id"])
        analysis = _load(root, "analyses/stability-analyses", binding["stability_analysis_id"])
        gate = _load(root, "analyses/stability-policies", binding["stability_gate_policy_id"])
        h2 = _h2(analysis); frozen = frozen_observations[key]
        if h2["h2_status"] != frozen["h2_status"] or h2["high_confidence_denominator"] != frozen["high_confidence_denominator"] or h2["high_confidence_unstable_numerator"] != frozen["high_confidence_unstable_numerator"] or (h2["hcir"] is not None and abs(h2["hcir"] - float(frozen["hcir"])) > EPS):
            raise RuntimeError(f"H2 frozen evidence mismatch for {key}.")
        ordered = sorted(study["seed_runs"], key=lambda run: (-float(run["validation_metrics"]["f1"]), int(run.get("training_seed", run["seed"]))))
        if ordered[0]["run_id"] != binding["selected_run_id"]:
            raise RuntimeError(f"Selected-run rule mismatch for {key}.")
        confidences = [max(float(case["selected_run_probability"]), 1 - float(case["selected_run_probability"])) for case in analysis["cases"]]
        coverage = sum(decision["disposition"] == "ACCEPT" for decision in gate["decisions"]) / len(gate["decisions"])
        comparator = validation_matched_confidence_cutoff(confidences, coverage)
        if any(abs(float(comparator[k]) - float(binding[{"confidence_cutoff": "confidence_cutoff", "validation_coverage": "confidence_validation_coverage", "absolute_coverage_gap": "absolute_coverage_gap"}[k]])) > EPS for k in comparator):
            raise RuntimeError(f"Comparator coverage mismatch for {key}.")
        h2_rows.append({"dataset_id": key[0], "model_family": key[1], **h2})
        corrected_h1.append({"dataset_id": key[0], "model_family": key[1], "h1_confirmatory_status": "NOT_ASSESSABLE", "reason": "PRE_SPECIFIED_COMPACTNESS_RULE_UNDERSPECIFIED", "retained_validation_f1": frozen["validation_f1"], "retained_probability_std": frozen["probability_std"], "retained_pairwise_disagreement": frozen["pairwise_prediction_disagreement_distribution"], "retained_proportion_selected_run_agreement_lt_1": frozen["proportion_selected_run_agreement_lt_1"], "retained_proportion_selected_run_agreement_lt_0_80": frozen["proportion_selected_run_agreement_lt_0_80"]})
        comparator_rows.append({"dataset_id": key[0], "model_family": key[1], "stability_coverage": coverage, **comparator, "frozen_cutoff": binding["confidence_cutoff"], "frozen_gap": binding["absolute_coverage_gap"]})
        for run in study["seed_runs"]:
            digest = run["model_artifact_sha256"]
            blob = root / "artifacts" / "sha256" / digest[:2] / digest
            record = root / "objects" / "artifacts" / f"{digest}.json"
            if not blob.is_file() or not record.is_file() or sha256_file(blob) != digest:
                raise RuntimeError(f"Frozen model artifact missing or invalid: {key}/{run['run_id']}.")
            artifacts.append({"logical_project_root": f"projects/{key[0]}/{key[1]}", "dataset_id": key[0], "model_family": key[1], "run_id": run["run_id"], "training_seed": run.get("training_seed", run["seed"]), "split_seed": run.get("split_seed"), "model_artifact_sha256": digest, "artifact_blob": f"artifacts/sha256/{digest[:2]}/{digest}", "artifact_metadata": f"objects/artifacts/{digest}.json", "preprocessing_identity": json.dumps(run["normalization"], sort_keys=True), "dataset_fingerprint": run["dataset_fingerprint"]})
        if key[1] == "flat_neuro_fuzzy" and key[0] in {"ai4i_2020", "uci_bank_marketing"}:
            flat = _flat_nf(binding)
            if flat["orientation_check"] != "PASS":
                raise RuntimeError(f"Flat Neuro-Fuzzy semantic audit failed for {key}.")
            flat_rows.append(flat)
    if len(artifacts) != 300:
        raise RuntimeError(f"Expected 300 verified frozen model artifacts, found {len(artifacts)}.")
    payload = {"status": "PASS", "h1_corrected_status": "NOT_ASSESSABLE", "h1_reason": "PRE_SPECIFIED_COMPACTNESS_RULE_UNDERSPECIFIED", "h2_rows": h2_rows, "h2_counts": {"PATTERN_OBSERVED": sum(row["h2_status"] == "PATTERN_OBSERVED" for row in h2_rows), "PATTERN_NOT_OBSERVED": sum(row["h2_status"] == "PATTERN_NOT_OBSERVED" for row in h2_rows), "NOT_ASSESSABLE": sum(row["h2_status"] == "NOT_ASSESSABLE" for row in h2_rows)}, "comparator_rows": comparator_rows, "flat_neuro_fuzzy_forensics": flat_rows, "model_artifact_count": len(artifacts), "final_test_access": "CLOSED", "models_retrained": False}
    _write(RESULTS / "H1_CORRECTED_INTERPRETATION.json", corrected_h1)
    _write(RESULTS / "H2_INDEPENDENT_RECOMPUTATION.json", h2_rows)
    _write(RESULTS / "COMPARATOR_COVERAGE_AUDIT.json", comparator_rows)
    _write(RESULTS / "FLAT_NEURO_FUZZY_FORENSIC_AUDIT.json", flat_rows)
    (RESULTS / "MODEL_ARTIFACT_FREEZE.jsonl").write_text("".join(canonical_json(row) + "\n" for row in artifacts), encoding="utf-8")
    _write(RESULTS / "PHASE1_5_AUDIT_RECEIPT.json", payload)
    return payload


if __name__ == "__main__":
    print(canonical_json(audit()))
