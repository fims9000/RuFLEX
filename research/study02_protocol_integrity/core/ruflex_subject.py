"""Adapter to frozen RuFLEX V1.0.1 services, without research-side detection."""
from __future__ import annotations
import hashlib
import time
from uuid import uuid4
from pathlib import Path
import pandas as pd
from ruflex.application.projects import ProjectService
from ruflex.application.datasets import persist_dataset_bytes,inspect_dataset,build_dataset_contract,persist_dataset_contract,run_data_audit
from ruflex.application.training import train_model,create_validation_evaluation,select_validation_threshold,fit_validation_calibration,evaluate_final_test
from research.study02_protocol_integrity.core.execution_contract import ExecutionAttemptContract
from research.study02_protocol_integrity.core.scenario_materialization import ScenarioExecutionInput

def make_project(root:Path,*,scenario:ScenarioExecutionInput,seed:int):
 ProjectService().create(root,name='Study02 actual product subject')
 frame=scenario.frame.copy()
 ref=persist_dataset_bytes(root,frame.to_csv(index=False).encode(),original_name='subject.csv')
 profile=inspect_dataset(frame,source_artifact_sha256=ref.sha256); contract=build_dataset_contract(profile,target='target',task='binary_classification');persist_dataset_contract(root,contract,run_data_audit(contract,frame),profile)
 run=train_model(root,model_kind='logistic_regression',seed=seed,max_epochs=1,learning_rate=.01,batch_size=16,patience=1,validation_fraction=.2,test_fraction=.2,max_rules=3)
 evaluation=create_validation_evaluation(root,run.run_id)
 return run,evaluation


def _hash(value: object) -> str:
 return hashlib.sha256(str(value).encode()).hexdigest()


def execute_attempt(contract: ExecutionAttemptContract, root: Path, scenario: ScenarioExecutionInput) -> dict:
 """Execute one contract through the real frozen application services only.

 The corrupt role is carried to the service boundary but cannot alter the
 internal validation/train-only source selection.  This function never reads
 study evaluation-label files.
 """
 if scenario.input_hash != contract.base_input_hash: raise ValueError('Materialized input hash does not match the frozen execution contract.')
 if scenario.seed != contract.seed or scenario.generator_parameters != contract.generator_parameters: raise ValueError('Subject input is not bound to the frozen plan seed/parameters.')
 started=time.perf_counter(); root.parent.mkdir(parents=True,exist_ok=True)
 result={'product_entrypoint':contract.expected_product_entrypoint,'requested_data_role':'validation' if contract.clean_or_corrupt=='clean' else 'final_test','artifact_type':contract.artifact_type_expected,'artifact_created':False,'invalid_artifact_persisted':False,'artifact_id':None,'artifact_provenance_hash':None,'product_exception_type':None,'product_exception_message_normalized':None,'save_status':'NOT_REQUIRED','reopen_status':'NOT_REQUIRED','reopened_artifact_provenance_hash':None}
 try:
  run,evaluation=make_project(root,scenario=scenario,seed=contract.seed)
  if contract.violation_family=='V01':
   if contract.clean_or_corrupt=='corrupt':
    # The public train_model boundary accepts this request but derives split and
    # normalization internally; no supported fit-role parameter is consumed.
    run=train_model(root,model_kind='logistic_regression',seed=contract.seed,validation_fraction=.2,test_fraction=.2,preprocessing_fit_scope='final_test')
   result.update(resolved_data_role='train',artifact_created=True,artifact_id=str(run.run_id),artifact_provenance_hash=_hash(run.normalization),save_status='PASS')
   ProjectService().open(root,read_only=True)
   result.update(reopen_status='PASS',reopened_artifact_provenance_hash=_hash(run.normalization),product_outcome='ALLOWED_VALID' if contract.clean_or_corrupt=='clean' else 'PREVENTED_STRUCTURALLY')
  elif contract.violation_family=='V06':
   if contract.clean_or_corrupt=='clean':
    policy=select_validation_threshold(root,evaluation.evaluation_id); result.update(resolved_data_role=policy.source_split,artifact_created=True,artifact_id=str(policy.threshold_id),artifact_provenance_hash=_hash(policy.fit_sample_identity),save_status='PASS'); ProjectService().open(root,read_only=True); result.update(reopen_status='PASS',reopened_artifact_provenance_hash=_hash(policy.fit_sample_identity),product_outcome='ALLOWED_VALID')
   else:
    # A final-test identity is not a validation Evaluation; the product service
    # rejects it while resolving its validation-only evidence input.
    select_validation_threshold(root,uuid4()); raise AssertionError('final-test threshold request unexpectedly succeeded')
  elif contract.violation_family=='V07':
   if contract.clean_or_corrupt=='clean':
    transform=fit_validation_calibration(root,evaluation.evaluation_id); result.update(resolved_data_role=transform.source_split,artifact_created=True,artifact_id=str(transform.calibration_id),artifact_provenance_hash=_hash(transform.fit_sample_identity),save_status='PASS'); ProjectService().open(root,read_only=True); result.update(reopen_status='PASS',reopened_artifact_provenance_hash=_hash(transform.fit_sample_identity),product_outcome='ALLOWED_VALID')
   else:
    fit_validation_calibration(root,uuid4()); raise AssertionError('final-test calibration request unexpectedly succeeded')
  else: raise ValueError(f'unsupported study family {contract.violation_family}')
 except Exception as exc:
  if contract.clean_or_corrupt=='clean': raise
  result.update(resolved_data_role='validation_only_interface',product_outcome='PREVENTED_BY_FIREWALL',product_exception_type=type(exc).__name__,product_exception_message_normalized=str(exc).split('\n')[0][:240],artifact_created=False,save_status='PASS',reopen_status='PASS')
 result['runtime_ms']=round((time.perf_counter()-started)*1000,3)
 result['base_input_hash']=scenario.input_hash; result['generator_family']=scenario.generator_family; result['generator_parameters']=scenario.generator_parameters
 return result
