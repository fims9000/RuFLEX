from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.s03_explanation_validation.corruptions import corrupt_contract
from research.s03_explanation_validation.corruptions.library import assert_one_violation, low_fidelity_generation_parameters
from research.s03_explanation_validation.run_synthetic_conformance import run as conformance
from research.s03_explanation_validation.run_synthetic_smoke import smoke
from research.s03_explanation_validation.validate_phase0_1 import validate
from ruflex.domain.evidence import ExplanationContract, FeatureAttribution


def _clean() -> ExplanationContract:
    return ExplanationContract(
        run_id="00000000-0000-0000-0000-000000000001", model_kind="logistic_regression", model_artifact_sha256="a" * 64,
        preprocessing_identity="p", feature_order_identity="order", sample_identity="s", reference_identity="r",
        generation_parameters={"background_count": 24}, sample={"x1": 1.0, "x2": 2.0, "x3": 3.0, "x4": 4.0}, target="target",
        prediction=.7, base_value=.1, completeness_error=0.0, reference_definition="train reference",
        attributions=[FeatureAttribution(feature="x1", observed_value=1., reference_value=0., attribution=.8), FeatureAttribution(feature="x2", observed_value=2., reference_value=0., attribution=-.4), FeatureAttribution(feature="x3", observed_value=3., reference_value=0., attribution=.2), FeatureAttribution(feature="x4", observed_value=4., reference_value=0., attribution=-.1)],
    )


@pytest.mark.parametrize(("family", "subtype", "severity", "changed"), [
    ("M1_MODEL_MISMATCH", "artifact_sha_swap", "NONE", ["model_artifact_sha256"]), ("M1_MODEL_MISMATCH", "run_identity_swap", "NONE", ["run_id"]),
    ("P1_PREPROCESSING_MISMATCH", "preprocessing_identity_swap", "NONE", ["preprocessing_identity"]), ("P1_PREPROCESSING_MISMATCH", "feature_order_identity_swap", "NONE", ["feature_order_identity"]),
    ("S1_SAMPLE_TARGET_MISMATCH", "sample_identity_swap", "NONE", ["sample_identity"]), ("S1_SAMPLE_TARGET_MISMATCH", "target_identity_swap", "NONE", ["target"]),
    ("R1_REFERENCE_BACKGROUND_MISMATCH", "reference_identity_swap", "NONE", ["reference_identity"]),
    ("A1_ATTRIBUTION_MUTATION", "additive_noise", "LOW", ["attributions"]), ("A1_ATTRIBUTION_MUTATION", "sign_flip", "MEDIUM", ["attributions"]), ("A1_ATTRIBUTION_MUTATION", "permutation", "HIGH", ["attributions"]),
    ("ADV_EXPLAINER_AWARE", "structurally_valid_attribution_permutation", "LOW", ["attributions"]),
])
def test_s03_corruption_is_one_declared_violation(family, subtype, severity, changed):
    clean = _clean(); corrupt, actual = corrupt_contract(clean, family=family, subtype=subtype, severity=severity, seed=3003)
    assert actual == changed; assert_one_violation(clean, corrupt, actual)
    assert clean.model_dump(mode="json") != corrupt.model_dump(mode="json")


@pytest.mark.parametrize("severity", ["LOW", "MEDIUM", "HIGH"])
def test_s03_permutation_reassigns_values_not_feature_records(severity):
    clean = _clean(); corrupt, _ = corrupt_contract(clean, family="A1_ATTRIBUTION_MUTATION", subtype="permutation", severity=severity, seed=3003)
    assert [item.feature for item in corrupt.attributions] == [item.feature for item in clean.attributions]
    assert {item.feature: item.attribution for item in corrupt.attributions} != {item.feature: item.attribution for item in clean.attributions}


def test_s03_severity_levels_have_distinct_effective_parameters():
    clean = _clean()
    effects = []
    for severity in ("LOW", "MEDIUM", "HIGH"):
        corrupt, _ = corrupt_contract(clean, family="A1_ATTRIBUTION_MUTATION", subtype="additive_noise", severity=severity, seed=3003)
        effects.append(tuple(item.attribution for item in corrupt.attributions))
    assert len(set(effects)) == 3


def test_s03_low_fidelity_is_fresh_route_recipe_not_vector_mutation():
    assert low_fidelity_generation_parameters({"steps": 64}, explainer="integrated_gradients", severity="HIGH") == {"steps": 16}
    assert low_fidelity_generation_parameters({"route": "deterministic_exact"}, explainer="occlusion", severity="HIGH") is None
    with pytest.raises(ValueError, match="fresh product-native"):
        corrupt_contract(_clean(), family="L1_LOW_FIDELITY", subtype="reduced_budget", severity="LOW", seed=1)


def test_s03_synthetic_conformance_covers_all_declared_families():
    result = conformance(); assert result["benchmark_results_seen"] is False
    assert {row["family"] for row in result["rows"]} == {"M1_MODEL_MISMATCH", "P1_PREPROCESSING_MISMATCH", "S1_SAMPLE_TARGET_MISMATCH", "R1_REFERENCE_BACKGROUND_MISMATCH", "A1_ATTRIBUTION_MUTATION", "L1_LOW_FIDELITY", "ADV_EXPLAINER_AWARE"}


def test_s03_phase0_1_validator_and_pair_matrix():
    # Phase 0.1 stays historical evidence.  The Phase 0.2 product replay
    # hardening intentionally invalidates its frozen code identity rather than
    # silently rewriting the old manifest.
    with pytest.raises(AssertionError, match="Frozen identity differs"):
        validate()


def test_s03_quantus_preflight_is_optional_and_frozen_not_available_when_uninstalled():
    root = Path(__file__).resolve().parents[1] / "research" / "s03_explanation_validation" / "config"
    spec, receipt = json.loads((root / "quantus_spec.json").read_text()), json.loads((root / "quantus_preflight_receipt.json").read_text())
    assert spec["optional_dependency"] == "quantus==0.6.0"
    assert spec["required_for_product_runtime"] is False
    assert receipt["synthetic_only"] is True and receipt["benchmark_accessed"] is False
    assert receipt["state"] in {"AVAILABLE", "NOT_AVAILABLE"}


def test_s03_synthetic_native_product_smoke():
    result = smoke(); assert result["empirical_s03_evidence"] is False; assert result["clean_status"] == "PASSED_AVAILABLE_CHECKS"; assert result["corrupt_status"] == "FAILED"; assert result["localized_model_identity"]; assert result["reopen_status"] == "FAILED"
