from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from uuid import UUID

import numpy as np

from ruflex.application.training import TrainingError, _atomic_write_text, load_training_study, load_validation_evaluation
from ruflex.domain.stability import CaseStability, MetricDistribution, RiskCoverageComparison, StabilityGateApplication, StabilityGateDecision, StabilityGatePolicy, StudyStabilityAnalysis


def _root(project_root: Path, name: str) -> Path:
    result = Path(project_root).resolve() / "analyses" / name
    result.mkdir(parents=True, exist_ok=True)
    return result


def _identity(prefix: str, payload: object) -> str:
    packed = json.dumps({"prefix": prefix, "payload": payload}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()


def _probability(row) -> float:
    if row.probability is not None:
        return float(row.probability)
    return float(1.0 / (1.0 + math.exp(-max(min(float(row.prediction), 60.0), -60.0))))


def _case_key(row) -> str:
    return f"source:{row.source_row}" if row.source_row is not None else f"row:{row.row}"


def _metric_distribution(values: list[float]) -> MetricDistribution:
    array = np.asarray(values, dtype=float)
    return MetricDistribution(mean=float(array.mean()), std=float(array.std(ddof=0)), minimum=float(array.min()), maximum=float(array.max()), median=float(np.median(array)), iqr=float(np.percentile(array, 75) - np.percentile(array, 25)))


def create_study_stability_analysis(project_root: Path, study_id: UUID, *, high_confidence_threshold: float = 0.9, unstable_agreement_threshold: float = 0.8) -> StudyStabilityAnalysis:
    study = load_training_study(project_root, study_id)
    if study.task != "binary_classification":
        raise TrainingError("Study Stability Analysis currently requires binary probabilistic classification.")
    if len(study.seed_runs) < 3:
        raise TrainingError("Stability analysis requires at least three independently trained runs.")
    split_ids = {run.split.split_identity for run in study.seed_runs}
    dataset_ids = {run.dataset_fingerprint for run in study.seed_runs}
    if len(split_ids) != 1 or None in split_ids:
        raise TrainingError("Study Stability Analysis requires identical persisted validation split identity across runs. Use TRAINING_VARIABILITY.")
    if len(dataset_ids) != 1:
        raise TrainingError("Study runs refer to different dataset revisions and cannot be compared.")
    by_run = {str(run.run_id): {_case_key(row): row for row in run.prediction_preview} for run in study.seed_runs}
    case_sets = {tuple(sorted(rows)) for rows in by_run.values()}
    if len(case_sets) != 1:
        raise TrainingError("Study runs do not have identical validation cases; prediction stability is not comparable.")
    selected = next((run for run in study.seed_runs if run.run_id == study.selected_run_id), None)
    if selected is None:
        raise TrainingError("TrainingStudy selected_run_id does not reference one of its seed runs.")
    cases: list[CaseStability] = []
    for key in sorted(next(iter(by_run.values()))):
        rows = {run_id: mapping[key] for run_id, mapping in by_run.items()}
        probabilities = {run_id: _probability(row) for run_id, row in rows.items()}
        labels = {run_id: int(value >= 0.5) for run_id, value in probabilities.items()}
        values = np.asarray(list(probabilities.values()), dtype=float)
        positive_fraction = float(np.mean(list(labels.values())))
        agreement = float(max(positive_fraction, 1.0 - positive_fraction))
        entropy = 0.0 if positive_fraction in {0.0, 1.0} else float(-(positive_fraction * math.log2(positive_fraction) + (1.0 - positive_fraction) * math.log2(1.0 - positive_fraction)))
        selected_row = rows[str(selected.run_id)]
        cases.append(CaseStability(case_id=key, source_row=selected_row.source_row, target=int(selected_row.target >= .5), selected_run_probability=probabilities[str(selected.run_id)], selected_run_class=labels[str(selected.run_id)], mean_probability=float(values.mean()), std_probability=float(values.std(ddof=0)), min_probability=float(values.min()), max_probability=float(values.max()), probability_range=float(values.max() - values.min()), predicted_class_agreement=agreement, positive_vote_fraction=positive_fraction, vote_entropy=entropy, run_probabilities=probabilities, run_labels=labels))
    metrics = {metric: _metric_distribution([float(run.validation_metrics[metric]) for run in study.seed_runs]) for metric in ("accuracy", "f1", "roc_auc", "pr_auc", "brier", "ece") if all(metric in run.validation_metrics for run in study.seed_runs)}
    high = [case for case in cases if max(case.selected_run_probability, 1.0 - case.selected_run_probability) >= high_confidence_threshold]
    unstable = [case for case in high if case.predicted_class_agreement < unstable_agreement_threshold]
    analysis = StudyStabilityAnalysis(study_id=study.study_id, dataset_fingerprint=selected.dataset_fingerprint, split_identity=next(iter(split_ids)), model_kind=study.model_kind, task="binary_classification", run_ids=[run.run_id for run in study.seed_runs], training_seeds=[int(run.training_seed or run.seed) for run in study.seed_runs], split_seed=int(selected.split.split_seed or selected.split.seed), evaluation_case_identity=_identity("validation-cases", sorted(by_run[str(selected.run_id)])), selected_run_id=selected.run_id, case_count=len(cases), metric_distributions=metrics, cases=cases, high_confidence_threshold=high_confidence_threshold, unstable_agreement_threshold=unstable_agreement_threshold, high_confidence_case_count=len(high), high_confidence_unstable_case_count=len(unstable), high_confidence_instability_rate=(len(unstable) / len(high) if high else 0.0))
    _atomic_write_text(_root(project_root, "stability-analyses") / f"{analysis.analysis_id}.json", analysis.model_dump_json(indent=2))
    _atomic_write_text(_root(project_root, "stability-analyses") / "active-analysis.json", json.dumps({"analysis_id": str(analysis.analysis_id)}, sort_keys=True))
    return analysis


def load_study_stability_analysis(project_root: Path, analysis_id: UUID) -> StudyStabilityAnalysis:
    return StudyStabilityAnalysis.model_validate_json((_root(project_root, "stability-analyses") / f"{analysis_id}.json").read_text())


def list_study_stability_analyses(project_root: Path) -> list[StudyStabilityAnalysis]:
    records = []
    for path in _root(project_root, "stability-analyses").glob("*.json"):
        try:
            records.append(StudyStabilityAnalysis.model_validate_json(path.read_text()))
        except (ValueError, OSError):
            continue
    return sorted(records, key=lambda item: item.created_at)


def _risk(cases: list[CaseStability], accepted: list[CaseStability]) -> float | None:
    if not accepted:
        return None
    return float(np.mean([case.selected_run_class != case.target for case in accepted]))


def create_stability_gate_policy(project_root: Path, analysis_id: UUID, evaluation_id: UUID, *, min_confidence: float, min_class_agreement: float, max_probability_std: float, calibration_id: UUID | None = None) -> StabilityGatePolicy:
    if any((_root(project_root, "final-tests")).glob("*.json")):
        raise TrainingError("Final-test evidence already exists; a Stability Gate cannot be fitted after final-test access.")
    analysis = load_study_stability_analysis(project_root, analysis_id)
    evaluation = load_validation_evaluation(project_root, evaluation_id)
    if evaluation.run_id != analysis.selected_run_id:
        raise TrainingError("Stability Gate requires validation evidence for the selected TrainingStudy run.")
    if evaluation.task != "binary_classification":
        raise TrainingError("Stability Gate is available only for binary probabilistic classification.")
    evaluation_cases = {_case_key(row) for row in evaluation.prediction_preview}
    if evaluation_cases != {case.case_id for case in analysis.cases}:
        raise TrainingError("Validation Evaluation cases do not match the frozen StudyStabilityAnalysis case identity.")
    decisions: list[StabilityGateDecision] = []
    accepted: list[CaseStability] = []
    for case in analysis.cases:
        confidence = max(case.selected_run_probability, 1.0 - case.selected_run_probability)
        reasons: list[str] = []
        if confidence < min_confidence: reasons.append("LOW_CONFIDENCE")
        if case.predicted_class_agreement < min_class_agreement: reasons.append("RUN_DISAGREEMENT")
        if case.std_probability > max_probability_std: reasons.append("HIGH_DISPERSION")
        if not reasons: accepted.append(case)
        decisions.append(StabilityGateDecision(case_id=case.case_id, disposition="ACCEPT" if not reasons else "REVIEW", reasons=reasons, selected_run_probability=case.selected_run_probability, confidence=confidence, class_agreement=case.predicted_class_agreement, probability_std=case.std_probability))
    coverage = len(accepted) / len(analysis.cases)
    ranked = sorted(analysis.cases, key=lambda case: max(case.selected_run_probability, 1 - case.selected_run_probability), reverse=True)
    confidence_only = ranked[:len(accepted)]
    all_cases = list(analysis.cases)
    comparison = [RiskCoverageComparison(policy="NO_REVIEW", coverage=1.0, accepted_count=len(all_cases), accepted_risk=_risk(all_cases, all_cases)), RiskCoverageComparison(policy="RANDOM_REVIEW", coverage=coverage, accepted_count=len(accepted), accepted_risk=_risk(all_cases, all_cases)), RiskCoverageComparison(policy="CONFIDENCE_ONLY", coverage=coverage, accepted_count=len(confidence_only), accepted_risk=_risk(all_cases, confidence_only)), RiskCoverageComparison(policy="STABILITY_AWARE", coverage=coverage, accepted_count=len(accepted), accepted_risk=_risk(all_cases, accepted))]
    policy = StabilityGatePolicy(study_id=analysis.study_id, stability_analysis_id=analysis.analysis_id, selected_run_id=analysis.selected_run_id, evaluation_id=evaluation.evaluation_id, calibration_id=calibration_id, fit_sample_identity=analysis.evaluation_case_identity, min_confidence=min_confidence, min_class_agreement=min_class_agreement, max_probability_std=max_probability_std, decisions=decisions, risk_coverage=comparison)
    _atomic_write_text(_root(project_root, "stability-policies") / f"{policy.policy_id}.json", policy.model_dump_json(indent=2))
    _atomic_write_text(_root(project_root, "stability-policies") / "active-policy.json", json.dumps({"policy_id": str(policy.policy_id)}, sort_keys=True))
    return policy


def load_stability_gate_policy(project_root: Path, policy_id: UUID) -> StabilityGatePolicy:
    return StabilityGatePolicy.model_validate_json((_root(project_root, "stability-policies") / f"{policy_id}.json").read_text())


def list_stability_gate_policies(project_root: Path) -> list[StabilityGatePolicy]:
    result = []
    for path in _root(project_root, "stability-policies").glob("*.json"):
        try: result.append(StabilityGatePolicy.model_validate_json(path.read_text()))
        except (ValueError, OSError): continue
    return sorted(result, key=lambda item: item.created_at)


def apply_stability_gate_policy(project_root: Path, policy_id: UUID, sample: dict[str, float], *, metadata: dict[str, object] | None = None, generalization_contract_id: UUID | None = None) -> StabilityGateApplication:
    """Apply a frozen prediction-stability gate without fitting any parameter.

    Every run stored in the bound StudyStabilityAnalysis evaluates the same
    supplied sample. Explanation evidence is deliberately absent from this
    operational path.
    """
    from ruflex.application.evidence import predict_run_sample
    from ruflex.application.generalization import ScopeDisposition, classify_scope, load_generalization_contract
    policy = load_stability_gate_policy(project_root, policy_id)
    analysis = load_study_stability_analysis(project_root, policy.stability_analysis_id)
    probabilities = {str(run_id): float(1.0 / (1.0 + math.exp(-max(min(predict_run_sample(project_root, run_id, sample), 60.0), -60.0)))) for run_id in analysis.run_ids}
    selected_probability = probabilities[str(policy.selected_run_id)]
    labels = [int(value >= .5) for value in probabilities.values()]
    positive_fraction = float(np.mean(labels)); agreement = float(max(positive_fraction, 1.0 - positive_fraction)); dispersion = float(np.std(list(probabilities.values()), ddof=0)); confidence = max(selected_probability, 1.0 - selected_probability)
    reasons: list[str] = []
    disposition = "ACCEPT"
    if generalization_contract_id is not None:
        scope = classify_scope(load_generalization_contract(project_root, generalization_contract_id), metadata or {})
        if scope.disposition == ScopeDisposition.BLOCK:
            disposition = "BLOCK"; reasons.append("OUT_OF_SCOPE")
    if disposition != "BLOCK":
        if confidence < policy.min_confidence: reasons.append("LOW_CONFIDENCE")
        if agreement < policy.min_class_agreement: reasons.append("RUN_DISAGREEMENT")
        if dispersion > policy.max_probability_std: reasons.append("HIGH_DISPERSION")
        if reasons: disposition = "REVIEW"
    return StabilityGateApplication(policy_id=policy.policy_id, selected_run_id=policy.selected_run_id, disposition=disposition, reasons=reasons, selected_run_probability=selected_probability, predicted_label=int(selected_probability >= .5), confidence=confidence, class_agreement=agreement, probability_std=dispersion, run_probabilities=probabilities)
