from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from uuid import UUID

import numpy as np

from ruflex.application.evidence import _atomic_write_text, _explanations_root, load_explanation
from ruflex.application.training import load_training_run
from ruflex.domain.evidence import ExplanationContract, ExplanationPairwiseAgreement, ExplanationReproducibilityAnalysis, FeatureExplanationVariability


class ReproducibilityError(ValueError):
    pass


def _root(project_root: Path) -> Path:
    root = Path(project_root).resolve() / "evidence" / "explanation-reproducibility"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _case_key(explanation: ExplanationContract) -> str:
    return "case:" + hashlib.sha256(json.dumps({"sample": explanation.sample, "target": explanation.target}, sort_keys=True).encode()).hexdigest()


def _rank(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="stable")
    result = np.empty(len(values), dtype=float)
    result[order] = np.arange(len(values), dtype=float)
    for value in np.unique(values):
        tied = np.flatnonzero(values == value)
        if len(tied) > 1:
            result[tied] = float(result[tied].mean())
    return result


def _spearman(left: np.ndarray, right: np.ndarray) -> float | None:
    if len(left) < 2 or np.std(left) == 0 or np.std(right) == 0:
        return None
    return float(np.corrcoef(_rank(left), _rank(right))[0, 1])


def _top_overlap(left: np.ndarray, right: np.ndarray, k: int) -> float:
    left_top = set(np.argsort(np.abs(left))[-k:].tolist())
    right_top = set(np.argsort(np.abs(right))[-k:].tolist())
    return len(left_top & right_top) / k


def list_explanations(project_root: Path) -> list[ExplanationContract]:
    items = []
    for path in _explanations_root(project_root).glob("*.json"):
        if path.name == "active-explanation.json":
            continue
        try:
            items.append(ExplanationContract.model_validate_json(path.read_text()))
        except (ValueError, OSError):
            continue
    return sorted(items, key=lambda item: item.created_at, reverse=True)


def create_explanation_reproducibility(project_root: Path, explanation_ids: list[UUID]) -> ExplanationReproducibilityAnalysis:
    if len(explanation_ids) < 4:
        raise ReproducibilityError("At least four explanation objects across at least two runs are required.")
    explanations = [load_explanation(project_root, item) for item in explanation_ids]
    by_run: dict[UUID, list[ExplanationContract]] = defaultdict(list)
    for item in explanations:
        by_run[item.run_id].append(item)
    if len(by_run) < 2:
        raise ReproducibilityError("Explanation reproducibility requires at least two independently persisted run artifacts.")
    runs = {run_id: load_training_run(project_root, run_id) for run_id in by_run}
    first = next(iter(runs.values()))
    if any(run.dataset_fingerprint != first.dataset_fingerprint or run.task != first.task or run.target != first.target for run in runs.values()):
        raise ReproducibilityError("Runs must share DatasetContract revision, task and target.")
    case_sets = {run_id: {row.source_row if row.source_row is not None else row.row for row in run.prediction_preview} for run_id, run in runs.items()}
    if any(values != next(iter(case_sets.values())) for values in case_sets.values()):
        raise ReproducibilityError("Runs do not share identical validation case identities; resampling cannot be compared as a paired reproducibility analysis.")
    first_explanation = explanations[0]
    if any(item.method != first_explanation.method or item.reference_definition != first_explanation.reference_definition for item in explanations):
        raise ReproducibilityError("Explanation methods or reference/background protocols are incompatible.")
    features = [item.feature for item in first_explanation.attributions]
    if any([item.feature for item in explanation.attributions] != features for explanation in explanations):
        raise ReproducibilityError("Explanation feature/concept semantics are incompatible.")
    expected_cases = {_case_key(item) for item in by_run[next(iter(by_run))]}
    if not expected_cases or any({_case_key(item) for item in items} != expected_cases for items in by_run.values()):
        raise ReproducibilityError("Every run must provide explanation evidence for the identical declared evaluation cases.")
    # Background numeric values must also be the same for train-reference methods, not merely textually described alike.
    for case in expected_cases:
        group = [item for items in by_run.values() for item in items if _case_key(item) == case]
        refs = [[round(attr.reference_value, 12) for attr in item.attributions] for item in group]
        if any(ref != refs[0] for ref in refs[1:]):
            raise ReproducibilityError("Explanation reference/background values differ across runs for a declared comparison case.")
    pairwise: list[ExplanationPairwiseAgreement] = []
    feature_values: dict[str, list[float]] = defaultdict(list)
    feature_signs: dict[str, list[int]] = defaultdict(list)
    all_spearman: list[float] = []
    all_sign: list[float] = []
    all_overlap: list[float] = []
    all_pred_diff: list[float] = []
    all_pred_class: list[float] = []
    for left_id, right_id in combinations(by_run, 2):
        left_cases = {_case_key(item): item for item in by_run[left_id]}
        right_cases = {_case_key(item): item for item in by_run[right_id]}
        diffs=[]; classes=[]; ranks=[]; signs=[]; overlaps=[]
        for case in sorted(expected_cases):
            left, right = left_cases[case], right_cases[case]
            lv=np.asarray([a.attribution for a in left.attributions]); rv=np.asarray([a.attribution for a in right.attributions])
            diffs.append(abs(left.prediction-right.prediction))
            if first.task == "binary_classification": classes.append(float((left.prediction >= .5) == (right.prediction >= .5)))
            rank=_spearman(lv, rv)
            if rank is not None: ranks.append(rank)
            signs.append(float(np.mean(np.sign(lv) == np.sign(rv))))
            overlaps.append(_top_overlap(lv, rv, min(3, len(features))))
            for feature, value, other in zip(features, lv, rv, strict=True):
                feature_values[feature].extend([float(value), float(other)]); feature_signs[feature].extend([int(np.sign(value)), int(np.sign(other))])
        pairwise.append(ExplanationPairwiseAgreement(left_run_id=left_id,right_run_id=right_id,prediction_mean_absolute_difference=float(np.mean(diffs)),prediction_class_agreement=None if not classes else float(np.mean(classes)),explanation_spearman=None if not ranks else float(np.mean(ranks)),explanation_sign_agreement=float(np.mean(signs)),top_k_overlap=float(np.mean(overlaps)),case_count=len(expected_cases)))
        all_pred_diff.extend(diffs); all_pred_class.extend(classes); all_spearman.extend(ranks); all_sign.extend(signs); all_overlap.extend(overlaps)
    variability=[]
    for feature in features:
        values=np.asarray(feature_values[feature]); signs=feature_signs[feature]
        variability.append(FeatureExplanationVariability(feature=feature,mean_attribution=float(values.mean()),standard_deviation=float(values.std()),sign_agreement=float(max(signs.count(-1), signs.count(0), signs.count(1))/len(signs))))
    explanation_agreement={"mean_sign_agreement":float(np.mean(all_sign)),"mean_top_k_overlap":float(np.mean(all_overlap))}
    warnings=["Prediction agreement is reported separately and must not be interpreted as explanation stability."]
    if all_spearman:
        explanation_agreement["mean_spearman"] = float(np.mean(all_spearman))
    else:
        warnings.append("Rank correlation is unavailable because at least one comparison has a constant attribution vector.")
    prediction_agreement={"mean_absolute_difference":float(np.mean(all_pred_diff))}
    if first.task == "binary_classification": prediction_agreement["class_agreement"] = float(np.mean(all_pred_class))
    else: warnings.append("Regression prediction reproducibility is reported as continuous prediction difference; class agreement is not applicable.")
    result=ExplanationReproducibilityAnalysis(run_ids=list(by_run),explanation_ids=explanation_ids,task=first.task,target=first.target,dataset_fingerprint=str(first.dataset_fingerprint),validation_case_identities=[str(value) for value in sorted(next(iter(case_sets.values())))],explanation_method=first_explanation.method,reference_protocol=first_explanation.reference_definition,prediction_agreement=prediction_agreement,explanation_agreement=explanation_agreement,pairwise=pairwise,per_feature_variability=variability,warnings=warnings)
    _atomic_write_text(_root(project_root) / f"{result.analysis_id}.json", result.model_dump_json(indent=2))
    _atomic_write_text(_root(project_root) / "active-analysis.json", json.dumps({"analysis_id": str(result.analysis_id)}))
    return result


def load_latest_explanation_reproducibility(project_root: Path) -> ExplanationReproducibilityAnalysis:
    pointer=json.loads((_root(project_root) / "active-analysis.json").read_text())
    return ExplanationReproducibilityAnalysis.model_validate_json((_root(project_root) / f"{pointer['analysis_id']}.json").read_text())
