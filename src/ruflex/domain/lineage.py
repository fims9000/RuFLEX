from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


WorkbenchTarget = Literal["PROJECT", "DATA", "MODELS", "STUDIES", "ANALYSES", "EVIDENCE"]


class LineageNode(BaseModel):
    """One persisted RuFLEX project object exposed in the provenance graph."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    label: str = Field(min_length=1)
    detail: str | None = None
    target: WorkbenchTarget
    object_id: str | None = None
    status: str | None = None


class LineageEdge(BaseModel):
    """A provenance relation that exists in persisted project metadata."""

    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    relation: str = Field(min_length=1)


class LineageGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    nodes: list[LineageNode] = Field(default_factory=list)
    edges: list[LineageEdge] = Field(default_factory=list)
    scientific_note: str = (
        "Project Lineage is reconstructed only from persisted RuFLEX object references. "
        "Missing edges are left unknown rather than inferred from temporal proximity."
    )
