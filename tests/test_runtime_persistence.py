from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ruflex.application.datasets import build_dataset_contract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.training import load_training_run, train_model
from ruflex.application.capabilities import negotiate_run_capabilities
from ruflex.domain.training import TrainingRun


def _dataset(root: Path) -> None:
    frame = pd.DataFrame({"x": range(32), "target": [value % 2 for value in range(32)]})
    artifact = persist_dataset_bytes(root, frame.to_csv(index=False).encode(), original_name="fixture.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=artifact.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)


def test_new_run_persists_runtime_identity_and_reopens(tmp_path: Path) -> None:
    _dataset(tmp_path)
    run = train_model(tmp_path, model_kind="decision_tree", seed=7, max_depth=2, validation_fraction=.2, test_fraction=.2)
    reopened = load_training_run(tmp_path, run.run_id)
    assert reopened.schema_version == 3
    assert reopened.adapter_key == "sklearn_decision_tree"
    assert reopened.runtime_capability_snapshot_hash
    assert negotiate_run_capabilities(reopened).decisions[0].status in {"AVAILABLE", "NOT_APPLICABLE"}


def test_legacy_run_without_runtime_identity_remains_inspectable() -> None:
    raw = TrainingRun.model_validate({
        "schema_version": 2, "model_kind": "decision_tree", "task": "binary_classification", "target": "target", "feature_columns": ["x"], "seed": 1,
        "max_epochs": 1, "learning_rate": 0.0, "batch_size": 1, "patience": None,
        "split": {"seed": 1, "validation_fraction": .2, "test_fraction": .2, "train_count": 1, "validation_count": 1, "test_count": 1},
        "model_spec": {}, "normalization": {}, "training_summary": {}, "trajectory": [], "validation_metrics": {}, "prediction_preview": [], "model_artifact_sha256": "a" * 64,
    })
    assert raw.adapter_key is None
    assert negotiate_run_capabilities(raw).decisions[0].status in {"AVAILABLE", "NOT_APPLICABLE"}


def test_legacy_run_with_missing_adapter_remains_inspectable_but_unavailable() -> None:
    raw = TrainingRun.model_validate({
        "schema_version": 2, "model_kind": "removed_adapter_model", "task": "binary_classification", "target": "target", "feature_columns": ["x"], "seed": 1,
        "max_epochs": 1, "learning_rate": 0.0, "batch_size": 1, "patience": None,
        "split": {"seed": 1, "validation_fraction": .2, "test_fraction": .2, "train_count": 1, "validation_count": 1, "test_count": 1},
        "model_spec": {}, "normalization": {}, "training_summary": {}, "trajectory": [], "validation_metrics": {}, "prediction_preview": [], "model_artifact_sha256": "b" * 64,
    })
    decisions = negotiate_run_capabilities(raw).decisions
    assert {item.status for item in decisions} == {"UNAVAILABLE_RUNTIME"}
    assert {item.reason_code for item in decisions} == {"CAPABILITY_UNAVAILABLE"}
