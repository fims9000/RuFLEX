"""Immutable, validated registry for trusted runtime adapters."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from importlib import metadata
from typing import Any

from ruflex.runtime.contracts import (
    ExecutionBackendDescriptor,
    ExplainerDescriptor,
    ModelAdapter,
    ModelAdapterDescriptor,
    RuntimeIdentity,
    ValidatorDescriptor,
)
from ruflex.runtime.errors import RuntimeDependencyMissingError, RuntimeDuplicateError, RuntimeNotFoundError, RuntimeUntrustedError, RuntimeVersionMismatchError


class RuntimeRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ModelAdapter] = {}
        self._components: dict[str, dict[str, ExplainerDescriptor | ValidatorDescriptor | ExecutionBackendDescriptor]] = {
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
        self._components[identity.kind][identity.key] = descriptor

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
        """Resolve the declared concrete TrainingRun kind without UI name logic."""
        for descriptor in self.model_descriptors():
            if model_kind in descriptor.training_model_kinds:
                return self.resolve_model_adapter(descriptor.identity.key)
        raise RuntimeNotFoundError(model_kind)

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

    def discover_entry_points(self, *, group: str = "ruflex.plugins") -> list[ModelAdapterDescriptor]:
        if self._frozen:
            raise RuntimeDuplicateError("runtime_snapshot")
        points = metadata.entry_points()
        selected = points.select(group=group) if hasattr(points, "select") else points.get(group, ())
        discovered: list[ModelAdapterDescriptor] = []
        for point in sorted(selected, key=lambda item: item.name):
            candidate = point.load()
            adapter = candidate() if callable(candidate) else candidate
            if not isinstance(adapter, ModelAdapter):
                raise TypeError(f"Runtime entry point {point.name!r} does not provide a ModelAdapter.")
            self.register_model_adapter(adapter)
            discovered.append(adapter.descriptor)
        return discovered


_builtin_registry: RuntimeRegistry | None = None


def builtin_runtime_registry() -> RuntimeRegistry:
    global _builtin_registry
    if _builtin_registry is None:
        from ruflex.runtime.builtins import builtin_model_adapters
        from ruflex.runtime.backends import LOCAL_EXECUTOR
        from ruflex.runtime.explainers import BUILTIN_EXPLAINERS
        from ruflex.runtime.validators import NATIVE_EXPLANATION_VALIDATOR

        registry = RuntimeRegistry()
        for adapter in builtin_model_adapters():
            registry.register_model_adapter(adapter)
        for descriptor in BUILTIN_EXPLAINERS:
            registry.register_component(descriptor)
        registry.register_component(NATIVE_EXPLANATION_VALIDATOR)
        registry.register_component(LOCAL_EXECUTOR)
        # Installed entry-point packages cross the trust boundary only through
        # the same descriptor validation as built-ins, before the snapshot is
        # frozen. No discovery occurs in the middle of a run.
        registry.discover_entry_points()
        _builtin_registry = registry.freeze()
    return _builtin_registry
