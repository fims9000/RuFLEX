from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ValidationError

from ruflex.application.datasets import LeakageAuditReport, TransformPipelineContract, load_dataset_contract, load_leakage_audit, load_transform_pipeline_contract
from ruflex.application.evidence import _atomic_write_text
from ruflex.application.generalization import GeneralizationContract, SliceAnalysis
from ruflex.application.fis import list_fis_revisions
from ruflex.domain.assurance import AssuranceCase, AssuranceClaim, AssuranceGate
from ruflex.application.behavior import _requirement_identity, evaluate_behavior_spec
from ruflex.domain.behavior import BehaviorRevisionComparison, BehaviorSpec, BehaviorSpecResult
from ruflex.domain.evidence import ExplanationCheck, ExplanationContract, ExplanationReproducibilityAnalysis
from ruflex.domain.exhaustive import ExhaustiveLabResult
from ruflex.domain.selective import SelectivePredictionPolicy
from ruflex.domain.stability import StabilityGatePolicy, StudyStabilityAnalysis
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


def _prefixed_objects(root: Path, prefix: str, model: type[ModelT]) -> list[ModelT]:
    if not root.is_dir():
        return []
    items: list[ModelT] = []
    for path in root.glob(f"{prefix}*.json"):
        try:
            items.append(model.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValidationError, ValueError):
            continue
    return items


def _has_malformed_prefixed_object(root: Path, prefix: str, model: type[ModelT]) -> bool:
    if not root.is_dir():
        return False
    for path in root.glob(f"{prefix}*.json"):
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
    from ruflex.application.project_integrity import inspect_project_integrity
    project_integrity = inspect_project_integrity(base)
    integrity_evidence = (
        [f"project-integrity:{issue.code}:{issue.path}" for issue in project_integrity.issues]
        if project_integrity.issues else ["project-integrity:PASS"]
    )
    integrity_risk = (
        f"{len(project_integrity.issues)} persisted project-integrity issue(s) require review."
        if project_integrity.issues else None
    )
    gates.append(_gate(
        "project_integrity",
        project_integrity.status,
        integrity_evidence,
        integrity_risk,
    ))
    try:
        contract = load_dataset_contract(base)
        gates.append(_gate("dataset_contract", "PASS", [f"dataset:{contract.dataset_fingerprint}"]))
    except (ValueError, OSError, ValidationError) as error:
        gates.append(_gate("dataset_contract", "FAIL", [], f"DatasetContract is missing or malformed: {error}"))
    runs_root = base / "runs"; runs = _objects(runs_root, TrainingRun)
    status, risk = _evidence_status(present=bool(runs), valid=bool(runs), malformed=_has_malformed_object(runs_root, TrainingRun), unavailable="No valid TrainingRun provenance exists.", invalid="Training provenance is invalid.")
    gates.append(_gate("training_provenance", status, [f"run:{x.run_id}" for x in runs], risk))
    transforms_root = base / "data" / "transforms"; transforms = _objects(transforms_root, TransformPipelineContract)
    try:
        transforms_by_id = {str(item.pipeline_id): load_transform_pipeline_contract(base, item.pipeline_id) for item in transforms}
        transform_ok = bool(transforms) and all(
            loaded.pipeline_identity == item.pipeline_identity
            and all(
                run.dataset_fingerprint == loaded.dataset_fingerprint
                and run.split.split_contract_id == loaded.split_contract_id
                and run.feature_columns == loaded.feature_order
                for run in runs if run.transform_pipeline_id == str(item.pipeline_id)
            )
            for item in transforms
            for loaded in [transforms_by_id[str(item.pipeline_id)]]
        )
    except (OSError, ValueError, ValidationError):
        transforms_by_id = {}
        transform_ok = False
    status, risk = _evidence_status(present=bool(transforms), valid=bool(transform_ok), malformed=_has_malformed_object(transforms_root, TransformPipelineContract), unavailable="No persisted train-only transform pipeline exists.", invalid="Transform pipeline provenance is invalid.")
    gates.append(_gate("transform_pipeline", status, [f"transform-pipeline:{x.pipeline_id}" for x in transforms], risk))
    leakage_root = base / "data" / "leakage-audits"; leakage_audits = _objects(leakage_root, LeakageAuditReport)
    try:
        loaded_audits = [load_leakage_audit(base, item.audit_id) for item in leakage_audits]
        leakage_ok = bool(loaded_audits) and all(
            audit.status != "FAIL"
            and (
                audit.transform_pipeline_id is None
                or audit.transform_pipeline_id in transforms_by_id
                and transforms_by_id[audit.transform_pipeline_id].dataset_fingerprint == audit.dataset_fingerprint
                and transforms_by_id[audit.transform_pipeline_id].split_contract_id == audit.split_contract_id
            )
            and all(
                run.leakage_audit_id != str(audit.audit_id)
                or run.dataset_fingerprint == audit.dataset_fingerprint
                and run.transform_pipeline_id == audit.transform_pipeline_id
                and run.split.split_contract_id == audit.split_contract_id
                for run in runs
            )
            for audit in loaded_audits
        )
    except (OSError, ValueError, ValidationError):
        leakage_ok = False
    status, risk = _evidence_status(present=bool(leakage_audits), valid=bool(leakage_ok), malformed=_has_malformed_object(leakage_root, LeakageAuditReport), unavailable="No persisted data-leakage audit exists.", invalid="A persisted data-leakage audit failed or is invalid.")
    gates.append(_gate("data_leakage_audit", status, [f"leakage-audit:{x.audit_id}" for x in leakage_audits], risk))
    studies_root = base / "studies"; studies = _objects(studies_root, TrainingStudy)
    status, risk = _evidence_status(present=bool(studies), valid=any(len(x.seed_runs) >= 3 for x in studies), malformed=_has_malformed_object(studies_root, TrainingStudy), unavailable="No valid multi-seed study exists.", invalid="No study contains sufficient seed-run evidence.")
    gates.append(_gate("multi_seed_evidence", status, [f"study:{x.study_id}" for x in studies], risk))
    evaluations_root = base / "analyses" / "evaluations"; evaluations = _objects(evaluations_root, AnalysisEvaluation)
    evaluation_ids = {x.evaluation_id for x in evaluations}
    evaluation_by_id = {item.evaluation_id: item for item in evaluations}
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
    stability_root = base / "analyses" / "stability-analyses"; stability = _objects(stability_root, StudyStabilityAnalysis)
    run_by_id = {item.run_id: item for item in runs}
    study_by_id = {item.study_id: item for item in studies}
    threshold_by_id = {item.threshold_id: item for item in thresholds}
    from ruflex.application.project_integrity import _stability_analysis_cases_match
    stability_ok = stability and all(
        item.applicability == "APPLICABLE"
        and item.validation_alignment_status == "EXACT_MATCH"
        and item.mode == "TRAINING_VARIABILITY"
        and len(item.run_ids) >= 3
        and item.case_count == len(item.cases)
        and item.case_count > 0
        and item.evaluation_case_identity is not None
        and all(case.run_support_count == len(item.run_ids) for case in item.cases)
        and item.study_id in study_by_id
        and set(item.run_ids) == {run.run_id for run in study_by_id[item.study_id].seed_runs}
        and all(run_id in run_by_id and run_by_id[run_id].dataset_fingerprint == item.dataset_fingerprint for run_id in item.run_ids)
        and _stability_analysis_cases_match(
            item,
            study_by_id[item.study_id],
            evaluation_by_id.get(item.evaluation_id) if item.evaluation_id is not None else None,
            threshold_by_id.get(item.class_threshold_id) if item.class_threshold_id is not None else None,
        )
        for item in stability
    )
    status, risk = _evidence_status(present=bool(stability), valid=bool(stability_ok), malformed=_has_malformed_object(stability_root, StudyStabilityAnalysis), unavailable="Study Stability Analysis is absent.", invalid="Cross-run stability evidence is incomplete.")
    gates.append(_gate("prediction_stability", status, [f"stability-analysis:{x.analysis_id}" for x in stability], risk))
    stability_policy_root = base / "analyses" / "stability-policies"; stability_policies = _objects(stability_policy_root, StabilityGatePolicy)
    stability_by_id = {item.analysis_id: item for item in stability}
    from ruflex.application.project_integrity import _stability_gate_evidence_matches
    stability_policy_ok = stability_policies and all(
        item.source_split == "validation"
        and item.frozen_at is not None
        and item.probability_source == "raw"
        and item.stability_analysis_id in stability_by_id
        and item.evaluation_id in evaluation_by_id
        and item.class_threshold_id in {threshold.threshold_id for threshold in thresholds}
        and item.selected_run_id in run_by_id
        and item.run_ids == stability_by_id[item.stability_analysis_id].run_ids
        and item.dataset_fingerprint == stability_by_id[item.stability_analysis_id].dataset_fingerprint
        and evaluation_by_id[item.evaluation_id].run_id == item.selected_run_id
        and evaluation_by_id[item.evaluation_id].split == "validation"
        and next(threshold for threshold in thresholds if threshold.threshold_id == item.class_threshold_id).evaluation_id == item.evaluation_id
        and next(threshold for threshold in thresholds if threshold.threshold_id == item.class_threshold_id).run_id == item.selected_run_id
        and next(threshold for threshold in thresholds if threshold.threshold_id == item.class_threshold_id).source_split == "validation"
        and next(threshold for threshold in thresholds if threshold.threshold_id == item.class_threshold_id).probability_source == "raw"
        and next(threshold for threshold in thresholds if threshold.threshold_id == item.class_threshold_id).calibration_id is None
        and next(threshold for threshold in thresholds if threshold.threshold_id == item.class_threshold_id).selected_threshold == item.decision_threshold
        and stability_by_id[item.stability_analysis_id].class_threshold_id == item.class_threshold_id
        and stability_by_id[item.stability_analysis_id].decision_threshold == item.decision_threshold
        and item.fit_sample_identity == stability_by_id[item.stability_analysis_id].evaluation_case_identity
        and len(item.decisions) == stability_by_id[item.stability_analysis_id].case_count
        and _stability_gate_evidence_matches(item, stability_by_id[item.stability_analysis_id])
        for item in stability_policies
    )
    status, risk = _evidence_status(present=bool(stability_policies), valid=bool(stability_policy_ok), malformed=_has_malformed_object(stability_policy_root, StabilityGatePolicy), unavailable="Stability-aware review policy is absent.", invalid="Stability-aware review policy is incompatible with validation stability evidence.")
    gates.append(_gate("stability_gate_policy", status, [f"stability-policy:{x.policy_id}" for x in stability_policies], risk))
    contracts_root = base / "objects" / "protocols" / "generalization"; contracts = _objects(contracts_root, GeneralizationContract)
    frozen = [x for x in contracts if x.frozen_at is not None]
    if _has_malformed_object(contracts_root, GeneralizationContract):
        gates.append(_gate("generalization_contract", "FAIL", [], "Malformed GeneralizationContract prevents a PASS claim."))
    else:
        gates.append(_gate("generalization_contract", "PASS" if frozen else ("NOT_AVAILABLE" if not contracts else "WARN"), [f"generalization:{x.contract_id}" for x in frozen], None if frozen else "No frozen GeneralizationContract exists."))
    slices_root = base / "analyses" / "slices"; slices = _objects(slices_root, SliceAnalysis)
    runs_by_id = {item.run_id: item for item in runs}
    contracts_by_id = {item.contract_id: item for item in contracts}

    def slice_matches(item: SliceAnalysis) -> bool:
        evaluation = evaluation_by_id.get(item.evaluation_id)
        run = runs_by_id.get(item.run_id)
        scope = contracts_by_id.get(item.generalization_contract_id) if item.generalization_contract_id is not None else None
        definitions = {definition.name: definition for definition in item.definitions}
        results_by_name = {result.name: result for result in item.results}
        return bool(
            evaluation is not None
            and run is not None
            and evaluation.run_id == item.run_id
            and evaluation.split == "validation"
            and evaluation.dataset_fingerprint == item.dataset_fingerprint
            and run.dataset_fingerprint == item.dataset_fingerprint
            and item.source_split == "validation"
            and item.test_status == "LOCKED_NOT_EVALUATED"
            and (item.generalization_contract_id is None or (scope is not None and scope.dataset_fingerprint == item.dataset_fingerprint))
            and len(definitions) == len(item.definitions)
            and len(results_by_name) == len(item.results)
            and set(definitions) == set(results_by_name)
            and all(
                result.metric == item.metric
                and result.kind == definitions[name].kind
                and (
                    (result.n == 0 and result.status == "EMPTY" and result.value is None and result.delta_vs_overall is None)
                    or (result.n > 0 and result.value is None and result.status == "WARN" and result.delta_vs_overall is None)
                    or (result.n > 0 and result.value is not None and result.delta_vs_overall is not None and abs(result.delta_vs_overall - (result.value - result.overall_value)) <= 1e-12)
                )
                for name, result in results_by_name.items()
            )
        )

    slice_ok = bool(slices) and all(slice_matches(item) for item in slices)
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
    runs_by_id = {item.run_id: item for item in runs}
    explanations_by_id = {item.explanation_id: item for item in explanations}

    def reproducibility_matches(item: ExplanationReproducibilityAnalysis) -> bool:
        matched_runs = [runs_by_id.get(run_id) for run_id in item.run_ids]
        matched_explanations = [explanations_by_id.get(explanation_id) for explanation_id in item.explanation_ids]
        case_sets = [
            [row.source_row if row.source_row is not None else row.row for row in run.prediction_preview]
            for run in matched_runs if run is not None
        ]
        expected_cases = [str(value) for value in sorted(case_sets[0])] if case_sets else []
        expected_pairs = {
            frozenset((left, right))
            for index, left in enumerate(item.run_ids)
            for right in item.run_ids[index + 1:]
        }
        actual_pairs = {
            frozenset((pair.left_run_id, pair.right_run_id))
            for pair in item.pairwise
        }
        return bool(
            len(item.run_ids) >= 2
            and len(set(item.run_ids)) == len(item.run_ids)
            and len(set(item.explanation_ids)) == len(item.explanation_ids)
            and all(run is not None for run in matched_runs)
            and all(explanation is not None for explanation in matched_explanations)
            and {explanation.run_id for explanation in matched_explanations if explanation is not None} == set(item.run_ids)
            and all(run.dataset_fingerprint == item.dataset_fingerprint and run.task == item.task and run.target == item.target for run in matched_runs if run is not None)
            and all(explanation.method == item.explanation_method and explanation.reference_definition == item.reference_protocol for explanation in matched_explanations if explanation is not None)
            and all(len(values) == len(set(values)) and values == case_sets[0] for values in case_sets)
            and bool(expected_cases)
            and len(expected_cases) == len(set(expected_cases))
            and item.validation_case_identities == expected_cases
            and len(item.pairwise) == len(actual_pairs)
            and actual_pairs == expected_pairs
        )

    repro_ok = reproducibility and all(reproducibility_matches(item) for item in reproducibility)
    status, risk = _evidence_status(present=bool(reproducibility), valid=bool(repro_ok), malformed=_has_malformed_object(reproducibility_root, ExplanationReproducibilityAnalysis), unavailable="Cross-run reproducibility is absent.", invalid="Cross-run reproducibility is incomplete.")
    gates.append(_gate("explanation_reproducibility", status, [f"reproducibility:{x.analysis_id}" for x in reproducibility], risk))
    behavior_root = base / "evidence" / "behavior-specs"; specs = _objects(behavior_root, BehaviorSpec)
    results = _prefixed_objects(behavior_root, "result-", BehaviorSpecResult)
    result_by_spec = {x.spec_id: x for x in results}
    behavior_invalid = _has_malformed_object(behavior_root, BehaviorSpec) or _has_malformed_prefixed_object(behavior_root, "result-", BehaviorSpecResult)
    if len({item.spec_id for item in specs}) != len(specs) or any(item.spec_id not in {spec.spec_id for spec in specs} for item in results):
        behavior_invalid = True
    if not behavior_invalid:
        for result in results:
            spec = next((item for item in specs if item.spec_id == result.spec_id), None)
            if spec is None:
                behavior_invalid = True
                break
            try:
                expected = evaluate_behavior_spec(base, spec)
                if result.model_dump(mode="json", exclude={"result_id", "created_at"}) != expected.model_dump(mode="json", exclude={"result_id", "created_at"}):
                    behavior_invalid = True
                    break
            except (OSError, ValueError, TypeError, KeyError, IndexError):
                behavior_invalid = True
                break
    if behavior_invalid:
        gates.append(_gate("behavior_specs", "FAIL", [], "Malformed BehaviorSpec evidence prevents a PASS claim."))
    elif not specs:
        gates.append(_gate("behavior_specs", "NOT_AVAILABLE", [], "No valid BehaviorSpec exists."))
    elif any(x.spec_id not in result_by_spec for x in specs):
        gates.append(_gate("behavior_specs", "WARN", [f"behavior-spec:{x.spec_id}" for x in specs], "One or more BehaviorSpecs lack execution evidence."))
    elif any(result_by_spec[x.spec_id].status == "FAIL" for x in specs):
        gates.append(_gate("behavior_specs", "FAIL", [f"behavior-result:{result_by_spec[x.spec_id].result_id}" for x in specs], "A persisted BehaviorSpec execution failed."))
    else:
        gates.append(_gate("behavior_specs", "PASS", [f"behavior-result:{result_by_spec[x.spec_id].result_id}" for x in specs]))
    comparisons = _prefixed_objects(behavior_root, "comparison-", BehaviorRevisionComparison)
    comparison_malformed = _has_malformed_prefixed_object(behavior_root, "comparison-", BehaviorRevisionComparison)
    if not comparison_malformed:
        comparison_malformed = any(path.name != f"comparison-{comparison.comparison_id}.json" for path, comparison in (
            (path, BehaviorRevisionComparison.model_validate_json(path.read_text(encoding="utf-8")))
            for path in behavior_root.glob("comparison-*.json")
        )) if behavior_root.is_dir() else False
    by_result = {item.result_id: item for item in results}
    by_spec = {item.spec_id: item for item in specs}
    comparison_invalid = False
    for comparison in comparisons:
        baseline = by_result.get(comparison.baseline_result_id)
        candidate = by_result.get(comparison.candidate_result_id)
        baseline_spec = by_spec.get(baseline.spec_id) if baseline else None
        candidate_spec = by_spec.get(candidate.spec_id) if candidate else None
        transition = f"{baseline.status}_TO_{candidate.status}" if baseline and candidate else None
        if (
            baseline_spec is None or candidate_spec is None
            or _requirement_identity(baseline_spec) != comparison.requirement_identity
            or _requirement_identity(candidate_spec) != comparison.requirement_identity
            or comparison.baseline_status != baseline.status or comparison.candidate_status != candidate.status
            or comparison.transition != transition or comparison.regression_detected != (transition == "PASS_TO_FAIL")
            or comparison.baseline_binding != str(baseline.model_artifact_sha256 or baseline.fis_semantic_hash)
            or comparison.candidate_binding != str(candidate.model_artifact_sha256 or candidate.fis_semantic_hash)
        ):
            comparison_invalid = True
    if comparison_malformed or comparison_invalid:
        gates.append(_gate("behavior_revision_comparisons", "FAIL", [], "Malformed or mismatched behavior revision evidence prevents a PASS claim."))
    elif not comparisons:
        gates.append(_gate("behavior_revision_comparisons", "NOT_AVAILABLE", [], "No behavior revision comparison has been persisted."))
    else:
        gates.append(_gate("behavior_revision_comparisons", "PASS", [f"behavior-comparison:{item.comparison_id}" for item in comparisons]))
    exhaustive_root = base / "evidence" / "exhaustive-lab"; exhaustive = _objects(exhaustive_root, ExhaustiveLabResult)
    try:
        known_fis_hashes = {item.semantic_hash for item in list_fis_revisions(base)}
    except (OSError, ValueError, ValidationError):
        known_fis_hashes = set()

    def exhaustive_result_matches(item: ExhaustiveLabResult) -> bool:
        if item.state_count != len(item.paths) or item.state_estimate < item.state_count or item.state_count > item.max_states:
            return False
        if item.kind == "decision_tree_structure":
            run = runs_by_id.get(item.run_id) if item.run_id is not None else None
            return (
                item.exactness_label == "EXACT_FINITE_STRUCTURE"
                and isinstance(run, TrainingRun)
                and run.model_kind == "decision_tree"
                and item.fis_semantic_hash is None
                and item.requested_grid_points is None
            )
        points = item.requested_grid_points
        return (
            item.exactness_label == "EXACT_ON_DECLARED_DISCRETE_GRID"
            and item.fis_semantic_hash in known_fis_hashes
            and item.run_id is None
            and points is not None
            and len(item.declared_grid) > 0
            and all(len(values) == points for values in item.declared_grid.values())
            and item.state_estimate == points ** len(item.declared_grid)
            and all(set(state.get("inputs", {})) == set(item.declared_grid) for state in item.paths)
        )

    exhaustive_ok = bool(exhaustive) and all(exhaustive_result_matches(item) for item in exhaustive)
    status, risk = _evidence_status(present=bool(exhaustive), valid=bool(exhaustive_ok), malformed=_has_malformed_object(exhaustive_root, ExhaustiveLabResult), unavailable="Exhaustive evidence is absent.", invalid="Exhaustive evidence has an invalid exactness label.")
    gates.append(_gate("exhaustive_lab", status, [f"exhaustive:{x.result_id}" for x in exhaustive], risk))
    final_root = base / "analyses" / "final-tests"; final_tests = _objects(final_root, FinalTestEvaluation)
    final_test_integrity_codes = {
        "FINAL_TEST_EVIDENCE_MALFORMED",
        "FINAL_TEST_PROVENANCE_MISMATCH",
        "FINAL_TEST_DUPLICATE_POLICY_EVIDENCE",
        "FINAL_TEST_ACTIVE_POINTER_INVALID",
        "DATASET_TEST_UNLOCK_INCONSISTENT",
    }
    final_integrity_ok = not any(issue.code in final_test_integrity_codes for issue in project_integrity.issues)
    final_ok = bool(final_tests) and all(x.status == "FINAL_TEST_EVALUATED" and x.policy_frozen_at is not None for x in final_tests) and final_integrity_ok
    status, risk = _evidence_status(present=bool(final_tests), valid=bool(final_ok), malformed=_has_malformed_object(final_root, FinalTestEvaluation), unavailable="Final-test evidence is absent.", invalid="Final-test evidence does not resolve to its frozen model, validation policy, case identities, metrics, timestamps, or Stability evidence.")
    gates.append(_gate("final_test", status, [f"final-test:{x.final_test_id}" for x in final_tests], risk))
    claims = [
        AssuranceClaim(
            statement=f"{gate.key.replace('_', ' ').capitalize()} is supported by the declared persisted evidence.",
            status="SUPPORTED" if gate.status == "PASS" else "QUALIFIED",
            evidence_ids=gate.evidence,
            assumptions=["Referenced evidence remains readable and correctly bound to its recorded provenance."],
            limitations=[gate.risk] if gate.risk else [],
        )
        for gate in gates if gate.evidence
    ]
    result = AssuranceCase(gates=gates, claims=claims, unresolved_risks=[x.risk for x in gates if x.risk])
    _atomic_write_text(_root(base) / f"{result.assurance_id}.json", result.model_dump_json(indent=2))
    _atomic_write_text(_root(base) / "active-case.json", json.dumps({"assurance_id": str(result.assurance_id)}))
    return result


def load_latest_assurance_case(root: Path) -> AssuranceCase:
    pointer = json.loads((_root(root) / "active-case.json").read_text())
    return AssuranceCase.model_validate_json((_root(root) / f"{pointer['assurance_id']}.json").read_text())


def load_assurance_case(root: Path, assurance_id: UUID) -> AssuranceCase:
    return AssuranceCase.model_validate_json((_root(root) / f"{assurance_id}.json").read_text())
