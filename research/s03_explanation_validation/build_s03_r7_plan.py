"""Build the separately namespaced S03-R7 corrected corrupt plans."""
from __future__ import annotations
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parent; CONFIG=ROOT/"config"
SOURCE=CONFIG/"locked_artifact_plan_phase0_2_treeshap_amendment.jsonl"
def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"))
def key(kind,row): return hashlib.sha256(canon({"namespace":"S03-R7", "kind":kind,"source_artifact_key":row["artifact_key"]}).encode()).hexdigest()[:24]
def main():
    original=[json.loads(x) for x in SOURCE.read_text().splitlines() if x]
    corrupt=[x for x in original if x["artifact_role"]=="CORRUPT"]
    executable=[]; nonexecutable=[]
    for row in corrupt:
        base={**row,"source_r6_plan_artifact_key":row["artifact_key"],"r7_artifact_id":key("artifact",row),"r7_pair_id":key("pair",row),"experiment":"S03-R7"}
        if row["expected_applicability"]=="NOT_APPLICABLE":
            nonexecutable.append({**base,"artifact_applicability":"NOT_APPLICABLE","non_executable_condition":True,"artifact_execution":"NOT_EXECUTED","reason":"EXACT_OCCLUSION_HAS_NO_MEANINGFUL_REDUCED_FIDELITY_BUDGET" if row["explainer"]=="occlusion" else "TREE_SHAP_HAS_NO_FINITE_REDUCED_FIDELITY_ROUTE"})
        else:
            executable.append({**base,"artifact_applicability":"APPLICABLE","non_executable_condition":False})
    evaluations=[]
    for artifact in executable:
        for mode in ("IDENTITY_ONLY","METRIC_ONLY","COMBINED"):
            evaluations.append({**artifact,"validator_mode":mode,"r7_execution_id":hashlib.sha256(canon({"namespace":"S03-R7","artifact":artifact["r7_artifact_id"],"mode":mode}).encode()).hexdigest()[:24]})
    assert len(corrupt)==5808 and len(nonexecutable)==576 and len(executable)==5232 and len(evaluations)==15696
    (CONFIG/"s03_r7_artifact_plan.jsonl").write_text("".join(canon(x)+"\n" for x in executable))
    (CONFIG/"s03_r7_non_executable_conditions.jsonl").write_text("".join(canon(x)+"\n" for x in nonexecutable))
    (CONFIG/"s03_r7_evaluation_plan.jsonl").write_text("".join(canon(x)+"\n" for x in evaluations))
    return {"r7_corrupt_artifacts":len(executable),"r7_corrupt_evaluations":len(evaluations),"artifact_level_not_applicable":len(nonexecutable),"r7_total_evaluations":792+len(evaluations)}
if __name__=="__main__": print(canon(main()))
