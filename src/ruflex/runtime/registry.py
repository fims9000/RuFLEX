"""Immutable, validated registry for trusted runtime adapters."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from importlib import metadata
from typing import Any

from ruflex.runtime.contracts import (
    ExecutionBackendDescriptor,
    ExecutionBackendAdapter,
    ExplainerAdapter,
    ExplainerDescriptor,
    ExplanationValidatorAdapter,
    ModelAdapter,
    ModelAdapterDescriptor,
    RuntimeIdentity,
    ValidatorDescriptor,
)
from ruflex.runtime.errors import RuntimeDependencyMissingError, RuntimeDuplicateError, RuntimeIncompatibleError, RuntimeNotFoundError, RuntimeUntrustedError, RuntimeVersionMismatchError


class RuntimeRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ModelAdapter] = {}
        self._components: dict[str, dict[str, ExplainerDescriptor | ValidatorDescriptor | ExecutionBackendDescriptor]] = {
            "explainer": {},
            "explanation_validator": {},
            "execution_backend": {},
        }
        self._component_implementations: dict[str, dict[str, object]] = {
            "explainer": {},
            "explanation_validator": {},
            "execution_backend": {},
        }
        self._frozen = False

    def register_model_adapter(self, adapter: ModelAdapter, *, trusted: bool = True) -> None:
        descriptor = adapter.descriptor
        identity = descriptor.identity
        if identity.kind != "model_adapter":
            raise ValueError("Model adapter identity must have kind 'model_adapter'.")
        if not trusted:
            raise RuntimeUntrustedError(identity.key)
        if self._frozen or identity.key in self._adapters:
            raise RuntimeDuplicateError(identity.key)
        for dependency in descriptor.optional_dependencies:
            if importlib.util.find_spec(dependency) is None:
                raise RuntimeDependencyMissingError(identity.key, dependency)
        self._adapters[identity.key] = adapter

    def register_component(
        self,
        descriptor: ExplainerDescriptor | ValidatorDescriptor | ExecutionBackendDescriptor,
        *,
        implementation: object | None = None,
        trusted: bool = True,
    ) -> None:
        """Register a non-model runtime component before snapshot freeze.

        Components declare capabilities and provenance; application services own
        canonical persistence and invoke their safe product-native operation.
        """
        identity = descriptor.identity
        if identity.kind not in self._components:
            raise ValueError(f"Unsupported runtime component kind {identity.kind!r}.")
        if not trusted:
            raise RuntimeUntrustedError(identity.key)
        if self._frozen or identity.key in self._components[identity.kind]:
            raise RuntimeDuplicateError(identity.key)
        if implementation is not None:
            expected_protocol = {
                "explainer": ExplainerAdapter,
                "explanation_validator": ExplanationValidatorAdapter,
                "execution_backend": ExecutionBackendAdapter,
            }[identity.kind]
            if not isinstance(implementation, expected_protocol):
                raise TypeError(
                    f"Runtime component {identity.key!r} does not provide the complete "
                    f"{expected_protocol.__name__} contract."
                )
        self._components[identity.kind][identity.key] = descriptor
        if implementation is not None:
            self._component_implementations[identity.kind][identity.key] = implementation

    def freeze(self) -> "RuntimeRegistry":
        self._frozen = True
        return self

    def resolve_model_adapter(self, key: str, *, version: str | None = None) -> ModelAdapter:
        try:
            adapter = self._adapters[key]
        except KeyError as error:
            raise RuntimeNotFoundError(key) from error
        if version is not None and adapter.descriptor.identity.version != version:
            raise RuntimeVersionMismatchError(key, version)
        return adapter

    def resolve_training_model_kind(self, model_kind: str) -> ModelAdapter:
        """Resolve the stable default for a semantic model kind.

        A registered native adapter remains the backward-compatible default
        when an explicitly selectable external adapter also implements that
        kind. Ambiguous non-native registrations fail closed instead of making
        plugin sort order part of model selection.
        """
        matches = [
            self._adapters[key]
            for key in sorted(self._adapters)
            if model_kind in self._adapters[key].descriptor.training_model_kinds
        ]
        if not matches:
            raise RuntimeNotFoundError(model_kind)
        native = [item for item in matches if item.descriptor.identity.provider == "ruflex.builtin"]
        if len(native) == 1:
            return native[0]
        if len(native) > 1:
            raise RuntimeIncompatibleError(f"Multiple native adapters declare model kind {model_kind!r}.")
        if len(matches) == 1:
            return matches[0]
        keys = ", ".join(f"{item.descriptor.identity.key}@{item.descriptor.identity.version}" for item in matches)
        raise RuntimeIncompatibleError(
            f"Model kind {model_kind!r} is declared by multiple adapters ({keys}); select an adapter explicitly."
        )

    def model_descriptors(self) -> list[ModelAdapterDescriptor]:
        return [self._adapters[key].descriptor for key in sorted(self._adapters)]

    def component_descriptors(
        self, kind: str,
    ) -> list[ExplainerDescriptor | ValidatorDescriptor | ExecutionBackendDescriptor]:
        try:
            components = self._components[kind]
        except KeyError as error:
            raise RuntimeNotFoundError(kind) from error
        return [components[key] for key in sorted(components)]

    def resolve_component(
        self, kind: str, key: str, *, version: str | None = None,
    ) -> ExplainerDescriptor | ValidatorDescriptor | ExecutionBackendDescriptor:
        try:
            descriptor = self._components[kind][key]
        except KeyError as error:
            raise RuntimeNotFoundError(key) from error
        if version is not None and descriptor.identity.version != version:
            raise RuntimeVersionMismatchError(key, version)
        return descriptor

    def resolve_component_implementation(self, kind: str, key: str, *, version: str | None = None) -> object:
        """Resolve a component only after its descriptor/version gate passes."""
        self.resolve_component(kind, key, version=version)
        try:
            return self._component_implementations[kind][key]
        except KeyError as error:
            raise RuntimeNotFoundError(key) from error

    def snapshot(self) -> dict[str, Any]:
        models = [descriptor.model_dump(mode="json") for descriptor in self.model_descriptors()]
        components = {
            "explainers": [descriptor.model_dump(mode="json") for descriptor in self.component_descriptors("explainer")],
            "validators": [descriptor.model_dump(mode="json") for descriptor in self.component_descriptors("explanation_validator")],
            "backends": [descriptor.model_dump(mode="json") for descriptor in self.component_descriptors("execution_backend")],
        }
        payload = {"models": models, **components}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {"schema_version": 2, "frozen": self._frozen, **payload, "sha256": hashlib.sha256(canonical).hexdigest()}

    def discover_entry_points(self, *, group: str | None = None) -> list[ModelAdapterDescriptor | ExplainerDescriptor | ValidatorDescriptor | ExecutionBackendDescriptor]:
        """Discover trusted runtime components by their declared category.

        ``ruflex.plugins`` remains a model-adapter compatibility group. New
        plugins use category-specific groups, so an explainer/validator/backend
        can enter the same frozen capability snapshot without pretending to be
        a trainable model.
        """
        if self._frozen:
            raise RuntimeDuplicateError("runtime_snapshot")
        groups = (group,) if group is not None else (
            "ruflex.plugins", "ruflex.model_adapters", "ruflex.explainers",
            "ruflex.validators", "ruflex.execution_backends",
        )
        points = metadata.entry_points()
        discovered: list[ModelAdapterDescriptor | ExplainerDescriptor | ValidatorDescriptor | ExecutionBackendDescriptor] = []
        for entry_group in groups:
            selected = points.select(group=entry_group) if hasattr(points, "select") else points.get(entry_group, ())
            for point in sorted(selected, key=lambda item: item.name):
                candidate = point.load(); adapter = candidate() if callable(candidate) else candidate
                if entry_group in {"ruflex.plugins", "ruflex.model_adapters"}:
                    if not isinstance(adapter, ModelAdapter): raise TypeError(f"Runtime entry point {point.name!r} does not provide a ModelAdapter.")
                    self.register_model_adapter(adapter); discovered.append(adapter.descriptor); continue
                if entry_group == "ruflex.explainers":
                    if not isinstance(adapter, ExplainerAdapter): raise TypeError(f"Runtime entry point {point.name!r} does not provide an ExplainerAdapter.")
                elif entry_group == "ruflex.validators":
                    if not isinstance(adapter, ExplanationValidatorAdapter): raise TypeError(f"Runtime entry point {point.name!r} does not provide an ExplanationValidatorAdapter.")
                elif entry_group == "ruflex.execution_backends":
                    if not isinstance(adapter, ExecutionBackendAdapter): raise TypeError(f"Runtime entry point {point.name!r} does not provide an ExecutionBackendAdapter.")
                else: raise RuntimeNotFoundError(entry_group)
                self.register_component(adapter.descriptor, implementation=adapter); discovered.append(adapter.descriptor)
        return discovered


_builtin_registry: RuntimeRegistry | None = None


def builtin_runtime_registry() -> RuntimeRegistry:
    global _builtin_registry
    if _builtin_registry is None:
        from ruflex.runtime.builtins import builtin_model_adapters
        from ruflex.runtime.backends import LOCAL_EXECUTOR, local_execution_backend_adapter
        from ruflex.runtime.explainers import builtin_explainer_adapters
        from ruflex.runtime.validators import NATIVE_EXPLANATION_VALIDATOR, native_explanation_validator_adapter

        registry = RuntimeRegistry()
        for adapter in builtin_model_adapters():
            registry.register_model_adapter(adapter)
        for adapter in builtin_explainer_adapters():
            registry.register_component(adapter.descriptor, implementation=adapter)
        registry.register_component(NATIVE_EXPLANATION_VALIDATOR, implementation=native_explanation_validator_adapter())
        registry.register_component(LOCAL_EXECUTOR, implementation=local_execution_backend_adapter())
        # Installed entry-point packages cross the trust boundary only through
        # the same descriptor validation as built-ins, before the snapshot is
        # frozen. No discovery occurs in the middle of a run.
        registry.discover_entry_points()
        _builtin_registry = registry.freeze()
    return _builtin_registry
