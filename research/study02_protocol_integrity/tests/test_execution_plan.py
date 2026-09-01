import json
from pathlib import Path

import pytest

from research.study02_protocol_integrity.core.execution_contract import ExecutionAttemptContract, RAW_RESULT_FIELDS
from research.study02_protocol_integrity.core.ruflex_subject import execute_attempt
from research.study02_protocol_integrity.core.scenario_materialization import materialize_plan
from research.study02_protocol_integrity.scripts.locked_executor import LockedExecutionForbidden, run, validate_plan

ROOT=Path(__file__).resolve().parents[1]

def plans(): return [json.loads(line) for line in (ROOT/'artifacts/manifests/locked_execution_plan.jsonl').read_text().splitlines()]

def test_locked_executor_plan_contains_60_pairs():
 assert validate_plan()['pairs']==60

def test_locked_plan_has_20_pairs_per_supported_family():
 rows=plans(); assert {family:sum(r['family']==family for r in rows) for family in ('V01','V06','V07')}=={'V01':20,'V06':20,'V07':20}

def test_every_pair_has_two_execution_contracts():
 for plan in plans():
  clean=ExecutionAttemptContract.from_payload(plan['clean_execution_contract']); corrupt=ExecutionAttemptContract.from_payload(plan['corrupt_execution_contract'])
  assert clean.clean_or_corrupt=='clean' and corrupt.clean_or_corrupt=='corrupt' and clean.pair_id==corrupt.pair_id

def test_execution_contract_reaches_real_product_entrypoint(tmp_path):
 plan=plans()[0]; contract=ExecutionAttemptContract.from_payload(plan['clean_execution_contract'])
 outcome=execute_attempt(contract,tmp_path/'project',materialize_plan(plan))
 assert outcome['product_entrypoint']==contract.expected_product_entrypoint and outcome['product_outcome']=='ALLOWED_VALID'

def test_v01_clean_uses_train_only_preprocessing_and_corrupt_is_structurally_unexpressible(tmp_path):
 plan=next(row for row in plans() if row['family']=='V01')
 clean=execute_attempt(ExecutionAttemptContract.from_payload(plan['clean_execution_contract']),tmp_path/'clean',materialize_plan(plan))
 corrupt=execute_attempt(ExecutionAttemptContract.from_payload(plan['corrupt_execution_contract']),tmp_path/'corrupt',materialize_plan(plan))
 assert clean['resolved_data_role']=='train' and corrupt['product_outcome']=='PREVENTED_STRUCTURALLY' and corrupt['resolved_data_role']=='train'

@pytest.mark.parametrize('family',('V06','V07'))
def test_final_test_attempt_is_rejected_by_product(family,tmp_path):
 plan=next(row for row in plans() if row['family']==family)
 clean=execute_attempt(ExecutionAttemptContract.from_payload(plan['clean_execution_contract']),tmp_path/'clean',materialize_plan(plan))
 corrupt=execute_attempt(ExecutionAttemptContract.from_payload(plan['corrupt_execution_contract']),tmp_path/'corrupt',materialize_plan(plan))
 assert clean['product_outcome']=='ALLOWED_VALID' and clean['artifact_created'] is True
 assert corrupt['product_outcome']=='PREVENTED_BY_FIREWALL' and corrupt['artifact_created'] is False and corrupt['product_exception_type']

def test_prevented_is_not_labeled_detected_and_persistence_is_present(tmp_path):
 plan=next(row for row in plans() if row['family']=='V06')
 result=execute_attempt(ExecutionAttemptContract.from_payload(plan['corrupt_execution_contract']),tmp_path/'project',materialize_plan(plan))
 assert result['product_outcome']=='PREVENTED_BY_FIREWALL' and result['reopen_status']=='PASS'

def test_raw_schema_complete_and_executor_requires_authorization(tmp_path,monkeypatch):
 assert 'product_outcome' in RAW_RESULT_FIELDS and 'oracle_reference_id' not in RAW_RESULT_FIELDS
 monkeypatch.setattr('research.study02_protocol_integrity.scripts.locked_executor.AUTHORIZATION',tmp_path/'missing.json')
 with pytest.raises(LockedExecutionForbidden): run()

def test_dry_validator_does_not_execute_locked_outcomes():
 raw=ROOT/'artifacts/raw/locked_outcomes.jsonl'; before=raw.read_bytes() if raw.exists() else None
 result=validate_plan()
 assert result['status']=='PASS' and (raw.read_bytes() if raw.exists() else None)==before

def test_pair_plans_do_not_prefill_observed_results():
 forbidden={'product_outcome','artifact_created','product_exception_type','baseline_outcome','runtime_ms'}
 assert all(not (set(row)&forbidden) for row in plans())

def test_basic_manifest_audit_is_independent_from_product_services():
 text=(ROOT/'baselines/basic_manifest_audit.py').read_text().lower()
 assert 'import ruflex' not in text and 'from ruflex' not in text and 'execute_attempt' not in text

def test_generic_10_of_10_report_is_superseded_and_native_dev_is_product_backed():
 historical=json.loads((ROOT/'artifacts/aggregated/dev_report.json').read_text()); native=json.loads((ROOT/'artifacts/aggregated/dev_native_report.json').read_text())
 assert historical['status']=='SUPERSEDED_HARNESS_ONLY' and native['status']=='PRODUCT_BACKED_DEV' and native['rows']==18
