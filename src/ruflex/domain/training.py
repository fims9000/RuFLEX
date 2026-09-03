from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EpochPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    epoch: int
    train_loss: float
    validation_loss: float | None = None
    train_metrics: dict[str, float] = Field(default_factory=dict)
    validation_metrics: dict[str, float] | None = None


class SplitProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: Literal["random_holdout"] = "random_holdout"
    # `seed` is retained for RC2.1 project compatibility.  New objects record
    # the seed that controls membership explicitly as `split_seed`.
    seed: int
    split_seed: int | None = None
    split_identity: str | None = None
    validation_fraction: float
    test_fraction: float
    train_count: int
    validation_count: int
    test_count: int
    preprocessing_fit_scope: Literal["train_only"] = "train_only"
    test_status: Literal["LOCKED_NOT_EVALUATED"] = "LOCKED_NOT_EVALUATED"

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_seed(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("split_seed") is None and value.get("seed") is not None:
            value = dict(value)
            value["split_seed"] = value["seed"]
        return value


class PredictionRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row: int
    source_row: int | None = None
    target: float
    prediction: float
    probability: float | None = None
    calibrated_probability: float | None = None
    predicted_label: int | None = None
    residual: float | None = None


class ConfusionMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    true_negative: int
    false_positive: int
    false_negative: int
    true_positive: int


class CalibrationBin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lower: float
    upper: float
    count: int
    mean_probability: float
    observed_positive_rate: float


class TrainingRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 2
    run_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["succeeded"] = "succeeded"
    model_kind: Literal["flat_neuro_fuzzy", "logistic_regression", "linear_regression", "decision_tree", "random_forest", "gradient_boosting"] = "flat_neuro_fuzzy"
    task: Literal["regression", "binary_classification"]
    target: str
    dataset_fingerprint: str | None = None
    dataset_artifact_sha256: str | None = None
    feature_columns: list[str]
    # Legacy compatibility alias.  For new runs it equals training_seed.
    seed: int
    split_seed: int | None = None
    training_seed: int | None = None
    randomness_protocol: Literal["LEGACY_COMBINED", "SINGLE_RUN_EXPLICIT", "TRAINING_VARIABILITY", "SPLIT_VARIABILITY", "COMBINED_VARIABILITY"] = "LEGACY_COMBINED"
    max_epochs: int
    learning_rate: float
    batch_size: int
    patience: int | None
    split: SplitProvenance
    model_spec: dict
    normalization: dict
    training_summary: dict
    trajectory: list[EpochPoint]
    validation_metrics: dict[str, float]
    prediction_preview: list[PredictionRow]
    confusion_matrix: ConfusionMatrix | None = None
    calibration: list[CalibrationBin] = Field(default_factory=list)
    model_artifact_sha256: str
    runtime_seconds: float = Field(default=0.0, ge=0.0)
    evaluation_split: Literal["validation"] = "validation"
    scientific_note: str = (
        "Metrics shown here are validation metrics. The held-out test split remains locked and is not used for model selection."
    )

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_randomness(cls, value: object) -> object:
        if isinstance(value, dict):
            value = dict(value)
            legacy = value.get("seed")
            if value.get("split_seed") is None:
                value["split_seed"] = legacy
            if value.get("training_seed") is None:
                value["training_seed"] = legacy
            if "randomness_protocol" not in value:
                value["randomness_protocol"] = "LEGACY_COMBINED"
        return value


class TrainingStudy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 2
    study_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    name: str
    model_kind: Literal["flat_neuro_fuzzy", "logistic_regression", "linear_regression", "decision_tree", "random_forest", "gradient_boosting"] = "flat_neuro_fuzzy"
    task: Literal["regression", "binary_classification"]
    selection_metric: str
    selection_split: Literal["validation"] = "validation"
    selection_rule: Literal["max", "min"]
    seed_runs: list[TrainingRun]
    selected_run_id: UUID
    selection_reason: str
    randomness_protocol: Literal["LEGACY_COMBINED", "TRAINING_VARIABILITY", "SPLIT_VARIABILITY", "COMBINED_VARIABILITY"] = "LEGACY_COMBINED"
    split_seed: int | None = None
    training_seeds: list[int] = Field(default_factory=list)


class StudySeedState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int
    split_seed: int | None = None
    training_seed: int | None = None
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"] = "QUEUED"
    run_id: UUID | None = None
    runtime_seconds: float | None = None
    error: str | None = None


class StudyJob(BaseModel):
    """Durable asynchronous execution state for a multi-seed Study."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 3
    job_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    name: str
    model_kind: Literal["flat_neuro_fuzzy", "logistic_regression", "linear_regression", "decision_tree", "random_forest", "gradient_boosting"] = "flat_neuro_fuzzy"
    selection_metric: str
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"] = "QUEUED"
    cancel_requested: bool = False
    seed_states: list[StudySeedState]
    randomness_protocol: Literal["LEGACY_COMBINED", "TRAINING_VARIABILITY", "SPLIT_VARIABILITY", "COMBINED_VARIABILITY"] = "LEGACY_COMBINED"
    split_seed: int | None = None
    study_id: UUID | None = None
    error: str | None = None
    execution_backend: Literal["LOCAL"] = "LOCAL"
    execution_config: dict[str, int | float | str | bool | None] = Field(default_factory=dict)
    recovery_count: int = Field(default=0, ge=0)
    recovery_note: str | None = None


class CalibrationProvenance(BaseModel):
    """Describes what the calibration view is, without overstating it as calibration."""

    model_config = ConfigDict(extra="forbid")

    method: Literal["validation_reliability_bins", "platt_scaling"] = "validation_reliability_bins"
    fit_scope: Literal["not_fitted", "validation_only"] = "not_fitted"
    status: Literal["DESCRIPTIVE_NOT_CALIBRATED", "FITTED_VALIDATION_ONLY"] = "DESCRIPTIVE_NOT_CALIBRATED"
    bin_count: int = Field(ge=0)
    parameters: dict[str, float] = Field(default_factory=dict)
    fit_sample_identity: str | None = None


class ThresholdProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_split: Literal["validation"] = "validation"
    objective: Literal["f1"] = "f1"
    candidate_rule: str = "thresholds 0.01 through 0.99"
    selected_threshold: float = Field(ge=0.0, le=1.0)
    selection_result: float
    probability_source: Literal["raw", "calibrated"] = "raw"
    fit_sample_identity: str | None = None


class CalibratedPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row: int
    target: float
    raw_probability: float
    calibrated_probability: float


class CalibrationTransform(BaseModel):
    """Persisted validation-derived probability transform.

    This object is deliberately separate from the immutable Evaluation.  Its
    provenance makes it explicit that fitting and descriptive calibration
    diagnostics were performed on validation data, never on the protected
    final-test split.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    calibration_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluation_id: UUID
    run_id: UUID
    method: Literal["platt_scaling"] = "platt_scaling"
    source_split: Literal["validation"] = "validation"
    test_status: Literal["LOCKED_NOT_EVALUATED"] = "LOCKED_NOT_EVALUATED"
    input_kind: Literal["model_logit"] = "model_logit"
    fit_sample_count: int = Field(ge=1)
    fit_sample_identity: str
    coefficient: float
    intercept: float
    brier_before: float
    brier_after: float
    ece_before: float
    ece_after: float
    calibration_bins: list[CalibrationBin] = Field(default_factory=list)
    predictions: list[CalibratedPrediction] = Field(default_factory=list)
    scientific_note: str = (
        "The calibration transform was fitted on validation data only. "
        "Its validation diagnostics are descriptive and are not final-test estimates."
    )


class ThresholdDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row: int
    target: int
    probability: float
    predicted_label: int


class DecisionThresholdPolicy(BaseModel):
    """Persisted validation-only decision threshold and its selection evidence."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    threshold_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluation_id: UUID
    run_id: UUID
    calibration_id: UUID | None = None
    source_split: Literal["validation"] = "validation"
    test_status: Literal["LOCKED_NOT_EVALUATED"] = "LOCKED_NOT_EVALUATED"
    objective: Literal["f1"] = "f1"
    probability_source: Literal["raw", "calibrated"] = "raw"
    candidate_rule: str
    selected_threshold: float = Field(ge=0.0, le=1.0)
    selection_result: float
    fit_sample_identity: str
    metrics: dict[str, float]
    confusion_matrix: ConfusionMatrix
    decisions: list[ThresholdDecision] = Field(default_factory=list)
    scientific_note: str = (
        "The decision threshold was selected on validation data only. "
        "The held-out final test remained locked and was not used for threshold selection."
    )


class AnalysisEvaluation(BaseModel):
    """Immutable, run-bound validation analysis object for the Studio."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    evaluation_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: UUID
    task: Literal["regression", "binary_classification"]
    target: str
    model_kind: str | None = None
    model_artifact_sha256: str | None = None
    dataset_fingerprint: str | None = None
    dataset_artifact_sha256: str | None = None
    preprocessing_identity: str | None = None
    split: Literal["validation"] = "validation"
    test_status: Literal["LOCKED_NOT_EVALUATED"] = "LOCKED_NOT_EVALUATED"
    metrics: dict[str, float]
    prediction_preview: list[PredictionRow]
    validation_row_count: int = Field(default=0, ge=0)
    confusion_matrix: ConfusionMatrix | None = None
    calibration: CalibrationProvenance
    calibration_bins: list[CalibrationBin] = Field(default_factory=list)
    threshold: ThresholdProvenance | None = None
    scientific_note: str = (
        "This is a validation analysis object. The held-out final test split remains locked and was not used for selection."
    )


class FinalTestEvaluation(BaseModel):
    """Explicit, immutable evaluation of the previously locked final-test split.

    The object records which validation-derived calibration/threshold policy was
    frozen before test access. It never contains fitting or selection state.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 2
    final_test_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: UUID
    evaluation_id: UUID
    task: Literal["regression", "binary_classification"]
    target: str
    model_kind: str
    model_artifact_sha256: str
    dataset_fingerprint: str
    dataset_artifact_sha256: str
    preprocessing_identity: str
    split: Literal["test"] = "test"
    status: Literal["FINAL_TEST_EVALUATED"] = "FINAL_TEST_EVALUATED"
    calibration_id: UUID | None = None
    threshold_id: UUID | None = None
    selective_policy_id: UUID | None = None
    stability_gate_policy_id: UUID | None = None
    stability_gate_evidence: "FinalTestStabilityEvidence | None" = None
    probability_source: Literal["not_applicable", "raw", "calibrated"] = "not_applicable"
    decision_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    metrics: dict[str, float]
    prediction_rows: list[PredictionRow]
    test_row_count: int = Field(ge=1)
    confusion_matrix: ConfusionMatrix | None = None
    calibration_bins: list[CalibrationBin] = Field(default_factory=list)
    test_sample_identity: str
    test_case_identity: str | None = None
    policy_identity: str
    policy_frozen_at: datetime | None = None
    dataset_test_unlock_at: datetime | None = None
    scientific_note: str = (
        "This object is the explicit final-test evaluation of a policy frozen before final-test access. "
        "No fitting, calibration fitting, threshold selection, or model selection is performed on final-test data. "
        "Additional pre-frozen policies may be evaluated only on the same frozen final-test cases; policies created after first access are blocked."
    )


class FinalTestStabilityCase(BaseModel):
    """Frozen, non-tuning application of one Stability Gate final-test case."""

    model_config = ConfigDict(extra="forbid")
    case_id: str
    source_row: int
    target: int
    selected_run_probability: float
    selected_run_class: int
    majority_class_agreement: float = Field(ge=0.0, le=1.0)
    selected_run_agreement: float = Field(ge=0.0, le=1.0)
    probability_std: float = Field(ge=0.0)
    disposition: Literal["ACCEPT", "REVIEW", "BLOCK"]
    reasons: list[Literal["LOW_CONFIDENCE", "RUN_DISAGREEMENT", "HIGH_DISPERSION", "OUT_OF_SCOPE", "INSUFFICIENT_RUN_SUPPORT"]] = Field(default_factory=list)


class FinalTestStabilityEvidence(BaseModel):
    """Evaluation-only evidence from a policy frozen before test unlock."""

    model_config = ConfigDict(extra="forbid")
    policy_id: UUID
    class_threshold_id: UUID
    decision_threshold: float = Field(ge=0.0, le=1.0)
    run_ids: list[UUID] = Field(min_length=3)
    cases: list[FinalTestStabilityCase]
    accepted_count: int = Field(ge=0)
    review_count: int = Field(ge=0)
    block_count: int = Field(ge=0)
    coverage: float = Field(ge=0.0, le=1.0)
    accepted_error: float | None = None
    accepted_false_negative_count: int = Field(ge=0)
    accepted_false_negative_rate: float | None = None
    confidence_only_accepted_error: float | None = None
    confidence_only_accepted_count: int = Field(ge=0)
    scientific_note: str = "Frozen policy application only; no final-test fitting, selection, or threshold adjustment occurred."


class AnalysisComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 2
    comparison_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    task: Literal["regression", "binary_classification"]
    target: str
    split: Literal["validation"] = "validation"
    run_ids: list[UUID] = Field(min_length=2)
    dataset_fingerprint: str | None = None
    validation_alignment: Literal["same_cases", "mixed_cases", "unknown"] = "unknown"
    validation_sample_identities: dict[str, str] = Field(default_factory=dict)
    fis_id: UUID | None = None
    fis_semantic_hash: str | None = None
    metric_rows: list[dict[str, float | str]]
    scientific_note: str = "Comparison is validation-only. Locked final test data are not included."


class TreePathStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: int
    feature_name: str
    threshold: float
    value: float
    decision: Literal["left", "right"]


class TreePathEvidence(BaseModel):
    """Exact deterministic execution path of a persisted declarative tree."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    evidence_id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    model_artifact_sha256: str
    preprocessing_identity: str
    input_sample: dict[str, float]
    steps: list[TreePathStep]
    leaf_id: int
    prediction: float
    class_probabilities: dict[str, float] | None = None
    label: Literal["EXACT TREE EXECUTION PATH"] = "EXACT TREE EXECUTION PATH"
