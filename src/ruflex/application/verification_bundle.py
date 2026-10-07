"""Safe, declarative evidence export; never an executable project archive."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from ruflex.application.assurance import load_latest_assurance_case
from ruflex.application.behavior import _requirement_identity
from ruflex.application.evidence import _atomic_write_text
from ruflex.application.lineage import build_project_lineage
from ruflex.domain.verification import VerificationBundle, VerificationBundleValidation
from ruflex.application.datasets import DataAuditReport, DatasetContract, DatasetProfile, LeakageAuditReport, SplitContract, TransformPipelineContract, _transform_pipeline_identity, row_identity
from ruflex.domain.assurance import AssuranceCase
from ruflex.domain.behavior import BehaviorRevisionComparison, BehaviorSpec, BehaviorSpecResult
from ruflex.domain.demo import ConditionMonitoringDemo
from ruflex.domain.evidence import ExplanationCheck, ExplanationContract, ExplanationReproducibilityAnalysis
from ruflex.domain.expert_correction import ExpertCorrectionRevision
from ruflex.domain.exhaustive import ExhaustiveLabResult
from ruflex.domain.fis import FISSpec
from ruflex.application.generalization import GeneralizationContract, SliceAnalysis
from ruflex.domain.selective import SelectivePredictionPolicy
from ruflex.domain.stability import StabilityGatePolicy, StudyStabilityAnalysis
from ruflex.domain.training import AnalysisComparison, AnalysisEvaluation, CalibrationTransform, DecisionThresholdPolicy, FinalTestEvaluation, TrainingRun, TrainingStudy, TreePathEvidence

_EVIDENCE_DIRS = (
    "runs", "studies", "analyses/evaluations", "analyses/calibrations", "analyses/thresholds",
    "analyses/selective-policies", "analyses/stability-analyses", "analyses/stability-policies", "analyses/slices", "analyses/final-tests", "analyses/comparisons",
    "objects/protocols/generalization", "evidence/explanations", "evidence/explanation-checks",
    "evidence/explanation-reproducibility", "evidence/behavior-specs", "evidence/exhaustive-lab",
    "evidence/tree-paths", "evidence/assurance", "evidence/condition-monitoring-demo", "analyses/expert-corrections",
)
_DECLARATIVE_MODEL_DIRS = ("models/fis",)
_POINTERS = {"active-training-run.json", "active-study.json", "active-evaluation.json", "active-calibration.json", "active-threshold.json", "active-policy.json", "active-slice-analysis.json", "active-final-test.json", "active-comparison.json", "active-explanation.json", "active-check.json", "active-analysis.json", "active-spec.json", "active-result.json", "active-case.json", "active-correction.json", "active-demo.json", "active-bundle.json", "latest.json"}
_EXCLUDED = ["raw datasets", "pickle/joblib", "untrusted executable code", "credentials", "node_modules", "caches", "temporary build products"]


def _sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()


_FORBIDDEN_SUFFIXES = (".pkl", ".pickle", ".joblib", ".pyc", ".py", ".sh", ".exe")


def _safe_name(name: str) -> bool:
    path = Path(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and not name.startswith("/")


def _model_for_entry(name: str) -> type[BaseModel] | None:
    if name == "data/dataset-contract.json": return DatasetContract
    if name == "data/dataset-profile.json": return DatasetProfile
    if name == "data/dataset-audit.json": return DataAuditReport
    if name.startswith("data/splits/"): return SplitContract
    if name.startswith("data/transforms/"): return TransformPipelineContract
    if name.startswith("data/leakage-audits/"): return LeakageAuditReport
    if name.startswith("runs/"): return TrainingRun
    if name.startswith("studies/"): return TrainingStudy
    if name.startswith("analyses/evaluations/"): return AnalysisEvaluation
    if name.startswith("analyses/calibrations/"): return CalibrationTransform
    if name.startswith("analyses/thresholds/"): return DecisionThresholdPolicy
    if name.startswith("analyses/selective-policies/"): return SelectivePredictionPolicy
    if name.startswith("analyses/stability-analyses/"): return StudyStabilityAnalysis
    if name.startswith("analyses/stability-policies/"): return StabilityGatePolicy
    if name.startswith("analyses/slices/"): return SliceAnalysis
    if name.startswith("analyses/final-tests/"): return FinalTestEvaluation
    if name.startswith("analyses/comparisons/"): return AnalysisComparison
    if name.startswith("objects/protocols/generalization/"): return GeneralizationContract
    if name.startswith("evidence/explanations/"): return ExplanationContract
    if name.startswith("evidence/explanation-checks/"): return ExplanationCheck
    if name.startswith("evidence/explanation-reproducibility/"): return ExplanationReproducibilityAnalysis
    if name.startswith("evidence/tree-paths/"): return TreePathEvidence
    if name.startswith("analyses/expert-corrections/"): return ExpertCorrectionRevision
    if name.startswith("evidence/exhaustive-lab/"): return ExhaustiveLabResult
    if name.startswith("evidence/condition-monitoring-demo/"): return ConditionMonitoringDemo
    if name.startswith("models/fis/") and name.endswith(".json"): return FISSpec
    if name.startswith("evidence/behavior-specs/comparison-"): return BehaviorRevisionComparison
    if name.startswith("evidence/behavior-specs/result-"): return BehaviorSpecResult
    if name.startswith("evidence/behavior-specs/"): return BehaviorSpec
    if name.startswith("evidence/assurance/"): return AssuranceCase
    return None


def _read_bundle_entries(source: Path) -> tuple[dict[str, bytes], str | None, list[str]]:
    """Read a ZIP or an extracted bundle without executing any contents."""
    errors: list[str] = []
    if source.is_file():
        raw = source.read_bytes()
        try:
            with zipfile.ZipFile(source) as archive:
                names = archive.namelist()
                if len(names) != len(set(names)): errors.append("Bundle contains duplicate entry names.")
                entries = {name: archive.read(name) for name in names if _safe_name(name)}
                if any(not _safe_name(name) for name in names): errors.append("Bundle contains an unsafe archive path.")
        except zipfile.BadZipFile:
            return {}, _sha(raw), ["Bundle is not a valid ZIP archive."]
        return entries, _sha(raw), errors
    if source.is_dir():
        entries = {path.relative_to(source).as_posix(): path.read_bytes() for path in source.rglob("*") if path.is_file()}
        return entries, None, errors
    return {}, None, ["Bundle path does not exist."]


def _validate_relationships(objects: list[BaseModel]) -> list[str]:
    by_type: dict[type[BaseModel], set[str]] = {}
    objects_by_type: dict[type[BaseModel], dict[str, BaseModel]] = {}
    for object_ in objects:
        identifier_field = {
            DatasetContract: "dataset_fingerprint", SplitContract: "split_id", TransformPipelineContract: "pipeline_id", LeakageAuditReport: "audit_id", TrainingRun: "run_id", TrainingStudy: "study_id", AnalysisEvaluation: "evaluation_id", CalibrationTransform: "calibration_id", DecisionThresholdPolicy: "threshold_id", SelectivePredictionPolicy: "policy_id", StudyStabilityAnalysis: "analysis_id", StabilityGatePolicy: "policy_id", FinalTestEvaluation: "final_test_id", ExplanationContract: "explanation_id", ExplanationCheck: "check_id", ExplanationReproducibilityAnalysis: "analysis_id", TreePathEvidence: "evidence_id", ExpertCorrectionRevision: "correction_id", ExhaustiveLabResult: "result_id", ConditionMonitoringDemo: "demo_id", FISSpec: "fis_id", BehaviorSpec: "spec_id", BehaviorSpecResult: "result_id", BehaviorRevisionComparison: "comparison_id", AssuranceCase: "assurance_id",
        }.get(type(object_))
        identifier = getattr(object_, identifier_field) if identifier_field else None
        if identifier is not None:
            by_type.setdefault(type(object_), set()).add(str(identifier))
            objects_by_type.setdefault(type(object_), {})[str(identifier)] = object_
    def exists(model: type[BaseModel], value: Any) -> bool: return value is None or str(value) in by_type.get(model, set())
    errors: list[str] = []
    contracts = objects_by_type.get(DatasetContract, {})
    profiles = [item for item in objects if isinstance(item, DatasetProfile)]
    if contracts:
        from ruflex.application.project_integrity import _dataset_contract_profile_mismatch
        for contract in contracts.values():
            if not profiles or any(_dataset_contract_profile_mismatch(contract, profile) for profile in profiles):
                errors.append("DatasetContract feature roles do not match the bundled DatasetProfile.")
    splits = objects_by_type.get(SplitContract, {})
    transforms = objects_by_type.get(TransformPipelineContract, {})
    audits = objects_by_type.get(LeakageAuditReport, {})
    studies = objects_by_type.get(TrainingStudy, {})
    runs = objects_by_type.get(TrainingRun, {})
    evaluations = objects_by_type.get(AnalysisEvaluation, {})
    calibrations = objects_by_type.get(CalibrationTransform, {})
    thresholds = objects_by_type.get(DecisionThresholdPolicy, {})
    stability_analyses = objects_by_type.get(StudyStabilityAnalysis, {})
    generalization_contracts = objects_by_type.get(GeneralizationContract, {})
    selective_policies = objects_by_type.get(SelectivePredictionPolicy, {})
    final_tests = objects_by_type.get(FinalTestEvaluation, {})
    fis_specs = [item for item in objects if isinstance(item, FISSpec)]
    from ruflex.application.project_integrity import _stability_analysis_cases_match, _stability_gate_evidence_matches
    from ruflex.application.project_integrity import _assurance_claim_graph_matches
    for object_ in objects:
        if isinstance(object_, SplitContract):
            contract = contracts.get(object_.dataset_fingerprint)
            if not isinstance(contract, DatasetContract) or object_.dataset_artifact_sha256 != contract.source_artifact_sha256:
                errors.append(f"SplitContract {object_.split_id} has broken DatasetContract provenance.")
        if isinstance(object_, TransformPipelineContract):
            contract = contracts.get(object_.dataset_fingerprint)
            split = splits.get(str(object_.split_contract_id)) if object_.split_contract_id is not None else None
            if object_.pipeline_identity != _transform_pipeline_identity(object_):
                errors.append(f"TransformPipelineContract {object_.pipeline_id} has an invalid immutable pipeline identity.")
            if not isinstance(contract, DatasetContract) or (object_.split_contract_id is not None and not isinstance(split, SplitContract)):
                errors.append(f"TransformPipelineContract {object_.pipeline_id} has broken dataset or split provenance.")
            elif isinstance(split, SplitContract) and split.dataset_fingerprint != object_.dataset_fingerprint:
                errors.append(f"TransformPipelineContract {object_.pipeline_id} references a SplitContract for a different dataset.")
        if isinstance(object_, LeakageAuditReport):
            contract = contracts.get(object_.dataset_fingerprint)
            split = splits.get(str(object_.split_contract_id)) if object_.split_contract_id is not None else None
            transform = transforms.get(str(object_.transform_pipeline_id)) if object_.transform_pipeline_id is not None else None
            if not isinstance(contract, DatasetContract):
                errors.append(f"LeakageAuditReport {object_.audit_id} references a missing DatasetContract.")
            if object_.split_contract_id is not None and not isinstance(split, SplitContract):
                errors.append(f"LeakageAuditReport {object_.audit_id} references missing SplitContract {object_.split_contract_id}.")
            if object_.transform_pipeline_id is not None and not isinstance(transform, TransformPipelineContract):
                errors.append(f"LeakageAuditReport {object_.audit_id} references missing TransformPipelineContract {object_.transform_pipeline_id}.")
            if isinstance(split, SplitContract) and split.dataset_fingerprint != object_.dataset_fingerprint:
                errors.append(f"LeakageAuditReport {object_.audit_id} references a SplitContract for a different dataset.")
            if isinstance(transform, TransformPipelineContract) and (
                transform.dataset_fingerprint != object_.dataset_fingerprint
                or transform.split_contract_id != object_.split_contract_id
            ):
                errors.append(f"LeakageAuditReport {object_.audit_id} has mismatched split/transform provenance.")
        if isinstance(object_, TrainingRun):
            split = splits.get(str(object_.split.split_contract_id)) if object_.split.split_contract_id is not None else None
            transform = transforms.get(str(object_.transform_pipeline_id)) if object_.transform_pipeline_id is not None else None
            audit = audits.get(str(object_.leakage_audit_id)) if object_.leakage_audit_id is not None else None
            if object_.split.split_contract_id is not None and not isinstance(split, SplitContract):
                errors.append(f"TrainingRun {object_.run_id} references missing SplitContract {object_.split.split_contract_id}.")
            elif isinstance(split, SplitContract) and (
                split.dataset_fingerprint != object_.dataset_fingerprint
                or split.split_identity != object_.split.split_identity
            ):
                errors.append(f"TrainingRun {object_.run_id} has mismatched SplitContract provenance.")
            if object_.transform_pipeline_id is not None and not isinstance(transform, TransformPipelineContract):
                errors.append(f"TrainingRun {object_.run_id} references missing TransformPipelineContract {object_.transform_pipeline_id}.")
            elif isinstance(transform, TransformPipelineContract) and (
                transform.dataset_fingerprint != object_.dataset_fingerprint
                or transform.split_contract_id != object_.split.split_contract_id
                or transform.feature_order != object_.feature_columns
            ):
                errors.append(f"TrainingRun {object_.run_id} has mismatched TransformPipelineContract provenance.")
            if object_.leakage_audit_id is not None and not isinstance(audit, LeakageAuditReport):
                errors.append(f"TrainingRun {object_.run_id} references missing LeakageAuditReport {object_.leakage_audit_id}.")
            elif isinstance(audit, LeakageAuditReport) and (
                audit.dataset_fingerprint != object_.dataset_fingerprint
                or audit.split_contract_id != object_.split.split_contract_id
                or audit.transform_pipeline_id != object_.transform_pipeline_id
            ):
                errors.append(f"TrainingRun {object_.run_id} has mismatched LeakageAuditReport provenance.")
        if isinstance(object_, AnalysisEvaluation) and not exists(TrainingRun, object_.run_id): errors.append(f"Evaluation {object_.evaluation_id} references missing TrainingRun {object_.run_id}.")
        elif isinstance(object_, CalibrationTransform) and (not exists(AnalysisEvaluation, object_.evaluation_id) or not exists(TrainingRun, object_.run_id)): errors.append(f"Calibration {object_.calibration_id} has a broken evaluation/run reference.")
        elif isinstance(object_, DecisionThresholdPolicy) and (not exists(AnalysisEvaluation, object_.evaluation_id) or not exists(TrainingRun, object_.run_id)): errors.append(f"Threshold {object_.threshold_id} has a broken evaluation/run reference.")
        elif isinstance(object_, SelectivePredictionPolicy):
            evaluation = evaluations.get(str(object_.evaluation_id))
            run = runs.get(str(object_.run_id))
            threshold = thresholds.get(str(object_.class_threshold_id))
            calibration = calibrations.get(str(object_.calibration_id)) if object_.calibration_id is not None else None
            from ruflex.application.project_integrity import _selective_policy_fit_identity_matches, _selective_policy_risk_coverage_matches
            if (
                not isinstance(evaluation, AnalysisEvaluation)
                or not isinstance(run, TrainingRun)
                or not isinstance(threshold, DecisionThresholdPolicy)
                or (object_.calibration_id is not None and not isinstance(calibration, CalibrationTransform))
                or evaluation.run_id != object_.run_id
                or evaluation.split != "validation"
                or run.dataset_fingerprint != evaluation.dataset_fingerprint
                or threshold.evaluation_id != object_.evaluation_id
                or threshold.run_id != object_.run_id
                or object_.source_split != "validation"
                or object_.test_status != "LOCKED_NOT_EVALUATED"
                or object_.class_threshold != threshold.selected_threshold
                or threshold.source_split != "validation"
                or threshold.test_status != "LOCKED_NOT_EVALUATED"
                or (object_.calibration_id is None and (object_.probability_source != "raw" or threshold.calibration_id is not None or threshold.probability_source != "raw"))
                or (object_.calibration_id is not None and (calibration is None or calibration.evaluation_id != object_.evaluation_id or calibration.run_id != object_.run_id or calibration.source_split != "validation" or object_.probability_source != "calibrated" or threshold.calibration_id != object_.calibration_id or threshold.probability_source != "calibrated"))
                or not _selective_policy_fit_identity_matches(object_, evaluation, threshold, calibration)
                or not _selective_policy_risk_coverage_matches(object_, evaluation, threshold, calibration)
            ):
                errors.append(f"Selective policy {object_.policy_id} does not match its exact frozen validation evidence or recomputed confidence risk-coverage curve.")
        elif isinstance(object_, ExplanationContract):
            run = runs.get(str(object_.run_id))
            from ruflex.application.project_integrity import _stable_identity
            identities_match = (
                (object_.preprocessing_identity is None or object_.preprocessing_identity == _stable_identity("preprocessing", run.normalization))
                and (object_.feature_order_identity is None or object_.feature_order_identity == _stable_identity("feature-order", list(run.feature_columns)))
                and (object_.sample_identity is None or object_.sample_identity == _stable_identity("explanation-sample", {"run_id": str(run.run_id), "sample": object_.sample, "target": object_.target}))
                and (object_.reference_identity is None or object_.reference_identity == _stable_identity("explanation-reference", {"run_id": str(run.run_id), "method": object_.method, "reference_definition": object_.reference_definition}))
            ) if isinstance(run, TrainingRun) else False
            if not isinstance(run, TrainingRun):
                errors.append(f"Explanation {object_.explanation_id} references missing TrainingRun {object_.run_id}.")
            elif (
                object_.model_kind != run.model_kind
                or object_.model_artifact_sha256 != run.model_artifact_sha256
                or (object_.preprocessing_artifact_sha256 is not None and object_.preprocessing_artifact_sha256 != run.preprocessing_artifact_sha256)
                or list(object_.sample) != list(run.feature_columns)
                or [item.feature for item in object_.attributions] != list(run.feature_columns)
                or object_.target != run.target
                or not identities_match
            ):
                errors.append(f"Explanation {object_.explanation_id} does not match its frozen model, preprocessing, feature, target, or sample identities.")
        elif isinstance(object_, ExplanationCheck):
            explanations = objects_by_type.get(ExplanationContract, {})
            explanation = explanations.get(str(object_.explanation_id))
            run = runs.get(str(object_.run_id))
            from ruflex.application.project_integrity import _explanation_check_frozen_components_match
            names = [item.name for item in object_.checks]
            expected_status = (
                "FAILED" if any(item.status == "FAIL" for item in object_.checks)
                else "WARNING" if any(item.status == "WARN" for item in object_.checks)
                else "PASSED_AVAILABLE_CHECKS"
            )
            if not isinstance(explanation, ExplanationContract) or not isinstance(run, TrainingRun) or object_.run_id != explanation.run_id:
                errors.append(f"Explanation check {object_.check_id} has broken evidence provenance.")
            elif (
                object_.status != expected_status
                or len(names) != len(set(names))
                or (object_.validator_key is not None and any(item.validator_key != object_.validator_key for item in object_.checks))
                or (object_.schema_version >= 3 and (not all((object_.validator_key, object_.validator_version, object_.validator_provider)) or not _explanation_check_frozen_components_match(object_, explanation, run)))
            ):
                errors.append(f"Explanation check {object_.check_id} summary or deterministic contract-derived checks do not match its frozen evidence.")
        elif isinstance(object_, AnalysisComparison):
            from ruflex.application.project_integrity import _validation_sample_identity
            compared_runs = [runs.get(str(run_id)) for run_id in object_.run_ids]
            rows = [row for row in object_.metric_rows if row.get("subject_type") == "training_run"]
            rows_by_run = {str(row.get("run_id")): row for row in rows}
            expected_identities = {
                str(run.run_id): identity
                for run in compared_runs
                if isinstance(run, TrainingRun) and (identity := _validation_sample_identity(run)) is not None
            }
            if object_.fis_id is not None and object_.validation_alignment == "same_cases" and expected_identities:
                expected_identities[f"fis:{object_.fis_id}"] = next(iter(expected_identities.values()))
            expected_alignment = (
                "unknown" if len(expected_identities) < len(compared_runs)
                else "same_cases" if len(set(expected_identities.values())) == 1
                else "mixed_cases"
            )
            if (
                len(set(object_.run_ids)) != len(object_.run_ids)
                or any(not isinstance(run, TrainingRun) for run in compared_runs)
                or any(run.task != object_.task or run.target != object_.target or run.evaluation_split != "validation" or run.split.test_status != "LOCKED_NOT_EVALUATED" for run in compared_runs if isinstance(run, TrainingRun))
                or len({run.dataset_fingerprint for run in compared_runs if isinstance(run, TrainingRun)}) > 1
                or (object_.dataset_fingerprint is not None and any(run.dataset_fingerprint != object_.dataset_fingerprint for run in compared_runs if isinstance(run, TrainingRun)))
                or len(rows) != len(object_.run_ids)
                or len(rows_by_run) != len(rows)
                or set(rows_by_run) != {str(run_id) for run_id in object_.run_ids}
                or any(
                    rows_by_run[str(run.run_id)].get("subject_id") != f"run:{run.run_id}"
                    or rows_by_run[str(run.run_id)].get("model_kind") != run.model_kind
                    or any(metric not in rows_by_run[str(run.run_id)] or not isinstance(rows_by_run[str(run.run_id)][metric], (float, int)) or abs(float(rows_by_run[str(run.run_id)][metric]) - float(value)) > 1e-12 for metric, value in run.validation_metrics.items())
                    for run in compared_runs if isinstance(run, TrainingRun)
                )
                or (object_.schema_version >= 2 and object_.validation_sample_identities != expected_identities)
                or (object_.schema_version >= 2 and object_.validation_alignment != expected_alignment)
                or (object_.fis_id is None) != (object_.fis_semantic_hash is None)
            ):
                errors.append(f"Analysis comparison {object_.comparison_id} does not match its frozen validation runs, metrics, or case identities.")
        elif isinstance(object_, SliceAnalysis):
            evaluation = evaluations.get(str(object_.evaluation_id))
            run = runs.get(str(object_.run_id))
            scope = generalization_contracts.get(str(object_.generalization_contract_id)) if object_.generalization_contract_id is not None else None
            definitions = {item.name: item for item in object_.definitions}
            results = {item.name: item for item in object_.results}
            if (
                not isinstance(evaluation, AnalysisEvaluation)
                or not isinstance(run, TrainingRun)
                or evaluation.run_id != object_.run_id
                or evaluation.split != "validation"
                or evaluation.dataset_fingerprint != object_.dataset_fingerprint
                or run.dataset_fingerprint != object_.dataset_fingerprint
                or object_.source_split != "validation"
                or object_.test_status != "LOCKED_NOT_EVALUATED"
                or (object_.generalization_contract_id is not None and (not isinstance(scope, GeneralizationContract) or scope.dataset_fingerprint != object_.dataset_fingerprint))
                or len(definitions) != len(object_.definitions)
                or len(results) != len(object_.results)
                or set(definitions) != set(results)
                or any(result.metric != object_.metric or result.kind != definitions[name].kind or (result.n == 0 and (result.status != "EMPTY" or result.value is not None or result.delta_vs_overall is not None)) or (result.n > 0 and result.value is not None and (result.delta_vs_overall is None or abs(result.delta_vs_overall - (result.value - result.overall_value)) > 1e-12)) for name, result in results.items())
            ):
                errors.append(f"Slice analysis {object_.analysis_id} does not match its frozen validation Evaluation, scope contract, definitions, or result arithmetic.")
        elif isinstance(object_, TreePathEvidence):
            run = runs.get(str(object_.run_id))
            if (
                not isinstance(run, TrainingRun)
                or run.model_kind != "decision_tree"
                or object_.model_artifact_sha256 != run.model_artifact_sha256
                or list(object_.input_sample) != list(run.feature_columns)
                or [step.feature_name for step in object_.steps if step.feature_name not in run.feature_columns]
                or (object_.class_probabilities is not None and run.task != "binary_classification")
            ):
                errors.append(f"Tree path evidence {object_.evidence_id} does not match its frozen Decision Tree run and feature schema.")
        elif isinstance(object_, ExplanationReproducibilityAnalysis):
            analysis_runs = [runs.get(str(run_id)) for run_id in object_.run_ids]
            explanations = objects_by_type.get(ExplanationContract, {})
            analysis_explanations = [explanations.get(str(explanation_id)) for explanation_id in object_.explanation_ids]
            case_sets = [
                sorted(row.source_row if row.source_row is not None else row.row for row in run.prediction_preview)
                for run in analysis_runs if isinstance(run, TrainingRun)
            ]
            expected_cases = [str(value) for value in case_sets[0]] if case_sets else []
            expected_pairs = {
                frozenset((str(left), str(right)))
                for index, left in enumerate(object_.run_ids)
                for right in object_.run_ids[index + 1:]
            }
            actual_pairs = {frozenset((str(pair.left_run_id), str(pair.right_run_id))) for pair in object_.pairwise}
            if (
                len(set(object_.run_ids)) != len(object_.run_ids)
                or len(set(object_.explanation_ids)) != len(object_.explanation_ids)
                or len(analysis_runs) < 2
                or any(not isinstance(run, TrainingRun) for run in analysis_runs)
                or any(not isinstance(item, ExplanationContract) for item in analysis_explanations)
                or any(item.run_id not in object_.run_ids for item in analysis_explanations if isinstance(item, ExplanationContract))
                or {str(item.run_id) for item in analysis_explanations if isinstance(item, ExplanationContract)} != {str(run_id) for run_id in object_.run_ids}
                or any(run.dataset_fingerprint != object_.dataset_fingerprint or run.task != object_.task or run.target != object_.target for run in analysis_runs if isinstance(run, TrainingRun))
                or any(item.method != object_.explanation_method or item.reference_definition != object_.reference_protocol for item in analysis_explanations if isinstance(item, ExplanationContract))
                or any(len(values) != len(set(values)) or values != case_sets[0] for values in case_sets)
                or object_.validation_case_identities != expected_cases
                or len(object_.validation_case_identities) != len(set(object_.validation_case_identities))
                or len(object_.pairwise) != len(actual_pairs)
                or actual_pairs != expected_pairs
            ):
                errors.append(f"Explanation reproducibility analysis {object_.analysis_id} has broken run, explanation, or validation-case provenance.")
        elif isinstance(object_, ExpertCorrectionRevision):
            hashes = {spec.semantic_hash for spec in fis_specs if str(spec.fis_id) == str(object_.fis_id)}
            contracts = objects_by_type.get(DatasetContract, {})
            matching_contract = contracts.get(object_.dataset_fingerprint)
            explanations = objects_by_type.get(ExplanationContract, {})
            if (
                object_.source_semantic_hash not in hashes
                or object_.result_semantic_hash not in hashes
                or not isinstance(matching_contract, DatasetContract)
                or matching_contract.target != object_.target
                or (object_.source_explanation_id is not None and str(object_.source_explanation_id) not in explanations)
                or object_.test_status != "LOCKED_NOT_EVALUATED"
            ):
                errors.append(f"Expert correction {object_.correction_id} does not resolve to its frozen FIS, dataset, target, or source explanation.")
        elif isinstance(object_, ExhaustiveLabResult):
            if object_.kind == "decision_tree_structure":
                run = runs.get(str(object_.run_id)) if object_.run_id is not None else None
                invalid = not isinstance(run, TrainingRun) or run.model_kind != "decision_tree" or object_.fis_semantic_hash is not None
            else:
                known_hashes = {spec.semantic_hash for spec in fis_specs}
                invalid = object_.fis_semantic_hash not in known_hashes or object_.run_id is not None
            if invalid or object_.state_count != len(object_.paths) or object_.state_estimate < object_.state_count:
                errors.append(f"Exhaustive Lab result {object_.result_id} has broken finite-state or model provenance.")
        elif isinstance(object_, ConditionMonitoringDemo):
            policy = selective_policies.get(str(object_.policy_id))
            run = runs.get(str(policy.run_id)) if isinstance(policy, SelectivePredictionPolicy) else None
            threshold = thresholds.get(str(policy.class_threshold_id)) if isinstance(policy, SelectivePredictionPolicy) else None
            explanation = objects_by_type.get(ExplanationContract, {}).get(str(object_.explanation_id)) if object_.explanation_id is not None else None
            check = objects_by_type.get(ExplanationCheck, {}).get(str(object_.explanation_check_id)) if object_.explanation_check_id is not None else None
            scope = generalization_contracts.get(str(object_.generalization_contract_id)) if object_.generalization_contract_id is not None else None
            expected_label = int(object_.probability >= threshold.selected_threshold) if isinstance(threshold, DecisionThresholdPolicy) else None
            expected_confidence = max(object_.probability, 1.0 - object_.probability)
            expected_decision = None
            if isinstance(policy, SelectivePredictionPolicy):
                expected_decision = "ACCEPT" if object_.confidence >= policy.confidence_cutoff else "REVIEW"
            if object_.scope_disposition == "BLOCK":
                expected_decision = "OUT_OF_SCOPE"
            elif object_.scope_disposition == "REVIEW":
                expected_decision = "REVIEW"
            if (
                not isinstance(policy, SelectivePredictionPolicy)
                or not isinstance(run, TrainingRun)
                or not isinstance(threshold, DecisionThresholdPolicy)
                or (object_.generalization_contract_id is not None and (not isinstance(scope, GeneralizationContract) or scope.dataset_fingerprint != run.dataset_fingerprint))
                or abs(object_.confidence - expected_confidence) > 1e-12
                or object_.predicted_class != expected_label
                or object_.decision != expected_decision
                or object_.scope_disposition not in {"ALLOW", "BLOCK", "REVIEW", "NOT_EVALUATED"}
                or (object_.explanation_id is not None and (not isinstance(explanation, ExplanationContract) or explanation.run_id != policy.run_id))
                or (object_.explanation_check_id is not None and (not isinstance(check, ExplanationCheck) or check.explanation_id != object_.explanation_id or check.run_id != policy.run_id))
                or (object_.assurance_id is not None and not exists(AssuranceCase, object_.assurance_id))
                or object_.verification_bundle_sha256 is None
                or len(object_.verification_bundle_sha256) != 64
                or any(character not in "0123456789abcdef" for character in object_.verification_bundle_sha256)
            ):
                errors.append(f"Condition-monitoring demo {object_.demo_id} has broken policy, prediction, scope, explanation, Assurance, or bundle provenance.")
        elif isinstance(object_, BehaviorRevisionComparison):
            baseline = objects_by_type.get(BehaviorSpecResult, {}).get(str(object_.baseline_result_id))
            candidate = objects_by_type.get(BehaviorSpecResult, {}).get(str(object_.candidate_result_id))
            baseline_spec = objects_by_type.get(BehaviorSpec, {}).get(str(baseline.spec_id)) if isinstance(baseline, BehaviorSpecResult) else None
            candidate_spec = objects_by_type.get(BehaviorSpec, {}).get(str(candidate.spec_id)) if isinstance(candidate, BehaviorSpecResult) else None
            transition = f"{baseline.status}_TO_{candidate.status}" if isinstance(baseline, BehaviorSpecResult) and isinstance(candidate, BehaviorSpecResult) else None
            if (
                not isinstance(baseline, BehaviorSpecResult) or not isinstance(candidate, BehaviorSpecResult)
                or not isinstance(baseline_spec, BehaviorSpec) or not isinstance(candidate_spec, BehaviorSpec)
                or _requirement_identity(baseline_spec) != object_.requirement_identity
                or _requirement_identity(candidate_spec) != object_.requirement_identity
                or object_.baseline_status != baseline.status or object_.candidate_status != candidate.status
                or object_.transition != transition or object_.regression_detected != (transition == "PASS_TO_FAIL")
            ):
                errors.append(f"Behavior revision comparison {object_.comparison_id} has broken result provenance.")
        elif isinstance(object_, StudyStabilityAnalysis):
            study = studies.get(str(object_.study_id))
            evaluation = evaluations.get(str(object_.evaluation_id)) if object_.evaluation_id is not None else None
            threshold = thresholds.get(str(object_.class_threshold_id)) if object_.class_threshold_id is not None else None
            if (
                not isinstance(study, TrainingStudy)
                or (object_.evaluation_id is not None and not isinstance(evaluation, AnalysisEvaluation))
                or (object_.class_threshold_id is not None and not isinstance(threshold, DecisionThresholdPolicy))
                or not _stability_analysis_cases_match(object_, study, evaluation, threshold)
            ):
                errors.append(f"Study Stability Analysis {object_.analysis_id} does not match its frozen runs and validation evidence.")
        elif isinstance(object_, StabilityGatePolicy):
            analysis = stability_analyses.get(str(object_.stability_analysis_id))
            evaluation = evaluations.get(str(object_.evaluation_id))
            threshold = thresholds.get(str(object_.class_threshold_id))
            if (
                not isinstance(analysis, StudyStabilityAnalysis)
                or not isinstance(evaluation, AnalysisEvaluation)
                or not isinstance(threshold, DecisionThresholdPolicy)
                or object_.study_id != analysis.study_id
                or object_.selected_run_id != analysis.selected_run_id
                or object_.run_ids != analysis.run_ids
                or object_.evaluation_id != analysis.evaluation_id
                or object_.class_threshold_id != analysis.class_threshold_id
                or object_.dataset_fingerprint != analysis.dataset_fingerprint
                or object_.dataset_artifact_sha256 != analysis.dataset_artifact_sha256
                or object_.source_split != "validation"
                or object_.probability_source != "raw"
                or object_.calibration_id is not None
                or object_.decision_threshold != threshold.selected_threshold
                or threshold.source_split != "validation"
                or threshold.probability_source != "raw"
                or threshold.calibration_id is not None
                or evaluation.run_id != object_.selected_run_id
                or evaluation.split != "validation"
                or not _stability_gate_evidence_matches(object_, analysis)
            ):
                errors.append(f"Stability gate {object_.policy_id} does not match its frozen analysis, selected run, validation threshold, or case evidence.")
        elif isinstance(object_, FinalTestEvaluation):
            from ruflex.application.project_integrity import (
                _final_test_freeze_timestamps_match,
                _final_test_metrics_match,
                _final_test_stability_evidence_matches,
                _stable_identity,
            )
            evaluation = evaluations.get(str(object_.evaluation_id))
            run = runs.get(str(object_.run_id))
            threshold = thresholds.get(str(object_.threshold_id)) if object_.threshold_id is not None else None
            calibration = calibrations.get(str(object_.calibration_id)) if object_.calibration_id is not None else None
            selective = selective_policies.get(str(object_.selective_policy_id)) if object_.selective_policy_id is not None else None
            gate = next((item for item in objects if isinstance(item, StabilityGatePolicy) and item.policy_id == object_.stability_gate_policy_id), None)
            analysis = stability_analyses.get(str(gate.stability_analysis_id)) if isinstance(gate, StabilityGatePolicy) else None
            stability_runs = [runs.get(str(run_id)) for run_id in gate.run_ids] if isinstance(gate, StabilityGatePolicy) else []
            source_rows = [int(row.source_row) for row in object_.prediction_rows if row.source_row is not None]
            case_ids = [row.row_identity or (row_identity(object_.dataset_fingerprint, int(row.source_row)) if row.source_row is not None else None) for row in object_.prediction_rows]
            expected_sample_identity = _stable_identity("final-test-samples", {"dataset_fingerprint": object_.dataset_fingerprint, "run_id": str(object_.run_id), "source_rows": sorted(source_rows)})
            expected_case_identity = _stable_identity("final-test-cases", {"dataset_fingerprint": object_.dataset_fingerprint, "row_identities": sorted(case_ids)}) if all(case_ids) else None
            if (
                not isinstance(evaluation, AnalysisEvaluation)
                or not isinstance(run, TrainingRun)
                or evaluation.run_id != object_.run_id
                or evaluation.split != "validation"
                or run.dataset_fingerprint != object_.dataset_fingerprint
                or run.dataset_artifact_sha256 != object_.dataset_artifact_sha256
                or run.model_artifact_sha256 != object_.model_artifact_sha256
                or run.preprocessing_artifact_sha256 != object_.preprocessing_artifact_sha256
                or object_.task != evaluation.task
                or object_.target != evaluation.target
                or object_.model_kind != evaluation.model_kind
                or object_.model_artifact_sha256 != evaluation.model_artifact_sha256
                or object_.dataset_fingerprint != evaluation.dataset_fingerprint
                or object_.dataset_artifact_sha256 != evaluation.dataset_artifact_sha256
                or object_.preprocessing_identity != evaluation.preprocessing_identity
                or object_.preprocessing_artifact_sha256 != evaluation.preprocessing_artifact_sha256
                or object_.test_row_count != len(object_.prediction_rows)
                or len(set(source_rows)) != len(source_rows)
                or len(set(case_ids)) != len(case_ids)
                or any(row.source_row is None or row.row != index for index, row in enumerate(object_.prediction_rows))
                or any(row.row_identity not in (None, row_identity(object_.dataset_fingerprint, int(row.source_row))) for row in object_.prediction_rows if row.source_row is not None)
                or object_.test_sample_identity != expected_sample_identity
                or object_.test_case_identity != expected_case_identity
                or object_.policy_identity != _stable_identity("final-test-policy", {
                    "run_id": str(object_.run_id),
                    "evaluation_id": str(object_.evaluation_id),
                    "model_artifact": object_.model_artifact_sha256,
                    "preprocessing": object_.preprocessing_identity,
                    "calibration_id": None if object_.calibration_id is None else str(object_.calibration_id),
                    "threshold_id": None if object_.threshold_id is None else str(object_.threshold_id),
                    "selective_policy_id": None if object_.selective_policy_id is None else str(object_.selective_policy_id),
                    "stability_gate_policy_id": None if object_.stability_gate_policy_id is None else str(object_.stability_gate_policy_id),
                })
                or object_.policy_frozen_at is None
                or object_.dataset_test_unlock_at is None
                or object_.policy_frozen_at > object_.dataset_test_unlock_at
                or (object_.threshold_id is not None and (threshold is None or threshold.evaluation_id != object_.evaluation_id or threshold.run_id != object_.run_id or threshold.selected_threshold != object_.decision_threshold))
                or (object_.calibration_id is not None and (calibration is None or calibration.evaluation_id != object_.evaluation_id or calibration.run_id != object_.run_id))
                or (object_.selective_policy_id is not None and (selective is None or selective.evaluation_id != object_.evaluation_id or selective.run_id != object_.run_id or selective.class_threshold_id != object_.threshold_id))
                or (object_.stability_gate_policy_id is not None and (not isinstance(gate, StabilityGatePolicy) or gate.evaluation_id != object_.evaluation_id or gate.selected_run_id != object_.run_id or gate.class_threshold_id != object_.threshold_id))
                or any(item is None for item in stability_runs)
                or not _final_test_freeze_timestamps_match(object_, run, evaluation, threshold, calibration, selective, gate, analysis, stability_runs)
                or not _final_test_metrics_match(object_, threshold, calibration)
                or not _final_test_stability_evidence_matches(object_, gate)
            ):
                errors.append(f"Final-test evaluation {object_.final_test_id} does not match its frozen model, policy, case identities, metrics, or Stability evidence.")
        elif isinstance(object_, AssuranceCase) and not _assurance_claim_graph_matches(object_):
            errors.append(f"AssuranceCase {object_.assurance_id} claims or unresolved risks do not match its declared evidence gates.")
    return errors


def validate_verification_bundle(path: Path | str) -> VerificationBundleValidation:
    """Fail-closed validation for a ZIP or freshly extracted evidence bundle."""
    source = Path(path)
    entries, bundle_sha, errors = _read_bundle_entries(source)
    warnings: list[str] = []
    manifest_sha: str | None = None
    manifest_raw = entries.get("verification-manifest.json")
    if manifest_raw is None:
        errors.append("Missing verification-manifest.json.")
        return VerificationBundleValidation(bundle_path=str(source), status="FAIL", bundle_sha256=bundle_sha, errors=errors)
    try:
        manifest = json.loads(manifest_raw)
        manifest_sha = _sha(manifest_raw)
    except json.JSONDecodeError:
        return VerificationBundleValidation(bundle_path=str(source), status="FAIL", bundle_sha256=bundle_sha, errors=[*errors, "verification-manifest.json is malformed JSON."])
    if manifest.get("schema_version") != 2 or manifest.get("inspection_first") is not True:
        errors.append("Unsupported or non-inspection-first verification manifest.")
    if manifest.get("excluded") != _EXCLUDED:
        errors.append("Verification manifest does not declare the frozen inspection-first exclusions.")
    checksum_file = entries.get("verification-manifest.sha256", b"").decode("utf-8", errors="replace").split()
    if not checksum_file or checksum_file[0] != manifest_sha:
        errors.append("verification-manifest.sha256 does not match the manifest.")
    checksums = manifest.get("checksums")
    if not isinstance(checksums, dict) or not checksums:
        errors.append("Manifest has no checksum inventory.")
        checksums = {}
    for name, expected in checksums.items():
        actual = entries.get(name)
        if actual is None: errors.append(f"Manifest entry is missing: {name}.")
        elif _sha(actual) != expected: errors.append(f"Checksum mismatch: {name}.")
    allowed_unmanifested = {"verification-manifest.json", "verification-manifest.sha256"}
    unlisted = set(entries) - set(checksums) - allowed_unmanifested
    if unlisted: errors.append("Bundle contains entries absent from the checksum inventory: " + ", ".join(sorted(unlisted)) + ".")
    for name in entries:
        if not _safe_name(name) or name.lower().endswith(_FORBIDDEN_SUFFIXES) or "node_modules" in Path(name).parts:
            errors.append(f"Bundle contains prohibited or unsafe entry: {name}.")
    objects: list[BaseModel] = []
    for name, raw in checksums.items():
        model = _model_for_entry(name)
        if model is None: continue
        try: objects.append(model.model_validate_json(entries[name]))
        except (ValidationError, ValueError, KeyError) as error: errors.append(f"Invalid {model.__name__} evidence at {name}: {error}.")
    errors.extend(_validate_relationships(objects))
    if any(isinstance(item, TreePathEvidence) for item in objects):
        warnings.append("TreePathEvidence run/hash/feature bindings were checked, but exact path replay is unavailable because model artifacts are excluded from the inspection-first bundle.")
    if any(isinstance(item, ExplanationReproducibilityAnalysis) for item in objects):
        warnings.append("ExplanationReproducibilityAnalysis run, explanation, and case bindings were checked; aggregate agreement values are not independently recomputed by the portable bundle validator.")
    if any(isinstance(item, ConditionMonitoringDemo) for item in objects):
        warnings.append("ConditionMonitoringDemo policy and decision arithmetic were checked, but model inference cannot be replayed because executable/model artifacts are excluded from the inspection-first bundle.")
    assurance_objects = {str(item.assurance_id): item for item in objects if isinstance(item, AssuranceCase)}
    if not assurance_objects:
        errors.append("No typed AssuranceCase object was found in the bundle.")
    else:
        summary_raw = entries.get("assurance-summary.json")
        try:
            summary = AssuranceCase.model_validate_json(summary_raw) if summary_raw is not None else None
            assurance_id = str(manifest.get("assurance_id"))
            if summary is None or str(summary.assurance_id) != assurance_id or assurance_objects.get(assurance_id) != summary:
                errors.append("assurance-summary.json does not match its manifest-bound persisted AssuranceCase.")
            elif entries.get("report.md") != (
                "# RuFLEX Verification Bundle\n\nInspection-first declarative evidence package. Independent AssuranceCase gates are not a trust score.\n\n"
                + "## Assurance gates\n\n"
                + "\n".join(f"- {gate.key}: {gate.status}" + (f" — {gate.risk}" if gate.risk else "") for gate in summary.gates)
                + "\n"
            ).encode():
                errors.append("report.md does not match the manifest-bound AssuranceCase gates.")
        except (ValidationError, ValueError) as error:
            errors.append(f"assurance-summary.json is malformed or invalid: {error}.")
    return VerificationBundleValidation(bundle_path=str(source), status="FAIL" if errors else "PASS", bundle_sha256=bundle_sha, manifest_sha256=manifest_sha, checked_entries=len(checksums), errors=errors, warnings=warnings)


def _declarative_paths(base: Path) -> list[Path]:
    result: list[Path] = []
    project = base / "project.yaml"
    if project.is_file(): result.append(project)
    for relative in ("data/dataset-contract.json", "data/dataset-profile.json", "data/dataset-audit.json"):
        path = base / relative
        if path.is_file(): result.append(path)
    split_root = base / "data" / "splits"
    if split_root.is_dir(): result.extend(path for path in sorted(split_root.glob("*.json")) if path.is_file())
    transform_root = base / "data" / "transforms"
    if transform_root.is_dir(): result.extend(path for path in sorted(transform_root.glob("*.json")) if path.is_file())
    leakage_root = base / "data" / "leakage-audits"
    if leakage_root.is_dir(): result.extend(path for path in sorted(leakage_root.glob("*.json")) if path.is_file())
    for directory in _EVIDENCE_DIRS:
        root = base / directory
        if not root.is_dir(): continue
        for path in sorted(root.glob("*.json")):
            if path.name not in _POINTERS and not path.name.startswith("result-") or path.name.startswith("result-"):
                result.append(path)
    for directory in _DECLARATIVE_MODEL_DIRS:
        root = base / directory
        if root.is_dir():
            result.extend(path for path in sorted(root.rglob("*.json")) if path.is_file())
    return result


def load_verification_bundle_record(root: Path, bundle_id: str) -> VerificationBundle:
    path = Path(root).resolve() / "evidence" / "verification-bundles" / f"{bundle_id}.json"
    return VerificationBundle.model_validate_json(path.read_text(encoding="utf-8"))


def export_verification_bundle(root: Path) -> dict:
    base = Path(root).resolve(); assurance = load_latest_assurance_case(base)
    contents: dict[str, bytes] = {}
    for path in _declarative_paths(base):
        name = path.relative_to(base).as_posix()
        if name.endswith((".pkl", ".pickle", ".joblib", ".pyc")) or "node_modules" in name:
            continue
        contents[name] = path.read_bytes()
    contents["lineage.json"] = build_project_lineage(base).model_dump_json(indent=2).encode()
    contents["assurance-summary.json"] = assurance.model_dump_json(indent=2).encode()
    report = "# RuFLEX Verification Bundle\n\nInspection-first declarative evidence package. Independent AssuranceCase gates are not a trust score.\n\n"
    report += "## Assurance gates\n\n" + "\n".join(f"- {gate.key}: {gate.status}" + (f" — {gate.risk}" if gate.risk else "") for gate in assurance.gates) + "\n"
    contents["report.md"] = report.encode()
    checksums = {name: _sha(data) for name, data in sorted(contents.items())}
    manifest = {"schema_version": 2, "inspection_first": True, "assurance_id": str(assurance.assurance_id), "checksums": checksums, "excluded": _EXCLUDED, "manifest_checksum_file": "verification-manifest.sha256"}
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode()
    contents["verification-manifest.json"] = manifest_bytes
    contents["verification-manifest.sha256"] = f"{_sha(manifest_bytes)}  verification-manifest.json\n".encode()
    out = base / "exports"; out.mkdir(parents=True, exist_ok=True)
    bundle = out / f"verification-bundle-{assurance.assurance_id}.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(contents.items()): archive.writestr(name, data)
    object_ = VerificationBundle(assurance_id=assurance.assurance_id, sha256=_sha(bundle.read_bytes()), entry_count=len(contents), manifest_sha256=_sha(manifest_bytes), excluded=_EXCLUDED)
    evidence_root = base / "evidence" / "verification-bundles"; evidence_root.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(evidence_root / f"{object_.bundle_id}.json", object_.model_dump_json(indent=2))
    _atomic_write_text(evidence_root / "active-bundle.json", json.dumps({"bundle_id": str(object_.bundle_id), "path": str(bundle)}))
    return {**object_.model_dump(mode="json"), "path": str(bundle)}
