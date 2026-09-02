"""Metadata-only A01 Phase 2 preflight.  It never calls final-test replay."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from uuid import UUID
from ruflex.application.artifacts import ArtifactRef,ArtifactStore
from ruflex.application.datasets import load_dataset_contract
from ruflex.application.selective import load_selective_policy
from ruflex.application.stability import load_stability_gate_policy,load_study_stability_analysis
from ruflex.application.training import load_decision_threshold,load_training_run,load_training_study,load_validation_evaluation

ROOT=Path(__file__).resolve().parents[1]; RESULTS=ROOT/"results"/"phase1_validation"; CONFIG=ROOT/"config"
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"))
def run(output:Path)->dict:
 bindings=json.loads((RESULTS/"selected_runs.json").read_text()); artifacts=0; chains=[]
 for b in bindings:
  root=Path(b["project_root"]);contract=load_dataset_contract(root);ev=load_validation_evaluation(root,UUID(b["evaluation_id"]));selected=load_training_run(root,ev.run_id);study=load_training_study(root,UUID(b["study_id"]));th=load_decision_threshold(root,UUID(b["threshold_id"]));gate=load_stability_gate_policy(root,UUID(b["stability_gate_policy_id"]));cp=load_selective_policy(root,UUID(b["confidence_only_policy_id"]));analysis=load_study_stability_analysis(root,gate.stability_analysis_id)
  if contract.dataset_fingerprint!=selected.dataset_fingerprint or contract.source_artifact_sha256!=selected.dataset_artifact_sha256 or selected.split.split_seed!=42 or study.selected_run_id!=selected.run_id:raise RuntimeError("dataset/study binding mismatch")
  if th.probability_source!="raw" or th.calibration_id is not None or th.evaluation_id!=ev.evaluation_id or gate.evaluation_id!=ev.evaluation_id or gate.class_threshold_id!=th.threshold_id or (gate.min_confidence,gate.min_class_agreement,gate.max_probability_std)!=(.9,.8,.15) or len(gate.run_ids)!=20 or cp.class_threshold_id!=th.threshold_id or cp.confidence_cutoff!=b["confidence_cutoff"]:raise RuntimeError("policy chain mismatch")
  for run_id in gate.run_ids:
   item=load_training_run(root,run_id)
   if not ArtifactStore(root).verify(ArtifactRef(sha256=item.model_artifact_sha256)).valid:raise RuntimeError("model artifact invalid")
   artifacts+=1
  chains.append({"dataset_id":b["dataset_id"],"model_family":b["model_family"],"dataset_fingerprint":contract.dataset_fingerprint,"source_artifact_sha256":contract.source_artifact_sha256,"split_identity":selected.split.split_identity,"selected_run_id":str(selected.run_id),"threshold_id":str(th.threshold_id),"stability_policy_id":str(gate.policy_id),"confidence_policy_id":str(cp.policy_id)})
 if artifacts!=300:raise RuntimeError("expected 300 verified artifacts")
 phase175=json.loads((CONFIG/"phase1_75_executor_freeze_manifest.json").read_text()); p15=json.loads((CONFIG/"phase1_5_scientific_freeze_manifest.json").read_text())
 release=ROOT.parents[1]/"release"; values={"phase1_75_manifest_id":phase175["manifest_id"],"phase1_5_manifest_id":p15["manifest_id"],"phase2_executor_sha256":phase175["executor_bindings"]["phase2_executor_sha256"],"statistics_sha256":phase175["executor_bindings"]["statistics_sha256"],"result_schema_sha256":phase175["executor_bindings"]["result_schema_sha256"],"dataset_spec_sha256":"c5bc7d8d5842067147d28263fa96ae35374fe56afd411ff2ff7a286eace44b42","statistical_plan_sha256":"59c411cf345350e012bcb9011ba56192f4e796e787fe5ce40ed05a68fc8c707d","evidence_bundle_sha256":sha(release/"RuFLEX_A01_PHASE1_5_VALIDATION_EVIDENCE_BUNDLE.zip"),"runtime_bundle_sha256":sha(release/"RuFLEX_A01_FROZEN_MODELS_RUNTIME_BUNDLE.zip")}
 receipt={"status":"PASS","timestamp":datetime.now(timezone.utc).isoformat(),"source_head":__import__("subprocess").check_output(["git","-C",str(ROOT.parents[1]),"rev-parse","HEAD"],text=True).strip(),"identities":values,"artifacts_verified":artifacts,"policy_chains_verified":len(chains),"active_dataset_revisions_verified":len(chains),"final_test_accessed":False,"chains":chains};receipt["receipt_sha256"]=hashlib.sha256(canonical(receipt).encode()).hexdigest();output.parent.mkdir(parents=True,exist_ok=True);output.write_text(canonical(receipt)+"\n");return receipt
if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);a=p.parse_args();print(canonical(run(a.output)))
