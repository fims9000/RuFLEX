"""Freeze Phase 0.2 without rewriting earlier manifests."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent; C=ROOT/"config"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(x):return json.dumps(x,sort_keys=True,separators=(",",":"))
def main():
 files=["PRE_EXECUTION_PHASE0_2_AUDIT.md","build_phase0_2.py","sample_selection.py","run_synthetic_native_e2e.py","run_quantus_synthetic_preflight.py","freeze_environment.py","freeze_phase0_2.py","validate_phase0_2.py","config/matrix_phase0_2.json","config/validator_spec_phase0_2.json","config/quantus_spec_phase0_2.json","config/locked_artifact_plan_phase0_2.jsonl","config/locked_execution_plan_phase0_2.jsonl","config/component_applicability_matrix.json","config/localization_oracle_phase0_2.json","config/quantus_synthetic_preflight.json","config/synthetic_native_e2e_receipt.json","config/environment_lock.json","config/corruption_spec_phase0_1.json","config/model_specs.json","config/explainer_generation_spec.json","../../src/ruflex/domain/evidence.py","../../src/ruflex/application/evidence.py","corruptions/library.py"]
 p={"schema_version":1,"study":"S03","status":"PHASE0_2_FINAL_PRE_BENCHMARK_EXECUTABILITY_FROZEN","original_phase0_1_manifest_id":"dc8153d1ddffea76b181f39b77fb02618b9dc7baecf3fad1eb06c54b0438206d","benchmark_results_seen":False,"benchmark_explanations_generated":False,"scientific_outcomes_seen":False,"file_hashes":{f:sha(ROOT/f) for f in files},"clean_artifacts":264,"corrupt_artifacts":5808,"clean_evaluations":792,"corrupt_evaluations":17424,"total_evaluations":18216};p["manifest_id"]=hashlib.sha256(canon(p).encode()).hexdigest();(C/"phase0_2_conformance_manifest.json").write_text(canon(p)+"\n");return p
if __name__=="__main__":print(canon(main()))
