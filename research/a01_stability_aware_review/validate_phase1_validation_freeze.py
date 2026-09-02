"""Fail-closed validator for A01 Phase 1 validation evidence.

It intentionally validates a different state from ``validate_pre_freeze``:
benchmark training has occurred, but final-test evidence remains forbidden.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from research.a01_stability_aware_review.core import ROOT, canonical_json, config_hash, load_json, sha256_bytes
from research.a01_stability_aware_review.scripts.build_phase0_5_manifest import PHASE0_IDENTITIES
from research.a01_stability_aware_review.statistics import validation_matched_confidence_cutoff
from ruflex.application.selective import load_selective_policy
from ruflex.application.stability import load_stability_gate_policy, load_study_stability_analysis
from ruflex.application.training import load_decision_threshold, load_training_study, load_validation_evaluation


RESULTS = ROOT / "results" / "phase1_validation"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _error(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def validate(base: Path = ROOT) -> list[str]:
    errors: list[str] = []
    root = base / "results" / "phase1_validation"
    config = base / "config"
    expected = ["phase1_execution_manifest.json", "run_ledger.jsonl", "cell_status.jsonl", "selected_runs.json", "validation_observations.json", "phase1_validation_freeze_manifest.json", "FINAL_TEST_FIREWALL_RECEIPT.json"]
    for name in expected:
        _error(errors, (root / name).is_file(), f"missing Phase 1 artifact: {name}")
    if errors:
        return errors
    execution = load_json(root / "phase1_execution_manifest.json")
    freeze = load_json(root / "phase1_validation_freeze_manifest.json")
    firewall = load_json(root / "FINAL_TEST_FIREWALL_RECEIPT.json")
    ledger = _rows(root / "run_ledger.jsonl")
    cells = _rows(root / "cell_status.jsonl")
    bindings = load_json(root / "selected_runs.json")
    observations = load_json(root / "validation_observations.json")
    _error(errors, execution.get("status") == "VALIDATION_EXECUTED_FINAL_TEST_CLOSED" and execution.get("declared_runs") == 300, "Phase 1 execution manifest does not declare the exact validation-only matrix")
    _error(errors, len(cells) == 15 and len({(row.get("dataset_id"), row.get("model_family")) for row in cells}) == 15, "Phase 1 must contain exactly fifteen dataset/model cells")
    _error(errors, len(ledger) == 300 and len({(row.get("dataset_id"), row.get("model_family"), row.get("training_seed")) for row in ledger}) == 300, "run ledger must contain exactly the 300 declared unique executions")
    _error(errors, all(row.get("split_seed") == 42 and row.get("training_seed") in range(20) for row in ledger), "ledger contains altered split or replacement training seeds")
    _error(errors, all(row.get("status") == "SUCCEEDED" for row in ledger), "A01 Phase 1 is incomplete: every declared seed must succeed")
    _error(errors, len(bindings) == len(observations) == 15, "every complete cell needs exactly one binding and validation observation")
    _error(errors, firewall == {"final_test_artifacts": [], "statement": "NO A01 FINAL-TEST DATA ACCESSED", "status": "PASS", "timestamp": firewall.get("timestamp")}, "final-test firewall receipt is malformed")
    _error(errors, execution.get("final_test_access") == "CLOSED" and freeze.get("final_test_access") == "CLOSED", "Phase 1 must keep final test closed")
    phase0_manifest = load_json(config / "locked_manifest.json")
    phase0_without_id = dict(phase0_manifest); actual_phase0_manifest_id = phase0_without_id.pop("manifest_id", None)
    actual_phase0 = {
        "protocol_sha256": sha256_bytes((base / "PROTOCOL.md").read_bytes()),
        "dataset_spec_sha256": config_hash(config / "dataset_specs.json"),
        "model_spec_sha256": config_hash(config / "model_specs.json"),
        "execution_plan_sha256": sha256_bytes((config / "locked_execution_plan.jsonl").read_bytes()),
        "phase0_manifest_id": actual_phase0_manifest_id,
    }
    _error(errors, actual_phase0 == PHASE0_IDENTITIES, "one or more frozen Phase 0 identities changed")
    phase0_5 = load_json(config / "phase0_5_manifest.json")
    _error(errors, phase0_5.get("phase0_5_manifest_id") == freeze.get("phase0_5_manifest_id") == "89d1618fb2ecab090ea6ca98ab6e54c91aa87f3a8be6a329696ba40c1dc838cd" and phase0_5.get("statistical_analysis_plan_sha256") == "59c411cf345350e012bcb9011ba56192f4e796e787fe5ce40ed05a68fc8c707d", "Phase 0.5 manifest/statistical-plan provenance changed")
    _error(errors, execution.get("environment", {}).get("execution_plan_sha256") == PHASE0_IDENTITIES["execution_plan_sha256"] and execution.get("environment", {}).get("model_spec_sha256") == PHASE0_IDENTITIES["model_spec_sha256"] and execution.get("environment", {}).get("statistical_analysis_plan_sha256") == phase0_5.get("statistical_analysis_plan_sha256"), "execution environment receipt does not bind frozen Phase 0/0.5 identities")
    for binding in bindings:
        project = Path(binding["project_root"])
        try:
            study = load_training_study(project, UUID(binding["study_id"]))
            evaluation = load_validation_evaluation(project, UUID(binding["evaluation_id"]))
            threshold = load_decision_threshold(project, UUID(binding["threshold_id"]))
            analysis = load_study_stability_analysis(project, UUID(binding["stability_analysis_id"]))
            gate = load_stability_gate_policy(project, UUID(binding["stability_gate_policy_id"]))
            comparator = load_selective_policy(project, UUID(binding["confidence_only_policy_id"]))
        except (FileNotFoundError, ValueError, KeyError) as error:
            errors.append(f"cannot reopen frozen cell {binding.get('dataset_id')}/{binding.get('model_family')}: {error}")
            continue
        _error(errors, len(study.seed_runs) == 20 and study.randomness_protocol == "TRAINING_VARIABILITY" and study.split_seed == 42, f"study provenance invalid for {binding['dataset_id']}/{binding['model_family']}")
        ordered = sorted(study.seed_runs, key=lambda run: (-float(run.validation_metrics["f1"]), int(run.training_seed if run.training_seed is not None else run.seed)))
        _error(errors, study.selected_run_id == ordered[0].run_id == UUID(binding["selected_run_id"]), f"selected run violates frozen F1/tie rule for {binding['dataset_id']}/{binding['model_family']}")
        _error(errors, threshold.evaluation_id == evaluation.evaluation_id and threshold.run_id == study.selected_run_id and threshold.probability_source == "raw" and threshold.calibration_id is None, f"raw validation threshold provenance invalid for {binding['dataset_id']}/{binding['model_family']}")
        _error(errors, analysis.study_id == study.study_id and analysis.evaluation_id == evaluation.evaluation_id and analysis.class_threshold_id == threshold.threshold_id and analysis.decision_threshold == threshold.selected_threshold and analysis.validation_alignment_status == "EXACT_MATCH" and len(analysis.run_ids) == 20, f"stability analysis provenance invalid for {binding['dataset_id']}/{binding['model_family']}")
        _error(errors, gate.min_confidence == .9 and gate.min_class_agreement == .8 and gate.max_probability_std == .15 and gate.probability_source == "raw" and gate.class_threshold_id == threshold.threshold_id, f"frozen Stability Gate constants/provenance invalid for {binding['dataset_id']}/{binding['model_family']}")
        confidences = [max(case.selected_run_probability, 1 - case.selected_run_probability) for case in analysis.cases]
        coverage = sum(decision.disposition == "ACCEPT" for decision in gate.decisions) / len(gate.decisions)
        matched = validation_matched_confidence_cutoff(confidences, coverage)
        _error(errors, comparator.run_id == study.selected_run_id and comparator.class_threshold_id == threshold.threshold_id and comparator.calibration_id is None and comparator.confidence_cutoff == matched["confidence_cutoff"], f"A01 validation-matched comparator provenance invalid for {binding['dataset_id']}/{binding['model_family']}")
        _error(errors, binding.get("h3_status") == "NOT_ASSESSABLE" and binding.get("h3_reason") == "FINAL_TEST_NOT_OPENED", f"H3 must remain unassessable in Phase 1 for {binding['dataset_id']}/{binding['model_family']}")
    frozen_files = [path for path in sorted(root.rglob("*")) if path.is_file() and path.name not in {"phase1_validation_freeze_manifest.json", "run_ledger_live.jsonl"}]
    actual_inputs = {path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes()) for path in frozen_files}
    _error(errors, freeze.get("inputs") == actual_inputs, "Phase 1 manifest does not hash every frozen validation artifact exactly")
    manifest_without_id = dict(freeze); manifest_id = manifest_without_id.pop("phase1_validation_freeze_manifest_id", None)
    _error(errors, manifest_id == sha256_bytes(canonical_json(manifest_without_id).encode()), "Phase 1 freeze manifest identity is invalid")
    return errors


if __name__ == "__main__":
    issues = validate()
    if issues:
        raise SystemExit("A01 Phase 1 validation freeze failed: " + "; ".join(issues))
    print("A01 PHASE 1 VALIDATION EXECUTION COMPLETE — POLICIES FROZEN — FINAL TEST CLOSED")
