from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
class AssuranceGate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    key:str; status:Literal["PASS","WARN","FAIL","NOT_AVAILABLE"]; evidence:list[str]=Field(default_factory=list); risk:str|None=None


class AssuranceClaim(BaseModel):
    """A qualified claim with explicit persisted evidence and boundaries."""

    model_config=ConfigDict(extra="forbid")
    claim_id: UUID = Field(default_factory=uuid4)
    statement: str = Field(min_length=1)
    status: Literal["SUPPORTED", "QUALIFIED", "UNSUPPORTED"]
    evidence_ids: list[str] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_is_explicit(self) -> "AssuranceClaim":
        if any(not evidence.strip() for evidence in self.evidence_ids):
            raise ValueError("Assurance claims require non-empty evidence identities.")
        return self
class AssuranceCase(BaseModel):
    model_config=ConfigDict(extra="forbid")
    schema_version:int=2; assurance_id:UUID=Field(default_factory=uuid4); created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc)); gates:list[AssuranceGate]; claims:list[AssuranceClaim]=Field(default_factory=list); unresolved_risks:list[str]=Field(default_factory=list); scientific_note:str="Independent evidence gates and qualified claims are not a scalar trust score."
