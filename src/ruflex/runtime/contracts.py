"""Pure typed contracts for the RuFLEX runtime trust boundary."""
from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

import numpy as np
from pydantic import BaseModel, ConfigDict, Field


RuntimeKind = Literal["model_adapter", "explainer", "explanation_validator", "execution_backend"]
Task = Literal["regression", "binary_classification"]


class RuntimeIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{2,80}$")
    version: str = Field(min_length=1, max_length=80)
    provider: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,120}$")
    kind: RuntimeKind

    @property
    def canonical_key(self) -> str:
        return f"{self.kind}:{self.provider}:{self.key}:{self.version}"


class ModelAdapterDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    identity: RuntimeIdentity
    family: str
    training_model_kinds: tuple[str, ...]
    supported_tasks: tuple[Task, ...]
    input_modalities: tuple[str, ...] = ("tabular",)
    capabilities: dict[str, bool] = Field(default_factory=dict)
    supported_explainers: tuple[str, ...] = ()
    config_schema: dict[str, Any] = Field(default_factory=dict)
    defaults: dict[str, Any] = Field(default_factory=dict)
    parameter_constraints: dict[str, Any] = Field(default_factory=dict)
    optional_dependencies: tuple[str, ...] = ()
    evidence_objects_produced: tuple[str, ...] = ("TrainingRun", "ModelArtifact")
    limitations: tuple[str, ...] = ()
    available: bool = True
    unavailability_reason: str | None = None


class FitRequest(BaseModel):
    """Core-prepared, train/validation-only adapter input."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    task: Task
    feature_names: tuple[str, ...]
    X_train: Any
    y_train: Any
    X_validation: Any
    y_validation: Any
    split_identity: str
    split_seed: int
    training_seed: int
    validated_parameters: dict[str, Any] = Field(default_factory=dict)
    preprocessing_identity: str


class FitResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    model_payload: Any | None = None
    serialized_artifact: bytes
    artifact_media_type: str
    model_spec: dict[str, Any] = Field(default_factory=dict)
    training_summary: dict[str, Any] = Field(default_factory=dict)
    trajectory: list[dict[str, Any]] = Field(default_factory=list)
    validation_raw_predictions: list[float]
    validation_raw_probabilities: list[float] | None = None
    model_specific_metadata: dict[str, Any] = Field(default_factory=dict)


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    task: Task
    feature_names: tuple[str, ...]
    features: Any
    artifact: bytes
    model_spec: dict[str, Any] = Field(default_factory=dict)
    preprocessing_identity: str


class PredictionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prediction: list[float]
    score: list[float] | None = None
    probability: list[float] | None = None
    raw_score: list[float] | None = None


@runtime_checkable
class ModelAdapter(Protocol):
    descriptor: ModelAdapterDescriptor

    def fit(self, request: FitRequest) -> FitResult: ...
    def predict(self, request: PredictionRequest) -> PredictionResult: ...
