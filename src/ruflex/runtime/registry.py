"""Immutable, validated registry for trusted runtime adapters."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from importlib import metadata
from typing import Any

from ruflex.runtime.contracts import ModelAdapter, ModelAdapterDescriptor, RuntimeIdentity
from ruflex.runtime.errors import RuntimeDependencyMissingError, RuntimeDuplicateError, RuntimeNotFoundError, RuntimeUntrustedError, RuntimeVersionMismatchError


class RuntimeRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ModelAdapter] = {}
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

    def snapshot(self) -> dict[str, Any]:
        models = [descriptor.model_dump(mode="json") for descriptor in self.model_descriptors()]
        canonical = json.dumps(models, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {"schema_version": 1, "frozen": self._frozen, "models": models, "sha256": hashlib.sha256(canonical).hexdigest()}

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

        registry = RuntimeRegistry()
        for adapter in builtin_model_adapters():
            registry.register_model_adapter(adapter)
        _builtin_registry = registry.freeze()
    return _builtin_registry
