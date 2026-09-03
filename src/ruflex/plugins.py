from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


PluginKind = Literal["model_adapter", "explainer", "explanation_validator", "metric", "exporter", "execution_backend"]


class PluginDescriptor(BaseModel):
    """Inspectable contract required before a trusted integration can run."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{2,80}$")
    version: str = Field(min_length=1, max_length=80)
    kind: PluginKind
    capabilities: dict[str, bool] = Field(default_factory=dict)
    config_schema: dict[str, Any] = Field(default_factory=dict)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    trusted: bool = True
    scientific_note: str = "Registered plugins are inspected product integrations, not arbitrary executable uploads."


class PluginContractError(RuntimeError):
    pass


class PluginRegistry:
    """Fail closed for implicit, duplicate, or untrusted integrations."""

    def __init__(self) -> None:
        self._descriptors: dict[str, PluginDescriptor] = {}
        self._implementations: dict[str, object] = {}

    def register(self, descriptor: PluginDescriptor, implementation: object) -> None:
        if not descriptor.trusted:
            raise PluginContractError(f"Plugin {descriptor.key!r} is not trusted and cannot be registered for local execution.")
        if descriptor.key in self._descriptors:
            raise PluginContractError(f"Plugin key {descriptor.key!r} is already registered.")
        if getattr(implementation, "key", None) != descriptor.key or getattr(implementation, "version", None) != descriptor.version:
            raise PluginContractError(f"Plugin implementation does not match descriptor {descriptor.key!r}.")
        self._descriptors[descriptor.key] = descriptor
        self._implementations[descriptor.key] = implementation

    def descriptor(self, key: str) -> PluginDescriptor:
        try:
            return self._descriptors[key]
        except KeyError as error:
            raise PluginContractError(f"Plugin capability is unavailable: {key!r} is not registered.") from error

    def implementation(self, key: str) -> object:
        self.descriptor(key)
        return self._implementations[key]

    def list_descriptors(self) -> list[PluginDescriptor]:
        return [self._descriptors[key] for key in sorted(self._descriptors)]


@runtime_checkable
class ModelAdapterPlugin(Protocol):
    """Boundary for trusted model adapters; plugins operate on canonical project data, never opaque GUI state."""

    key: str
    version: str

    def capabilities(self) -> dict[str, bool]: ...
    def fit(self, *, project_root: str, config: dict[str, Any]) -> Any: ...
    def predict(self, *, project_root: str, model_id: str, rows: list[dict[str, Any]]) -> list[Any]: ...


@runtime_checkable
class ExplainerPlugin(Protocol):
    key: str
    version: str

    def supports(self, capabilities: dict[str, bool]) -> bool: ...
    def explain(self, *, project_root: str, run_id: str, sample: dict[str, float], config: dict[str, Any]) -> Any: ...


@runtime_checkable
class ExplanationValidatorPlugin(Protocol):
    key: str
    version: str

    def validate(self, *, project_root: str, explanation_id: str) -> Any: ...


@runtime_checkable
class MetricPlugin(Protocol):
    key: str
    version: str

    def compute(self, *, targets: list[float], predictions: list[float], context: dict[str, Any]) -> float: ...


@runtime_checkable
class ExporterPlugin(Protocol):
    key: str
    version: str

    def can_export(self, canonical_object: Any) -> tuple[bool, str | None]: ...
    def export(self, canonical_object: Any) -> bytes: ...
