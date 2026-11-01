"""Fail-closed validator for the separately authorized S03-R7 matrix."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent; CONFIG=ROOT/"config"; CLEAN=ROOT/"results"/"phase1_clean_baseline_r6"; R6=ROOT/"results"/"phase2_corrupt_r6"; R7=ROOT/"results"/"s03_r7"
def rows(p): return [json.loads(x) for x in p.read_text().splitlines() if x]
def validate():
    clean=json.loads((CLEAN/"PHASE1_CLEAN_FREEZE_MANIFEST.json").read_text()); assert clean["clean_artifacts"]==264 and clean["clean_evaluations"]==792
    interrupted=json.loads((R6/"R6_INTERRUPTED_CORRUPT_PLAN_DEFECT_RECEIPT.json").read_text()); assert interrupted["corrupt_artifacts_persisted"]==16 and interrupted["corrupt_evaluations_persisted"]==48
    qa=json.loads((ROOT/"results"/"quantus_amendment_r6"/"QUANTUS_AMENDMENT_QA.json").read_text()); assert qa["state"]=="PASS"
    artifact=rows(CONFIG/"s03_r7_artifact_plan.jsonl"); nonexec=rows(CONFIG/"s03_r7_non_executable_conditions.jsonl"); evaluation=rows(CONFIG/"s03_r7_evaluation_plan.jsonl")
    assert len(artifact)==5232 and len(nonexec)==576 and len(evaluation)==15696
    assert all(x["artifact_applicability"]=="APPLICABLE" and x["artifact_execution"]!="NOT_EXECUTED" for x in artifact)
    assert all(x["artifact_applicability"]=="NOT_APPLICABLE" and x["artifact_execution"]=="NOT_EXECUTED" for x in nonexec)
    assert not any(x["explainer"]=="occlusion" and x["failure_family"]=="L1_LOW_FIDELITY" for x in artifact)
    assert not any(x["explainer"]=="tree_shap" and x["failure_family"]=="L1_LOW_FIDELITY" for x in artifact)
    assert len({x["r7_artifact_id"] for x in artifact})==5232 and len({x["r7_pair_id"] for x in artifact})==5232 and len({x["r7_execution_id"] for x in evaluation})==15696
    assert not R7.exists() or not list(R7.glob("R7_CORRUPT_ARTIFACTS.jsonl"))
    return {"status":"PASS","r7_corrupt_artifacts":5232,"r7_corrupt_evaluations":15696,"non_executable":576,"r6_corrupt_excluded":True}
if __name__=="__main__": print(json.dumps(validate(),sort_keys=True))
