from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class VerificationBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    bundle_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assurance_id: UUID
    sha256: str
    entry_count: int = Field(ge=1)
    manifest_sha256: str
    inspection_first: bool = True
    excluded: list[str] = Field(default_factory=list)
