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
