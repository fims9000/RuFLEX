from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class RiskCoveragePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confidence_cutoff: float = Field(ge=0.5, le=1.0)
    coverage: float = Field(ge=0.0, le=1.0)
    accepted_risk: float | None = Field(default=None, ge=0.0, le=1.0)
    accepted_count: int = Field(ge=0)


class SelectivePredictionPolicy(BaseModel):
    """Validation-only confidence policy, deliberately independent of class threshold."""
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    policy_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluation_id: UUID
    run_id: UUID
    calibration_id: UUID | None = None
    source_split: str = "validation"
    test_status: str = "LOCKED_NOT_EVALUATED"
    confidence_cutoff: float = Field(ge=0.5, le=1.0)
    class_threshold_id: UUID
    class_threshold: float = Field(ge=0.0, le=1.0)
    probability_source: str
    fit_sample_identity: str
    risk_coverage: list[RiskCoveragePoint]
    scientific_note: str = "This ACCEPT/REVIEW policy was selected on validation evidence only and is separate from the class decision threshold."


class SelectiveDecision(BaseModel):
    """Application of an already-frozen policy; it performs no tuning."""
    model_config = ConfigDict(extra="forbid")
    policy_id: UUID
    run_id: UUID
    probability: float = Field(ge=0.0, le=1.0)
    predicted_label: int
    confidence: float = Field(ge=0.5, le=1.0)
    disposition: Literal["ACCEPT", "REVIEW", "OUT_OF_SCOPE"]
    scope_disposition: Literal["ALLOW", "REVIEW", "BLOCK", "NOT_EVALUATED"] = "NOT_EVALUATED"
    reasons: list[str] = Field(default_factory=list)
