"""Sharp equal-coverage bounds from frozen A01 aggregate counts.

This is a *partial-identification* audit. It does not retrain models or
reconstruct case-level confidence rankings. All results are conditional
on the same frozen predictions and binary error labels under both policies.
Run from the repository root:
  python research/a01_stability_aware_review/scripts/bound_matched_coverage_a01.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "results" / "phase2_final"


def sharp_baseline_bounds(n: int, all_errors: int, base_accept: int,
                          base_errors: int, target_accept: int) -> tuple[int, int]:
    """Min/max errors after extending or restricting baseline acceptance.

    The intervals are *tight* over all feasible accepted subsets of the
    originally accepted/reviewed cases; no ranking or randomization is assumed.
    """
    if not (0 <= base_errors <= base_accept <= n
            and 0 <= all_errors - base_errors <= n - base_accept
            and 0 <= target_accept <= n):
        raise ValueError("inconsistent cohort or error totals")
    if target_accept <= base_accept:
        removed = base_accept - target_accept
        return (
            base_errors - min(removed, base_errors),
            base_errors - max(0, removed - (base_accept - base_errors)),
        )
    added = target_accept - base_accept
    rejected_errors = all_errors - base_errors
    rejected_correct = n - base_accept - rejected_errors
    return (
        base_errors + max(0, added - rejected_correct),
        base_errors + min(added, rejected_errors),
    )


def audit(source_dir: Path = FROZEN) -> dict:
    source = source_dir / "A01_FINAL_RESULTS.json"
    manifest = json.loads((source_dir / "A01_FINAL_RESULT_FREEZE_MANIFEST.json").read_text())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != manifest["immutable_result_json_sha256"]:
        raise ValueError("A01 frozen source changed: SHA-256 does not match manifest")
    frozen = json.loads(source.read_text())
    rows = []
    for cell in frozen["cells"]:
        no = cell["no_review"]
        base = cell["confidence_only_frozen"]
        gate = cell["stability_gate_frozen"]
        n = int(no["total_cases"])
        all_errors = int(no["accepted_errors"])
        ba, be = int(base["accepted_count"]), int(base["accepted_errors"])
        ga, ge = int(gate["accepted_count"]), int(gate["accepted_errors"])
        if any(int(z["total_cases"]) != n for z in (base, gate)):
            raise ValueError("policy cohorts differ")
        if not (0 <= ge <= ga and 0 <= all_errors - ge <= n - ga):
            raise ValueError("gate counts inconsistent with frozen error totals")
        low, high = sharp_baseline_bounds(n, all_errors, ba, be, ga)
        if ge < low:
            status = "GATE_BETTER_FOR_EVERY_FEASIBLE_BASELINE_MATCH"
        elif ge > high:
            status = "GATE_WORSE_FOR_EVERY_FEASIBLE_BASELINE_MATCH"
        elif low == high == ge:
            status = "SAME_ERROR_COUNT_AND_COVERAGE"
        else:
            status = "UNIDENTIFIED_FROM_AGGREGATES"
        rows.append({
            "dataset": cell["dataset_id"], "model": cell["model_family"],
            "n": n, "no_review_errors": all_errors,
            "confidence_accepted": ba, "confidence_errors": be,
            "gate_accepted": ga, "gate_errors": ge,
            "confidence_matched_min_errors": low,
            "confidence_matched_max_errors": high,
            "min_gate_excess_errors_vs_any_baseline_extension": ge - high,
            "status": status,
        })
    if len(rows) != 15:
        raise ValueError("expected 15 frozen A01 cells")
    return {
        "source_sha256": digest,
        "method": "tight aggregate-only bounds at the gate's acceptance count",
        "assumptions": "same frozen prediction errors and cohort across policies; no case ranks used",
        "not_established": "matched-budget measured baseline, superiority out of sample, or original training replay",
        "rows": rows,
    }


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
