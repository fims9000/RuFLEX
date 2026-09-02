from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.a01_stability_aware_review.scripts.audit_phase1_5_scientific_freeze import audit
from research.a01_stability_aware_review.scripts.execute_phase2_final_test import authorization_gate
from research.a01_stability_aware_review.scripts.phase2_synthetic_dry_run import dry_run
from research.a01_stability_aware_review.statistics import validation_matched_confidence_cutoff


ROOT = Path(__file__).resolve().parents[1] / "research" / "a01_stability_aware_review"


def test_h1_amendment_withdraws_binary_labels_without_rewriting_phase1() -> None:
    rows = json.loads((ROOT / "results/phase1_5_audit/H1_CORRECTED_INTERPRETATION.json").read_text())
    assert len(rows) == 15
    assert {row["h1_confirmatory_status"] for row in rows} == {"NOT_ASSESSABLE"}
    assert {row["reason"] for row in rows} == {"PRE_SPECIFIED_COMPACTNESS_RULE_UNDERSPECIFIED"}


def test_h2_recomputation_and_model_freeze_are_complete() -> None:
    receipt = audit()
    assert receipt["h2_counts"] == {"PATTERN_OBSERVED": 4, "PATTERN_NOT_OBSERVED": 11, "NOT_ASSESSABLE": 0}
    assert receipt["model_artifact_count"] == 300


def test_decision_tree_coverage_gap_is_minimal_frozen_result() -> None:
    rows = json.loads((ROOT / "results/phase1_5_audit/COMPARATOR_COVERAGE_AUDIT.json").read_text())
    selected = [row for row in rows if row["model_family"] == "decision_tree"]
    assert [round(row["absolute_coverage_gap"], 6) for row in selected] == [0.0115, 0.039573, 0.026316]


def test_phase2_refuses_without_unlock_before_data_access() -> None:
    with pytest.raises(PermissionError, match="final test is closed"):
        authorization_gate(None, {"phase1_5_manifest_id": "x"})


def test_phase2_dry_run_is_synthetic_only() -> None:
    result = dry_run()
    assert result["status"] == "PASS"
    assert result["final_test_accessed"] is False
    assert result["data"] == "SYNTHETIC_NON_A01_NON_FINAL"
