"""Read-only integrity inspection for local-first RuFLEX project reopen."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ruflex.application.artifacts import ArtifactRecord, ArtifactRef, ArtifactStore
from ruflex.application.datasets import DatasetConfirmationError, DatasetContract, DatasetProfile, SplitContract, load_data_audit, load_dataset_contract, load_dataset_profile, load_split_contract
from ruflex.application.fis import list_fis_revisions, load_fis
from ruflex.application.jobs import Job
from ruflex.application.projects import ProjectService
from ruflex.application.training import list_training_runs
from ruflex.domain.evidence import ExplanationCheck, ExplanationContract
from ruflex.domain.project import ProjectIntegrityIssue, ProjectIntegrityReport
from ruflex.runtime.registry import builtin_runtime_registry


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
    for run in runs:
        if run.schema_version >= 3:
            if not all((run.adapter_key, run.adapter_version, run.adapter_provider, run.adapter_kind, run.runtime_capability_snapshot_hash)):
                issues.append(ProjectIntegrityIssue(code="RUNTIME_BINDING_MISSING", status="FAIL", path=f"runs/{run.run_id}.json", detail="A schema-v3 TrainingRun is missing its required runtime adapter binding."))
            else:
                try:
                    builtin_runtime_registry().resolve_model_adapter(run.adapter_key, version=run.adapter_version)
                except Exception:
                    issues.append(ProjectIntegrityIssue(code="RUNTIME_UNAVAILABLE", status="WARN", path=f"runs/{run.run_id}.json", detail="The persisted adapter is unavailable locally; the run remains inspectable but replay is unavailable."))
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
        if run.preprocessing_artifact_sha256 is not None:
            verification = store.verify(ArtifactRef(sha256=run.preprocessing_artifact_sha256)); checked += 1
            if not verification.valid:
                issues.append(ProjectIntegrityIssue(code="PREPROCESSING_ARTIFACT_INVALID", status="FAIL", path=f"runs/{run.run_id}.json", detail=verification.message))
            else:
                try:
                    with store.open(ArtifactRef(sha256=run.preprocessing_artifact_sha256)) as handle:
                        preprocessing = json.loads(handle.read().decode("utf-8"))
                    if preprocessing.get("format") != "ruflex.preprocessing/v1" or preprocessing.get("fit_scope") != "train_only" or preprocessing.get("normalization") != run.normalization or preprocessing.get("feature_columns") != run.feature_columns or preprocessing.get("missing_value_policy") != "median" or set(preprocessing.get("imputation_values", {})) != set(run.feature_columns):
                        issues.append(ProjectIntegrityIssue(code="PREPROCESSING_PROVENANCE_MISMATCH", status="FAIL", path=f"runs/{run.run_id}.json", detail="Persisted preprocessing artifact does not match the TrainingRun's train-only normalization and feature schema."))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                    issues.append(ProjectIntegrityIssue(code="PREPROCESSING_ARTIFACT_MALFORMED", status="FAIL", path=f"runs/{run.run_id}.json", detail=str(error)))
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
    status = "FAIL" if any(issue.status == "FAIL" for issue in issues) else "WARN" if issues else "PASS"
    return ProjectIntegrityReport(project_id=project.id, status=status, checked_objects=checked, issues=issues)
