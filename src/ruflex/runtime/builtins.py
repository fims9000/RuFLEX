"""Descriptors for built-in adapters.

Compute implementations are introduced behind the same descriptors during the
training migration; keeping the declarations here makes the catalog and API
derive from one trusted source.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruflex.application.model_catalog import get_model_capability_contract
from ruflex.runtime.contracts import FitRequest, FitResult, ModelAdapterDescriptor, PredictionRequest, PredictionResult, RuntimeIdentity
from ruflex.runtime.errors import RuntimeExecutionError


@dataclass(frozen=True)
class _BuiltinAdapter:
    descriptor: ModelAdapterDescriptor

    def fit(self, request: FitRequest) -> FitResult:
        raise RuntimeExecutionError(self.descriptor.identity.key)

    def predict(self, request: PredictionRequest) -> PredictionResult:
        raise RuntimeExecutionError(self.descriptor.identity.key)

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
