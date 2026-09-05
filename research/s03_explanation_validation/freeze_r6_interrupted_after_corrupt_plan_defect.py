"""Preserve the limited R6 corrupt exposure after a frozen-plan contradiction."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent; OUT=ROOT/"results"/"phase2_corrupt_r6"; CONFIG=ROOT/"config"
def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    artifacts=[json.loads(x) for x in (OUT/"CORRUPT_ARTIFACTS.jsonl").read_text().splitlines() if x]
    evaluations=[json.loads(x) for x in (OUT/"CORRUPT_EVALUATIONS.jsonl").read_text().splitlines() if x]
    bad=next(json.loads(x) for x in (CONFIG/"locked_artifact_plan_phase0_2_treeshap_amendment.jsonl").read_text().splitlines() if '"failure_family":"L1_LOW_FIDELITY"' in x and '"explainer":"occlusion"' in x)
    assert bad["expected_applicability"]=="NOT_APPLICABLE" and bad["artifact_execution"]=="fresh_product_native_reduced_budget_explanation"
    payload={"schema_version":1,"study":"S03","status":"R6_INTERRUPTED_AFTER_CORRUPT_PLAN_SCIENTIFIC_CORRECTNESS_DEFECT","created_at":datetime.now(timezone.utc).isoformat(),"defect":"Frozen L1/Occlusion condition is declared NOT_APPLICABLE but commands fresh product-native reduced-budget execution; the latter is prohibited because exact Occlusion has no meaningful computational fidelity knob.","corrupt_artifacts_persisted":len(artifacts),"corrupt_evaluations_persisted":len(evaluations),"corrupt_artifacts_sha256":sha(OUT/"CORRUPT_ARTIFACTS.jsonl"),"corrupt_evaluations_sha256":sha(OUT/"CORRUPT_EVALUATIONS.jsonl"),"first_unsupported_plan_row":bad,"no_l1_occlusion_artifact_created":True,"no_final_result_generated":True,"required_disposition":"Do not repair or continue original R6 after corrupt exposure; preserve this attempt and design a separately identified corrected experiment."}; payload["receipt_id"]=hashlib.sha256(canon(payload).encode()).hexdigest(); (OUT/"R6_INTERRUPTED_CORRUPT_PLAN_DEFECT_RECEIPT.json").write_text(canon(payload)+"\n"); return payload
if __name__=="__main__": print(canon(main()))
