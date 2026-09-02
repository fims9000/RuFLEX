"""Read-only integrity validation for an extracted A01 final evidence bundle."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def main() -> None:
    p=argparse.ArgumentParser();p.add_argument("--bundle-root",type=Path,required=True);a=p.parse_args();root=a.bundle_root;manifest=json.loads((root/"BUNDLE_MANIFEST.json").read_text());errors=[]
    for item in manifest["files"]:
        path=root/item["path"]
        if not path.is_file(): errors.append(f"missing {item['path']}")
        elif hashlib.sha256(path.read_bytes()).hexdigest()!=item["sha256"]: errors.append(f"hash mismatch {item['path']}")
    result=root/"phase2_final/A01_FINAL_RESULTS.json";audit=root/"phase2_final/A01_PHASE2_INDEPENDENT_RECOMPUTATION.json";freeze=root/"phase2_final/A01_FINAL_RESULT_FREEZE_RECEIPT.json"
    if not result.is_file() or not audit.is_file() or not freeze.is_file(): errors.append("missing final read-only record")
    elif json.loads(audit.read_text()).get("status")!="INDEPENDENT_RECOMPUTATION_PASS":errors.append("audit is not PASS")
    if errors:raise SystemExit("A01 FINAL EVIDENCE BUNDLE FAIL: "+"; ".join(errors))
    print(f"A01 FINAL EVIDENCE BUNDLE PASS: {len(manifest['files'])} hashed files")
if __name__=="__main__":main()
