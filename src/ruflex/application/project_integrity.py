"""Read-only integrity inspection for local-first RuFLEX project reopen."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ruflex.application.artifacts import ArtifactRecord, ArtifactRef, ArtifactStore
from ruflex.application.datasets import DatasetConfirmationError, DatasetContract, DatasetProfile, LeakageAuditReport, SplitContract, TransformPipelineContract, load_data_audit, load_dataset_contract, load_dataset_profile, load_leakage_audit, load_split_contract, load_transform_pipeline_contract, row_identity
from ruflex.application.fis import list_fis_revisions, load_fis
from ruflex.application.jobs import Job
from ruflex.application.projects import ProjectService
from ruflex.application.training import _select_study_run, _stable_identity, list_training_runs
from ruflex.application.behavior import _requirement_identity
from ruflex.domain.behavior import BehaviorRevisionComparison, BehaviorSpec, BehaviorSpecResult
from ruflex.domain.evidence import ExplanationCheck, ExplanationContract
from ruflex.domain.project import ProjectIntegrityIssue, ProjectIntegrityReport
from ruflex.domain.training import AnalysisEvaluation, CalibrationTransform, DecisionThresholdPolicy, FinalTestEvaluation, StudyJob, TrainingStudy
from ruflex.domain.selective import SelectivePredictionPolicy
from ruflex.domain.stability import StabilityGatePolicy, StudyStabilityAnalysis
from ruflex.runtime.registry import builtin_runtime_registry
from ruflex.runtime.compatibility import resolve_run_adapter
from ruflex.runtime.compatibility import LEGACY_MODEL_KIND_TO_ADAPTER


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
            verification = ArtifactStore(base).verify(ArtifactRef(sha256=contract.source_artifact_sha256)); checked += 1
            if not verification.valid: issues.append(ProjectIntegrityIssue(code="DATASET_ARTIFACT_INVALID", status="FAIL", path="data/dataset-contract.json", detail=verification.message))
        except (FileNotFoundError, ValidationError, ValueError) as error:
            issues.append(ProjectIntegrityIssue(code="DATASET_EVIDENCE_MALFORMED", status="FAIL", path="data", detail=str(error)))
    elif any((base / "data").glob("*.json")):
        issues.append(ProjectIntegrityIssue(code="DATASET_EVIDENCE_INCOMPLETE", status="FAIL", path="data", detail="Dataset evidence exists but the canonical DatasetContract is missing."))
    split_root = base / "data" / "splits"
    if split_root.exists() and not split_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="SPLIT_CONTRACT_EVIDENCE_MALFORMED", status="FAIL", path="data/splits", detail="Split-contract evidence path is not a directory."))
    elif split_root.is_dir():
        for path in sorted(split_root.glob("*.json")):
            checked += 1
            try:
                split = SplitContract.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(split.split_id): raise ValueError("SplitContract filename does not match its persisted identity.")
                load_split_contract(base, split.split_id)
            except (FileNotFoundError, ValidationError, ValueError, DatasetConfirmationError, OSError) as error:
                issues.append(ProjectIntegrityIssue(code="SPLIT_CONTRACT_EVIDENCE_MALFORMED", status="FAIL", path=str(path.relative_to(base)), detail=str(error)))
    transform_root = base / "data" / "transforms"
    if transform_root.exists() and not transform_root.is_dir():
        issues.append(ProjectIntegrityIssue(code="TRANSFORM_PIPELINE_EVIDENCE_MALFORMED", status="FAIL", path="data/transforms", detail="Transform-pipeline evidence path is not a directory."))
    elif transform_root.is_dir():
        for path in sorted(transform_root.glob("*.json")):
            checked += 1
            try:
                pipeline = TransformPipelineContract.model_validate_json(path.read_text(encoding="utf-8"))
                if path.stem != str(pipeline.pipeline_id): raise ValueError("TransformPipelineContract filename does not match its persisted identity.")
                load_transform_pipeline_contract(base, pipeline.pipeline_id)
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
            except (FileNotFoundError, ValidationError, ValueError, DatasetConfirmationError, OSError) as error:
                issues.append(ProjectIntegrityIssue(code="LEAKAGE_AUDIT_EVIDENCE_MALFORMED", status="FAIL", path=str(path.relative_to(base)), detail=str(error)))
    try:
        runs = list_training_runs(base); checked += len(runs)
    except (ValidationError, ValueError, FileNotFoundError) as error:
        runs = []
        issues.append(ProjectIntegrityIssue(code="TRAINING_EVIDENCE_MALFORMED", status="FAIL", path="runs", detail=str(error)))
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
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["evaluation_id"]
                if str(active_id) not in {str(key) for key in evaluations}:
                    raise ValueError("Active validation Evaluation pointer does not resolve to persisted evidence.")
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
            except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="CALIBRATION_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
        active_path = calibration_root / "active-calibration.json"
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["calibration_id"]
                if str(active_id) not in {str(key) for key in calibrations}:
                    raise ValueError("Active calibration pointer does not resolve to persisted evidence.")
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
                ):
                    issues.append(ProjectIntegrityIssue(code="DECISION_THRESHOLD_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="Decision threshold does not match its exact validation Evaluation, calibration, probability source, or case support."))
            except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="DECISION_THRESHOLD_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
        active_path = threshold_root / "active-threshold.json"
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["threshold_id"]
                if str(active_id) not in {str(key) for key in thresholds}:
                    raise ValueError("Active decision-threshold pointer does not resolve to persisted evidence.")
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
                ):
                    issues.append(ProjectIntegrityIssue(code="SELECTIVE_POLICY_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="Selective policy does not match its exact validation Evaluation, threshold, or calibration binding."))
            except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="SELECTIVE_POLICY_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
        active_path = selective_root / "active-policy.json"
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["policy_id"]
                if str(active_id) not in {str(key) for key in selective_policies}:
                    raise ValueError("Active selective-policy pointer does not resolve to persisted evidence.")
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
        if active_study_path.exists():
            checked += 1
            try:
                active_study_id = json.loads(active_study_path.read_text(encoding="utf-8"))["study_id"]
                if str(active_study_id) not in {str(key) for key in studies_by_id}:
                    raise ValueError("Active TrainingStudy pointer does not resolve to persisted evidence.")
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
                    threshold = thresholds.get(analysis.class_threshold_id) if analysis.class_threshold_id else None
                    if (
                        study is None
                        or not study_run_ids
                        or set(analysis.run_ids) != study_run_ids
                        or analysis.selected_run_id != study.selected_run_id
                        or analysis.model_kind != study.model_kind
                        or any(run.dataset_fingerprint != analysis.dataset_fingerprint for run in study.seed_runs)
                        or (analysis.evaluation_id is not None and (analysis.evaluation_id not in evaluations or evaluations[analysis.evaluation_id].run_id != analysis.selected_run_id))
                        or (analysis.class_threshold_id is not None and (threshold is None or threshold.evaluation_id != analysis.evaluation_id or threshold.run_id != analysis.selected_run_id or threshold.selected_threshold != analysis.decision_threshold))
                    ):
                        issues.append(ProjectIntegrityIssue(code="STABILITY_ANALYSIS_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="Stability Analysis does not resolve to its exact TrainingStudy, run set, selected Evaluation, or validation threshold."))
                except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                    issues.append(ProjectIntegrityIssue(code="STABILITY_ANALYSIS_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
            active_path = stability_root / "active-analysis.json"
            if active_path.exists():
                checked += 1
                try:
                    active_id = json.loads(active_path.read_text(encoding="utf-8"))["analysis_id"]
                    if str(active_id) not in {str(key) for key in stability_analyses}:
                        raise ValueError("Active Stability Analysis pointer does not resolve to persisted evidence.")
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
                        or {item.case_id for item in policy.decisions} != {item.case_id for item in analysis.cases}
                    ):
                        issues.append(ProjectIntegrityIssue(code="STABILITY_GATE_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="Stability Gate does not match its frozen Analysis, selected validation Evaluation, raw threshold, run support, or case evidence."))
                except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                    issues.append(ProjectIntegrityIssue(code="STABILITY_GATE_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
            active_path = stability_policy_root / "active-policy.json"
            if active_path.exists():
                checked += 1
                try:
                    active_id = json.loads(active_path.read_text(encoding="utf-8"))["policy_id"]
                    if str(active_id) not in {str(key) for key in stability_policies}:
                        raise ValueError("Active Stability Gate pointer does not resolve to persisted evidence.")
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
                    source_rows = [int(row.source_row) for row in final_test.prediction_rows if row.source_row is not None]
                    row_identities = [row.row_identity or row_identity(final_test.dataset_fingerprint, int(row.source_row)) for row in final_test.prediction_rows if row.source_row is not None]
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
                        or (final_test.policy_frozen_at is not None and final_test.dataset_test_unlock_at is not None and final_test.policy_frozen_at > final_test.dataset_test_unlock_at)
                        or (evaluation is not None and final_test.dataset_test_unlock_at is not None and evaluation.created_at > final_test.dataset_test_unlock_at)
                        or (threshold is not None and final_test.dataset_test_unlock_at is not None and threshold.created_at > final_test.dataset_test_unlock_at)
                        or (calibration is not None and final_test.dataset_test_unlock_at is not None and calibration.created_at > final_test.dataset_test_unlock_at)
                        or (selective_policy is not None and final_test.dataset_test_unlock_at is not None and selective_policy.created_at > final_test.dataset_test_unlock_at)
                        or (stability_policy is not None and final_test.dataset_test_unlock_at is not None and stability_policy.frozen_at > final_test.dataset_test_unlock_at)
                        or (final_test.threshold_id is not None and (threshold is None or threshold.evaluation_id != final_test.evaluation_id or threshold.run_id != final_test.run_id or threshold.selected_threshold != final_test.decision_threshold or threshold.probability_source != final_test.probability_source))
                        or (final_test.calibration_id is not None and (calibration is None or calibration.evaluation_id != final_test.evaluation_id or calibration.run_id != final_test.run_id))
                        or (final_test.selective_policy_id is not None and (selective_policy is None or selective_policy.evaluation_id != final_test.evaluation_id or selective_policy.run_id != final_test.run_id or selective_policy.class_threshold_id != final_test.threshold_id))
                        or (final_test.stability_gate_policy_id is not None and (stability_policy is None or stability_policy.evaluation_id != final_test.evaluation_id or stability_policy.selected_run_id != final_test.run_id or stability_policy.class_threshold_id != final_test.threshold_id))
                    ):
                        issues.append(ProjectIntegrityIssue(code="FINAL_TEST_PROVENANCE_MISMATCH", status="FAIL", path=relative_path, detail="FinalTestEvaluation does not match its frozen validation Evaluation, model, dataset, threshold, calibration, or selective/stability policy bindings."))
                except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
                    issues.append(ProjectIntegrityIssue(code="FINAL_TEST_EVIDENCE_MALFORMED", status="FAIL", path=relative_path, detail=str(error)))
            active_path = final_test_root / "active-final-test.json"
            if active_path.exists():
                checked += 1
                try:
                    active_id = json.loads(active_path.read_text(encoding="utf-8"))["final_test_id"]
                    if str(active_id) not in {str(key) for key in final_tests}:
                        raise ValueError("Active FinalTestEvaluation pointer does not resolve to persisted evidence.")
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
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["explanation_id"]
                if str(active_id) not in {str(key) for key in explanations}:
                    raise ValueError("Active explanation pointer does not resolve to a persisted explanation.")
            except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="EXPLANATION_ACTIVE_POINTER_INVALID", status="FAIL", path="evidence/explanations/active-explanation.json", detail=str(error)))
    check_root = base / "evidence" / "explanation-checks"
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
                explanation = explanations.get(check.explanation_id)
                if explanation is None:
                    issues.append(ProjectIntegrityIssue(code="EXPLANATION_CHECK_EXPLANATION_MISSING", status="FAIL", path=relative_path, detail="Explanation check references an explanation that is not present."))
                elif check.run_id != explanation.run_id:
                    issues.append(ProjectIntegrityIssue(code="EXPLANATION_CHECK_RUN_MISMATCH", status="FAIL", path=relative_path, detail="Explanation check run identity does not match its explanation."))
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
        if active_path.exists():
            checked += 1
            try:
                active_id = json.loads(active_path.read_text(encoding="utf-8"))["check_id"]
                if str(active_id) not in {str(key) for key in check_ids}:
                    raise ValueError("Active explanation-check pointer does not resolve to persisted evidence.")
            except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
                issues.append(ProjectIntegrityIssue(code="EXPLANATION_CHECK_ACTIVE_POINTER_INVALID", status="FAIL", path="evidence/explanation-checks/active-check.json", detail=str(error)))
    try:
        jobs_root = base / "jobs"
        if jobs_root.exists() and not jobs_root.is_dir():
            raise ValueError("Persisted jobs path is not a directory.")
        jobs = [Job.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(jobs_root.glob("*.json"))] if jobs_root.is_dir() else []
        checked += len(jobs)
        for job in jobs:
            if job.schema_version < 2:
                continue
            relative_path = f"jobs/{job.job_id}.json"
            if not all((job.execution_backend_key, job.execution_backend_version, job.execution_backend_provider)):
                issues.append(ProjectIntegrityIssue(code="JOB_BACKEND_RUNTIME_BINDING_MISSING", status="FAIL", path=relative_path, detail="A schema-v2 job is missing execution backend runtime provenance."))
                continue
            try:
                descriptor = builtin_runtime_registry().resolve_component("execution_backend", job.execution_backend_key, version=job.execution_backend_version)
                if descriptor.identity.provider != job.execution_backend_provider:
                    issues.append(ProjectIntegrityIssue(code="JOB_BACKEND_RUNTIME_PROVIDER_MISMATCH", status="FAIL", path=relative_path, detail="Job backend provider does not match the active frozen descriptor."))
            except Exception:
                issues.append(ProjectIntegrityIssue(code="JOB_BACKEND_RUNTIME_UNAVAILABLE", status="WARN", path=relative_path, detail="Persisted execution backend is unavailable locally; job remains inspectable."))
    except (ValidationError, ValueError, FileNotFoundError) as error:
        issues.append(ProjectIntegrityIssue(code="JOB_EVIDENCE_MALFORMED", status="FAIL", path="jobs", detail=str(error)))
    status = "FAIL" if any(issue.status == "FAIL" for issue in issues) else "WARN" if any(issue.status == "WARN" for issue in issues) else "PASS"
    return ProjectIntegrityReport(project_id=project.id, status=status, checked_objects=checked, issues=issues)
