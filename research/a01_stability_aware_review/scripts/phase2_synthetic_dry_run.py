"""Exercise Phase 2 result primitives with synthetic, non-A01 data only."""
from __future__ import annotations

from research.a01_stability_aware_review.statistics import accepted_case_risk, paired_bootstrap_delta_risk


def dry_run() -> dict:
    truth = [0, 1, 1, 0, 1, 0, 1, 0]
    selected_prediction = [0, 1, 0, 0, 1, 1, 1, 0]
    stability = ["ACCEPT", "ACCEPT", "REVIEW", "ACCEPT", "ACCEPT", "REVIEW", "ACCEPT", "ACCEPT"]
    confidence = ["ACCEPT", "ACCEPT", "ACCEPT", "ACCEPT", "ACCEPT", "REVIEW", "ACCEPT", "ACCEPT"]
    return {"status": "PASS", "data": "SYNTHETIC_NON_A01_NON_FINAL", "stability_risk": accepted_case_risk(truth, selected_prediction, stability).__dict__, "confidence_risk": accepted_case_risk(truth, selected_prediction, confidence).__dict__, "bootstrap": paired_bootstrap_delta_risk(truth, selected_prediction, stability, confidence, replicates=100, seed=20260902), "final_test_accessed": False}


if __name__ == "__main__": print(dry_run())
