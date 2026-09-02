"""Frozen A01 Phase 2 executor; product-native replay only, never fitting."""
from __future__ import annotations
import argparse, csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID
from research.a01_stability_aware_review.statistics import accepted_case_fnr, accepted_case_risk, h3_interpretation, paired_bootstrap_policy_metrics, select_illustrative_cases
from ruflex.application.artifacts import ArtifactRef, ArtifactStore
from ruflex.application.selective import load_selective_policy
from ruflex.application.stability import load_stability_gate_policy, load_study_stability_analysis
from ruflex.application.training import evaluate_final_test, load_decision_threshold, load_training_run, load_validation_evaluation

RESULT_SCHEMA={"schema_version":1,"required":["dataset_id","model_family","selected_run_id","threshold_id","stability_gate_policy_id","confidence_only_policy_id","final_test_id","no_review","confidence_only_frozen","stability_gate_frozen","observed_delta_risk","bootstrap","h3_status"],"tables":["T05_final_test_policy_outcomes.csv","T06_h3_effects.csv","T07_ai4i_fnr.csv","T08_final_scientific_status.csv"],"figures":["F05_final_test_risk_coverage","F06_delta_accepted_case_risk","F07_ai4i_accepted_case_fnr","F08_deterministic_unstable_cases"]}

def _json(v:Any)->str:return json.dumps(v,sort_keys=True,separators=(",",":"))
def _sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def _write(p:Path,v:Any)->None:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(_json(v)+"\n")
def _utc()->str:return datetime.now(timezone.utc).isoformat()

def authorization_gate(unlock_path:Path|None,expected:dict[str,str])->dict[str,Any]:
 if unlock_path is None or not unlock_path.is_file():raise PermissionError("A01 final test is closed: explicit external unlock artifact is required before any dataset read.")
 unlock=json.loads(unlock_path.read_text()); required={"study":"A01","allow_single_final_test_opening":True,**expected}
 if not unlock.get("authorized_at") or any(unlock.get(k)!=v for k,v in required.items()):raise PermissionError("A01 unlock identity mismatch.")
 return unlock

def _verify(binding:dict[str,Any])->None:
 root=Path(binding["project_root"]); ev=load_validation_evaluation(root,UUID(binding["evaluation_id"])); run=load_training_run(root,ev.run_id); th=load_decision_threshold(root,UUID(binding["threshold_id"])); gate=load_stability_gate_policy(root,UUID(binding["stability_gate_policy_id"])); cp=load_selective_policy(root,UUID(binding["confidence_only_policy_id"])); analysis=load_study_stability_analysis(root,gate.stability_analysis_id)
 if str(run.run_id)!=binding["selected_run_id"] or th.evaluation_id!=ev.evaluation_id or th.probability_source!="raw" or th.calibration_id is not None:raise RuntimeError("frozen raw threshold chain mismatch")
 if gate.evaluation_id!=ev.evaluation_id or gate.class_threshold_id!=th.threshold_id or gate.decision_threshold!=th.selected_threshold or len(gate.run_ids)!=20 or gate.run_ids!=analysis.run_ids:raise RuntimeError("frozen Stability Gate chain mismatch")
 if cp.evaluation_id!=ev.evaluation_id or cp.run_id!=run.run_id or cp.class_threshold_id!=th.threshold_id or cp.calibration_id is not None:raise RuntimeError("frozen confidence policy chain mismatch")
 for run_id in gate.run_ids:
  item=load_training_run(root,run_id)
  if not ArtifactStore(root).verify(ArtifactRef(sha256=item.model_artifact_sha256)).valid:raise RuntimeError("frozen model missing or invalid")

def _verify_bundles(paths:dict[str,Path],expected:dict[str,str])->None:
 for key,identity in (("evidence_bundle","evidence_bundle_sha256"),("runtime_bundle","runtime_bundle_sha256")):
  path=paths.get(key)
  if path is None or not path.is_file() or _sha(path)!=expected.get(identity):raise RuntimeError(f"frozen {key} bundle verification failed")

def _opening(root:Path,unlock:Path,expected:dict[str,str])->None:
 p=root/"FINAL_TEST_OPENING_RECEIPT.json"; digest=_sha(unlock)
 if p.exists():
  old=json.loads(p.read_text())
  if old.get("unlock_sha256")!=digest or old.get("identities")!=expected:raise RuntimeError("opening receipt differs from frozen authorization")
  return
 _write(p,{"unlock_sha256":digest,"identities":expected,"opened_at":_utc(),"execution_state":"OPENED_INCOMPLETE"})

def _result(binding:dict[str,Any],final:Any)->dict[str,Any]:
 ev=final.stability_gate_evidence
 if ev is None:raise RuntimeError("product-native final Stability evidence absent")
 source={int(r.source_row):r for r in final.prediction_rows}; rows=[]
 for case in ev.cases:
  row=source.get(case.source_row)
  if row is None or int(row.target)!=case.target or int(row.predicted_label)!=case.selected_run_class or abs(float(row.probability)-case.selected_run_probability)>1e-12:raise RuntimeError("final case alignment mismatch")
  rows.append({"case_id":case.case_id,"target":case.target,"prediction":case.selected_run_class,"probability":case.selected_run_probability,"selected_run_agreement":case.selected_run_agreement,"majority_class_agreement":case.majority_class_agreement,"probability_std":case.probability_std,"stability":case.disposition,"reasons":list(case.reasons)})
 truth=[r["target"] for r in rows]; pred=[r["prediction"] for r in rows]; stability=[r["stability"] for r in rows]; confidence=["ACCEPT" if max(r["probability"],1-r["probability"])>=float(binding["confidence_cutoff"]) else "REVIEW" for r in rows]; no_review=["ACCEPT"]*len(rows)
 nr,co,st=(accepted_case_risk(truth,pred,d).__dict__ for d in (no_review,confidence,stability)); bootstrap=paired_bootstrap_policy_metrics(truth,pred,stability,confidence,replicates=10000,seed=20260902); delta=None if st["accepted_risk"] is None or co["accepted_risk"] is None else st["accepted_risk"]-co["accepted_risk"]
 fnr=None if binding["dataset_id"]!="ai4i_2020" else {"no_review":accepted_case_fnr(truth,pred,no_review),"confidence_only_frozen":accepted_case_fnr(truth,pred,confidence),"stability_gate_frozen":accepted_case_fnr(truth,pred,stability)}
 delta_fnr=None if fnr is None or fnr["stability_gate_frozen"]["accepted_case_fnr"] is None or fnr["confidence_only_frozen"]["accepted_case_fnr"] is None else fnr["stability_gate_frozen"]["accepted_case_fnr"]-fnr["confidence_only_frozen"]["accepted_case_fnr"]
 return {"schema_version":1,"dataset_id":binding["dataset_id"],"model_family":binding["model_family"],"selected_run_id":binding["selected_run_id"],"threshold_id":binding["threshold_id"],"decision_threshold":binding["decision_threshold"],"stability_gate_policy_id":binding["stability_gate_policy_id"],"confidence_only_policy_id":binding["confidence_only_policy_id"],"confidence_cutoff":binding["confidence_cutoff"],"final_test_id":str(final.final_test_id),"test_case_identity":final.test_case_identity,"no_review":nr,"confidence_only_frozen":co,"stability_gate_frozen":st,"observed_delta_risk":delta,"bootstrap":bootstrap,"h1_status":"NOT_ASSESSABLE","h2_status":binding.get("h2_status","FROZEN_PHASE1_STATUS"),"h3_status":h3_interpretation(bootstrap["delta_risk"]["percentile_ci_95"]),"ai4i_fnr":fnr,"observed_delta_fnr":delta_fnr,"reason_codes":bootstrap["delta_risk"]["reason_codes"],"illustrative_case_ids":select_illustrative_cases([{**r,"selected_run_confidence":max(r["probability"],1-r["probability"])} for r in rows],limit=min(5,len(rows))),"product_native_evidence":True,"research_derived_statistics":True}

def _ledger(p:Path)->dict[str,dict[str,Any]]:
 f=p/"phase2_execution_ledger.jsonl";return {} if not f.exists() else {r["cell_id"]:r for r in (json.loads(x) for x in f.read_text().splitlines() if x)}
def _save_ledger(p:Path,rows:dict[str,dict[str,Any]])->None:
 f=p/"phase2_execution_ledger.jsonl";f.parent.mkdir(parents=True,exist_ok=True);f.write_text("".join(_json(rows[k])+"\n" for k in sorted(rows)))

def _tables(root:Path,results:list[dict[str,Any]])->None:
 root=root/"tables";root.mkdir(parents=True,exist_ok=True)
 policies=[];effects=[];fnr=[];status=[]
 for row in results:
  for name,key in (("NO_REVIEW","no_review"),("CONFIDENCE_ONLY_FROZEN","confidence_only_frozen"),("STABILITY_GATE_FROZEN","stability_gate_frozen")):
   policies.append({"dataset":row["dataset_id"],"model":row["model_family"],"policy":name,**row[key]})
  effects.append({"dataset":row["dataset_id"],"model":row["model_family"],"delta_risk":row["observed_delta_risk"],"ci_95":row["bootstrap"]["delta_risk"]["percentile_ci_95"],"h3_status":row["h3_status"]})
  status.append({"dataset":row["dataset_id"],"model":row["model_family"],"h1":row["h1_status"],"h2":row["h2_status"],"h3":row["h3_status"],"reasons":row["reason_codes"]})
  if row["ai4i_fnr"]:
   for name,value in row["ai4i_fnr"].items():fnr.append({"dataset":row["dataset_id"],"model":row["model_family"],"policy":name,**value,"delta_fnr":row["observed_delta_fnr"],"delta_fnr_ci_95":row["bootstrap"]["delta_fnr"]["percentile_ci_95"]})
 for name,rows in (("T05_final_test_policy_outcomes.csv",policies),("T06_h3_effects.csv",effects),("T07_ai4i_fnr.csv",fnr),("T08_final_scientific_status.csv",status)):
  keys=sorted({k for row in rows for k in row}) or ["dataset"]
  with (root/name).open("w",newline="",encoding="utf-8") as h:
   w=csv.DictWriter(h,fieldnames=keys);w.writeheader();w.writerows(rows)

def execute(bindings:list[dict[str,Any]],*,unlock_path:Path,output_root:Path,expected:dict[str,str],bundle_paths:dict[str,Path])->list[dict[str,Any]]:
 authorization_gate(unlock_path,expected)
 _verify_bundles(bundle_paths,expected)
 for b in bindings:_verify(b)
 _opening(output_root,unlock_path,expected); ledger=_ledger(output_root); results=[]
 for b in bindings:
  cell=f"{b['dataset_id']}::{b['model_family']}"; target=output_root/"cells"/(cell.replace("::","__")+".json")
  if ledger.get(cell,{}).get("state")=="FROZEN" and target.exists():results.append(json.loads(target.read_text()));continue
  ledger[cell]={"cell_id":cell,"state":"OPENING","selected_run_id":b["selected_run_id"],"threshold_id":b["threshold_id"],"stability_policy_id":b["stability_gate_policy_id"],"confidence_policy_id":b["confidence_only_policy_id"]};_save_ledger(output_root,ledger)
  final=evaluate_final_test(Path(b["project_root"]),UUID(b["evaluation_id"]),calibration_id=None,threshold_id=UUID(b["threshold_id"]),selective_policy_id=UUID(b["confidence_only_policy_id"]),stability_gate_policy_id=UUID(b["stability_gate_policy_id"]))
  value=_result(b,final);_write(target,value);ledger[cell].update({"state":"FROZEN","final_test_id":value["final_test_id"],"result_sha256":_sha(target)});_save_ledger(output_root,ledger);results.append(value)
 _write(output_root/"A01_FINAL_RESULTS.json",{"schema_version":1,"cells":results,"global_h3_claim":"FORBIDDEN"});_tables(output_root,results);return results

def main()->None:
 p=argparse.ArgumentParser();p.add_argument("--unlock",type=Path,required=True);p.add_argument("--bindings",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True);p.add_argument("--expected",type=Path,required=True);p.add_argument("--evidence-bundle",type=Path,required=True);p.add_argument("--runtime-bundle",type=Path,required=True);a=p.parse_args();execute(json.loads(a.bindings.read_text()),unlock_path=a.unlock,output_root=a.output_root,expected=json.loads(a.expected.read_text()),bundle_paths={"evidence_bundle":a.evidence_bundle,"runtime_bundle":a.runtime_bundle})
if __name__=="__main__":main()
