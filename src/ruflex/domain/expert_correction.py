from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from ruflex.domain.fis import FISSpec


class ExpertCorrectionRevision(BaseModel):
    """Audit record for a bounded expert-guided Sugeno consequent refit.

    The fuzzy antecedent structure and membership functions remain fixed. Rule
    consequents explicitly selected as locked remain unchanged. Only the
    remaining Sugeno consequents are fitted on the TRAIN partition.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 2
    correction_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fis_id: UUID
    source_semantic_hash: str
    result_semantic_hash: str
    dataset_fingerprint: str
    target: str
    split_seed: int
    validation_fraction: float
    test_fraction: float
    train_row_count: int
    skipped_row_count: int = 0
    locked_rule_ids: list[UUID] = Field(default_factory=list)
    fitted_rule_ids: list[UUID] = Field(default_factory=list)
    source_explanation_id: UUID | None = None
    train_rmse_before: float
    train_rmse_after: float
    validation_row_count: int = 0
    validation_rmse_before: float | None = None
    validation_rmse_after: float | None = None
    fit_method: str = "train_only_weighted_least_squares_sugeno_consequents"
    test_status: str = "LOCKED_NOT_EVALUATED"
    scientific_note: str = (
        "Expert correction keeps the fuzzy antecedent structure fixed and refits only unlocked Sugeno consequents on TRAIN. "
        "Validation and final-test rows are not used by this correction fit. "
        "Validation may be evaluated after fitting as before/after evidence; final test remains locked."
    )


class ExpertCorrectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correction: ExpertCorrectionRevision
    fis: FISSpec
