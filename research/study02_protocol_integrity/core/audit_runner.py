"""Invoke only real subject adapter outcomes; never interpret planted markers."""
from __future__ import annotations
from pathlib import Path
import json
from research.study02_protocol_integrity.core.execution_contract import ExecutionAttemptContract
from research.study02_protocol_integrity.core.ruflex_subject import execute_attempt
from research.study02_protocol_integrity.core.scenario_materialization import materialize_plan
def exercise_preventable(family:str, root:Path)->dict:
 root_plan=Path(__file__).resolve().parents[1]/'artifacts/manifests/locked_execution_plan.jsonl'
 plan=next(json.loads(line) for line in root_plan.read_text().splitlines() if json.loads(line)['family']==family)
 contract=ExecutionAttemptContract.from_payload(dict(plan['clean_execution_contract']))
 result=execute_attempt(contract,root,materialize_plan(plan)); result['entry_point']=result['product_entrypoint']; return result
