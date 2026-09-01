from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    run_support_count: int = Field(ge=0)
    run_support_fraction: float = Field(ge=0.0, le=1.0)
    target: int
    selected_run_probability: float
    selected_run_class: int | None = None
    mean_probability: float
    std_probability: float
    min_probability: float
    max_probability: float
    probability_range: float
    majority_class: int | None = None
    majority_class_agreement: float | None = Field(default=None, ge=0.0, le=1.0)
    selected_run_agreement: float | None = Field(default=None, ge=0.0, le=1.0)
    positive_vote_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    vote_entropy: float | None = Field(default=None, ge=0.0)
    run_probabilities: dict[str, float]
    run_labels: dict[str, int]

    @model_validator(mode="before")
    @classmethod
    def _migrate_support(cls, value: object) -> object:
        if isinstance(value, dict) and "run_support_count" not in value:
            value = dict(value)
            count = len(value.get("run_probabilities", {}))
            value["run_support_count"] = count
            value["run_support_fraction"] = 1.0
        if isinstance(value, dict) and "majority_class_agreement" not in value:
            value = dict(value)
            legacy = value.pop("predicted_class_agreement", None)
            value["majority_class_agreement"] = legacy
            value["selected_run_agreement"] = legacy
            value.setdefault("majority_class", None)
        return value


class RiskCoverageComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy: Literal["NO_REVIEW", "RANDOM_REVIEW", "CONFIDENCE_ONLY", "STABILITY_AWARE"]
    coverage: float = Field(ge=0.0, le=1.0)
    accepted_count: int = Field(ge=0)
    accepted_risk: float | None = None


class StudyStabilityAnalysis(BaseModel):
    """Persisted, validation-only cross-run prediction-stability evidence."""

    model_config = ConfigDict(extra="forbid")
    schema_version: int = 3
    analysis_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    study_id: UUID
    dataset_fingerprint: str | None
    dataset_artifact_sha256: str | None = None
    mode: Literal["TRAINING_VARIABILITY", "SPLIT_VARIABILITY", "COMBINED_VARIABILITY", "LEGACY_COMBINED"] = "LEGACY_COMBINED"
    split_identity: str | None = None
    split_seeds: list[int] = Field(default_factory=list)
    model_kind: str
    task: Literal["binary_classification"]
    run_ids: list[UUID] = Field(min_length=3)
    training_seeds: list[int] = Field(min_length=3)
    split_seed: int | None = None
    evaluation_case_identity: str | None = None
    evaluation_id: UUID | None = None
    class_threshold_id: UUID | None = None
    decision_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    validation_alignment_status: Literal["EXACT_MATCH", "MIXED_CASE_IDENTITIES", "NOT_APPLICABLE"]
    applicability: Literal["APPLICABLE", "NOT_APPLICABLE"] = "APPLICABLE"
    applicability_reason: str | None = None
    selected_run_id: UUID
    case_count: int = Field(ge=0)
    case_support_requirement: int = Field(default=3, ge=1)
    metric_distributions: dict[str, MetricDistribution]
    cases: list[CaseStability]
    probability_source: Literal["raw"] = "raw"
    high_confidence_threshold: float = Field(default=0.9, ge=0.5, le=1.0)
    unstable_agreement_threshold: float = Field(default=0.8, gt=0.0, le=1.0)
    high_confidence_instability_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    high_confidence_case_count: int = Field(ge=0)
    high_confidence_unstable_case_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    scientific_note: str = (
        "Prediction reproducibility is measured independently from explanation reproducibility. "
        "Close aggregate metrics or high confidence for one selected run do not establish stable case-level decisions."
    )

    @model_validator(mode="before")
    @classmethod
    def _migrate_v1(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        value = dict(value)
        value.setdefault("mode", "TRAINING_VARIABILITY" if value.get("split_identity") else "LEGACY_COMBINED")
        value.setdefault("dataset_artifact_sha256", None)
        value.setdefault("split_seeds", [value["split_seed"]] * len(value.get("run_ids", [])) if value.get("split_seed") is not None else [])
        value.setdefault("validation_alignment_status", "EXACT_MATCH" if value.get("cases") else "NOT_APPLICABLE")
        value.setdefault("applicability", "APPLICABLE" if value.get("cases") else "NOT_APPLICABLE")
        value.setdefault("applicability_reason", None)
        value.setdefault("case_support_requirement", 3)
        value.setdefault("probability_source", "raw")
        value.setdefault("warnings", [])
        value.setdefault("evaluation_id", None)
        value.setdefault("class_threshold_id", None)
        value.setdefault("decision_threshold", None)
        return value


class StabilityGateDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    disposition: Literal["ACCEPT", "REVIEW", "BLOCK"]
    reasons: list[Literal["LOW_CONFIDENCE", "RUN_DISAGREEMENT", "HIGH_DISPERSION", "OUT_OF_SCOPE", "INSUFFICIENT_RUN_SUPPORT"]] = Field(default_factory=list)
    selected_run_probability: float
    confidence: float
    majority_class_agreement: float
    selected_run_agreement: float
    probability_std: float
    run_support_count: int = Field(ge=0)

    @model_validator(mode="before")
    @classmethod
    def _migrate_support(cls, value: object) -> object:
        if isinstance(value, dict) and "run_support_count" not in value:
            value = dict(value)
            value["run_support_count"] = 0
        if isinstance(value, dict) and "selected_run_agreement" not in value:
            value = dict(value)
            legacy = value.pop("class_agreement", 0.0)
            value["majority_class_agreement"] = legacy
            value["selected_run_agreement"] = legacy
        return value


class StabilityGatePolicy(BaseModel):
    """A validation-derived decision gate; no explanation statistic is a gate input."""

    model_config = ConfigDict(extra="forbid")
    schema_version: int = 3
    policy_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    frozen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    study_id: UUID
    stability_analysis_id: UUID
    selected_run_id: UUID
    evaluation_id: UUID
    # Older persisted gates remain inspectable, but cannot be applied because
    # they did not record an explicit frozen decision-threshold provenance.
    class_threshold_id: UUID | None = None
    decision_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    dataset_fingerprint: str | None = None
    dataset_artifact_sha256: str | None = None
    model_kind: str
    calibration_id: UUID | None = None
    source_split: Literal["validation"] = "validation"
    fit_sample_identity: str
    run_ids: list[UUID] = Field(min_length=3)
    required_run_support: int = Field(default=3, ge=3)
    probability_source: Literal["raw"] = "raw"
    analysis_schema_version: int
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

    @model_validator(mode="before")
    @classmethod
    def _migrate_v1(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        value = dict(value)
        value.setdefault("dataset_fingerprint", None)
        value.setdefault("dataset_artifact_sha256", None)
        value.setdefault("model_kind", "unknown")
        value.setdefault("run_ids", [value["selected_run_id"]] if value.get("selected_run_id") else [])
        # V1 policies are preserved for inspection but do not satisfy the new
        # three-run gate provenance contract.
        value.setdefault("required_run_support", 3)
        value.setdefault("probability_source", "raw")
        value.setdefault("analysis_schema_version", 1)
        # Old gates lacked an explicit threshold and are preserved for
        # inspection only; they cannot satisfy current assurance provenance.
        value.setdefault("class_threshold_id", value.get("threshold_id", None))
        value.setdefault("decision_threshold", None)
        return value


class StabilityGateApplication(BaseModel):
    """A non-tuning application of a frozen Stability Gate to one new case."""

    model_config = ConfigDict(extra="forbid")
    policy_id: UUID
    selected_run_id: UUID
    disposition: Literal["ACCEPT", "REVIEW", "BLOCK"]
    reasons: list[Literal["LOW_CONFIDENCE", "RUN_DISAGREEMENT", "HIGH_DISPERSION", "OUT_OF_SCOPE", "INSUFFICIENT_RUN_SUPPORT"]] = Field(default_factory=list)
    selected_run_probability: float
    predicted_label: int
    confidence: float
    majority_class_agreement: float
    selected_run_agreement: float
    probability_std: float
    run_support_count: int = Field(ge=0)
    run_probabilities: dict[str, float]

    @model_validator(mode="before")
    @classmethod
    def _migrate_support(cls, value: object) -> object:
        if isinstance(value, dict) and "run_support_count" not in value:
            value = dict(value)
            value["run_support_count"] = len(value.get("run_probabilities", {}))
        if isinstance(value, dict) and "selected_run_agreement" not in value:
            value = dict(value)
            legacy = value.pop("class_agreement", 0.0)
            value["majority_class_agreement"] = legacy
            value["selected_run_agreement"] = legacy
        return value
