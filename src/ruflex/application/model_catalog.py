"""Capability-declared model catalog used by the object-centric Studio."""
from __future__ import annotations

from dataclasses import asdict, dataclass


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

    def to_dict(self) -> dict:
        payload = asdict(self)
        for key in ("supported_tasks", "input_modalities", "supported_explainers", "export_formats", "optional_dependencies", "evidence_objects_produced", "limitations"):
            payload[key] = list(payload[key])
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


def list_model_catalog() -> list[dict]:
    return [asdict(entry) for entry in _ENTRIES]


def model_capability_contracts() -> list[ModelCapabilityContract]:
    """Return deterministic built-in runtime declarations without name guessing."""
    contracts: list[ModelCapabilityContract] = []
    for entry in _ENTRIES:
        explainers = tuple(name for name, enabled in (
            ("occlusion", entry.capabilities.occlusion), ("shap", entry.capabilities.shap),
            ("tree_shap", entry.capabilities.tree_shap),
            ("integrated_gradients", entry.capabilities.integrated_gradients),
            ("gradient_shap", entry.capabilities.gradient_shap),
        ) if enabled)
        trainable = entry.capabilities.fit
        contracts.append(ModelCapabilityContract(
            key=entry.key, display_name=entry.label, version="1.1.0", provider="ruflex.builtin",
            family=entry.family,
            supported_tasks=("binary_classification", "multiclass_classification", "regression") if trainable else (),
            training_model_kinds=("logistic_regression", "linear_regression") if entry.key == "linear" else ((entry.key,) if trainable else ()),
            input_modalities=("tabular",), available=entry.available,
            unavailability_reason=None if entry.available else "OPTIONAL_DEPENDENCY_MISSING",
            capabilities=entry.capabilities, supported_explainers=explainers,
            export_formats=("matlab_fis",) if entry.capabilities.export_fis else (),
            config_schema={"type": "object", "additionalProperties": False}, defaults={"seed": 42},
            parameter_constraints={}, optional_dependencies=(),
            evidence_objects_produced=("TrainingRun", "ModelArtifact") if trainable else ("FISSpec", "FISEvaluation"),
            limitations=tuple(item for item in (entry.limitation,) if item),
        ))
    return contracts


def get_model_capability_contract(model_kind: str) -> ModelCapabilityContract | None:
    key = "linear" if model_kind in {"logistic_regression", "linear_regression"} else model_kind
    return next((item for item in model_capability_contracts() if item.key == key), None)
