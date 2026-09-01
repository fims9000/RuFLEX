from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class MetricDistribution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mean: float
    std: float
    minimum: float
    maximum: float
    median: float
    iqr: float


class CaseStability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    source_row: int | None = None
    target: int
    selected_run_probability: float
    selected_run_class: int
    mean_probability: float
    std_probability: float
    min_probability: float
    max_probability: float
    probability_range: float
    predicted_class_agreement: float = Field(ge=0.0, le=1.0)
    positive_vote_fraction: float = Field(ge=0.0, le=1.0)
    vote_entropy: float = Field(ge=0.0)
    run_probabilities: dict[str, float]
    run_labels: dict[str, int]


class RiskCoverageComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy: Literal["NO_REVIEW", "RANDOM_REVIEW", "CONFIDENCE_ONLY", "STABILITY_AWARE"]
    coverage: float = Field(ge=0.0, le=1.0)
    accepted_count: int = Field(ge=0)
    accepted_risk: float | None = None


class StudyStabilityAnalysis(BaseModel):
    """Persisted, validation-only cross-run prediction-stability evidence."""

    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    analysis_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    study_id: UUID
    dataset_fingerprint: str | None
    split_identity: str
    model_kind: str
    task: Literal["binary_classification"]
    run_ids: list[UUID] = Field(min_length=3)
    training_seeds: list[int] = Field(min_length=3)
    split_seed: int
    evaluation_case_identity: str
    selected_run_id: UUID
    case_count: int = Field(ge=1)
    metric_distributions: dict[str, MetricDistribution]
    cases: list[CaseStability]
    high_confidence_threshold: float = Field(default=0.9, ge=0.5, le=1.0)
    unstable_agreement_threshold: float = Field(default=0.8, gt=0.0, le=1.0)
    high_confidence_instability_rate: float = Field(ge=0.0, le=1.0)
    high_confidence_case_count: int = Field(ge=0)
    high_confidence_unstable_case_count: int = Field(ge=0)
    scientific_note: str = (
        "Prediction reproducibility is measured independently from explanation reproducibility. "
        "Close aggregate metrics or high confidence for one selected run do not establish stable case-level decisions."
    )


class StabilityGateDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    disposition: Literal["ACCEPT", "REVIEW", "BLOCK"]
    reasons: list[Literal["LOW_CONFIDENCE", "RUN_DISAGREEMENT", "HIGH_DISPERSION", "OUT_OF_SCOPE"]] = Field(default_factory=list)
    selected_run_probability: float
    confidence: float
    class_agreement: float
    probability_std: float


class StabilityGatePolicy(BaseModel):
    """A validation-derived decision gate; no explanation statistic is a gate input."""

    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    policy_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    frozen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    study_id: UUID
    stability_analysis_id: UUID
    selected_run_id: UUID
    evaluation_id: UUID
    calibration_id: UUID | None = None
    source_split: Literal["validation"] = "validation"
    fit_sample_identity: str
    min_confidence: float = Field(ge=0.5, le=1.0)
    min_class_agreement: float = Field(gt=0.0, le=1.0)
    max_probability_std: float = Field(ge=0.0)
    decisions: list[StabilityGateDecision]
    risk_coverage: list[RiskCoverageComparison]
    test_status: Literal["LOCKED_NOT_EVALUATED"] = "LOCKED_NOT_EVALUATED"
    scientific_note: str = (
        "This policy was derived from validation evidence only. Prediction stability is an operational review signal; "
        "explanation stability remains a separate evidence channel and is not used as a decision criterion."
    )


class StabilityGateApplication(BaseModel):
    """A non-tuning application of a frozen Stability Gate to one new case."""

    model_config = ConfigDict(extra="forbid")
    policy_id: UUID
    selected_run_id: UUID
    disposition: Literal["ACCEPT", "REVIEW", "BLOCK"]
    reasons: list[Literal["LOW_CONFIDENCE", "RUN_DISAGREEMENT", "HIGH_DISPERSION", "OUT_OF_SCOPE"]] = Field(default_factory=list)
    selected_run_probability: float
    predicted_label: int
    confidence: float
    class_agreement: float
    probability_std: float
    run_probabilities: dict[str, float]
