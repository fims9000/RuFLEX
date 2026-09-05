from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ruflex.application.datasets import build_dataset_contract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.runtime_training import train_with_adapter
from ruflex.application.training import load_training_run
from ruflex.application.artifacts import ArtifactRef, ArtifactStore
from ruflex.runtime.contracts import FitRequest, FitResult, ModelAdapterDescriptor, PredictionRequest, PredictionResult, RuntimeIdentity
from ruflex.runtime.registry import RuntimeRegistry
from ruflex.runtime import builtin_runtime_registry


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


@pytest.mark.parametrize("adapter_key,model_kind,parameters", [
    ("ruflex_flat_neuro_fuzzy", "flat_neuro_fuzzy", {"max_epochs": 2, "batch_size": 16, "patience": 2, "max_rules": 3, "learning_rate": .01}),
    ("sklearn_linear", "logistic_regression", {}),
    ("sklearn_decision_tree", "decision_tree", {"max_depth": 2}),
    ("sklearn_random_forest", "random_forest", {"n_estimators": 3}),
    ("sklearn_gradient_boosting", "gradient_boosting", {"n_estimators": 3, "learning_rate": .1, "max_depth": 2}),
])
def test_generic_core_service_executes_builtin_sklearn_adapters(tmp_path: Path, adapter_key: str, model_kind: str, parameters: dict) -> None:
    _project(tmp_path)
    run = train_with_adapter(tmp_path, registry=builtin_runtime_registry(), adapter_key=adapter_key, model_kind=model_kind, seed=8, parameters=parameters)
    assert run.adapter_key == adapter_key
    assert run.model_artifact_sha256
    assert run.validation_metrics
    with ArtifactStore(tmp_path).open(ArtifactRef(sha256=run.model_artifact_sha256)) as handle:
        result = builtin_runtime_registry().resolve_model_adapter(adapter_key).predict(PredictionRequest(task="binary_classification", feature_names=("x",), features=np.asarray([[.2], [.8]]), artifact=handle.read(), model_spec=run.model_spec, preprocessing_identity=run.preprocessing_artifact_sha256 or ""))
    assert len(result.prediction) == 2
    assert result.probability is not None
