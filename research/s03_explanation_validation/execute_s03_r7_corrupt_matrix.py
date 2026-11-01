"""Execute the corrected S03-R7 matrix; it never reads R6 corrupt results."""
from __future__ import annotations
import hashlib,json,time
from datetime import datetime,timezone
from pathlib import Path
from uuid import UUID
from research.s03_explanation_validation.execute_corrupt_matrix import _alternate,_low_fidelity,_component_map,_metrics,_evaluation,MODELS
from ruflex.application.evidence import _persist_explanation,check_explanation,load_explanation
from ruflex.application.training import load_training_run

ROOT=Path(__file__).resolve().parent; CONFIG=ROOT/"config"; CLEAN=ROOT/"results"/"phase1_clean_baseline_r6"; AMENDMENT=ROOT/"results"/"quantus_amendment_r6"; OUT=ROOT/"results"/"s03_r7"
def canon(x):return json.dumps(x,sort_keys=True,separators=(",",":"),default=str)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def write_jsonl(p,x):p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+".tmp");t.write_text("".join(canon(v)+"\n" for v in x));t.replace(p)
def write_json(p,x):p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+".tmp");t.write_text(canon(x)+"\n");t.replace(p)
def main():
    plan=rows(CONFIG/"s03_r7_artifact_plan.jsonl"); assert len(plan)==5232
    clean={x["artifact_key"]:x for x in rows(CLEAN/"CLEAN_ARTIFACTS.jsonl")}; runledger={(x["dataset_id"],x["model_family"]):x for x in json.loads((CLEAN/"run_ledger.json").read_text())["rows"]}
    q={(x["clean_artifact_key"],x["metric_name"]):x for x in rows(AMENDMENT/"CLEAN_QUANTUS_METRICS.jsonl")}
    ap=OUT/"R7_CORRUPT_ARTIFACTS.jsonl"; ep=OUT/"R7_CORRUPT_EVALUATIONS.jsonl"; existing={x["r7_artifact_id"]:x for x in rows(ap)} if ap.exists() else {}; evaluations={x["r7_execution_id"]:x for x in rows(ep)} if ep.exists() else {}
    for i,planned in enumerate(plan,1):
        stored=existing.get(planned["r7_artifact_id"])
        if stored is None:
            parent=clean[planned["clean_artifact_key"]];root=Path(parent["project_root"]);clean_contract=load_explanation(root,UUID(parent["explanation_id"]));started=time.perf_counter()
            if planned["failure_family"]=="L1_LOW_FIDELITY": corrupt=_low_fidelity(root,load_training_run(root,clean_contract.run_id),clean_contract,planned["severity"]);changed=["generation_parameters"]; receipt={"fresh_product_native_reduced_budget":True,"changed_fields":changed}
            else:
                library=__import__("research.s03_explanation_validation.corruptions.library",fromlist=["corrupt_contract","mutation_receipt"]);corrupt,changed=library.corrupt_contract(clean_contract,family=planned["failure_family"],subtype=planned["failure_subtype"],severity=planned["severity"],seed=3003,alternate_run_id=_alternate(parent,runledger));corrupt=_persist_explanation(root,corrupt);receipt=library.mutation_receipt(clean_contract,corrupt,family=planned["failure_family"],subtype=planned["failure_subtype"],severity=planned["severity"],seed=3003,changed_fields=changed)
            check=check_explanation(root,corrupt.explanation_id);component=_component_map(check);metric=_metrics(q,planned["clean_artifact_key"],root,corrupt);path=root/"evidence"/"explanations"/f"{corrupt.explanation_id}.json"
            stored={**planned,"state":"EVALUATED","project_root":str(root),"clean_explanation_id":parent["explanation_id"],"clean_sha256":parent["explanation_sha256"],"explanation_id":str(corrupt.explanation_id),"explanation_sha256":sha(path),"check_id":str(check.check_id),"changed_fields":changed,"mutation_receipt":receipt,"check_components":component,"quantus":metric,"runtime_seconds":time.perf_counter()-started,"created_at":datetime.now(timezone.utc).isoformat()};existing[planned["r7_artifact_id"]]=stored;write_jsonl(ap,[existing[k] for k in sorted(existing)])
        for mode in ("IDENTITY_ONLY","METRIC_ONLY","COMBINED"):
            eid=hashlib.sha256(canon({"namespace":"S03-R7","artifact":planned["r7_artifact_id"],"mode":mode}).encode()).hexdigest()[:24]
            if eid not in evaluations:
                ev=_evaluation(stored,mode,stored["check_components"],stored["quantus"],planned.get("expected_localization_component")); evaluations[eid]={**ev,"r7_execution_id":eid};write_jsonl(ep,[evaluations[k] for k in sorted(evaluations)])
        if i%10==0:print(canon({"progress":i,"of":len(plan)}),flush=True)
    assert len(existing)==5232 and len(evaluations)==15696
    x={"schema_version":1,"study":"S03-R7","status":"R7_CORRUPT_EXECUTION_COMPLETE","corrupt_artifacts":5232,"corrupt_evaluations":15696,"artifacts_sha256":sha(ap),"evaluations_sha256":sha(ep),"created_at":datetime.now(timezone.utc).isoformat()};x["manifest_id"]=hashlib.sha256(canon(x).encode()).hexdigest();write_json(OUT/"R7_CORRUPT_EXECUTION_MANIFEST.json",x);return x
if __name__=="__main__":print(canon(main()))
