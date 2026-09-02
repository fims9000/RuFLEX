"""Create the immutable-style Phase 0.1 conformance manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"

def canonical(value: object) -> str: return json.dumps(value, sort_keys=True, separators=(",", ":"))
def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> dict:
    files = [
        "PRE_EXECUTION_IMPLEMENTATION_AUDIT.md", "PROTOCOL_PHASE0_1_ADDENDUM.md", "STATISTICAL_ANALYSIS_PLAN_PHASE0_1_ADDENDUM.md",
        "config/dataset_specs.json", "config/model_specs.json", "config/explainer_generation_spec.json", "config/validator_spec.json",
        "config/quantus_spec.json", "config/quantus_preflight_receipt.json", "config/corruption_spec_phase0_1.json",
        "config/applicability_matrix.json", "config/localization_oracle.json", "config/locked_artifact_plan.jsonl",
        "config/locked_execution_plan_phase0_1.jsonl", "config/synthetic_conformance_receipt.json",
        "build_phase0_1.py", "freeze_phase0_1.py", "validate_phase0_1.py", "run_synthetic_conformance.py",
        "corruptions/library.py", "requirements-optional.txt", "../../src/ruflex/domain/evidence.py", "../../src/ruflex/application/evidence.py",
    ]
    phase0 = json.loads((CONFIG / "phase0_manifest.json").read_text())
    payload = {
        "schema_version": 1, "study": "S03", "status": "PHASE0_1_CONFORMANCE_FROZEN_NO_BENCHMARK_RESULTS",
        "original_phase0_manifest_id": "3fcccf0a49a6026084577476865b4bfd4a6660f18450dffacd4ee7bf9be371b4",
        "original_phase0_hashes": phase0["hashes"],
        "benchmark_results_seen": False, "benchmark_explanations_generated": False, "scientific_outcomes_seen": False,
        "file_hashes": {name: sha(ROOT / name) for name in files},
        "old_execution_plan_rows": 18216,
        "new_execution_plan_rows": sum(1 for _ in (CONFIG / "locked_execution_plan_phase0_1.jsonl").open()),
        "new_artifact_plan_rows": sum(1 for _ in (CONFIG / "locked_artifact_plan.jsonl").open()),
    }
    payload["manifest_id"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
    (CONFIG / "phase0_1_conformance_manifest.json").write_text(canonical(payload) + "\n", encoding="utf-8")
    return payload

if __name__ == "__main__": print(canonical(main()))
