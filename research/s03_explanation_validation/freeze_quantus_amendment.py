"""Freeze the authorized R6 Quantus semantics amendment without rewriting CLEAN."""
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CONFIG=ROOT/"config"; RESULTS=ROOT/"results"/"quantus_amendment_r6"; CLEAN=ROOT/"results"/"phase1_clean_baseline_r6"
def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    clean=json.loads((CLEAN/"PHASE1_CLEAN_FREEZE_MANIFEST.json").read_text())
    refreeze=json.loads((RESULTS/"R6_CLEAN_QUANTUS_DETERMINISTIC_REFREEZE.json").read_text())
    files=["S03_AMENDMENT_QUANTUS_RNG_TARGET_SEMANTICS.md","quantus_execution.py","execute_quantus_amendment.py","execute_corrupt_matrix.py","config/quantus_spec_phase0_2.json","config/validator_spec_phase0_2.json","config/corruption_spec_phase0_1.json","STATISTICAL_ANALYSIS_PLAN.md","STATISTICAL_ANALYSIS_PLAN_PHASE0_1_ADDENDUM.md"]
    value={"schema_version":1,"study":"S03","status":"QUANTUS_RNG_TARGET_SEMANTICS_AMENDMENT_FROZEN","r6_clean_manifest_id":clean["manifest_id"],"phase0_2_dataset_id_amendment_manifest_id":json.loads((CONFIG/"phase0_2_dataset_id_amendment_manifest.json").read_text())["manifest_id"],"phase0_2_treeshap_amendment_manifest_id":json.loads((CONFIG/"phase0_2_treeshap_amendment_manifest.json").read_text())["manifest_id"],"phase0_2_sample_position_amendment_manifest_id":json.loads((CONFIG/"phase0_2_sample_position_amendment_manifest.json").read_text())["manifest_id"],"base_seed":3003,"seed_rule":"uint32(first_32_bits(SHA256('S03|R6|3003|'+clean_artifact_key+'|'+metric_name)))","target_model_rule":"resolve(contract.run_id)","clean_quantus_refreeze_id":refreeze["refreeze_id"],"clean_quantus_refreeze_sha256":sha(RESULTS/"R6_CLEAN_QUANTUS_DETERMINISTIC_REFREEZE.json"),"component_applicability_sha256":sha(RESULTS/"quantus_component_applicability_r6.jsonl"),"unchanged_metric_inventory_sha256":sha(CONFIG/"quantus_spec_phase0_2.json"),"unchanged_corruption_spec_sha256":sha(CONFIG/"corruption_spec_phase0_1.json"),"file_hashes":{f:sha(ROOT/f) for f in files}}
    value["manifest_id"]=hashlib.sha256(canon(value).encode()).hexdigest(); (CONFIG/"quantus_rng_target_amendment_manifest.json").write_text(canon(value)+"\n"); return value
if __name__=="__main__": print(canon(main()))
