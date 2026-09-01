from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field

class ExhaustiveLabResult(BaseModel):
    model_config=ConfigDict(extra="forbid")
    schema_version:int=1
    result_id:UUID=Field(default_factory=uuid4)
    created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))
    kind:Literal["decision_tree_structure","fis_discrete_grid"]
    exactness_label:Literal["EXACT_FINITE_STRUCTURE","EXACT_ON_DECLARED_DISCRETE_GRID"]
    run_id:UUID|None=None
    fis_semantic_hash:str|None=None
    declared_grid:dict[str,list[float]]=Field(default_factory=dict)
    state_count:int=Field(ge=0)
    state_estimate:int=Field(ge=0)
    max_states:int=Field(ge=1)
    paths:list[dict]=Field(default_factory=list)
    uncovered_states:list[dict]=Field(default_factory=list)
    dead_rules:list[str]=Field(default_factory=list)
    conflict_states:list[dict]=Field(default_factory=list)
    scientific_note:str
