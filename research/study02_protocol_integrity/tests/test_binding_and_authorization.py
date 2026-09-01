import hashlib
import json
from pathlib import Path

import pytest

from research.study02_protocol_integrity.core.execution_contract import ExecutionAttemptContract
from research.study02_protocol_integrity.core.scenario_materialization import materialize_plan
from research.study02_protocol_integrity.scripts import locked_executor

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]

def plans(): return [json.loads(line) for line in (ROOT/'artifacts/manifests/locked_execution_plan.jsonl').read_text().splitlines()]

def test_same_plan_materializes_identically_and_different_seed_changes_input():
 first=plans()[0]; same_a=materialize_plan(first); same_b=materialize_plan(first)
 changed=dict(first); changed['seed']+=1; changed['generator_parameters']=dict(changed['generator_parameters']); changed['generator_parameters']['seed']=changed['seed']
 assert same_a.input_hash==same_b.input_hash and same_a.input_hash!=materialize_plan(changed).input_hash

def test_all_frozen_pairs_bind_seed_parameters_and_identical_pair_base_input():
 rows=plans(); assert len(rows)==60
 hashes=[]
 for row in rows:
  materialized=materialize_plan(row); hashes.append(materialized.input_hash)
  clean=ExecutionAttemptContract.from_payload(dict(row['clean_execution_contract'])); corrupt=ExecutionAttemptContract.from_payload(dict(row['corrupt_execution_contract']))
  assert materialized.input_hash==row['base_input_hash']==row['clean_input_hash']==row['corrupt_input_hash']==clean.base_input_hash==corrupt.base_input_hash
  assert clean.seed==row['seed'] and clean.generator_parameters==row['generator_parameters']
 assert len(set(hashes))==60

def test_changed_seed_or_generator_parameters_changes_plan_identity():
 row=plans()[0]; original=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 changed=dict(row); changed['seed']+=1; changed['generator_parameters']=dict(changed['generator_parameters']); changed['generator_parameters']['seed']=changed['seed']
 replacement=hashlib.sha256(json.dumps(changed,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 assert original!=replacement

def _record(manifest, **overrides):
 value={'study':'Study 02 — Protocol Integrity','authorization_status':'AUTHORIZED','product_sha':manifest['product_sha256'],'protocol_sha':manifest['protocol_hash'],'manifest_id':manifest['manifest_hash'],'execution_plan_sha':manifest['locked_execution_plan_sha256'],'authorized_at':'PRE_TEST_DRY_FIXTURE','authorization_note':'test'}; value.update(overrides); return value

@pytest.mark.parametrize('field',('manifest_id','protocol_sha','product_sha','execution_plan_sha'))
def test_authorization_identity_mismatch_refuses(tmp_path,monkeypatch,field):
 manifest=json.loads((ROOT/'config/locked_suite_manifest.json').read_text()); auth=tmp_path/'authorization.json'; auth.write_text(json.dumps(_record(manifest,**{field:'wrong'})))
 monkeypatch.setattr(locked_executor,'AUTHORIZATION',auth)
 with pytest.raises(locked_executor.LockedExecutionForbidden): locked_executor.authorization_gate(dry_stop=True)

def test_no_authorization_refuses_and_matching_external_record_passes_without_outcomes(tmp_path,monkeypatch):
 manifest_path=ROOT/'config/locked_suite_manifest.json'; plan_path=ROOT/'artifacts/manifests/locked_execution_plan.jsonl'; protocol_path=ROOT/'PROTOCOL.md'; before=(hashlib.sha256(manifest_path.read_bytes()).hexdigest(),hashlib.sha256(plan_path.read_bytes()).hexdigest(),hashlib.sha256(protocol_path.read_bytes()).hexdigest())
 auth=tmp_path/'authorization.json'; monkeypatch.setattr(locked_executor,'AUTHORIZATION',auth)
 with pytest.raises(locked_executor.LockedExecutionForbidden): locked_executor.authorization_gate(dry_stop=True)
 manifest=json.loads(manifest_path.read_text()); auth.write_text(json.dumps(_record(manifest)))
 assert locked_executor.authorization_gate(dry_stop=True)['authorization']=='PASS'
 after=(hashlib.sha256(manifest_path.read_bytes()).hexdigest(),hashlib.sha256(plan_path.read_bytes()).hexdigest(),hashlib.sha256(protocol_path.read_bytes()).hexdigest())
 assert before==after

def test_no_fixed_scientific_seed_in_subject_adapter():
 text=(ROOT/'core/ruflex_subject.py').read_text()
 assert 'seed=29' not in text and 'seed=31' not in text
