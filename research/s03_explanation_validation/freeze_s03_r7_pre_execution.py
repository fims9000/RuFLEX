from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from research.s03_explanation_validation.validate_s03_r7_pre_execution import validate
ROOT=Path(__file__).resolve().parent; C=ROOT/"config"; CLEAN=ROOT/"results"/"phase1_clean_baseline_r6"; R6=ROOT/"results"/"phase2_corrupt_r6"; Q=ROOT/"results"/"quantus_amendment_r6"
def canon(x):return json.dumps(x,sort_keys=True,separators=(",",":"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert validate()["status"]=="PASS"
    files=["S03_AMENDMENT_R7_L1_OCCLUSION_APPLICABILITY.md","build_s03_r7_plan.py","validate_s03_r7_pre_execution.py","execute_s03_r7_corrupt_matrix.py","config/s03_r7_artifact_plan.jsonl","config/s03_r7_evaluation_plan.jsonl","config/s03_r7_non_executable_conditions.jsonl"]
    x={"schema_version":1,"study":"S03-R7","status":"R7_PRE_EXECUTION_FROZEN","created_at":datetime.now(timezone.utc).isoformat(),"r6_clean_manifest_id":json.loads((CLEAN/"PHASE1_CLEAN_FREEZE_MANIFEST.json").read_text())["manifest_id"],"r6_interruption_receipt_sha256":sha(R6/"R6_INTERRUPTED_CORRUPT_PLAN_DEFECT_RECEIPT.json"),"quantus_amendment_manifest_id":json.loads((C/"quantus_rng_target_amendment_manifest.json").read_text())["manifest_id"],"r7_corrupt_artifacts":5232,"r7_corrupt_evaluations":15696,"artifact_level_not_applicable":576,"file_hashes":{f:sha(ROOT/f) for f in files}}
    x["manifest_id"]=hashlib.sha256(canon(x).encode()).hexdigest(); (C/"S03_R7_PRE_EXECUTION_MANIFEST.json").write_text(canon(x)+"\n");return x
if __name__=="__main__":print(canon(main()))
