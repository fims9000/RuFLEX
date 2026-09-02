"""Deterministic, one-violation S03 corruption primitives.

L1 is deliberately an execution recipe: it obtains a fresh explanation with
a reduced, frozen budget and never edits a clean attribution vector.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any
from uuid import UUID, uuid5

from ruflex.domain.evidence import ExplanationContract

SEVERITY = {"LOW": 0.05, "MEDIUM": 0.25, "HIGH": 0.75}
GENERATED_FIELDS = {"explanation_id", "created_at"}


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def _effective_k(severity: str, count: int) -> int:
    if count < 2:
        raise ValueError("Attribution reassignment requires at least two features.")
    return max(2, min(count, math.ceil(SEVERITY[severity] * count)))


def _selected_indices(clean: ExplanationContract, severity: str) -> list[int]:
    ranked = sorted(range(len(clean.attributions)), key=lambda i: (-abs(clean.attributions[i].attribution), clean.attributions[i].feature))
    return ranked[:_effective_k(severity, len(ranked))]


def effective_severity_parameters(clean: ExplanationContract, *, family: str, subtype: str, severity: str) -> dict[str, Any]:
    if severity == "NONE":
        return {"severity": "NONE"}
    fraction = SEVERITY[severity]
    if family == "A1_ATTRIBUTION_MUTATION" and subtype == "additive_noise":
        scale = max(max((abs(item.attribution) for item in clean.attributions), default=0.0), 1e-12)
        return {"severity": severity, "fraction": fraction, "scale": scale, "delta": fraction * scale}
    if (family == "A1_ATTRIBUTION_MUTATION" and subtype in {"sign_flip", "permutation"}) or family == "ADV_EXPLAINER_AWARE":
        return {"severity": severity, "fraction": fraction, "effective_k": _effective_k(severity, len(clean.attributions))}
    if family == "L1_LOW_FIDELITY":
        return {"severity": severity, "budget_reduction_fraction": fraction}
    return {"severity": severity, "fraction": fraction}


def low_fidelity_generation_parameters(clean_parameters: dict[str, Any], *, explainer: str, severity: str) -> dict[str, Any] | None:
    """Return a lower-budget native route or ``None`` if no fidelity knob exists."""
    if explainer == "occlusion":
        return None
    field_minimum = {
        "integrated_gradients": ("steps", 8), "gradient_shap": ("background_count", 8),
        "permutation_shap": ("background_count", 8), "tree_shap": ("background_count", 8),
    }
    if explainer not in field_minimum:
        return None
    field, minimum = field_minimum[explainer]
    if field not in clean_parameters:
        return None
    result = dict(clean_parameters)
    result[field] = int(max(minimum, round(float(clean_parameters[field]) * (1.0 - SEVERITY[severity]))))
    if explainer == "permutation_shap" and "max_evals" in result:
        result["max_evals"] = max(int(result["max_evals"] * (1.0 - SEVERITY[severity])), 1)
    return result


def _rotate_values(data: dict[str, Any], indices: list[int]) -> None:
    values = [data["attributions"][index]["attribution"] for index in indices]
    rotated = values[1:] + values[:1]
    if values == rotated:
        raise ValueError("Selected values are equivalent; corruption is NOT_APPLICABLE rather than duplicated.")
    for index, value in zip(indices, rotated, strict=True):
        data["attributions"][index]["attribution"] = value


def corrupt_contract(clean: ExplanationContract, *, family: str, subtype: str, severity: str, seed: int, alternate_run_id: UUID | None = None) -> tuple[ExplanationContract, list[str]]:
    """Create exactly one declared contract/vector mutation without touching clean."""
    if family == "L1_LOW_FIDELITY":
        raise ValueError("L1 requires fresh product-native explanation generation, not contract mutation.")
    data = clean.model_dump(mode="json")
    rng = random.Random(seed)
    if family == "M1_MODEL_MISMATCH" and subtype == "artifact_sha_swap":
        data["model_artifact_sha256"] = "0" * 64; changed = ["model_artifact_sha256"]
    elif family == "M1_MODEL_MISMATCH" and subtype == "run_identity_swap":
        alternate = alternate_run_id or uuid5(UUID("09c3e60a-5a5f-43a2-a81b-1e737dbe14b3"), str(clean.run_id))
        if alternate == clean.run_id: raise ValueError("Alternate run must differ from primary run.")
        data["run_id"] = str(alternate); changed = ["run_id"]
    elif family == "P1_PREPROCESSING_MISMATCH" and subtype == "preprocessing_identity_swap":
        data["preprocessing_identity"] = "s03-corrupt-preprocessing-identity"; changed = ["preprocessing_identity"]
    elif family == "P1_PREPROCESSING_MISMATCH" and subtype == "feature_order_identity_swap":
        data["feature_order_identity"] = "s03-corrupt-feature-order-identity"; changed = ["feature_order_identity"]
    elif family == "S1_SAMPLE_TARGET_MISMATCH" and subtype == "sample_identity_swap":
        data["sample_identity"] = "s03-corrupt-sample-identity"; changed = ["sample_identity"]
    elif family == "S1_SAMPLE_TARGET_MISMATCH" and subtype == "target_identity_swap":
        data["target"] = f"{clean.target}__s03_wrong_target"; changed = ["target"]
    elif family == "R1_REFERENCE_BACKGROUND_MISMATCH" and subtype == "reference_identity_swap":
        data["reference_identity"] = "s03-corrupt-reference-identity"; changed = ["reference_identity"]
    elif family == "A1_ATTRIBUTION_MUTATION" and subtype == "additive_noise":
        delta = effective_severity_parameters(clean, family=family, subtype=subtype, severity=severity)["delta"]
        for item in data["attributions"]: item["attribution"] += delta * (1 if rng.randrange(2) else -1)
        changed = ["attributions"]
    elif family == "A1_ATTRIBUTION_MUTATION" and subtype == "sign_flip":
        for index in _selected_indices(clean, severity): data["attributions"][index]["attribution"] *= -1
        changed = ["attributions"]
    elif family in {"A1_ATTRIBUTION_MUTATION", "ADV_EXPLAINER_AWARE"} and subtype in {"permutation", "structurally_valid_attribution_permutation"}:
        _rotate_values(data, _selected_indices(clean, severity)); changed = ["attributions"]
    else:
        raise ValueError(f"Unsupported S03 corruption {family}/{subtype}/{severity}.")
    data.pop("explanation_id", None)
    corrupt = ExplanationContract.model_validate(data)
    assert_one_violation(clean, corrupt, changed)
    return corrupt, changed


def assert_one_violation(clean: ExplanationContract, corrupt: ExplanationContract, changed_fields: list[str]) -> None:
    left, right = clean.model_dump(mode="json"), corrupt.model_dump(mode="json")
    observed = sorted(key for key in left if key not in GENERATED_FIELDS and left[key] != right[key])
    if observed != sorted(changed_fields):
        raise AssertionError(f"One-violation invariant failed: declared={changed_fields}; observed={observed}")


def mutation_receipt(clean: ExplanationContract, corrupt: ExplanationContract, *, family: str, subtype: str, severity: str, seed: int, changed_fields: list[str]) -> dict[str, Any]:
    return {"schema_version": 2, "source_clean_sha256": _sha(clean.model_dump(mode="json")), "output_sha256": _sha(corrupt.model_dump(mode="json")), "failure_family": family, "failure_subtype": subtype, "severity": severity, "seed": seed, "changed_fields": changed_fields, "effective_parameters": effective_severity_parameters(clean, family=family, subtype=subtype, severity=severity), "unchanged_fields": "all ExplanationContract fields other than changed_fields and generated explanation_id/created_at"}
