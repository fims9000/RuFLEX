"""Create the deterministic A01 Phase 0.5 statistical-freeze manifest."""
from __future__ import annotations

from pathlib import Path

from research.a01_stability_aware_review.core import CONFIG, canonical_json, load_json, sha256_bytes


PHASE0_IDENTITIES = {
    "protocol_sha256": "bfcb27f48f1d1aa8552cdf5465c0b89b712c3d035d58ccc9d6088dcabd500469",
    "dataset_spec_sha256": "c5bc7d8d5842067147d28263fa96ae35374fe56afd411ff2ff7a286eace44b42",
    "model_spec_sha256": "7368bdf6707e2c5c3179c0544bcea5aee5e9a28e61d05ccbf4f483397e5924ef",
    "execution_plan_sha256": "5794a27071843af36aab1ce7aa179f40681b677d7d4253edfd8c19768679aa2e",
    "phase0_manifest_id": "ac3ba69bbca49a8214156aca9cf521e0bdb517d46677b7bab027765439fe5816",
}


def build(config_root: Path = CONFIG) -> dict[str, str]:
    plan_path = config_root / "statistical_analysis_plan.json"
    plan = load_json(plan_path)
    statistical_sha = sha256_bytes(plan_path.read_bytes())
    payload = {
        "schema_version": 1, "study": "A01 — Stability-Aware Selective Review",
        "phase": "0.5", "status": "PHASE_0_5_PRE_EXECUTION_STATISTICAL_FREEZE",
        "phase0_manifest_historical_provenance": PHASE0_IDENTITIES["phase0_manifest_id"],
        "phase0_locked_identities": PHASE0_IDENTITIES,
        "statistical_analysis_plan_sha256": statistical_sha,
        "statistical_plan_status": plan.get("status"),
        "final_test_access": "FORBIDDEN_UNTIL_SEPARATE_CONFIRMATORY_AUTHORIZATION",
        "benchmark_training": "NOT_EXECUTED",
    }
    payload["phase0_5_manifest_id"] = sha256_bytes(canonical_json(payload).encode("utf-8"))
    (config_root / "phase0_5_manifest.json").write_text(canonical_json(payload) + "\n", encoding="utf-8")
    return {"statistical_analysis_plan_sha256": statistical_sha, "phase0_5_manifest_id": payload["phase0_5_manifest_id"]}


if __name__ == "__main__":
    print(canonical_json(build()))
