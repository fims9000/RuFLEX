"""Fail-closed validator for S03 Phase 0.1, before benchmark materialization."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from research.s03_explanation_validation.build_phase0_1 import main as rebuild

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"
PHASE0 = "3fcccf0a49a6026084577476865b4bfd4a6660f18450dffacd4ee7bf9be371b4"


def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(value: object) -> str: return json.dumps(value, sort_keys=True, separators=(",", ":"))


def validate() -> dict:
    manifest_path = CONFIG / "phase0_1_conformance_manifest.json"
    if not manifest_path.exists(): raise AssertionError("Phase 0.1 manifest is missing.")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["original_phase0_manifest_id"] == PHASE0
    assert manifest["benchmark_results_seen"] is False and manifest["benchmark_explanations_generated"] is False and manifest["scientific_outcomes_seen"] is False
    phase0 = json.loads((CONFIG / "phase0_manifest.json").read_text())
    assert phase0["manifest_id"] == PHASE0
    assert phase0["hashes"] == manifest["original_phase0_hashes"]
    for filename, expected in manifest["file_hashes"].items():
        assert sha(ROOT / filename) == expected, f"Frozen identity differs: {filename}"
    execution = [json.loads(line) for line in (CONFIG / "locked_execution_plan_phase0_1.jsonl").read_text().splitlines() if line]
    artifacts = [json.loads(line) for line in (CONFIG / "locked_artifact_plan.jsonl").read_text().splitlines() if line]
    assert len(execution) == len({row["execution_id"] for row in execution})
    assert all(row["pair_id"] and row["clean_artifact_key"] and row["artifact_key"] for row in execution)
    assert all(row["validator_mode"] in {"IDENTITY_ONLY", "METRIC_ONLY", "COMBINED"} for row in execution)
    assert len(artifacts) * 3 == len(execution)
    assert not (ROOT / "results").exists(), "Benchmark result directory exists before Phase 1."
    receipt = json.loads((CONFIG / "synthetic_conformance_receipt.json").read_text())
    assert all(row["status"] in {"PASS", "NOT_APPLICABLE"} for row in receipt["rows"])
    required = {"M1_MODEL_MISMATCH", "P1_PREPROCESSING_MISMATCH", "S1_SAMPLE_TARGET_MISMATCH", "R1_REFERENCE_BACKGROUND_MISMATCH", "A1_ATTRIBUTION_MUTATION", "L1_LOW_FIDELITY", "ADV_EXPLAINER_AWARE"}
    assert required <= {row["family"] for row in receipt["rows"]}
    before = sha(CONFIG / "locked_execution_plan_phase0_1.jsonl")
    rebuilt = rebuild(write_preflight=False)
    assert before == sha(CONFIG / "locked_execution_plan_phase0_1.jsonl"), "Execution plan rebuild is nondeterministic."
    return {"status": "PASS", "artifact_rows": len(artifacts), "evaluation_rows": len(execution), "rebuild": rebuilt, "benchmark_results_seen": False}


if __name__ == "__main__": print(canonical(validate()))
