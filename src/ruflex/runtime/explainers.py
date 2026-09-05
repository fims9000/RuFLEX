"""Typed declarations for persisted explanation routes."""
from ruflex.runtime.contracts import ExplainerDescriptor, RuntimeIdentity


BUILTIN_EXPLAINERS: tuple[ExplainerDescriptor, ...] = (
    ExplainerDescriptor(identity=RuntimeIdentity(key="occlusion", version="1", provider="ruflex.builtin", kind="explainer"), supported_tasks=("binary_classification", "regression")),
    ExplainerDescriptor(identity=RuntimeIdentity(key="shap", version="1", provider="ruflex.builtin", kind="explainer"), supported_tasks=("binary_classification", "regression")),
    ExplainerDescriptor(identity=RuntimeIdentity(key="tree_shap", version="1", provider="ruflex.builtin", kind="explainer"), supported_tasks=("binary_classification", "regression"), required_capabilities=("tree_shap",)),
    ExplainerDescriptor(identity=RuntimeIdentity(key="integrated_gradients", version="1", provider="ruflex.builtin", kind="explainer"), supported_tasks=("binary_classification", "regression"), required_capabilities=("integrated_gradients",)),
    ExplainerDescriptor(identity=RuntimeIdentity(key="gradient_shap", version="1", provider="ruflex.builtin", kind="explainer"), supported_tasks=("binary_classification", "regression"), required_capabilities=("gradient_shap",)),
)
