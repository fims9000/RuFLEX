"""Bind the DatasetContract correctness amendment without rewriting Phase 0.2."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent; C=ROOT/"config"
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(value:object)->str:return json.dumps(value,sort_keys=True,separators=(",",":"))
def main()->dict:
 historical=json.loads((C/"phase0_2_conformance_manifest.json").read_text())
 files=["AMENDMENT_001_DATASET_ID_HEURISTIC.md","execute_phase1_clean_baseline.py","validate_phase1_clean_baseline.py","freeze_phase0_2_amendment.py","config/locked_artifact_plan_phase0_2.jsonl","config/locked_execution_plan_phase0_2.jsonl","config/component_applicability_matrix.json","config/environment_lock.json","../../src/ruflex/application/datasets.py"]
 value={"schema_version":1,"study":"S03","status":"DATASET_PROFILING_AMENDMENT_FROZEN_COHERENT_PHASE1_RESTART_AUTHORIZED","historical_phase0_2_manifest_id":historical["manifest_id"],"interrupted_phase1_receipt":"results/phase1_clean_baseline/PHASE1_INTERRUPTED_RECEIPT.json","benchmark_explanations_seen":False,"benchmark_corrupt_explanations_seen":False,"empirical_detection_results_seen":False,"final_test_accessed":False,"bank_feature_count":62,"bank_required_feature":"job_housemaid","matrix_counts":{"clean_artifacts":264,"clean_evaluations":792,"corrupt_artifacts":5808,"total_evaluations":18216},"file_hashes":{name:sha(ROOT/name) for name in files}}
 value["manifest_id"]=hashlib.sha256(canonical(value).encode()).hexdigest()
 (C/"phase0_2_dataset_id_amendment_manifest.json").write_text(canonical(value)+"\n")
 return value
if __name__=="__main__":print(canonical(main()))
