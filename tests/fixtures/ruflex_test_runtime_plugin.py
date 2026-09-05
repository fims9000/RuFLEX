"""Installed-entry-point fixture only; never imported by production code."""
from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np

from ruflex.runtime.contracts import FitRequest, FitResult, ModelAdapterDescriptor, PredictionRequest, PredictionResult, RuntimeIdentity


@dataclass(frozen=True)
class EntryPointFixtureAdapter:
    descriptor = ModelAdapterDescriptor(
        identity=RuntimeIdentity(key="entrypoint_fixture", version="1", provider="ruflex.tests", kind="model_adapter"),
        family="Test fixture", training_model_kinds=("entrypoint_fixture_model",), supported_tasks=("binary_classification",),
        capabilities={"fit": True, "predict": True, "predict_proba": True},
    )

    def fit(self, request: FitRequest) -> FitResult:
        raw = np.asarray(request.X_validation, dtype=float)[:, 0]
        return FitResult(serialized_artifact=json.dumps({"fixture": "entrypoint"}).encode(), artifact_media_type="application/vnd.ruflex.entrypoint-fixture+json", validation_raw_predictions=raw.tolist(), validation_raw_probabilities=(1 / (1 + np.exp(-raw))).tolist())

    def predict(self, request: PredictionRequest) -> PredictionResult:
        raw = np.asarray(request.features, dtype=float)[:, 0]
        probability = 1 / (1 + np.exp(-raw))
        return PredictionResult(prediction=(probability >= .5).astype(float).tolist(), probability=probability.tolist(), score=probability.tolist(), raw_score=raw.tolist())


def factory() -> EntryPointFixtureAdapter:
    return EntryPointFixtureAdapter()
