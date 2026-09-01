from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


PROJECT_SCHEMA_VERSION = 1
ROOT_FORMAT_VERSION = 1
OBJECT_STORE_VERSION = 1
PROJECT_DIRECTORY_NAMES = (
    "data",
    "models",
    "studies",
    "runs",
    "explanations",
    "tests",
    "reports",
    "artifacts",
    "provenance",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectManifest(BaseModel):
    """Safe, declarative identity record for a RuFLEX Studio workspace."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = PROJECT_SCHEMA_VERSION
    project_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    created_at: datetime = Field(default_factory=utc_now)
    modified_at: datetime = Field(default_factory=utc_now)
    root_format_version: int = ROOT_FORMAT_VERSION
    object_store_version: int = OBJECT_STORE_VERSION
    active_generalization_contract_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    name: str
    description: str | None
    root: Path
    schema_version: int
    read_only: bool
    modified_at: datetime


class Project(BaseModel):
    """Runtime handle over the canonical declarative project manifest."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    root: Path
    manifest: ProjectManifest
    read_only: bool = False

    @property
    def id(self) -> UUID:
        return self.manifest.project_id

    def summary(self) -> ProjectSummary:
        return ProjectSummary(
            project_id=self.id,
            name=self.manifest.name,
            description=self.manifest.description,
            root=self.root,
            schema_version=self.manifest.schema_version,
            read_only=self.read_only,
            modified_at=self.manifest.modified_at,
        )
