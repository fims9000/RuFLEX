"""Validate A01 design metadata without importing data or opening final test."""
from __future__ import annotations

import json
from pathlib import Path


def validate(plan: dict) -> list[str]:
    errors: list[str] = []
    if plan.get("status") != "PRE_FREEZE_NO_FINAL_TEST_ACCESS": errors.append("plan is not marked pre-freeze")
    if plan.get("primary_protocol") != "TRAINING_VARIABILITY": errors.append("primary protocol must isolate training variability")
    seeds = plan.get("training_seeds", [])
    if len(seeds) != 20 or len(set(seeds)) != 20: errors.append("primary design requires 20 distinct training seeds")
    if plan.get("split_seed") is None: errors.append("primary design lacks fixed split seed")
    gate = plan.get("validation_only_policy", {})
    if not (.5 <= gate.get("min_confidence", -1) <= 1 and 0 < gate.get("min_class_agreement", -1) <= 1 and gate.get("max_probability_std", -1) >= 0): errors.append("invalid validation-only Stability Gate thresholds")
    if plan.get("final_test") != "FORBIDDEN_UNTIL_POLICY_AND_PROTOCOL_FREEZE": errors.append("final-test firewall is not explicit")
    return errors


if __name__ == "__main__":
    plan = json.loads((Path(__file__).parent / "config" / "pre_freeze_plan.json").read_text(encoding="utf-8"))
    issues = validate(plan)
    if issues:
        raise SystemExit("A01 pre-freeze validation failed: " + "; ".join(issues))
    print("A01 PRE-FREEZE PLAN: PASS (no final-test access)")
