"""Freeze Phase 2 executor code without modifying the Phase 1.5 manifest."""
from __future__ import annotations
import hashlib,json
from research.a01_stability_aware_review.core import CONFIG,ROOT,canonical_json,sha256_file
def build()->dict:
 prior=json.loads((CONFIG/"phase1_5_scientific_freeze_manifest.json").read_text())
 files={"phase2_executor_sha256":sha256_file(ROOT/"scripts/execute_phase2_final_test.py"),"statistics_sha256":sha256_file(ROOT/"statistics.py"),"result_schema_sha256":sha256_file(CONFIG/"phase2_result_schema.json"),"dry_run_fixture_sha256":sha256_file(ROOT/"scripts/phase2_synthetic_dry_run.py")}
 value={"schema_version":1,"study":"A01","phase":"1.75","phase1_5_manifest_id":prior["manifest_id"],"phase1_5_manifest_sha256":sha256_file(CONFIG/"phase1_5_scientific_freeze_manifest.json"),"executor_bindings":files,"final_test_status":"CLOSED","authorization_record":"EXTERNAL_ONLY_NOT_CREATED"};value["manifest_id"]=hashlib.sha256(canonical_json(value).encode()).hexdigest();(CONFIG/"phase1_75_executor_freeze_manifest.json").write_text(canonical_json(value)+"\n");return value
if __name__=="__main__":print(canonical_json(build()))
