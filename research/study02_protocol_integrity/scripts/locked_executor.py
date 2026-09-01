"""Resumable locked executor. Pre-unlock it validates only; it never emits outcomes."""
from __future__ import annotations
import argparse
import hashlib
import inspect
import json
from pathlib import Path

from research.study02_protocol_integrity.baselines.basic_manifest_audit import audit as basic_manifest_audit
from research.study02_protocol_integrity.core.execution_contract import ExecutionAttemptContract, PRODUCT_SHA256, RAW_RESULT_FIELDS
from research.study02_protocol_integrity.core.ruflex_subject import execute_attempt
from research.study02_protocol_integrity.core.scenario_materialization import materialize_plan

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'artifacts/manifests/locked_execution_plan.jsonl'
OUTCOMES=ROOT/'artifacts/raw/locked_outcomes.jsonl'
AUTHORIZATION=ROOT.parents[1]/'.agent-state/STUDY02_TEST_AUTHORIZATION.json'

class LockedExecutionForbidden(RuntimeError): pass

def _sha(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def _rows()->list[dict]: return [json.loads(line) for line in PLAN.read_text().splitlines() if line]
def _manifest()->dict: return json.loads((ROOT/'config/locked_suite_manifest.json').read_text())

def _authorization()->dict|None:
 return json.loads(AUTHORIZATION.read_text()) if AUTHORIZATION.exists() else None

def authorization_gate(*,dry_stop:bool=False)->dict:
 manifest=_manifest(); record=_authorization()
 if not record or record.get('authorization_status')!='AUTHORIZED': raise LockedExecutionForbidden('TEST UNLOCK is not authorized by an external matching record.')
 expected={'product_sha':manifest['product_sha256'],'protocol_sha':manifest['protocol_hash'],'manifest_id':manifest['manifest_hash'],'execution_plan_sha':manifest['locked_execution_plan_sha256']}
 if any(record.get(key)!=value for key,value in expected.items()): raise LockedExecutionForbidden('External authorization does not match the frozen identities.')
 return {'authorization':'PASS','dry_stop':dry_stop,**expected}

def validate_plan()->dict:
 manifest=_manifest(); assert manifest['product_sha256']==PRODUCT_SHA256
 assert PLAN.exists(),'locked execution plan is missing'
 rows=_rows(); assert len(rows)==60
 assert {row['family'] for row in rows}=={'V01','V06','V07'}
 assert {family:sum(row['family']==family for row in rows) for family in {'V01','V06','V07'}}=={'V01':20,'V06':20,'V07':20}
 scenarios:set[str]=set()
 for row in rows:
  assert row['actual_product_entrypoint'].startswith('ruflex.application.training.')
  assert row['baseline_plan']['entrypoint'].endswith('basic_manifest_audit.audit')
  assert row['persistence_plan']['required'] is True
  contracts=[ExecutionAttemptContract.from_payload(dict(row[key])) for key in ('clean_execution_contract','corrupt_execution_contract')]
  assert contracts[0].clean_or_corrupt=='clean' and contracts[1].clean_or_corrupt=='corrupt'
  assert contracts[0].pair_id==contracts[1].pair_id==row['pair_id']
  assert contracts[0].violation_family==contracts[1].violation_family==row['family']
  assert contracts[0].contract_hash==row['clean_execution_contract_hash']
  assert contracts[1].contract_hash==row['corrupt_execution_contract_hash']
  assert contracts[0].forbidden_source_roles==contracts[1].forbidden_source_roles==('final_test',)
  materialized=materialize_plan(row)
  assert materialized.input_hash==row['base_input_hash']==contracts[0].base_input_hash==contracts[1].base_input_hash
  assert materialize_plan(row).input_hash==materialized.input_hash
  assert contracts[0].seed==contracts[1].seed==row['seed'] and contracts[0].generator_parameters==row['generator_parameters']
  scenarios.update((contracts[0].scenario_id,contracts[1].scenario_id))
 assert len(scenarios)==120
 assert tuple(inspect.signature(execute_attempt).parameters)==('contract','root','scenario')
 assert tuple(RAW_RESULT_FIELDS) and 'product_outcome' in RAW_RESULT_FIELDS
 return {'status':'PASS','pairs':len(rows),'scenarios':len(scenarios),'plan_sha256':_sha(PLAN),'materialized_inputs':len(rows),'unique_input_hashes':len({materialize_plan(row).input_hash for row in rows}),'executor_locked':_authorization() is None}

def _result_row(*,contract:ExecutionAttemptContract,plan:dict,observed:dict,manifest:dict)->dict:
 alerts=basic_manifest_audit({'final_test_role_used':contract.clean_or_corrupt=='corrupt'})
 return {'study_revision':contract.study_revision,'product_sha':contract.product_sha,'protocol_sha':manifest['protocol_hash'],'manifest_id':manifest['manifest_hash'],'execution_plan_hash':_sha(PLAN),'pair_id':contract.pair_id,'scenario_id':contract.scenario_id,'family':contract.violation_family,'seed':plan['seed'],'clean_or_corrupt':contract.clean_or_corrupt,'product_entrypoint':observed['product_entrypoint'],'requested_data_role':observed['requested_data_role'],'resolved_data_role':observed['resolved_data_role'],'product_outcome':observed['product_outcome'],'product_exception_type':observed['product_exception_type'],'product_exception_message_normalized':observed['product_exception_message_normalized'],'artifact_created':observed['artifact_created'],'artifact_type':observed['artifact_type'],'artifact_id':observed['artifact_id'],'artifact_provenance_hash':observed['artifact_provenance_hash'],'false_block':False,'false_warning':False,'baseline_outcome':'ALERT' if alerts else 'NO_ALERT','baseline_alert_count':len(alerts),'persistence_required':contract.persistence_required,'save_status':observed['save_status'],'reopen_status':observed['reopen_status'],'reopened_artifact_provenance_hash':observed['reopened_artifact_provenance_hash'],'runtime_ms':observed['runtime_ms'],'generator_family':plan['generator_family'],'generator_parameters':plan['generator_parameters'],'execution_contract_hash':contract.contract_hash,'base_input_hash':observed['base_input_hash'],'clean_input_hash':plan['clean_input_hash'],'corrupt_input_hash':plan['corrupt_input_hash'],'action_attempted':contract.operation_role,'invalid_artifact_persisted':False,'failure_class':None}

def run(*,result_root:Path|None=None)->dict:
 manifest=_manifest(); authorization_gate()
 validated=validate_plan(); output=OUTCOMES if result_root is None else Path(result_root)/'locked_outcomes.jsonl'; output.parent.mkdir(parents=True,exist_ok=True)
 existing={json.loads(line)['scenario_id'] for line in output.read_text().splitlines() if line} if output.exists() else set(); emitted=0
 with output.open('a',encoding='utf-8') as handle:
  for plan in _rows():
   for key in ('clean_execution_contract','corrupt_execution_contract'):
    contract=ExecutionAttemptContract.from_payload(dict(plan[key]))
    if contract.scenario_id in existing: continue
    observed=execute_attempt(contract,output.parent/'projects'/contract.scenario_id,materialize_plan(plan))
    row=_result_row(contract=contract,plan=plan,observed=observed,manifest=manifest); assert set(row)==set(RAW_RESULT_FIELDS)
    handle.write(json.dumps(row,sort_keys=True)+'\n');handle.flush();emitted+=1
 return {**validated,'emitted':emitted,'outcomes_path':str(output)}

def main()->None:
 parser=argparse.ArgumentParser();parser.add_argument('--validate-plan',action='store_true');parser.add_argument('--validate-authorization',action='store_true');args=parser.parse_args()
 if args.validate_plan: print(json.dumps(validate_plan(),sort_keys=True));return
 if args.validate_authorization: print(json.dumps(authorization_gate(dry_stop=True),sort_keys=True));return
 print(json.dumps(run(),sort_keys=True))
if __name__=='__main__': main()
