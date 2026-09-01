from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ModelAdapterPlugin(Protocol):
    """Boundary for trusted model adapters; plugins operate on canonical project data, never opaque GUI state."""

    key: str

    def capabilities(self) -> dict[str, bool]: ...
    def fit(self, *, project_root: str, config: dict[str, Any]) -> Any: ...
    def predict(self, *, project_root: str, model_id: str, rows: list[dict[str, Any]]) -> list[Any]: ...


@runtime_checkable
class ExplainerPlugin(Protocol):
    key: str

    def supports(self, capabilities: dict[str, bool]) -> bool: ...
    def explain(self, *, project_root: str, run_id: str, sample: dict[str, float], config: dict[str, Any]) -> Any: ...


@runtime_checkable
class ExplanationValidatorPlugin(Protocol):
    key: str

    def validate(self, *, project_root: str, explanation_id: str) -> Any: ...


@runtime_checkable
class MetricPlugin(Protocol):
    key: str

    def compute(self, *, targets: list[float], predictions: list[float], context: dict[str, Any]) -> float: ...


@runtime_checkable
class ExporterPlugin(Protocol):
    key: str

    def can_export(self, canonical_object: Any) -> tuple[bool, str | None]: ...
    def export(self, canonical_object: Any) -> bytes: ...
