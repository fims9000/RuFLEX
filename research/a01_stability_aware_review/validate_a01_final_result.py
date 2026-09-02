"""Read-only A01 Phase 2.1 final-result validator."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime
from pathlib import Path

from research.a01_stability_aware_review.post_execution import RESULTS, ROOT, load_json, sha256

def main() -> None:
    p=argparse.ArgumentParser();p.add_argument("--result-root",type=Path,default=RESULTS);a=p.parse_args();root=a.result_root;errors=[]
    required=["A01_FINAL_RESULTS.json","A01_FINAL_TEST_UNLOCK.json","FINAL_TEST_OPENING_RECEIPT.json","A01_PHASE2_INDEPENDENT_RECOMPUTATION.json","A01_FINAL_RESULTS.md","A01_FINAL_RESULT_FREEZE_MANIFEST.json","A01_FINAL_RESULT_FREEZE_RECEIPT.json"]
    for name in required:
        if not (root/name).is_file():errors.append(f"missing {name}")
    if errors: raise SystemExit("A01 FINAL VALIDATOR FAIL: "+"; ".join(errors))
    result=load_json(root/"A01_FINAL_RESULTS.json"); audit=load_json(root/"A01_PHASE2_INDEPENDENT_RECOMPUTATION.json"); manifest=load_json(root/"A01_FINAL_RESULT_FREEZE_MANIFEST.json"); receipt=load_json(root/"A01_FINAL_RESULT_FREEZE_RECEIPT.json");opening=load_json(root/"FINAL_TEST_OPENING_RECEIPT.json")
    if len(result.get("cells",[])) != 15:errors.append("expected 15 result cells")
    if audit.get("status") != "INDEPENDENT_RECOMPUTATION_PASS" or audit.get("mismatches"): errors.append("independent recomputation failed")
    if manifest.get("immutable_result_json_sha256") != sha256(root/"A01_FINAL_RESULTS.json"):errors.append("immutable result JSON hash mismatch")
    if manifest.get("opening_receipt_sha256") != sha256(root/"FINAL_TEST_OPENING_RECEIPT.json"):errors.append("opening receipt hash mismatch")
    if receipt.get("final_result_manifest_id") != manifest.get("manifest_id") or receipt.get("independent_audit") != "PASS":errors.append("freeze receipt mismatch")
    statuses={"SUPPORTS_H3":0,"CONTRADICTS_H3":0,"INCONCLUSIVE":0,"NOT_ASSESSABLE":0}
    ids=set(); opened=datetime.fromisoformat(opening["opened_at"].replace("Z","+00:00"))
    forbidden=("runs","studies","evaluations","calibrations","thresholds","selective-policies","stability-analyses","stability-gates")
    for cell in result["cells"]:
        key=(cell["dataset_id"],cell["model_family"])
        if key in ids:errors.append(f"duplicate cell {key}")
        ids.add(key);statuses[cell["h3_status"]]=statuses.get(cell["h3_status"],0)+1
        ci=cell["bootstrap"]["delta_risk"]["percentile_ci_95"]
        expected="NOT_ASSESSABLE" if ci is None else ("SUPPORTS_H3" if ci[1]<0 else "CONTRADICTS_H3" if ci[0]>0 else "INCONCLUSIVE")
        if cell["h3_status"] != expected:errors.append(f"H3 classification mismatch {key}")
        path=ROOT/"artifacts"/"phase1-projects"/cell["dataset_id"]/cell["model_family"]/"analyses"/"final-tests"/f"{cell['final_test_id']}.json"
        if not path.is_file():errors.append(f"missing FinalTestEvaluation {key}")
        elif load_json(path).get("final_test_id") != cell["final_test_id"]:errors.append(f"FinalTestEvaluation identity mismatch {key}")
        project=path.parents[2]
        for folder in forbidden:
            for obj in project.glob(f"**/{folder}/*.json"):
                try: created=load_json(obj).get("created_at")
                except json.JSONDecodeError: continue
                if created and datetime.fromisoformat(created.replace("Z","+00:00")) > opened: errors.append(f"post-opening frozen-object mutation {obj}")
    for name in ("T05_final_test_policy_outcomes.csv","T06_h3_effects.csv","T07_ai4i_fnr.csv","T08_final_scientific_status.csv"):
        expected_hash=manifest.get("tables",{}).get(name)
        if expected_hash != sha256(root/"tables"/name):errors.append(f"table hash mismatch {name}")
    for name, digest in manifest.get("figures",{}).items():
        if digest != sha256(root/"figures"/name):errors.append(f"figure hash mismatch {name}")
    h2=load_json(ROOT/"results/phase1_5_audit/PHASE1_5_AUDIT_RECEIPT.json").get("h2_counts",{})
    if h2.get("PATTERN_OBSERVED") != 4 or h2.get("PATTERN_NOT_OBSERVED") != 11:errors.append("frozen H2 interpretation missing")
    if errors: raise SystemExit("A01 FINAL VALIDATOR FAIL: "+"; ".join(errors))
    print("A01 FINAL VALIDATOR PASS", json.dumps({"cells":len(ids),"h3":statuses,"post_opening_timestamp_audit":"PASS"},sort_keys=True))

if __name__=="__main__":main()
