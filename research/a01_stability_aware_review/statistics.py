"""Frozen A01 statistics primitives; no training or final-test access occurs here."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

import numpy as np


ReasonCode = Literal[
    "ZERO_HIGH_CONFIDENCE_DENOMINATOR", "ZERO_ACCEPTED_CASES", "ZERO_ACCEPTED_POSITIVES",
    "METRIC_UNDEFINED_SINGLE_CLASS", "INSUFFICIENT_VALID_BOOTSTRAPS",
    "INCOMPLETE_DECLARED_RUN_SUPPORT", "FINAL_TEST_NOT_OPENED", "GENERALITY_ONLY", "NO_EMPIRICAL_CLAIM",
]


@dataclass(frozen=True)
class RiskSummary:
    total_cases: int
    accepted_count: int
    review_count: int
    block_count: int
    coverage: float
    accepted_errors: int
    accepted_risk: float | None
    reason_codes: tuple[str, ...]


def validation_matched_confidence_cutoff(confidences: Iterable[float], stability_coverage: float) -> dict[str, float]:
    """Freeze Policy B using validation confidences only.

    Candidates are the distinct selected-run confidence values.  Coverage is
    accepted fraction at ``confidence >= cutoff``.  Equal coverage gaps choose
    the higher cutoff, then normal numeric ordering, as declared in the SAP.
    """
    values = np.asarray(list(confidences), dtype=float)
    if values.size == 0:
        raise ValueError("Validation-matched comparator requires at least one validation confidence.")
    if not 0.0 <= stability_coverage <= 1.0:
        raise ValueError("Stability validation coverage must be in [0, 1].")
    candidates = sorted({float(value) for value in values})
    rows = []
    for cutoff in candidates:
        coverage = float(np.mean(values >= cutoff))
        rows.append((abs(coverage - stability_coverage), -cutoff, cutoff, coverage))
    _, _, cutoff, coverage = min(rows)
    return {"confidence_cutoff": cutoff, "validation_coverage": coverage, "absolute_coverage_gap": abs(coverage - stability_coverage)}


def accepted_case_risk(truth: Iterable[int], predicted: Iterable[int], dispositions: Iterable[str]) -> RiskSummary:
    labels = np.asarray(list(truth), dtype=int)
    estimates = np.asarray(list(predicted), dtype=int)
    states = list(dispositions)
    if not (len(labels) == len(estimates) == len(states)):
        raise ValueError("Truth, prediction and disposition arrays must have equal length.")
    accepted = np.asarray([state == "ACCEPT" for state in states], dtype=bool)
    errors = int(np.sum(labels[accepted] != estimates[accepted]))
    count = int(np.sum(accepted))
    return RiskSummary(
        total_cases=len(labels), accepted_count=count, review_count=states.count("REVIEW"), block_count=states.count("BLOCK"),
        coverage=(count / len(labels) if len(labels) else 0.0), accepted_errors=errors,
        accepted_risk=None if count == 0 else errors / count,
        reason_codes=("ZERO_ACCEPTED_CASES",) if count == 0 else (),
    )


def accepted_case_fnr(truth: Iterable[int], predicted: Iterable[int], dispositions: Iterable[str]) -> dict[str, int | float | None | list[str]]:
    labels = np.asarray(list(truth), dtype=int); estimates = np.asarray(list(predicted), dtype=int)
    accepted = np.asarray([state == "ACCEPT" for state in dispositions], dtype=bool)
    positives = accepted & (labels == 1)
    denominator = int(np.sum(positives)); false_negatives = int(np.sum(positives & (estimates == 0)))
    return {"accepted_positive_count": denominator, "accepted_false_negative_count": false_negatives, "accepted_case_fnr": None if denominator == 0 else false_negatives / denominator, "reason_codes": ["ZERO_ACCEPTED_POSITIVES"] if denominator == 0 else []}


def paired_bootstrap_delta_risk(
    truth: Iterable[int], selected_prediction: Iterable[int], stability_disposition: Iterable[str], confidence_disposition: Iterable[str],
    *, replicates: int = 10_000, seed: int = 20_260_902,
) -> dict[str, object]:
    """Paired case bootstrap for the already frozen policies.

    Undefined replicate risks remain invalid; they are never converted to zero.
    """
    labels = np.asarray(list(truth), dtype=int); predictions = np.asarray(list(selected_prediction), dtype=int)
    stability = np.asarray(list(stability_disposition), dtype=object); confidence = np.asarray(list(confidence_disposition), dtype=object)
    if not (len(labels) == len(predictions) == len(stability) == len(confidence)) or len(labels) == 0:
        raise ValueError("Paired bootstrap requires non-empty, aligned case arrays.")
    rng = np.random.default_rng(seed); values: list[float] = []; invalid = 0
    for _ in range(replicates):
        index = rng.integers(0, len(labels), size=len(labels))
        left = accepted_case_risk(labels[index], predictions[index], stability[index])
        right = accepted_case_risk(labels[index], predictions[index], confidence[index])
        if left.accepted_risk is None or right.accepted_risk is None:
            invalid += 1
        else:
            values.append(left.accepted_risk - right.accepted_risk)
    valid_fraction = len(values) / replicates
    return {
        "requested_replicates": replicates, "valid_replicates": len(values), "invalid_replicates": invalid,
        "valid_fraction": valid_fraction, "delta_risk_percentile_ci_95": None if valid_fraction < .9 else [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))],
        "reason_codes": ["INSUFFICIENT_VALID_BOOTSTRAPS"] if valid_fraction < .9 else [],
    }


def paired_bootstrap_policy_metrics(
    truth: Iterable[int], selected_prediction: Iterable[int], stability_disposition: Iterable[str], confidence_disposition: Iterable[str],
    *, replicates: int = 10_000, seed: int = 20_260_902,
) -> dict[str, object]:
    """Frozen paired percentile bootstrap for all Phase 2 policy quantities.

    One deterministic index stream is used for every statistic.  Undefined
    risks/FNRs are invalid per statistic; they are never silently coerced to
    zero.  This is statistics-only and contains no data/model access.
    """
    labels = np.asarray(list(truth), dtype=int); predictions = np.asarray(list(selected_prediction), dtype=int)
    stability = np.asarray(list(stability_disposition), dtype=object); confidence = np.asarray(list(confidence_disposition), dtype=object)
    if not (len(labels) == len(predictions) == len(stability) == len(confidence)) or len(labels) == 0:
        raise ValueError("Paired bootstrap requires non-empty aligned case arrays.")
    collected: dict[str, list[float]] = {key: [] for key in ("stability_risk", "confidence_risk", "delta_risk", "delta_coverage", "stability_fnr", "confidence_fnr", "delta_fnr")}
    invalid: dict[str, int] = {key: 0 for key in collected}
    rng = np.random.default_rng(seed)
    for _ in range(replicates):
        index = rng.integers(0, len(labels), size=len(labels))
        left = accepted_case_risk(labels[index], predictions[index], stability[index]); right = accepted_case_risk(labels[index], predictions[index], confidence[index])
        for key, value in (("stability_risk", left.accepted_risk), ("confidence_risk", right.accepted_risk)):
            if value is None: invalid[key] += 1
            else: collected[key].append(float(value))
        if left.accepted_risk is None or right.accepted_risk is None: invalid["delta_risk"] += 1
        else: collected["delta_risk"].append(float(left.accepted_risk - right.accepted_risk))
        collected["delta_coverage"].append(float(left.coverage - right.coverage))
        left_fnr = accepted_case_fnr(labels[index], predictions[index], stability[index])["accepted_case_fnr"]
        right_fnr = accepted_case_fnr(labels[index], predictions[index], confidence[index])["accepted_case_fnr"]
        for key, value in (("stability_fnr", left_fnr), ("confidence_fnr", right_fnr)):
            if value is None: invalid[key] += 1
            else: collected[key].append(float(value))
        if left_fnr is None or right_fnr is None: invalid["delta_fnr"] += 1
        else: collected["delta_fnr"].append(float(left_fnr - right_fnr))
    def summary(key: str) -> dict[str, object]:
        valid = len(collected[key]); fraction = valid / replicates
        return {"requested_replicates": replicates, "valid_replicates": valid, "invalid_replicates": invalid[key], "valid_fraction": fraction, "percentile_ci_95": None if fraction < .9 else [float(np.percentile(collected[key], 2.5)), float(np.percentile(collected[key], 97.5))], "reason_codes": ["INSUFFICIENT_VALID_BOOTSTRAPS"] if fraction < .9 else []}
    return {"bootstrap_seed": seed, "replicates": replicates, **{key: summary(key) for key in collected}}


def paired_bootstrap_delta_fnr(*args: object, **kwargs: object) -> dict[str, object]:
    """Compatibility helper exposing the frozen FNR-difference bootstrap."""
    return paired_bootstrap_policy_metrics(*args, **kwargs)["delta_fnr"]


def paired_bootstrap_delta_coverage(*args: object, **kwargs: object) -> dict[str, object]:
    """Compatibility helper exposing the frozen coverage-difference bootstrap."""
    return paired_bootstrap_policy_metrics(*args, **kwargs)["delta_coverage"]


def h3_interpretation(ci: list[float] | None) -> str:
    if ci is None:
        return "NOT_ASSESSABLE"
    if ci[1] < 0:
        return "SUPPORTS_H3"
    if ci[0] > 0:
        return "CONTRADICTS_H3"
    return "INCONCLUSIVE"


def select_illustrative_cases(cases: Iterable[dict[str, object]], *, limit: int) -> list[str]:
    """Deterministic case selection: agreement ascending, confidence descending, ID."""
    ordered = sorted(cases, key=lambda item: (float(item["selected_run_agreement"]), -float(item["selected_run_confidence"]), str(item["case_id"])))
    return [str(item["case_id"]) for item in ordered[:limit]]


def validate_result_statuses(result: dict[str, object]) -> list[str]:
    """Reject generic software-style PASS labels in scientific result records."""
    errors: list[str] = []
    if result.get("h1_status") not in {"PATTERN_OBSERVED", "PATTERN_NOT_OBSERVED", "NOT_ASSESSABLE"}:
        errors.append("invalid H1 scientific status")
    if result.get("h2_status") not in {"PATTERN_OBSERVED", "PATTERN_NOT_OBSERVED", "NOT_ASSESSABLE"}:
        errors.append("invalid H2 scientific status")
    for status in result.get("h3_by_model_family", []):
        if status not in {"SUPPORTS_H3", "CONTRADICTS_H3", "INCONCLUSIVE", "NOT_ASSESSABLE"}:
            errors.append("invalid H3 scientific status")
            break
    return errors
