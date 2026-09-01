from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

import numpy as np

from ruflex.application.evidence import predict_run_sample
from ruflex.application.generalization import ScopeDisposition, classify_scope, load_generalization_contract
from ruflex.application.training import TrainingError, _atomic_write_text, load_decision_threshold, load_validation_calibration, load_validation_evaluation
from ruflex.domain.selective import RiskCoveragePoint, SelectiveDecision, SelectivePredictionPolicy


def _root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "analyses" / "selective-policies"
    root.mkdir(parents=True, exist_ok=True)
    return root


def create_selective_policy(project_root: Path, evaluation_id: UUID, confidence_cutoff: float, calibration_id: UUID | None = None, threshold_id: UUID | None = None) -> SelectivePredictionPolicy:
    """Freeze ACCEPT/REVIEW on the same validation cases as a class policy."""
    if any((Path(project_root).resolve() / "analyses" / "final-tests").glob("*.json")):
        raise TrainingError("Final-test evidence already exists; a selective-review policy cannot be tuned after final-test access.")
    evaluation = load_validation_evaluation(project_root, evaluation_id)
    if evaluation.task != "binary_classification":
        raise TrainingError("Selective prediction is available only for binary probabilistic classification.")
    if threshold_id is None:
        raise TrainingError("Selective prediction requires the exact validation-derived class DecisionThreshold policy.")
    threshold = load_decision_threshold(project_root, threshold_id)
    if threshold.evaluation_id != evaluation_id or threshold.run_id != evaluation.run_id:
        raise TrainingError("DecisionThreshold does not belong to the selected validation evaluation.")
    if threshold.calibration_id != calibration_id:
        raise TrainingError("Selective policy must use the exact calibration provenance bound to its DecisionThreshold.")
    rows = evaluation.prediction_preview
    if not rows:
        raise TrainingError("Validation evaluation contains no prediction evidence.")
    if calibration_id:
        calibration = load_validation_calibration(project_root, calibration_id)
        if calibration.evaluation_id != evaluation_id or calibration.run_id != evaluation.run_id:
            raise TrainingError("Calibration does not belong to the selected validation evaluation.")
        by_row = {item.row: item.calibrated_probability for item in calibration.predictions}
        if any(row.row not in by_row for row in rows):
            raise TrainingError("Calibration transform does not cover every validation case.")
        probabilities = np.asarray([by_row[row.row] for row in rows], dtype=float)
        source = "calibrated"
    else:
        probabilities = np.asarray([row.probability if row.probability is not None else 1 / (1 + np.exp(-row.prediction)) for row in rows], dtype=float)
        source = "raw"
    targets = np.asarray([int(row.target >= 0.5) for row in rows], dtype=int)
    labels = (probabilities >= threshold.selected_threshold).astype(int)
    confidences = np.maximum(probabilities, 1 - probabilities)
    points = []
    for cutoff in np.round(np.arange(0.5, 1.0, 0.05), 2):
        accepted = confidences >= cutoff
        count = int(accepted.sum())
        risk = None if count == 0 else float(np.mean(labels[accepted] != targets[accepted]))
        points.append(RiskCoveragePoint(confidence_cutoff=float(cutoff), coverage=float(count / len(rows)), accepted_risk=risk, accepted_count=count))
    cases = [{"validation_row": int(row.row), "source_row": row.source_row, "target": int(target), "probability": float(probability)} for row, target, probability in zip(rows, targets, probabilities, strict=True)]
    identity = hashlib.sha256(json.dumps({"dataset": evaluation.dataset_fingerprint, "evaluation": str(evaluation_id), "threshold": str(threshold_id), "calibration": None if calibration_id is None else str(calibration_id), "cases": cases}, sort_keys=True).encode()).hexdigest()
    policy = SelectivePredictionPolicy(evaluation_id=evaluation_id, run_id=evaluation.run_id, calibration_id=calibration_id, class_threshold_id=threshold.threshold_id, class_threshold=threshold.selected_threshold, confidence_cutoff=confidence_cutoff, probability_source=source, fit_sample_identity=identity, risk_coverage=points)
    _atomic_write_text(_root(project_root) / f"{policy.policy_id}.json", policy.model_dump_json(indent=2))
    _atomic_write_text(_root(project_root) / "active-policy.json", json.dumps({"policy_id": str(policy.policy_id)}))
    return policy


def load_selective_policy(project_root: Path, policy_id: UUID) -> SelectivePredictionPolicy:
    return SelectivePredictionPolicy.model_validate_json((_root(project_root) / f"{policy_id}.json").read_text())


def apply_selective_policy(project_root: Path, policy_id: UUID, sample: dict[str, float], *, metadata: dict[str, object] | None = None, generalization_contract_id: UUID | None = None) -> SelectiveDecision:
    policy = load_selective_policy(project_root, policy_id)
    raw = predict_run_sample(project_root, policy.run_id, sample)
    probability = float(1 / (1 + np.exp(-np.clip(raw, -60.0, 60.0))))
    if policy.calibration_id is not None:
        calibration = load_validation_calibration(project_root, policy.calibration_id)
        probability = float(1 / (1 + np.exp(-np.clip(calibration.coefficient * raw + calibration.intercept, -60.0, 60.0))))
    label, confidence = int(probability >= policy.class_threshold), max(probability, 1 - probability)
    if generalization_contract_id is not None:
        scope = classify_scope(load_generalization_contract(project_root, generalization_contract_id), metadata or {})
        if scope.disposition == ScopeDisposition.BLOCK:
            return SelectiveDecision(policy_id=policy.policy_id, run_id=policy.run_id, probability=probability, predicted_label=label, confidence=confidence, disposition="OUT_OF_SCOPE", scope_disposition="BLOCK", reasons=scope.reasons)
        if scope.disposition == ScopeDisposition.REVIEW:
            return SelectiveDecision(policy_id=policy.policy_id, run_id=policy.run_id, probability=probability, predicted_label=label, confidence=confidence, disposition="REVIEW", scope_disposition="REVIEW", reasons=scope.reasons + ["Scope review takes precedence over confidence acceptance."])
        scope_disposition, reasons = "ALLOW", scope.reasons
    else:
        scope_disposition, reasons = "NOT_EVALUATED", []
    disposition = "ACCEPT" if confidence >= policy.confidence_cutoff else "REVIEW"
    if disposition == "REVIEW": reasons.append("Confidence is below the frozen selective-review cutoff.")
    return SelectiveDecision(policy_id=policy.policy_id, run_id=policy.run_id, probability=probability, predicted_label=label, confidence=confidence, disposition=disposition, scope_disposition=scope_disposition, reasons=reasons)


def load_latest_selective_policy(project_root: Path) -> SelectivePredictionPolicy:
    pointer = json.loads((_root(project_root) / "active-policy.json").read_text())
    return load_selective_policy(project_root, UUID(pointer["policy_id"]))
