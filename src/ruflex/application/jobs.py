from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(BaseModel):
    """Durable local-first job record for non-training product operations."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    job_id: UUID = Field(default_factory=uuid4)
    kind: str
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: str | None = None
    request: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    log: list[str] = Field(default_factory=list)


def _jobs_root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _job_path(project_root: Path, job_id: UUID) -> Path:
    return _jobs_root(project_root) / f"{job_id}.json"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".job-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def persist_job(project_root: Path, job: Job) -> Job:
    _atomic_write(_job_path(project_root, job.job_id), job.model_dump_json(indent=2))
    return job


def load_job(project_root: Path, job_id: UUID) -> Job:
    return Job.model_validate_json(_job_path(project_root, job_id).read_text(encoding="utf-8"))


def list_jobs(project_root: Path, *, kind: str | None = None) -> list[Job]:
    jobs = [Job.model_validate_json(path.read_text(encoding="utf-8")) for path in _jobs_root(project_root).glob("*.json")]
    if kind is not None:
        jobs = [job for job in jobs if job.kind == kind]
    return sorted(jobs, key=lambda job: (job.created_at, str(job.job_id)), reverse=True)
