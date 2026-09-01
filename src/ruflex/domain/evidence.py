from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class FeatureAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature: str
    observed_value: float
    reference_value: float
    attribution: float
    occluded_prediction: float | None = None


class ExplanationContract(BaseModel):
    """Persisted post-hoc explanation with explicit epistemic boundaries."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    explanation_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: UUID
    model_kind: str
    model_artifact_sha256: str
    preprocessing_identity: str | None = None
    sample_identity: str | None = None
    reference_identity: str | None = None
    sample: dict[str, float]
    target: str
    scope: Literal["local_sample"] = "local_sample"
    family: Literal["occlusion", "integrated_gradients", "gradient_shap", "shap", "tree_shap"] = "occlusion"
    method: Literal["train_reference_occlusion", "integrated_gradients_train_reference", "gradient_shap_train_background", "permutation_shap_train_background", "tree_shap_train_background"] = "train_reference_occlusion"
    epistemic_category: Literal["POST-HOC ATTRIBUTION"] = "POST-HOC ATTRIBUTION"
    exactness: Literal["post_hoc"] = "post_hoc"
    prediction: float
    output_space: Literal["prediction", "probability", "raw_score"] = "prediction"
    base_value: float | None = None
    completeness_error: float | None = None
    reference_definition: str
    feature_representation: str = "raw DatasetContract feature values"
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    attributions: list[FeatureAttribution]
    scientific_note: str = (
        "Occlusion measures prediction change after replacing one feature with a train-derived reference. "
        "It is post-hoc attribution, not an exact computation trace and not a causal effect."
    )


class ExplanationCheckItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: Literal["PASS", "WARN", "FAIL", "N/A"]
    detail: str


class ExplanationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    check_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    explanation_id: UUID
    run_id: UUID
    status: Literal["PASSED_AVAILABLE_CHECKS", "WARNING", "FAILED"]
    checks: list[ExplanationCheckItem]
    scientific_note: str = (
        "Checks validate available technical invariants of this explanation. "
        "They do not establish causal correctness or universal explanation quality."
    )


class ExplanationPairwiseAgreement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left_run_id: UUID
    right_run_id: UUID
    prediction_mean_absolute_difference: float
    prediction_class_agreement: float | None = Field(default=None, ge=0.0, le=1.0)
    explanation_spearman: float | None = Field(default=None, ge=-1.0, le=1.0)
    explanation_sign_agreement: float = Field(ge=0.0, le=1.0)
    top_k_overlap: float = Field(ge=0.0, le=1.0)
    case_count: int = Field(ge=1)


class FeatureExplanationVariability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feature: str
    mean_attribution: float
    standard_deviation: float = Field(ge=0.0)
    sign_agreement: float = Field(ge=0.0, le=1.0)


class ExplanationReproducibilityAnalysis(BaseModel):
    """Cross-run post-hoc reproducibility; predictive and explanatory agreement stay separate."""
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    analysis_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_ids: list[UUID] = Field(min_length=2)
    explanation_ids: list[UUID] = Field(min_length=4)
    task: str
    target: str
    dataset_fingerprint: str
    validation_case_identities: list[str] = Field(min_length=1)
    explanation_method: str
    reference_protocol: str
    prediction_agreement: dict[str, float]
    explanation_agreement: dict[str, float]
    pairwise: list[ExplanationPairwiseAgreement] = Field(min_length=1)
    per_feature_variability: list[FeatureExplanationVariability] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
    scientific_note: str = (
        "Prediction agreement and post-hoc explanation agreement are measured separately. "
        "Stable predictions do not establish stable explanations."
    )
