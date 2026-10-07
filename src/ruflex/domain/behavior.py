from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from ruflex.domain.fis import FISTrace


class BehaviorSpec(BaseModel):
    """An executable, revision-bound behavioural requirement; never a score."""
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 2
    spec_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: UUID | None = None
    model_artifact_sha256: str | None = None
    fis_id: UUID | None = None
    fis_semantic_hash: str | None = None
    name: str = Field(min_length=1)
    kind: Literal["output_range", "monotonic_pair", "invariance_pair", "symmetry_pair", "bounded_perturbation", "categorical_invariance", "forbidden_region", "required_order", "domain_constraint", "regression_case", "batch_regression_suite"]
    sample: dict[str, float]
    comparison_sample: dict[str, float] | None = None
    minimum: float | None = None
    maximum: float | None = None
    expected_direction: Literal["nondecreasing", "nonincreasing"] | None = None
    maximum_delta: float | None = Field(default=None, ge=0.0)
    cases: list["BehaviorCase"] = Field(default_factory=list)
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


class BehaviorCase(BaseModel):
    name: str = Field(min_length=1)
    sample: dict[str, float] = Field(min_length=1)
    minimum: float | None = None
    maximum: float | None = None


class BehaviorObservation(BaseModel):
    name: str
    output: float
    status: Literal["PASS", "FAIL"]
    detail: str


class BehaviorSpecResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1, 2] = 1
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
    observations: list[BehaviorObservation] = Field(default_factory=list)
    exact_fis_traces: dict[str, FISTrace] = Field(default_factory=dict)

    @model_validator(mode="after")
    def trace_schema(self) -> "BehaviorSpecResult":
        if self.schema_version == 1 and self.exact_fis_traces:
            raise ValueError("Legacy BehaviorSpecResult cannot claim new exact FIS traces.")
        if self.run_id is not None and self.exact_fis_traces:
            raise ValueError("TrainingRun-bound BehaviorSpecResult cannot claim native FIS traces.")
        if self.schema_version == 2 and self.fis_id is not None and not self.exact_fis_traces:
            raise ValueError("New FIS-bound BehaviorSpecResult requires its exact computation trace.")
        return self


class BehaviorRevisionComparison(BaseModel):
    """Read-only transition evidence for the same requirement across revisions."""
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    comparison_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    requirement_identity: str
    baseline_result_id: UUID
    candidate_result_id: UUID
    baseline_status: Literal["PASS", "FAIL"]
    candidate_status: Literal["PASS", "FAIL"]
    transition: Literal["PASS_TO_PASS", "PASS_TO_FAIL", "FAIL_TO_PASS", "FAIL_TO_FAIL"]
    regression_detected: bool
    baseline_binding: str
    candidate_binding: str
    scientific_note: str = (
        "This comparison reports a frozen requirement's status transition across two persisted revisions. "
        "It does not establish causal attribution for the revision or validate untested requirements."
    )
