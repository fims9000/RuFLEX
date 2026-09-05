"""Typed built-in post-hoc explainer adapters.

The adapters choose no fallback and persist nothing themselves.  They only
bind a frozen runtime identity to a supported existing product-native route;
the application remains responsible for the ExplanationContract.
"""
from __future__ import annotations

from dataclasses import dataclass

from ruflex.runtime.contracts import ExplainerDescriptor, ExplainerRequest, ExplainerResult, RuntimeIdentity


BUILTIN_EXPLAINERS: tuple[ExplainerDescriptor, ...] = (
    ExplainerDescriptor(identity=RuntimeIdentity(key="occlusion", version="1", provider="ruflex.builtin", kind="explainer"), supported_tasks=("binary_classification", "regression")),
    ExplainerDescriptor(identity=RuntimeIdentity(key="shap", version="1", provider="ruflex.builtin", kind="explainer"), supported_tasks=("binary_classification", "regression")),
    ExplainerDescriptor(identity=RuntimeIdentity(key="tree_shap", version="1", provider="ruflex.builtin", kind="explainer"), supported_tasks=("binary_classification", "regression"), required_capabilities=("tree_shap",)),
    ExplainerDescriptor(identity=RuntimeIdentity(key="integrated_gradients", version="1", provider="ruflex.builtin", kind="explainer"), supported_tasks=("binary_classification", "regression"), required_capabilities=("integrated_gradients",)),
    ExplainerDescriptor(identity=RuntimeIdentity(key="gradient_shap", version="1", provider="ruflex.builtin", kind="explainer"), supported_tasks=("binary_classification", "regression"), required_capabilities=("gradient_shap",)),
)


@dataclass(frozen=True)
class _BuiltinExplainerAdapter:
    descriptor: ExplainerDescriptor

    def supports(self, *, run_capabilities: dict[str, str], task: str, artifact: str) -> tuple[bool, str | None]:
        if task not in self.descriptor.supported_tasks:
            return False, f"Task {task!r} is not supported by {self.descriptor.identity.key}."
        for capability in self.descriptor.required_capabilities:
            if run_capabilities.get(capability) != "AVAILABLE":
                return False, f"Required capability {capability!r} is unavailable for the persisted artifact."
        return True, None

    def explain(self, request: ExplainerRequest) -> ExplainerResult:
        # Late import keeps the runtime contract layer independent from
        # application persistence while retaining current vetted algorithms.
        from ruflex.application import evidence

        values = request.parameters
        routes = {
            "occlusion": lambda: evidence._build_occlusion_explanation(request.project_root, request.run_id, request.sample),
            "integrated_gradients": lambda: evidence._build_integrated_gradients_explanation(request.project_root, request.run_id, request.sample, steps=int(values.get("steps", 64))),
            "gradient_shap": lambda: evidence._build_gradient_shap_explanation(request.project_root, request.run_id, request.sample, background_count=int(values.get("background_count", 24))),
            "shap": lambda: evidence._build_permutation_shap_explanation(request.project_root, request.run_id, request.sample, background_count=int(values.get("background_count", 24)), max_evals=None if values.get("max_evals") is None else int(values["max_evals"])),
            "tree_shap": lambda: evidence._build_tree_shap_explanation(request.project_root, request.run_id, request.sample, background_count=int(values.get("background_count", 32))),
        }
        return ExplainerResult(explanation=routes[self.descriptor.identity.key]())


def builtin_explainer_adapters() -> tuple[_BuiltinExplainerAdapter, ...]:
    return tuple(_BuiltinExplainerAdapter(descriptor) for descriptor in BUILTIN_EXPLAINERS)
