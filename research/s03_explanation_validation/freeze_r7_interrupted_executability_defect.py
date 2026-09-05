from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent; OUT=ROOT/"results"/"s03_r7"; PLAN=ROOT/"config"/"s03_r7_artifact_plan.jsonl"
def canon(x):return json.dumps(x,sort_keys=True,separators=(",",":"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    artifacts=[json.loads(x) for x in (OUT/"R7_CORRUPT_ARTIFACTS.jsonl").read_text().splitlines() if x]; evaluations=[json.loads(x) for x in (OUT/"R7_CORRUPT_EVALUATIONS.jsonl").read_text().splitlines() if x];done={x["r7_artifact_id"] for x in artifacts};failed=next(x for x in (json.loads(y) for y in PLAN.read_text().splitlines() if y) if x["r7_artifact_id"] not in done)
    p={"schema_version":1,"study":"S03-R7","status":"R7_INTERRUPTED_AFTER_CLEAN_PARENT_EXECUTABILITY_DEFECT","created_at":datetime.now(timezone.utc).isoformat(),"defect":"The declared A1/sign_flip corruption for an inherited CLEAN parent was semantically identical because all selected attribution values were zero. The pre-execution plan marked it executable without materializing/verifying actual clean-parent mutation distinctness.","r7_corrupt_artifacts_persisted":len(artifacts),"r7_corrupt_evaluations_persisted":len(evaluations),"artifacts_sha256":sha(OUT/"R7_CORRUPT_ARTIFACTS.jsonl"),"evaluations_sha256":sha(OUT/"R7_CORRUPT_EVALUATIONS.jsonl"),"first_failed_executable_condition":failed,"required_disposition":"Do not repair R7 after corrupt exposure. Preserve R7 as interrupted and perform any future corrected experiment only after pre-materializing every clean-parent/subtype/severity executability result before first corrupt outcome."};p["receipt_id"]=hashlib.sha256(canon(p).encode()).hexdigest();(OUT/"R7_INTERRUPTED_EXECUTABILITY_DEFECT_RECEIPT.json").write_text(canon(p)+"\n");return p
if __name__=="__main__":print(canon(main()))
