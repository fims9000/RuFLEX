"""Read-only integrity inspection for local-first RuFLEX project reopen."""
from __future__ import annotations

import json
import hashlib
import math
from datetime import datetime
from pathlib import Path
from uuid import UUID

import numpy as np
from pydantic import ValidationError
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

from ruflex.application.artifacts import ArtifactRecord, ArtifactRef, ArtifactStore
from ruflex.application.datasets import DatasetConfirmationError, DatasetContract, DatasetProfile, LeakageAuditReport, SplitContract, TransformPipelineContract, load_data_audit, load_dataset_contract, load_dataset_profile, load_leakage_audit, load_split_contract, load_transform_pipeline_contract, row_identity
from ruflex.application.fis import list_fis_revisions, load_fis
from ruflex.application.jobs import Job
from ruflex.application.projects import ProjectService
from ruflex.application.training import _baseline_metrics, _calibration_bins_from_probabilities, _classification_metrics_at_threshold, _ece_from_bins, _operating_curves, _select_study_run, _stable_identity, _validation_sample_identity, list_training_runs
from ruflex.application.behavior import _requirement_identity
from ruflex.application.generalization import SliceAnalysis, load_generalization_contract
from ruflex.domain.behavior import BehaviorRevisionComparison, BehaviorSpec, BehaviorSpecResult
from ruflex.domain.evidence import ExplanationCheck, ExplanationContract, ExplanationReproducibilityAnalysis
from ruflex.domain.expert_correction import ExpertCorrectionRevision
from ruflex.domain.exhaustive import ExhaustiveLabResult
from ruflex.domain.assurance import AssuranceCase
from ruflex.domain.verification import VerificationBundle
from ruflex.domain.project import ProjectIntegrityIssue, ProjectIntegrityReport
from ruflex.domain.training import AnalysisComparison, AnalysisEvaluation, CalibrationTransform, DecisionThresholdPolicy, FinalTestEvaluation, StudyJob, TrainingStudy, TreePathEvidence
from ruflex.domain.selective import SelectivePredictionPolicy
from ruflex.domain.stability import StabilityGatePolicy, StudyStabilityAnalysis
from ruflex.runtime.registry import builtin_runtime_registry
from ruflex.runtime.compatibility import resolve_run_adapter
from ruflex.runtime.compatibility import LEGACY_MODEL_KIND_TO_ADAPTER


def _final_test_stability_evidence_matches(final_test: FinalTestEvaluation, policy: StabilityGatePolicy | None) -> bool:
    evidence = final_test.stability_gate_evidence
    if final_test.stability_gate_policy_id is None:
        return evidence is None
    if policy is None or evidence is None or evidence.policy_id != policy.policy_id:
        return False
    if (
        evidence.class_threshold_id != policy.class_threshold_id
        or evidence.decision_threshold != policy.decision_threshold
        or evidence.run_ids != policy.run_ids
        or len(evidence.cases) != len(final_test.prediction_rows)
    ):
        return False
    predictions = {row.row_identity or (row_identity(final_test.dataset_fingerprint, int(row.source_row)) if row.source_row is not None else None): row for row in final_test.prediction_rows}
    cases = {case.row_identity or case.case_id: case for case in evidence.cases}
    if (
        None in predictions
        or len(predictions) != len(final_test.prediction_rows)
        or len(cases) != len(evidence.cases)
        or list(predictions) != [case.row_identity or case.case_id for case in evidence.cases]
    ):
        return False
    for identity, row in predictions.items():
        case = cases[identity]
        probability = case.selected_run_probability
        expected_class = int(probability >= policy.decision_threshold)
        if (
            case.case_id != identity
            or (case.row_identity is not None and case.row_identity != identity)
            or row.source_row != case.source_row
            or row.target is None
            or int(row.target) != case.target
            or row.probability is None
            or not math.isclose(float(row.probability), probability, rel_tol=1e-12, abs_tol=1e-12)
            or row.predicted_label != expected_class
            or case.selected_run_class != expected_class
        ):
            return False
        expected_reasons: list[str] = []
        if max(probability, 1.0 - probability) < policy.min_confidence:
            expected_reasons.append("LOW_CONFIDENCE")
        if case.selected_run_agreement < policy.min_class_agreement:
            expected_reasons.append("RUN_DISAGREEMENT")
        if len(policy.run_ids) < policy.required_run_support:
            expected_reasons.append("INSUFFICIENT_RUN_SUPPORT")
        if case.probability_std > policy.max_probability_std:
            expected_reasons.append("HIGH_DISPERSION")
        if case.reasons != expected_reasons or case.disposition != ("REVIEW" if expected_reasons else "ACCEPT"):
            return False
    accepted = [case for case in evidence.cases if case.disposition == "ACCEPT"]
    reviewed = [case for case in evidence.cases if case.disposition == "REVIEW"]
    blocked = [case for case in evidence.cases if case.disposition == "BLOCK"]
    accepted_errors = sum(case.selected_run_class != case.target for case in accepted)
    accepted_fn = sum(case.selected_run_class == 0 and case.target == 1 for case in accepted)
    accepted_positives = sum(case.target == 1 for case in accepted)
    confidence_only = sorted(evidence.cases, key=lambda case: max(case.selected_run_probability, 1.0 - case.selected_run_probability), reverse=True)[:len(accepted)]
    confidence_error = None if not confidence_only else sum(case.selected_run_class != case.target for case in confidence_only) / len(confidence_only)
    expected_coverage = len(accepted) / len(evidence.cases) if evidence.cases else 0.0
    return (
        evidence.accepted_count == len(accepted)
        and evidence.review_count == len(reviewed)
        and evidence.block_count == len(blocked)
        and math.isclose(evidence.coverage, expected_coverage, rel_tol=1e-12, abs_tol=1e-12)
        and evidence.accepted_error == (None if not accepted else accepted_errors / len(accepted))
        and evidence.accepted_false_negative_count == accepted_fn
        and evidence.accepted_false_negative_rate == (None if accepted_positives == 0 else accepted_fn / accepted_positives)
        and evidence.confidence_only_accepted_count == len(confidence_only)
        and evidence.confidence_only_accepted_error == confidence_error
    )


def _final_test_metrics_match(
    final_test: FinalTestEvaluation,
    threshold: DecisionThresholdPolicy | None,
    calibration: CalibrationTransform | None,
) -> bool:
    if not final_test.prediction_rows:
        return False
    targets = np.asarray([row.target for row in final_test.prediction_rows], dtype=float)
    predictions = np.asarray([row.prediction for row in final_test.prediction_rows], dtype=float)
    if final_test.task == "binary_classification":
        if threshold is None:
            return False
        truth = (targets >= 0.5).astype(int)
        raw_probabilities = 1.0 / (1.0 + np.exp(-np.clip(predictions, -60.0, 60.0)))
        probabilities = raw_probabilities
        if calibration is not None:
            calibrated_logits = calibration.coefficient * predictions + calibration.intercept
            calibrated_probabilities = 1.0 / (1.0 + np.exp(-np.clip(calibrated_logits, -60.0, 60.0)))
            probabilities = calibrated_probabilities if threshold.probability_source == "calibrated" else raw_probabilities
        elif threshold.probability_source == "calibrated":
            return False
        for index, row in enumerate(final_test.prediction_rows):
            if (
                row.probability is None
                or not math.isclose(row.probability, float(raw_probabilities[index]), rel_tol=1e-12, abs_tol=1e-12)
                or (calibration is None and row.calibrated_probability is not None)
                or (calibration is not None and row.calibrated_probability is None)
                or (calibration is not None and not math.isclose(row.calibrated_probability, float(calibrated_probabilities[index]), rel_tol=1e-12, abs_tol=1e-12))
            ):
                return False
        metrics, confusion, labels = _classification_metrics_at_threshold(truth, probabilities, threshold.selected_threshold)
        metrics["brier"] = float(np.mean((probabilities - truth) ** 2))
        bins = _calibration_bins_from_probabilities(truth, probabilities)
        metrics["ece"] = _ece_from_bins(bins, len(truth))
        if len(np.unique(truth)) == 2:
            metrics["roc_auc"] = float(roc_auc_score(truth, probabilities))
            metrics["pr_auc"] = float(average_precision_score(truth, probabilities))
        curves = _operating_curves(truth, probabilities)
        if final_test.confusion_matrix != confusion or [row.predicted_label for row in final_test.prediction_rows] != labels.tolist():
            return False
    else:
        if threshold is not None or calibration is not None or any(row.probability is not None or row.calibrated_probability is not None for row in final_test.prediction_rows):
            return False
        metrics = _baseline_metrics(final_test.task, targets, predictions)
        bins = []
        curves = ([], [])
        if final_test.confusion_matrix is not None or any(row.residual is None or not math.isclose(row.residual, float(row.target - row.prediction), rel_tol=1e-12, abs_tol=1e-12) for row in final_test.prediction_rows):
            return False
    if set(metrics) != set(final_test.metrics) or any(
        not math.isclose(float(final_test.metrics[name]), value, rel_tol=1e-12, abs_tol=1e-12)
        for name, value in metrics.items()
    ):
        return False
    return (
        [item.model_dump() for item in final_test.calibration_bins] == [item.model_dump() for item in bins]
        and [item.model_dump() for item in final_test.roc_curve] == [item.model_dump() for item in curves[0]]
        and [item.model_dump() for item in final_test.precision_recall_curve] == [item.model_dump() for item in curves[1]]
    )


def _threshold_evidence_matches(
    threshold: DecisionThresholdPolicy,
    evaluation: AnalysisEvaluation | None,
    calibration: CalibrationTransform | None,
) -> bool:
    if evaluation is None or evaluation.task != "binary_classification" or evaluation.split != "validation" or not evaluation.prediction_preview:
        return False
    rows = evaluation.prediction_preview
    targets = np.asarray([int(row.target >= 0.5) for row in rows], dtype=int)
    raw_probabilities = np.asarray([
        float(row.probability) if row.probability is not None
        else float(1.0 / (1.0 + np.exp(-np.clip(row.prediction, -60.0, 60.0))))
        for row in rows
    ], dtype=float)
    if threshold.probability_source == "raw":
        if calibration is not None or threshold.calibration_id is not None:
            return False
        probabilities = raw_probabilities
        sample_identity = _stable_identity(
            "validation-threshold",
            {"evaluation_id": str(evaluation.evaluation_id), "run_id": str(evaluation.run_id), "targets": targets.tolist(), "probabilities": probabilities.tolist()},
        )
    else:
        if calibration is None or calibration.calibration_id != threshold.calibration_id or calibration.evaluation_id != evaluation.evaluation_id or calibration.run_id != evaluation.run_id:
            return False
        if len(calibration.predictions) != len(rows):
            return False
        for row, calibrated in zip(rows, calibration.predictions, strict=True):
            if (
                row.row != calibrated.row
                or row.source_row != calibrated.source_row
                or row.row_identity != calibrated.row_identity
                or not math.isclose(row.target, calibrated.target, rel_tol=1e-12, abs_tol=1e-12)
                or row.probability is None
                or not math.isclose(row.probability, calibrated.raw_probability, rel_tol=1e-12, abs_tol=1e-12)
            ):
                return False
        probabilities = np.asarray([item.calibrated_probability for item in calibration.predictions], dtype=float)
        sample_identity = calibration.fit_sample_identity
    candidates = np.round(np.arange(0.01, 1.0, 0.01), 2)
    scores = np.asarray([f1_score(targets, probabilities >= candidate, zero_division=0) for candidate in candidates], dtype=float)
    best_score = float(scores.max())
    best_candidates = candidates[np.isclose(scores, best_score, rtol=0.0, atol=1e-12)]
    selected = float(sorted(best_candidates.tolist(), key=lambda value: (abs(value - 0.5), value))[0])
    expected_metrics, expected_confusion, expected_labels = _classification_metrics_at_threshold(targets, probabilities, selected)
    if (
        threshold.objective != "f1"
        or threshold.source_split != "validation"
        or threshold.test_status != "LOCKED_NOT_EVALUATED"
        or threshold.candidate_rule != "thresholds 0.01 through 0.99; maximize validation F1; ties choose closest to 0.50, then lower threshold"
        or threshold.selected_threshold != selected
        or not math.isclose(threshold.selection_result, best_score, rel_tol=1e-12, abs_tol=1e-12)
        or threshold.fit_sample_identity != sample_identity
        or threshold.confusion_matrix != expected_confusion
        or set(threshold.metrics) != set(expected_metrics)
        or any(not math.isclose(float(threshold.metrics[name]), value, rel_tol=1e-12, abs_tol=1e-12) for name, value in expected_metrics.items())
    ):
        return False
    if threshold.decisions:
        if len(threshold.decisions) != len(rows):
            return False
        for decision, row, target, probability, label in zip(threshold.decisions, rows, targets, probabilities, expected_labels, strict=True):
            if (
                decision.row != row.row
                or decision.target != int(target)
                or not math.isclose(decision.probability, float(probability), rel_tol=1e-12, abs_tol=1e-12)
                or decision.predicted_label != int(label)
            ):
                return False
    return True


def _calibration_evidence_matches(calibration: CalibrationTransform, evaluation: AnalysisEvaluation | None) -> bool:
    if evaluation is None or evaluation.task != "binary_classification" or evaluation.split != "validation" or not evaluation.prediction_preview:
        return False
    rows = evaluation.prediction_preview
    if calibration.run_id != evaluation.run_id or calibration.source_split != "validation" or calibration.test_status != "LOCKED_NOT_EVALUATED" or calibration.method != "platt_scaling" or calibration.input_kind != "model_logit" or calibration.fit_sample_count != len(rows) or len(calibration.predictions) != len(rows):
        return False
    targets = np.asarray([int(row.target >= 0.5) for row in rows], dtype=int)
    logits = np.asarray([float(row.prediction) for row in rows], dtype=float)
    expected_identity = _stable_identity(
        "validation-calibration",
        {"evaluation_id": str(evaluation.evaluation_id), "run_id": str(evaluation.run_id), "targets": targets.tolist(), "logits": logits.tolist()},
    )
    raw_probabilities = np.asarray([
        float(row.probability) if row.probability is not None
        else float(1.0 / (1.0 + np.exp(-np.clip(row.prediction, -60.0, 60.0))))
        for row in rows
    ], dtype=float)
    calibrated_probabilities = 1.0 / (1.0 + np.exp(-np.clip(calibration.coefficient * logits + calibration.intercept, -60.0, 60.0)))
    expected_before_bins = _calibration_bins_from_probabilities(targets, raw_probabilities)
    expected_after_bins = _calibration_bins_from_probabilities(targets, calibrated_probabilities)
    if calibration.fit_sample_identity != expected_identity:
        return False
    for row, record, target, raw_probability, calibrated_probability in zip(rows, calibration.predictions, targets, raw_probabilities, calibrated_probabilities, strict=True):
        if (
            row.row != record.row
            or row.source_row != record.source_row
            or row.row_identity != record.row_identity
            or record.target != row.target
            or record.target != int(target)
            or not math.isclose(record.raw_probability, float(raw_probability), rel_tol=1e-12, abs_tol=1e-12)
            or not math.isclose(record.calibrated_probability, float(calibrated_probability), rel_tol=1e-12, abs_tol=1e-12)
        ):
            return False
    expected_brier_before = float(np.mean((raw_probabilities - targets) ** 2))
    expected_brier_after = float(np.mean((calibrated_probabilities - targets) ** 2))
    expected_ece_before = _ece_from_bins(expected_before_bins, len(rows))
    expected_ece_after = _ece_from_bins(expected_after_bins, len(rows))
    bins_match = len(calibration.calibration_bins) == len(expected_after_bins) and all(
        actual.lower == expected.lower
        and actual.upper == expected.upper
        and actual.count == expected.count
        and math.isclose(actual.mean_probability, expected.mean_probability, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(actual.observed_positive_rate, expected.observed_positive_rate, rel_tol=1e-12, abs_tol=1e-12)
        for actual, expected in zip(calibration.calibration_bins, expected_after_bins, strict=True)
    )
    return (
        math.isclose(calibration.brier_before, expected_brier_before, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(calibration.brier_after, expected_brier_after, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(calibration.ece_before, expected_ece_before, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(calibration.ece_after, expected_ece_after, rel_tol=1e-12, abs_tol=1e-12)
        and bins_match
    )


def _stability_analysis_cases_match(
    analysis: StudyStabilityAnalysis,
    study: TrainingStudy | None,
    evaluation: AnalysisEvaluation | None,
    threshold: DecisionThresholdPolicy | None,
) -> bool:
    if study is None or analysis.case_count != len(analysis.cases):
        return False
    study_runs = study.seed_runs
    if not study_runs:
        return False
    selected_run = next((run for run in study_runs if run.run_id == study.selected_run_id), None)
    split_ids = {run.split.split_identity for run in study_runs}
    split_seeds = [int(run.split.split_seed if run.split.split_seed is not None else run.split.seed) for run in study_runs]
    training_seeds = [int(run.training_seed if run.training_seed is not None else run.seed) for run in study_runs]
    expected_metrics = {
        metric: [float(run.validation_metrics[metric]) for run in study_runs]
        for metric in ("accuracy", "f1", "roc_auc", "pr_auc", "brier", "ece")
        if all(metric in run.validation_metrics for run in study_runs)
    }
    if selected_run is None or (
        analysis.mode != study.randomness_protocol
        or analysis.dataset_fingerprint != selected_run.dataset_fingerprint
        or analysis.dataset_artifact_sha256 != selected_run.dataset_artifact_sha256
        or analysis.model_kind != study.model_kind
        or analysis.task != study.task
        or analysis.split_seeds != split_seeds
        or analysis.training_seeds != training_seeds
        or analysis.split_identity != (next(iter(split_ids)) if len(split_ids) == 1 else None)
        or analysis.split_seed != (split_seeds[0] if len(set(split_seeds)) == 1 else None)
        or set(analysis.metric_distributions) != set(expected_metrics)
    ):
        return False
    for metric, values in expected_metrics.items():
        array = np.asarray(values, dtype=float)
        expected_summary = {
            "mean": float(array.mean()),
            "std": float(array.std(ddof=0)),
            "minimum": float(array.min()),
            "maximum": float(array.max()),
            "median": float(np.median(array)),
            "iqr": float(np.percentile(array, 75) - np.percentile(array, 25)),
        }
        actual_summary = analysis.metric_distributions[metric]
        if any(
            not math.isclose(getattr(actual_summary, field), expected, rel_tol=1e-12, abs_tol=1e-12)
            for field, expected in expected_summary.items()
        ):
            return False
    if analysis.applicability != "APPLICABLE" or analysis.validation_alignment_status != "EXACT_MATCH":
        return not analysis.cases and analysis.case_count == 0 and analysis.high_confidence_case_count == 0 and analysis.high_confidence_unstable_case_count == 0 and analysis.high_confidence_instability_rate is None
    if not analysis.cases or len({case.case_id for case in analysis.cases}) != len(analysis.cases) or analysis.case_support_requirement > len(analysis.run_ids):
        return False
    expected_case_ids: set[str] | None = None
    run_rows: dict[str, dict[str, object]] = {}
    for run in study.seed_runs:
        rows: dict[str, object] = {}
        for row in run.prediction_preview:
            key = row.row_identity or (f"source:{row.source_row}" if row.source_row is not None else f"row:{row.row}")
            if key in rows:
                return False
            rows[key] = row
        if expected_case_ids is None:
            expected_case_ids = set(rows)
        elif expected_case_ids != set(rows):
            return False
        run_rows[str(run.run_id)] = rows
    if expected_case_ids is None or {case.case_id for case in analysis.cases} != expected_case_ids:
        return False
    evaluation_rows: dict[str, object] = {}
    if evaluation is not None:
        for row in evaluation.prediction_preview:
            key = row.row_identity or (f"source:{row.source_row}" if row.source_row is not None else f"row:{row.row}")
            if key in evaluation_rows:
                return False
            evaluation_rows[key] = row
        if set(evaluation_rows) != expected_case_ids:
            return False
    if (threshold is None) != (analysis.decision_threshold is None) or (threshold is None) != (analysis.class_threshold_id is None) or (threshold is not None and evaluation is None):
        return False
    if threshold is not None and (threshold.selected_threshold != analysis.decision_threshold or threshold.threshold_id != analysis.class_threshold_id):
        return False

    high_confidence: list[object] = []
    unstable: list[object] = []
    for case in analysis.cases:
        if case.run_support_count != len(analysis.run_ids) or case.run_support_fraction != 1.0 or set(case.run_probabilities) != {str(run_id) for run_id in analysis.run_ids}:
            return False
        actual_values: list[float] = []
        expected_labels: dict[str, int] = {}
        for run_id in analysis.run_ids:
            row = run_rows.get(str(run_id), {}).get(case.case_id)
            if row is None:
                return False
            value = float(row.probability) if row.probability is not None else 1.0 / (1.0 + math.exp(-max(min(float(row.prediction), 60.0), -60.0)))
            if not math.isclose(case.run_probabilities[str(run_id)], value, rel_tol=1e-12, abs_tol=1e-12):
                return False
            actual_values.append(value)
            if threshold is not None:
                expected_labels[str(run_id)] = int(value >= threshold.selected_threshold)
        if case.run_labels != expected_labels:
            return False
        mean = sum(actual_values) / len(actual_values)
        std = math.sqrt(sum((value - mean) ** 2 for value in actual_values) / len(actual_values))
        selected_probability = case.run_probabilities[str(analysis.selected_run_id)]
        selected_row = run_rows[str(analysis.selected_run_id)][case.case_id]
        if (
            not math.isclose(case.selected_run_probability, selected_probability, rel_tol=1e-12, abs_tol=1e-12)
            or not math.isclose(case.mean_probability, mean, rel_tol=1e-12, abs_tol=1e-12)
            or not math.isclose(case.std_probability, std, rel_tol=1e-12, abs_tol=1e-12)
            or not math.isclose(case.min_probability, min(actual_values), rel_tol=1e-12, abs_tol=1e-12)
            or not math.isclose(case.max_probability, max(actual_values), rel_tol=1e-12, abs_tol=1e-12)
            or not math.isclose(case.probability_range, max(actual_values) - min(actual_values), rel_tol=1e-12, abs_tol=1e-12)
            or case.source_row != selected_row.source_row
            or case.row_identity != selected_row.row_identity
            or case.target != int(selected_row.target >= 0.5)
        ):
            return False
        if evaluation is not None:
            selected_row = evaluation_rows[case.case_id]
            if (
                case.source_row != selected_row.source_row
                or case.row_identity != selected_row.row_identity
                or case.target != int(selected_row.target >= 0.5)
            ):
                return False
        if threshold is None:
            if any(value is not None for value in (case.selected_run_class, case.majority_class, case.majority_class_agreement, case.selected_run_agreement, case.positive_vote_fraction, case.vote_entropy)):
                return False
            continue
        positive_fraction = sum(expected_labels.values()) / len(expected_labels)
        majority_class = int(positive_fraction >= 0.5)
        selected_label = expected_labels[str(analysis.selected_run_id)]
        selected_agreement = sum(label == selected_label for label in expected_labels.values()) / len(expected_labels)
        majority_agreement = max(positive_fraction, 1.0 - positive_fraction)
        entropy = None if positive_fraction in {0.0, 1.0} else -(positive_fraction * math.log2(positive_fraction) + (1.0 - positive_fraction) * math.log2(1.0 - positive_fraction))
        if (
            case.selected_run_class != selected_label
            or case.majority_class != majority_class
            or case.majority_class_agreement != majority_agreement
            or case.selected_run_agreement != selected_agreement
            or case.positive_vote_fraction != positive_fraction
            or case.vote_entropy != entropy
        ):
            return False
        if max(selected_probability, 1.0 - selected_probability) >= analysis.high_confidence_threshold:
            high_confidence.append(case)
            if selected_agreement < analysis.unstable_agreement_threshold:
                unstable.append(case)
    identity_payload = json.dumps({"prefix": "validation-cases", "payload": sorted(expected_case_ids)}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_case_identity = hashlib.sha256(identity_payload).hexdigest()
    return (
        (threshold is None and analysis.high_confidence_case_count == 0 and analysis.high_confidence_unstable_case_count == 0 and analysis.high_confidence_instability_rate is None)
        or (
            analysis.evaluation_id is not None
            and evaluation is not None
            and analysis.evaluation_case_identity == expected_case_identity
            and analysis.high_confidence_case_count == len(high_confidence)
            and analysis.high_confidence_unstable_case_count == len(unstable)
            and analysis.high_confidence_instability_rate == (None if not high_confidence else len(unstable) / len(high_confidence))
        )
    )


def _stability_gate_evidence_matches(policy: StabilityGatePolicy, analysis: StudyStabilityAnalysis) -> bool:
    if (
        policy.run_ids != analysis.run_ids
        or policy.required_run_support != analysis.case_support_requirement
        or policy.analysis_schema_version != analysis.schema_version
        or policy.fit_sample_identity != analysis.evaluation_case_identity
        or len(policy.decisions) != len(analysis.cases)
        or [decision.case_id for decision in policy.decisions] != [case.case_id for case in analysis.cases]
    ):
        return False
    accepted = []
    for case, decision in zip(analysis.cases, policy.decisions, strict=True):
        if case.selected_run_class is None or case.selected_run_agreement is None or case.majority_class_agreement is None:
            return False
        confidence = max(case.selected_run_probability, 1.0 - case.selected_run_probability)
        reasons: list[str] = []
        if confidence < policy.min_confidence:
            reasons.append("LOW_CONFIDENCE")
        if case.selected_run_agreement < policy.min_class_agreement:
            reasons.append("RUN_DISAGREEMENT")
        if case.std_probability > policy.max_probability_std:
            reasons.append("HIGH_DISPERSION")
        if case.run_support_count < policy.required_run_support:
            reasons.append("INSUFFICIENT_RUN_SUPPORT")
        disposition = "REVIEW" if reasons else "ACCEPT"
        if (
            decision.reasons != reasons
            or decision.disposition != disposition
            or decision.run_support_count != case.run_support_count
            or not math.isclose(decision.selected_run_probability, case.selected_run_probability, rel_tol=1e-12, abs_tol=1e-12)
            or not math.isclose(decision.confidence, confidence, rel_tol=1e-12, abs_tol=1e-12)
            or not math.isclose(decision.majority_class_agreement, case.majority_class_agreement, rel_tol=1e-12, abs_tol=1e-12)
            or not math.isclose(decision.selected_run_agreement, case.selected_run_agreement, rel_tol=1e-12, abs_tol=1e-12)
            or not math.isclose(decision.probability_std, case.std_probability, rel_tol=1e-12, abs_tol=1e-12)
        ):
            return False
        if disposition == "ACCEPT":
            accepted.append(case)
    case_count = len(analysis.cases)
    if not case_count:
        return False
    accepted_count = len(accepted)
    ranked_confidence = sorted(analysis.cases, key=lambda case: max(case.selected_run_probability, 1.0 - case.selected_run_probability), reverse=True)
    confidence_only = ranked_confidence[:accepted_count]
    random_selected = sorted(analysis.cases, key=lambda case: _stable_identity("stability-random-baseline-v1", case.case_id))[:accepted_count]

    def accepted_risk(cases: list[object]) -> float | None:
        if not cases:
            return None
        return sum(case.selected_run_class != case.target for case in cases) / len(cases)

    expected_comparisons = [
        ("NO_REVIEW", case_count, accepted_risk(analysis.cases), 1.0),
        ("RANDOM_REVIEW", len(random_selected), accepted_risk(random_selected), accepted_count / case_count),
        ("CONFIDENCE_ONLY", len(confidence_only), accepted_risk(confidence_only), accepted_count / case_count),
        ("STABILITY_AWARE", accepted_count, accepted_risk(accepted), accepted_count / case_count),
    ]
    if len(policy.risk_coverage) != len(expected_comparisons):
        return False
    for actual, (name, count, risk, coverage) in zip(policy.risk_coverage, expected_comparisons, strict=True):
        if (
            actual.policy != name
            or actual.accepted_count != count
            or actual.accepted_risk != risk
            or not math.isclose(actual.coverage, coverage, rel_tol=1e-12, abs_tol=1e-12)
        ):
            return False
    return True


def _selective_policy_risk_coverage_matches(
    policy: SelectivePredictionPolicy,
    evaluation: AnalysisEvaluation,
    threshold: DecisionThresholdPolicy,
    calibration: CalibrationTransform | None,
) -> bool:
    """Recompute the frozen confidence curve from validation evidence only."""
    rows = evaluation.prediction_preview
    if not rows:
        return False
    if policy.calibration_id is None:
        probabilities = np.asarray([
            row.probability if row.probability is not None
            else 1.0 / (1.0 + math.exp(-max(min(float(row.prediction), 60.0), -60.0)))
            for row in rows
        ], dtype=float)
    else:
        if calibration is None or calibration.evaluation_id != evaluation.evaluation_id:
            return False
        calibrated_by_row = {item.row: item.calibrated_probability for item in calibration.predictions}
        if len(calibrated_by_row) != len(calibration.predictions) or any(row.row not in calibrated_by_row for row in rows):
            return False
        probabilities = np.asarray([calibrated_by_row[row.row] for row in rows], dtype=float)
    targets = np.asarray([int(row.target >= 0.5) for row in rows], dtype=int)
    labels = (probabilities >= threshold.selected_threshold).astype(int)
    confidences = np.maximum(probabilities, 1.0 - probabilities)
    expected_cutoffs = np.round(np.arange(0.5, 1.0, 0.05), 2)
    if len(policy.risk_coverage) != len(expected_cutoffs):
        return False
    for actual, cutoff in zip(policy.risk_coverage, expected_cutoffs, strict=True):
        accepted = confidences >= cutoff
        accepted_count = int(accepted.sum())
        accepted_risk = None if accepted_count == 0 else float(np.mean(labels[accepted] != targets[accepted]))
        if (
            not math.isclose(actual.confidence_cutoff, float(cutoff), rel_tol=0.0, abs_tol=1e-12)
            or actual.accepted_count != accepted_count
            or not math.isclose(actual.coverage, accepted_count / len(rows), rel_tol=1e-12, abs_tol=1e-12)
            or (actual.accepted_risk is None) != (accepted_risk is None)
            or (accepted_risk is not None and not math.isclose(actual.accepted_risk, accepted_risk, rel_tol=1e-12, abs_tol=1e-12))
        ):
            return False
    return True


def _selective_policy_fit_identity_matches(
    policy: SelectivePredictionPolicy,
    evaluation: AnalysisEvaluation,
    threshold: DecisionThresholdPolicy,
    calibration: CalibrationTransform | None,
) -> bool:
    rows = evaluation.prediction_preview
    if calibration is None:
        probabilities = [
            row.probability if row.probability is not None
            else float(1.0 / (1.0 + np.exp(-row.prediction)))
            for row in rows
        ]
    else:
        by_row = {item.row: item.calibrated_probability for item in calibration.predictions}
        if len(by_row) != len(calibration.predictions) or any(row.row not in by_row for row in rows):
            return False
        probabilities = [float(by_row[row.row]) for row in rows]
    cases = [
        {
            "validation_row": int(row.row),
            "source_row": row.source_row,
            "target": int(row.target >= 0.5),
            "probability": float(probability),
        }
        for row, probability in zip(rows, probabilities, strict=True)
    ]
    identity = hashlib.sha256(json.dumps({
        "dataset": evaluation.dataset_fingerprint,
        "evaluation": str(evaluation.evaluation_id),
        "threshold": str(threshold.threshold_id),
        "calibration": None if calibration is None else str(calibration.calibration_id),
        "cases": cases,
    }, sort_keys=True).encode()).hexdigest()
    return policy.fit_sample_identity == identity


def _explanation_check_frozen_components_match(
    check: ExplanationCheck,
    explanation: ExplanationContract,
    run,
) -> bool:
    """Verify deterministic contract-derived checks without replaying explainers."""
    items = {item.name: item for item in check.checks}
    if len(items) != len(check.checks):
        return False
    preprocessing_identity = _stable_identity("preprocessing", run.normalization)
    feature_order_identity = _stable_identity("feature-order", list(run.feature_columns))
    sample_identity = _stable_identity(
        "explanation-sample",
        {"run_id": str(run.run_id), "sample": explanation.sample, "target": explanation.target},
    )
    reference_identity = _stable_identity(
        "explanation-reference",
        {"run_id": str(run.run_id), "method": explanation.method, "reference_definition": explanation.reference_definition},
    )
    expected_statuses = {
        "model_identity": "PASS" if run.model_artifact_sha256 == explanation.model_artifact_sha256 else "FAIL",
        "preprocessing_identity": "WARN" if explanation.preprocessing_identity is None else ("PASS" if explanation.preprocessing_identity == preprocessing_identity else "FAIL"),
        "preprocessing_artifact": "WARN" if explanation.preprocessing_artifact_sha256 is None else ("PASS" if explanation.preprocessing_artifact_sha256 == run.preprocessing_artifact_sha256 else "FAIL"),
        "feature_order_identity": "WARN" if explanation.feature_order_identity is None else ("PASS" if explanation.feature_order_identity == feature_order_identity else "FAIL"),
        "sample_target_identity": "WARN" if explanation.sample_identity is None else ("PASS" if explanation.sample_identity == sample_identity and explanation.target == run.target else "FAIL"),
        "reference_identity": "WARN" if explanation.reference_identity is None else ("PASS" if explanation.reference_identity == reference_identity else "FAIL"),
        "causal_validity": "N/A",
    }
    if explanation.completeness_error is None:
        expected_statuses["additivity"] = "N/A"
    else:
        if explanation.base_value is None:
            return False
        recomputed_error = abs(explanation.prediction - (explanation.base_value + sum(item.attribution for item in explanation.attributions)))
        tolerance = 5e-5 if explanation.family == "tree_shap" else (5e-3 if explanation.family in {"integrated_gradients", "shap"} else 5e-2)
        if not math.isclose(explanation.completeness_error, recomputed_error, rel_tol=1e-10, abs_tol=1e-12):
            return False
        expected_statuses["numerical_completeness"] = "PASS" if recomputed_error <= tolerance else "WARN"
    identity_failed = any(status == "FAIL" for name, status in expected_statuses.items() if name != "causal_validity")
    repeatability = items.get("repeatability")
    if repeatability is None or (identity_failed and repeatability.status != "N/A"):
        return False
    if not identity_failed and repeatability.status not in {"PASS", "FAIL"}:
        return False
    expected_statuses["repeatability"] = repeatability.status
    categories = {
        "model_identity": "provenance_identity",
        "preprocessing_identity": "provenance_identity",
        "preprocessing_artifact": "provenance_identity",
        "feature_order_identity": "provenance_identity",
        "sample_target_identity": "provenance_identity",
        "reference_identity": "provenance_identity",
        "repeatability": "replay_integrity",
        "additivity": "quantitative_quality",
        "numerical_completeness": "quantitative_quality",
        "causal_validity": "claim_boundary",
    }
    return all(
        name in items
        and items[name].status == status
        and items[name].category == categories[name]
        and items[name].validator_key == check.validator_key
        for name, status in expected_statuses.items()
    ) and set(items) == set(expected_statuses)


def _assurance_claim_graph_matches(case: AssuranceCase) -> bool:
    expected_claims = [
        (
            f"{gate.key.replace('_', ' ').capitalize()} is supported by the declared persisted evidence.",
            "SUPPORTED" if gate.status == "PASS" else "QUALIFIED",
            gate.evidence,
            ["Referenced evidence remains readable and correctly bound to its recorded provenance."],
            [gate.risk] if gate.risk else [],
        )
        for gate in case.gates if gate.evidence
    ]
    actual_claims = [
        (claim.statement, claim.status, claim.evidence_ids, claim.assumptions, claim.limitations)
        for claim in case.claims
    ]
    return (
        len({str(claim.claim_id) for claim in case.claims}) == len(case.claims)
        and actual_claims == expected_claims
        and case.unresolved_risks == [gate.risk for gate in case.gates if gate.risk]
    )


def _require_active_pointer(objects, pointer_path: Path, relative_path: str, code: str, label: str) -> ProjectIntegrityIssue | None:
    if objects and not pointer_path.exists():
        return ProjectIntegrityIssue(
            code=code,
            status="FAIL",
            path=relative_path,
            detail=f"Persisted {label} exist but the active pointer required by latest-object hydration is missing.",
        )
    return None


def _active_latest_pointer_issue(
    objects: list | dict,
    pointer_path: Path,
    relative_path: str,
    code: str,
    label: str,
    pointer_key: str,
    identity_attribute: str,
    *,
    require_latest: bool = True,
) -> ProjectIntegrityIssue | None:
    """Validate a persisted active pointer against its collection and latest object."""
    values = list(objects.values()) if isinstance(objects, dict) else list(objects)
    if values and not pointer_path.exists():
        return _require_active_pointer(values, pointer_path, relative_path, code, label)
    if not pointer_path.exists():
        return None
    try:
        payload = json.loads(pointer_path.read_text(encoding="utf-8"))
        active_id = payload[pointer_key]
        by_id = {str(getattr(item, identity_attribute)): item for item in values}
        active = by_id.get(str(active_id))
        if active is None:
            raise ValueError(f"Active {label} pointer does not resolve to persisted evidence.")
        if require_latest and all(hasattr(item, "created_at") for item in values):
            latest = max(values, key=lambda item: (item.created_at, str(getattr(item, identity_attribute))))
            if str(getattr(latest, identity_attribute)) != str(active_id):
                raise ValueError(f"Active {label} pointer does not identify the latest persisted object.")
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
        return ProjectIntegrityIssue(code=code, status="FAIL", path=relative_path, detail=str(error))
    return None


def _dataset_contract_profile_mismatch(contract: DatasetContract, profile: DatasetProfile) -> str | None:
    """Check that confirmed target/ID/feature roles agree with the profiled schema."""
    columns = [column.name for column in profile.columns]
    if len(columns) != len(set(columns)):
        return "DatasetProfile contains duplicate column names."
    if contract.target not in columns:
        return "DatasetContract target is absent from the DatasetProfile."
    if len(contract.id_columns) != len(set(contract.id_columns)) or not set(contract.id_columns) <= set(columns):
        return "DatasetContract ID columns are duplicated or absent from the DatasetProfile."
    if contract.target in contract.id_columns:
        return "DatasetContract target cannot also be an ID column."
    expected_features = [name for name in columns if name not in {contract.target, *contract.id_columns}]
    if contract.feature_columns != expected_features:
        return "DatasetContract feature columns/order do not match its confirmed target and ID roles."
    if contract.role_decisions:
        expected_roles = {
            name: "target" if name == contract.target else "id" if name in contract.id_columns else "feature"
            for name in columns
        }
        if contract.role_decisions != expected_roles:
            return "DatasetContract role_decisions do not match its target, ID, and feature columns."
    profile_payload = json.dumps([(column.name, column.dtype, column.semantic_type) for column in profile.columns]) + profile.source_artifact_sha256
    expected_fingerprint = hashlib.sha256(profile_payload.encode()).hexdigest()
    if profile.fingerprint != expected_fingerprint:
        return "DatasetProfile fingerprint does not match its persisted column schema and source artifact identity."
    if profile.source_artifact_sha256 != contract.source_artifact_sha256:
        return "DatasetProfile source artifact identity does not match the DatasetContract."
    return None


def _load_pointer_collection(
    base: Path,
    relative_dir: str,
    validator,
    identity_attribute: str,
    pointer_name: str,
    pointer_key: str,
    code: str,
    label: str,
    *,
    exclude: tuple[str, ...] = (),
    require_latest: bool = True,
) -> tuple[list, list[ProjectIntegrityIssue], int]:
    """Read a small persisted evidence family and verify its active/latest pointer."""
    root = base / relative_dir
    issues: list[ProjectIntegrityIssue] = []
    if root.exists() and not root.is_dir():
        return [], [ProjectIntegrityIssue(code=f"{code.removesuffix('_ACTIVE_POINTER_INVALID')}_EVIDENCE_MALFORMED", status="FAIL", path=relative_dir, detail="Persisted evidence path is not a directory.")], 0
    objects = []
    checked = 0
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            if path.name == pointer_name or path.name in exclude:
                continue
            checked += 1
            try:
                item = validator.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(getattr(item, identity_attribute)):
                    raise ValueError(f"{label} filename does not match its persisted identity.")
                objects.append(item)
            except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code=f"{code.removesuffix('_ACTIVE_POINTER_INVALID')}_EVIDENCE_MALFORMED", status="FAIL", path=str(path.relative_to(base)), detail=str(error)))
    pointer_issue = _active_latest_pointer_issue(
        objects,
        root / pointer_name,
        f"{relative_dir}/{pointer_name}",
        code,
        label,
        pointer_key,
        identity_attribute,
        require_latest=require_latest,
    )
    if pointer_issue is not None:
        issues.append(pointer_issue)
        checked += 1
    elif (root / pointer_name).exists():
        checked += 1
    return objects, issues, checked


def _inspect_auxiliary_evidence_integrity(
    base: Path,
    runs_by_id: dict,
    evaluations: dict,
    dataset_contract: DatasetContract | None,
    explanations: dict,
) -> tuple[list[ProjectIntegrityIssue], int]:
    """Check latest-object pointers for persisted evidence families not loaded above."""
    specs = (
        ("analyses/comparisons", AnalysisComparison, "active-comparison.json", "comparison_id", "comparison_id", "ANALYSIS_COMPARISON_ACTIVE_POINTER_INVALID"),
        ("analyses/slices", SliceAnalysis, "active-slice-analysis.json", "analysis_id", "analysis_id", "SLICE_ANALYSIS_ACTIVE_POINTER_INVALID"),
        ("evidence/explanation-reproducibility", ExplanationReproducibilityAnalysis, "active-analysis.json", "analysis_id", "analysis_id", "EXPLANATION_REPRODUCIBILITY_ACTIVE_POINTER_INVALID"),
        ("analyses/expert-corrections", ExpertCorrectionRevision, "active-correction.json", "correction_id", "correction_id", "EXPERT_CORRECTION_ACTIVE_POINTER_INVALID"),
        ("evidence/exhaustive-lab", ExhaustiveLabResult, "active-result.json", "result_id", "result_id", "EXHAUSTIVE_RESULT_ACTIVE_POINTER_INVALID"),
        # TreePathEvidence has no created_at field, so only referential integrity is meaningful.
        ("evidence/tree-paths", TreePathEvidence, "latest.json", "evidence_id", "evidence_id", "TREE_PATH_ACTIVE_POINTER_INVALID"),
    )
    issues: list[ProjectIntegrityIssue] = []
    checked = 0
    for relative_dir, validator, pointer_name, pointer_key, identity_attribute, code in specs:
        objects, family_issues, family_checked = _load_pointer_collection(
            base,
            relative_dir,
            validator,
            identity_attribute,
            pointer_name,
            pointer_key,
            code,
            relative_dir.rsplit("/", 1)[-1],
            require_latest=relative_dir != "evidence/tree-paths",
        )
        issues.extend(family_issues)
        checked += family_checked
        for item in objects:
            relative_path = f"{relative_dir}/{getattr(item, identity_attribute)}.json"
            try:
                if isinstance(item, AnalysisComparison):
                    compared_runs = [runs_by_id.get(run_id) for run_id in item.run_ids]
                    if (
                        len(set(item.run_ids)) != len(item.run_ids)
                        or any(run is None for run in compared_runs)
                        or any(run.task != item.task or run.target != item.target or run.evaluation_split != "validation" or run.split.test_status != "LOCKED_NOT_EVALUATED" for run in compared_runs if run is not None)
                        or len({run.dataset_fingerprint for run in compared_runs if run is not None}) > 1
                    ):
                        raise ValueError("AnalysisComparison run, task, target, dataset, or validation provenance is inconsistent.")
                    expected_dataset = next((run.dataset_fingerprint for run in compared_runs if run is not None and run.dataset_fingerprint is not None), None)
                    if (item.dataset_fingerprint is not None and item.dataset_fingerprint != expected_dataset) or (dataset_contract is not None and expected_dataset is not None and expected_dataset != dataset_contract.dataset_fingerprint):
                        raise ValueError("AnalysisComparison dataset fingerprint does not match its runs.")
                    run_rows = [row for row in item.metric_rows if row.get("subject_type") == "training_run"]
                    rows_by_run = {str(row.get("run_id")): row for row in run_rows}
                    if len(run_rows) != len(item.run_ids) or len(rows_by_run) != len(run_rows) or set(rows_by_run) != {str(run_id) for run_id in item.run_ids}:
                        raise ValueError("AnalysisComparison must contain exactly one metric row for each referenced TrainingRun.")
                    for run in compared_runs:
                        row = rows_by_run[str(run.run_id)]
                        if row.get("subject_id") != f"run:{run.run_id}" or row.get("model_kind") != run.model_kind:
                            raise ValueError("AnalysisComparison subject row does not match its TrainingRun identity.")
                        for metric, expected_value in run.validation_metrics.items():
                            if metric not in row or not math.isclose(float(row[metric]), float(expected_value), rel_tol=1e-12, abs_tol=1e-12):
                                raise ValueError("AnalysisComparison validation metrics differ from the persisted TrainingRun.")
                    if item.schema_version >= 2:
                        expected_identities = {
                            str(run.run_id): identity
                            for run in compared_runs
                            if (identity := _validation_sample_identity(run)) is not None
                        }
                        if item.fis_id is not None and item.validation_alignment == "same_cases" and expected_identities:
                            expected_identities[f"fis:{item.fis_id}"] = next(iter(expected_identities.values()))
                        if item.validation_sample_identities != expected_identities:
                            raise ValueError("AnalysisComparison validation case identities do not match its referenced runs.")
                        alignment = "unknown" if len(expected_identities) < len(compared_runs) else "same_cases" if len(set(expected_identities.values())) == 1 else "mixed_cases"
                        if item.validation_alignment != alignment:
                            raise ValueError("AnalysisComparison alignment label does not match its frozen validation identities.")
                    if (item.fis_id is None) != (item.fis_semantic_hash is None):
                        raise ValueError("AnalysisComparison manual FIS identity and semantic hash must be bound together.")
                    if item.fis_id is not None:
                        fis = load_fis(base, str(item.fis_id))
                        if fis.semantic_hash != item.fis_semantic_hash:
                            raise ValueError("AnalysisComparison manual FIS semantic hash does not match its persisted FIS.")
                elif isinstance(item, SliceAnalysis):
                    evaluation = evaluations.get(item.evaluation_id)
                    if (
                        evaluation is None
                        or evaluation.run_id != item.run_id
                        or evaluation.split != "validation"
                        or evaluation.dataset_fingerprint != item.dataset_fingerprint
                        or (dataset_contract is not None and item.dataset_fingerprint != dataset_contract.dataset_fingerprint)
                        or item.source_split != "validation"
                        or item.test_status != "LOCKED_NOT_EVALUATED"
                    ):
                        raise ValueError("SliceAnalysis does not resolve to its exact validation Evaluation, TrainingRun, and DatasetContract.")
                    if item.generalization_contract_id is not None:
                        scope = load_generalization_contract(base, item.generalization_contract_id)
                        if scope.dataset_fingerprint != item.dataset_fingerprint:
                            raise ValueError("SliceAnalysis GeneralizationContract belongs to a different dataset revision.")
                    definition_names = [definition.name for definition in item.definitions]
                    result_names = [result.name for result in item.results]
                    if len(set(definition_names)) != len(definition_names) or set(result_names) != set(definition_names) or any(result.metric != item.metric for result in item.results):
                        raise ValueError("SliceAnalysis result rows do not match their frozen definitions and metric.")
                elif isinstance(item, TreePathEvidence):
                    run = runs_by_id.get(item.run_id)
                    if run is None or run.model_kind != "decision_tree" or item.model_artifact_sha256 != run.model_artifact_sha256:
                        raise ValueError("TreePathEvidence does not resolve to its exact frozen Decision Tree artifact.")
                    store = ArtifactStore(base)
                    with store.open(ArtifactRef(sha256=run.model_artifact_sha256)) as handle:
                        payload = json.loads(handle.read().decode("utf-8"))
                    if (
                        payload.get("format") != "ruflex.declarative-decision-tree/v1"
                        or payload.get("feature_columns") != run.feature_columns
                        or item.preprocessing_identity != json.dumps(payload.get("normalization", {}), sort_keys=True)
                        or set(item.input_sample) != set(run.feature_columns)
                        or any(step.feature_name not in run.feature_columns for step in item.steps)
                    ):
                        raise ValueError("TreePathEvidence input/path feature identities do not match its TrainingRun.")
                    tree = payload["tree"]
                    columns = payload["feature_columns"]
                    normal = payload["normalization"]
                    centers = normal.get("center") or [0.0] * len(columns)
                    scales = normal.get("scale") or [1.0] * len(columns)
                    node = 0
                    expected_steps = []
                    while tree["children_left"][node] != -1:
                        feature_index = tree["feature_index"][node]
                        feature_name = columns[feature_index]
                        threshold = float(tree["threshold"][node])
                        value = (float(item.input_sample[feature_name]) - float(centers[feature_index])) / max(float(scales[feature_index]), 1e-12)
                        decision = "left" if value <= threshold else "right"
                        expected_steps.append((node, feature_name, threshold, value, decision))
                        node = tree["children_left"][node] if decision == "left" else tree["children_right"][node]
                    actual_steps = [(step.node_id, step.feature_name, step.threshold, step.value, step.decision) for step in item.steps]
                    if len(actual_steps) != len(expected_steps) or any(
                        actual[:2] != expected[:2]
                        or actual[4] != expected[4]
                        or not math.isclose(actual[2], expected[2], rel_tol=1e-12, abs_tol=1e-12)
                        or not math.isclose(actual[3], expected[3], rel_tol=1e-12, abs_tol=1e-12)
                        for actual, expected in zip(actual_steps, expected_steps, strict=True)
                    ) or item.leaf_id != node:
                        raise ValueError("TreePathEvidence steps or leaf do not replay from its frozen Decision Tree artifact.")
                    values = [float(value) for value in tree["values"][node]]
                    if payload.get("task") == "binary_classification":
                        total = max(sum(values), 1e-12)
                        expected_probabilities = {str(index): value / total for index, value in enumerate(values)}
                        expected_prediction = float(max(expected_probabilities, key=expected_probabilities.get))
                        if item.class_probabilities is None or set(item.class_probabilities) != set(expected_probabilities) or any(
                            not math.isclose(item.class_probabilities[key], value, rel_tol=1e-12, abs_tol=1e-12)
                            for key, value in expected_probabilities.items()
                        ):
                            raise ValueError("TreePathEvidence class probabilities do not match its frozen Decision Tree leaf.")
                    else:
                        expected_probabilities = None
                        expected_prediction = values[0]
                        if item.class_probabilities is not None:
                            raise ValueError("Regression TreePathEvidence must not contain class probabilities.")
                    if not math.isclose(item.prediction, expected_prediction, rel_tol=1e-12, abs_tol=1e-12):
                        raise ValueError("TreePathEvidence prediction does not match its frozen Decision Tree leaf.")
                elif isinstance(item, ExplanationReproducibilityAnalysis):
                    analysis_runs = [runs_by_id.get(run_id) for run_id in item.run_ids]
                    analysis_explanations = [explanations.get(explanation_id) for explanation_id in item.explanation_ids]
                    if (
                        len(set(item.run_ids)) != len(item.run_ids)
                        or len(set(item.explanation_ids)) != len(item.explanation_ids)
                        or any(run is None for run in analysis_runs)
                        or any(explanation is None for explanation in analysis_explanations)
                        or any(explanation.run_id not in item.run_ids for explanation in analysis_explanations if explanation is not None)
                        or any(run.dataset_fingerprint != item.dataset_fingerprint or run.task != item.task or run.target != item.target for run in analysis_runs if run is not None)
                        or any(explanation.method != item.explanation_method or explanation.reference_definition != item.reference_protocol for explanation in analysis_explanations if explanation is not None)
                    ):
                        raise ValueError("ExplanationReproducibilityAnalysis does not resolve to its exact runs and ExplanationContracts.")
                    expected_case_values = sorted(
                        row.source_row if row.source_row is not None else row.row
                        for row in analysis_runs[0].prediction_preview
                    ) if analysis_runs else []
                    expected_cases = [str(value) for value in expected_case_values]
                    run_case_sets = [
                        [
                            row.source_row if row.source_row is not None else row.row
                            for row in run.prediction_preview
                        ]
                        for run in analysis_runs
                        if run is not None
                    ]
                    if (
                        len(expected_case_values) != len(set(expected_case_values))
                        or any(len(values) != len(set(values)) or sorted(values) != expected_case_values for values in run_case_sets)
                        or item.validation_case_identities != expected_cases
                    ):
                        raise ValueError("ExplanationReproducibilityAnalysis validation case identities do not align across its runs.")
                elif isinstance(item, ExpertCorrectionRevision):
                    revisions = list_fis_revisions(base, str(item.fis_id))
                    revision_hashes = {revision.semantic_hash for revision in revisions}
                    if item.source_semantic_hash not in revision_hashes or item.result_semantic_hash not in revision_hashes:
                        raise ValueError("ExpertCorrectionRevision source/result semantic hashes do not resolve to persisted FIS revisions.")
                    if dataset_contract is not None and (
                        item.dataset_fingerprint != dataset_contract.dataset_fingerprint
                        or item.target != dataset_contract.target
                    ):
                        raise ValueError("ExpertCorrectionRevision belongs to a different DatasetContract revision.")
                    if item.source_explanation_id is not None and item.source_explanation_id not in explanations:
                        raise ValueError("ExpertCorrectionRevision source explanation does not resolve to persisted evidence.")
                elif isinstance(item, ExhaustiveLabResult):
                    if item.kind == "decision_tree_structure":
                        run = runs_by_id.get(item.run_id)
                        if run is None or run.model_kind != "decision_tree":
                            raise ValueError("Exhaustive Decision Tree result does not resolve to a persisted Decision Tree TrainingRun.")
                    else:
                        known_hashes = {revision.semantic_hash for revision in list_fis_revisions(base)}
                        if item.fis_semantic_hash not in known_hashes or item.run_id is not None:
                            raise ValueError("Exhaustive FIS grid result does not resolve to a persisted FIS semantic identity.")
            except (ValueError, TypeError, KeyError, IndexError, OSError, ValidationError, DatasetConfirmationError) as error:
                code = {
                    AnalysisComparison: "ANALYSIS_COMPARISON_PROVENANCE_MISMATCH",
                    SliceAnalysis: "SLICE_ANALYSIS_PROVENANCE_MISMATCH",
                    TreePathEvidence: "TREE_PATH_PROVENANCE_MISMATCH",
                    ExplanationReproducibilityAnalysis: "EXPLANATION_REPRODUCIBILITY_PROVENANCE_MISMATCH",
                    ExpertCorrectionRevision: "EXPERT_CORRECTION_PROVENANCE_MISMATCH",
                    ExhaustiveLabResult: "EXHAUSTIVE_RESULT_PROVENANCE_MISMATCH",
                }[type(item)]
                issues.append(ProjectIntegrityIssue(code=code, status="FAIL", path=relative_path, detail=str(error)))
    return issues, checked


def _final_test_freeze_timestamps_match(
    final_test: FinalTestEvaluation,
    run,
    evaluation: AnalysisEvaluation | None,
    threshold: DecisionThresholdPolicy | None,
    calibration: CalibrationTransform | None,
    selective_policy: SelectivePredictionPolicy | None,
    stability_policy: StabilityGatePolicy | None,
    stability_analysis: StudyStabilityAnalysis | None,
    stability_runs: list,
) -> bool:
    unlock = final_test.dataset_test_unlock_at
    frozen_at = final_test.policy_frozen_at
    if unlock is None or frozen_at is None or run is None or evaluation is None:
        return False
    source_objects = [run, evaluation, threshold, calibration, selective_policy, stability_policy]
    source_times = [item.created_at for item in source_objects if item is not None]
    protected_times = list(source_times)
    if stability_policy is not None:
        if stability_analysis is None or stability_policy.frozen_at < stability_policy.created_at:
            return False
        if stability_analysis.created_at > stability_policy.created_at:
            return False
        if any(item.created_at > stability_policy.created_at for item in stability_runs):
            return False
        protected_times.extend([stability_policy.frozen_at, stability_analysis.created_at])
        protected_times.extend(item.created_at for item in stability_runs)
    timestamps = [unlock, frozen_at, *protected_times]
    if any(item.tzinfo is None or item.utcoffset() is None for item in timestamps):
        return False
    return frozen_at == max(source_times) and all(item <= unlock for item in protected_times)


def inspect_project_integrity(root: Path) -> ProjectIntegrityReport:
    """Inspect persisted evidence without reopening or retraining artifacts.

    Missing optional objects are not failures; malformed persisted evidence or a
    broken reference is.  This makes projects inspectable even when a workflow
    is intentionally incomplete.
    """
    project = ProjectService().open(root, read_only=True)
    base = project.root
    issues: list[ProjectIntegrityIssue] = []
    checked = 1
    contract: DatasetContract | None = None
    if (base / "data" / "dataset-contract.json").exists():
        try:
            contract = load_dataset_contract(base); profile = load_dataset_profile(base); audit = load_data_audit(base); checked += 3
            if profile.fingerprint != contract.dataset_fingerprint or audit.dataset_fingerprint != contract.dataset_fingerprint:
                issues.append(ProjectIntegrityIssue(code="DATASET_IDENTITY_MISMATCH", status="FAIL", path="data", detail="Dataset profile, audit, and contract do not share a dataset fingerprint."))
            role_mismatch = _dataset_contract_profile_mismatch(contract, profile)
            if role_mismatch is not None:
                issues.append(ProjectIntegrityIssue(code="DATASET_ROLE_CONTRACT_MISMATCH", status="FAIL", path="data/dataset-contract.json", detail=role_mismatch))
            verification = ArtifactStore(base).verify(ArtifactRef(sha256=contract.source_artifact_sha256)); checked += 1
            if not verification.valid: issues.append(ProjectIntegrityIssue(code="DATASET_ARTIFACT_INVALID", status="FAIL", path="data/dataset-contract.json", detail=verification.message))
        except (FileNotFoundError, ValidationError, ValueError) as error:
            issues.append(ProjectIntegrityIssue(code="DATASET_EVIDENCE_MALFORMED", status="FAIL", path="data", detail=str(error)))
    elif any((base / "data").glob("*.json")):
        issues.append(ProjectIntegrityIssue(code="DATASET_EVIDENCE_INCOMPLETE", status="FAIL", path="data", detail="Dataset evidence exists but the canonical DatasetContract is missing."))
    split_root = base / "data" / "splits"
    persisted_splits: dict[object, SplitContract] = {}
    if split_root.exists() and not split_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="SPLIT_CONTRACT_EVIDENCE_MALFORMED", status="FAIL", path="data/splits", detail="Split-contract evidence path is not a directory."))
    elif split_root.is_dir():
        for path in sorted(split_root.glob("*.json")):
            checked += 1
            try:
                split = SplitContract.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(split.split_id): raise ValueError("SplitContract filename does not match its persisted identity.")
                load_split_contract(base, split.split_id)
                persisted_splits[split.split_id] = split
            except (FileNotFoundError, ValidationError, ValueError, DatasetConfirmationError, OSError) as error:
                issues.append(ProjectIntegrityIssue(code="SPLIT_CONTRACT_EVIDENCE_MALFORMED", status="FAIL", path=str(path.relative_to(base)), detail=str(error)))
    active_split_path = base / "data" / "active-split-contract.json"
    split_pointer_issue = _active_latest_pointer_issue(
        persisted_splits,
        active_split_path,
        "data/active-split-contract.json",
        "SPLIT_CONTRACT_ACTIVE_POINTER_INVALID",
        "SplitContract",
        "split_id",
        "split_id",
        require_latest=False,
    )
    if split_pointer_issue is not None:
        issues.append(split_pointer_issue)
        checked += 1
    elif active_split_path.exists():
        checked += 1
        try:
            pointer = json.loads(active_split_path.read_text(encoding="utf-8"))
            active_split = next((item for item in persisted_splits.values() if str(item.split_id) == str(pointer["split_id"])), None)
            if active_split is None:
                raise ValueError("Active SplitContract pointer does not resolve to persisted evidence.")
            if pointer.get("split_identity") != active_split.split_identity:
                raise ValueError("Active SplitContract pointer identity does not match its persisted contract.")
            load_split_contract(base, active_split.split_id)
        except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError, DatasetConfirmationError) as error:
            issues.append(ProjectIntegrityIssue(code="SPLIT_CONTRACT_ACTIVE_POINTER_INVALID", status="FAIL", path="data/active-split-contract.json", detail=str(error)))
    transform_root = base / "data" / "transforms"
    if transform_root.exists() and not transform_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="TRANSFORM_PIPELINE_EVIDENCE_MALFORMED", status="FAIL", path="data/transforms", detail="Transform-pipeline evidence path is not a directory."))
    elif transform_root.is_dir():
        for path in sorted(transform_root.glob("*.json")):
            checked += 1
            try:
                pipeline = TransformPipelineContract.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(pipeline.pipeline_id): raise ValueError("TransformPipelineContract filename does not match its persisted identity.")
                resolved = load_transform_pipeline_contract(base, pipeline.pipeline_id)
                if contract is not None and resolved.feature_order != contract.feature_columns:
                    raise DatasetConfirmationError("TransformPipelineContract feature order does not match the active DatasetContract.")
                preprocessing = ArtifactStore(base).verify(ArtifactRef(sha256=resolved.preprocessing_artifact_sha256)); checked += 1
                if not preprocessing.valid:
                    raise DatasetConfirmationError(f"TransformPipelineContract preprocessing artifact is invalid: {preprocessing.message}")
            except (FileNotFoundError, ValidationError, ValueError, DatasetConfirmationError, OSError) as error:
                issues.append(ProjectIntegrityIssue(code="TRANSFORM_PIPELINE_EVIDENCE_MALFORMED", status="FAIL", path=str(path.relative_to(base)), detail=str(error)))
    leakage_root = base / "data" / "leakage-audits"
    if leakage_root.exists() and not leakage_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="LEAKAGE_AUDIT_EVIDENCE_MALFORMED", status="FAIL", path="data/leakage-audits", detail="Leakage-audit evidence path is not a directory."))
    elif leakage_root.is_dir():
        for path in sorted(leakage_root.glob("*.json")):
            checked += 1
            try:
                audit = LeakageAuditReport.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(audit.audit_id): raise ValueError("LeakageAuditReport filename does not match its persisted identity.")
                load_leakage_audit(base, audit.audit_id)
                expected_status = "FAIL" if any(item.severity == "fail" for item in audit.findings) else "WARN" if audit.findings else "PASS"
                if any(item.severity not in {"fail", "warning"} for item in audit.findings) or audit.status != expected_status:
                    raise DatasetConfirmationError("LeakageAuditReport status does not match its persisted findings.")
                if audit.transform_pipeline_id is not None:
                    pipeline = load_transform_pipeline_contract(base, audit.transform_pipeline_id)
                    if contract is not None and pipeline.feature_order != contract.feature_columns:
                        raise DatasetConfirmationError("TransformPipelineContract feature order does not match the active DatasetContract.")
                    if pipeline.split_contract_id != audit.split_contract_id:
                        raise DatasetConfirmationError("LeakageAuditReport split does not match its referenced TransformPipelineContract.")
            except (FileNotFoundError, ValidationError, ValueError, DatasetConfirmationError, OSError) as error:
                issues.append(ProjectIntegrityIssue(code="LEAKAGE_AUDIT_EVIDENCE_MALFORMED", status="FAIL", path=str(path.relative_to(base)), detail=str(error)))
    try:
        runs = list_training_runs(base); checked += len(runs)
    except (ValidationError, ValueError, FileNotFoundError) as error:
        runs = []
        issues.append(ProjectIntegrityIssue(code="TRAINING_EVIDENCE_MALFORMED", status="FAIL", path="runs", detail=str(error)))
    active_run_path = base / "runs" / "active-training-run.json"
    if runs and not active_run_path.exists():
        issues.append(ProjectIntegrityIssue(code="TRAINING_RUN_ACTIVE_POINTER_INVALID", status="FAIL", path="runs/active-training-run.json", detail="Persisted TrainingRuns exist but the active-run pointer required by latest-run hydration is missing."))
    if active_run_path.exists():
        checked += 1
        try:
            active_run_id = json.loads(active_run_path.read_text(encoding="utf-8"))["run_id"]
            if str(active_run_id) not in {str(run.run_id) for run in runs}:
                raise ValueError("Active TrainingRun pointer does not resolve to persisted evidence.")
            latest_run = max(runs, key=lambda item: (item.created_at, str(item.run_id)), default=None)
            if latest_run is not None and str(latest_run.run_id) != str(active_run_id):
                raise ValueError("Active TrainingRun pointer does not identify the latest persisted run.")
        except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
            issues.append(ProjectIntegrityIssue(code="TRAINING_RUN_ACTIVE_POINTER_INVALID", status="FAIL", path="runs/active-training-run.json", detail=str(error)))
    store = ArtifactStore(base)
    fis_root = base / "models" / "fis"
    if fis_root.exists() and not fis_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="FIS_EVIDENCE_MALFORMED", status="FAIL", path="models/fis", detail="FIS evidence path is not a directory."))
    elif fis_root.is_dir():
        fis_paths = sorted(fis_root.glob("*.json"))
        fis_ids: set[str] = set()
        for path in fis_paths:
            checked += 1
            relative_path = str(path.relative_to(base))
            try:
                spec = load_fis(base, path.stem)
                if str(spec.fis_id) != path.stem:
                    raise ValueError("FIS filename does not match its persisted identity.")
                fis_ids.add(path.stem)
                list_fis_revisions(base, path.stem); checked += 1
            except (FileNotFoundError, ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="FIS_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
        active_path = fis_root / "active.txt"
        if active_path.exists():
            checked += 1
            try:
                active_id = active_path.read_text(encoding="utf-8").strip()
                if active_id not in fis_ids:
                    raise ValueError("Active FIS pointer does not resolve to a persisted FIS.")
            except (ValueError, OSError) as error:
                issues.append(ProjectIntegrityIssue(code="FIS_ACTIVE_POINTER_INVALID", status="FAIL", path="models/fis/active.txt", detail=str(error)))
    import_root = base / "models" / "fis" / "imports"
    if import_root.exists() and not import_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="IMPORTED_FIS_PROVENANCE_MALFORMED", status="FAIL", path="models/fis/imports", detail="Imported FIS provenance path is not a directory."))
    elif import_root.is_dir():
        for receipt_path in sorted(import_root.glob("*.json")):
            checked += 1
            relative_path = str(receipt_path.relative_to(base))
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                required = ("fis_id", "semantic_hash", "source_format", "source_artifact_sha256", "importer", "importer_version")
                if not all(isinstance(receipt.get(field), str) and receipt[field] for field in required):
                    raise ValueError("Import receipt is missing a required non-empty identity field.")
                if receipt["source_format"] != "matlab_fis" or receipt["importer"] != "ruflex_matlab_fis_importer" or receipt["importer_version"] != "1":
                    raise ValueError("Import receipt declares an unsupported importer provenance.")
                if receipt_path.stem != receipt["fis_id"]:
                    raise ValueError("Import receipt filename does not match its FIS identity.")
                source_ref = ArtifactRef(sha256=receipt["source_artifact_sha256"])
                verification = store.verify(source_ref); checked += 1
                if not verification.valid:
                    issues.append(ProjectIntegrityIssue(code="IMPORTED_FIS_SOURCE_ARTIFACT_INVALID", status="FAIL", path=relative_path, detail=verification.message))
                    continue
                source_record = ArtifactRecord.model_validate_json((base / "objects" / "artifacts" / f"{source_ref.sha256}.json").read_text(encoding="utf-8")); checked += 1
                if source_record.source_kind != "imported" or source_record.source_uri != "matlab_fis_import":
                    issues.append(ProjectIntegrityIssue(code="IMPORTED_FIS_SOURCE_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="Import receipt source artifact is not a MATLAB FIS imported artifact."))
                spec = load_fis(base, receipt["fis_id"]); checked += 1
                if spec.semantic_hash != receipt["semantic_hash"]:
                    issues.append(ProjectIntegrityIssue(code="IMPORTED_FIS_SEMANTIC_MISMATCH", status="FAIL", path=relative_path, detail="Import receipt semantic hash does not match the persisted FIS."))
            except (FileNotFoundError, ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="IMPORTED_FIS_PROVENANCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
    runs_by_id = {run.run_id: run for run in runs}
    evaluation_root = base / "analyses" / "evaluations"
    evaluations: dict[object, AnalysisEvaluation] = {}
    if evaluation_root.exists() and not evaluation_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="VALIDATION_EVALUATION_EVIDENCE_MALFORMED", status="FAIL", path="analyses/evaluations", detail="Validation Evaluation evidence path is not a directory."))
    elif evaluation_root.is_dir():
        for path in sorted(evaluation_root.glob("*.json")):
            if path.name == "active-evaluation.json":
                continue
            checked += 1
            relative_path = str(path.relative_to(base))
            try:
                evaluation = AnalysisEvaluation.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(evaluation.evaluation_id):
                    raise ValueError("Validation Evaluation filename does not match its persisted identity.")
                evaluations[evaluation.evaluation_id] = evaluation
                run = runs_by_id.get(evaluation.run_id)
                if run is None:
                    issues.append(ProjectIntegrityIssue(code="VALIDATION_EVALUATION_RUN_MISSING", status="FAIL", path=relative_path, detail="Validation Evaluation references a TrainingRun that is not present."))
                    continue
                provenance_matches = (
                    evaluation.task == run.task
                    and evaluation.target == run.target
                    and evaluation.model_kind == run.model_kind
                    and evaluation.model_artifact_sha256 == run.model_artifact_sha256
                    and (run.dataset_fingerprint is None or evaluation.dataset_fingerprint == run.dataset_fingerprint)
                    and (run.dataset_artifact_sha256 is None or evaluation.dataset_artifact_sha256 == run.dataset_artifact_sha256)
                    and evaluation.preprocessing_artifact_sha256 == run.preprocessing_artifact_sha256
                    and evaluation.prediction_preview == run.prediction_preview
                    and evaluation.validation_row_count == len(run.prediction_preview)
                )
                if not provenance_matches:
                    issues.append(ProjectIntegrityIssue(code="VALIDATION_EVALUATION_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="Validation Evaluation does not match its frozen TrainingRun, dataset, preprocessing, or complete validation predictions."))
            except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="VALIDATION_EVALUATION_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
        active_path = evaluation_root / "active-evaluation.json"
        missing_pointer = _require_active_pointer(evaluations, active_path, "analyses/evaluations/active-evaluation.json", "VALIDATION_EVALUATION_ACTIVE_POINTER_INVALID", "validation Evaluations")
        if missing_pointer is not None:
            checked += 1; issues.append(missing_pointer)
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["evaluation_id"]
                if str(active_id) not in {str(key) for key in evaluations}:
                    raise ValueError("Active validation Evaluation pointer does not resolve to persisted evidence.")
                latest_evaluation = max(evaluations.values(), key=lambda item: (item.created_at, str(item.evaluation_id)), default=None)
                if latest_evaluation is not None and str(latest_evaluation.evaluation_id) != str(active_id):
                    raise ValueError("Active validation Evaluation pointer does not identify the latest persisted Evaluation.")
            except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="VALIDATION_EVALUATION_ACTIVE_POINTER_INVALID", status="FAIL", path="analyses/evaluations/active-evaluation.json", detail=str(error)))
    calibration_root = base / "analyses" / "calibrations"
    calibrations: dict[object, CalibrationTransform] = {}
    if calibration_root.exists() and not calibration_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="CALIBRATION_EVIDENCE_MALFORMED", status="FAIL", path="analyses/calibrations", detail="Calibration evidence path is not a directory."))
    elif calibration_root.is_dir():
        for path in sorted(calibration_root.glob("*.json")):
            if path.name == "active-calibration.json":
                continue
            checked += 1
            relative_path = str(path.relative_to(base))
            try:
                calibration = CalibrationTransform.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(calibration.calibration_id):
                    raise ValueError("Calibration filename does not match its persisted identity.")
                calibrations[calibration.calibration_id] = calibration
                evaluation = evaluations.get(calibration.evaluation_id)
                if evaluation is None or evaluation.run_id != calibration.run_id or evaluation.split != "validation":
                    issues.append(ProjectIntegrityIssue(code="CALIBRATION_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="Calibration does not resolve to its exact validation Evaluation and TrainingRun."))
                elif not _calibration_evidence_matches(calibration, evaluation):
                    issues.append(ProjectIntegrityIssue(code="CALIBRATION_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="Calibration predictions, validation identities, fit sample identity, or descriptive metrics do not match the exact Evaluation and persisted transform."))
            except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="CALIBRATION_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
        active_path = calibration_root / "active-calibration.json"
        missing_pointer = _require_active_pointer(calibrations, active_path, "analyses/calibrations/active-calibration.json", "CALIBRATION_ACTIVE_POINTER_INVALID", "calibration transforms")
        if missing_pointer is not None:
            checked += 1; issues.append(missing_pointer)
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["calibration_id"]
                if str(active_id) not in {str(key) for key in calibrations}:
                    raise ValueError("Active calibration pointer does not resolve to persisted evidence.")
                latest_calibration = max(calibrations.values(), key=lambda item: (item.created_at, str(item.calibration_id)), default=None)
                if latest_calibration is not None and str(latest_calibration.calibration_id) != str(active_id):
                    raise ValueError("Active calibration pointer does not identify the latest persisted transform.")
            except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="CALIBRATION_ACTIVE_POINTER_INVALID", status="FAIL", path="analyses/calibrations/active-calibration.json", detail=str(error)))
    threshold_root = base / "analyses" / "thresholds"
    thresholds: dict[object, DecisionThresholdPolicy] = {}
    if threshold_root.exists() and not threshold_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="DECISION_THRESHOLD_EVIDENCE_MALFORMED", status="FAIL", path="analyses/thresholds", detail="Decision-threshold evidence path is not a directory."))
    elif threshold_root.is_dir():
        for path in sorted(threshold_root.glob("*.json")):
            if path.name == "active-threshold.json":
                continue
            checked += 1
            relative_path = str(path.relative_to(base))
            try:
                threshold = DecisionThresholdPolicy.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(threshold.threshold_id):
                    raise ValueError("Decision-threshold filename does not match its persisted identity.")
                thresholds[threshold.threshold_id] = threshold
                evaluation = evaluations.get(threshold.evaluation_id)
                calibration = calibrations.get(threshold.calibration_id) if threshold.calibration_id else None
                if (
                    evaluation is None
                    or evaluation.run_id != threshold.run_id
                    or (threshold.calibration_id is not None and (calibration is None or calibration.evaluation_id != threshold.evaluation_id))
                    or (threshold.probability_source == "raw" and threshold.calibration_id is not None)
                    or (threshold.probability_source == "calibrated" and threshold.calibration_id is None)
                    or (threshold.decisions and len(threshold.decisions) != evaluation.validation_row_count)
                    or not _threshold_evidence_matches(threshold, evaluation, calibration)
                ):
                    issues.append(ProjectIntegrityIssue(code="DECISION_THRESHOLD_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="Decision threshold does not match its exact validation Evaluation, calibration, probability source, or case support."))
            except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="DECISION_THRESHOLD_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
        active_path = threshold_root / "active-threshold.json"
        missing_pointer = _require_active_pointer(thresholds, active_path, "analyses/thresholds/active-threshold.json", "DECISION_THRESHOLD_ACTIVE_POINTER_INVALID", "decision thresholds")
        if missing_pointer is not None:
            checked += 1; issues.append(missing_pointer)
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["threshold_id"]
                if str(active_id) not in {str(key) for key in thresholds}:
                    raise ValueError("Active decision-threshold pointer does not resolve to persisted evidence.")
                latest_threshold = max(thresholds.values(), key=lambda item: (item.created_at, str(item.threshold_id)), default=None)
                if latest_threshold is not None and str(latest_threshold.threshold_id) != str(active_id):
                    raise ValueError("Active decision-threshold pointer does not identify the latest persisted policy.")
            except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="DECISION_THRESHOLD_ACTIVE_POINTER_INVALID", status="FAIL", path="analyses/thresholds/active-threshold.json", detail=str(error)))
    selective_root = base / "analyses" / "selective-policies"
    selective_policies: dict[object, SelectivePredictionPolicy] = {}
    if selective_root.exists() and not selective_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="SELECTIVE_POLICY_EVIDENCE_MALFORMED", status="FAIL", path="analyses/selective-policies", detail="Selective-policy evidence path is not a directory."))
    elif selective_root.is_dir():
        for path in sorted(selective_root.glob("*.json")):
            if path.name == "active-policy.json":
                continue
            checked += 1
            relative_path = str(path.relative_to(base))
            try:
                policy = SelectivePredictionPolicy.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(policy.policy_id):
                    raise ValueError("Selective-policy filename does not match its persisted identity.")
                selective_policies[policy.policy_id] = policy
                evaluation = evaluations.get(policy.evaluation_id)
                threshold = thresholds.get(policy.class_threshold_id)
                calibration = calibrations.get(policy.calibration_id) if policy.calibration_id else None
                if (
                    evaluation is None
                    or threshold is None
                    or evaluation.run_id != policy.run_id
                    or threshold.evaluation_id != policy.evaluation_id
                    or threshold.run_id != policy.run_id
                    or threshold.selected_threshold != policy.class_threshold
                    or threshold.calibration_id != policy.calibration_id
                    or (policy.calibration_id is not None and (calibration is None or calibration.evaluation_id != policy.evaluation_id))
                    or policy.source_split != "validation"
                    or policy.probability_source != ("raw" if policy.calibration_id is None else "calibrated")
                    or not _selective_policy_fit_identity_matches(policy, evaluation, threshold, calibration)
                    or not _selective_policy_risk_coverage_matches(policy, evaluation, threshold, calibration)
                ):
                    issues.append(ProjectIntegrityIssue(code="SELECTIVE_POLICY_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="Selective policy does not match its exact validation cases, threshold/calibration binding, or recomputed confidence risk–coverage evidence."))
            except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="SELECTIVE_POLICY_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
        active_path = selective_root / "active-policy.json"
        missing_pointer = _require_active_pointer(selective_policies, active_path, "analyses/selective-policies/active-policy.json", "SELECTIVE_POLICY_ACTIVE_POINTER_INVALID", "selective policies")
        if missing_pointer is not None:
            checked += 1; issues.append(missing_pointer)
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["policy_id"]
                if str(active_id) not in {str(key) for key in selective_policies}:
                    raise ValueError("Active selective-policy pointer does not resolve to persisted evidence.")
                latest_policy = max(selective_policies.values(), key=lambda item: (item.created_at, str(item.policy_id)), default=None)
                if latest_policy is not None and str(latest_policy.policy_id) != str(active_id):
                    raise ValueError("Active selective-policy pointer does not identify the latest persisted policy.")
            except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="SELECTIVE_POLICY_ACTIVE_POINTER_INVALID", status="FAIL", path="analyses/selective-policies/active-policy.json", detail=str(error)))
    for run in runs:
        run_path = f"runs/{run.run_id}.json"
        try:
            adapter = resolve_run_adapter(run, registry=builtin_runtime_registry())
            if run.schema_version >= 3 and not run.runtime_capability_snapshot_hash:
                raise ValueError("A schema-v3 TrainingRun is missing its runtime capability snapshot hash.")
            if run.schema_version < 3:
                issues.append(ProjectIntegrityIssue(code="ADAPTER_IDENTITY", status="PASS", path=run_path, detail=f"Resolved legacy {run.model_kind} through deterministic read-only mapping to {adapter.descriptor.identity.key}@{adapter.descriptor.identity.version}; persisted file was not rewritten."))
            else:
                issues.append(ProjectIntegrityIssue(code="ADAPTER_IDENTITY", status="PASS", path=run_path, detail=f"Exact adapter {adapter.descriptor.identity.key}@{adapter.descriptor.identity.version} is registered and supports {run.model_kind}."))
        except Exception as error:
            legacy_unbound = run.schema_version < 3 and not any((run.adapter_key, run.adapter_version, run.adapter_provider, run.adapter_kind))
            issues.append(ProjectIntegrityIssue(code="ADAPTER_IDENTITY", status="WARN" if legacy_unbound else "FAIL", path=run_path, detail=f"Legacy run remains inspectable but has no available adapter mapping: {error}" if legacy_unbound else f"Persisted adapter identity is invalid or unavailable: {error}"))
        verification = store.verify(ArtifactRef(sha256=run.model_artifact_sha256)); checked += 1
        if not verification.valid:
            issues.append(ProjectIntegrityIssue(code="MODEL_ARTIFACT_INVALID", status="FAIL", path=f"runs/{run.run_id}.json", detail=verification.message))
        elif run.preprocessing_artifact_sha256 is not None:
            try:
                model_record = ArtifactRecord.model_validate_json((base / "objects" / "artifacts" / f"{run.model_artifact_sha256}.json").read_text(encoding="utf-8"))
                if run.preprocessing_artifact_sha256 not in model_record.parent_artifacts:
                    issues.append(ProjectIntegrityIssue(code="MODEL_PREPROCESSING_LINEAGE_MISMATCH", status="FAIL", path=f"runs/{run.run_id}.json", detail="Model artifact does not declare its frozen preprocessing artifact as an input."))
            except (FileNotFoundError, ValidationError, ValueError) as error:
                issues.append(ProjectIntegrityIssue(code="MODEL_ARTIFACT_METADATA_MALFORMED", status="FAIL", path=f"runs/{run.run_id}.json", detail=str(error)))
        if contract is not None and (run.dataset_fingerprint != contract.dataset_fingerprint or run.dataset_artifact_sha256 != contract.source_artifact_sha256):
            issues.append(ProjectIntegrityIssue(code="RUN_DATASET_MISMATCH", status="FAIL", path=f"runs/{run.run_id}.json", detail="TrainingRun dataset identity does not match the active DatasetContract."))
        if run.split.split_contract_id is not None:
            try:
                split_contract = load_split_contract(base, run.split.split_contract_id); checked += 1
                if split_contract.split_identity != run.split.split_identity or split_contract.family.lower() != run.split.family:
                    raise DatasetConfirmationError("TrainingRun split provenance differs from its immutable SplitContract.")
                if dict(split_contract.role_identity_hashes) != dict(run.split.role_identity_hashes):
                    raise DatasetConfirmationError("TrainingRun role identity hashes differ from its immutable SplitContract.")
            except (FileNotFoundError, ValidationError, ValueError, DatasetConfirmationError) as error:
                issues.append(ProjectIntegrityIssue(code="SPLIT_CONTRACT_PROVENANCE_MISMATCH", status="FAIL", path=f"runs/{run.run_id}.json", detail=str(error)))
        if run.transform_pipeline_id is not None:
            try:
                pipeline = load_transform_pipeline_contract(base, run.transform_pipeline_id); checked += 1
                if pipeline.preprocessing_artifact_sha256 != run.preprocessing_artifact_sha256 or pipeline.feature_order != run.feature_columns:
                    raise DatasetConfirmationError("TransformPipelineContract does not match TrainingRun preprocessing provenance.")
            except (FileNotFoundError, ValidationError, ValueError, DatasetConfirmationError) as error:
                issues.append(ProjectIntegrityIssue(code="TRANSFORM_PIPELINE_PROVENANCE_MISMATCH", status="FAIL", path=f"runs/{run.run_id}.json", detail=str(error)))
        if run.leakage_audit_id is not None:
            try:
                audit = load_leakage_audit(base, run.leakage_audit_id); checked += 1
                if audit.status == "FAIL" or audit.transform_pipeline_id != run.transform_pipeline_id or audit.split_contract_id != run.split.split_contract_id:
                    raise DatasetConfirmationError("LeakageAuditReport does not match TrainingRun provenance.")
            except (FileNotFoundError, ValidationError, ValueError, DatasetConfirmationError) as error:
                issues.append(ProjectIntegrityIssue(code="LEAKAGE_AUDIT_PROVENANCE_MISMATCH", status="FAIL", path=f"runs/{run.run_id}.json", detail=str(error)))
        if run.preprocessing_artifact_sha256 is not None:
            verification = store.verify(ArtifactRef(sha256=run.preprocessing_artifact_sha256)); checked += 1
            if not verification.valid:
                issues.append(ProjectIntegrityIssue(code="PREPROCESSING_ARTIFACT_INVALID", status="FAIL", path=f"runs/{run.run_id}.json", detail=verification.message))
            else:
                try:
                    with store.open(ArtifactRef(sha256=run.preprocessing_artifact_sha256)) as handle:
                        preprocessing = json.loads(handle.read().decode("utf-8"))
                    legacy = preprocessing.get("format") == "ruflex.preprocessing/v1"
                    current = preprocessing.get("format") == "ruflex.preprocessing/v2"
                    categorical = preprocessing.get("categorical_encoding", {})
                    categorical_valid = legacy or (
                        categorical.get("kind") == "ordinal"
                        and set(categorical.get("columns", [])) <= set(run.feature_columns)
                        and set(categorical.get("categories", {})) == set(categorical.get("columns", []))
                        and categorical.get("unknown_value") == -1.0
                    )
                    missing_policy_valid = preprocessing.get("missing_value_policy") == ("median" if legacy else "train_median_or_mode")
                    if not (legacy or current) or preprocessing.get("fit_scope") != "train_only" or preprocessing.get("normalization") != run.normalization or preprocessing.get("feature_columns") != run.feature_columns or not missing_policy_valid or set(preprocessing.get("imputation_values", {})) != set(run.feature_columns) or not categorical_valid:
                        issues.append(ProjectIntegrityIssue(code="PREPROCESSING_PROVENANCE_MISMATCH", status="FAIL", path=f"runs/{run.run_id}.json", detail="Persisted preprocessing artifact does not match the TrainingRun's train-only normalization and feature schema."))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                    issues.append(ProjectIntegrityIssue(code="PREPROCESSING_ARTIFACT_MALFORMED", status="FAIL", path=f"runs/{run.run_id}.json", detail=str(error)))
    study_root = base / "studies"
    studies_by_id: dict[object, TrainingStudy] = {}
    if study_root.exists() and not study_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="STUDY_EVIDENCE_MALFORMED", status="FAIL", path="studies", detail="Persisted study path is not a directory."))
    elif study_root.is_dir():
        registry = builtin_runtime_registry()
        for study_path in sorted(study_root.glob("*.json")):
            if study_path.name == "active-study.json":
                continue
            checked += 1
            relative_path = str(study_path.relative_to(base))
            try:
                study = TrainingStudy.model_validate_json(study_path.read_text(encoding="utf-8"))
                if study_path.stem != str(study.study_id):
                    raise ValueError("TrainingStudy filename does not match its persisted identity.")
                studies_by_id[study.study_id] = study
                run_ids = [item.run_id for item in study.seed_runs]
                seed_pairs = [
                    (
                        int(item.split_seed if item.split_seed is not None else item.seed),
                        int(item.training_seed if item.training_seed is not None else item.seed),
                    )
                    for item in study.seed_runs
                ]
                if len(set(run_ids)) != len(run_ids) or len(set(seed_pairs)) != len(seed_pairs):
                    issues.append(ProjectIntegrityIssue(code="STUDY_RUN_SUPPORT_INVALID", status="FAIL", path=relative_path, detail="TrainingStudy contains duplicate TrainingRun identities or duplicate split/training seed pairs."))
                if not any((study.adapter_key, study.adapter_version, study.adapter_provider)) and study.schema_version < 3:
                    legacy = LEGACY_MODEL_KIND_TO_ADAPTER.get(study.model_kind)
                    if legacy is None:
                        raise ValueError(f"Legacy study model kind {study.model_kind!r} has no adapter mapping.")
                    adapter = registry.resolve_model_adapter(legacy[0], version=legacy[1])
                    identity_note = "Resolved by deterministic read-only legacy mapping"
                elif not all((study.adapter_key, study.adapter_version, study.adapter_provider)):
                    raise ValueError("TrainingStudy runtime adapter identity is partial or missing.")
                else:
                    adapter = registry.resolve_model_adapter(study.adapter_key, version=study.adapter_version)
                    if adapter.descriptor.identity.provider != study.adapter_provider:
                        raise ValueError("TrainingStudy adapter provider does not match the registered runtime.")
                    identity_note = "Exact persisted adapter identity verified"
                if study.model_kind not in adapter.descriptor.training_model_kinds:
                    raise ValueError("TrainingStudy adapter does not support its declared model kind.")
                if study.selected_run_id not in {item.run_id for item in study.seed_runs}:
                    raise ValueError("TrainingStudy selected run is absent from its declared seed runs.")
                run_dataset_fingerprints = {item.dataset_fingerprint for item in study.seed_runs}
                actual_training_seeds = [int(item.training_seed if item.training_seed is not None else item.seed) for item in study.seed_runs]
                actual_split_seeds = [int(item.split_seed if item.split_seed is not None else item.seed) for item in study.seed_runs]
                training_seed_list_valid = study.training_seeds == actual_training_seeds or (study.schema_version < 3 and not study.training_seeds)
                randomness_valid = len(run_dataset_fingerprints) == 1 and training_seed_list_valid
                if study.randomness_protocol == "TRAINING_VARIABILITY":
                    randomness_valid = randomness_valid and study.split_seed is not None and all(seed == study.split_seed for seed in actual_split_seeds) and len({item.split.split_identity for item in study.seed_runs}) == 1
                elif study.randomness_protocol == "SPLIT_VARIABILITY":
                    randomness_valid = randomness_valid and len(set(actual_training_seeds)) == 1 and study.split_seed is None
                elif study.randomness_protocol in {"COMBINED_VARIABILITY", "LEGACY_COMBINED"}:
                    randomness_valid = randomness_valid and all(split_seed == training_seed for split_seed, training_seed in zip(actual_split_seeds, actual_training_seeds, strict=True))
                if not randomness_valid:
                    issues.append(ProjectIntegrityIssue(code="STUDY_RANDOMNESS_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="TrainingStudy seed fields or dataset identities do not match the declared variability protocol."))
                for embedded in study.seed_runs:
                    persisted_run = runs_by_id.get(embedded.run_id)
                    if persisted_run is None:
                        raise ValueError("TrainingStudy references a seed run without a canonical persisted TrainingRun.")
                    if (
                        embedded.model_artifact_sha256 != persisted_run.model_artifact_sha256
                        or embedded.dataset_fingerprint != persisted_run.dataset_fingerprint
                        or embedded.dataset_artifact_sha256 != persisted_run.dataset_artifact_sha256
                        or embedded.split.split_identity != persisted_run.split.split_identity
                        or embedded.training_seed != persisted_run.training_seed
                        or embedded.validation_metrics != persisted_run.validation_metrics
                        or embedded.prediction_preview != persisted_run.prediction_preview
                    ):
                        raise ValueError("TrainingStudy embedded run differs from its canonical persisted TrainingRun.")
                    embedded_adapter = resolve_run_adapter(embedded, registry=registry)
                    if embedded_adapter.descriptor.identity != adapter.descriptor.identity:
                        raise ValueError("TrainingStudy seed run adapter differs from the frozen study adapter.")
                selected, _, expected_rule = _select_study_run(
                    [(run, run.validation_metrics.get(study.selection_metric)) for run in study.seed_runs],
                    study.selection_metric,
                )
                if study.selection_rule != expected_rule or study.selected_run_id != selected.run_id:
                    raise ValueError("TrainingStudy selected run does not follow its persisted validation metric and deterministic tie-break rule.")
                issues.append(ProjectIntegrityIssue(code="ADAPTER_IDENTITY", status="PASS", path=relative_path, detail=f"{identity_note}: {adapter.descriptor.identity.key}@{adapter.descriptor.identity.version}; selected run and seed-run bindings agree."))
            except Exception as error:
                issues.append(ProjectIntegrityIssue(code="ADAPTER_IDENTITY", status="FAIL", path=relative_path, detail=f"TrainingStudy adapter provenance is invalid: {error}"))
        active_study_path = study_root / "active-study.json"
        missing_pointer = _require_active_pointer(studies_by_id, active_study_path, "studies/active-study.json", "STUDY_ACTIVE_POINTER_INVALID", "TrainingStudies")
        if missing_pointer is not None:
            checked += 1; issues.append(missing_pointer)
        if active_study_path.exists():
            checked += 1
            try:
                active_study_id = json.loads(active_study_path.read_text(encoding="utf-8"))["study_id"]
                if str(active_study_id) not in {str(key) for key in studies_by_id}:
                    raise ValueError("Active TrainingStudy pointer does not resolve to persisted evidence.")
                latest_study = max(studies_by_id.values(), key=lambda item: (item.created_at, str(item.study_id)), default=None)
                if latest_study is not None and str(latest_study.study_id) != str(active_study_id):
                    raise ValueError("Active TrainingStudy pointer does not identify the latest persisted study.")
            except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="STUDY_ACTIVE_POINTER_INVALID", status="FAIL", path="studies/active-study.json", detail=str(error)))
        stability_root = base / "analyses" / "stability-analyses"
        stability_analyses: dict[object, StudyStabilityAnalysis] = {}
        if stability_root.exists() and not stability_root.is_dir():
            issues.append(ProjectIntegrityIssue(code="STABILITY_ANALYSIS_EVIDENCE_MALFORMED", status="FAIL", path="analyses/stability-analyses", detail="Stability Analysis evidence path is not a directory."))
        elif stability_root.is_dir():
            for path in sorted(stability_root.glob("*.json")):
                if path.name == "active-analysis.json":
                    continue
                checked += 1
                relative_path = str(path.relative_to(base))
                try:
                    analysis = StudyStabilityAnalysis.model_validate_json(path.read_text(encoding="utf-8"))
                    if path.stem != str(analysis.analysis_id):
                        raise ValueError("Stability Analysis filename does not match its persisted identity.")
                    stability_analyses[analysis.analysis_id] = analysis
                    study = studies_by_id.get(analysis.study_id)
                    study_run_ids = set() if study is None else {run.run_id for run in study.seed_runs}
                    expected_study_run_ids = [] if study is None else [run.run_id for run in study.seed_runs]
                    threshold = thresholds.get(analysis.class_threshold_id) if analysis.class_threshold_id else None
                    if (
                        study is None
                        or not study_run_ids
                        or len(set(analysis.run_ids)) != len(analysis.run_ids)
                        or set(analysis.run_ids) != study_run_ids
                        or (analysis.schema_version >= 3 and analysis.run_ids != expected_study_run_ids)
                        or analysis.selected_run_id != study.selected_run_id
                        or analysis.model_kind != study.model_kind
                        or any(run.dataset_fingerprint != analysis.dataset_fingerprint for run in study.seed_runs)
                        or (analysis.evaluation_id is not None and (analysis.evaluation_id not in evaluations or evaluations[analysis.evaluation_id].run_id != analysis.selected_run_id))
                        or (analysis.class_threshold_id is not None and (threshold is None or threshold.evaluation_id != analysis.evaluation_id or threshold.run_id != analysis.selected_run_id or threshold.selected_threshold != analysis.decision_threshold))
                        or not _stability_analysis_cases_match(analysis, study, evaluations.get(analysis.evaluation_id) if analysis.evaluation_id else None, threshold)
                    ):
                        issues.append(ProjectIntegrityIssue(code="STABILITY_ANALYSIS_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="Stability Analysis does not resolve to its exact TrainingStudy, run set, selected Evaluation, or validation threshold."))
                except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                    issues.append(ProjectIntegrityIssue(code="STABILITY_ANALYSIS_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
            active_path = stability_root / "active-analysis.json"
            missing_pointer = _require_active_pointer(stability_analyses, active_path, "analyses/stability-analyses/active-analysis.json", "STABILITY_ANALYSIS_ACTIVE_POINTER_INVALID", "Stability Analyses")
            if missing_pointer is not None:
                checked += 1; issues.append(missing_pointer)
            if active_path.exists():
                checked += 1
                try:
                    active_id = json.loads(active_path.read_text(encoding="utf-8"))["analysis_id"]
                    if str(active_id) not in {str(key) for key in stability_analyses}:
                        raise ValueError("Active Stability Analysis pointer does not resolve to persisted evidence.")
                    latest_analysis = max(stability_analyses.values(), key=lambda item: (item.created_at, str(item.analysis_id)), default=None)
                    if latest_analysis is not None and str(latest_analysis.analysis_id) != str(active_id):
                        raise ValueError("Active Stability Analysis pointer does not identify the latest persisted analysis.")
                except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                    issues.append(ProjectIntegrityIssue(code="STABILITY_ANALYSIS_ACTIVE_POINTER_INVALID", status="FAIL", path="analyses/stability-analyses/active-analysis.json", detail=str(error)))
        stability_policy_root = base / "analyses" / "stability-policies"
        stability_policies: dict[object, StabilityGatePolicy] = {}
        if stability_policy_root.exists() and not stability_policy_root.is_dir():
            issues.append(ProjectIntegrityIssue(code="STABILITY_GATE_EVIDENCE_MALFORMED", status="FAIL", path="analyses/stability-policies", detail="Stability Gate evidence path is not a directory."))
        elif stability_policy_root.is_dir():
            for path in sorted(stability_policy_root.glob("*.json")):
                if path.name == "active-policy.json":
                    continue
                checked += 1
                relative_path = str(path.relative_to(base))
                try:
                    policy = StabilityGatePolicy.model_validate_json(path.read_text(encoding="utf-8"))
                    if path.stem != str(policy.policy_id):
                        raise ValueError("Stability Gate filename does not match its persisted identity.")
                    stability_policies[policy.policy_id] = policy
                    analysis = stability_analyses.get(policy.stability_analysis_id)
                    evaluation = evaluations.get(policy.evaluation_id)
                    threshold = thresholds.get(policy.class_threshold_id) if policy.class_threshold_id else None
                    if (
                        analysis is None
                        or evaluation is None
                        or policy.study_id != analysis.study_id
                        or policy.evaluation_id != analysis.evaluation_id
                        or policy.selected_run_id != analysis.selected_run_id
                        or set(policy.run_ids) != set(analysis.run_ids)
                        or policy.dataset_fingerprint != analysis.dataset_fingerprint
                        or policy.dataset_artifact_sha256 != analysis.dataset_artifact_sha256
                        or policy.model_kind != analysis.model_kind
                        or policy.source_split != "validation"
                        or policy.probability_source != "raw"
                        or policy.calibration_id is not None
                        or threshold is None
                        or policy.class_threshold_id != analysis.class_threshold_id
                        or policy.decision_threshold != threshold.selected_threshold
                        or evaluation.run_id != policy.selected_run_id
                        or not _stability_gate_evidence_matches(policy, analysis)
                    ):
                        issues.append(ProjectIntegrityIssue(code="STABILITY_GATE_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="Stability Gate does not match its frozen Analysis, selected validation Evaluation, raw threshold, run support, or case evidence."))
                except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                    issues.append(ProjectIntegrityIssue(code="STABILITY_GATE_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
            active_path = stability_policy_root / "active-policy.json"
            missing_pointer = _require_active_pointer(stability_policies, active_path, "analyses/stability-policies/active-policy.json", "STABILITY_GATE_ACTIVE_POINTER_INVALID", "Stability Gate policies")
            if missing_pointer is not None:
                checked += 1; issues.append(missing_pointer)
            if active_path.exists():
                checked += 1
                try:
                    active_id = json.loads(active_path.read_text(encoding="utf-8"))["policy_id"]
                    if str(active_id) not in {str(key) for key in stability_policies}:
                        raise ValueError("Active Stability Gate pointer does not resolve to persisted evidence.")
                    latest_policy = max(stability_policies.values(), key=lambda item: (item.created_at, str(item.policy_id)), default=None)
                    if latest_policy is not None and str(latest_policy.policy_id) != str(active_id):
                        raise ValueError("Active Stability Gate pointer does not identify the latest persisted policy.")
                except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                    issues.append(ProjectIntegrityIssue(code="STABILITY_GATE_ACTIVE_POINTER_INVALID", status="FAIL", path="analyses/stability-policies/active-policy.json", detail=str(error)))
        final_test_root = base / "analyses" / "final-tests"
        final_tests: dict[object, FinalTestEvaluation] = {}
        if final_test_root.exists() and not final_test_root.is_dir():
            issues.append(ProjectIntegrityIssue(code="FINAL_TEST_EVIDENCE_MALFORMED", status="FAIL", path="analyses/final-tests", detail="FinalTestEvaluation evidence path is not a directory."))
        elif final_test_root.is_dir():
            for path in sorted(final_test_root.glob("*.json")):
                if path.name == "active-final-test.json":
                    continue
                checked += 1
                relative_path = str(path.relative_to(base))
                try:
                    final_test = FinalTestEvaluation.model_validate_json(path.read_text(encoding="utf-8"))
                    if path.stem != str(final_test.final_test_id):
                        raise ValueError("FinalTestEvaluation filename does not match its persisted identity.")
                    final_tests[final_test.final_test_id] = final_test
                    evaluation = evaluations.get(final_test.evaluation_id)
                    run = runs_by_id.get(final_test.run_id)
                    threshold = thresholds.get(final_test.threshold_id) if final_test.threshold_id else None
                    calibration = calibrations.get(final_test.calibration_id) if final_test.calibration_id else None
                    selective_policy = selective_policies.get(final_test.selective_policy_id) if final_test.selective_policy_id else None
                    stability_policy = stability_policies.get(final_test.stability_gate_policy_id) if final_test.stability_gate_policy_id else None
                    stability_analysis = None if stability_policy is None else stability_analyses.get(stability_policy.stability_analysis_id)
                    stability_runs = [] if stability_policy is None else [runs_by_id[run_id] for run_id in stability_policy.run_ids if run_id in runs_by_id]
                    source_rows = [int(row.source_row) for row in final_test.prediction_rows if row.source_row is not None]
                    row_identities = [row.row_identity or row_identity(final_test.dataset_fingerprint, int(row.source_row)) for row in final_test.prediction_rows if row.source_row is not None]
                    row_identity_bindings_match = all(
                        row.source_row is not None
                        and row.row == index
                        and row.row_identity in (None, row_identity(final_test.dataset_fingerprint, int(row.source_row)))
                        for index, row in enumerate(final_test.prediction_rows)
                    )
                    expected_case_identity = _stable_identity("final-test-cases", {"dataset_fingerprint": final_test.dataset_fingerprint, "row_identities": sorted(row_identities)})
                    expected_sample_identity = _stable_identity("final-test-samples", {"dataset_fingerprint": final_test.dataset_fingerprint, "run_id": str(final_test.run_id), "source_rows": sorted(source_rows)})
                    expected_policy_identity = _stable_identity(
                        "final-test-policy",
                        {
                            "run_id": str(final_test.run_id),
                            "evaluation_id": str(final_test.evaluation_id),
                            "model_artifact": final_test.model_artifact_sha256,
                            "preprocessing": final_test.preprocessing_identity,
                            "calibration_id": None if final_test.calibration_id is None else str(final_test.calibration_id),
                            "threshold_id": None if final_test.threshold_id is None else str(final_test.threshold_id),
                            "selective_policy_id": None if final_test.selective_policy_id is None else str(final_test.selective_policy_id),
                            "stability_gate_policy_id": None if final_test.stability_gate_policy_id is None else str(final_test.stability_gate_policy_id),
                        },
                    )
                    identity_hashes_match = (
                        len(source_rows) == final_test.test_row_count
                        and len(set(source_rows)) == final_test.test_row_count
                        and len(set(row_identities)) == final_test.test_row_count
                        and row_identity_bindings_match
                        and final_test.test_sample_identity == expected_sample_identity
                        and final_test.test_case_identity == expected_case_identity
                        and final_test.policy_identity == expected_policy_identity
                    )
                    if (
                        evaluation is None
                        or run is None
                        or evaluation.run_id != final_test.run_id
                        or final_test.task != evaluation.task
                        or final_test.target != evaluation.target
                        or final_test.model_kind != evaluation.model_kind
                        or final_test.model_artifact_sha256 != evaluation.model_artifact_sha256
                        or final_test.dataset_fingerprint != evaluation.dataset_fingerprint
                        or final_test.dataset_artifact_sha256 != evaluation.dataset_artifact_sha256
                        or final_test.preprocessing_identity != evaluation.preprocessing_identity
                        or final_test.preprocessing_artifact_sha256 != evaluation.preprocessing_artifact_sha256
                        or final_test.test_row_count != len(final_test.prediction_rows)
                        or not identity_hashes_match
                        or final_test.policy_frozen_at is None
                        or final_test.dataset_test_unlock_at is None
                        or not _final_test_freeze_timestamps_match(final_test, run, evaluation, threshold, calibration, selective_policy, stability_policy, stability_analysis, stability_runs)
                        or (final_test.policy_frozen_at is not None and final_test.dataset_test_unlock_at is not None and final_test.policy_frozen_at > final_test.dataset_test_unlock_at)
                        or (run is not None and final_test.dataset_test_unlock_at is not None and run.created_at > final_test.dataset_test_unlock_at)
                        or (
                            stability_policy is not None
                            and final_test.dataset_test_unlock_at is not None
                            and any(
                                runs_by_id.get(run_id) is None
                                or runs_by_id[run_id].created_at > final_test.dataset_test_unlock_at
                                for run_id in stability_policy.run_ids
                            )
                        )
                        or (evaluation is not None and final_test.dataset_test_unlock_at is not None and evaluation.created_at > final_test.dataset_test_unlock_at)
                        or (threshold is not None and final_test.dataset_test_unlock_at is not None and threshold.created_at > final_test.dataset_test_unlock_at)
                        or (calibration is not None and final_test.dataset_test_unlock_at is not None and calibration.created_at > final_test.dataset_test_unlock_at)
                        or (selective_policy is not None and final_test.dataset_test_unlock_at is not None and selective_policy.created_at > final_test.dataset_test_unlock_at)
                        or (stability_policy is not None and final_test.dataset_test_unlock_at is not None and stability_policy.frozen_at > final_test.dataset_test_unlock_at)
                        or (final_test.threshold_id is not None and (threshold is None or threshold.evaluation_id != final_test.evaluation_id or threshold.run_id != final_test.run_id or threshold.selected_threshold != final_test.decision_threshold or threshold.probability_source != final_test.probability_source))
                        or (threshold is not None and threshold.calibration_id != final_test.calibration_id)
                        or (final_test.task == "binary_classification" and threshold is None)
                        or (final_test.task == "regression" and (threshold is not None or calibration is not None))
                        or (final_test.calibration_id is not None and (calibration is None or calibration.evaluation_id != final_test.evaluation_id or calibration.run_id != final_test.run_id))
                        or (final_test.selective_policy_id is not None and (selective_policy is None or selective_policy.evaluation_id != final_test.evaluation_id or selective_policy.run_id != final_test.run_id or selective_policy.class_threshold_id != final_test.threshold_id))
                        or (final_test.stability_gate_policy_id is not None and (stability_policy is None or stability_policy.evaluation_id != final_test.evaluation_id or stability_policy.selected_run_id != final_test.run_id or stability_policy.class_threshold_id != final_test.threshold_id))
                        or not _final_test_metrics_match(final_test, threshold, calibration)
                        or not _final_test_stability_evidence_matches(final_test, stability_policy)
                    ):
                        issues.append(ProjectIntegrityIssue(code="FINAL_TEST_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="FinalTestEvaluation does not match its frozen validation Evaluation, model, dataset, threshold, calibration, or selective/stability policy bindings."))
                except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                    issues.append(ProjectIntegrityIssue(code="FINAL_TEST_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
            unlocks_by_dataset: dict[str, list[datetime]] = {}
            for final_test in final_tests.values():
                unlock = final_test.dataset_test_unlock_at
                if unlock is None:
                    continue
                unlocks_by_dataset.setdefault(final_test.dataset_fingerprint, []).append(unlock)
                if final_test.created_at.tzinfo is None or unlock.tzinfo is None or unlock > final_test.created_at:
                    issues.append(ProjectIntegrityIssue(code="DATASET_TEST_UNLOCK_INCONSISTENT", status="FAIL", path=f"analyses/final-tests/{final_test.final_test_id}.json", detail="Dataset first-test unlock must be timezone-aware and no later than the persisted evaluation creation time."))
            for dataset_fingerprint, unlocks in unlocks_by_dataset.items():
                if len(set(unlocks)) > 1:
                    issues.append(ProjectIntegrityIssue(code="DATASET_TEST_UNLOCK_INCONSISTENT", status="FAIL", path="analyses/final-tests", detail=f"FinalTestEvaluations for dataset revision {dataset_fingerprint} do not share one immutable first-test unlock timestamp."))
            policy_identities: set[tuple[str, str]] = set()
            for final_test in final_tests.values():
                identity = (final_test.dataset_fingerprint, final_test.policy_identity)
                if identity in policy_identities:
                    issues.append(ProjectIntegrityIssue(code="FINAL_TEST_DUPLICATE_POLICY_EVIDENCE", status="FAIL", path=f"analyses/final-tests/{final_test.final_test_id}.json", detail="The same frozen final-test policy has multiple persisted result objects; the canonical executor should return the existing evaluation instead."))
                policy_identities.add(identity)
            active_path = final_test_root / "active-final-test.json"
            missing_pointer = _require_active_pointer(final_tests, active_path, "analyses/final-tests/active-final-test.json", "FINAL_TEST_ACTIVE_POINTER_INVALID", "FinalTestEvaluations")
            if missing_pointer is not None:
                checked += 1; issues.append(missing_pointer)
            if active_path.exists():
                checked += 1
                try:
                    active_id = json.loads(active_path.read_text(encoding="utf-8"))["final_test_id"]
                    if str(active_id) not in {str(key) for key in final_tests}:
                        raise ValueError("Active FinalTestEvaluation pointer does not resolve to persisted evidence.")
                    latest_created_at = max(item.created_at for item in final_tests.values())
                    latest_ids = {str(item.final_test_id) for item in final_tests.values() if item.created_at == latest_created_at}
                    if str(active_id) not in latest_ids:
                        raise ValueError("Active FinalTestEvaluation pointer does not reference the most recently persisted result.")
                except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                    issues.append(ProjectIntegrityIssue(code="FINAL_TEST_ACTIVE_POINTER_INVALID", status="FAIL", path="analyses/final-tests/active-final-test.json", detail=str(error)))
        study_jobs_root = study_root / "jobs"
        if study_jobs_root.exists() and not study_jobs_root.is_dir():
            issues.append(ProjectIntegrityIssue(code="STUDY_JOB_EVIDENCE_MALFORMED", status="FAIL", path="studies/jobs", detail="Persisted StudyJob path is not a directory."))
        elif study_jobs_root.is_dir():
            for job_path in sorted(study_jobs_root.glob("*.json")):
                checked += 1
                relative_path = str(job_path.relative_to(base))
                try:
                    job = StudyJob.model_validate_json(job_path.read_text(encoding="utf-8"))
                    if job_path.stem != str(job.job_id):
                        raise ValueError("StudyJob filename does not match its persisted identity.")
                    if not any((job.adapter_key, job.adapter_version, job.adapter_provider)) and job.schema_version < 5:
                        legacy = LEGACY_MODEL_KIND_TO_ADAPTER.get(job.model_kind)
                        if legacy is None:
                            raise ValueError(f"Legacy StudyJob model kind {job.model_kind!r} has no adapter mapping.")
                        adapter = registry.resolve_model_adapter(legacy[0], version=legacy[1])
                        identity_note = "Resolved by deterministic read-only legacy mapping"
                    elif not all((job.adapter_key, job.adapter_version, job.adapter_provider)):
                        raise ValueError("StudyJob runtime adapter identity is partial or missing.")
                    else:
                        adapter = registry.resolve_model_adapter(job.adapter_key, version=job.adapter_version)
                        if adapter.descriptor.identity.provider != job.adapter_provider:
                            raise ValueError("StudyJob adapter provider does not match the registered runtime.")
                        identity_note = "Exact persisted adapter identity verified"
                    if job.model_kind not in adapter.descriptor.training_model_kinds:
                        raise ValueError("StudyJob adapter does not support its declared model kind.")
                    completed_run_ids: set[object] = set()
                    for state in job.seed_states:
                        if state.status == "SUCCEEDED":
                            if state.run_id is None:
                                raise ValueError("A successful StudyJob seed has no TrainingRun identity.")
                            run = runs_by_id.get(state.run_id)
                            if run is None:
                                raise ValueError("A successful StudyJob seed references a missing canonical TrainingRun.")
                            run_training_seed = int(run.training_seed if run.training_seed is not None else run.seed)
                            run_split_seed = int(run.split_seed if run.split_seed is not None else run.seed)
                            expected_training_seed = int(state.training_seed if state.training_seed is not None else state.seed)
                            expected_split_seed = int(state.split_seed if state.split_seed is not None else state.seed)
                            run_adapter = resolve_run_adapter(run, registry=registry)
                            if (
                                run.model_kind != job.model_kind
                                or (job.dataset_fingerprint is not None and run.dataset_fingerprint != job.dataset_fingerprint)
                                or run_training_seed != expected_training_seed
                                or run_split_seed != expected_split_seed
                                or run_adapter.descriptor.identity != adapter.descriptor.identity
                            ):
                                raise ValueError("A successful StudyJob seed differs from its frozen run, dataset, seed, or adapter binding.")
                            completed_run_ids.add(run.run_id)
                        elif state.run_id is not None:
                            raise ValueError("A non-successful StudyJob seed must not claim a completed TrainingRun.")
                    if job.study_id is not None:
                        study = studies_by_id.get(job.study_id)
                        if study is None:
                            raise ValueError("StudyJob references a TrainingStudy that is not present.")
                        study_run_ids = {run.run_id for run in study.seed_runs}
                        if all((study.adapter_key, study.adapter_version, study.adapter_provider)):
                            study_adapter_matches = (
                                study.adapter_key == adapter.descriptor.identity.key
                                and study.adapter_version == adapter.descriptor.identity.version
                                and study.adapter_provider == adapter.descriptor.identity.provider
                            )
                        elif study.schema_version < 3 and study.seed_runs:
                            study_adapter_matches = resolve_run_adapter(study.seed_runs[0], registry=registry).descriptor.identity == adapter.descriptor.identity
                        else:
                            study_adapter_matches = False
                        if (
                            study.model_kind != job.model_kind
                            or (job.dataset_fingerprint is not None and any(run.dataset_fingerprint != job.dataset_fingerprint for run in study.seed_runs))
                            or study_run_ids != completed_run_ids
                            or not study_adapter_matches
                        ):
                            raise ValueError("StudyJob does not match its created TrainingStudy and completed seed runs.")
                    elif job.status == "SUCCEEDED":
                        raise ValueError("A successful StudyJob is missing its TrainingStudy identity.")
                    issues.append(ProjectIntegrityIssue(code="ADAPTER_IDENTITY", status="PASS", path=relative_path, detail=f"{identity_note}: {adapter.descriptor.identity.key}@{adapter.descriptor.identity.version}."))
                except Exception as error:
                    issues.append(ProjectIntegrityIssue(code="ADAPTER_IDENTITY", status="FAIL", path=relative_path, detail=f"StudyJob adapter provenance is invalid: {error}"))
    behavior_root = base / "evidence" / "behavior-specs"
    behavior_specs: dict[object, BehaviorSpec] = {}
    behavior_results: dict[object, BehaviorSpecResult] = {}
    behavior_comparison_paths: list[Path] = []
    if behavior_root.exists() and not behavior_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="BEHAVIOR_EVIDENCE_MALFORMED", status="FAIL", path="evidence/behavior-specs", detail="Behavior evidence path is not a directory."))
    elif behavior_root.is_dir():
        for path in sorted(behavior_root.glob("*.json")):
            if path.name in {"active-spec.json", "active-result.json"}:
                continue
            checked += 1
            relative_path = str(path.relative_to(base))
            try:
                if path.name.startswith("result-"):
                    result = BehaviorSpecResult.model_validate_json(path.read_text(encoding="utf-8"))
                    if path.name != f"result-{result.result_id}.json":
                        raise ValueError("BehaviorSpecResult filename does not match its persisted identity.")
                    behavior_results[result.result_id] = result
                elif path.name.startswith("comparison-"):
                    behavior_comparison_paths.append(path)
                else:
                    spec = BehaviorSpec.model_validate_json(path.read_text(encoding="utf-8"))
                    if path.name != f"{spec.spec_id}.json":
                        raise ValueError("BehaviorSpec filename does not match its persisted identity.")
                    behavior_specs[spec.spec_id] = spec
            except (OSError, ValidationError, ValueError) as error:
                issues.append(ProjectIntegrityIssue(code="BEHAVIOR_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
        for path in behavior_comparison_paths:
            relative_path = str(path.relative_to(base))
            try:
                comparison = BehaviorRevisionComparison.model_validate_json(path.read_text(encoding="utf-8"))
                if path.name != f"comparison-{comparison.comparison_id}.json":
                    raise ValueError("BehaviorRevisionComparison filename does not match its persisted identity.")
                baseline = behavior_results.get(comparison.baseline_result_id)
                candidate = behavior_results.get(comparison.candidate_result_id)
                if baseline is None or candidate is None:
                    raise ValueError("BehaviorRevisionComparison references a missing BehaviorSpecResult.")
                baseline_spec = behavior_specs.get(baseline.spec_id)
                candidate_spec = behavior_specs.get(candidate.spec_id)
                if baseline_spec is None or candidate_spec is None:
                    raise ValueError("BehaviorRevisionComparison references a missing BehaviorSpec.")
                transition = f"{baseline.status}_TO_{candidate.status}"
                if (
                    _requirement_identity(baseline_spec) != comparison.requirement_identity
                    or _requirement_identity(candidate_spec) != comparison.requirement_identity
                    or comparison.baseline_status != baseline.status
                    or comparison.candidate_status != candidate.status
                    or comparison.transition != transition
                    or comparison.regression_detected != (transition == "PASS_TO_FAIL")
                ):
                    raise ValueError("BehaviorRevisionComparison transition or requirement provenance does not match its frozen results.")
            except (OSError, ValidationError, ValueError) as error:
                issues.append(ProjectIntegrityIssue(code="BEHAVIOR_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
        for objects, pointer_name, pointer_key, identity_attribute, code, label in (
            (behavior_specs, "active-spec.json", "spec_id", "spec_id", "BEHAVIOR_SPEC_ACTIVE_POINTER_INVALID", "BehaviorSpecs"),
            (behavior_results, "active-result.json", "result_id", "result_id", "BEHAVIOR_RESULT_ACTIVE_POINTER_INVALID", "BehaviorSpecResults"),
        ):
            pointer_issue = _active_latest_pointer_issue(
                objects,
                behavior_root / pointer_name,
                f"evidence/behavior-specs/{pointer_name}",
                code,
                label,
                pointer_key,
                identity_attribute,
            )
            if pointer_issue is not None:
                checked += 1
                issues.append(pointer_issue)
            elif (behavior_root / pointer_name).exists():
                checked += 1
    explanation_root = base / "evidence" / "explanations"
    explanations: dict[object, ExplanationContract] = {}
    if explanation_root.exists() and not explanation_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="EXPLANATION_EVIDENCE_MALFORMED", status="FAIL", path="evidence/explanations", detail="Explanation evidence path is not a directory."))
    elif explanation_root.is_dir():
        for path in sorted(explanation_root.glob("*.json")):
            if path.name == "active-explanation.json":
                continue
            checked += 1
            relative_path = str(path.relative_to(base))
            try:
                explanation = ExplanationContract.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(explanation.explanation_id):
                    raise ValueError("Explanation filename does not match its persisted identity.")
                explanations[explanation.explanation_id] = explanation
                run = runs_by_id.get(explanation.run_id)
                if run is None:
                    issues.append(ProjectIntegrityIssue(code="EXPLANATION_RUN_MISSING", status="FAIL", path=relative_path, detail="Explanation references a TrainingRun that is not present."))
                    continue
                if explanation.model_artifact_sha256 != run.model_artifact_sha256:
                    issues.append(ProjectIntegrityIssue(code="EXPLANATION_MODEL_MISMATCH", status="FAIL", path=relative_path, detail="Explanation model artifact does not match its TrainingRun."))
                if explanation.preprocessing_artifact_sha256 is not None and explanation.preprocessing_artifact_sha256 != run.preprocessing_artifact_sha256:
                    issues.append(ProjectIntegrityIssue(code="EXPLANATION_PREPROCESSING_MISMATCH", status="FAIL", path=relative_path, detail="Explanation preprocessing artifact does not match its TrainingRun."))
                if list(explanation.sample) != list(run.feature_columns) or set(explanation.sample) != set(run.feature_columns):
                    issues.append(ProjectIntegrityIssue(code="EXPLANATION_SAMPLE_SCHEMA_MISMATCH", status="FAIL", path=relative_path, detail="Explanation sample feature identity/order does not match its TrainingRun."))
                if [item.feature for item in explanation.attributions] != list(run.feature_columns):
                    issues.append(ProjectIntegrityIssue(code="EXPLANATION_ATTRIBUTION_SCHEMA_MISMATCH", status="FAIL", path=relative_path, detail="Explanation attribution feature identity/order does not match its TrainingRun."))
                if explanation.target != run.target:
                    issues.append(ProjectIntegrityIssue(code="EXPLANATION_TARGET_MISMATCH", status="FAIL", path=relative_path, detail="Explanation target does not match its TrainingRun."))
                if explanation.schema_version >= 3 and not all((explanation.explainer_key, explanation.explainer_version, explanation.explainer_provider)):
                    issues.append(ProjectIntegrityIssue(code="EXPLAINER_RUNTIME_BINDING_MISSING", status="FAIL", path=relative_path, detail="A schema-v3 ExplanationContract is missing explainer runtime provenance."))
                elif explanation.schema_version >= 3:
                    try:
                        descriptor = builtin_runtime_registry().resolve_component("explainer", explanation.explainer_key, version=explanation.explainer_version)
                        if descriptor.identity.provider != explanation.explainer_provider:
                            issues.append(ProjectIntegrityIssue(code="EXPLAINER_RUNTIME_PROVIDER_MISMATCH", status="FAIL", path=relative_path, detail="Explanation runtime provider does not match the active frozen descriptor."))
                    except Exception:
                        issues.append(ProjectIntegrityIssue(code="EXPLAINER_RUNTIME_UNAVAILABLE", status="WARN", path=relative_path, detail="Persisted explainer runtime is unavailable locally; evidence remains inspectable but cannot be replayed."))
            except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="EXPLANATION_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
        active_path = explanation_root / "active-explanation.json"
        missing_pointer = _require_active_pointer(explanations, active_path, "evidence/explanations/active-explanation.json", "EXPLANATION_ACTIVE_POINTER_INVALID", "ExplanationContracts")
        if missing_pointer is not None:
            checked += 1; issues.append(missing_pointer)
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["explanation_id"]
                if str(active_id) not in {str(key) for key in explanations}:
                    raise ValueError("Active explanation pointer does not resolve to a persisted explanation.")
                latest_explanation = max(explanations.values(), key=lambda item: (item.created_at, str(item.explanation_id)), default=None)
                if latest_explanation is not None and str(latest_explanation.explanation_id) != str(active_id):
                    raise ValueError("Active explanation pointer does not identify the latest persisted ExplanationContract.")
            except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="EXPLANATION_ACTIVE_POINTER_INVALID", status="FAIL", path="evidence/explanations/active-explanation.json", detail=str(error)))
    check_root = base / "evidence" / "explanation-checks"
    checks_by_id: dict[object, ExplanationCheck] = {}
    if check_root.exists() and not check_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="EXPLANATION_CHECK_EVIDENCE_MALFORMED", status="FAIL", path="evidence/explanation-checks", detail="Explanation-check evidence path is not a directory."))
    elif check_root.is_dir():
        check_ids: set[object] = set()
        for path in sorted(check_root.glob("*.json")):
            if path.name == "active-check.json":
                continue
            checked += 1
            relative_path = str(path.relative_to(base))
            try:
                check = ExplanationCheck.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(check.check_id):
                    raise ValueError("Explanation check filename does not match its persisted identity.")
                check_ids.add(check.check_id)
                checks_by_id[check.check_id] = check
                explanation = explanations.get(check.explanation_id)
                if explanation is None:
                    issues.append(ProjectIntegrityIssue(code="EXPLANATION_CHECK_EXPLANATION_MISSING", status="FAIL", path=relative_path, detail="Explanation check references an explanation that is not present."))
                elif check.run_id != explanation.run_id:
                    issues.append(ProjectIntegrityIssue(code="EXPLANATION_CHECK_RUN_MISMATCH", status="FAIL", path=relative_path, detail="Explanation check run identity does not match its explanation."))
                expected_status = (
                    "FAILED" if any(item.status == "FAIL" for item in check.checks)
                    else "WARNING" if any(item.status == "WARN" for item in check.checks)
                    else "PASSED_AVAILABLE_CHECKS"
                )
                check_names = [item.name for item in check.checks]
                if (
                    check.status != expected_status
                    or len(check_names) != len(set(check_names))
                    or (check.validator_key is not None and any(item.validator_key != check.validator_key for item in check.checks))
                ):
                    issues.append(ProjectIntegrityIssue(code="EXPLANATION_CHECK_SUMMARY_MISMATCH", status="FAIL", path=relative_path, detail="ExplanationCheck summary status, component uniqueness, or validator binding is inconsistent with its persisted check items."))
                check_run = runs_by_id.get(check.run_id)
                if check.schema_version >= 3 and explanation is not None and check_run is not None and not _explanation_check_frozen_components_match(check, explanation, check_run):
                    issues.append(ProjectIntegrityIssue(code="EXPLANATION_CHECK_COMPONENT_MISMATCH", status="FAIL", path=relative_path, detail="Deterministic ExplanationCheck identity/completeness components do not match their persisted ExplanationContract and TrainingRun."))
                if check.schema_version >= 3 and not all((check.validator_key, check.validator_version, check.validator_provider)):
                    issues.append(ProjectIntegrityIssue(code="VALIDATOR_RUNTIME_BINDING_MISSING", status="FAIL", path=relative_path, detail="A schema-v3 ExplanationCheck is missing validator runtime provenance."))
                elif check.schema_version >= 3:
                    try:
                        descriptor = builtin_runtime_registry().resolve_component("explanation_validator", check.validator_key, version=check.validator_version)
                        if descriptor.identity.provider != check.validator_provider:
                            issues.append(ProjectIntegrityIssue(code="VALIDATOR_RUNTIME_PROVIDER_MISMATCH", status="FAIL", path=relative_path, detail="Explanation validator provider does not match the active frozen descriptor."))
                    except Exception:
                        issues.append(ProjectIntegrityIssue(code="VALIDATOR_RUNTIME_UNAVAILABLE", status="WARN", path=relative_path, detail="Persisted validator runtime is unavailable locally; evidence remains inspectable."))
            except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="EXPLANATION_CHECK_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
        active_path = check_root / "active-check.json"
        missing_pointer = _require_active_pointer(checks_by_id, active_path, "evidence/explanation-checks/active-check.json", "EXPLANATION_CHECK_ACTIVE_POINTER_INVALID", "ExplanationChecks")
        if missing_pointer is not None:
            checked += 1; issues.append(missing_pointer)
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["check_id"]
                if str(active_id) not in {str(key) for key in check_ids}:
                    raise ValueError("Active explanation-check pointer does not resolve to persisted evidence.")
                latest_check = max(checks_by_id.values(), key=lambda item: (item.created_at, str(item.check_id)), default=None)
                if latest_check is not None and str(latest_check.check_id) != str(active_id):
                    raise ValueError("Active explanation-check pointer does not identify the latest persisted check.")
            except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="EXPLANATION_CHECK_ACTIVE_POINTER_INVALID", status="FAIL", path="evidence/explanation-checks/active-check.json", detail=str(error)))
    assurance_cases: dict[object, AssuranceCase] = {}
    assurance_root = base / "evidence" / "assurance"
    if assurance_root.exists() and not assurance_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="ASSURANCE_EVIDENCE_MALFORMED", status="FAIL", path="evidence/assurance", detail="AssuranceCase evidence path is not a directory."))
    elif assurance_root.is_dir():
        for path in sorted(assurance_root.glob("*.json")):
            if path.name == "active-case.json":
                continue
            checked += 1
            try:
                case = AssuranceCase.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(case.assurance_id):
                    raise ValueError("AssuranceCase filename does not match its persisted identity.")
                assurance_cases[case.assurance_id] = case
                if case.schema_version >= 2 and not _assurance_claim_graph_matches(case):
                    issues.append(ProjectIntegrityIssue(code="ASSURANCE_CLAIM_GRAPH_MISMATCH", status="FAIL", path=str(path.relative_to(base)), detail="Persisted Assurance claims or unresolved risks do not match their declared evidence gates."))
            except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="ASSURANCE_EVIDENCE_MALFORMED", status="FAIL", path=str(path.relative_to(base)), detail=str(error)))
        active_path = assurance_root / "active-case.json"
        missing_pointer = _require_active_pointer(assurance_cases, active_path, "evidence/assurance/active-case.json", "ASSURANCE_ACTIVE_POINTER_INVALID", "AssuranceCases")
        if missing_pointer is not None:
            checked += 1; issues.append(missing_pointer)
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["assurance_id"]
                if str(active_id) not in {str(key) for key in assurance_cases}:
                    raise ValueError("Active AssuranceCase pointer does not resolve to persisted evidence.")
                latest_case = max(assurance_cases.values(), key=lambda item: (item.created_at, str(item.assurance_id)), default=None)
                if latest_case is not None and str(latest_case.assurance_id) != str(active_id):
                    raise ValueError("Active AssuranceCase pointer does not identify the latest persisted case.")
            except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="ASSURANCE_ACTIVE_POINTER_INVALID", status="FAIL", path="evidence/assurance/active-case.json", detail=str(error)))
    verification_bundles: dict[object, VerificationBundle] = {}
    bundle_root = base / "evidence" / "verification-bundles"
    if bundle_root.exists() and not bundle_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="VERIFICATION_BUNDLE_EVIDENCE_MALFORMED", status="FAIL", path="evidence/verification-bundles", detail="VerificationBundle evidence path is not a directory."))
    elif bundle_root.is_dir():
        for path in sorted(bundle_root.glob("*.json")):
            if path.name == "active-bundle.json":
                continue
            checked += 1
            try:
                bundle = VerificationBundle.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(bundle.bundle_id):
                    raise ValueError("VerificationBundle filename does not match its persisted identity.")
                archive_path = base / "exports" / f"verification-bundle-{bundle.assurance_id}.zip"
                if bundle.assurance_id not in assurance_cases or not archive_path.is_file():
                    raise ValueError("VerificationBundle does not resolve to its AssuranceCase and exported archive.")
                if hashlib.sha256(archive_path.read_bytes()).hexdigest() != bundle.sha256:
                    raise ValueError("VerificationBundle archive checksum does not match its persisted identity.")
                verification_bundles[bundle.bundle_id] = bundle
            except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="VERIFICATION_BUNDLE_EVIDENCE_MALFORMED", status="FAIL", path=str(path.relative_to(base)), detail=str(error)))
        active_path = bundle_root / "active-bundle.json"
        missing_pointer = _require_active_pointer(verification_bundles, active_path, "evidence/verification-bundles/active-bundle.json", "VERIFICATION_BUNDLE_ACTIVE_POINTER_INVALID", "VerificationBundles")
        if missing_pointer is not None:
            checked += 1; issues.append(missing_pointer)
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["bundle_id"]
                if str(active_id) not in {str(key) for key in verification_bundles}:
                    raise ValueError("Active VerificationBundle pointer does not resolve to persisted evidence.")
                latest_bundle = max(verification_bundles.values(), key=lambda item: (item.created_at, str(item.bundle_id)), default=None)
                if latest_bundle is not None and str(latest_bundle.bundle_id) != str(active_id):
                    raise ValueError("Active VerificationBundle pointer does not identify the latest persisted bundle.")
            except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="VERIFICATION_BUNDLE_ACTIVE_POINTER_INVALID", status="FAIL", path="evidence/verification-bundles/active-bundle.json", detail=str(error)))
    try:
        jobs_root = base / "jobs"
        if jobs_root.exists() and not jobs_root.is_dir():
            raise ValueError("Persisted jobs path is not a directory.")
        for path in sorted(jobs_root.glob("*.json")) if jobs_root.is_dir() else []:
            checked += 1
            relative_path = str(path.relative_to(base))
            try:
                job = Job.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(job.job_id):
                    raise ValueError("Persisted Job filename does not match its identity.")
            except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="JOB_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
                continue
            if job.schema_version >= 2:
                if not all((job.execution_backend_key, job.execution_backend_version, job.execution_backend_provider)):
                    issues.append(ProjectIntegrityIssue(code="JOB_BACKEND_RUNTIME_BINDING_MISSING", status="FAIL", path=relative_path, detail="A schema-v2 job is missing execution backend runtime provenance."))
                    continue
                try:
                    descriptor = builtin_runtime_registry().resolve_component("execution_backend", job.execution_backend_key, version=job.execution_backend_version)
                    if descriptor.identity.provider != job.execution_backend_provider:
                        issues.append(ProjectIntegrityIssue(code="JOB_BACKEND_RUNTIME_PROVIDER_MISMATCH", status="FAIL", path=relative_path, detail="Job backend provider does not match the active frozen descriptor."))
                except Exception:
                    issues.append(ProjectIntegrityIssue(code="JOB_BACKEND_RUNTIME_UNAVAILABLE", status="WARN", path=relative_path, detail="Persisted execution backend is unavailable locally; job remains inspectable."))
            if job.status.value != "succeeded" or job.kind not in {"explanation_generation", "explanation_check", "assurance_case", "verification_bundle_export"}:
                continue
            try:
                if job.kind == "explanation_generation":
                    explanation_id = UUID(job.output["explanation_id"])
                    explanation = explanations.get(explanation_id)
                    if explanation is None or explanation.run_id != UUID(job.request["run_id"]) or explanation.explainer_key != job.request["method"]:
                        raise ValueError("Completed explanation job output does not match its persisted request and ExplanationContract.")
                elif job.kind == "explanation_check":
                    check_id = UUID(job.output["check_id"])
                    check = checks_by_id.get(check_id)
                    if check is None or check.explanation_id != UUID(job.request["explanation_id"]) or check.validator_key != job.request["validator_key"]:
                        raise ValueError("Completed explanation-check job output does not match its request and ExplanationCheck.")
                elif job.kind == "assurance_case":
                    assurance_id = UUID(job.output["assurance_id"])
                    if assurance_id not in assurance_cases:
                        raise ValueError("Completed AssuranceCase job output does not resolve to persisted evidence.")
                else:
                    bundle_id = UUID(job.output["bundle_id"])
                    if bundle_id not in verification_bundles:
                        raise ValueError("Completed VerificationBundle job output does not resolve to persisted evidence.")
            except (KeyError, TypeError, ValueError) as error:
                issues.append(ProjectIntegrityIssue(code="JOB_OUTPUT_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail=str(error)))
    except (ValidationError, ValueError, FileNotFoundError) as error:
        issues.append(ProjectIntegrityIssue(code="JOB_EVIDENCE_MALFORMED", status="FAIL", path="jobs", detail=str(error)))
    auxiliary_pointer_issues, auxiliary_pointer_checks = _inspect_auxiliary_evidence_integrity(
        base,
        {run.run_id: run for run in runs},
        evaluations,
        contract,
        explanations,
    )
    issues.extend(auxiliary_pointer_issues)
    checked += auxiliary_pointer_checks
    status = "FAIL" if any(issue.status == "FAIL" for issue in issues) else "WARN" if any(issue.status == "WARN" for issue in issues) else "PASS"
    return ProjectIntegrityReport(project_id=project.id, status=status, checked_objects=checked, issues=issues)
