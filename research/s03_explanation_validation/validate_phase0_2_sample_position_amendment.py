"""Fail-closed pre-R6 validator for Amendment 003."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict:
    manifest = json.loads((CONFIG / "phase0_2_sample_position_amendment_manifest.json").read_text())
    assert manifest["status"] == "SAMPLE_POSITION_IDENTITY_AMENDMENT_FROZEN_COHERENT_R6_CLEAN_BASELINE_AUTHORIZED"
    for name, digest in manifest["file_hashes"].items():
        assert sha(ROOT / name) == digest, f"AMENDMENT_003_IDENTITY_MISMATCH:{name}"
    r5 = json.loads((ROOT / manifest["interrupted_r5_receipt"]).read_text())
    assert r5["benchmark_clean_explanations_generated_before_stop"] == 176
    assert r5["benchmark_corrupt_artifacts_generated"] == 0 and not r5["final_test_accessed"]
    table = pd.read_csv(ROOT.parent / "a01_stability_aware_review" / "artifacts" / "phase1-data" / "materialized" / "wisconsin_diagnostic" / "canonical.csv")
    assert int(table.iloc[37]["diagnosis"]) == 0
    assert int(table.iloc[37]["id"]) != 37
    assert not (ROOT / "results" / "phase1_clean_baseline_r6" / "PHASE1_CLEAN_FREEZE_MANIFEST.json").exists()
    return {"status": "PASS", "r5_interrupted_clean_artifacts": 176, "r6_final_test_accessed": False}


if __name__ == "__main__":
    print(json.dumps(validate(), sort_keys=True))
