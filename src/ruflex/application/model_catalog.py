"""Capability-declared model catalog used by the object-centric Studio."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModelCatalogEntry:
    key: str
    label: str
    family: str
    available: bool
    capabilities: dict[str, bool]
    limitation: str | None = None


_ENTRIES = (
    ModelCatalogEntry("mamdani", "Type-1 Mamdani FIS", "Fuzzy", True, {"fit": False, "predict": True, "exact_semantic_trace": True, "rule_access": True, "editable_components": True, "export_fis": True}, None),
    ModelCatalogEntry("sugeno", "Type-1 Sugeno FIS", "Fuzzy", True, {"fit": False, "predict": True, "exact_semantic_trace": True, "rule_access": True, "editable_components": True, "export_fis": False}, "MATLAB export is currently blocked for Sugeno to avoid semantic substitution."),
    ModelCatalogEntry("flat_neuro_fuzzy", "ANFIS / Flat neuro-fuzzy", "Fuzzy", True, {"fit": True, "predict": True, "exact_semantic_trace": False, "gradient_access": True, "calibration": True, "editable_components": False, "occlusion": True, "shap": True, "integrated_gradients": True, "gradient_shap": True}, "Trace availability depends on retained explicit fuzzy semantics."),
    ModelCatalogEntry("decision_tree", "Decision Tree", "Classical baseline", True, {"fit": True, "predict": True, "predict_proba": True, "structural_trace": True, "exact_semantic_trace": False, "exact_tree_path": True, "rule_access": True, "tree_shap": True, "gradient_access": False, "occlusion": True, "shap": True}, "Exact execution path and model-specific TreeSHAP are separate evidence objects; TreeSHAP remains post-hoc attribution."),
    ModelCatalogEntry("random_forest", "Random Forest", "Classical baseline", True, {"fit": True, "predict": True, "predict_proba": True, "structural_trace": True, "exact_semantic_trace": False, "exact_tree_path": False, "tree_shap": True, "gradient_access": False, "occlusion": True, "shap": True}, "TreeSHAP attributes the full persisted forest aggregation; RuFLEX never presents one constituent path as an exact ensemble explanation."),
    ModelCatalogEntry("gradient_boosting", "Gradient Boosting", "Classical baseline", True, {"fit": True, "predict": True, "predict_proba": True, "structural_trace": True, "exact_semantic_trace": False, "exact_tree_path": False, "tree_shap": True, "gradient_access": False, "occlusion": True, "shap": True}, "TreeSHAP explains the additive raw score for binary boosting; no constituent path is mislabeled as exact ensemble explanation."),
    ModelCatalogEntry("linear", "Logistic / Linear Regression", "Classical baseline", True, {"fit": True, "predict": True, "export": True, "occlusion": True, "shap": True}, "Trains a safe declarative coefficient artifact; binary data use logistic regression and regression data use linear regression."),
)


def list_model_catalog() -> list[dict]:
    return [asdict(entry) for entry in _ENTRIES]
