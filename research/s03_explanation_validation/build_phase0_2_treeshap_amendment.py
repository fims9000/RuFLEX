"""Build the Amendment 002 S03 plan without rewriting historical Phase 0.2 files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from research.s03_explanation_validation import build_phase0_2 as historical

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _components(explainer: str, family: str, subtype: str, mode: str, quantus_state: str) -> list[dict]:
    rows = historical.components(explainer, family, subtype, mode, quantus_state)
    if family == "L1_LOW_FIDELITY" and explainer == "tree_shap":
        for row in rows:
            row["state"] = "NOT_APPLICABLE"
            row["reason"] = "TreeSHAP uses tree-path-dependent persisted node frequencies; no finite reduced-budget route exists."
    return rows


def main() -> dict:
    matrix = json.loads((CONFIG / "matrix_phase0_2.json").read_text())
    corrupt = json.loads((CONFIG / "corruption_spec_phase0_1.json").read_text())
    preflight = json.loads((CONFIG / "quantus_synthetic_preflight.json").read_text())
    quantus_state = "AVAILABLE" if preflight.get("state") == "AVAILABLE" else "NOT_AVAILABLE"
    artifacts: list[dict] = []
    evaluations: list[dict] = []
    applicability: list[dict] = []
    for dataset in matrix["datasets"]:
        for model, explainers in matrix["models"].items():
            for explainer in explainers:
                for slot in range(matrix["samples_per_dataset_model"]):
                    clean_key = historical.key("clean", dataset, model, explainer, slot)
                    clean = {
                        "artifact_key": clean_key, "clean_artifact_key": clean_key,
                        "pair_id": historical.key("clean-pair", dataset, model, explainer, slot),
                        "artifact_role": "CLEAN", "dataset_id": dataset, "model_family": model,
                        "explainer": explainer, "sample_slot": slot, "failure_family": "CLEAN",
                        "failure_subtype": "clean", "severity": "NONE",
                        "effective_severity_parameters": {"severity": "NONE"},
                        "expected_applicability": "APPLICABLE", "expected_localization_component": None,
                        "artifact_execution": "fresh_product_native_clean_explanation",
                        "benchmark_execution_forbidden": True,
                    }
                    conditions = [clean]
                    for family, detail in corrupt["families"].items():
                        for subtype in detail["subtypes"]:
                            for severity in historical.severity_values(detail):
                                is_tree_l1 = family == "L1_LOW_FIDELITY" and explainer == "tree_shap"
                                if family == "L1_LOW_FIDELITY" and explainer == "occlusion":
                                    state, reason = "NOT_APPLICABLE", "L1 unavailable for exact occlusion route."
                                elif is_tree_l1:
                                    state, reason = "NOT_APPLICABLE", "TreeSHAP has no finite reduced-budget route under Amendment 002."
                                else:
                                    state, reason = "APPLICABLE", "Declared contract/explainer route."
                                conditions.append({
                                    "artifact_key": historical.key("corrupt", dataset, model, explainer, slot, family, subtype, severity),
                                    "clean_artifact_key": clean_key,
                                    "pair_id": historical.key("pair", dataset, model, explainer, slot, family, subtype, severity),
                                    "artifact_role": "CORRUPT", "dataset_id": dataset, "model_family": model,
                                    "explainer": explainer, "sample_slot": slot, "failure_family": family,
                                    "failure_subtype": subtype, "severity": severity,
                                    "effective_severity_parameters": historical.effective(family, subtype, severity),
                                    "expected_applicability": state, "applicability_reason": reason,
                                    "expected_localization_component": historical.expected_component(family, subtype),
                                    "artifact_execution": "NOT_APPLICABLE_NO_ARTIFACT" if is_tree_l1 else ("fresh_product_native_reduced_budget_explanation" if family == "L1_LOW_FIDELITY" else "clean_contract_one_violation_mutation"),
                                    "benchmark_execution_forbidden": True,
                                })
                    for artifact in conditions:
                        if artifact["artifact_role"] == "CORRUPT":
                            artifacts.append(artifact)
                        for mode in matrix["validator_modes"]:
                            row = dict(artifact)
                            row["validator_mode"] = mode
                            row["execution_id"] = historical.key("evaluation", artifact["artifact_key"], mode)
                            row["component_applicability"] = _components(explainer, artifact["failure_family"], artifact["failure_subtype"], mode, quantus_state)
                            evaluations.append(row)
                            applicability.extend({"dataset_id": dataset, "model_family": model, "explainer": explainer, "failure_family": artifact["failure_family"], "failure_subtype": artifact["failure_subtype"], "validator_mode": mode, **component} for component in row["component_applicability"])
    clean_artifacts = [row for row in evaluations if row["artifact_role"] == "CLEAN"]
    if len(artifacts) != 5808 or len(clean_artifacts) != 792 or len(evaluations) != 18216:
        raise RuntimeError(f"AMENDMENT_002_PLAN_COUNT_MISMATCH:{len(artifacts)}/{len(clean_artifacts)}/{len(evaluations)}")
    clean_artifact_rows = [
        row for row in evaluations
        if row["artifact_role"] == "CLEAN" and row["validator_mode"] == matrix["validator_modes"][0]
    ]
    (CONFIG / "locked_artifact_plan_phase0_2_treeshap_amendment.jsonl").write_text(
        "".join(canonical(row) + "\n" for row in artifacts + clean_artifact_rows)
    )
    (CONFIG / "locked_execution_plan_phase0_2_treeshap_amendment.jsonl").write_text("".join(canonical(row) + "\n" for row in evaluations))
    unique = {canonical(row): row for row in applicability}
    (CONFIG / "component_applicability_matrix_treeshap_amendment.json").write_text(canonical({"schema_version": 3, "rows": list(unique.values())}) + "\n")
    return {"clean_artifacts": 264, "corrupt_artifacts": 5808, "clean_evaluations": 792, "corrupt_evaluations": 17424, "evaluations": 18216}


if __name__ == "__main__":
    print(canonical(main()))
