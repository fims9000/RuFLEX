"""Freeze Amendment 003 without rewriting earlier S03 manifests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> dict:
    tree = json.loads((CONFIG / "phase0_2_treeshap_amendment_manifest.json").read_text())
    files = [
        "AMENDMENT_003_SAMPLE_POSITION_IDENTITY.md",
        "execute_phase1_clean_baseline.py",
        "freeze_phase0_2_sample_position_amendment.py",
        "validate_phase0_2_sample_position_amendment.py",
        "config/locked_artifact_plan_phase0_2_treeshap_amendment.jsonl",
        "config/locked_execution_plan_phase0_2_treeshap_amendment.jsonl",
    ]
    value = {
        "schema_version": 1, "study": "S03",
        "status": "SAMPLE_POSITION_IDENTITY_AMENDMENT_FROZEN_COHERENT_R6_CLEAN_BASELINE_AUTHORIZED",
        "treeshap_amendment_manifest_id": tree["manifest_id"],
        "interrupted_r5_receipt": "results/phase1_clean_baseline_r5/PHASE1_R5_INTERRUPTED_RECEIPT.json",
        "benchmark_models_seen": 15,
        "benchmark_clean_explanations_seen": 176,
        "clean_baseline_frozen": False,
        "benchmark_corrupt_explanations_seen": False,
        "empirical_detection_results_seen": False,
        "final_test_accessed": False,
        "prediction_preview_source_row_semantics": "canonical_materialized_table_position",
        "file_hashes": {name: sha(ROOT / name) for name in files},
    }
    value["manifest_id"] = hashlib.sha256(canonical(value).encode()).hexdigest()
    (CONFIG / "phase0_2_sample_position_amendment_manifest.json").write_text(canonical(value) + "\n")
    return value


if __name__ == "__main__":
    print(canonical(main()))
