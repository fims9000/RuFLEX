"""Canonical persisted TrainingRun inference through its exact runtime adapter."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ruflex.application.artifacts import ArtifactRef, ArtifactStore
from ruflex.domain.training import TrainingRun
from ruflex.runtime.compatibility import resolve_run_adapter
from ruflex.runtime.contracts import PredictionRequest, PredictionResult
from ruflex.runtime.registry import RuntimeRegistry, builtin_runtime_registry
from ruflex.runtime.errors import RuntimeIncompatibleError


def predict_persisted_run(
    project_root: Path,
    run: TrainingRun,
    normalized_features: np.ndarray,
    *,
    registry: RuntimeRegistry | None = None,
) -> PredictionResult:
    """Load and replay one frozen artifact; never fit or dispatch on model_kind."""
    matrix = np.asarray(normalized_features, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    if matrix.ndim != 2 or matrix.shape[1] != len(run.feature_columns):
        raise RuntimeIncompatibleError("Persisted model inference input does not match the frozen feature order.")
    if not run.preprocessing_artifact_sha256:
        raise RuntimeIncompatibleError("Persisted model inference requires its frozen preprocessing identity.")
    adapter = resolve_run_adapter(run, registry=registry or builtin_runtime_registry())
    with ArtifactStore(project_root).open(ArtifactRef(sha256=run.model_artifact_sha256)) as handle:
        result = adapter.predict(PredictionRequest(
            task=run.task,
            feature_names=tuple(run.feature_columns),
            features=matrix,
            artifact=handle.read(),
            model_spec=run.model_spec,
            preprocessing_identity=run.preprocessing_artifact_sha256,
        ))
    _validate_prediction_result(result, task=run.task, expected_count=matrix.shape[0])
    return result


def _validate_prediction_result(result: PredictionResult, *, task: str, expected_count: int) -> None:
    prediction = np.asarray(result.prediction, dtype=float).reshape(-1)
    if prediction.size != expected_count or not np.all(np.isfinite(prediction)):
        raise RuntimeIncompatibleError("Model adapter returned missing, misaligned, or non-finite predictions.")
    if task != "binary_classification":
        return
    probability = None if result.probability is None else np.asarray(result.probability, dtype=float).reshape(-1)
    raw = None if result.raw_score is None else np.asarray(result.raw_score, dtype=float).reshape(-1)
    if probability is None and raw is None:
        raise RuntimeIncompatibleError("Binary model adapter replay must return a raw score or probability.")
    if probability is not None and (probability.size != expected_count or not np.all(np.isfinite(probability)) or np.any((probability < 0.0) | (probability > 1.0))):
        raise RuntimeIncompatibleError("Model adapter returned invalid binary probabilities.")
    if raw is not None and (raw.size != expected_count or not np.all(np.isfinite(raw))):
        raise RuntimeIncompatibleError("Model adapter returned invalid binary raw scores.")
    if probability is not None and raw is not None:
        raw_probability = 1.0 / (1.0 + np.exp(-np.clip(raw, -60.0, 60.0)))
        if not np.allclose(probability, raw_probability, rtol=1e-10, atol=1e-12):
            raise RuntimeIncompatibleError("Model adapter raw scores and probabilities use inconsistent class semantics.")


def raw_prediction(result: PredictionResult, *, task: str) -> np.ndarray:
    """Return the historical RuFLEX raw-score semantics for frozen replay."""
    if task == "regression":
        return np.asarray(result.prediction, dtype=float).reshape(-1)
    if result.raw_score is not None:
        return np.asarray(result.raw_score, dtype=float).reshape(-1)
    if result.probability is None:
        raise RuntimeIncompatibleError("Binary model adapter replay must return a raw score or probability.")
    probability = np.clip(np.asarray(result.probability, dtype=float).reshape(-1), 1e-12, 1.0 - 1e-12)
    return np.log(probability / (1.0 - probability))


def probability_prediction(result: PredictionResult, *, task: str) -> np.ndarray:
    """Return binary probabilities from the same adapter result used everywhere."""
    if task != "binary_classification":
        raise RuntimeIncompatibleError("Probability prediction is only defined for binary classification.")
    if result.probability is not None:
        return np.asarray(result.probability, dtype=float).reshape(-1)
    if result.raw_score is None:
        raise RuntimeIncompatibleError("Binary model adapter replay must return a raw score or probability.")
    raw = np.asarray(result.raw_score, dtype=float).reshape(-1)
    return 1.0 / (1.0 + np.exp(-np.clip(raw, -60.0, 60.0)))
