"""Synthetic-only native RuFLEX S03 route; never an S03 benchmark execution."""
from __future__ import annotations
import json,tempfile
from pathlib import Path
from uuid import UUID
import pandas as pd
from ruflex.application.evidence import check_explanation, create_occlusion_explanation, load_explanation_check
from ruflex.application.training import train_model
from ruflex.application.datasets import build_dataset_contract,inspect_dataset,persist_dataset_bytes,persist_dataset_contract,run_data_audit
from research.s03_explanation_validation.corruptions import corrupt_contract,mutation_receipt

def smoke() -> dict:
 with tempfile.TemporaryDirectory(prefix='ruflex-s03-smoke-') as tmp:
  root=Path(tmp);frame=pd.DataFrame([{'x1':float(i),'x2':float((i*7)%11),'target':int(i%3==0)} for i in range(60)])
  raw=frame.to_csv(index=False).encode(); artifact=persist_dataset_bytes(root,raw); profile=inspect_dataset(frame,source_artifact_sha256=artifact.sha256); contract=build_dataset_contract(profile,target='target',task='binary_classification');persist_dataset_contract(root,contract,run_data_audit(contract,frame),profile)
  run=train_model(root,model_kind='logistic_regression',seed=17,validation_fraction=.2,test_fraction=.2)
  clean=create_occlusion_explanation(root,run.run_id,{'x1':15.0,'x2':6.0}); clean_check=check_explanation(root,clean.explanation_id)
  corrupt,fields=corrupt_contract(clean,family='M1_MODEL_MISMATCH',subtype='artifact_sha_swap',severity='NONE',seed=3003)
  ep=root/'evidence'/'explanations';ep.mkdir(parents=True,exist_ok=True);(ep/f'{corrupt.explanation_id}.json').write_text(corrupt.model_dump_json(indent=2))
  check=check_explanation(root,corrupt.explanation_id); reopened=load_explanation_check(root,check.check_id)
  return {'study':'S03_SYNTHETIC_SMOKE_ONLY','empirical_s03_evidence':False,'clean_status':clean_check.status,'corrupt_status':check.status,'localized_model_identity':any(i.name=='model_identity' and i.status=='FAIL' for i in check.checks),'reopen_status':reopened.status,'receipt':mutation_receipt(clean,corrupt,family='M1_MODEL_MISMATCH',subtype='artifact_sha_swap',severity='NONE',seed=3003,changed_fields=fields)}
if __name__=='__main__':print(json.dumps(smoke(),sort_keys=True))
