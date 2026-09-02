"""Build deterministic S03 Phase 0.1 plans; never materializes benchmark data."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"
OLD_PLAN_ROWS = 18_216


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(*parts: object) -> str:
    return hashlib.sha256(canonical(parts).encode()).hexdigest()[:24]


def severity_values(detail: dict) -> list[str]:
    return detail.get("severity_levels", ["NONE"])


def applicability(*, explainer: str, family: str, subtype: str) -> tuple[str, str]:
    if family == "L1_LOW_FIDELITY" and explainer == "occlusion":
        return "NOT_APPLICABLE", "Occlusion has no declared computational-fidelity budget."
    if family == "L1_LOW_FIDELITY" and explainer not in {"integrated_gradients", "gradient_shap", "permutation_shap", "tree_shap"}:
        return "NOT_APPLICABLE", "No frozen product-native reduced-budget explainer route."
    if family == "R1_REFERENCE_BACKGROUND_MISMATCH" and explainer == "occlusion":
        return "APPLICABLE", "Occlusion has a train-derived reference declaration."
    return "APPLICABLE", "Declared product contract/explainer route supports this condition."


def expected_component(family: str, subtype: str) -> str:
    return {
        ("M1_MODEL_MISMATCH", "artifact_sha_swap"): "model_identity",
        ("M1_MODEL_MISMATCH", "run_identity_swap"): "model_identity",
        ("P1_PREPROCESSING_MISMATCH", "preprocessing_identity_swap"): "preprocessing_identity",
        ("P1_PREPROCESSING_MISMATCH", "feature_order_identity_swap"): "feature_order_identity",
        ("S1_SAMPLE_TARGET_MISMATCH", "sample_identity_swap"): "sample_target_identity",
        ("S1_SAMPLE_TARGET_MISMATCH", "target_identity_swap"): "sample_target_identity",
        ("R1_REFERENCE_BACKGROUND_MISMATCH", "reference_identity_swap"): "reference_identity",
        ("A1_ATTRIBUTION_MUTATION", "additive_noise"): "repeatability",
        ("A1_ATTRIBUTION_MUTATION", "sign_flip"): "repeatability",
        ("A1_ATTRIBUTION_MUTATION", "permutation"): "repeatability",
        ("L1_LOW_FIDELITY", "reduced_budget"): "external_quantus_or_replay_integrity",
        ("ADV_EXPLAINER_AWARE", "structurally_valid_attribution_permutation"): "external_quantus_or_replay_integrity",
    }[(family, subtype)]


def effective_parameters(family: str, subtype: str, severity: str) -> dict:
    if severity == "NONE":
        return {"severity": "NONE"}
    fraction = {"LOW": 0.05, "MEDIUM": 0.25, "HIGH": 0.75}[severity]
    if family == "A1_ATTRIBUTION_MUTATION" and subtype == "additive_noise":
        return {"severity": severity, "fraction": fraction, "delta_formula": "severity*max(max_abs_clean_attribution,1e-12)", "rademacher_seeded": True}
    if (family == "A1_ATTRIBUTION_MUTATION" and subtype in {"sign_flip", "permutation"}) or family == "ADV_EXPLAINER_AWARE":
        return {"severity": severity, "fraction": fraction, "effective_k_rule": "max(2,min(n_features,ceil(severity*n_features)))", "duplicate_equivalence": "NOT_APPLICABLE"}
    if family == "L1_LOW_FIDELITY":
        return {"severity": severity, "fraction": fraction, "budget_rule": "max(method_minimum,round(clean_budget*(1-severity)))"}
    return {"severity": severity, "fraction": fraction}


def main(*, write_preflight: bool = True) -> dict:
    matrix = json.loads((CONFIG / "matrix.json").read_text())
    corrupt = json.loads((CONFIG / "corruption_spec_phase0_1.json").read_text())
    validator = json.loads((CONFIG / "validator_spec.json").read_text())
    artifact_rows: list[dict] = []
    evaluation_rows: list[dict] = []
    applicability_rows: list[dict] = []
    oracle: dict[str, dict] = {}
    for family, detail in corrupt["families"].items():
        for subtype in detail["subtypes"]:
            component = expected_component(family, subtype)
            oracle[f"{family}/{subtype}"] = {"expected_component": component, "acceptable_native_reason_names": [component], "generic_failed_is_localized": False}
    for dataset in matrix["datasets"]:
        for model, explainers in matrix["models"].items():
            for explainer in explainers:
                for sample_slot in range(matrix["samples_per_dataset_model"]):
                    clean_key = key("clean", dataset, model, explainer, sample_slot)
                    for family, detail in corrupt["families"].items():
                        for subtype in detail["subtypes"]:
                            for severity in severity_values(detail):
                                state, reason = applicability(explainer=explainer, family=family, subtype=subtype)
                                pair_id = key("pair", dataset, model, explainer, sample_slot, family, subtype, severity)
                                artifact_key = key("corrupt", pair_id)
                                artifact = {
                                    "artifact_key": artifact_key, "pair_id": pair_id, "clean_artifact_key": clean_key,
                                    "dataset_id": dataset, "model_family": model, "explainer": explainer, "sample_slot": sample_slot,
                                    "failure_family": family, "failure_subtype": subtype, "severity": severity,
                                    "effective_severity_parameters": effective_parameters(family, subtype, severity),
                                    "expected_applicability": state, "applicability_reason": reason,
                                    "expected_localization_component": expected_component(family, subtype),
                                    "artifact_execution": "fresh_product_native_reduced_budget_explanation" if family == "L1_LOW_FIDELITY" else "clean_contract_one_violation_mutation",
                                    "benchmark_execution_forbidden": True,
                                }
                                artifact_rows.append(artifact)
                                for mode in validator["modes"]:
                                    row = dict(artifact)
                                    row["execution_id"] = key("evaluation", artifact_key, mode)
                                    row["validator_mode"] = mode
                                    row["repeat_identity"] = 0
                                    evaluation_rows.append(row)
                                    applicability_rows.append({"model_family": model, "explainer": explainer, "failure_family": family, "failure_subtype": subtype, "validator_mode": mode, "state": state, "reason": reason})
    for name, rows in (("locked_artifact_plan.jsonl", artifact_rows), ("locked_execution_plan_phase0_1.jsonl", evaluation_rows)):
        (CONFIG / name).write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")
    unique_applicability = {canonical(row): row for row in applicability_rows}
    (CONFIG / "applicability_matrix.json").write_text(canonical({"schema_version": 1, "rows": list(unique_applicability.values())}) + "\n", encoding="utf-8")
    (CONFIG / "localization_oracle.json").write_text(canonical({"schema_version": 1, "oracle": oracle}) + "\n", encoding="utf-8")
    if write_preflight:
        quantus_available = importlib.util.find_spec("quantus") is not None
        (CONFIG / "quantus_preflight_receipt.json").write_text(canonical({"schema_version": 1, "synthetic_only": True, "benchmark_accessed": False, "quantus_0_6_0_available": quantus_available, "state": "AVAILABLE" if quantus_available else "NOT_AVAILABLE", "reason": "quantus==0.6.0 unavailable in isolated research environment" if not quantus_available else "Synthetic compatibility must be executed by test environment"}) + "\n", encoding="utf-8")
    return {"artifact_rows": len(artifact_rows), "evaluation_rows": len(evaluation_rows), "old_evaluation_rows": OLD_PLAN_ROWS}


if __name__ == "__main__":
    print(canonical(main()))
