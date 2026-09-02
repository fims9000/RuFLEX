"""Synthetic-only conformance receipt for every S03 Phase 0.1 subtype."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ruflex.domain.evidence import ExplanationContract, FeatureAttribution
from research.s03_explanation_validation.corruptions.library import (
    assert_one_violation, corrupt_contract, effective_severity_parameters,
    low_fidelity_generation_parameters,
)

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"


def _clean() -> ExplanationContract:
    return ExplanationContract(
        run_id="00000000-0000-0000-0000-000000000001", model_kind="logistic_regression", model_artifact_sha256="a" * 64,
        preprocessing_identity="pre", feature_order_identity="order", sample_identity="sample", reference_identity="reference",
        generation_parameters={"background_count": 24, "max_evals": 37}, sample={"x1": 1.0, "x2": 2.0, "x3": 3.0, "x4": 4.0},
        target="target", prediction=0.7, base_value=0.1, completeness_error=0.0, reference_definition="train reference",
        attributions=[
            FeatureAttribution(feature="x1", observed_value=1.0, reference_value=0.0, attribution=0.8),
            FeatureAttribution(feature="x2", observed_value=2.0, reference_value=0.0, attribution=-0.4),
            FeatureAttribution(feature="x3", observed_value=3.0, reference_value=0.0, attribution=0.2),
            FeatureAttribution(feature="x4", observed_value=4.0, reference_value=0.0, attribution=-0.1),
        ],
    )


def run() -> dict:
    clean = _clean(); rows: list[dict] = []
    cases = [
        ("M1_MODEL_MISMATCH", "artifact_sha_swap", "NONE"), ("M1_MODEL_MISMATCH", "run_identity_swap", "NONE"),
        ("P1_PREPROCESSING_MISMATCH", "preprocessing_identity_swap", "NONE"), ("P1_PREPROCESSING_MISMATCH", "feature_order_identity_swap", "NONE"),
        ("S1_SAMPLE_TARGET_MISMATCH", "sample_identity_swap", "NONE"), ("S1_SAMPLE_TARGET_MISMATCH", "target_identity_swap", "NONE"),
        ("R1_REFERENCE_BACKGROUND_MISMATCH", "reference_identity_swap", "NONE"),
    ]
    for subtype in ("additive_noise", "sign_flip", "permutation"):
        cases.extend(("A1_ATTRIBUTION_MUTATION", subtype, severity) for severity in ("LOW", "MEDIUM", "HIGH"))
    cases.extend(("ADV_EXPLAINER_AWARE", "structurally_valid_attribution_permutation", severity) for severity in ("LOW", "MEDIUM", "HIGH"))
    for family, subtype, severity in cases:
        corrupt, changed = corrupt_contract(clean, family=family, subtype=subtype, severity=severity, seed=3003)
        assert_one_violation(clean, corrupt, changed)
        rows.append({"family": family, "subtype": subtype, "severity": severity, "status": "PASS", "changed_fields": changed, "effective_parameters": effective_severity_parameters(clean, family=family, subtype=subtype, severity=severity)})
    for explainer, parameters in (("integrated_gradients", {"steps": 64}), ("gradient_shap", {"background_count": 24}), ("permutation_shap", {"background_count": 24, "max_evals": 37}), ("tree_shap", {"background_count": 32}), ("occlusion", {"route": "deterministic_exact"})):
        for severity in ("LOW", "MEDIUM", "HIGH"):
            recipe = low_fidelity_generation_parameters(parameters, explainer=explainer, severity=severity)
            rows.append({"family": "L1_LOW_FIDELITY", "subtype": "reduced_budget", "explainer": explainer, "severity": severity, "status": "NOT_APPLICABLE" if recipe is None else "PASS", "fresh_product_native_generation_required": True, "generation_parameters": recipe})
    result = {"schema_version": 1, "study": "S03_SYNTHETIC_CONFORMANCE_ONLY", "benchmark_results_seen": False, "benchmark_explanations_generated": False, "scientific_outcomes_seen": False, "rows": rows}
    result["receipt_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (CONFIG / "synthetic_conformance_receipt.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
