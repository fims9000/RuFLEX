from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BehaviorSpec(BaseModel):
    """An executable, revision-bound behavioural requirement; never a score."""
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    spec_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: UUID | None = None
    model_artifact_sha256: str | None = None
    fis_id: UUID | None = None
    fis_semantic_hash: str | None = None
    name: str = Field(min_length=1)
    kind: Literal["output_range", "monotonic_pair", "invariance_pair", "regression_case"]
    sample: dict[str, float]
    comparison_sample: dict[str, float] | None = None
    minimum: float | None = None
    maximum: float | None = None
    expected_direction: Literal["nondecreasing", "nonincreasing"] | None = None
    tolerance: float = Field(default=1e-9, ge=0.0)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def exact_binding(self) -> "BehaviorSpec":
        if (self.run_id is None) == (self.fis_id is None):
            raise ValueError("BehaviorSpec must bind to exactly one TrainingRun artifact or FIS revision.")
        if self.run_id is not None and not self.model_artifact_sha256:
            raise ValueError("TrainingRun-bound BehaviorSpec requires model artifact identity.")
        if self.fis_id is not None and not self.fis_semantic_hash:
            raise ValueError("FIS-bound BehaviorSpec requires semantic revision identity.")
        return self


class BehaviorSpecResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    spec_id: UUID
    run_id: UUID | None = None
    model_artifact_sha256: str | None = None
    fis_id: UUID | None = None
    fis_semantic_hash: str | None = None
    status: Literal["PASS", "FAIL"]
    observed_output: float
    comparison_output: float | None = None
    detail: str
