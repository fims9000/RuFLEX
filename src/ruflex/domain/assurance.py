from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field
class AssuranceGate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    key:str; status:Literal["PASS","WARN","FAIL","NOT_AVAILABLE"]; evidence:list[str]=Field(default_factory=list); risk:str|None=None
class AssuranceCase(BaseModel):
    model_config=ConfigDict(extra="forbid")
    schema_version:int=1; assurance_id:UUID=Field(default_factory=uuid4); created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc)); gates:list[AssuranceGate]; unresolved_risks:list[str]=Field(default_factory=list); scientific_note:str="Independent evidence gates are not a scalar trust score."
