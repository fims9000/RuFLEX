"""Read-only integrity inspection for local-first RuFLEX project reopen."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ruflex.application.artifacts import ArtifactRecord, ArtifactRef, ArtifactStore
from ruflex.application.datasets import DatasetContract, DatasetProfile, load_data_audit, load_dataset_contract, load_dataset_profile
from ruflex.application.projects import ProjectService
from ruflex.application.training import list_training_runs
from ruflex.domain.project import ProjectIntegrityIssue, ProjectIntegrityReport


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
    try:
        runs = list_training_runs(base); checked += len(runs)
    except (ValidationError, ValueError, FileNotFoundError) as error:
        runs = []
        issues.append(ProjectIntegrityIssue(code="TRAINING_EVIDENCE_MALFORMED", status="FAIL", path="runs", detail=str(error)))
    store = ArtifactStore(base)
    for run in runs:
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
    status = "FAIL" if any(issue.status == "FAIL" for issue in issues) else "WARN" if issues else "PASS"
    return ProjectIntegrityReport(project_id=project.id, status=status, checked_objects=checked, issues=issues)
