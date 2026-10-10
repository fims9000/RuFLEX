"""Descriptors for built-in adapters.

Compute implementations are introduced behind the same descriptors during the
training migration; keeping the declarations here makes the catalog and API
derive from one trusted source.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from ruflex.core.enums import TaskType
from ruflex.models.flat_nf.model import FlatNeuroFuzzyModel
from ruflex.models.specs import ShallowModelSpec
from ruflex.training.config import FineTuningOptions, ModelTrainingConfig, RefinementOptions, StagewiseOptions

from ruflex.application.model_catalog import ModelCapabilities, get_model_capability_contract
from ruflex.runtime.contracts import FitRequest, FitResult, ModelAdapterDescriptor, PredictionRequest, PredictionResult, RuntimeIdentity
from ruflex.runtime.errors import RuntimeExecutionError, RuntimeIncompatibleError


_NATIVE_CAPABILITIES: dict[str, dict[str, bool]] = {
    "native_flat_neuro_fuzzy": asdict(ModelCapabilities(
        fit=True, predict=True, predict_proba=True, gradient_access=True, differentiable=True,
        calibration=True, occlusion=True, shap=True, integrated_gradients=True, gradient_shap=True,
    )),
    "native_linear": asdict(ModelCapabilities(
        fit=True, predict=True, predict_proba=True, export=True, occlusion=True, shap=True,
    )),
    "native_decision_tree": asdict(ModelCapabilities(
        fit=True, predict=True, predict_proba=True, tree_structure=True, structural_trace=True,
        exact_tree_path=True, exact_enumeration=True, rule_access=True, tree_shap=True,
        occlusion=True, shap=True,
    )),
    "native_random_forest": asdict(ModelCapabilities(
        fit=True, predict=True, predict_proba=True, tree_structure=True, structural_trace=True,
        tree_shap=True, occlusion=True, shap=True,
    )),
    "native_gradient_boosting": asdict(ModelCapabilities(
        fit=True, predict=True, predict_proba=True, tree_structure=True, structural_trace=True,
        tree_shap=True, occlusion=True, shap=True,
    )),
}


@dataclass(frozen=True)
class _BuiltinAdapter:
    descriptor: ModelAdapterDescriptor

    def fit(self, request: FitRequest) -> FitResult:
        """Compute only: no project paths, artifact stores, or policy state."""
        key = self.descriptor.identity.key
        X_train = np.asarray(request.X_train, dtype=float)
        y_train = np.asarray(request.y_train, dtype=float).reshape(-1)
        X_validation = np.asarray(request.X_validation, dtype=float)
        task = request.task
        parameters = request.validated_parameters
        seed = request.training_seed
        if key == "native_flat_neuro_fuzzy":
            from ruflex.application.training import _build_flat_spec, _seed_everything

            _seed_everything(seed)
            max_rules = int(parameters.get("max_rules", 8))
            spec = _build_flat_spec(pd.DataFrame(X_train, columns=request.feature_names), list(request.feature_names), max_rules=max_rules)
            model = FlatNeuroFuzzyModel(spec)
            config = ModelTrainingConfig(
                task_type=TaskType(request.task), use_bootstrap_initialization=True, use_stagewise_pretraining=False,
                stagewise=StagewiseOptions(epochs_per_stage=1, decision_epochs=1, refinement_rounds=1),
                fine_tuning=FineTuningOptions(max_epochs=int(parameters.get("max_epochs", 20)), learning_rate=float(parameters.get("learning_rate", .01)), batch_size=int(parameters.get("batch_size", 32)), patience=parameters.get("patience", 8), shuffle=True, classification_threshold=.5),
                refinement=RefinementOptions(cycles=1),
            )
            # The domain trainer expects a split-shaped object; the adapter
            # constructs only train/validation partitions and no test data.
            from types import SimpleNamespace
            adapter_split = SimpleNamespace(train_features=X_train, train_targets=y_train, validation_features=X_validation, validation_targets=np.asarray(request.y_validation, dtype=float))
            summary = model.fit(adapter_split, config)
            raw = np.asarray(model.predict(X_validation), dtype=float).reshape(-1)
            with tempfile.NamedTemporaryFile(prefix="ruflex-runtime-flat-", suffix=".pt", delete=False) as handle:
                temporary = Path(handle.name)
            try:
                model.save_bundle(temporary, metadata={"producer": "ruflex.runtime", "model_kind": "flat_neuro_fuzzy", "task": request.task, "feature_columns": list(request.feature_names), "training_seed": seed, "split_seed": request.split_seed})
                artifact_bytes = temporary.read_bytes()
            finally:
                temporary.unlink(missing_ok=True)
            history = [{"epoch": point.epoch, "train_loss": point.train_loss, "validation_loss": point.validation_loss, "train_metrics": point.train_metrics, "validation_metrics": point.validation_metrics} for point in summary.history]
            return FitResult(model_payload=None, serialized_artifact=artifact_bytes, artifact_media_type="application/x-pytorch-model", model_spec=spec.to_dict(), training_summary=summary.to_dict(), trajectory=history, validation_raw_predictions=raw.tolist(), validation_raw_probabilities=(1 / (1 + np.exp(-np.clip(raw, -60, 60)))).tolist() if request.task == "binary_classification" else None)
        if key == "native_linear":
            expected_kind = "logistic_regression" if task == "binary_classification" else "linear_regression"
            if request.model_kind is not None and request.model_kind != expected_kind:
                raise RuntimeIncompatibleError(f"Model kind {request.model_kind!r} is incompatible with dataset task {task!r}; use {expected_kind!r}.")
            if task == "binary_classification":
                estimator = LogisticRegression(random_state=seed, max_iter=1000).fit(X_train, y_train.astype(int))
                raw = np.asarray(estimator.decision_function(X_validation), dtype=float).reshape(-1)
            else:
                estimator = LinearRegression().fit(X_train, y_train)
                raw = np.asarray(estimator.predict(X_validation), dtype=float).reshape(-1)
            payload = {"format": "ruflex.declarative-linear-baseline/v1", "model_kind": "logistic_regression" if task == "binary_classification" else "linear_regression", "task": task, "feature_columns": list(request.feature_names), "coefficients": np.asarray(estimator.coef_).reshape(-1).astype(float).tolist(), "intercept": float(np.asarray(estimator.intercept_).reshape(-1)[0]), "split_seed": request.split_seed, "training_seed": seed}
            return FitResult(serialized_artifact=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(), artifact_media_type="application/vnd.ruflex.declarative-linear-model+json", model_spec={"coefficients": payload["coefficients"], "intercept": payload["intercept"]}, training_summary={"source": "linear", "fit_calls": 1}, validation_raw_predictions=raw.tolist(), validation_raw_probabilities=(1 / (1 + np.exp(-np.clip(raw, -60, 60)))).tolist() if task == "binary_classification" else None)
        if key == "native_decision_tree":
            estimator = DecisionTreeClassifier(random_state=seed, max_depth=parameters.get("max_depth")).fit(X_train, y_train.astype(int)) if task == "binary_classification" else DecisionTreeRegressor(random_state=seed, max_depth=parameters.get("max_depth")).fit(X_train, y_train)
            raw = np.log(np.clip(estimator.predict_proba(X_validation)[:, 1], 1e-12, 1 - 1e-12) / np.clip(1 - estimator.predict_proba(X_validation)[:, 1], 1e-12, 1)) if task == "binary_classification" else estimator.predict(X_validation)
            payload = _tree_artifact(estimator, request=request, model_kind="decision_tree")
            tree_spec = payload["tree"]
            return FitResult(serialized_artifact=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(), artifact_media_type="application/vnd.ruflex.declarative-decision-tree+json", model_spec={"node_count": tree_spec["node_count"], "max_depth": tree_spec["max_depth"], "leaf_count": sum(1 for node in tree_spec["children_left"] if node == -1)}, training_summary={"source": "decision_tree", "fit_calls": 1}, validation_raw_predictions=np.asarray(raw, dtype=float).reshape(-1).tolist())
        if key in {"native_random_forest", "native_gradient_boosting"}:
            count = int(parameters.get("n_estimators") or (25 if key == "native_random_forest" else 50))
            depth = parameters.get("max_depth")
            if key == "native_random_forest":
                estimator = RandomForestClassifier(n_estimators=count, random_state=seed, max_depth=depth).fit(X_train, y_train.astype(int)) if task == "binary_classification" else RandomForestRegressor(n_estimators=count, random_state=seed, max_depth=depth).fit(X_train, y_train)
                probabilities = estimator.predict_proba(X_validation)[:, 1] if task == "binary_classification" else None
                raw = np.log(np.clip(probabilities, 1e-12, 1 - 1e-12) / np.clip(1 - probabilities, 1e-12, 1)) if probabilities is not None else estimator.predict(X_validation)
                trees = [_tree_artifact(tree, request=request, model_kind="decision_tree")["tree"] for tree in estimator.estimators_]
                payload = {"format": "ruflex.declarative-random-forest/v1", "model_kind": "random_forest", "task": task, "feature_columns": list(request.feature_names), "parameters": {"n_estimators": count, "max_depth": depth, "random_state": seed}, "split_seed": request.split_seed, "training_seed": seed, "trees": trees}
                media = "application/vnd.ruflex.declarative-random-forest+json"
            else:
                rate = float(parameters.get("learning_rate", .1))
                depth = int(depth or 3)
                estimator = GradientBoostingClassifier(n_estimators=count, learning_rate=rate, max_depth=depth, random_state=seed).fit(X_train, y_train.astype(int)) if task == "binary_classification" else GradientBoostingRegressor(n_estimators=count, learning_rate=rate, max_depth=depth, random_state=seed).fit(X_train, y_train)
                raw = estimator.decision_function(X_validation) if task == "binary_classification" else estimator.predict(X_validation)
                trees = [_tree_artifact(tree, request=request, model_kind="decision_tree")["tree"] for tree in np.asarray(estimator.estimators_, dtype=object).reshape(-1)]
                initial = float(np.asarray(estimator._raw_predict_init(X_train[:1]), dtype=float).reshape(-1)[0])
                payload = {"format": "ruflex.declarative-gradient-boosting/v1", "model_kind": "gradient_boosting", "task": task, "feature_columns": list(request.feature_names), "parameters": {"n_estimators": count, "learning_rate": rate, "max_depth": depth, "random_state": seed}, "split_seed": request.split_seed, "training_seed": seed, "initial_raw_prediction": initial, "trees": trees}
                media = "application/vnd.ruflex.declarative-gradient-boosting+json"
            model_spec = {"tree_count": len(trees), "node_count": sum(tree["node_count"] for tree in trees), "max_depth": max(tree["max_depth"] for tree in trees), "leaf_count": sum(sum(1 for node in tree["children_left"] if node == -1) for tree in trees)}
            return FitResult(serialized_artifact=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(), artifact_media_type=media, model_spec=model_spec, training_summary={"source": key.removeprefix("sklearn_"), "fit_calls": 1, "estimator_count": count}, validation_raw_predictions=np.asarray(raw, dtype=float).reshape(-1).tolist(), validation_raw_probabilities=None if task != "binary_classification" else (1 / (1 + np.exp(-np.clip(raw, -60, 60)))).tolist())
        raise RuntimeExecutionError(key)

    def predict(self, request: PredictionRequest) -> PredictionResult:
        if self.descriptor.identity.key == "native_flat_neuro_fuzzy":
            spec = ShallowModelSpec.from_dict(request.model_spec)
            model = FlatNeuroFuzzyModel(spec)
            with tempfile.NamedTemporaryFile(prefix="ruflex-runtime-load-", suffix=".pt", delete=False) as handle:
                handle.write(request.artifact)
                temporary = Path(handle.name)
            try:
                model.load_bundle(temporary)
            finally:
                temporary.unlink(missing_ok=True)
            raw = np.asarray(model.predict(np.asarray(request.features, dtype=float)), dtype=float).reshape(-1)
            if request.task == "binary_classification":
                probability = 1 / (1 + np.exp(-np.clip(raw, -60, 60)))
                return PredictionResult(prediction=(probability >= .5).astype(float).tolist(), probability=probability.tolist(), score=probability.tolist(), raw_score=raw.tolist())
            return PredictionResult(prediction=raw.tolist(), score=raw.tolist())
        payload = json.loads(request.artifact.decode("utf-8"))
        values = np.asarray(request.features, dtype=float)
        if values.ndim == 1:
            values = values.reshape(1, -1)
        kind = self.descriptor.identity.key
        if kind == "native_linear":
            raw = values @ np.asarray(payload["coefficients"], dtype=float) + float(payload["intercept"])
        elif kind == "native_decision_tree":
            raw = np.asarray([_tree_prediction(payload["tree"], row, task=request.task) for row in values])
            if request.task == "binary_classification":
                probability = raw
                clipped = np.clip(probability, 1e-12, 1.0 - 1e-12)
                raw_score = np.log(clipped / (1.0 - clipped))
                return PredictionResult(prediction=(probability >= .5).astype(float).tolist(), probability=probability.tolist(), score=probability.tolist(), raw_score=raw_score.tolist())
        elif kind == "native_random_forest":
            raw = np.asarray([np.mean([_tree_prediction(tree, row, task=request.task) for tree in payload["trees"]]) for row in values])
            if request.task == "binary_classification":
                clipped = np.clip(raw, 1e-12, 1.0 - 1e-12)
                raw_score = np.log(clipped / (1.0 - clipped))
                return PredictionResult(prediction=(raw >= .5).astype(float).tolist(), probability=raw.tolist(), score=raw.tolist(), raw_score=raw_score.tolist())
        elif kind == "native_gradient_boosting":
            raw = np.asarray([float(payload["initial_raw_prediction"]) + float(payload["parameters"]["learning_rate"]) * sum(_tree_prediction(tree, row, task="regression") for tree in payload["trees"]) for row in values])
        else:
            raise RuntimeExecutionError(kind)
        if request.task == "binary_classification":
            probability = 1.0 / (1.0 + np.exp(-np.clip(raw, -60, 60)))
            return PredictionResult(prediction=(probability >= .5).astype(float).tolist(), probability=probability.tolist(), score=probability.tolist(), raw_score=np.asarray(raw).tolist())
        return PredictionResult(prediction=np.asarray(raw, dtype=float).tolist(), score=np.asarray(raw, dtype=float).tolist())

def _tree_artifact(estimator: Any, *, request: FitRequest, model_kind: str) -> dict[str, Any]:
    """Serialize sklearn tree state as safe declarative JSON, not pickle."""
    tree = estimator.tree_
    return {
        "format": "ruflex.declarative-decision-tree/v1", "model_kind": model_kind,
        "task": request.task, "target": "", "feature_columns": list(request.feature_names),
        "classes": None if request.task == "regression" or not hasattr(estimator, "classes_") else [str(item) for item in estimator.classes_],
        "parameters": {key: value for key, value in estimator.get_params().items() if isinstance(value, (str, int, float, bool, type(None)))},
        "tree": {
            "node_count": int(tree.node_count), "max_depth": int(tree.max_depth),
            "children_left": [int(item) for item in tree.children_left], "children_right": [int(item) for item in tree.children_right],
            "feature_index": [int(item) for item in tree.feature], "threshold": [float(item) for item in tree.threshold],
            "impurity": [float(item) for item in tree.impurity], "samples": [int(item) for item in tree.n_node_samples],
            "values": np.asarray(tree.value, dtype=float).reshape(tree.node_count, -1).tolist(),
        },
        "split_seed": request.split_seed, "training_seed": request.training_seed,
    }


def _tree_prediction(tree: dict[str, Any], row: np.ndarray, *, task: str) -> float:
    node = 0
    while int(tree["children_left"][node]) != -1:
        feature = int(tree["feature_index"][node])
        node = int(tree["children_left"][node]) if float(row[feature]) <= float(tree["threshold"][node]) else int(tree["children_right"][node])
    values = np.asarray(tree["values"][node], dtype=float).reshape(-1)
    if task == "binary_classification":
        return .5 if values.sum() <= 0 else float(values[1] / values.sum())
    return float(values[0])


def _descriptor(key: str, *, kinds: tuple[str, ...]) -> ModelAdapterDescriptor:
    catalog_key = "linear" if key == "native_linear" else key.removeprefix("native_")
    if catalog_key == "flat_neuro_fuzzy":
        catalog_key = "flat_neuro_fuzzy"
    contract = get_model_capability_contract(catalog_key)
    assert contract is not None
    capabilities = _NATIVE_CAPABILITIES[key]
    supported_explainers = tuple(name for name, enabled in (
        ("occlusion", capabilities["occlusion"]),
        ("shap", capabilities["shap"]),
        ("tree_shap", capabilities["tree_shap"]),
        ("integrated_gradients", capabilities["integrated_gradients"]),
        ("gradient_shap", capabilities["gradient_shap"]),
    ) if enabled)
    return ModelAdapterDescriptor(
        identity=RuntimeIdentity(key=key, version="1", provider="ruflex.builtin", kind="model_adapter"),
        family=contract.family,
        training_model_kinds=kinds,
        supported_tasks=contract.supported_tasks,
        model_kind_tasks={
            "logistic_regression": ("binary_classification",),
            "linear_regression": ("regression",),
        } if key == "native_linear" else {},
        capabilities=capabilities,
        supported_explainers=supported_explainers,
        config_schema=contract.config_schema,
        defaults=contract.defaults,
        parameter_constraints=contract.parameter_constraints,
        optional_dependencies=contract.optional_dependencies,
        evidence_objects_produced=contract.evidence_objects_produced,
        limitations=contract.limitations,
        available=contract.available,
        unavailability_reason=contract.unavailability_reason,
    )


def builtin_model_adapters() -> tuple[_BuiltinAdapter, ...]:
    return (
        _BuiltinAdapter(_descriptor("native_flat_neuro_fuzzy", kinds=("flat_neuro_fuzzy",))),
        _BuiltinAdapter(_descriptor("native_linear", kinds=("logistic_regression", "linear_regression"))),
        _BuiltinAdapter(_descriptor("native_decision_tree", kinds=("decision_tree",))),
        _BuiltinAdapter(_descriptor("native_random_forest", kinds=("random_forest",))),
        _BuiltinAdapter(_descriptor("native_gradient_boosting", kinds=("gradient_boosting",))),
    )
