"""Descriptors for built-in adapters.

Compute implementations are introduced behind the same descriptors during the
training migration; keeping the declarations here makes the catalog and API
derive from one trusted source.
"""
from __future__ import annotations

from dataclasses import dataclass

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
