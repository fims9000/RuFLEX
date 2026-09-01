from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(BaseModel):
    """Minimal canonical job record; scheduling is added in a later slice."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID = Field(default_factory=uuid4)
    kind: str
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: str | None = None
