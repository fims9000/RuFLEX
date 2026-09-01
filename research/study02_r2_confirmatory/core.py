from __future__ import annotations
import hashlib,json,time
from dataclasses import asdict,dataclass
from pathlib import Path
from uuid import UUID
import numpy as np
import pandas as pd
from ruflex.application.projects import ProjectService
from ruflex.application.datasets import persist_dataset_bytes,inspect_dataset,build_dataset_contract,persist_dataset_contract,run_data_audit
from ruflex.application.training import train_model,create_validation_evaluation,select_validation_threshold,fit_validation_calibration,evaluate_final_test

PRODUCT_SHA='772270a076e77b9c36d07e51bae8e45f5a3b1eddd69045176e63dc83834a3224'
def digest(value:object)->str:return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
@dataclass(frozen=True)
class Contract:
 pair_id:str;scenario_id:str;family:str;role:str;seed:int;generator_family:str;generator_parameters:dict;base_input_hash:str;entrypoint:str
 def payload(self):return asdict(self)
 def hash(self):return digest(self.payload())
def parameters(family:str,seed:int)->dict:
 return {'family':'iid' if family=='V06' else 'temporal','seed':seed,'sample_count':112+seed%17,'feature_count':4+seed%4,'class_imbalance':.32,'temporal_drift':0.0 if family=='V06' else .25}
def materialize(plan:dict)->tuple[pd.DataFrame,str,str]:
 p=plan['generator_parameters'];rng=np.random.default_rng(plan['seed']);x=rng.normal(size=(p['sample_count'],p['feature_count']))
 if p['family']=='temporal':x+=np.linspace(0,p['temporal_drift'],p['sample_count'])[:,None]
 weights=rng.normal(size=p['feature_count']);score=x@weights+rng.normal(0,.12,p['sample_count']);target=np.zeros(p['sample_count'],dtype=int);target[np.argsort(score)[-max(3,round(p['sample_count']*p['class_imbalance'])):]]=1
 frame=pd.DataFrame(x,columns=[f'feature_{i+1}' for i in range(p['feature_count'])]);frame['target']=target
 csv=frame.to_csv(index=False,float_format='%.17g');data_content_sha256=hashlib.sha256(csv.encode()).hexdigest()
 return frame,digest({'pair_id':plan['pair_id'],'parameters':p,'csv':csv}),data_content_sha256
def make_project(root:Path,frame:pd.DataFrame,seed:int):
 ProjectService().create(root,name='Study02 R2 subject');ref=persist_dataset_bytes(root,frame.to_csv(index=False).encode(),original_name='r2.csv');profile=inspect_dataset(frame,source_artifact_sha256=ref.sha256);contract=build_dataset_contract(profile,target='target',task='binary_classification');persist_dataset_contract(root,contract,run_data_audit(contract,frame),profile)
 run=train_model(root,model_kind='logistic_regression',seed=seed,validation_fraction=.2,test_fraction=.2);evaluation=create_validation_evaluation(root,run.run_id);return run,evaluation
def execute(contract:Contract,plan:dict,root:Path)->dict:
 frame,input_hash,data_content_sha256=materialize(plan);assert input_hash==contract.base_input_hash;assert data_content_sha256==plan['data_content_sha256'];started=time.perf_counter();run,evaluation=make_project(root,frame,contract.seed)
 result={'pair_id':contract.pair_id,'scenario_id':contract.scenario_id,'family':contract.family,'clean_or_corrupt':contract.role,'seed':contract.seed,'generator_parameters':contract.generator_parameters,'base_input_hash':input_hash,'data_content_sha256':data_content_sha256,'execution_contract_hash':contract.hash(),'product_entrypoint':contract.entrypoint,'validation_evaluation_id':str(evaluation.evaluation_id),'final_test_id':None,'final_test_artifact_exists':False,'final_test_artifact_type':None,'final_test_provenance':None,'attempted_source_id':str(evaluation.evaluation_id),'attempted_source_type':'AnalysisEvaluation','artifact_created':False,'artifact_id':None,'product_outcome':None,'exception_type':None,'exception_message':None,'invalid_artifact_persisted':False,'runtime_ms':0.0}
 if contract.family=='V06':
  threshold=select_validation_threshold(root,evaluation.evaluation_id); final=evaluate_final_test(root,evaluation.evaluation_id,threshold_id=threshold.threshold_id)
  if contract.role=='clean':result.update(artifact_created=True,artifact_id=str(threshold.threshold_id),product_outcome='ALLOWED_VALID')
  else:
   final_path=root/'analyses/final-tests'/f'{final.final_test_id}.json';result.update(final_test_id=str(final.final_test_id),final_test_artifact_exists=final_path.exists(),final_test_artifact_type='FinalTestEvaluation',final_test_provenance=final.model_dump(mode='json'),attempted_source_id=str(final.final_test_id),attempted_source_type='FinalTestEvaluation')
   try:select_validation_threshold(root,final.final_test_id)
   except Exception as exc:result.update(product_outcome='PREVENTED_BY_VALIDATION_ONLY_ARTIFACT_INTERFACE',exception_type=type(exc).__name__,exception_message=str(exc).split('\n')[0])
   else:result.update(product_outcome='MISSED',invalid_artifact_persisted=True)
 else:
  calibration=fit_validation_calibration(root,evaluation.evaluation_id);threshold=select_validation_threshold(root,evaluation.evaluation_id,calibration_id=calibration.calibration_id);final=evaluate_final_test(root,evaluation.evaluation_id,calibration_id=calibration.calibration_id,threshold_id=threshold.threshold_id)
  if contract.role=='clean':result.update(artifact_created=True,artifact_id=str(calibration.calibration_id),product_outcome='ALLOWED_VALID')
  else:
   final_path=root/'analyses/final-tests'/f'{final.final_test_id}.json';result.update(final_test_id=str(final.final_test_id),final_test_artifact_exists=final_path.exists(),final_test_artifact_type='FinalTestEvaluation',final_test_provenance=final.model_dump(mode='json'),attempted_source_id=str(final.final_test_id),attempted_source_type='FinalTestEvaluation')
   try:fit_validation_calibration(root,final.final_test_id)
   except Exception as exc:result.update(product_outcome='PREVENTED_BY_VALIDATION_ONLY_ARTIFACT_INTERFACE',exception_type=type(exc).__name__,exception_message=str(exc).split('\n')[0])
   else:result.update(product_outcome='MISSED',invalid_artifact_persisted=True)
 ProjectService().open(root,read_only=True);result['reopen_status']='PASS';result['runtime_ms']=round((time.perf_counter()-started)*1000,3);return result
