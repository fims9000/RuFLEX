"""Fail-closed validator for S03 Amendment 002 before R5 model fitting."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from research.s03_explanation_validation.build_phase0_2_treeshap_amendment import main as rebuild

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict:
    manifest = json.loads((CONFIG / "phase0_2_treeshap_amendment_manifest.json").read_text())
    assert manifest["status"] == "TREESHAP_EXECUTION_AMENDMENT_FROZEN_COHERENT_R5_CLEAN_BASELINE_AUTHORIZED"
    for name, digest in manifest["file_hashes"].items():
        assert sha(ROOT / name) == digest, f"AMENDMENT_002_IDENTITY_MISMATCH:{name}"
    execution = CONFIG / "locked_execution_plan_phase0_2_treeshap_amendment.jsonl"
    before = sha(execution)
    counts = rebuild()
    assert sha(execution) == before, "AMENDMENT_002_PLAN_NONDETERMINISTIC"
    assert counts == {"clean_artifacts": 264, "corrupt_artifacts": 5808, "clean_evaluations": 792, "corrupt_evaluations": 17424, "evaluations": 18216}
    rows = [json.loads(line) for line in execution.read_text().splitlines()]
    tree_l1 = [row for row in rows if row["failure_family"] == "L1_LOW_FIDELITY" and row["explainer"] == "tree_shap"]
    assert tree_l1 and all(row["expected_applicability"] == "NOT_APPLICABLE" for row in tree_l1)
    assert all(row["artifact_execution"] == "NOT_APPLICABLE_NO_ARTIFACT" for row in tree_l1)
    receipt = json.loads((ROOT / manifest["interrupted_r4_receipt"]).read_text())
    assert receipt["benchmark_clean_explanations_generated_before_stop"] == 175
    assert receipt["benchmark_corrupt_artifacts_generated"] == 0
    r5 = ROOT / "results" / "phase1_clean_baseline_r5"
    assert not (r5 / "PHASE1_CLEAN_FREEZE_MANIFEST.json").exists(), "R5_ALREADY_FROZEN"
    return {"status": "PASS", "tree_shap_feature_perturbation": "tree_path_dependent", **counts}


if __name__ == "__main__":
    print(json.dumps(validate(), sort_keys=True))
