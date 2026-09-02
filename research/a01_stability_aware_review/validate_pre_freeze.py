"""Fail-closed validation of the A01 locked pre-final-test protocol."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research.a01_stability_aware_review.core import CONFIG, PRODUCT_SNAPSHOT, build_execution_plan, canonical_json, config_hash, load_json, sha256_bytes


def _error(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def _plan_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _final_test_artifacts(base: Path) -> list[Path]:
    found: list[Path] = []
    for relative in ("artifacts/final-test", "artifacts/final_test", "artifacts/results", "results", "final-test"):
        path = base / relative
        if path.exists() and any(path.rglob("*")):
            found.append(path)
    return found


def validate(base: Path = Path(__file__).parent) -> list[str]:
    errors: list[str] = []
    config = base / "config"
    required = ["pre_freeze_plan.json", "dataset_specs.json", "model_specs.json", "locked_execution_plan.jsonl", "locked_protocol.json", "locked_manifest.json"]
    for name in required:
        _error(errors, (config / name).is_file(), f"missing locked A01 config: {name}")
    if errors:
        return errors
    plan = load_json(config / "pre_freeze_plan.json")
    datasets = load_json(config / "dataset_specs.json")
    models = load_json(config / "model_specs.json")
    protocol = load_json(config / "locked_protocol.json")
    manifest = load_json(config / "locked_manifest.json")
    rows = _plan_rows(config / "locked_execution_plan.jsonl")
    _error(errors, plan.get("status") == "PRE_FREEZE_NO_FINAL_TEST_ACCESS", "status must remain PRE_FREEZE_NO_FINAL_TEST_ACCESS")
    _error(errors, plan.get("primary_protocol") == "TRAINING_VARIABILITY", "primary protocol must isolate training variability")
    _error(errors, plan.get("split_seed") == 42, "primary split_seed must be exactly 42")
    _error(errors, plan.get("split_fractions") == {"train": .6, "validation": .2, "final_test": .2}, "split fractions must be fixed at 0.60/0.20/0.20")
    seeds = plan.get("training_seeds", [])
    _error(errors, seeds == list(range(20)) and len(set(seeds)) == 20, "primary training seeds must be exactly 0..19 once each")
    _error(errors, plan.get("selected_run_rule") == {"primary_metric": "validation_f1", "selection": "max", "tie_break": "lowest_training_seed"}, "selected-run rule must be validation F1 max with lowest training-seed tie-break")
    _error(errors, plan.get("decision_threshold") == {"objective": "f1", "probability_source": "raw", "calibration_id": None, "scope": "validation_only"}, "decision threshold must be raw validation F1 evidence")
    gate = plan.get("validation_only_policy", {})
    _error(errors, gate.get("min_confidence") == .9, "A01 confidence constant must be exactly 0.90")
    _error(errors, gate.get("min_class_agreement") == .8, "A01 selected-run agreement constant must be exactly 0.80")
    _error(errors, gate.get("max_probability_std") == .15, "A01 probability-dispersion constant must be exactly 0.15")
    _error(errors, gate.get("probability_source") == "raw" and gate.get("constants_status") == "PRE_SPECIFIED_PRE_FINAL_TEST", "gate must use pre-specified raw probability constants")
    _error(errors, plan.get("hcir") == {"confidence_source": "selected_run_raw_probability", "high_confidence": .9, "agreement_source": "selected_run_agreement", "unstable_agreement": .8, "zero_denominator": "null_na"}, "HCIR must use selected-run agreement and null/N/A zero denominator")
    _error(errors, plan.get("calibration", {}).get("operational_gate_input") is False, "calibration cannot be an A01 operational gate input")
    _error(errors, plan.get("explanation_reproducibility", {}).get("operational_gate_input") is False, "explanation evidence cannot be an A01 operational gate input")
    _error(errors, plan.get("declared_run_support") == {"required_runs_per_dataset_model": 20, "failure_status": "INCOMPLETE_DECLARED_RUN_SUPPORT", "replacement_seed": "FORBIDDEN"}, "A01 must fail closed on incomplete 20-run support")
    _error(errors, plan.get("final_test") == "FORBIDDEN_UNTIL_SEPARATE_CONFIRMATORY_AUTHORIZATION", "final-test execution must remain forbidden")
    expected_datasets = {"ai4i_2020", "uci_bank_marketing", "wisconsin_diagnostic"}
    expected_models = {"logistic_regression", "decision_tree", "random_forest", "gradient_boosting", "flat_neuro_fuzzy"}
    _error(errors, {item.get("canonical_dataset_id") for item in datasets.get("datasets", [])} == expected_datasets, "locked datasets differ from the declared A01 matrix")
    _error(errors, {item.get("model_family") for item in models.get("models", [])} == expected_models, "locked model families differ from the declared A01 matrix")
    for item in datasets.get("datasets", []):
        _error(errors, len(item.get("raw_file_sha256", "")) == 64 and len(item.get("materialized_table_sha256", "")) == 64, f"dataset {item.get('canonical_dataset_id')} lacks locked raw/materialized SHA-256")
        _error(errors, item.get("split_seed") == 42 and item.get("split_fractions") == plan.get("split_fractions"), f"dataset {item.get('canonical_dataset_id')} split contract differs from A01")
        split_ids = item.get("split_identities", {})
        _error(errors, set(split_ids) == {"train", "validation", "final_test"} and all(isinstance(value, str) and len(value) == 64 for value in split_ids.values()), f"dataset {item.get('canonical_dataset_id')} lacks frozen split identities")
        _error(errors, item.get("preprocessing", {}).get("fit_scope") == "TRAIN_ONLY", f"dataset {item.get('canonical_dataset_id')} preprocessing is not train-only")
        _error(errors, bool(item.get("feature_columns")) and bool(item.get("row_identity")), f"dataset {item.get('canonical_dataset_id')} lacks feature/row identity")
    for item in models.get("models", []):
        _error(errors, item.get("preprocessing_identity") == "standard-median-train-only/v1" and bool(item.get("product_request")), f"model {item.get('model_family')} lacks fixed product preprocessing/config")
    dataset_hash = config_hash(config / "dataset_specs.json")
    model_hash = config_hash(config / "model_specs.json")
    protocol_hash = sha256_bytes((base / "PROTOCOL.md").read_bytes())
    plan_hash = sha256_bytes((config / "locked_execution_plan.jsonl").read_bytes())
    expected_rows = build_execution_plan({**datasets, "dataset_spec_sha256": dataset_hash}, {**models, "model_spec_sha256": model_hash}, plan)
    _error(errors, rows == expected_rows, "locked execution plan is not the deterministic 300-run A01 matrix")
    _error(errors, len(rows) == 300 and len({row.get("execution_id") for row in rows}) == 300, "locked execution plan must contain 300 unique declared runs")
    _error(errors, all(row.get("final_test_execution") == "FORBIDDEN_UNTIL_SEPARATE_AUTHORIZATION" for row in rows), "execution plan permits a final-test run")
    _error(errors, protocol.get("product_source_snapshot") == PRODUCT_SNAPSHOT, "locked protocol does not reference the accepted RC2 product snapshot")
    _error(errors, protocol.get("protocol_document_sha256") == protocol_hash and protocol.get("dataset_spec_sha256") == dataset_hash and protocol.get("model_spec_sha256") == model_hash and protocol.get("execution_plan_sha256") == plan_hash, "locked protocol identity does not match actual frozen inputs")
    _error(errors, protocol.get("expected_training_runs") == 300, "locked protocol must declare 300 primary runs")
    _error(errors, manifest.get("locked_protocol_sha256") == sha256_bytes((config / "locked_protocol.json").read_bytes()), "manifest does not bind the exact locked protocol")
    manifest_without_id = dict(manifest); manifest_id = manifest_without_id.pop("manifest_id", None)
    _error(errors, manifest_id == sha256_bytes(canonical_json(manifest_without_id).encode("utf-8")), "manifest identity is invalid")
    _error(errors, not _final_test_artifacts(base), "A01 final-test artifact exists before authorization")
    return errors


if __name__ == "__main__":
    issues = validate()
    if issues:
        raise SystemExit("A01 pre-freeze validation failed: " + "; ".join(issues))
    print("A01 PROTOCOL LOCK READY — FINAL TEST NOT ACCESSED")
