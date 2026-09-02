"""Fail-closed S03 DatasetContract amendment validator."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd
from ruflex.application.datasets import build_dataset_contract,inspect_dataset
from research.s03_explanation_validation.build_phase0_2 import main as rebuild
ROOT=Path(__file__).resolve().parent; C=ROOT/"config"
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def validate()->dict:
 manifest=json.loads((C/"phase0_2_dataset_id_amendment_manifest.json").read_text())
 assert manifest["status"]=="DATASET_PROFILING_AMENDMENT_FROZEN_COHERENT_PHASE1_RESTART_AUTHORIZED"
 for name,digest in manifest["file_hashes"].items(): assert sha(ROOT/name)==digest,name
 table=ROOT.parent/"a01_stability_aware_review"/"artifacts"/"phase1-data"/"materialized"/"uci_bank_marketing"/"canonical.csv"
 frame=pd.read_csv(table); profile=inspect_dataset(frame,source_artifact_sha256="a"*64)
 contract=build_dataset_contract(profile,target="y",task="binary_classification",id_columns=["source_row_id"])
 assert len(contract.feature_columns)==62 and "job_housemaid" in contract.feature_columns
 plan=C/"locked_execution_plan_phase0_2.jsonl"; before=sha(plan); counts=rebuild(); assert sha(plan)==before
 assert counts=={"clean_artifacts":264,"corrupt_artifacts":5808,"clean_evaluations":792,"corrupt_evaluations":17424,"evaluations":18216}
 receipt=ROOT/"results"/"phase1_clean_baseline"/"PHASE1_INTERRUPTED_RECEIPT.json"
 old=json.loads(receipt.read_text()); assert old["benchmark_models_trained_before_stop"]==5 and old["benchmark_clean_explanations_generated"]==0 and not old["final_test_accessed"]
 return {"status":"PASS","bank_feature_count":62,**counts,"interrupted_attempt_preserved":True}
if __name__=="__main__":print(json.dumps(validate(),sort_keys=True))
