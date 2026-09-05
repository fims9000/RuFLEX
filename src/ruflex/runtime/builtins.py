"""Descriptors for built-in adapters.

Compute implementations are introduced behind the same descriptors during the
training migration; keeping the declarations here makes the catalog and API
derive from one trusted source.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from ruflex.application.model_catalog import get_model_capability_contract
from ruflex.runtime.contracts import FitRequest, FitResult, ModelAdapterDescriptor, PredictionRequest, PredictionResult, RuntimeIdentity
from ruflex.runtime.errors import RuntimeExecutionError


@dataclass(frozen=True)
class _BuiltinAdapter:
    descriptor: ModelAdapterDescriptor

    def fit(self, request: FitRequest) -> FitResult:
        """Compute only: no project paths, artifact stores, or policy state."""
        key = self.descriptor.identity.key
        if key == "ruflex_flat_neuro_fuzzy":
            # The Flat-NF bridge remains in the legacy artifact codec while its
            # torch trainer is extracted; it is deliberately unavailable to
            # the generic service rather than receiving a different science.
            raise RuntimeExecutionError(key)
        X_train = np.asarray(request.X_train, dtype=float)
        y_train = np.asarray(request.y_train, dtype=float).reshape(-1)
        X_validation = np.asarray(request.X_validation, dtype=float)
        task = request.task
        parameters = request.validated_parameters
        seed = request.training_seed
        if key == "sklearn_linear":
            if task == "binary_classification":
                estimator = LogisticRegression(random_state=seed, max_iter=1000).fit(X_train, y_train.astype(int))
                raw = np.asarray(estimator.decision_function(X_validation), dtype=float).reshape(-1)
            else:
                estimator = LinearRegression().fit(X_train, y_train)
                raw = np.asarray(estimator.predict(X_validation), dtype=float).reshape(-1)
            payload = {"format": "ruflex.declarative-linear-baseline/v1", "model_kind": "logistic_regression" if task == "binary_classification" else "linear_regression", "task": task, "feature_columns": list(request.feature_names), "coefficients": np.asarray(estimator.coef_).reshape(-1).astype(float).tolist(), "intercept": float(np.asarray(estimator.intercept_).reshape(-1)[0]), "split_seed": request.split_seed, "training_seed": seed}
            return FitResult(serialized_artifact=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(), artifact_media_type="application/vnd.ruflex.declarative-linear-model+json", model_spec={"coefficients": payload["coefficients"], "intercept": payload["intercept"]}, training_summary={"source": "linear", "epochs_ran": 1}, validation_raw_predictions=raw.tolist(), validation_raw_probabilities=(1 / (1 + np.exp(-np.clip(raw, -60, 60)))).tolist() if task == "binary_classification" else None)
        if key == "sklearn_decision_tree":
            estimator = DecisionTreeClassifier(random_state=seed, max_depth=parameters.get("max_depth")).fit(X_train, y_train.astype(int)) if task == "binary_classification" else DecisionTreeRegressor(random_state=seed, max_depth=parameters.get("max_depth")).fit(X_train, y_train)
            raw = np.log(np.clip(estimator.predict_proba(X_validation)[:, 1], 1e-12, 1 - 1e-12) / np.clip(1 - estimator.predict_proba(X_validation)[:, 1], 1e-12, 1)) if task == "binary_classification" else estimator.predict(X_validation)
            payload = _tree_artifact(estimator, request=request, model_kind="decision_tree")
            return FitResult(serialized_artifact=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(), artifact_media_type="application/vnd.ruflex.declarative-decision-tree+json", model_spec={"node_count": payload["tree"]["node_count"], "max_depth": payload["tree"]["max_depth"]}, training_summary={"source": "decision_tree", "epochs_ran": 1}, validation_raw_predictions=np.asarray(raw, dtype=float).reshape(-1).tolist())
        if key in {"sklearn_random_forest", "sklearn_gradient_boosting"}:
            count = int(parameters.get("n_estimators") or (25 if key == "sklearn_random_forest" else 50))
            depth = parameters.get("max_depth")
            if key == "sklearn_random_forest":
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
            return FitResult(serialized_artifact=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(), artifact_media_type=media, model_spec={"tree_count": len(trees)}, training_summary={"source": key.removeprefix("sklearn_"), "epochs_ran": count}, validation_raw_predictions=np.asarray(raw, dtype=float).reshape(-1).tolist(), validation_raw_probabilities=None if task != "binary_classification" else (1 / (1 + np.exp(-np.clip(raw, -60, 60)))).tolist())
        raise RuntimeExecutionError(key)

    def predict(self, request: PredictionRequest) -> PredictionResult:
        if self.descriptor.identity.key == "ruflex_flat_neuro_fuzzy":
            raise RuntimeExecutionError(self.descriptor.identity.key)
        payload = json.loads(request.artifact.decode("utf-8"))
        values = np.asarray(request.features, dtype=float)
        if values.ndim == 1:
            values = values.reshape(1, -1)
        kind = self.descriptor.identity.key
        if kind == "sklearn_linear":
            raw = values @ np.asarray(payload["coefficients"], dtype=float) + float(payload["intercept"])
        elif kind == "sklearn_decision_tree":
            raw = np.asarray([_tree_prediction(payload["tree"], row, task=request.task) for row in values])
            if request.task == "binary_classification":
                probability = raw
                return PredictionResult(prediction=(probability >= .5).astype(float).tolist(), probability=probability.tolist(), score=probability.tolist())
        elif kind == "sklearn_random_forest":
            raw = np.asarray([np.mean([_tree_prediction(tree, row, task=request.task) for tree in payload["trees"]]) for row in values])
            if request.task == "binary_classification":
                return PredictionResult(prediction=(raw >= .5).astype(float).tolist(), probability=raw.tolist(), score=raw.tolist())
        elif kind == "sklearn_gradient_boosting":
            raw = np.asarray([float(payload["initial_raw_prediction"]) + float(payload["parameters"]["learning_rate"]) * sum(_tree_prediction(tree, row, task="regression") for tree in payload["trees"]) for row in values])
        else:
            raise RuntimeExecutionError(kind)
        if request.task == "binary_classification":
            probability = 1.0 / (1.0 + np.exp(-np.clip(raw, -60, 60)))
            return PredictionResult(prediction=(probability >= .5).astype(float).tolist(), probability=probability.tolist(), score=probability.tolist(), raw_score=np.asarray(raw).tolist())
        return PredictionResult(prediction=np.asarray(raw, dtype=float).tolist(), score=np.asarray(raw, dtype=float).tolist())

    def fit_compatibility_project(self, project_root: Path, *, model_kind: str, config: dict[str, Any]) -> Any:
        """Temporary bridge for v1.1 artifact codecs during the core migration.

        This method is intentionally private-to-core: it neither exposes a
        plugin API nor lets an adapter persist arbitrary project objects.  The
        canonical runtime ``fit(FitRequest)`` remains the durable public
        contract; this bridge lets existing trustworthy declarative artifact
        codecs retain their exact scientific semantics while they move behind
        it one adapter at a time.
        """
        from ruflex.application import training

        runners = {
            "ruflex_flat_neuro_fuzzy": lambda: training.train_flat_neuro_fuzzy(project_root, **{key: value for key, value in config.items() if key not in {"n_estimators", "max_depth"}}),
            "sklearn_linear": lambda: training.train_linear_baseline(project_root, kind=model_kind, seed=config.get("seed"), split_seed=config.get("split_seed"), training_seed=config.get("training_seed"), validation_fraction=config["validation_fraction"], test_fraction=config["test_fraction"]),
            "sklearn_decision_tree": lambda: training.train_decision_tree(project_root, seed=config.get("seed"), split_seed=config.get("split_seed"), training_seed=config.get("training_seed"), validation_fraction=config["validation_fraction"], test_fraction=config["test_fraction"], max_depth=config.get("max_depth")),
            "sklearn_random_forest": lambda: training.train_random_forest(project_root, seed=config.get("seed"), split_seed=config.get("split_seed"), training_seed=config.get("training_seed"), validation_fraction=config["validation_fraction"], test_fraction=config["test_fraction"], n_estimators=config.get("n_estimators") or 25, max_depth=config.get("max_depth")),
            "sklearn_gradient_boosting": lambda: training.train_gradient_boosting(project_root, seed=config.get("seed"), split_seed=config.get("split_seed"), training_seed=config.get("training_seed"), validation_fraction=config["validation_fraction"], test_fraction=config["test_fraction"], n_estimators=config.get("n_estimators") or 50, learning_rate=config["learning_rate"], max_depth=config.get("max_depth") or 3),
        }
        try:
            return runners[self.descriptor.identity.key]()
        except KeyError as error:
            raise RuntimeExecutionError(self.descriptor.identity.key) from error


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
    catalog_key = "linear" if key == "linear" else key
    contract = get_model_capability_contract(catalog_key)
    assert contract is not None
    return ModelAdapterDescriptor(
        identity=RuntimeIdentity(key=f"sklearn_{key}" if key != "flat_neuro_fuzzy" else "ruflex_flat_neuro_fuzzy", version="1", provider="ruflex.builtin", kind="model_adapter"),
        family=contract.family,
        training_model_kinds=kinds,
        supported_tasks=contract.supported_tasks,
        capabilities=contract.capabilities.__dict__,
        supported_explainers=contract.supported_explainers,
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
        _BuiltinAdapter(_descriptor("flat_neuro_fuzzy", kinds=("flat_neuro_fuzzy",))),
        _BuiltinAdapter(_descriptor("linear", kinds=("logistic_regression", "linear_regression"))),
        _BuiltinAdapter(_descriptor("decision_tree", kinds=("decision_tree",))),
        _BuiltinAdapter(_descriptor("random_forest", kinds=("random_forest",))),
        _BuiltinAdapter(_descriptor("gradient_boosting", kinds=("gradient_boosting",))),
    )
