"""A01 Phase 2.1 read-only audit and presentation utilities.

This module deliberately consumes only persisted Phase 2 evidence.  It does
not import product training, policy-fitting, or final-test application code.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from research.a01_stability_aware_review.statistics import (
    accepted_case_fnr, accepted_case_risk, h3_interpretation,
    paired_bootstrap_policy_metrics,
)

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results" / "phase2_final"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def final_evidence_path(cell: dict[str, Any]) -> Path:
    return ROOT / "artifacts" / "phase1-projects" / cell["dataset_id"] / cell["model_family"] / "analyses" / "final-tests" / f"{cell['final_test_id']}.json"


def _case_arrays(cell: dict[str, Any]) -> tuple[list[int], list[int], list[str], list[str], list[dict[str, Any]]]:
    evidence = load_json(final_evidence_path(cell))
    prediction = {int(row["source_row"]): row for row in evidence["prediction_rows"]}
    rows: list[dict[str, Any]] = []
    for case in evidence["stability_gate_evidence"]["cases"]:
        row = prediction.get(int(case["source_row"]))
        if row is None:
            raise ValueError(f"missing product prediction for {cell['dataset_id']}:{cell['model_family']}:{case['case_id']}")
        if int(row["target"]) != int(case["target"]) or int(row["predicted_label"]) != int(case["selected_run_class"]):
            raise ValueError("persisted product/stability label alignment mismatch")
        if abs(float(row["probability"]) - float(case["selected_run_probability"])) > 1e-12:
            raise ValueError("persisted product/stability probability alignment mismatch")
        rows.append({
            "case_id": case["case_id"], "source_row": int(case["source_row"]), "target": int(case["target"]),
            "prediction": int(case["selected_run_class"]), "probability": float(case["selected_run_probability"]),
            "confidence": max(float(case["selected_run_probability"]), 1 - float(case["selected_run_probability"])),
            "selected_run_agreement": float(case["selected_run_agreement"]),
            "majority_class_agreement": float(case["majority_class_agreement"]),
            "probability_std": float(case["probability_std"]), "stability": case["disposition"],
            "reasons": list(case.get("reasons", [])),
        })
    truth = [row["target"] for row in rows]
    pred = [row["prediction"] for row in rows]
    stability = [row["stability"] for row in rows]
    confidence = ["ACCEPT" if row["confidence"] >= float(cell["confidence_cutoff"]) else "REVIEW" for row in rows]
    return truth, pred, stability, confidence, rows


def recompute_cell(cell: dict[str, Any]) -> dict[str, Any]:
    truth, pred, stability, confidence, rows = _case_arrays(cell)
    no_review = ["ACCEPT"] * len(rows)
    summaries = {
        "no_review": accepted_case_risk(truth, pred, no_review).__dict__,
        "confidence_only_frozen": accepted_case_risk(truth, pred, confidence).__dict__,
        "stability_gate_frozen": accepted_case_risk(truth, pred, stability).__dict__,
    }
    boot = paired_bootstrap_policy_metrics(truth, pred, stability, confidence, replicates=10_000, seed=20_260_902)
    delta = None if summaries["stability_gate_frozen"]["accepted_risk"] is None or summaries["confidence_only_frozen"]["accepted_risk"] is None else summaries["stability_gate_frozen"]["accepted_risk"] - summaries["confidence_only_frozen"]["accepted_risk"]
    fnr = None
    delta_fnr = None
    if cell["dataset_id"] == "ai4i_2020":
        fnr = {
            "no_review": accepted_case_fnr(truth, pred, no_review),
            "confidence_only_frozen": accepted_case_fnr(truth, pred, confidence),
            "stability_gate_frozen": accepted_case_fnr(truth, pred, stability),
        }
        left, right = fnr["stability_gate_frozen"]["accepted_case_fnr"], fnr["confidence_only_frozen"]["accepted_case_fnr"]
        delta_fnr = None if left is None or right is None else left - right
    return {**summaries, "bootstrap": boot, "observed_delta_risk": delta, "ai4i_fnr": fnr,
            "observed_delta_fnr": delta_fnr, "h3_status": h3_interpretation(boot["delta_risk"]["percentile_ci_95"]),
            "case_count": len(rows), "unstable_cases": sorted((r for r in rows if r["selected_run_agreement"] < .80), key=lambda r: (r["selected_run_agreement"], -r["confidence"], r["case_id"]))}


def _same(a: Any, b: Any, tol: float = 1e-12) -> bool:
    if a is None or b is None: return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)): return abs(float(a) - float(b)) <= tol
    # Product dataclasses retain tuples in memory; the immutable executor
    # serializes those same values as JSON arrays.  Compare sequence content,
    # not the incidental Python container used by the read-only audit.
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)): return len(a) == len(b) and all(_same(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict): return set(a) == set(b) and all(_same(a[k], b[k], tol) for k in a)
    return a == b


def independent_audit(result_root: Path = RESULTS, *, output: Path | None = None) -> dict[str, Any]:
    frozen = load_json(result_root / "A01_FINAL_RESULTS.json")
    mismatches: list[dict[str, Any]] = []
    recomputed: list[dict[str, Any]] = []
    for cell in frozen["cells"]:
        observed = recompute_cell(cell)
        recomputed.append({"dataset_id": cell["dataset_id"], "model_family": cell["model_family"], **observed})
        for field in ("no_review", "confidence_only_frozen", "stability_gate_frozen", "observed_delta_risk", "ai4i_fnr", "observed_delta_fnr", "bootstrap", "h3_status"):
            if not _same(cell[field], observed[field]):
                mismatches.append({"cell": f"{cell['dataset_id']}::{cell['model_family']}", "statistic": field,
                                   "frozen": cell[field], "recomputed": observed[field], "tolerance": 1e-12})
    out = {"schema_version": 1, "role": "POST_EXECUTION_READ_ONLY", "source": "persisted_final_test_case_evidence",
           "frozen_result_sha256": sha256(result_root / "A01_FINAL_RESULTS.json"),
           "status": "INDEPENDENT_RECOMPUTATION_PASS" if not mismatches else "INDEPENDENT_RECOMPUTATION_FAIL",
           "cell_count": len(recomputed), "mismatches": mismatches, "recomputed_cells": recomputed}
    if output: output.write_text(canonical(out) + "\n", encoding="utf-8")
    return out
