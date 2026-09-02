"""Fail-closed S03 Phase 0.2 final pre-benchmark validator."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from research.s03_explanation_validation.build_phase0_2 import main as rebuild
ROOT=Path(__file__).resolve().parent; C=ROOT/"config"
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def validate()->dict:
 m=json.loads((C/"phase0_2_conformance_manifest.json").read_text())
 assert m["original_phase0_1_manifest_id"]=="dc8153d1ddffea76b181f39b77fb02618b9dc7baecf3fad1eb06c54b0438206d"
 assert not any(m[k] for k in ("benchmark_results_seen","benchmark_explanations_generated","scientific_outcomes_seen"))
 for n,h in m["file_hashes"].items(): assert sha(ROOT/n)==h,n
 a=[json.loads(x) for x in (C/"locked_artifact_plan_phase0_2.jsonl").read_text().splitlines()]; e=[json.loads(x) for x in (C/"locked_execution_plan_phase0_2.jsonl").read_text().splitlines()]
 assert len(a)==6072 and sum(x["artifact_role"]=="CLEAN" for x in a)==264 and sum(x["artifact_role"]=="CORRUPT" for x in a)==5808
 assert len(e)==18216 and sum(x["artifact_role"]=="CLEAN" for x in e)==792 and sum(x["artifact_role"]=="CORRUPT" for x in e)==17424
 assert len({x["execution_id"] for x in e})==len(e)
 assert all(x["clean_artifact_key"] and x["pair_id"] for x in e)
 q=json.loads((C/"quantus_synthetic_preflight.json").read_text()); assert q["state"]=="AVAILABLE" and q["quantus_version"]=="0.6.0" and len(q["routes"])==11
 native=json.loads((C/"synthetic_native_e2e_receipt.json").read_text()); assert len(native["subtype_outcomes"])==19 and all(not x["unhandled_exception"] for x in native["subtype_outcomes"])
 assert all(x["fresh_native_generation"] for x in native["l1_outcomes"])
 assert json.loads((C/"environment_lock.json").read_text())["packages"]["quantus"]=="0.6.0"
 assert not (ROOT/"results").exists()
 before=sha(C/"locked_execution_plan_phase0_2.jsonl"); rebuild(); assert sha(C/"locked_execution_plan_phase0_2.jsonl")==before
 return {"status":"PASS","clean_evaluations":792,"corrupt_evaluations":17424,"total_evaluations":18216,"benchmark_results_seen":False}
if __name__=="__main__":print(json.dumps(validate(),sort_keys=True))
