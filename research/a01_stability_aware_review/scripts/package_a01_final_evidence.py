"""POST_EXECUTION_READ_ONLY portable A01 final evidence bundle builder."""
from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path
from research.a01_stability_aware_review.post_execution import RESULTS, ROOT, canonical, load_json, sha256

def main() -> None:
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);p.add_argument("--result-root",type=Path,default=RESULTS);a=p.parse_args();root=a.result_root
    result=load_json(root/"A01_FINAL_RESULTS.json"); files=[]
    for rel in ("PROTOCOL.md","MASTER_SPEC.md","STATISTICAL_ANALYSIS_PLAN.md","AMENDMENT_001_H1_UNDERSPECIFICATION.md","config/locked_manifest.json","config/phase0_5_manifest.json","config/phase1_5_scientific_freeze_manifest.json","config/phase1_75_executor_freeze_manifest.json","config/phase2_result_schema.json","results/phase1_validation/phase1_validation_freeze_manifest.json","results/phase1_validation/selected_runs.json","results/phase1_5_audit/PHASE1_5_AUDIT_RECEIPT.json","results/phase1_5_audit/H2_INDEPENDENT_RECOMPUTATION.json"):
        path=ROOT/rel
        if path.is_file():files.append((path,Path("research")/rel))
    for path in sorted(root.rglob("*")):
        if path.is_file():files.append((path,Path("phase2_final")/path.relative_to(root)))
    for cell in result["cells"]:
        source=ROOT/"artifacts"/"phase1-projects"/cell["dataset_id"]/cell["model_family"]/"analyses"/"final-tests"/f"{cell['final_test_id']}.json"
        files.append((source,Path("product_final_test_evidence")/cell["dataset_id"]/cell["model_family"]/source.name))
    manifest={"schema_version":1,"role":"POST_EXECUTION_READ_ONLY","contains_raw_datasets":False,"cell_count":len(result["cells"]),"files":[{"path":str(arc),"sha256":sha256(src)} for src,arc in files]}
    manifest["manifest_id"]=hashlib.sha256(canonical(manifest).encode()).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.output,"w",compression=zipfile.ZIP_DEFLATED) as bundle:
        for source,arc in files:bundle.write(source,arcname=str(arc))
        bundle.writestr("BUNDLE_MANIFEST.json",canonical(manifest)+"\n")
    print(f"A01 FINAL EVIDENCE BUNDLE {a.output} {sha256(a.output)}")

if __name__=="__main__":main()
