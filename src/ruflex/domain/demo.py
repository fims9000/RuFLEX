from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field

class ConditionMonitoringDemo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    demo_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    policy_id: UUID
    telemetry: dict[str, float]
    predicted_class: int
    probability: float
    confidence: float
    decision: Literal["ACCEPT", "REVIEW", "OUT_OF_SCOPE"]
    scope_disposition: str
    explanation_id: UUID | None = None
    explanation_check_id: UUID | None = None
    assurance_id: UUID | None = None
    verification_bundle_sha256: str | None = None
    explanation_note: str = "Use persisted explanation evidence for engineering review; no actuator command is produced."
    safety_note: str = "Condition-monitoring decision support only. No targeting, weapon engagement, or autonomous control command."
