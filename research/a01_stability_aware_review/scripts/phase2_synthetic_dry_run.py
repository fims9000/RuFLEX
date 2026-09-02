"""End-to-end non-A01 fixture for the exact frozen Phase 2 executor."""
from __future__ import annotations
import hashlib, json, tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from ruflex.api.main import app
from research.a01_stability_aware_review.scripts.execute_phase2_final_test import execute

def _must(r):
 if r.status_code>=400:raise RuntimeError(r.text)
 return r.json()
def _table():
 return "x,y,target\n"+"".join(f"{i%17},{(i*7)%19},{int((i%17)+(i*7)%19>18)}\n" for i in range(120))
def _sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()

def run() -> dict:
 with tempfile.TemporaryDirectory(prefix="ruflex-a01-phase2-fixture-") as temp:
  root=Path(temp)/"project"; c=TestClient(app); sid=_must(c.post("/api/projects",json={"path":str(root),"name":"A01 Phase2 executor fixture only"}))["session_id"]
  _must(c.post("/api/projects/dataset/confirm",json={"session_id":sid,"csv_text":_table(),"target":"target","task":"binary_classification","id_columns":[]}))
  study=_must(c.post("/api/projects/training/studies",json={"session_id":sid,"name":"synthetic fixture only","model_kind":"random_forest","seeds":list(range(20)),"randomness_protocol":"TRAINING_VARIABILITY","split_seed":42,"selection_metric":"f1","max_epochs":1,"learning_rate":.01,"batch_size":16,"patience":1,"validation_fraction":.2,"test_fraction":.2,"max_rules":3}))
  ev=_must(c.post("/api/projects/analyses/evaluations",json={"session_id":sid,"run_id":study["selected_run_id"]}))
  th=_must(c.post("/api/projects/analyses/thresholds",json={"session_id":sid,"evaluation_id":ev["evaluation_id"],"objective":"f1"}))
  analysis=_must(c.post("/api/projects/analyses/stability",json={"session_id":sid,"study_id":study["study_id"],"evaluation_id":ev["evaluation_id"],"threshold_id":th["threshold_id"],"high_confidence_threshold":.9,"unstable_agreement_threshold":.8}))
  gate=_must(c.post("/api/projects/analyses/stability-policies",json={"session_id":sid,"analysis_id":analysis["analysis_id"],"evaluation_id":ev["evaluation_id"],"min_confidence":.9,"min_class_agreement":.8,"max_probability_std":.15}))
  policy=_must(c.post("/api/projects/analyses/selective-policies",json={"session_id":sid,"evaluation_id":ev["evaluation_id"],"threshold_id":th["threshold_id"],"confidence_cutoff":.8}))
  executor=Path(__file__).with_name("execute_phase2_final_test.py"); evidence=Path(temp)/"evidence.zip"; runtime=Path(temp)/"runtime.zip"; evidence.write_bytes(b"fixture evidence");runtime.write_bytes(b"fixture runtime")
  expected={"phase1_5_manifest_id":"fixture-manifest","evidence_bundle_sha256":_sha(evidence),"runtime_bundle_sha256":_sha(runtime),"phase2_executor_sha256":_sha(executor),"dataset_spec_sha256":"fixture-dataset","statistical_plan_sha256":"fixture-statistics"}; unlock=Path(temp)/"unlock.json";unlock.write_text(json.dumps({"study":"A01","allow_single_final_test_opening":True,"authorized_at":"fixture-only",**expected}))
  binding={"dataset_id":"synthetic_fixture","model_family":"random_forest","project_root":str(root),"study_id":study["study_id"],"selected_run_id":study["selected_run_id"],"evaluation_id":ev["evaluation_id"],"threshold_id":th["threshold_id"],"decision_threshold":th["selected_threshold"],"stability_gate_policy_id":gate["policy_id"],"confidence_only_policy_id":policy["policy_id"],"confidence_cutoff":.8,"h2_status":"FIXTURE_ONLY"}
  output=Path(temp)/"phase2"; bundles={"evidence_bundle":evidence,"runtime_bundle":runtime}; first=execute([binding],unlock_path=unlock,output_root=output,expected=expected,bundle_paths=bundles); second=execute([binding],unlock_path=unlock,output_root=output,expected=expected,bundle_paths=bundles)
  if first[0]["final_test_id"]!=second[0]["final_test_id"] or not (output/"FINAL_TEST_OPENING_RECEIPT.json").exists():raise RuntimeError("Phase 2 fixture resume/idempotence failed")
  return {"status":"PASS","study":"A01_PHASE2_EXECUTOR_FIXTURE_ONLY","data":"SYNTHETIC_NON_A01_NON_FINAL","empirical_a01_evidence":False,"final_test_accessed":False,"synthetic_fixture_final_test_accessed":True,"cell_count":len(first),"resume_idempotence":"PASS","h3_status":first[0]["h3_status"]}
def dry_run() -> dict:
 return run()
if __name__=="__main__":print(json.dumps(run(),sort_keys=True))
