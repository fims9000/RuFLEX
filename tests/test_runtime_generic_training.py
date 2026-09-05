from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ruflex.application.datasets import build_dataset_contract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.runtime_training import train_with_adapter
from ruflex.application.training import load_training_run
from ruflex.runtime.contracts import FitRequest, FitResult, ModelAdapterDescriptor, PredictionRequest, PredictionResult, RuntimeIdentity
from ruflex.runtime.registry import RuntimeRegistry


@dataclass(frozen=True)
class FixtureAdapter:
    descriptor = ModelAdapterDescriptor(
        identity=RuntimeIdentity(key="fixture_adapter", version="1", provider="ruflex.tests", kind="model_adapter"),
        family="Fixture", training_model_kinds=("fixture_model",), supported_tasks=("binary_classification",),
        capabilities={"fit": True, "predict": True, "predict_proba": True},
    )

    def fit(self, request: FitRequest) -> FitResult:
        assert not hasattr(request, "X_test")
        raw = np.asarray(request.X_validation, dtype=float)[:, 0] - .5
        return FitResult(serialized_artifact=json.dumps({"fixture": True}).encode(), artifact_media_type="application/vnd.ruflex.fixture+json", model_spec={"fixture": True}, training_summary={"epochs_ran": 1}, validation_raw_predictions=raw.tolist(), validation_raw_probabilities=(1 / (1 + np.exp(-raw))).tolist())

    def predict(self, request: PredictionRequest) -> PredictionResult:
        raw = np.asarray(request.features, dtype=float)[:, 0] - .5
        return PredictionResult(prediction=(raw >= 0).astype(float).tolist(), raw_score=raw.tolist(), probability=(1 / (1 + np.exp(-raw))).tolist())


def _project(root: Path) -> None:
    frame = pd.DataFrame({"x": range(40), "target": [index % 2 for index in range(40)]})
    source = persist_dataset_bytes(root, frame.to_csv(index=False).encode())
    profile = inspect_dataset(frame, source_artifact_sha256=source.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)


def test_generic_core_service_persists_external_adapter_without_project_access(tmp_path: Path) -> None:
    _project(tmp_path)
    registry = RuntimeRegistry()
    registry.register_model_adapter(FixtureAdapter())
    registry.freeze()
    run = train_with_adapter(tmp_path, registry=registry, adapter_key="fixture_adapter", model_kind="fixture_model", seed=4)
    reopened = load_training_run(tmp_path, run.run_id)
    assert reopened.adapter_key == "fixture_adapter"
    assert reopened.model_kind == "fixture_model"
    assert reopened.preprocessing_artifact_sha256
    assert reopened.split.test_status == "LOCKED_NOT_EVALUATED"
