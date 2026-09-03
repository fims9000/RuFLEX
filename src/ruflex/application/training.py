from __future__ import annotations

import json
import hashlib
import math
import os
import random
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from uuid import UUID

import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, average_precision_score, f1_score, mean_absolute_error, mean_squared_error, precision_score, r2_score, recall_score, roc_auc_score

from ruflex.application.artifacts import ArtifactMetadata, ArtifactRef, ArtifactStore
from ruflex.application.execution import local_executor
from ruflex.application.datasets import load_dataset_contract, load_dataset_frame, row_identity
from ruflex.core.enums import NormalizationMode, TaskType, VariableRole
from ruflex.core.membership import GaussianMembershipSpec
from ruflex.core.variables import VariableSpec
from ruflex.data.datasets import DatasetConfig, NormalizationArtifact, TabularDataset
from ruflex.domain.training import AnalysisComparison, AnalysisEvaluation, FinalTestEvaluation, FinalTestStabilityCase, FinalTestStabilityEvidence, CalibratedPrediction, CalibrationBin, CalibrationProvenance, CalibrationTransform, ConfusionMatrix, DecisionThresholdPolicy, EpochPoint, PredictionRow, SplitProvenance, StudyJob, StudySeedState, ThresholdDecision, ThresholdProvenance, TrainingRun, TrainingStudy, TreePathEvidence, TreePathStep
from ruflex.models.flat_nf.model import FlatNeuroFuzzyModel
from ruflex.models.specs import DecisionLayerSpec, ShallowModelSpec, TransparentBlockSpec
from ruflex.training.config import FineTuningOptions, ModelTrainingConfig, RefinementOptions, StagewiseOptions


class TrainingError(RuntimeError):
    pass


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".training-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _resolve_randomness(
    *, seed: int | None = None, split_seed: int | None = None, training_seed: int | None = None,
) -> tuple[int, int, str]:
    """Resolve explicit randomness without changing legacy one-seed projects.

    A legacy caller that supplies only ``seed`` intentionally retains its old
    coupled behaviour.  New callers supply both values and the split is then
    independent from stochastic model fitting.
    """
    legacy = seed if seed is not None else 42
    resolved_split = legacy if split_seed is None else split_seed
    resolved_training = legacy if training_seed is None else training_seed
    protocol = "LEGACY_COMBINED" if split_seed is None and training_seed is None else "SINGLE_RUN_EXPLICIT"
    return int(resolved_split), int(resolved_training), protocol


def _split_identity(dataset_fingerprint: str | None, split) -> str:
    payload = {
        "dataset_fingerprint": dataset_fingerprint,
        "train_source_rows": [int(value) for value in split.train_indices],
        "validation_source_rows": [int(value) for value in split.validation_indices],
        "test_source_rows": [int(value) for value in split.test_indices],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _provenance(contract, split, *, split_seed: int, validation_fraction: float, test_fraction: float) -> SplitProvenance:
    return SplitProvenance(
        seed=split_seed,
        split_seed=split_seed,
        split_identity=_split_identity(contract.dataset_fingerprint, split),
        validation_fraction=validation_fraction,
        test_fraction=test_fraction,
        train_count=int(split.train_features.shape[0]),
        validation_count=int(split.validation_features.shape[0]),
        test_count=int(split.test_features.shape[0]),
    )


def _runs_root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "runs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _active_run_path(project_root: Path) -> Path:
    return _runs_root(project_root) / "active-training-run.json"


def _studies_root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "studies"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _study_jobs_root(project_root: Path) -> Path:
    root = _studies_root(project_root) / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _study_job_path(project_root: Path, job_id: UUID) -> Path:
    return _study_jobs_root(project_root) / f"{job_id}.json"


_study_job_cancellations: dict[UUID, Event] = {}


def _evaluations_root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "analyses" / "evaluations"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _comparisons_root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "analyses" / "comparisons"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _final_tests_root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "analyses" / "final-tests"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _final_test_path(project_root: Path, final_test_id: UUID) -> Path:
    return _final_tests_root(project_root) / f"{final_test_id}.json"


def _calibrations_root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "analyses" / "calibrations"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _thresholds_root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "analyses" / "thresholds"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _tree_evidence_root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "evidence" / "tree-paths"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _run_path(project_root: Path, run_id: UUID) -> Path:
    return _runs_root(project_root) / f"{run_id}.json"


def _evaluation_path(project_root: Path, evaluation_id: UUID) -> Path:
    return _evaluations_root(project_root) / f"{evaluation_id}.json"


def _calibration_path(project_root: Path, calibration_id: UUID) -> Path:
    return _calibrations_root(project_root) / f"{calibration_id}.json"


def _threshold_path(project_root: Path, threshold_id: UUID) -> Path:
    return _thresholds_root(project_root) / f"{threshold_id}.json"


def _stable_identity(prefix: str, payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()}"


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _make_input_variable(frame, column: str, *, term_count: int = 3) -> VariableSpec:
    series = frame[column].dropna().astype(float)
    if series.empty:
        raise TrainingError(f"Feature {column!r} has no numeric values.")
    low = float(series.min())
    high = float(series.max())
    if math.isclose(low, high):
        high = low + 1.0
    centers = np.linspace(low, high, term_count)
    span = max(high - low, 1e-6)
    spread = max(span / max(term_count - 1, 1), 1e-3)
    return VariableSpec(
        name=column,
        membership=GaussianMembershipSpec(
            centers=tuple(float(value) for value in centers),
            spreads=tuple(float(spread) for _ in centers),
            term_names=tuple(f"term_{index + 1}" for index in range(term_count)),
        ),
        value_range=(low, high),
        role=VariableRole.INPUT,
        normalization=NormalizationMode.STANDARD,
    )


def _make_concept_variable(name: str) -> VariableSpec:
    return VariableSpec(
        name=name,
        membership=GaussianMembershipSpec(
            centers=(0.25, 0.75),
            spreads=(0.20, 0.20),
            term_names=("low", "high"),
        ),
        value_range=(0.0, 1.0),
        role=VariableRole.HIDDEN_CONCEPT,
        normalization=NormalizationMode.NONE,
    )


def _build_flat_spec(frame, feature_columns: list[str], *, max_rules: int = 8) -> ShallowModelSpec:
    variables = tuple(_make_input_variable(frame, column) for column in feature_columns)
    concept_count = max(1, min(4, len(variables)))
    concept_names = tuple(f"flat_concept_{index + 1}" for index in range(concept_count))
    feature_block = TransparentBlockSpec(
        name="flat_feature_block",
        input_indices=tuple(range(len(variables))),
        variables=variables,
        n_concepts=concept_count,
        concept_names=concept_names,
        max_rule_arity=min(2, len(variables)),
        max_rules=max_rules,
        rule_generation_mode="prototype",
    )
    decision_variables = tuple(_make_concept_variable(name) for name in concept_names)
    decision_layer = DecisionLayerSpec(
        name="flat_decision",
        variables=decision_variables,
        output_dim=1,
        output_names=("target",),
        max_rule_arity=min(2, len(decision_variables)),
        max_rules=max_rules,
        rule_generation_mode="prototype",
    )
    return ShallowModelSpec(
        input_dim=len(variables),
        feature_block=feature_block,
        decision_layer=decision_layer,
        stage_name="flat_stage",
    )


def _calibration_bins_from_probabilities(
    targets: np.ndarray,
    probabilities: np.ndarray,
    *,
    bin_count: int = 5,
) -> list[CalibrationBin]:
    truth = np.asarray(targets, dtype=int).reshape(-1)
    probs = np.asarray(probabilities, dtype=float).reshape(-1)
    bins: list[CalibrationBin] = []
    edges = np.linspace(0.0, 1.0, bin_count + 1)
    for lower, upper in zip(edges[:-1], edges[1:], strict=True):
        if upper == 1.0:
            mask = (probs >= lower) & (probs <= upper)
        else:
            mask = (probs >= lower) & (probs < upper)
        if not np.any(mask):
            continue
        bins.append(
            CalibrationBin(
                lower=float(lower),
                upper=float(upper),
                count=int(mask.sum()),
                mean_probability=float(probs[mask].mean()),
                observed_positive_rate=float(truth[mask].mean()),
            )
        )
    return bins


def _ece_from_bins(bins: list[CalibrationBin], sample_count: int) -> float:
    if sample_count <= 0:
        return 0.0
    return float(
        sum(item.count * abs(item.mean_probability - item.observed_positive_rate) for item in bins)
        / sample_count
    )


def _classification_metrics_at_threshold(
    targets: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
) -> tuple[dict[str, float], ConfusionMatrix, np.ndarray]:
    truth = np.asarray(targets, dtype=int).reshape(-1)
    probs = np.asarray(probabilities, dtype=float).reshape(-1)
    labels = (probs >= threshold).astype(int)
    tn = int(np.sum((truth == 0) & (labels == 0)))
    fp = int(np.sum((truth == 0) & (labels == 1)))
    fn = int(np.sum((truth == 1) & (labels == 0)))
    tp = int(np.sum((truth == 1) & (labels == 1)))
    metrics = {
        "accuracy": float(accuracy_score(truth, labels)),
        "precision": float(precision_score(truth, labels, zero_division=0)),
        "recall": float(recall_score(truth, labels, zero_division=0)),
        "f1": float(f1_score(truth, labels, zero_division=0)),
    }
    return metrics, ConfusionMatrix(
        true_negative=tn,
        false_positive=fp,
        false_negative=fn,
        true_positive=tp,
    ), labels


def _validation_payload(
    task: str,
    targets: np.ndarray,
    predictions: np.ndarray,
    *,
    source_rows: np.ndarray | None = None,
    dataset_fingerprint: str | None = None,
) -> tuple[list[PredictionRow], ConfusionMatrix | None, list[CalibrationBin]]:
    gold = np.asarray(targets, dtype=float).reshape(-1)
    raw = np.asarray(predictions, dtype=float).reshape(-1)
    source = None if source_rows is None else np.asarray(source_rows, dtype=int).reshape(-1)
    if source is not None and len(source) != len(gold):
        raise TrainingError("Validation source-row identity does not match prediction evidence length.")
    rows: list[PredictionRow] = []

    if task == "binary_classification":
        probabilities = 1.0 / (1.0 + np.exp(-np.clip(raw, -60.0, 60.0)))
        labels = (probabilities >= 0.5).astype(int)
        target_labels = (gold >= 0.5).astype(int)
        # Evaluation evidence is complete, not a UI-only preview: calibration,
        # threshold provenance and a reopened project must use the same validation
        # samples that produced its metrics.
        for index, (target, logit, probability, label) in enumerate(
            zip(gold, raw, probabilities, labels, strict=True)
        ):
            rows.append(
                PredictionRow(
                    row=index,
                    source_row=None if source is None else int(source[index]),
                    row_identity=None if source is None or dataset_fingerprint is None else row_identity(dataset_fingerprint, int(source[index])),
                    target=float(target),
                    prediction=float(logit),
                    probability=float(probability),
                    predicted_label=int(label),
                )
            )
        tn = int(np.sum((target_labels == 0) & (labels == 0)))
        fp = int(np.sum((target_labels == 0) & (labels == 1)))
        fn = int(np.sum((target_labels == 1) & (labels == 0)))
        tp = int(np.sum((target_labels == 1) & (labels == 1)))
        matrix = ConfusionMatrix(
            true_negative=tn,
            false_positive=fp,
            false_negative=fn,
            true_positive=tp,
        )
        bins = _calibration_bins_from_probabilities(target_labels, probabilities)
        return rows, matrix, bins

    for index, (target, prediction) in enumerate(zip(gold, raw, strict=True)):
        rows.append(
            PredictionRow(
                row=index,
                source_row=None if source is None else int(source[index]),
                row_identity=None if source is None or dataset_fingerprint is None else row_identity(dataset_fingerprint, int(source[index])),
                target=float(target),
                prediction=float(prediction),
                residual=float(prediction - target),
            )
        )
    return rows, None, []


def _baseline_metrics(task: str, targets: np.ndarray, raw_predictions: np.ndarray) -> dict[str, float]:
    gold = np.asarray(targets, dtype=float).reshape(-1)
    values = np.asarray(raw_predictions, dtype=float).reshape(-1)
    if task == TaskType.BINARY_CLASSIFICATION.value:
        probabilities = 1.0 / (1.0 + np.exp(-np.clip(values, -60.0, 60.0)))
        labels = (probabilities >= 0.5).astype(int)
        truth = (gold >= 0.5).astype(int)
        result = {
            "accuracy": float(accuracy_score(truth, labels)),
            "precision": float(precision_score(truth, labels, zero_division=0)),
            "recall": float(recall_score(truth, labels, zero_division=0)),
            "f1": float(f1_score(truth, labels, zero_division=0)),
            "brier": float(np.mean((probabilities - truth) ** 2)),
        }
        if len(np.unique(truth)) == 2:
            result["roc_auc"] = float(roc_auc_score(truth, probabilities))
            result["pr_auc"] = float(average_precision_score(truth, probabilities))
        calibration = _validation_payload(task, gold, values)[2]
        result["ece"] = _ece_from_bins(calibration, len(truth))
        return result
    return {
        "mse": float(mean_squared_error(gold, values)),
        "mae": float(mean_absolute_error(gold, values)),
        "rmse": float(np.sqrt(mean_squared_error(gold, values))),
        "r2": float(r2_score(gold, values)),
    }


def train_linear_baseline(
    project_root: Path,
    *,
    kind: str,
    seed: int | None = None,
    split_seed: int | None = None,
    training_seed: int | None = None,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
) -> TrainingRun:
    """Train a safe declarative linear baseline on the canonical train-only split.

    The artifact is JSON coefficients rather than pickle/joblib, so project opening
    never needs executable deserialization.
    """
    contract = load_dataset_contract(project_root)
    expected_kind = "logistic_regression" if contract.task == TaskType.BINARY_CLASSIFICATION.value else "linear_regression"
    if kind != expected_kind:
        raise TrainingError(f"{kind} is incompatible with DatasetContract task {contract.task!r}.")
    frame = load_dataset_frame(project_root)
    feature_columns = list(contract.feature_columns)
    if not feature_columns or any(not pd.api.types.is_numeric_dtype(frame[column].dropna()) for column in feature_columns):
        raise TrainingError("Linear baselines require one or more numeric DatasetContract feature columns.")
    resolved_split_seed, resolved_training_seed, randomness_protocol = _resolve_randomness(
        seed=seed, split_seed=split_seed, training_seed=training_seed,
    )
    _seed_everything(resolved_training_seed)
    split = TabularDataset.from_dataframe(frame).split(DatasetConfig(
        target_column=contract.target, feature_columns=tuple(feature_columns),
        validation_fraction=validation_fraction, test_fraction=test_fraction,
        normalization=NormalizationMode.STANDARD, fill_missing="median", random_state=resolved_split_seed,
    ))
    if split.validation_features.shape[0] == 0:
        raise TrainingError("The resolved validation split is empty.")
    if kind == "logistic_regression":
        train_targets = np.asarray(split.train_targets, dtype=float).reshape(-1)
        if set(np.unique(train_targets)) - {0.0, 1.0}:
            raise TrainingError("Logistic regression requires binary target values encoded as 0 and 1.")
        estimator = LogisticRegression(random_state=resolved_training_seed, max_iter=1000)
        estimator.fit(split.train_features, train_targets.astype(int))
        raw_validation = estimator.decision_function(split.validation_features)
        coefficients = np.asarray(estimator.coef_).reshape(-1)
        intercept = float(np.asarray(estimator.intercept_).reshape(-1)[0])
    else:
        estimator = LinearRegression()
        estimator.fit(split.train_features, np.asarray(split.train_targets, dtype=float).reshape(-1))
        raw_validation = estimator.predict(split.validation_features)
        coefficients = np.asarray(estimator.coef_).reshape(-1)
        intercept = float(np.asarray(estimator.intercept_).reshape(-1)[0])
    preview, confusion, calibration = _validation_payload(contract.task, split.validation_targets, raw_validation, source_rows=split.validation_indices, dataset_fingerprint=contract.dataset_fingerprint)
    metrics = _baseline_metrics(contract.task, split.validation_targets, raw_validation)
    artifact_payload = {
        "format": "ruflex.declarative-linear-baseline/v1", "model_kind": kind,
        "task": contract.task, "target": contract.target, "feature_columns": feature_columns,
        "coefficients": [float(value) for value in coefficients], "intercept": intercept,
        "normalization": _normalization_dict(split.normalization), "split_seed": resolved_split_seed,
        "training_seed": resolved_training_seed,
    }
    model_ref = ArtifactStore(project_root).ingest_bytes(
        json.dumps(artifact_payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        metadata=ArtifactMetadata(media_type="application/vnd.ruflex.declarative-linear-model+json", source_kind="generated", original_name=f"{kind}.json", parent_artifacts=[contract.source_artifact_sha256], producer={"component": "ruflex.application.training", "version": "1"}),
    )
    loss = metrics["mse"] if contract.task == TaskType.REGRESSION.value else 1.0 - metrics["accuracy"]
    summary = {"source": kind, "epochs_ran": 1, "best_epoch": 1, "monitor_name": "validation_loss", "best_monitor_value": loss, "train_loss": loss, "train_metrics": {}, "validation_loss": loss, "validation_metrics": metrics, "history": []}
    run = TrainingRun(
        model_kind=kind, task=contract.task, target=contract.target, dataset_fingerprint=contract.dataset_fingerprint, dataset_artifact_sha256=contract.source_artifact_sha256, feature_columns=feature_columns,
        seed=resolved_training_seed, split_seed=resolved_split_seed, training_seed=resolved_training_seed, randomness_protocol=randomness_protocol,
        max_epochs=1, learning_rate=0.0, batch_size=int(split.train_features.shape[0]), patience=None,
        split=_provenance(contract, split, split_seed=resolved_split_seed, validation_fraction=validation_fraction, test_fraction=test_fraction),
        model_spec={"model_kind": kind, "coefficients": artifact_payload["coefficients"], "intercept": intercept}, normalization=_normalization_dict(split.normalization), training_summary=summary,
        trajectory=[EpochPoint(epoch=0, train_loss=loss, validation_loss=loss, train_metrics={}, validation_metrics=metrics), EpochPoint(epoch=1, train_loss=loss, validation_loss=loss, train_metrics={}, validation_metrics=metrics)],
        validation_metrics=metrics, prediction_preview=preview, confusion_matrix=confusion, calibration=calibration, model_artifact_sha256=model_ref.sha256,
    )
    persist_training_run(project_root, run)
    return run


def _tree_payload(estimator, *, kind: str, task: str, target: str, feature_columns: list[str], normalization: dict, split_seed: int, training_seed: int) -> dict:
    tree = estimator.tree_
    return {
        "format": "ruflex.declarative-decision-tree/v1", "model_kind": kind,
        "task": task, "target": target, "feature_columns": feature_columns,
        "classes": None if task == TaskType.REGRESSION.value or not hasattr(estimator, "classes_") else [str(value) for value in estimator.classes_],
        "parameters": {key: value for key, value in estimator.get_params().items() if isinstance(value, (str, int, float, bool, type(None)))},
        "tree": {
            "node_count": int(tree.node_count), "max_depth": int(tree.max_depth),
            "children_left": [int(value) for value in tree.children_left], "children_right": [int(value) for value in tree.children_right],
            "feature_index": [int(value) for value in tree.feature], "threshold": [float(value) for value in tree.threshold],
            "impurity": [float(value) for value in tree.impurity], "samples": [int(value) for value in tree.n_node_samples],
            "values": np.asarray(tree.value, dtype=float).reshape(tree.node_count, -1).tolist(),
        },
        "normalization": normalization, "split_seed": split_seed, "training_seed": training_seed,
    }


def train_decision_tree(
    project_root: Path, *, seed: int | None = None, split_seed: int | None = None, training_seed: int | None = None, validation_fraction: float = 0.2,
    test_fraction: float = 0.2, max_depth: int | None = None,
) -> TrainingRun:
    """Train and persist an executable tree as inspectable JSON, never pickle."""
    contract = load_dataset_contract(project_root)
    frame = load_dataset_frame(project_root)
    feature_columns = list(contract.feature_columns)
    if not feature_columns or any(not pd.api.types.is_numeric_dtype(frame[column].dropna()) for column in feature_columns):
        raise TrainingError("Decision Tree requires numeric DatasetContract feature columns.")
    resolved_split_seed, resolved_training_seed, randomness_protocol = _resolve_randomness(seed=seed, split_seed=split_seed, training_seed=training_seed)
    _seed_everything(resolved_training_seed)
    split = TabularDataset.from_dataframe(frame).split(DatasetConfig(
        target_column=contract.target, feature_columns=tuple(feature_columns), validation_fraction=validation_fraction,
        test_fraction=test_fraction, normalization=NormalizationMode.STANDARD, fill_missing="median", random_state=resolved_split_seed,
    ))
    if split.validation_features.shape[0] == 0:
        raise TrainingError("The resolved validation split is empty.")
    if contract.task == TaskType.BINARY_CLASSIFICATION.value:
        target_values = np.asarray(split.train_targets, dtype=float).reshape(-1)
        if set(np.unique(target_values)) - {0.0, 1.0}:
            raise TrainingError("DecisionTreeClassifier currently requires binary target values encoded as 0 and 1.")
        estimator = DecisionTreeClassifier(random_state=resolved_training_seed, max_depth=max_depth)
        estimator.fit(split.train_features, target_values.astype(int))
        probabilities = estimator.predict_proba(split.validation_features)[:, 1]
        raw_validation = np.log(np.clip(probabilities, 1e-12, 1 - 1e-12) / np.clip(1 - probabilities, 1e-12, 1))
    elif contract.task == TaskType.REGRESSION.value:
        estimator = DecisionTreeRegressor(random_state=resolved_training_seed, max_depth=max_depth)
        estimator.fit(split.train_features, np.asarray(split.train_targets, dtype=float).reshape(-1))
        raw_validation = estimator.predict(split.validation_features)
    else:
        raise TrainingError(f"Unsupported task {contract.task!r} for Decision Tree.")
    preview, confusion, calibration = _validation_payload(contract.task, split.validation_targets, raw_validation, source_rows=split.validation_indices, dataset_fingerprint=contract.dataset_fingerprint)
    metrics = _baseline_metrics(contract.task, split.validation_targets, raw_validation)
    payload = _tree_payload(estimator, kind="decision_tree", task=contract.task, target=contract.target, feature_columns=feature_columns, normalization=_normalization_dict(split.normalization), split_seed=resolved_split_seed, training_seed=resolved_training_seed)
    ref = ArtifactStore(project_root).ingest_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"), metadata=ArtifactMetadata(media_type="application/vnd.ruflex.declarative-decision-tree+json", source_kind="generated", original_name="decision-tree.json", parent_artifacts=[contract.source_artifact_sha256], producer={"component": "ruflex.application.training", "version": "1"}))
    loss = metrics["mse"] if contract.task == TaskType.REGRESSION.value else 1 - metrics["accuracy"]
    summary = {"source": "decision_tree", "epochs_ran": 1, "best_epoch": 1, "monitor_name": "validation_loss", "best_monitor_value": loss, "train_loss": loss, "train_metrics": {}, "validation_loss": loss, "validation_metrics": metrics, "history": []}
    run = TrainingRun(model_kind="decision_tree", task=contract.task, target=contract.target, dataset_fingerprint=contract.dataset_fingerprint, dataset_artifact_sha256=contract.source_artifact_sha256, feature_columns=feature_columns, seed=resolved_training_seed, split_seed=resolved_split_seed, training_seed=resolved_training_seed, randomness_protocol=randomness_protocol, max_epochs=1, learning_rate=0.0, batch_size=int(split.train_features.shape[0]), patience=None, split=_provenance(contract, split, split_seed=resolved_split_seed, validation_fraction=validation_fraction, test_fraction=test_fraction), model_spec={"model_kind": "decision_tree", "node_count": payload["tree"]["node_count"], "max_depth": payload["tree"]["max_depth"], "leaf_count": sum(1 for value in payload["tree"]["children_left"] if value == -1)}, normalization=_normalization_dict(split.normalization), training_summary=summary, trajectory=[EpochPoint(epoch=0, train_loss=loss, validation_loss=loss, train_metrics={}, validation_metrics=metrics), EpochPoint(epoch=1, train_loss=loss, validation_loss=loss, train_metrics={}, validation_metrics=metrics)], validation_metrics=metrics, prediction_preview=preview, confusion_matrix=confusion, calibration=calibration, model_artifact_sha256=ref.sha256)
    persist_training_run(project_root, run)
    return run


def train_random_forest(
    project_root: Path, *, seed: int | None = None, split_seed: int | None = None, training_seed: int | None = None, validation_fraction: float = 0.2,
    test_fraction: float = 0.2, n_estimators: int = 25, max_depth: int | None = None,
) -> TrainingRun:
    """Train a real forest while retaining every constituent tree declaratively."""
    contract = load_dataset_contract(project_root); frame = load_dataset_frame(project_root)
    columns = list(contract.feature_columns)
    if not columns or any(not pd.api.types.is_numeric_dtype(frame[column].dropna()) for column in columns):
        raise TrainingError("Random Forest requires numeric DatasetContract feature columns.")
    resolved_split_seed, resolved_training_seed, randomness_protocol = _resolve_randomness(seed=seed, split_seed=split_seed, training_seed=training_seed)
    _seed_everything(resolved_training_seed)
    split = TabularDataset.from_dataframe(frame).split(DatasetConfig(target_column=contract.target, feature_columns=tuple(columns), validation_fraction=validation_fraction, test_fraction=test_fraction, normalization=NormalizationMode.STANDARD, fill_missing="median", random_state=resolved_split_seed))
    if contract.task == TaskType.BINARY_CLASSIFICATION.value:
        estimator = RandomForestClassifier(n_estimators=n_estimators, random_state=resolved_training_seed, max_depth=max_depth)
        estimator.fit(split.train_features, np.asarray(split.train_targets).reshape(-1).astype(int))
        probabilities = estimator.predict_proba(split.validation_features)[:, 1]
        raw = np.log(np.clip(probabilities, 1e-12, 1 - 1e-12) / np.clip(1 - probabilities, 1e-12, 1))
    elif contract.task == TaskType.REGRESSION.value:
        estimator = RandomForestRegressor(n_estimators=n_estimators, random_state=resolved_training_seed, max_depth=max_depth)
        estimator.fit(split.train_features, np.asarray(split.train_targets).reshape(-1))
        raw = estimator.predict(split.validation_features)
    else:
        raise TrainingError(f"Unsupported task {contract.task!r} for Random Forest.")
    preview, confusion, calibration = _validation_payload(contract.task, split.validation_targets, raw, source_rows=split.validation_indices, dataset_fingerprint=contract.dataset_fingerprint); metrics = _baseline_metrics(contract.task, split.validation_targets, raw)
    normalization = _normalization_dict(split.normalization)
    trees = [_tree_payload(tree, kind="decision_tree", task=contract.task, target=contract.target, feature_columns=columns, normalization=normalization, split_seed=resolved_split_seed, training_seed=resolved_training_seed)["tree"] for tree in estimator.estimators_]
    payload = {"format": "ruflex.declarative-random-forest/v1", "model_kind": "random_forest", "task": contract.task, "target": contract.target, "feature_columns": columns, "parameters": {"n_estimators": n_estimators, "max_depth": max_depth, "random_state": resolved_training_seed}, "split_seed": resolved_split_seed, "training_seed": resolved_training_seed, "normalization": normalization, "trees": trees, "ensemble_semantics": "aggregate constituent tree predictions; no single tree path is the exact explanation of the ensemble"}
    ref = ArtifactStore(project_root).ingest_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(), metadata=ArtifactMetadata(media_type="application/vnd.ruflex.declarative-random-forest+json", source_kind="generated", original_name="random-forest.json", parent_artifacts=[contract.source_artifact_sha256], producer={"component": "ruflex.application.training", "version": "1"}))
    loss = metrics["mse"] if contract.task == TaskType.REGRESSION.value else 1 - metrics["accuracy"]
    run = TrainingRun(model_kind="random_forest", task=contract.task, target=contract.target, dataset_fingerprint=contract.dataset_fingerprint, dataset_artifact_sha256=contract.source_artifact_sha256, feature_columns=columns, seed=resolved_training_seed, split_seed=resolved_split_seed, training_seed=resolved_training_seed, randomness_protocol=randomness_protocol, max_epochs=1, learning_rate=0., batch_size=int(split.train_features.shape[0]), patience=None, split=_provenance(contract, split, split_seed=resolved_split_seed, validation_fraction=validation_fraction, test_fraction=test_fraction), model_spec={"model_kind": "random_forest", "tree_count": n_estimators, "node_count": sum(tree["node_count"] for tree in trees), "max_depth": max(tree["max_depth"] for tree in trees), "leaf_count": sum(sum(1 for node in tree["children_left"] if node == -1) for tree in trees)}, normalization=normalization, training_summary={"source": "random_forest", "epochs_ran": 1, "best_epoch": 1, "monitor_name": "validation_loss", "best_monitor_value": loss, "train_loss": loss, "train_metrics": {}, "validation_loss": loss, "validation_metrics": metrics, "history": []}, trajectory=[EpochPoint(epoch=0, train_loss=loss, validation_loss=loss, train_metrics={}, validation_metrics=metrics), EpochPoint(epoch=1, train_loss=loss, validation_loss=loss, train_metrics={}, validation_metrics=metrics)], validation_metrics=metrics, prediction_preview=preview, confusion_matrix=confusion, calibration=calibration, model_artifact_sha256=ref.sha256)
    persist_training_run(project_root, run); return run


def train_gradient_boosting(project_root: Path, *, seed: int | None = None, split_seed: int | None = None, training_seed: int | None = None, validation_fraction: float = .2, test_fraction: float = .2, n_estimators: int = 50, learning_rate: float = .1, max_depth: int = 3) -> TrainingRun:
    """Train gradient boosting and retain its fitted regression trees declaratively."""
    contract = load_dataset_contract(project_root); frame = load_dataset_frame(project_root); columns = list(contract.feature_columns)
    if not columns or any(not pd.api.types.is_numeric_dtype(frame[column].dropna()) for column in columns): raise TrainingError("Gradient Boosting requires numeric DatasetContract feature columns.")
    resolved_split_seed, resolved_training_seed, randomness_protocol = _resolve_randomness(seed=seed, split_seed=split_seed, training_seed=training_seed)
    _seed_everything(resolved_training_seed)
    split = TabularDataset.from_dataframe(frame).split(DatasetConfig(target_column=contract.target, feature_columns=tuple(columns), validation_fraction=validation_fraction, test_fraction=test_fraction, normalization=NormalizationMode.STANDARD, fill_missing="median", random_state=resolved_split_seed))
    if contract.task == TaskType.BINARY_CLASSIFICATION.value:
        estimator = GradientBoostingClassifier(n_estimators=n_estimators, learning_rate=learning_rate, max_depth=max_depth, random_state=resolved_training_seed)
        estimator.fit(split.train_features, np.asarray(split.train_targets).reshape(-1).astype(int)); probabilities = estimator.predict_proba(split.validation_features)[:, 1]; raw = estimator.decision_function(split.validation_features)
    elif contract.task == TaskType.REGRESSION.value:
        estimator = GradientBoostingRegressor(n_estimators=n_estimators, learning_rate=learning_rate, max_depth=max_depth, random_state=resolved_training_seed)
        estimator.fit(split.train_features, np.asarray(split.train_targets).reshape(-1)); raw = estimator.predict(split.validation_features)
    else: raise TrainingError(f"Unsupported task {contract.task!r} for Gradient Boosting.")
    preview, confusion, calibration = _validation_payload(contract.task, split.validation_targets, raw, source_rows=split.validation_indices, dataset_fingerprint=contract.dataset_fingerprint); metrics = _baseline_metrics(contract.task, split.validation_targets, raw); normalization = _normalization_dict(split.normalization)
    tree_estimators = np.asarray(estimator.estimators_, dtype=object).reshape(-1).tolist()
    trees = [_tree_payload(tree, kind="decision_tree", task=contract.task, target=contract.target, feature_columns=columns, normalization=normalization, split_seed=resolved_split_seed, training_seed=resolved_training_seed)["tree"] for tree in tree_estimators]
    # Persist the fitted base score as part of the declarative ensemble semantics.
    # Without it a Gradient Boosting artifact cannot be replayed exactly enough for
    # local evidence after the original sklearn estimator has gone out of memory.
    initial_raw_prediction = float(np.asarray(estimator._raw_predict_init(split.train_features[:1]), dtype=float).reshape(-1)[0])
    payload = {"format": "ruflex.declarative-gradient-boosting/v1", "model_kind": "gradient_boosting", "task": contract.task, "target": contract.target, "feature_columns": columns, "parameters": {"n_estimators": n_estimators, "learning_rate": learning_rate, "max_depth": max_depth, "random_state": resolved_training_seed}, "split_seed": resolved_split_seed, "training_seed": resolved_training_seed, "normalization": normalization, "initial_raw_prediction": initial_raw_prediction, "trees": trees, "ensemble_semantics": "stagewise weighted aggregation; no single constituent path is the exact explanation of the ensemble"}
    ref = ArtifactStore(project_root).ingest_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(), metadata=ArtifactMetadata(media_type="application/vnd.ruflex.declarative-gradient-boosting+json", source_kind="generated", original_name="gradient-boosting.json", parent_artifacts=[contract.source_artifact_sha256], producer={"component": "ruflex.application.training", "version": "1"}))
    loss = metrics["mse"] if contract.task == TaskType.REGRESSION.value else 1-metrics["accuracy"]
    run = TrainingRun(model_kind="gradient_boosting", task=contract.task, target=contract.target, dataset_fingerprint=contract.dataset_fingerprint, dataset_artifact_sha256=contract.source_artifact_sha256, feature_columns=columns, seed=resolved_training_seed, split_seed=resolved_split_seed, training_seed=resolved_training_seed, randomness_protocol=randomness_protocol, max_epochs=n_estimators, learning_rate=learning_rate, batch_size=int(split.train_features.shape[0]), patience=None, split=_provenance(contract, split, split_seed=resolved_split_seed, validation_fraction=validation_fraction, test_fraction=test_fraction), model_spec={"model_kind":"gradient_boosting","tree_count":len(trees),"node_count":sum(tree["node_count"] for tree in trees),"max_depth":max(tree["max_depth"] for tree in trees),"leaf_count":sum(sum(1 for node in tree["children_left"] if node==-1) for tree in trees)}, normalization=normalization, training_summary={"source":"gradient_boosting","epochs_ran":n_estimators,"best_epoch":n_estimators,"monitor_name":"validation_loss","best_monitor_value":loss,"train_loss":loss,"train_metrics":{},"validation_loss":loss,"validation_metrics":metrics,"history":[]}, trajectory=[EpochPoint(epoch=0, train_loss=loss, validation_loss=loss, train_metrics={}, validation_metrics=metrics),EpochPoint(epoch=n_estimators, train_loss=loss, validation_loss=loss, train_metrics={}, validation_metrics=metrics)], validation_metrics=metrics,prediction_preview=preview,confusion_matrix=confusion,calibration=calibration,model_artifact_sha256=ref.sha256)
    persist_training_run(project_root, run); return run


def trace_decision_tree(project_root: Path, run_id: UUID, sample: dict[str, float]) -> TreePathEvidence:
    run = load_training_run(project_root, run_id)
    if run.model_kind != "decision_tree":
        raise TrainingError("Exact tree path is only available for a Decision Tree run.")
    store = ArtifactStore(project_root)
    with store.open(ArtifactRef(sha256=run.model_artifact_sha256)) as handle:
        payload = json.loads(handle.read().decode("utf-8"))
    if payload.get("format") != "ruflex.declarative-decision-tree/v1":
        raise TrainingError("Tree artifact format is not supported for exact path tracing.")
    columns = payload["feature_columns"]
    missing = [column for column in columns if column not in sample]
    if missing:
        raise TrainingError(f"Exact tree path requires values for: {', '.join(missing)}")
    normal = payload["normalization"]
    centers = normal.get("center") or [0.0] * len(columns)
    scales = normal.get("scale") or [1.0] * len(columns)
    normalized = {column: (float(sample[column]) - float(centers[index])) / max(float(scales[index]), 1e-12) for index, column in enumerate(columns)}
    tree = payload["tree"]; node = 0; steps: list[TreePathStep] = []
    while tree["children_left"][node] != -1:
        index = tree["feature_index"][node]; column = columns[index]; threshold = float(tree["threshold"][node]); value = normalized[column]
        go_left = value <= threshold
        steps.append(TreePathStep(node_id=node, feature_name=column, threshold=threshold, value=value, decision="left" if go_left else "right"))
        node = tree["children_left"][node] if go_left else tree["children_right"][node]
    values = [float(value) for value in tree["values"][node]]
    probabilities = None
    if payload["task"] == TaskType.BINARY_CLASSIFICATION.value:
        total = max(sum(values), 1e-12); probabilities = {str(index): value / total for index, value in enumerate(values)}; prediction = float(max(probabilities, key=probabilities.get))
    else:
        prediction = values[0]
    evidence = TreePathEvidence(run_id=run.run_id, model_artifact_sha256=run.model_artifact_sha256, preprocessing_identity=json.dumps(normal, sort_keys=True), input_sample={column: float(sample[column]) for column in columns}, steps=steps, leaf_id=node, prediction=prediction, class_probabilities=probabilities)
    _atomic_write_text(_tree_evidence_root(project_root) / f"{evidence.evidence_id}.json", evidence.model_dump_json(indent=2))
    _atomic_write_text(_tree_evidence_root(project_root) / "latest.json", json.dumps({"evidence_id": str(evidence.evidence_id)}, indent=2))
    return evidence


def load_tree_path(project_root: Path, evidence_id: UUID) -> TreePathEvidence:
    return TreePathEvidence.model_validate_json((_tree_evidence_root(project_root) / f"{evidence_id}.json").read_text(encoding="utf-8"))


def load_latest_tree_path(project_root: Path) -> TreePathEvidence:
    pointer = json.loads((_tree_evidence_root(project_root) / "latest.json").read_text(encoding="utf-8"))
    return load_tree_path(project_root, UUID(pointer["evidence_id"]))


def _normalization_dict(normalization: NormalizationArtifact) -> dict:
    return normalization.to_dict()


def train_flat_neuro_fuzzy(
    project_root: Path,
    *,
    seed: int | None = None,
    split_seed: int | None = None,
    training_seed: int | None = None,
    max_epochs: int = 20,
    learning_rate: float = 1e-2,
    batch_size: int = 32,
    patience: int | None = 8,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
    max_rules: int = 8,
) -> TrainingRun:
    if max_epochs <= 0:
        raise TrainingError("max_epochs must be positive.")
    if batch_size <= 0:
        raise TrainingError("batch_size must be positive.")
    if learning_rate <= 0:
        raise TrainingError("learning_rate must be positive.")
    if validation_fraction <= 0:
        raise TrainingError("A non-empty validation split is required for the Studio training route.")

    contract = load_dataset_contract(project_root)
    if contract.task not in {TaskType.REGRESSION.value, TaskType.BINARY_CLASSIFICATION.value}:
        raise TrainingError(f"Task {contract.task!r} is not supported by the current trainable neuro-fuzzy engine.")

    frame = load_dataset_frame(project_root)
    feature_columns = list(contract.feature_columns)
    if not feature_columns:
        raise TrainingError("The DatasetContract does not contain trainable feature columns.")

    non_numeric = [column for column in feature_columns if not pd.api.types.is_numeric_dtype(frame[column].dropna())]
    if non_numeric:
        raise TrainingError(
            "The current flat neuro-fuzzy engine requires numeric features. "
            f"Unsupported columns: {', '.join(non_numeric)}"
        )
    if not pd.api.types.is_numeric_dtype(frame[contract.target].dropna()):
        raise TrainingError("The current trainable engine requires a numeric target.")
    if contract.task == TaskType.BINARY_CLASSIFICATION.value:
        classes = sorted(float(value) for value in frame[contract.target].dropna().unique())
        if len(classes) != 2 or not set(classes).issubset({0.0, 1.0}):
            raise TrainingError("Binary classification currently requires target values encoded as 0 and 1.")

    resolved_split_seed, resolved_training_seed, randomness_protocol = _resolve_randomness(seed=seed, split_seed=split_seed, training_seed=training_seed)
    _seed_everything(resolved_training_seed)
    dataset = TabularDataset.from_dataframe(frame)
    split = dataset.split(
        DatasetConfig(
            target_column=contract.target,
            feature_columns=tuple(feature_columns),
            validation_fraction=validation_fraction,
            test_fraction=test_fraction,
            normalization=NormalizationMode.STANDARD,
            fill_missing="median",
            random_state=resolved_split_seed,
        )
    )
    if split.validation_features.shape[0] == 0:
        raise TrainingError("The resolved validation split is empty; increase the dataset size or validation fraction.")

    # Membership initialization must be derived from the training partition only.
    # Using the full frame here would leak validation/test distribution information
    # into model construction even though normalization itself is train-only.
    training_frame = pd.DataFrame(split.train_features, columns=feature_columns)
    spec = _build_flat_spec(training_frame, feature_columns, max_rules=max_rules)
    model = FlatNeuroFuzzyModel(spec)
    config = ModelTrainingConfig(
        task_type=TaskType(contract.task),
        use_bootstrap_initialization=True,
        use_stagewise_pretraining=False,
        stagewise=StagewiseOptions(epochs_per_stage=1, decision_epochs=1, refinement_rounds=1),
        fine_tuning=FineTuningOptions(
            max_epochs=max_epochs,
            learning_rate=learning_rate,
            batch_size=batch_size,
            patience=patience,
            shuffle=True,
            classification_threshold=0.5,
        ),
        refinement=RefinementOptions(cycles=1),
    )
    summary = model.fit(split, config)
    predictions = model.predict(split.validation_features)
    preview, confusion, calibration = _validation_payload(contract.task, split.validation_targets, predictions, source_rows=split.validation_indices, dataset_fingerprint=contract.dataset_fingerprint)

    with tempfile.NamedTemporaryFile(prefix="ruflex-model-", suffix=".pt", delete=False) as handle:
        temp_model_path = Path(handle.name)
    try:
        model.save_bundle(
            temp_model_path,
            metadata={
                "producer": "ruflex.application.training",
                "model_kind": "flat_neuro_fuzzy",
                "task": contract.task,
                "target": contract.target,
                "feature_columns": feature_columns,
                "seed": resolved_training_seed,
                "split_seed": resolved_split_seed,
                "training_seed": resolved_training_seed,
            },
        )
        model_ref = ArtifactStore(project_root).ingest_file(
            temp_model_path,
            metadata=ArtifactMetadata(
                media_type="application/x-pytorch-model",
                source_kind="generated",
                original_name="flat-neuro-fuzzy.pt",
                parent_artifacts=[contract.source_artifact_sha256],
                producer={"component": "ruflex.application.training", "version": "1"},
            ),
        )
    finally:
        temp_model_path.unlink(missing_ok=True)

    run = TrainingRun(
        task=contract.task,
        target=contract.target,
        dataset_fingerprint=contract.dataset_fingerprint,
        dataset_artifact_sha256=contract.source_artifact_sha256,
        feature_columns=feature_columns,
        seed=resolved_training_seed,
        split_seed=resolved_split_seed,
        training_seed=resolved_training_seed,
        randomness_protocol=randomness_protocol,
        max_epochs=max_epochs,
        learning_rate=learning_rate,
        batch_size=batch_size,
        patience=patience,
        split=_provenance(contract, split, split_seed=resolved_split_seed, validation_fraction=validation_fraction, test_fraction=test_fraction),
        model_spec=spec.to_dict(),
        normalization=_normalization_dict(split.normalization),
        training_summary=summary.to_dict(),
        trajectory=[
            EpochPoint(
                epoch=point.epoch,
                train_loss=point.train_loss,
                validation_loss=point.validation_loss,
                train_metrics=point.train_metrics,
                validation_metrics=point.validation_metrics,
            )
            for point in summary.history
        ],
        validation_metrics=dict(summary.validation_metrics or {}),
        prediction_preview=preview,
        confusion_matrix=confusion,
        calibration=calibration,
        model_artifact_sha256=model_ref.sha256,
    )
    persist_training_run(project_root, run)
    return run


def persist_training_run(project_root: Path, run: TrainingRun) -> None:
    path = _run_path(project_root, run.run_id)
    _atomic_write_text(path, run.model_dump_json(indent=2))
    _atomic_write_text(
        _active_run_path(project_root),
        json.dumps({"run_id": str(run.run_id)}, indent=2, sort_keys=True),
    )


def load_training_run(project_root: Path, run_id: UUID) -> TrainingRun:
    return TrainingRun.model_validate_json(_run_path(project_root, run_id).read_text(encoding="utf-8"))


def load_latest_training_run(project_root: Path) -> TrainingRun:
    pointer = json.loads(_active_run_path(project_root).read_text(encoding="utf-8"))
    return load_training_run(project_root, UUID(pointer["run_id"]))


def list_training_runs(project_root: Path) -> list[TrainingRun]:
    runs: list[TrainingRun] = []
    for path in _runs_root(project_root).glob("*.json"):
        try:
            UUID(path.stem)
        except ValueError:
            continue
        runs.append(TrainingRun.model_validate_json(path.read_text(encoding="utf-8")))
    return sorted(runs, key=lambda run: run.created_at)


def train_model(project_root: Path, *, model_kind: str, **config) -> TrainingRun:
    """Run one declared catalog adapter and record its wall-clock training time.

    The individual adapters persist their safe artifacts themselves.  This common
    entry point makes Study execution use exactly the same adapters and protocol
    constraints as a single Studio training run.
    """
    started = time.perf_counter()
    config = dict(config)
    # Preserve old API callers while allowing the explicit provenance contract.
    config.setdefault("seed", None)
    if model_kind == "flat_neuro_fuzzy":
        run = train_flat_neuro_fuzzy(project_root, **config)
    elif model_kind in {"logistic_regression", "linear_regression"}:
        run = train_linear_baseline(
            project_root,
            kind=model_kind,
            seed=config.get("seed"), split_seed=config.get("split_seed"), training_seed=config.get("training_seed"),
            validation_fraction=config["validation_fraction"],
            test_fraction=config["test_fraction"],
        )
    elif model_kind == "decision_tree":
        run = train_decision_tree(
            project_root,
            seed=config.get("seed"), split_seed=config.get("split_seed"), training_seed=config.get("training_seed"),
            validation_fraction=config["validation_fraction"],
            test_fraction=config["test_fraction"],
        )
    elif model_kind == "random_forest":
        run = train_random_forest(
            project_root,
            seed=config.get("seed"), split_seed=config.get("split_seed"), training_seed=config.get("training_seed"),
            validation_fraction=config["validation_fraction"],
            test_fraction=config["test_fraction"],
        )
    elif model_kind == "gradient_boosting":
        run = train_gradient_boosting(
            project_root,
            seed=config.get("seed"), split_seed=config.get("split_seed"), training_seed=config.get("training_seed"),
            validation_fraction=config["validation_fraction"],
            test_fraction=config["test_fraction"],
            learning_rate=config["learning_rate"],
        )
    else:
        raise TrainingError(f"Unsupported model kind {model_kind!r}.")
    run.runtime_seconds = time.perf_counter() - started
    persist_training_run(project_root, run)
    return run


def verify_training_model_artifact(project_root: Path, run: TrainingRun) -> bool:
    return ArtifactStore(project_root).verify(ArtifactRef(sha256=run.model_artifact_sha256)).valid


def _study_seed_pairs(*, seeds: list[int], randomness_protocol: str, split_seed: int | None, training_seed: int | None) -> list[tuple[int, int]]:
    unique = list(dict.fromkeys(seeds))
    if len(unique) < 3:
        raise TrainingError("A multi-seed study requires at least three distinct seeds.")
    if randomness_protocol == "TRAINING_VARIABILITY":
        return [(int(split_seed if split_seed is not None else 42), seed) for seed in unique]
    if randomness_protocol == "SPLIT_VARIABILITY":
        return [(seed, int(training_seed if training_seed is not None else 42)) for seed in unique]
    if randomness_protocol == "COMBINED_VARIABILITY":
        return [(seed, seed) for seed in unique]
    if randomness_protocol == "LEGACY_COMBINED":
        return [(seed, seed) for seed in unique]
    raise TrainingError(f"Unsupported randomness protocol {randomness_protocol!r}.")


def _select_study_run(values: list[tuple[TrainingRun, float | None]], selection_metric: str) -> tuple[TrainingRun, float, str]:
    """Select deterministically, including an explicit lowest-seed tie-break."""
    if any(value is None for _, value in values):
        raise TrainingError(f"Selection metric {selection_metric!r} is unavailable for this task.")
    rule = "min" if selection_metric in {"mse", "mae", "rmse"} else "max"
    resolved = [(run, float(value)) for run, value in values if value is not None]
    # The explicit second key prevents input-order from becoming an unrecorded
    # scientific selection rule when validation metrics are tied exactly.
    if rule == "min":
        selected, value = min(resolved, key=lambda pair: (pair[1], int(pair[0].training_seed if pair[0].training_seed is not None else pair[0].seed)))
    else:
        selected, value = min(resolved, key=lambda pair: (-pair[1], int(pair[0].training_seed if pair[0].training_seed is not None else pair[0].seed)))
    return selected, value, rule


def run_multi_seed_study(project_root: Path, *, name: str, model_kind: str = "flat_neuro_fuzzy", seeds: list[int], selection_metric: str = "f1", randomness_protocol: str = "LEGACY_COMBINED", split_seed: int | None = None, training_seed: int | None = None, **config) -> TrainingStudy:
    pairs = _study_seed_pairs(seeds=seeds, randomness_protocol=randomness_protocol, split_seed=split_seed, training_seed=training_seed)
    runs = [train_model(project_root, model_kind=model_kind, split_seed=current_split, training_seed=current_training, **config) for current_split, current_training in pairs]
    for run in runs:
        run.randomness_protocol = randomness_protocol
        persist_training_run(project_root, run)
    if selection_metric not in {"accuracy", "precision", "recall", "f1", "mse", "mae", "rmse", "r2"}:
        raise TrainingError(f"Unsupported selection metric {selection_metric!r}.")
    selected, value, rule = _select_study_run([(run, run.validation_metrics.get(selection_metric)) for run in runs], selection_metric)
    study = TrainingStudy(name=name, model_kind=model_kind, task=runs[0].task, selection_metric=selection_metric, selection_rule=rule, seed_runs=runs, selected_run_id=selected.run_id, selection_reason=f"Selected {model_kind} run by declared validation {selection_metric} ({rule}) = {value:.6g}; exact ties select lowest training_seed; locked test was not used.", randomness_protocol=randomness_protocol, split_seed=(pairs[0][0] if len({pair[0] for pair in pairs}) == 1 else None), training_seeds=[pair[1] for pair in pairs])
    _atomic_write_text(_studies_root(project_root) / f"{study.study_id}.json", study.model_dump_json(indent=2))
    _atomic_write_text(_studies_root(project_root) / "active-study.json", json.dumps({"study_id": str(study.study_id)}, indent=2))
    return study


def _persist_study_job(project_root: Path, job: StudyJob) -> None:
    _atomic_write_text(_study_job_path(project_root, job.job_id), job.model_dump_json(indent=2))


def load_study_job(project_root: Path, job_id: UUID) -> StudyJob:
    return StudyJob.model_validate_json(_study_job_path(project_root, job_id).read_text(encoding="utf-8"))


def list_study_jobs(project_root: Path) -> list[StudyJob]:
    """Read persisted job state; no thread-local state is treated as canonical."""
    return sorted(
        (StudyJob.model_validate_json(path.read_text(encoding="utf-8")) for path in _study_jobs_root(project_root).glob("*.json")),
        key=lambda job: (job.created_at, str(job.job_id)),
    )


def cancel_study_job(project_root: Path, job_id: UUID) -> StudyJob:
    job = load_study_job(project_root, job_id)
    if job.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
        return job
    job.cancel_requested = True
    _study_job_cancellations.setdefault(job_id, Event()).set()
    _persist_study_job(project_root, job)
    return job


def _execute_study_job(project_root: Path, job_id: UUID) -> None:
    cancellation = _study_job_cancellations.setdefault(job_id, Event())
    job = load_study_job(project_root, job_id)
    job.status = "RUNNING"
    job.started_at = job.started_at or datetime.now(timezone.utc)
    _persist_study_job(project_root, job)
    successful_runs: list[TrainingRun] = []
    for state in job.seed_states:
        if state.status == "SUCCEEDED":
            if state.run_id is None:
                state.status = "FAILED"; state.error = "Persisted successful seed has no TrainingRun identity."
            else:
                try: successful_runs.append(load_training_run(project_root, state.run_id))
                except (FileNotFoundError, ValueError) as error:
                    state.status = "FAILED"; state.error = f"Persisted TrainingRun cannot be reopened: {error}"
            _persist_study_job(project_root, job)
            continue
        if state.status == "FAILED":
            continue
        if cancellation.is_set() or job.cancel_requested:
            state.status = "CANCELLED"
            for pending in job.seed_states[job.seed_states.index(state) + 1:]:
                if pending.status == "QUEUED":
                    pending.status = "CANCELLED"
            job.status = "CANCELLED"
            job.finished_at = datetime.now(timezone.utc)
            _persist_study_job(project_root, job)
            return
        state.status = "RUNNING"
        _persist_study_job(project_root, job)
        try:
            run = train_model(project_root, model_kind=job.model_kind, split_seed=state.split_seed, training_seed=state.training_seed, **job.execution_config)
            run.randomness_protocol = job.randomness_protocol
            persist_training_run(project_root, run)
            state.status = "SUCCEEDED"
            state.run_id = run.run_id
            state.runtime_seconds = run.runtime_seconds
            successful_runs.append(run)
        except Exception as error:  # persisted job evidence must retain adapter failures
            state.status = "FAILED"
            state.error = str(error)
        _persist_study_job(project_root, job)
    if len(successful_runs) < 3:
        job.status = "FAILED"
        job.error = "Fewer than three seed runs succeeded; no scientific selection was produced."
    else:
        try:
            selection_metric = job.selection_metric
            selected, value, rule = _select_study_run([(run, run.validation_metrics.get(selection_metric)) for run in successful_runs], selection_metric)
            created = TrainingStudy(name=job.name, model_kind=job.model_kind, task=successful_runs[0].task, selection_metric=selection_metric, selection_rule=rule, seed_runs=successful_runs, selected_run_id=selected.run_id, selection_reason=f"Selected {job.model_kind} run by declared validation {selection_metric} ({rule}) = {value:.6g}; exact ties select lowest training_seed; locked test was not used.", randomness_protocol=job.randomness_protocol, split_seed=job.split_seed, training_seeds=[run.training_seed or run.seed for run in successful_runs])
            _atomic_write_text(_studies_root(project_root) / f"{created.study_id}.json", created.model_dump_json(indent=2))
            _atomic_write_text(_studies_root(project_root) / "active-study.json", json.dumps({"study_id": str(created.study_id)}, indent=2))
            job.study_id = created.study_id
            job.status = "SUCCEEDED"
        except Exception as error:
            job.status = "FAILED"
            job.error = str(error)
    job.finished_at = datetime.now(timezone.utc)
    _persist_study_job(project_root, job)


def _submit_study_job(project_root: Path, job_id: UUID) -> StudyJob:
    # Attaching after a Studio reopen is idempotent: an already active local
    # worker remains the sole executor, and callers simply observe its durable
    # job record rather than submitting duplicate training.
    local_executor.submit(project_root=project_root, job_id=job_id, operation=lambda: _execute_study_job(project_root, job_id))
    return load_study_job(project_root, job_id)


def start_study_job(project_root: Path, *, name: str, model_kind: str, seeds: list[int], selection_metric: str, randomness_protocol: str = "LEGACY_COMBINED", split_seed: int | None = None, training_seed: int | None = None, **config) -> StudyJob:
    pairs = _study_seed_pairs(seeds=seeds, randomness_protocol=randomness_protocol, split_seed=split_seed, training_seed=training_seed)
    job = StudyJob(name=name, model_kind=model_kind, selection_metric=selection_metric, seed_states=[StudySeedState(seed=current_training, split_seed=current_split, training_seed=current_training) for current_split, current_training in pairs], randomness_protocol=randomness_protocol, split_seed=(pairs[0][0] if len({pair[0] for pair in pairs}) == 1 else None), execution_config=config)
    _persist_study_job(project_root, job)
    return _submit_study_job(project_root, job.job_id)


def resume_study_job(project_root: Path, job_id: UUID) -> StudyJob:
    """Resume only an interrupted persisted request; never replace its seeds or config."""
    job = load_study_job(project_root, job_id)
    if job.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
        raise TrainingError(f"Study job {job_id} is terminal ({job.status}) and cannot be resumed.")
    if job.cancel_requested:
        raise TrainingError("A cancelled Study job cannot be resumed; create a new declared Study instead.")
    if local_executor.is_active(project_root=project_root, job_id=job_id):
        return job
    for state in job.seed_states:
        if state.status == "RUNNING":
            state.status = "QUEUED"
            state.error = None
    job.status = "QUEUED"
    job.recovery_count += 1
    job.recovery_note = "Explicitly resumed from persisted local execution state; completed seed identities were retained."
    _persist_study_job(project_root, job)
    return _submit_study_job(project_root, job.job_id)


def load_training_study(project_root: Path, study_id: UUID) -> TrainingStudy:
    return TrainingStudy.model_validate_json((_studies_root(project_root) / f"{study_id}.json").read_text(encoding="utf-8"))


def load_latest_training_study(project_root: Path) -> TrainingStudy:
    pointer = json.loads((_studies_root(project_root) / "active-study.json").read_text(encoding="utf-8"))
    return load_training_study(project_root, UUID(pointer["study_id"]))


def create_validation_evaluation(project_root: Path, run_id: UUID) -> AnalysisEvaluation:
    """Persist complete immutable validation evidence without touching final test."""
    run = load_training_run(project_root, run_id)
    contract = load_dataset_contract(project_root)
    if run.dataset_fingerprint is not None and run.dataset_fingerprint != contract.dataset_fingerprint:
        raise TrainingError("The active dataset no longer matches this TrainingRun. Reopen the matching dataset revision before creating an Evaluation.")
    rows = [row.model_copy(deep=True) for row in run.prediction_preview]
    preprocessing_identity = _stable_identity("preprocessing", run.normalization)
    evaluation = AnalysisEvaluation(
        run_id=run.run_id,
        task=run.task,
        target=run.target,
        model_kind=run.model_kind,
        model_artifact_sha256=run.model_artifact_sha256,
        dataset_fingerprint=run.dataset_fingerprint or contract.dataset_fingerprint,
        dataset_artifact_sha256=run.dataset_artifact_sha256 or contract.source_artifact_sha256,
        preprocessing_identity=preprocessing_identity,
        test_status=run.split.test_status,
        metrics=dict(run.validation_metrics),
        prediction_preview=rows,
        validation_row_count=len(rows),
        confusion_matrix=run.confusion_matrix,
        calibration=CalibrationProvenance(bin_count=len(run.calibration)),
        calibration_bins=list(run.calibration),
        threshold=None,
    )
    _atomic_write_text(_evaluation_path(project_root, evaluation.evaluation_id), evaluation.model_dump_json(indent=2))
    _atomic_write_text(
        _evaluations_root(project_root) / "active-evaluation.json",
        json.dumps({"evaluation_id": str(evaluation.evaluation_id)}, indent=2, sort_keys=True),
    )
    return evaluation


def load_validation_evaluation(project_root: Path, evaluation_id: UUID) -> AnalysisEvaluation:
    return AnalysisEvaluation.model_validate_json(
        _evaluation_path(project_root, evaluation_id).read_text(encoding="utf-8")
    )


def load_latest_validation_evaluation(project_root: Path) -> AnalysisEvaluation:
    pointer = json.loads((_evaluations_root(project_root) / "active-evaluation.json").read_text(encoding="utf-8"))
    return load_validation_evaluation(project_root, UUID(pointer["evaluation_id"]))


def fit_validation_calibration(project_root: Path, evaluation_id: UUID) -> CalibrationTransform:
    """Fit and persist Platt scaling on validation evidence only.

    The held-out final-test partition is never loaded by this function.  The
    resulting diagnostics describe the same validation evidence used for fit;
    they must not be interpreted as final-test calibration performance.
    """
    evaluation = load_validation_evaluation(project_root, evaluation_id)
    if evaluation.task != "binary_classification":
        raise TrainingError("Probability calibration is only available for binary classification evaluations.")
    rows = evaluation.prediction_preview
    if not rows:
        raise TrainingError("Validation evaluation contains no prediction evidence to calibrate.")
    targets = np.asarray([int(row.target >= 0.5) for row in rows], dtype=int)
    if len(np.unique(targets)) < 2:
        raise TrainingError("Validation calibration requires both target classes in the validation evidence.")
    logits = np.asarray([float(row.prediction) for row in rows], dtype=float)
    raw_probabilities = np.asarray([
        float(row.probability) if row.probability is not None
        else float(1.0 / (1.0 + np.exp(-np.clip(row.prediction, -60.0, 60.0))))
        for row in rows
    ], dtype=float)

    fitted = LogisticRegression(random_state=0, max_iter=1000)
    fitted.fit(logits.reshape(-1, 1), targets)
    calibrated_probabilities = fitted.predict_proba(logits.reshape(-1, 1))[:, 1]
    before_bins = _calibration_bins_from_probabilities(targets, raw_probabilities)
    after_bins = _calibration_bins_from_probabilities(targets, calibrated_probabilities)
    fit_identity = _stable_identity(
        "validation-calibration",
        {
            "evaluation_id": str(evaluation.evaluation_id),
            "run_id": str(evaluation.run_id),
            "targets": targets.tolist(),
            "logits": logits.tolist(),
        },
    )
    transform = CalibrationTransform(
        evaluation_id=evaluation.evaluation_id,
        run_id=evaluation.run_id,
        fit_sample_count=len(rows),
        fit_sample_identity=fit_identity,
        coefficient=float(fitted.coef_[0][0]),
        intercept=float(fitted.intercept_[0]),
        brier_before=float(np.mean((raw_probabilities - targets) ** 2)),
        brier_after=float(np.mean((calibrated_probabilities - targets) ** 2)),
        ece_before=_ece_from_bins(before_bins, len(rows)),
        ece_after=_ece_from_bins(after_bins, len(rows)),
        calibration_bins=after_bins,
        predictions=[
            CalibratedPrediction(
                row=row.row,
                source_row=row.source_row,
                row_identity=row.row_identity,
                target=float(row.target),
                raw_probability=float(raw_probability),
                calibrated_probability=float(calibrated_probability),
            )
            for row, raw_probability, calibrated_probability in zip(
                rows, raw_probabilities, calibrated_probabilities, strict=True
            )
        ],
    )
    _atomic_write_text(_calibration_path(project_root, transform.calibration_id), transform.model_dump_json(indent=2))
    _atomic_write_text(
        _calibrations_root(project_root) / "active-calibration.json",
        json.dumps({"calibration_id": str(transform.calibration_id)}, indent=2, sort_keys=True),
    )
    return transform


def load_validation_calibration(project_root: Path, calibration_id: UUID) -> CalibrationTransform:
    return CalibrationTransform.model_validate_json(
        _calibration_path(project_root, calibration_id).read_text(encoding="utf-8")
    )


def load_latest_validation_calibration(project_root: Path) -> CalibrationTransform:
    pointer = json.loads((_calibrations_root(project_root) / "active-calibration.json").read_text(encoding="utf-8"))
    return load_validation_calibration(project_root, UUID(pointer["calibration_id"]))


def _latest_calibration_for_run(project_root: Path, run_id: UUID) -> CalibrationTransform | None:
    matches: list[CalibrationTransform] = []
    for path in _calibrations_root(project_root).glob("*.json"):
        try:
            UUID(path.stem)
        except ValueError:
            continue
        try:
            item = CalibrationTransform.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if item.run_id == run_id:
            matches.append(item)
    return max(matches, key=lambda item: item.created_at) if matches else None


def select_validation_threshold(
    project_root: Path,
    evaluation_id: UUID,
    *,
    calibration_id: UUID | None = None,
    objective: str = "f1",
) -> DecisionThresholdPolicy:
    """Select and persist a decision threshold using validation evidence only."""
    if objective != "f1":
        raise TrainingError("Product V1 currently supports validation F1 threshold selection only.")
    evaluation = load_validation_evaluation(project_root, evaluation_id)
    if evaluation.task != "binary_classification":
        raise TrainingError("Decision-threshold selection is only available for binary classification evaluations.")
    rows = evaluation.prediction_preview
    if not rows:
        raise TrainingError("Validation evaluation contains no prediction evidence for threshold selection.")
    targets = np.asarray([int(row.target >= 0.5) for row in rows], dtype=int)
    calibration: CalibrationTransform | None = None
    if calibration_id is not None:
        calibration = load_validation_calibration(project_root, calibration_id)
        if calibration.evaluation_id != evaluation.evaluation_id or calibration.run_id != evaluation.run_id:
            raise TrainingError("Calibration transform does not belong to the selected validation evaluation.")
        by_row = {item.row: item.calibrated_probability for item in calibration.predictions}
        if any(row.row not in by_row for row in rows):
            raise TrainingError("Calibration transform does not cover the complete validation evidence.")
        probabilities = np.asarray([by_row[row.row] for row in rows], dtype=float)
        probability_source = "calibrated"
        sample_identity = calibration.fit_sample_identity
    else:
        probabilities = np.asarray([
            float(row.probability) if row.probability is not None
            else float(1.0 / (1.0 + np.exp(-np.clip(row.prediction, -60.0, 60.0))))
            for row in rows
        ], dtype=float)
        probability_source = "raw"
        sample_identity = _stable_identity(
            "validation-threshold",
            {
                "evaluation_id": str(evaluation.evaluation_id),
                "run_id": str(evaluation.run_id),
                "targets": targets.tolist(),
                "probabilities": probabilities.tolist(),
            },
        )

    candidates = np.round(np.arange(0.01, 1.0, 0.01), 2)
    scores = np.asarray([f1_score(targets, probabilities >= candidate, zero_division=0) for candidate in candidates], dtype=float)
    best_score = float(scores.max())
    best_candidates = candidates[np.isclose(scores, best_score, rtol=0.0, atol=1e-12)]
    selected = float(sorted(best_candidates.tolist(), key=lambda value: (abs(value - 0.5), value))[0])
    metrics, confusion, labels = _classification_metrics_at_threshold(targets, probabilities, selected)
    policy = DecisionThresholdPolicy(
        evaluation_id=evaluation.evaluation_id,
        run_id=evaluation.run_id,
        calibration_id=None if calibration is None else calibration.calibration_id,
        probability_source=probability_source,
        candidate_rule="thresholds 0.01 through 0.99; maximize validation F1; ties choose closest to 0.50, then lower threshold",
        selected_threshold=selected,
        selection_result=best_score,
        fit_sample_identity=sample_identity,
        metrics=metrics,
        confusion_matrix=confusion,
        decisions=[
            ThresholdDecision(
                row=row.row,
                target=int(target),
                probability=float(probability),
                predicted_label=int(label),
            )
            for row, target, probability, label in zip(rows, targets, probabilities, labels, strict=True)
        ],
    )
    _atomic_write_text(_threshold_path(project_root, policy.threshold_id), policy.model_dump_json(indent=2))
    _atomic_write_text(
        _thresholds_root(project_root) / "active-threshold.json",
        json.dumps({"threshold_id": str(policy.threshold_id)}, indent=2, sort_keys=True),
    )
    return policy


def load_decision_threshold(project_root: Path, threshold_id: UUID) -> DecisionThresholdPolicy:
    return DecisionThresholdPolicy.model_validate_json(
        _threshold_path(project_root, threshold_id).read_text(encoding="utf-8")
    )


def load_latest_decision_threshold(project_root: Path) -> DecisionThresholdPolicy:
    pointer = json.loads((_thresholds_root(project_root) / "active-threshold.json").read_text(encoding="utf-8"))
    return load_decision_threshold(project_root, UUID(pointer["threshold_id"]))


def _latest_threshold_for_run(project_root: Path, run_id: UUID) -> DecisionThresholdPolicy | None:
    matches: list[DecisionThresholdPolicy] = []
    for path in _thresholds_root(project_root).glob("*.json"):
        try:
            UUID(path.stem)
        except ValueError:
            continue
        try:
            item = DecisionThresholdPolicy.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if item.run_id == run_id:
            matches.append(item)
    return max(matches, key=lambda item: item.created_at) if matches else None


def _tree_declarative_output(tree: dict, vector: np.ndarray, *, task: str) -> float:
    node = 0
    while int(tree["children_left"][node]) != -1:
        feature_index = int(tree["feature_index"][node])
        threshold = float(tree["threshold"][node])
        node = int(tree["children_left"][node]) if float(vector[feature_index]) <= threshold else int(tree["children_right"][node])
    values = np.asarray(tree["values"][node], dtype=float).reshape(-1)
    if task == TaskType.BINARY_CLASSIFICATION.value:
        total = float(values.sum())
        return 0.5 if total <= 0.0 else float(values[1] / total)
    return float(values[0])


def _predict_persisted_run_normalized(
    project_root: Path,
    run: TrainingRun,
    normalized_features: np.ndarray,
) -> np.ndarray:
    """Replay one frozen TrainingRun without refitting anything.

    For binary classification the return value is the same raw/logit space that
    validation calibration consumed. Regression returns the model prediction.
    """
    matrix = np.asarray(normalized_features, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    if matrix.shape[1] != len(run.feature_columns):
        raise TrainingError("Final-test features do not match the frozen TrainingRun feature order.")

    if run.model_kind == "flat_neuro_fuzzy":
        spec = ShallowModelSpec.from_dict(run.model_spec)
        model = FlatNeuroFuzzyModel(spec)
        with ArtifactStore(project_root).open(ArtifactRef(sha256=run.model_artifact_sha256)) as handle:
            raw_bundle = handle.read()
        with tempfile.NamedTemporaryFile(prefix="ruflex-final-test-", suffix=".pt", delete=False) as handle:
            handle.write(raw_bundle)
            bundle_path = Path(handle.name)
        try:
            model.load_bundle(bundle_path)
            return np.asarray(model.predict(matrix), dtype=float).reshape(-1)
        finally:
            bundle_path.unlink(missing_ok=True)

    with ArtifactStore(project_root).open(ArtifactRef(sha256=run.model_artifact_sha256)) as handle:
        payload = json.loads(handle.read().decode("utf-8"))

    if run.model_kind in {"logistic_regression", "linear_regression"}:
        coefficients = np.asarray(payload["coefficients"], dtype=float).reshape(-1)
        return np.asarray(matrix @ coefficients + float(payload["intercept"]), dtype=float).reshape(-1)

    if run.model_kind == "decision_tree":
        outputs = np.asarray([
            _tree_declarative_output(payload["tree"], row, task=run.task) for row in matrix
        ], dtype=float)
        if run.task == TaskType.BINARY_CLASSIFICATION.value:
            clipped = np.clip(outputs, 1e-12, 1.0 - 1e-12)
            return np.log(clipped / (1.0 - clipped))
        return outputs

    if run.model_kind == "random_forest":
        outputs = np.asarray([
            float(np.mean([_tree_declarative_output(tree, row, task=run.task) for tree in payload["trees"]]))
            for row in matrix
        ], dtype=float)
        if run.task == TaskType.BINARY_CLASSIFICATION.value:
            clipped = np.clip(outputs, 1e-12, 1.0 - 1e-12)
            return np.log(clipped / (1.0 - clipped))
        return outputs

    if run.model_kind == "gradient_boosting":
        initial = payload.get("initial_raw_prediction")
        if initial is None:
            raise TrainingError(
                "This Gradient Boosting artifact predates reproducible ensemble replay. Retrain it before final-test evaluation."
            )
        learning_rate = float(payload["parameters"]["learning_rate"])
        return np.asarray([
            float(initial) + learning_rate * sum(
                _tree_declarative_output(tree, row, task=TaskType.REGRESSION.value)
                for tree in payload["trees"]
            )
            for row in matrix
        ], dtype=float)

    raise TrainingError(f"Final-test replay is unavailable for model kind {run.model_kind!r}.")


def evaluate_final_test(
    project_root: Path,
    evaluation_id: UUID,
    *,
    calibration_id: UUID | None = None,
    threshold_id: UUID | None = None,
    selective_policy_id: UUID | None = None,
    stability_gate_policy_id: UUID | None = None,
) -> FinalTestEvaluation:
    """Explicitly evaluate the frozen final-test split without any test-time fitting.

    The split is reconstructed from the immutable run protocol. Calibration and
    threshold policies, when used, must already exist and must belong to the
    selected validation evaluation. Nothing is selected from final-test results.
    """
    evaluation = load_validation_evaluation(project_root, evaluation_id)
    run = load_training_run(project_root, evaluation.run_id)
    contract = load_dataset_contract(project_root)
    if run.dataset_fingerprint is None or run.dataset_artifact_sha256 is None:
        raise TrainingError("Final-test evaluation requires dataset provenance on the frozen TrainingRun.")
    if contract.dataset_fingerprint != run.dataset_fingerprint or contract.source_artifact_sha256 != run.dataset_artifact_sha256:
        raise TrainingError(
            "The active dataset revision does not match the frozen TrainingRun. Reopen the matching dataset before final-test evaluation."
        )
    if evaluation.dataset_fingerprint != run.dataset_fingerprint or evaluation.model_artifact_sha256 != run.model_artifact_sha256:
        raise TrainingError("Validation Evaluation provenance does not match the frozen TrainingRun.")

    calibration: CalibrationTransform | None = None
    threshold: DecisionThresholdPolicy | None = None
    selective_policy = None
    stability_gate_policy = None
    if calibration_id is not None:
        calibration = load_validation_calibration(project_root, calibration_id)
        if calibration.evaluation_id != evaluation.evaluation_id or calibration.run_id != run.run_id:
            raise TrainingError("Calibration transform does not belong to this validation Evaluation/TrainingRun.")
    if threshold_id is not None:
        threshold = load_decision_threshold(project_root, threshold_id)
        if threshold.evaluation_id != evaluation.evaluation_id or threshold.run_id != run.run_id:
            raise TrainingError("Decision-threshold policy does not belong to this validation Evaluation/TrainingRun.")
        if threshold.probability_source == "calibrated":
            if calibration is None or threshold.calibration_id != calibration.calibration_id:
                raise TrainingError("The selected threshold requires its exact persisted validation calibration transform.")
        else:
            if threshold.calibration_id is not None:
                raise TrainingError("Raw-probability threshold provenance unexpectedly references calibration.")
            if calibration is not None:
                raise TrainingError("A raw-probability threshold does not use calibration; omit calibration_id for final-test evaluation.")
    if selective_policy_id is not None:
        from ruflex.application.selective import load_selective_policy
        selective_policy = load_selective_policy(project_root, selective_policy_id)
        if selective_policy.evaluation_id != evaluation.evaluation_id or selective_policy.run_id != run.run_id:
            raise TrainingError("Selective-review policy does not belong to this validation Evaluation/TrainingRun.")
        if threshold is None or selective_policy.class_threshold_id != threshold.threshold_id:
            raise TrainingError("Final-test selective policy requires its exact bound DecisionThreshold policy.")
        if selective_policy.calibration_id != (None if calibration is None else calibration.calibration_id):
            raise TrainingError("Final-test selective policy requires its exact bound calibration policy.")
    if stability_gate_policy_id is not None:
        from ruflex.application.stability import load_stability_gate_policy, load_study_stability_analysis
        stability_gate_policy = load_stability_gate_policy(project_root, stability_gate_policy_id)
        if stability_gate_policy.evaluation_id != evaluation.evaluation_id or stability_gate_policy.selected_run_id != run.run_id:
            raise TrainingError("Stability Gate policy does not belong to this validation Evaluation/selected TrainingRun.")
        if threshold is None or stability_gate_policy.class_threshold_id != threshold.threshold_id or stability_gate_policy.decision_threshold != threshold.selected_threshold or threshold.probability_source != "raw":
            raise TrainingError("Final-test Stability Gate requires its exact raw validation-derived DecisionThreshold policy.")
        stability_analysis = load_study_stability_analysis(project_root, stability_gate_policy.stability_analysis_id)
        if stability_analysis.applicability != "APPLICABLE" or stability_analysis.validation_alignment_status != "EXACT_MATCH":
            raise TrainingError("Final-test binding requires applicable fixed-split Stability Gate evidence.")
        if stability_gate_policy.run_ids != stability_analysis.run_ids or stability_gate_policy.dataset_fingerprint != run.dataset_fingerprint:
            raise TrainingError("Stability Gate provenance does not match its frozen study/dataset evidence.")
        if run.run_id not in stability_gate_policy.run_ids:
            raise TrainingError("Selected TrainingRun is not one of the frozen Stability Gate study runs.")

    if run.task == TaskType.BINARY_CLASSIFICATION.value and threshold is None:
        raise TrainingError(
            "Binary final-test evaluation requires a persisted validation-derived decision-threshold policy. "
            "Select the decision policy before explicitly opening the final test."
        )
    if run.task == TaskType.REGRESSION.value and (calibration is not None or threshold is not None):
        raise TrainingError("Calibration and decision-threshold policies are not applicable to regression final-test evaluation.")
    if run.dataset_fingerprint is None:
        raise TrainingError(
            "Frozen TrainingRun lacks DatasetContract fingerprint; cannot establish typed final-test row identities."
        )

    # Collect prior final-test evidence for this dataset revision. Repeating an
    # identical frozen policy is idempotent. Different policies are allowed only
    # when every policy object existed before the first final-test access and the
    # reconstructed holdout rows are exactly the same. This supports legitimate
    # pre-specified baseline comparisons without allowing post-test policy shopping.
    prior_final_tests: list[FinalTestEvaluation] = []
    for path in _final_tests_root(project_root).glob("*.json"):
        try:
            UUID(path.stem)
        except ValueError:
            continue
        try:
            prior = FinalTestEvaluation.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if prior.dataset_fingerprint != run.dataset_fingerprint:
            continue
        same_policy = (
            prior.run_id == run.run_id
            and prior.evaluation_id == evaluation.evaluation_id
            and prior.calibration_id == (None if calibration is None else calibration.calibration_id)
            and prior.threshold_id == (None if threshold is None else threshold.threshold_id)
            and prior.selective_policy_id == (None if selective_policy is None else selective_policy.policy_id)
            and prior.stability_gate_policy_id == (None if stability_gate_policy is None else stability_gate_policy.policy_id)
        )
        if same_policy:
            return prior
        prior_final_tests.append(prior)

    frame = load_dataset_frame(project_root)
    split = TabularDataset.from_dataframe(frame).split(DatasetConfig(
        target_column=run.target,
        feature_columns=tuple(run.feature_columns),
        validation_fraction=run.split.validation_fraction,
        test_fraction=run.split.test_fraction,
        normalization=NormalizationMode(run.normalization["mode"]),
        fill_missing="median",
        random_state=run.split.split_seed if run.split.split_seed is not None else run.seed,
    ))
    if split.test_features.shape[0] == 0:
        raise TrainingError("The frozen TrainingRun has no final-test rows to evaluate.")
    if len(split.test_indices) != run.split.test_count:
        raise TrainingError("Reconstructed final-test row count does not match the frozen TrainingRun provenance.")
    reconstructed_preprocessing = _stable_identity("preprocessing", split.normalization.to_dict())
    expected_preprocessing = _stable_identity("preprocessing", run.normalization)
    if reconstructed_preprocessing != expected_preprocessing:
        raise TrainingError("Train-derived preprocessing no longer reproduces the frozen TrainingRun.")

    test_case_identity = _stable_identity(
        "final-test-cases",
        {
            "dataset_fingerprint": run.dataset_fingerprint,
            "row_identities": sorted(row_identity(run.dataset_fingerprint, int(value)) for value in np.asarray(split.test_indices, dtype=int).reshape(-1)),
        },
    )
    policy_frozen_at = max(
        item.created_at
        for item in [run, evaluation, calibration, threshold, selective_policy, stability_gate_policy]
        if item is not None
    )
    if prior_final_tests:
        dataset_test_unlock_at = min(
            prior.dataset_test_unlock_at or prior.created_at
            for prior in prior_final_tests
        )
        if policy_frozen_at > dataset_test_unlock_at:
            raise TrainingError(
                "Final test has already been opened for this dataset revision. "
                "This model/evaluation/calibration/threshold policy was created after first test access and cannot be evaluated on the holdout."
            )
        if stability_gate_policy is not None:
            # A test-time gate evaluation may use several models, but all of
            # them must have been frozen before this dataset's first holdout
            # access.  This prevents adding a freshly trained "supporting"
            # run after seeing final-test outcomes.
            for study_run_id in stability_gate_policy.run_ids:
                study_run = load_training_run(project_root, study_run_id)
                if study_run.created_at > dataset_test_unlock_at:
                    raise TrainingError("A Stability Gate study run was created after final-test access and cannot be applied to the holdout.")
        for prior in prior_final_tests:
            prior_case_identity = prior.test_case_identity
            if prior_case_identity is None:
                prior_case_identity = _stable_identity(
                    "final-test-cases",
                    {
                        "dataset_fingerprint": prior.dataset_fingerprint,
                        "row_identities": sorted(
                            row.row_identity or row_identity(prior.dataset_fingerprint, int(row.source_row))
                            for row in prior.prediction_rows
                            if row.source_row is not None
                        ),
                    },
                )
            if prior_case_identity != test_case_identity:
                raise TrainingError(
                    "The candidate policy was frozen before test access, but its TrainingRun reconstructs different final-test rows. "
                    "RuFLEX will not compare policies on different holdout cases under one dataset final-test gate."
                )
    else:
        dataset_test_unlock_at = datetime.now(timezone.utc)

    raw_predictions = _predict_persisted_run_normalized(project_root, run, split.test_features)
    targets = np.asarray(split.test_targets, dtype=float).reshape(-1)
    source_rows = np.asarray(split.test_indices, dtype=int).reshape(-1)

    if run.task == TaskType.BINARY_CLASSIFICATION.value:
        truth = (targets >= 0.5).astype(int)
        raw_probabilities = 1.0 / (1.0 + np.exp(-np.clip(raw_predictions, -60.0, 60.0)))
        calibrated_probabilities: np.ndarray | None = None
        if calibration is not None:
            calibrated_logits = calibration.coefficient * raw_predictions + calibration.intercept
            calibrated_probabilities = 1.0 / (1.0 + np.exp(-np.clip(calibrated_logits, -60.0, 60.0)))
        assert threshold is not None
        probabilities = calibrated_probabilities if threshold.probability_source == "calibrated" else raw_probabilities
        assert probabilities is not None
        metrics, confusion, labels = _classification_metrics_at_threshold(
            truth, probabilities, threshold.selected_threshold
        )
        metrics["brier"] = float(np.mean((probabilities - truth) ** 2))
        bins = _calibration_bins_from_probabilities(truth, probabilities)
        metrics["ece"] = _ece_from_bins(bins, len(truth))
        if len(np.unique(truth)) == 2:
            metrics["roc_auc"] = float(roc_auc_score(truth, probabilities))
            metrics["pr_auc"] = float(average_precision_score(truth, probabilities))
        rows = [
            PredictionRow(
                row=index,
                source_row=int(source_row),
                row_identity=row_identity(run.dataset_fingerprint, int(source_row)),
                target=float(target),
                prediction=float(raw_prediction),
                probability=float(raw_probability),
                calibrated_probability=None if calibrated_probabilities is None else float(calibrated_probabilities[index]),
                predicted_label=int(label),
            )
            for index, (source_row, target, raw_prediction, raw_probability, label) in enumerate(
                zip(source_rows, targets, raw_predictions, raw_probabilities, labels, strict=True)
            )
        ]
        probability_source = threshold.probability_source
        decision_threshold = threshold.selected_threshold
        stability_evidence = None
        if stability_gate_policy is not None:
            from ruflex.application.stability import evaluate_frozen_stability_probabilities
            gate_runs = [load_training_run(project_root, run_id) for run_id in stability_gate_policy.run_ids]
            if any(item.split.split_identity != run.split.split_identity or item.dataset_fingerprint != run.dataset_fingerprint for item in gate_runs):
                raise TrainingError("Stability Gate runs do not reconstruct the frozen selected-run final-test split.")
            if any(_stable_identity("preprocessing", item.normalization) != expected_preprocessing for item in gate_runs):
                raise TrainingError("Stability Gate runs do not share the selected-run frozen preprocessing identity.")
            all_probabilities = {
                str(item.run_id): 1.0 / (1.0 + np.exp(-np.clip(_predict_persisted_run_normalized(project_root, item, split.test_features), -60.0, 60.0)))
                for item in gate_runs
            }
            gate_cases = []
            for index, source_row in enumerate(source_rows):
                application = evaluate_frozen_stability_probabilities(stability_gate_policy, {run_id: float(values[index]) for run_id, values in all_probabilities.items()})
                identity = row_identity(run.dataset_fingerprint, int(source_row))
                gate_cases.append(FinalTestStabilityCase(case_id=identity, source_row=int(source_row), row_identity=identity, target=int(truth[index]), selected_run_probability=application.selected_run_probability, selected_run_class=application.predicted_label, majority_class_agreement=application.majority_class_agreement, selected_run_agreement=application.selected_run_agreement, probability_std=application.probability_std, disposition=application.disposition, reasons=application.reasons))
            accepted = [case for case in gate_cases if case.disposition == "ACCEPT"]
            reviews = [case for case in gate_cases if case.disposition == "REVIEW"]
            blocks = [case for case in gate_cases if case.disposition == "BLOCK"]
            accepted_error = None if not accepted else float(np.mean([case.selected_run_class != case.target for case in accepted]))
            accepted_fn = sum(case.selected_run_class == 0 and case.target == 1 for case in accepted)
            accepted_positives = sum(case.target == 1 for case in accepted)
            confidence_only = sorted(gate_cases, key=lambda case: max(case.selected_run_probability, 1.0 - case.selected_run_probability), reverse=True)[:len(accepted)]
            confidence_error = None if not confidence_only else float(np.mean([case.selected_run_class != case.target for case in confidence_only]))
            stability_evidence = FinalTestStabilityEvidence(policy_id=stability_gate_policy.policy_id, class_threshold_id=stability_gate_policy.class_threshold_id, decision_threshold=stability_gate_policy.decision_threshold, run_ids=stability_gate_policy.run_ids, cases=gate_cases, accepted_count=len(accepted), review_count=len(reviews), block_count=len(blocks), coverage=len(accepted) / len(gate_cases), accepted_error=accepted_error, accepted_false_negative_count=accepted_fn, accepted_false_negative_rate=None if accepted_positives == 0 else accepted_fn / accepted_positives, confidence_only_accepted_error=confidence_error, confidence_only_accepted_count=len(confidence_only))
    else:
        metrics = _baseline_metrics(run.task, targets, raw_predictions)
        confusion = None
        bins = []
        rows = [
            PredictionRow(
                row=index,
                source_row=int(source_row),
                row_identity=row_identity(run.dataset_fingerprint, int(source_row)),
                target=float(target),
                prediction=float(prediction),
                residual=float(target - prediction),
            )
            for index, (source_row, target, prediction) in enumerate(
                zip(source_rows, targets, raw_predictions, strict=True)
            )
        ]
        probability_source = "not_applicable"
        decision_threshold = None
        stability_evidence = None

    test_sample_identity = _stable_identity(
        "final-test-samples",
        {
            "dataset_fingerprint": run.dataset_fingerprint,
            "run_id": str(run.run_id),
            "source_rows": sorted(int(value) for value in source_rows),
        },
    )
    policy_identity = _stable_identity(
        "final-test-policy",
        {
            "run_id": str(run.run_id),
            "evaluation_id": str(evaluation.evaluation_id),
            "model_artifact": run.model_artifact_sha256,
            "preprocessing": expected_preprocessing,
            "calibration_id": None if calibration is None else str(calibration.calibration_id),
            "threshold_id": None if threshold is None else str(threshold.threshold_id),
            "selective_policy_id": None if selective_policy is None else str(selective_policy.policy_id),
            "stability_gate_policy_id": None if stability_gate_policy is None else str(stability_gate_policy.policy_id),
        },
    )
    result = FinalTestEvaluation(
        created_at=datetime.now(timezone.utc),
        run_id=run.run_id,
        evaluation_id=evaluation.evaluation_id,
        task=run.task,
        target=run.target,
        model_kind=run.model_kind,
        model_artifact_sha256=run.model_artifact_sha256,
        dataset_fingerprint=run.dataset_fingerprint,
        dataset_artifact_sha256=run.dataset_artifact_sha256,
        preprocessing_identity=expected_preprocessing,
        calibration_id=None if calibration is None else calibration.calibration_id,
        threshold_id=None if threshold is None else threshold.threshold_id,
        selective_policy_id=None if selective_policy is None else selective_policy.policy_id,
        stability_gate_policy_id=None if stability_gate_policy is None else stability_gate_policy.policy_id,
        stability_gate_evidence=stability_evidence,
        probability_source=probability_source,
        decision_threshold=decision_threshold,
        metrics=metrics,
        prediction_rows=rows,
        test_row_count=len(rows),
        confusion_matrix=confusion,
        calibration_bins=bins,
        test_sample_identity=test_sample_identity,
        test_case_identity=test_case_identity,
        policy_identity=policy_identity,
        policy_frozen_at=policy_frozen_at,
        dataset_test_unlock_at=dataset_test_unlock_at,
    )
    _atomic_write_text(_final_test_path(project_root, result.final_test_id), result.model_dump_json(indent=2))
    _atomic_write_text(
        _final_tests_root(project_root) / "active-final-test.json",
        json.dumps({"final_test_id": str(result.final_test_id)}, indent=2, sort_keys=True),
    )
    return result


def load_final_test_evaluation(project_root: Path, final_test_id: UUID) -> FinalTestEvaluation:
    return FinalTestEvaluation.model_validate_json(
        _final_test_path(project_root, final_test_id).read_text(encoding="utf-8")
    )


def load_latest_final_test_evaluation(project_root: Path) -> FinalTestEvaluation:
    pointer = json.loads((_final_tests_root(project_root) / "active-final-test.json").read_text(encoding="utf-8"))
    return load_final_test_evaluation(project_root, UUID(pointer["final_test_id"]))


def _validation_sample_identity(run: TrainingRun) -> str | None:
    """Return a stable identity for the validation cases used by a run.

    Source-row indices are persisted with validation predictions, so this
    identity lets comparisons distinguish same-case evaluation from
    seed-resampled validation sets without touching the locked final test.
    """
    if run.dataset_fingerprint is None or not run.prediction_preview or any(row.source_row is None for row in run.prediction_preview):
        return None
    return _stable_identity(
        "validation-samples",
        {
            "dataset_fingerprint": run.dataset_fingerprint,
            "target": run.target,
            "row_identities": sorted(
                row.row_identity or row_identity(run.dataset_fingerprint, int(row.source_row))
                for row in run.prediction_preview if row.source_row is not None
            ),
        },
    )


def _manual_fis_comparison_row(
    project_root: Path,
    reference_run: TrainingRun,
    validation_identity: str,
) -> tuple[dict[str, float | str], UUID, str]:
    """Evaluate the active manual FIS on exactly the reference run's validation cases.

    The FIS consumes its declared raw dataset features.  We intentionally do not
    borrow a trained model's normalization or invent probability semantics.  For
    binary tasks a bounded [0, 1] FIS output is treated as a decision/ranking
    score with a declared 0.5 cutoff; calibration metrics remain unavailable.
    """
    from ruflex.application.fis import FISError, evaluate_fis, load_fis
    from ruflex.application.model_catalog import list_model_catalog

    spec = load_fis(project_root)
    if spec.semantic_hash is None:
        raise TrainingError("The active FIS must be saved with a semantic hash before comparison.")
    contract = load_dataset_contract(project_root)
    if reference_run.dataset_fingerprint and reference_run.dataset_fingerprint != contract.dataset_fingerprint:
        raise TrainingError(
            "The active dataset revision does not match the trained run used to declare FIS validation cases."
        )
    frame = load_dataset_frame(project_root)
    mapping: dict[str, str] = {}
    for variable in spec.inputs:
        column = variable.dataset_feature or variable.name
        if column not in frame.columns:
            raise TrainingError(
                f"Manual FIS input {variable.name!r} is not mapped to an available dataset column."
            )
        mapping[variable.name] = column

    source_rows = [row.source_row for row in reference_run.prediction_preview]
    if not source_rows or any(row is None for row in source_rows):
        raise TrainingError(
            "The reference run predates source-row provenance; a same-case manual FIS comparison cannot be proven."
        )
    outputs: list[float] = []
    started = time.perf_counter()
    for source_row in source_rows:
        assert source_row is not None
        if source_row < 0 or source_row >= len(frame):
            raise TrainingError("Persisted validation source-row identity is outside the active dataset artifact.")
        record = frame.iloc[int(source_row)]
        values: dict[str, float] = {}
        for variable_name, column in mapping.items():
            value = pd.to_numeric(pd.Series([record[column]]), errors="coerce").iloc[0]
            if pd.isna(value) or not np.isfinite(float(value)):
                raise TrainingError(
                    f"Manual FIS comparison found a non-finite validation value in {column!r}. "
                    "No imputation semantics are invented for an expert-authored FIS."
                )
            values[variable_name] = float(value)
        try:
            outputs.append(float(evaluate_fis(spec, values).output))
        except FISError as error:
            raise TrainingError(
                f"Manual FIS is undefined for validation source row {source_row}: {error}"
            ) from error
    runtime = time.perf_counter() - started
    targets = np.asarray([row.target for row in reference_run.prediction_preview], dtype=float)
    predictions = np.asarray(outputs, dtype=float)

    if reference_run.task == TaskType.BINARY_CLASSIFICATION.value:
        if spec.output.minimum < -1e-12 or spec.output.maximum > 1.0 + 1e-12:
            raise TrainingError(
                "Binary manual FIS comparison requires a declared output range within [0, 1]. "
                "RuFLEX will not silently rescale an expert score into probability space."
            )
        truth = (targets >= 0.5).astype(int)
        scores = np.clip(predictions, 0.0, 1.0)
        labels = (scores >= 0.5).astype(int)
        metrics: dict[str, float] = {
            "accuracy": float(accuracy_score(truth, labels)),
            "precision": float(precision_score(truth, labels, zero_division=0)),
            "recall": float(recall_score(truth, labels, zero_division=0)),
            "f1": float(f1_score(truth, labels, zero_division=0)),
        }
        if len(np.unique(truth)) == 2:
            metrics["roc_auc"] = float(roc_auc_score(truth, scores))
            metrics["pr_auc"] = float(average_precision_score(truth, scores))
        score_semantics = "bounded_0_1_score_not_calibrated_probability"
        threshold_status = "declared_fixed_score_cutoff_0.5"
    else:
        metrics = _baseline_metrics(reference_run.task, targets, predictions)
        score_semantics = "regression_output"
        threshold_status = "not_applicable"

    catalog = {entry["key"]: entry["capabilities"] for entry in list_model_catalog()}
    capabilities = catalog.get(spec.system_type, {})
    row: dict[str, float | str] = {
        "subject_id": f"fis:{spec.fis_id}",
        "subject_type": "manual_fis",
        "model_kind": spec.system_type,
        "seed": "manual",
        "runtime_seconds": float(runtime),
        "protocol_split": "validation",
        "test_status": reference_run.split.test_status,
        "model_artifact": spec.semantic_hash[:12],
        "preprocessing_identity": _stable_identity("fis-raw-input-mapping", mapping),
        "validation_sample_identity": validation_identity,
        "calibration_status": "not_fitted_probability_semantics_not_claimed",
        "threshold_status": threshold_status,
        "score_semantics": score_semantics,
        "rule_count": float(len(spec.rules)),
        "input_count": float(len(spec.inputs)),
        "term_count": float(sum(len(variable.terms) for variable in spec.inputs) + len(spec.output.terms)),
        "exact_semantic_trace": "yes",
        "capabilities": ", ".join(sorted(key for key, enabled in capabilities.items() if enabled)) or "none",
        **metrics,
    }
    return row, spec.fis_id, spec.semantic_hash


def create_validation_comparison(
    project_root: Path,
    run_ids: list[UUID],
    *,
    include_active_fis: bool = False,
) -> AnalysisComparison:
    runs = [load_training_run(project_root, run_id) for run_id in dict.fromkeys(run_ids)]
    if len(runs) + int(include_active_fis) < 2:
        raise TrainingError("A comparison requires at least two distinct model/run subjects.")
    if not runs:
        raise TrainingError("Manual FIS comparison requires at least one trained run to declare validation cases.")
    if len({run.task for run in runs}) != 1 or len({run.target for run in runs}) != 1:
        raise TrainingError("Only runs with the same task and target can be compared.")
    if any(run.evaluation_split != "validation" or run.split.test_status != "LOCKED_NOT_EVALUATED" for run in runs):
        raise TrainingError("Comparison requires validation-only runs with a locked test split.")
    dataset_fingerprints = {run.dataset_fingerprint for run in runs if run.dataset_fingerprint is not None}
    if len(dataset_fingerprints) > 1:
        raise TrainingError("Runs from different dataset revisions cannot be compared as one validation protocol.")

    validation_sample_identities = {
        str(run.run_id): identity
        for run in runs
        if (identity := _validation_sample_identity(run)) is not None
    }
    if len(validation_sample_identities) != len(runs):
        validation_alignment = "unknown"
        alignment_note = (
            "Validation case identity is unavailable for at least one legacy run, so same-case alignment cannot be proven."
        )
    elif len(set(validation_sample_identities.values())) == 1:
        validation_alignment = "same_cases"
        alignment_note = "All selected runs were evaluated on the same persisted validation cases."
    else:
        validation_alignment = "mixed_cases"
        alignment_note = (
            "Selected runs use different seed-derived validation cases. Metrics are suitable for describing resampled "
            "validation variability, but this is not a paired same-case model comparison."
        )

    from ruflex.application.model_catalog import list_model_catalog

    catalog = {entry["key"]: entry["capabilities"] for entry in list_model_catalog()}
    rows: list[dict[str, float | str]] = []
    for run in runs:
        catalog_key = "linear" if run.model_kind in {"logistic_regression", "linear_regression"} else run.model_kind
        capabilities = catalog.get(catalog_key, {})
        calibration = _latest_calibration_for_run(project_root, run.run_id)
        threshold = _latest_threshold_for_run(project_root, run.run_id)
        row: dict[str, float | str] = {
            "subject_id": f"run:{run.run_id}",
            "subject_type": "training_run",
            "run_id": str(run.run_id),
            "model_kind": run.model_kind,
            "seed": float(run.seed),
            "runtime_seconds": float(run.runtime_seconds),
            "protocol_split": "validation",
            "test_status": run.split.test_status,
            "model_artifact": run.model_artifact_sha256[:12],
            "preprocessing_identity": _stable_identity("preprocessing", run.normalization),
            "calibration_status": "fitted_validation_only" if calibration else "not_fitted",
            "threshold_status": "selected_validation_only" if threshold else "not_selected",
            "exact_tree_path": "yes" if capabilities.get("exact_tree_path") else "no",
            "structural_trace": "yes" if capabilities.get("structural_trace") else "no",
            "capabilities": ", ".join(sorted(key for key, enabled in capabilities.items() if enabled)) or "none",
            **{key: float(value) for key, value in run.validation_metrics.items()},
        }
        for source_key, output_key in (
            ("node_count", "node_count"),
            ("max_depth", "depth"),
            ("leaf_count", "leaf_count"),
            ("tree_count", "tree_count"),
        ):
            value = run.model_spec.get(source_key)
            if isinstance(value, (int, float)):
                row[output_key] = float(value)
        if calibration is not None:
            row["calibration_method"] = calibration.method
            row["calibrated_brier"] = float(calibration.brier_after)
            row["calibrated_ece"] = float(calibration.ece_after)
        if threshold is not None:
            row["decision_threshold"] = float(threshold.selected_threshold)
            row["threshold_objective"] = threshold.objective
            row["threshold_probability_source"] = threshold.probability_source
        row_identity = validation_sample_identities.get(str(run.run_id))
        if row_identity is not None:
            row["validation_sample_identity"] = row_identity
        rows.append(row)

    fis_id: UUID | None = None
    fis_semantic_hash: str | None = None
    if include_active_fis:
        if validation_alignment != "same_cases":
            raise TrainingError(
                "Manual FIS comparison requires selected trained runs to share the same persisted validation cases. "
                "Choose compatible runs from one declared split/seed before adding the FIS."
            )
        reference_identity = validation_sample_identities[str(runs[0].run_id)]
        fis_row, fis_id, fis_semantic_hash = _manual_fis_comparison_row(
            project_root, runs[0], reference_identity
        )
        rows.append(fis_row)
        validation_sample_identities[f"fis:{fis_id}"] = reference_identity
        alignment_note = (
            "All selected trained runs and the active manual FIS were evaluated on the same persisted validation cases."
        )

    comparison = AnalysisComparison(
        task=runs[0].task,
        target=runs[0].target,
        run_ids=[run.run_id for run in runs],
        dataset_fingerprint=next(iter(dataset_fingerprints), None),
        validation_alignment=validation_alignment,
        validation_sample_identities=validation_sample_identities,
        fis_id=fis_id,
        fis_semantic_hash=fis_semantic_hash,
        metric_rows=rows,
        scientific_note=(
            f"Comparison is validation-only. {alignment_note} "
            "Locked final test data are not included. Manual FIS outputs are not labeled calibrated probabilities unless such semantics are explicitly established."
        ),
    )
    _atomic_write_text(_comparisons_root(project_root) / f"{comparison.comparison_id}.json", comparison.model_dump_json(indent=2))
    _atomic_write_text(_comparisons_root(project_root) / "active-comparison.json", json.dumps({"comparison_id": str(comparison.comparison_id)}, indent=2))
    return comparison


def load_validation_comparison(project_root: Path, comparison_id: UUID) -> AnalysisComparison:
    return AnalysisComparison.model_validate_json((_comparisons_root(project_root) / f"{comparison_id}.json").read_text(encoding="utf-8"))


def load_latest_validation_comparison(project_root: Path) -> AnalysisComparison:
    pointer = json.loads((_comparisons_root(project_root) / "active-comparison.json").read_text(encoding="utf-8"))
    return load_validation_comparison(project_root, UUID(pointer["comparison_id"]))
