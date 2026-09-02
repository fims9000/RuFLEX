from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from research.a01_stability_aware_review.scripts.build_phase0_5_manifest import build
from research.a01_stability_aware_review.statistics import (
    accepted_case_risk,
    h3_interpretation,
    paired_bootstrap_delta_risk,
    select_illustrative_cases,
    validate_result_statuses,
    validation_matched_confidence_cutoff,
)
from research.a01_stability_aware_review.validate_pre_freeze import validate


SOURCE = Path(__file__).resolve().parents[1] / "research" / "a01_stability_aware_review"


def _copy_protocol(tmp_path: Path) -> Path:
    target = tmp_path / "a01"
    shutil.copytree(SOURCE, target, ignore=shutil.ignore_patterns("artifacts", "__pycache__"))
    return target


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _mutated_plan_fails(tmp_path: Path, name: str, mutate) -> None:
    root = _copy_protocol(tmp_path / name)
    path = root / "config" / "statistical_analysis_plan.json"
    plan = _json(path)
    mutate(plan)
    _write(path, plan)
    assert validate(root), name


def test_complete_phase0_5_statistical_freeze_passes() -> None:
    assert validate(SOURCE) == []


def test_phase0_identity_change_fails(tmp_path: Path) -> None:
    root = _copy_protocol(tmp_path)
    with (root / "PROTOCOL.md").open("a", encoding="utf-8") as handle:
        handle.write("\nChanged after Phase 0.\n")
    assert any("Phase 0 identities" in issue for issue in validate(root))


@pytest.mark.parametrize(
    ("name", "mutate"),
    [
        ("bootstrap-seed", lambda plan: plan["bootstrap"].__setitem__("rng_seed", 1)),
        ("bootstrap-count", lambda plan: plan["bootstrap"].__setitem__("replicates", 999)),
        ("ci-level", lambda plan: plan["bootstrap"]["ci"].__setitem__("level", .9)),
        ("effect-direction", lambda plan: plan["h3"]["effect"].__setitem__("delta_risk", "R_confidence - R_stability")),
        ("coverage-rule", lambda plan: plan["h3"]["validation_matched_coverage"].__setitem__("selection", "match final-test coverage")),
        ("missing-zero-denominator", lambda plan: plan["h2"].pop("zero_denominator")),
        ("missing-invalid-bootstrap", lambda plan: plan["bootstrap"].pop("minimum_valid_fraction")),
        ("majority-operational", lambda plan: plan["h2"].__setitem__("agreement_source", "majority_class_agreement")),
        ("final-test-comparator", lambda plan: plan["h3"]["validation_matched_coverage"].__setitem__("source_split", "final_test")),
        ("generic-pass", lambda plan: plan["result_schema"].__setitem__("h1_status", ["PASS"])),
    ],
)
def test_statistical_plan_mutations_fail_closed(tmp_path: Path, name: str, mutate) -> None:
    _mutated_plan_fails(tmp_path, name, mutate)


def test_result_schema_rejects_generic_scientific_pass() -> None:
    assert validate_result_statuses({"h1_status": "PASS", "h2_status": "PATTERN_OBSERVED", "h3_by_model_family": ["SUPPORTS_H3"]})


def test_deterministic_case_example_selection() -> None:
    cases = [
        {"case_id": "c", "selected_run_agreement": .4, "selected_run_confidence": .91},
        {"case_id": "b", "selected_run_agreement": .4, "selected_run_confidence": .91},
        {"case_id": "a", "selected_run_agreement": .4, "selected_run_confidence": .94},
    ]
    assert select_illustrative_cases(cases, limit=3) == ["a", "b", "c"]


def test_phase0_5_manifest_rebuild_is_byte_stable(tmp_path: Path) -> None:
    root = _copy_protocol(tmp_path)
    first = build(root / "config")
    first_bytes = (root / "config" / "phase0_5_manifest.json").read_bytes()
    second = build(root / "config")
    assert first == second
    assert first_bytes == (root / "config" / "phase0_5_manifest.json").read_bytes()


def test_benchmark_artifact_invalidates_pre_execution_state(tmp_path: Path) -> None:
    root = _copy_protocol(tmp_path)
    artifact = root / "artifacts" / "benchmark-results" / "forbidden.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}", encoding="utf-8")
    assert any("benchmark training/result artifact" in issue for issue in validate(root))


def test_statistics_primitives_preserve_undefined_not_zero() -> None:
    risk = accepted_case_risk([1, 0], [1, 0], ["REVIEW", "BLOCK"])
    assert risk.accepted_risk is None and risk.reason_codes == ("ZERO_ACCEPTED_CASES",)
    result = paired_bootstrap_delta_risk([1, 0], [1, 0], ["REVIEW", "REVIEW"], ["ACCEPT", "ACCEPT"], replicates=10, seed=20260902)
    assert result["delta_risk_percentile_ci_95"] is None
    assert result["reason_codes"] == ["INSUFFICIENT_VALID_BOOTSTRAPS"]


def test_matched_coverage_and_h3_interpretation_are_frozen_primitives() -> None:
    matched = validation_matched_confidence_cutoff([.1, .4, .7, .9], .5)
    assert matched == {"confidence_cutoff": .7, "validation_coverage": .5, "absolute_coverage_gap": 0.0}
    assert h3_interpretation([-.3, -.01]) == "SUPPORTS_H3"
    assert h3_interpretation([.01, .3]) == "CONTRADICTS_H3"
    assert h3_interpretation([-.01, .01]) == "INCONCLUSIVE"
    assert h3_interpretation(None) == "NOT_ASSESSABLE"
