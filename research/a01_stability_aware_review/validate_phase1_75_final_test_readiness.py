"""Fail-closed pre-unlock validator for the completed Phase 2 executor."""
from __future__ import annotations
import json
from pathlib import Path
from research.a01_stability_aware_review.core import CONFIG,ROOT,sha256_file
def validate()->list[str]:
 errors=[]; prior=json.loads((CONFIG/"phase1_5_scientific_freeze_manifest.json").read_text()); manifest=json.loads((CONFIG/"phase1_75_executor_freeze_manifest.json").read_text()); source=(ROOT/"scripts/execute_phase2_final_test.py").read_text()
 if manifest.get("phase1_5_manifest_id")!=prior.get("manifest_id"):errors.append("Phase 1.5 identity mismatch")
 for name,path in {"phase2_executor_sha256":ROOT/"scripts/execute_phase2_final_test.py","statistics_sha256":ROOT/"statistics.py","result_schema_sha256":CONFIG/"phase2_result_schema.json","dry_run_fixture_sha256":ROOT/"scripts/phase2_synthetic_dry_run.py"}.items():
  if manifest["executor_bindings"].get(name)!=sha256_file(path):errors.append(f"stale {name}")
 for forbidden in ("train_model","create_training_study","select_validation_threshold","create_selective_policy","create_stability_gate_policy"):
  if forbidden in source:errors.append(f"forbidden Phase 2 call: {forbidden}")
 if "evaluate_final_test" not in source or "paired_bootstrap_policy_metrics" not in source:errors.append("executor is incomplete")
 if not (ROOT/"AMENDMENT_001_H1_UNDERSPECIFICATION.md").exists():errors.append("H1 amendment missing")
 if (ROOT/"artifacts/phase1-projects").exists():
  count=sum(1 for _ in (ROOT/"artifacts/phase1-projects").rglob("runs/*.json") if _.name!="active-training-run.json")
  if count<300:errors.append("fewer than 300 frozen runs")
 for name in ("A01_FINAL_TEST_UNLOCK.json","FINAL_TEST_OPENING_RECEIPT.json","A01_FINAL_RESULTS.json"):
  if any(ROOT.rglob(name)):errors.append(f"real A01 final-test artifact exists: {name}")
 return errors
if __name__=="__main__":
 e=validate()
 if e:raise SystemExit("FAIL: "+"; ".join(e))
 print("PASS: Phase 1.75 executor frozen and A01 final test remains closed")
