"""Freeze the Amendment 002 executable S03 provenance without changing Phase 0.2."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from research.s03_explanation_validation.build_phase0_2_treeshap_amendment import main as rebuild

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> dict:
    historical = json.loads((CONFIG / "phase0_2_conformance_manifest.json").read_text())
    dataset_amendment = json.loads((CONFIG / "phase0_2_dataset_id_amendment_manifest.json").read_text())
    counts = rebuild()
    files = [
        "AMENDMENT_002_TREESHAP_ADDITIVITY_EXECUTION.md",
        "build_phase0_2_treeshap_amendment.py",
        "execute_phase1_clean_baseline.py",
        "freeze_phase0_2_treeshap_amendment.py",
        "validate_phase0_2_treeshap_amendment.py",
        "config/explainer_generation_spec_treeshap_amendment.json",
        "config/locked_artifact_plan_phase0_2_treeshap_amendment.jsonl",
        "config/locked_execution_plan_phase0_2_treeshap_amendment.jsonl",
        "config/component_applicability_matrix_treeshap_amendment.json",
        "../../src/ruflex/application/evidence.py",
    ]
    value = {
        "schema_version": 1,
        "study": "S03",
        "status": "TREESHAP_EXECUTION_AMENDMENT_FROZEN_COHERENT_R5_CLEAN_BASELINE_AUTHORIZED",
        "historical_phase0_2_manifest_id": historical["manifest_id"],
        "dataset_profiling_amendment_manifest_id": dataset_amendment["manifest_id"],
        "interrupted_r4_receipt": "results/phase1_clean_baseline_r4/PHASE1_R4_INTERRUPTED_RECEIPT.json",
        "benchmark_clean_explanations_seen": True,
        "clean_baseline_frozen": False,
        "benchmark_corrupt_explanations_seen": False,
        "empirical_detection_results_seen": False,
        "final_test_accessed": False,
        "tree_shap_feature_perturbation": "tree_path_dependent",
        "tree_shap_l1_applicability": "NOT_APPLICABLE",
        "matrix_counts": counts,
        "file_hashes": {name: sha(ROOT / name) for name in files},
    }
    value["manifest_id"] = hashlib.sha256(canonical(value).encode()).hexdigest()
    (CONFIG / "phase0_2_treeshap_amendment_manifest.json").write_text(canonical(value) + "\n")
    return value


if __name__ == "__main__":
    print(canonical(main()))
