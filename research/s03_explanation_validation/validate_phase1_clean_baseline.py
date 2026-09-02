"""Fail-closed validation for the S03 Phase 1 clean control freeze."""
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT/"results"/"phase1_clean_baseline_r6"
PROJECTS=ROOT/"artifacts"/"phase1_clean_projects_r6"
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path:Path)->list[dict]:return [json.loads(line) for line in path.read_text().splitlines() if line]
def validate()->dict:
 m=json.loads((RESULTS/"PHASE1_CLEAN_FREEZE_MANIFEST.json").read_text())
 assert m["status"]=="PHASE1_CLEAN_BASELINE_FROZEN_CORRUPT_EXECUTION_NOT_STARTED"
 assert m["declared_models"]==15 and m["sample_slots"]==120 and m["clean_artifacts"]==264 and m["clean_evaluations"]==792
 assert m["phase0_2_treeshap_amendment_manifest_id"]
 ledger=json.loads((RESULTS/"run_ledger.json").read_text())["rows"]
 assert len(ledger)==15 and all(x["status"]=="SUCCEEDED" for x in ledger)
 assert all(x["split_identity"] for x in ledger) and all(x["project_root"].startswith(str(PROJECTS)) for x in ledger)
 assert all(len({row["project_root"] for row in ledger if row["dataset_id"]==dataset})==1 for dataset in {row["dataset_id"] for row in ledger})
 selection=json.loads((RESULTS/"FROZEN_SAMPLE_SELECTION.json").read_text())["selection"]
 assert len(selection)==120 and len({(x["dataset_id"],x["model_family"],x["sample_slot"]) for x in selection})==120
 artifacts=rows(RESULTS/"CLEAN_ARTIFACTS.jsonl"); evaluations=rows(RESULTS/"CLEAN_EVALUATIONS.jsonl")
 artifact_ledger=json.loads((RESULTS/"clean_artifact_ledger.json").read_text())["rows"]
 assert len(artifact_ledger)==264 and {row["artifact_key"] for row in artifact_ledger}=={row["artifact_key"] for row in artifacts}
 assert len(artifacts)==264 and len({x["artifact_key"] for x in artifacts})==264
 assert len(evaluations)==792 and len({x["execution_id"] for x in evaluations})==792
 assert all(x["artifact_role"]=="CLEAN" and not x["numerical_warn_is_detector"] for x in evaluations)
 assert not list(ROOT.glob("results/**/CORRUPT*"))
 for root in PROJECTS.glob("*"):
  assert not list((root/"analyses"/"final-tests").glob("*.json")) if (root/"analyses"/"final-tests").exists() else True
 for field,file in (("run_ledger_sha256","run_ledger.json"),("sample_selection_sha256","FROZEN_SAMPLE_SELECTION.json"),("clean_artifacts_sha256","CLEAN_ARTIFACTS.jsonl"),("clean_evaluations_sha256","CLEAN_EVALUATIONS.jsonl")):
  assert m[field]==sha(RESULTS/file),field
 return {"status":"PASS","models":15,"samples":120,"clean_artifacts":264,"clean_evaluations":792,"final_test_accessed":False,"corrupt_artifacts_executed":0}
if __name__=="__main__":print(json.dumps(validate(),sort_keys=True))
