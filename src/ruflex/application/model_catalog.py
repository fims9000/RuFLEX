"""Capability-declared model catalog used by the object-centric Studio."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class ModelCapabilities:
    """Typed capability contract shared by catalog, explainers and validators."""

    fit: bool = False
    predict: bool = False
    predict_proba: bool = False
    gradient_access: bool = False
    differentiable: bool = False
    tree_structure: bool = False
    structural_trace: bool = False
    exact_tree_path: bool = False
    exact_semantic_trace: bool = False
    exact_enumeration: bool = False
    rule_access: bool = False
    editable_components: bool = False
    calibration: bool = False
    export: bool = False
    export_fis: bool = False
    occlusion: bool = False
    shap: bool = False
    tree_shap: bool = False
    integrated_gradients: bool = False
    gradient_shap: bool = False


@dataclass(frozen=True)
class ModelCatalogEntry:
    key: str
    label: str
    family: str
    available: bool
    capabilities: ModelCapabilities
    limitation: str | None = None


@dataclass(frozen=True)
class ModelCapabilityContract:
    """The trusted runtime contract used by new API and Studio clients."""

    key: str
    display_name: str
    version: str
    provider: str
    family: str
    supported_tasks: tuple[str, ...]
    training_model_kinds: tuple[str, ...]
    model_kind_tasks: dict[str, tuple[str, ...]]
    input_modalities: tuple[str, ...]
    available: bool
    unavailability_reason: str | None
    capabilities: ModelCapabilities
    supported_explainers: tuple[str, ...]
    export_formats: tuple[str, ...]
    config_schema: dict
    defaults: dict
    parameter_constraints: dict
    optional_dependencies: tuple[str, ...]
    evidence_objects_produced: tuple[str, ...]
    limitations: tuple[str, ...]
    adapter_key: str | None = None
    adapter_version: str | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        for key in ("supported_tasks", "input_modalities", "supported_explainers", "export_formats", "optional_dependencies", "evidence_objects_produced", "limitations"):
            payload[key] = list(payload[key])
        payload["model_kind_tasks"] = {kind: list(tasks) for kind, tasks in self.model_kind_tasks.items()}
        return payload


def _capabilities(**values: bool) -> ModelCapabilities:
    """Reject misspelled capability keys while leaving false values explicit."""

    return ModelCapabilities(**values)


_ENTRIES = (
    ModelCatalogEntry("mamdani", "Type-1 Mamdani FIS", "Fuzzy", True, _capabilities(predict=True, exact_semantic_trace=True, exact_enumeration=True, rule_access=True, editable_components=True, export_fis=True), None),
    ModelCatalogEntry("sugeno", "Type-1 Sugeno FIS", "Fuzzy", True, _capabilities(predict=True, exact_semantic_trace=True, exact_enumeration=True, rule_access=True, editable_components=True), "MATLAB export is currently blocked for Sugeno to avoid semantic substitution."),
    ModelCatalogEntry("flat_neuro_fuzzy", "ANFIS / Flat neuro-fuzzy", "Fuzzy", True, _capabilities(fit=True, predict=True, predict_proba=True, gradient_access=True, differentiable=True, calibration=True, occlusion=True, shap=True, integrated_gradients=True, gradient_shap=True), "Trace availability depends on retained explicit fuzzy semantics."),
    ModelCatalogEntry("decision_tree", "Decision Tree", "Classical baseline", True, _capabilities(fit=True, predict=True, predict_proba=True, tree_structure=True, structural_trace=True, exact_tree_path=True, exact_enumeration=True, rule_access=True, tree_shap=True, occlusion=True, shap=True), "Exact execution path and model-specific TreeSHAP are separate evidence objects; TreeSHAP remains post-hoc attribution."),
    ModelCatalogEntry("random_forest", "Random Forest", "Classical baseline", True, _capabilities(fit=True, predict=True, predict_proba=True, tree_structure=True, structural_trace=True, tree_shap=True, occlusion=True, shap=True), "TreeSHAP attributes the full persisted forest aggregation; RuFLEX never presents one constituent path as an exact ensemble explanation."),
    ModelCatalogEntry("gradient_boosting", "Gradient Boosting", "Classical baseline", True, _capabilities(fit=True, predict=True, predict_proba=True, tree_structure=True, structural_trace=True, tree_shap=True, occlusion=True, shap=True), "TreeSHAP explains the additive raw score for binary boosting; no constituent path is mislabeled as exact ensemble explanation."),
    ModelCatalogEntry("linear", "Logistic / Linear Regression", "Classical baseline", True, _capabilities(fit=True, predict=True, predict_proba=True, export=True, occlusion=True, shap=True), "Trains a safe declarative coefficient artifact; binary data use logistic regression and regression data use linear regression."),
)


# These declarations mirror the arguments accepted by the canonical training
# adapters.  They are deliberately data, rather than frontend knowledge: a
# client can render a conservative form without claiming a parameter is used
# by an adapter that ignores it.
_TRAINING_RUNTIME: dict[str, dict] = {
    "flat_neuro_fuzzy": {
        "supported_tasks": ("binary_classification", "regression"),
        "defaults": {"seed": 42, "max_epochs": 20, "learning_rate": 0.01, "batch_size": 32, "patience": 8, "max_rules": 8},
        "constraints": {"max_epochs": {"minimum": 1, "maximum": 2000}, "learning_rate": {"exclusiveMinimum": 0.0, "maximum": 1.0}, "batch_size": {"minimum": 1, "maximum": 100000}, "patience": {"minimum": 1, "maximum": 2000, "nullable": True}, "max_rules": {"minimum": 1, "maximum": 128}},
    },
    "linear": {
        "supported_tasks": ("binary_classification", "regression"),
        "defaults": {"seed": 42},
        "constraints": {},
    },
    "decision_tree": {
        "supported_tasks": ("binary_classification", "regression"),
        "defaults": {"seed": 42, "max_depth": None},
        "constraints": {"max_depth": {"minimum": 1, "nullable": True}},
    },
    "random_forest": {
        "supported_tasks": ("binary_classification", "regression"),
        "defaults": {"seed": 42, "n_estimators": 25, "max_depth": None},
        "constraints": {"n_estimators": {"minimum": 1}, "max_depth": {"minimum": 1, "nullable": True}},
    },
    "gradient_boosting": {
        "supported_tasks": ("binary_classification", "regression"),
        "defaults": {"seed": 42, "n_estimators": 50, "learning_rate": 0.1, "max_depth": 3},
        "constraints": {"n_estimators": {"minimum": 1}, "learning_rate": {"exclusiveMinimum": 0.0}, "max_depth": {"minimum": 1}},
    },
}

_SPLIT_DEFAULTS = {"validation_fraction": 0.2, "test_fraction": 0.2}
_SPLIT_CONSTRAINTS = {
    "validation_fraction": {"exclusiveMinimum": 0.0, "exclusiveMaximum": 1.0},
    "test_fraction": {"minimum": 0.0, "exclusiveMaximum": 1.0},
}


def list_model_catalog() -> list[dict]:
    """Return stable descriptive catalog rows with runtime-owned capabilities."""
    rows = [asdict(entry) for entry in _ENTRIES]
    # FIS descriptions remain catalog-owned. Executable TrainingRun model
    # capabilities are resolved from the exact registered adapter descriptor.
    from ruflex.runtime.registry import builtin_runtime_registry

    registry = builtin_runtime_registry()
    for row in rows:
        if not row["capabilities"].get("fit", False):
            continue
        model_kind = "logistic_regression" if row["key"] == "linear" else row["key"]
        try:
            adapter = registry.resolve_training_model_kind(model_kind)
        except Exception:
            row["available"] = False
            row["capabilities"] = {key: False for key in row["capabilities"]}
            row["limitation"] = "No registered runtime adapter declares this TrainingRun model kind."
            continue
        row["capabilities"] = {key: bool(value) for key, value in adapter.descriptor.capabilities.items()}
        row["available"] = bool(adapter.descriptor.available)
        row["runtime"] = {
            "adapter_key": adapter.descriptor.identity.key,
            "adapter_version": adapter.descriptor.identity.version,
        }
    return rows


def _declared_model_capability_contracts() -> list[ModelCapabilityContract]:
    """Return descriptive defaults used while native adapter descriptors build."""
    contracts: list[ModelCapabilityContract] = []
    for entry in _ENTRIES:
        explainers = tuple(name for name, enabled in (
            ("occlusion", entry.capabilities.occlusion), ("shap", entry.capabilities.shap),
            ("tree_shap", entry.capabilities.tree_shap),
            ("integrated_gradients", entry.capabilities.integrated_gradients),
            ("gradient_shap", entry.capabilities.gradient_shap),
        ) if enabled)
        trainable = entry.capabilities.fit
        runtime = _TRAINING_RUNTIME.get(entry.key, {})
        defaults = {**_SPLIT_DEFAULTS, **runtime.get("defaults", {})} if trainable else {}
        constraints = {**_SPLIT_CONSTRAINTS, **runtime.get("constraints", {})} if trainable else {}
        contracts.append(ModelCapabilityContract(
            key=entry.key, display_name=entry.label, version="1.1.0", provider="ruflex.builtin",
            family=entry.family,
            supported_tasks=runtime.get("supported_tasks", ()) if trainable else (),
            training_model_kinds=("logistic_regression", "linear_regression") if entry.key == "linear" else ((entry.key,) if trainable else ()),
            model_kind_tasks={"logistic_regression": ("binary_classification",), "linear_regression": ("regression",)} if entry.key == "linear" else {},
            input_modalities=("tabular",), available=entry.available,
            unavailability_reason=None if entry.available else "OPTIONAL_DEPENDENCY_MISSING",
            capabilities=entry.capabilities, supported_explainers=explainers,
            export_formats=("matlab_fis",) if entry.capabilities.export_fis else (),
            config_schema={"type": "object", "additionalProperties": False, "properties": constraints}, defaults=defaults,
            parameter_constraints=constraints, optional_dependencies=("torch",) if entry.key == "flat_neuro_fuzzy" else (),
            evidence_objects_produced=("TrainingRun", "ModelArtifact") if trainable else ("FISSpec", "FISEvaluation"),
            limitations=tuple(item for item in (entry.limitation,) if item),
        ))
    return contracts


def model_capability_contracts() -> list[ModelCapabilityContract]:
    """Project executable capabilities from adapters into stable catalog rows."""
    contracts = _declared_model_capability_contracts()
    from ruflex.runtime.registry import builtin_runtime_registry

    registry = builtin_runtime_registry()
    descriptors = registry.model_descriptors()
    for descriptor in descriptors:
        matching = None
        if descriptor.identity.provider == "ruflex.builtin":
            matching = next(
                (item for item in contracts if set(item.training_model_kinds) & set(descriptor.training_model_kinds)),
                None,
            )
        if matching is None:
            contracts.append(ModelCapabilityContract(
                key=descriptor.identity.key,
                display_name=descriptor.identity.key.replace("_", " ").title(),
                version=descriptor.identity.version,
                provider=descriptor.identity.provider,
                family=descriptor.family,
                adapter_key=descriptor.identity.key,
                adapter_version=descriptor.identity.version,
                supported_tasks=descriptor.supported_tasks,
                training_model_kinds=descriptor.training_model_kinds,
                model_kind_tasks=descriptor.model_kind_tasks,
                input_modalities=descriptor.input_modalities,
                available=descriptor.available,
                unavailability_reason=descriptor.unavailability_reason,
                capabilities=ModelCapabilities(**descriptor.capabilities),
                supported_explainers=descriptor.supported_explainers,
                export_formats=(),
                config_schema=descriptor.config_schema,
                defaults=descriptor.defaults,
                parameter_constraints=descriptor.parameter_constraints,
                optional_dependencies=descriptor.optional_dependencies,
                evidence_objects_produced=descriptor.evidence_objects_produced,
                limitations=descriptor.limitations,
            ))
            continue
        index = contracts.index(matching)
        contracts[index] = replace(
            matching,
            version=descriptor.identity.version,
            provider=descriptor.identity.provider,
            adapter_key=descriptor.identity.key,
            adapter_version=descriptor.identity.version,
            supported_tasks=descriptor.supported_tasks,
            training_model_kinds=descriptor.training_model_kinds,
            model_kind_tasks=descriptor.model_kind_tasks,
            available=descriptor.available,
            unavailability_reason=descriptor.unavailability_reason,
            capabilities=ModelCapabilities(**descriptor.capabilities),
            supported_explainers=descriptor.supported_explainers,
            config_schema=descriptor.config_schema,
            defaults=descriptor.defaults,
            parameter_constraints=descriptor.parameter_constraints,
            optional_dependencies=descriptor.optional_dependencies,
            evidence_objects_produced=descriptor.evidence_objects_produced,
            limitations=descriptor.limitations,
        )
    return contracts


def get_model_capability_contract(model_kind: str) -> ModelCapabilityContract | None:
    key = "linear" if model_kind in {"logistic_regression", "linear_regression"} else model_kind
    return next((item for item in _declared_model_capability_contracts() if item.key == key), None)
