from __future__ import annotations

from pathlib import Path

from research.a01_stability_aware_review.core import declared_run_support_status
from research.a01_stability_aware_review.statistics import validation_matched_confidence_cutoff


ROOT = Path(__file__).resolve().parents[1] / "research" / "a01_stability_aware_review"


def test_a01_primary_declared_support_requires_all_twenty_fixed_seeds() -> None:
    success = declared_run_support_status(list(range(20)), {seed: "SUCCEEDED" for seed in range(20)})
    assert success["status"] == "READY_FOR_PRE_FINAL_EVIDENCE"
    incomplete = declared_run_support_status(list(range(20)), {seed: "SUCCEEDED" for seed in range(19)})
    assert incomplete["status"] == "INCOMPLETE_DECLARED_RUN_SUPPORT"
    assert incomplete["missing_or_failed_training_seeds"] == [19]
    assert incomplete["replacement_seed_permitted"] is False


def test_a01_comparator_is_validation_matched_and_deterministic() -> None:
    result = validation_matched_confidence_cutoff([.52, .8, .8, .95], .5)
    # Both .80 and .95 are equally close to 0.50 coverage; the frozen tie
    # rule chooses the higher confidence cutoff.
    assert result == {"confidence_cutoff": .95, "validation_coverage": .25, "absolute_coverage_gap": .25}


def test_phase1_orchestrator_has_no_final_test_execution_path() -> None:
    source = (ROOT / "scripts" / "execute_phase1_validation.py").read_text(encoding="utf-8")
    assert "evaluate_final_test" not in source
    assert "FinalTestEvaluation" not in source


def test_phase1_validator_requires_exactly_frozen_gate_constants() -> None:
    source = (ROOT / "validate_phase1_validation_freeze.py").read_text(encoding="utf-8")
    assert "gate.min_confidence == .9" in source
    assert "gate.min_class_agreement == .8" in source
    assert "gate.max_probability_std == .15" in source
    assert "FINAL_TEST_NOT_OPENED" in source
