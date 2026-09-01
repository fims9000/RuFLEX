from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ValidationError

from ruflex.application.datasets import load_dataset_contract
from ruflex.application.evidence import _atomic_write_text
from ruflex.application.generalization import GeneralizationContract, SliceAnalysis
from ruflex.domain.assurance import AssuranceCase, AssuranceGate
from ruflex.domain.behavior import BehaviorSpec, BehaviorSpecResult
from ruflex.domain.evidence import ExplanationCheck, ExplanationContract, ExplanationReproducibilityAnalysis
from ruflex.domain.exhaustive import ExhaustiveLabResult
from ruflex.domain.selective import SelectivePredictionPolicy
from ruflex.domain.training import AnalysisEvaluation, CalibrationTransform, DecisionThresholdPolicy, FinalTestEvaluation, TrainingRun, TrainingStudy

ModelT = TypeVar("ModelT", bound=BaseModel)


def _root(root: Path) -> Path:
    path = Path(root).resolve() / "evidence" / "assurance"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _objects(root: Path, model: type[ModelT]) -> list[ModelT]:
    if not root.is_dir():
        return []
    items: list[ModelT] = []
    for path in root.glob("*.json"):
        try:
            UUID(path.stem)
            items.append(model.model_validate_json(path.read_text(encoding="utf-8")))
        except (ValueError, ValidationError, OSError):
            continue
    return items


def _has_malformed_object(root: Path, model: type[ModelT]) -> bool:
    """A UUID-named record that cannot validate is evidence of a failed gate.

    This deliberately differs from lineage loading: lineage may omit a broken
    historical record so a project remains inspectable, whereas Assurance must
    never turn a corrupt evidence directory into a green claim.
    """
    if not root.is_dir():
        return False
    for path in root.glob("*.json"):
        try:
            UUID(path.stem)
        except ValueError:
            continue
        try:
            model.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError):
            return True
    return False


def _gate(key: str, status: str, evidence: list[str], risk: str | None = None) -> AssuranceGate:
    return AssuranceGate(key=key, status=status, evidence=evidence, risk=risk)


def _evidence_status(*, present: bool, valid: bool, malformed: bool, unavailable: str, invalid: str) -> tuple[str, str | None]:
    if malformed:
        return "FAIL", "Malformed persisted evidence prevents a PASS claim."
    if not present:
        return "NOT_AVAILABLE", unavailable
    if not valid:
        return "FAIL", invalid
    return "PASS", None


def create_assurance_case(root: Path) -> AssuranceCase:
    base = Path(root).resolve()
    gates: list[AssuranceGate] = []
    try:
        contract = load_dataset_contract(base)
        gates.append(_gate("dataset_contract", "PASS", [f"dataset:{contract.dataset_fingerprint}"]))
    except (ValueError, OSError, ValidationError) as error:
        gates.append(_gate("dataset_contract", "FAIL", [], f"DatasetContract is missing or malformed: {error}"))
    runs_root = base / "runs"; runs = _objects(runs_root, TrainingRun)
    status, risk = _evidence_status(present=bool(runs), valid=bool(runs), malformed=_has_malformed_object(runs_root, TrainingRun), unavailable="No valid TrainingRun provenance exists.", invalid="Training provenance is invalid.")
    gates.append(_gate("training_provenance", status, [f"run:{x.run_id}" for x in runs], risk))
    studies_root = base / "studies"; studies = _objects(studies_root, TrainingStudy)
    status, risk = _evidence_status(present=bool(studies), valid=any(len(x.seed_runs) >= 3 for x in studies), malformed=_has_malformed_object(studies_root, TrainingStudy), unavailable="No valid multi-seed study exists.", invalid="No study contains sufficient seed-run evidence.")
    gates.append(_gate("multi_seed_evidence", status, [f"study:{x.study_id}" for x in studies], risk))
    evaluations_root = base / "analyses" / "evaluations"; evaluations = _objects(evaluations_root, AnalysisEvaluation)
    evaluation_ids = {x.evaluation_id for x in evaluations}
    valid_evaluations = evaluations and all(x.split == "validation" and x.test_status == "LOCKED_NOT_EVALUATED" for x in evaluations)
    status, risk = _evidence_status(present=bool(evaluations), valid=bool(valid_evaluations), malformed=_has_malformed_object(evaluations_root, AnalysisEvaluation), unavailable="Validation evidence is absent.", invalid="Validation evidence is not a locked validation evaluation.")
    gates.append(_gate("validation_evidence", status, [f"evaluation:{x.evaluation_id}" for x in evaluations], risk))
    calibrations_root = base / "analyses" / "calibrations"; calibrations = _objects(calibrations_root, CalibrationTransform)
    calibration_ok = calibrations and all(x.evaluation_id in evaluation_ids and x.source_split == "validation" for x in calibrations)
    status, risk = _evidence_status(present=bool(calibrations), valid=bool(calibration_ok), malformed=_has_malformed_object(calibrations_root, CalibrationTransform), unavailable="Calibration is absent.", invalid="Calibration is incompatible with validation evidence.")
    gates.append(_gate("calibration", status, [f"calibration:{x.calibration_id}" for x in calibrations], risk))
    thresholds_root = base / "analyses" / "thresholds"; thresholds = _objects(thresholds_root, DecisionThresholdPolicy)
    threshold_ok = thresholds and all(x.evaluation_id in evaluation_ids and x.source_split == "validation" for x in thresholds)
    status, risk = _evidence_status(present=bool(thresholds), valid=bool(threshold_ok), malformed=_has_malformed_object(thresholds_root, DecisionThresholdPolicy), unavailable="Class threshold is absent.", invalid="Class threshold is incompatible with validation evidence.")
    gates.append(_gate("class_threshold", status, [f"threshold:{x.threshold_id}" for x in thresholds], risk))
    policies_root = base / "analyses" / "selective-policies"; policies = _objects(policies_root, SelectivePredictionPolicy)
    policy_ok = policies and all(x.evaluation_id in evaluation_ids and x.source_split == "validation" for x in policies)
    status, risk = _evidence_status(present=bool(policies), valid=bool(policy_ok), malformed=_has_malformed_object(policies_root, SelectivePredictionPolicy), unavailable="Selective policy is absent.", invalid="Selective policy is incompatible with validation evidence.")
    gates.append(_gate("selective_policy", status, [f"selective-policy:{x.policy_id}" for x in policies], risk))
    contracts_root = base / "objects" / "protocols" / "generalization"; contracts = _objects(contracts_root, GeneralizationContract)
    frozen = [x for x in contracts if x.frozen_at is not None]
    if _has_malformed_object(contracts_root, GeneralizationContract):
        gates.append(_gate("generalization_contract", "FAIL", [], "Malformed GeneralizationContract prevents a PASS claim."))
    else:
        gates.append(_gate("generalization_contract", "PASS" if frozen else ("NOT_AVAILABLE" if not contracts else "WARN"), [f"generalization:{x.contract_id}" for x in frozen], None if frozen else "No frozen GeneralizationContract exists."))
    slices_root = base / "analyses" / "slices"; slices = _objects(slices_root, SliceAnalysis)
    slice_ok = slices and all(x.evaluation_id in evaluation_ids for x in slices)
    status, risk = _evidence_status(present=bool(slices), valid=bool(slice_ok), malformed=_has_malformed_object(slices_root, SliceAnalysis), unavailable="Slice evidence is absent.", invalid="Slice evidence is not linked to validation evidence.")
    gates.append(_gate("slice_evidence", status, [f"slice:{x.analysis_id}" for x in slices], risk))
    explanations_root = base / "evidence" / "explanations"; explanations = _objects(explanations_root, ExplanationContract)
    checks_root = base / "evidence" / "explanation-checks"; checks = _objects(checks_root, ExplanationCheck)
    check_by_explanation = {x.explanation_id: x for x in checks}
    if _has_malformed_object(explanations_root, ExplanationContract) or _has_malformed_object(checks_root, ExplanationCheck):
        gates.append(_gate("explanation_checks", "FAIL", [], "Malformed explanation or check evidence prevents a PASS claim."))
    elif not explanations:
        gates.append(_gate("explanation_checks", "NOT_AVAILABLE", [], "No valid ExplanationContract exists."))
    elif any(x.explanation_id not in check_by_explanation for x in explanations):
        gates.append(_gate("explanation_checks", "WARN", [f"explanation:{x.explanation_id}" for x in explanations], "One or more explanations have no persisted check."))
    elif any(check_by_explanation[x.explanation_id].status == "FAILED" for x in explanations):
        gates.append(_gate("explanation_checks", "FAIL", [f"check:{check_by_explanation[x.explanation_id].check_id}" for x in explanations], "A persisted ExplanationCheck failed."))
    else:
        gates.append(_gate("explanation_checks", "PASS", [f"check:{check_by_explanation[x.explanation_id].check_id}" for x in explanations]))
    reproducibility_root = base / "evidence" / "explanation-reproducibility"; reproducibility = _objects(reproducibility_root, ExplanationReproducibilityAnalysis)
    repro_ok = reproducibility and all(len(x.run_ids) >= 2 and x.validation_case_identities for x in reproducibility)
    status, risk = _evidence_status(present=bool(reproducibility), valid=bool(repro_ok), malformed=_has_malformed_object(reproducibility_root, ExplanationReproducibilityAnalysis), unavailable="Cross-run reproducibility is absent.", invalid="Cross-run reproducibility is incomplete.")
    gates.append(_gate("explanation_reproducibility", status, [f"reproducibility:{x.analysis_id}" for x in reproducibility], risk))
    behavior_root = base / "evidence" / "behavior-specs"; specs = _objects(behavior_root, BehaviorSpec)
    results = _objects(behavior_root, BehaviorSpecResult)
    result_by_spec = {x.spec_id: x for x in results}
    if _has_malformed_object(behavior_root, BehaviorSpec) or _has_malformed_object(behavior_root, BehaviorSpecResult):
        gates.append(_gate("behavior_specs", "FAIL", [], "Malformed BehaviorSpec evidence prevents a PASS claim."))
    elif not specs:
        gates.append(_gate("behavior_specs", "NOT_AVAILABLE", [], "No valid BehaviorSpec exists."))
    elif any(x.spec_id not in result_by_spec for x in specs):
        gates.append(_gate("behavior_specs", "WARN", [f"behavior-spec:{x.spec_id}" for x in specs], "One or more BehaviorSpecs lack execution evidence."))
    elif any(result_by_spec[x.spec_id].status == "FAIL" for x in specs):
        gates.append(_gate("behavior_specs", "FAIL", [f"behavior-result:{result_by_spec[x.spec_id].result_id}" for x in specs], "A persisted BehaviorSpec execution failed."))
    else:
        gates.append(_gate("behavior_specs", "PASS", [f"behavior-result:{result_by_spec[x.spec_id].result_id}" for x in specs]))
    exhaustive_root = base / "evidence" / "exhaustive-lab"; exhaustive = _objects(exhaustive_root, ExhaustiveLabResult)
    exhaustive_ok = exhaustive and all(x.exactness_label in {"EXACT_FINITE_STRUCTURE", "EXACT_ON_DECLARED_DISCRETE_GRID"} for x in exhaustive)
    status, risk = _evidence_status(present=bool(exhaustive), valid=bool(exhaustive_ok), malformed=_has_malformed_object(exhaustive_root, ExhaustiveLabResult), unavailable="Exhaustive evidence is absent.", invalid="Exhaustive evidence has an invalid exactness label.")
    gates.append(_gate("exhaustive_lab", status, [f"exhaustive:{x.result_id}" for x in exhaustive], risk))
    final_root = base / "analyses" / "final-tests"; final_tests = _objects(final_root, FinalTestEvaluation)
    final_ok = final_tests and all(x.status == "FINAL_TEST_EVALUATED" and x.policy_frozen_at is not None for x in final_tests)
    status, risk = _evidence_status(present=bool(final_tests), valid=bool(final_ok), malformed=_has_malformed_object(final_root, FinalTestEvaluation), unavailable="Final-test evidence is absent.", invalid="Final-test evidence is not tied to a frozen policy.")
    gates.append(_gate("final_test", status, [f"final-test:{x.final_test_id}" for x in final_tests], risk))
    result = AssuranceCase(gates=gates, unresolved_risks=[x.risk for x in gates if x.risk])
    _atomic_write_text(_root(base) / f"{result.assurance_id}.json", result.model_dump_json(indent=2))
    _atomic_write_text(_root(base) / "active-case.json", json.dumps({"assurance_id": str(result.assurance_id)}))
    return result


def load_latest_assurance_case(root: Path) -> AssuranceCase:
    pointer = json.loads((_root(root) / "active-case.json").read_text())
    return AssuranceCase.model_validate_json((_root(root) / f"{pointer['assurance_id']}.json").read_text())
