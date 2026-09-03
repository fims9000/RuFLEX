from __future__ import annotations

from pathlib import Path
from io import BytesIO, StringIO
import base64
import zipfile
import hashlib
import numpy as np
import pandas as pd
import yaml

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from uuid import UUID
from typing import Any, Literal

from ruflex.application.projects import ProjectError, ProjectReadOnlyError, ProjectService
from ruflex.application.artifacts import ArtifactMetadata, ArtifactRecord, ArtifactRef, ArtifactStore
from ruflex.application.datasets import DataAuditReport, DatasetContract, DatasetProfile, build_dataset_contract, inspect_dataset, load_data_audit, load_dataset_contract, load_dataset_frame, load_dataset_profile, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.generalization import ContractFreezeError, ContractLintReport, GeneralizationContract, GeneralizationContractError, NoveltyAxis, ScopeClassification, ScopeRule, SliceAnalysis, SliceDefinition, classify_scope, create_generalization_contract, create_slice_analysis, freeze_generalization_contract, lint_generalization_contract, load_generalization_contract, load_latest_slice_analysis, persist_generalization_contract, recommend_split_families
from ruflex.application.fis import FISError, create_default_fis, diagnose_fis, evaluate_fis, evaluate_response_surface, list_fis_revisions, load_fis, load_latest_trace, persist_fis, save_trace_artifact
from ruflex.application.fis_interop import export_matlab_fis, persist_imported_matlab_fis
from ruflex.application.model_catalog import list_model_catalog
from ruflex.domain.training import AnalysisComparison, AnalysisEvaluation, FinalTestEvaluation, CalibrationTransform, DecisionThresholdPolicy, StudyJob, TrainingRun, TrainingStudy, TreePathEvidence
from ruflex.application.jobs import Job
from ruflex.domain.evidence import ExplanationCheck, ExplanationContract
from ruflex.domain.evidence import ExplanationReproducibilityAnalysis
from ruflex.domain.behavior import BehaviorSpec, BehaviorSpecResult
from ruflex.domain.selective import SelectiveDecision, SelectivePredictionPolicy
from ruflex.domain.stability import StabilityGateApplication, StabilityGatePolicy, StudyStabilityAnalysis
from ruflex.domain.demo import ConditionMonitoringDemo
from ruflex.domain.exhaustive import ExhaustiveLabResult
from ruflex.domain.assurance import AssuranceCase
from ruflex.domain.verification import VerificationBundleValidation
from ruflex.domain.expert_correction import ExpertCorrectionResult, ExpertCorrectionRevision
from ruflex.domain.fis import FISEvaluation, FISSpec, ResponseSurface
from ruflex.application.workspace_sessions import WorkspaceSession, WorkspaceSessionError, WorkspaceSessionService
from ruflex.domain.project import ProjectIntegrityReport, ProjectSummary
from ruflex.domain.lineage import LineageGraph
from ruflex.application.lineage import build_project_lineage


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class OpenProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    read_only: bool = False


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID


class ValidateVerificationBundleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)


class UpdateProjectMetadataRequest(SessionRequest):
    description: str | None = Field(default=None, max_length=4000)


class IngestTextArtifactRequest(SessionRequest):
    text: str = Field(max_length=1_000_000)
    media_type: str = "text/plain"
    original_name: str | None = Field(default=None, max_length=255)


class InspectCsvRequest(SessionRequest):
    csv_text: str = Field(min_length=1, max_length=2_000_000)


class ConfirmDatasetRequest(SessionRequest):
    csv_text: str = Field(min_length=1, max_length=2_000_000)
    target: str = Field(min_length=1)
    task: str
    id_columns: list[str] = Field(default_factory=list)


class ImportDatasetRequest(SessionRequest):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1, max_length=8_000_000)
    target: str = Field(min_length=1)
    task: str
    id_columns: list[str] = Field(default_factory=list)


class DatasetInspection(BaseModel):
    profile: DatasetProfile


class DatasetConfirmation(BaseModel):
    contract: DatasetContract
    audit: DataAuditReport


class CreateGeneralizationContractRequest(SessionRequest):
    intended_use: str = Field(min_length=1)
    novelty_axes: list[NoveltyAxis] = Field(min_length=1)
    supported_scope: list[ScopeRule] = Field(default_factory=list)
    forbidden_scope: list[ScopeRule] = Field(default_factory=list)
    required_subgroups: list[ScopeRule] = Field(default_factory=list)
    unsupported_action: str = "BLOCK"


class ClassifyGeneralizationScopeRequest(SessionRequest):
    sample_metadata: dict[str, Any]


class GeneralizationContractResponse(BaseModel):
    contract: GeneralizationContract
    lint: ContractLintReport
    recommendations: list


class DatasetState(BaseModel):
    profile: DatasetProfile
    contract: DatasetContract
    audit: DataAuditReport
    preview: list[dict]


def _inspect_zip_workbook(raw: bytes) -> None:
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > 1_000:
                raise ValueError("XLSX has too many archive entries.")
            expanded = sum(item.file_size for item in entries)
            if expanded > 50_000_000:
                raise ValueError("XLSX expanded size exceeds the Product V1 import limit.")
            for item in entries:
                if item.filename.startswith("/") or ".." in Path(item.filename).parts:
                    raise ValueError("XLSX contains an unsafe archive path.")
                if item.compress_size and item.file_size / item.compress_size > 100:
                    raise ValueError("XLSX contains a suspicious compression ratio.")
    except zipfile.BadZipFile as error:
        raise ValueError("XLSX is not a valid ZIP workbook.") from error


class CreateFISRequest(SessionRequest):
    name: str = Field(default="Risk FIS", min_length=1, max_length=200)
    input_columns: list[str] | None = None


class SaveFISRequest(SessionRequest):
    spec: FISSpec


class ImportMatlabFISRequest(SessionRequest):
    source: str = Field(min_length=1, max_length=5_000_000)


class EvaluateFISRequest(SessionRequest):
    inputs: dict[str, float]
    persist_trace: bool = True


class ExpertCorrectionRequest(SessionRequest):
    locked_rule_ids: list[UUID] = Field(default_factory=list)
    seed: int = 42
    validation_fraction: float = Field(default=0.2, gt=0.0, lt=1.0)
    test_fraction: float = Field(default=0.2, ge=0.0, lt=1.0)
    source_explanation_id: UUID | None = None


class FISEvaluationResponse(BaseModel):
    evaluation: FISEvaluation
    trace_artifact_sha256: str | None = None


class ResponseSurfaceRequest(SessionRequest):
    spec: FISSpec
    x_variable: str = Field(min_length=1)
    y_variable: str = Field(min_length=1)
    fixed_inputs: dict[str, float] = Field(default_factory=dict)
    resolution: int = Field(default=31, ge=2, le=101)


class TrainModelRequest(SessionRequest):
    model_kind: Literal["flat_neuro_fuzzy", "logistic_regression", "linear_regression", "decision_tree", "random_forest", "gradient_boosting"] = "flat_neuro_fuzzy"
    seed: int = 42
    split_seed: int | None = None
    training_seed: int | None = None
    max_epochs: int = Field(default=20, ge=1, le=2000)
    learning_rate: float = Field(default=0.01, gt=0.0, le=1.0)
    batch_size: int = Field(default=32, ge=1, le=100000)
    patience: int | None = Field(default=8, ge=1, le=2000)
    validation_fraction: float = Field(default=0.2, gt=0.0, lt=1.0)
    test_fraction: float = Field(default=0.2, ge=0.0, lt=1.0)
    max_rules: int = Field(default=8, ge=1, le=128)


class MultiSeedStudyRequest(TrainModelRequest):
    name: str = Field(default="Multi-seed study", min_length=1, max_length=200)
    seeds: list[int] = Field(min_length=3, max_length=32)
    selection_metric: str = Field(default="f1")
    randomness_protocol: Literal["LEGACY_COMBINED", "TRAINING_VARIABILITY", "SPLIT_VARIABILITY", "COMBINED_VARIABILITY"] = "LEGACY_COMBINED"


class CreateAnalysisEvaluationRequest(SessionRequest):
    run_id: UUID


class CreateAnalysisComparisonRequest(SessionRequest):
    run_ids: list[UUID] = Field(min_length=1)
    include_active_fis: bool = False


class FitAnalysisCalibrationRequest(SessionRequest):
    evaluation_id: UUID


class SelectAnalysisThresholdRequest(SessionRequest):
    evaluation_id: UUID
    calibration_id: UUID | None = None
    objective: Literal["f1"] = "f1"


class CreateSelectivePolicyRequest(SessionRequest):
    evaluation_id: UUID
    confidence_cutoff: float = Field(ge=0.5, le=1.0)
    calibration_id: UUID | None = None
    threshold_id: UUID | None = None


class CreateStudyStabilityAnalysisRequest(SessionRequest):
    study_id: UUID
    evaluation_id: UUID | None = None
    threshold_id: UUID | None = None
    high_confidence_threshold: float = Field(default=0.9, ge=0.5, le=1.0)
    unstable_agreement_threshold: float = Field(default=0.8, gt=0.0, le=1.0)


class CreateStabilityGatePolicyRequest(SessionRequest):
    analysis_id: UUID
    evaluation_id: UUID
    calibration_id: UUID | None = None
    min_confidence: float = Field(default=0.9, ge=0.5, le=1.0)
    min_class_agreement: float = Field(default=0.8, gt=0.0, le=1.0)
    max_probability_std: float = Field(default=0.15, ge=0.0)


class ApplyStabilityGatePolicyRequest(SessionRequest):
    policy_id: UUID
    sample: dict[str, float] = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)
    generalization_contract_id: UUID | None = None


class ApplySelectivePolicyRequest(SessionRequest):
    policy_id: UUID
    sample: dict[str, float] = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)
    generalization_contract_id: UUID | None = None

class RunConditionMonitoringDemoRequest(SessionRequest):
    telemetry: dict[str, float] = Field(min_length=1)
    policy_id: UUID | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    generalization_contract_id: UUID | None = None


class EvaluateFinalTestRequest(SessionRequest):
    evaluation_id: UUID
    calibration_id: UUID | None = None
    threshold_id: UUID | None = None
    selective_policy_id: UUID | None = None
    stability_gate_policy_id: UUID | None = None


class TreePathTraceRequest(SessionRequest):
    run_id: UUID
    sample: dict[str, float] = Field(min_length=1)


class CreateOcclusionExplanationRequest(SessionRequest):
    run_id: UUID
    sample: dict[str, float] = Field(min_length=1)


class CreatePosthocExplanationRequest(SessionRequest):
    run_id: UUID
    sample: dict[str, float] = Field(min_length=1)
    method: Literal["occlusion", "integrated_gradients", "gradient_shap", "shap", "tree_shap"] = "occlusion"


class CheckExplanationRequest(SessionRequest):
    explanation_id: UUID


class CreateExplanationReproducibilityRequest(SessionRequest):
    explanation_ids: list[UUID] = Field(min_length=4, max_length=256)

class RunExhaustiveLabRequest(SessionRequest):
    kind: Literal["decision_tree_structure", "fis_discrete_grid"]
    run_id: UUID | None = None
    grid_points: int = Field(default=3, ge=2, le=9)
    max_states: int = Field(default=10_000, ge=1, le=1_000_000)


class CreateBehaviorSpecRequest(SessionRequest):
    run_id: UUID | None = None
    fis_id: UUID | None = None
    fis_semantic_hash: str | None = None
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["output_range", "monotonic_pair", "invariance_pair", "regression_case"]
    sample: dict[str, float] = Field(min_length=1)
    comparison_sample: dict[str, float] | None = None
    minimum: float | None = None
    maximum: float | None = None
    expected_direction: Literal["nondecreasing", "nonincreasing"] | None = None
    tolerance: float = Field(default=1e-9, ge=0.0)
    rationale: str = Field(min_length=1, max_length=2000)


class RunBehaviorSpecRequest(SessionRequest):
    spec_id: UUID


class CreateSliceAnalysisRequest(SessionRequest):
    evaluation_id: UUID
    metric: str | None = None
    definitions: list[SliceDefinition] = Field(min_length=1)


app = FastAPI(title="RuFLEX Studio API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
project_service = ProjectService()
service = WorkspaceSessionService(project_service)


class ProjectSessionSummary(ProjectSummary):
    session_id: UUID


def _project_error(error: ProjectError) -> HTTPException:
    if isinstance(error, WorkspaceSessionError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, ProjectReadOnlyError):
        return HTTPException(status_code=403, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


def _session_summary(session: WorkspaceSession) -> ProjectSessionSummary:
    return ProjectSessionSummary(**session.project.summary().model_dump(), session_id=session.session_id)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ruflex-studio"}


@app.get("/api/model-catalog")
def get_model_catalog() -> list[dict]:
    return list_model_catalog()


@app.post("/api/projects", response_model=ProjectSessionSummary, status_code=201)
def create_project(request: CreateProjectRequest) -> ProjectSessionSummary:
    try:
        return _session_summary(service.create(Path(request.path), name=request.name, description=request.description))
    except ProjectError as error:
        raise _project_error(error) from error


@app.post("/api/projects/open", response_model=ProjectSessionSummary)
def open_project(request: OpenProjectRequest) -> ProjectSessionSummary:
    try:
        return _session_summary(service.open(Path(request.path), read_only=request.read_only))
    except ProjectError as error:
        raise _project_error(error) from error


@app.post("/api/projects/save", response_model=ProjectSessionSummary)
def save_project(request: SessionRequest) -> ProjectSessionSummary:
    try:
        return _session_summary(service.save(request.session_id))
    except ProjectError as error:
        raise _project_error(error) from error


@app.post("/api/projects/metadata", response_model=ProjectSessionSummary)
def update_project_metadata(request: UpdateProjectMetadataRequest) -> ProjectSessionSummary:
    try:
        return _session_summary(service.update_metadata(request.session_id, description=request.description))
    except ProjectError as error:
        raise _project_error(error) from error


@app.post("/api/projects/close", status_code=204)
def close_project(request: SessionRequest) -> None:
    try:
        service.close(request.session_id)
    except ProjectError as error:
        raise _project_error(error) from error


@app.get("/api/projects/{session_id}/artifacts", response_model=list[ArtifactRecord])
def list_artifacts(session_id: UUID) -> list[ArtifactRecord]:
    try:
        return ArtifactStore(service.get(session_id).project.root).list_records()
    except ProjectError as error:
        raise _project_error(error) from error


@app.get("/api/projects/{session_id}/lineage", response_model=LineageGraph)
def get_project_lineage(session_id: UUID) -> LineageGraph:
    try:
        return build_project_lineage(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error


@app.get("/api/projects/{session_id}/integrity", response_model=ProjectIntegrityReport)
def get_project_integrity(session_id: UUID) -> ProjectIntegrityReport:
    from ruflex.application.project_integrity import inspect_project_integrity
    try:
        return inspect_project_integrity(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error


@app.post("/api/projects/artifacts/text", response_model=ArtifactRef, status_code=201)
def ingest_text_artifact(request: IngestTextArtifactRequest) -> ArtifactRef:
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot receive an artifact.")
        return ArtifactStore(session.project.root).ingest_bytes(
            request.text.encode("utf-8"),
            metadata=ArtifactMetadata(media_type=request.media_type, original_name=request.original_name, source_kind="generated"),
        )
    except ProjectError as error:
        raise _project_error(error) from error


@app.post("/api/projects/dataset/inspect", response_model=DatasetInspection)
def inspect_csv_dataset(request: InspectCsvRequest) -> DatasetInspection:
    try:
        service.get(request.session_id)
        digest = hashlib.sha256(request.csv_text.encode("utf-8")).hexdigest()
        return DatasetInspection(profile=inspect_dataset(pd.read_csv(StringIO(request.csv_text)), source_artifact_sha256=digest))
    except (ProjectError, ValueError, pd.errors.ParserError) as error:
        raise _project_error(error) if isinstance(error, ProjectError) else HTTPException(status_code=422, detail=f"CSV inspection failed: {error}")


@app.post("/api/projects/dataset/confirm", response_model=DatasetConfirmation)
def confirm_csv_dataset(request: ConfirmDatasetRequest) -> DatasetConfirmation:
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot receive a dataset contract.")
        raw = request.csv_text.encode("utf-8")
        frame = pd.read_csv(StringIO(request.csv_text))
        reference = persist_dataset_bytes(session.project.root, raw, original_name="studio-dataset.csv")
        profile = inspect_dataset(frame, source_artifact_sha256=reference.sha256)
        contract = build_dataset_contract(profile, target=request.target, task=request.task, id_columns=request.id_columns)
        audit = run_data_audit(contract, frame)
        persist_dataset_contract(session.project.root, contract, audit, profile)
        return DatasetConfirmation(contract=contract, audit=audit)
    except (ProjectError, ValueError, pd.errors.ParserError) as error:
        raise _project_error(error) if isinstance(error, ProjectError) else HTTPException(status_code=422, detail=f"Dataset confirmation failed: {error}")


@app.post("/api/projects/dataset/import", response_model=DatasetConfirmation)
def import_dataset(request: ImportDatasetRequest) -> DatasetConfirmation:
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot receive a dataset contract.")
        try:
            raw = base64.b64decode(request.content_base64, validate=True)
        except ValueError as error:
            raise ValueError("Dataset upload is not valid base64.") from error
        if len(raw) > 5_000_000:
            raise ValueError("Dataset upload exceeds the 5 MB Product V1 import limit.")
        suffix = Path(request.filename).suffix.lower()
        if suffix == ".csv":
            if raw.startswith(b"PK\x03\x04"):
                raise ValueError("Dataset extension/content mismatch: CSV upload is a ZIP-based file.")
            frame = pd.read_csv(BytesIO(raw))
            source_format, media_type = "csv", "text/csv"
        elif suffix == ".xlsx":
            if not raw.startswith(b"PK\x03\x04"):
                raise ValueError("Dataset extension/content mismatch: XLSX must be a ZIP-based workbook.")
            _inspect_zip_workbook(raw)
            frame = pd.read_excel(BytesIO(raw))
            source_format, media_type = "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            raise ValueError("Product V1 dataset import accepts only .csv and .xlsx files.")
        reference = persist_dataset_bytes(session.project.root, raw, original_name=Path(request.filename).name, media_type=media_type)
        profile = inspect_dataset(frame, source_artifact_sha256=reference.sha256)
        contract = build_dataset_contract(profile, target=request.target, task=request.task, id_columns=request.id_columns, source_format=source_format)
        audit = run_data_audit(contract, frame)
        persist_dataset_contract(session.project.root, contract, audit, profile)
        return DatasetConfirmation(contract=contract, audit=audit)
    except (ProjectError, ValueError, pd.errors.ParserError) as error:
        raise _project_error(error) if isinstance(error, ProjectError) else HTTPException(status_code=422, detail=f"Dataset import failed: {error}")


@app.get("/api/projects/{session_id}/dataset", response_model=DatasetState)
def get_dataset_state(session_id: UUID) -> DatasetState:
    try:
        session = service.get(session_id)
        frame = load_dataset_frame(session.project.root)
        preview = frame.head(50).where(pd.notna(frame.head(50)), None).to_dict(orient="records")
        return DatasetState(
            profile=load_dataset_profile(session.project.root),
            contract=load_dataset_contract(session.project.root),
            audit=load_data_audit(session.project.root),
            preview=preview,
        )
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No confirmed dataset is stored in this project.") from error
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=f"Stored dataset could not be loaded: {error}") from error


@app.get("/api/projects/{session_id}/dataset/features/{feature_name}/range")
def get_dataset_feature_range(session_id: UUID, feature_name: str) -> dict[str, float]:
    try:
        session = service.get(session_id)
        contract = load_dataset_contract(session.project.root)
        if feature_name not in contract.feature_columns:
            raise FISError(f"{feature_name!r} is not a DatasetContract feature.")
        values = pd.to_numeric(load_dataset_frame(session.project.root)[feature_name], errors="coerce").dropna()
        if values.empty or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise FISError(f"{feature_name!r} has no finite numeric values for a FIS range.")
        minimum, maximum = float(values.min()), float(values.max())
        if minimum >= maximum:
            raise FISError(f"{feature_name!r} must have at least two distinct numeric values.")
        return {"minimum": minimum, "maximum": maximum}
    except ProjectError as error:
        raise _project_error(error) from error
    except (FISError, KeyError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/projects/fis/default", response_model=FISSpec, status_code=201)
def create_default_project_fis(request: CreateFISRequest) -> FISSpec:
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot create a FIS.")
        return create_default_fis(session.project.root, name=request.name, input_columns=request.input_columns)
    except ProjectError as error:
        raise _project_error(error) from error
    except (FISError, FileNotFoundError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/fis/active", response_model=FISSpec)
def get_active_project_fis(session_id: UUID) -> FISSpec:
    try:
        session = service.get(session_id)
        return load_fis(session.project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No active FIS exists in this project.") from error
    except (FISError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/projects/fis/import/matlab")
def import_matlab_fis(request: ImportMatlabFISRequest) -> dict:
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot import a FIS.")
        result = persist_imported_matlab_fis(session.project.root, request.source)
        return {
            "spec": None if result.spec is None else result.spec.model_dump(mode="json"),
            "issues": [issue.__dict__ for issue in result.issues],
        }
    except ProjectError as error:
        raise _project_error(error) from error
    except (FISError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/fis/export/matlab", response_class=PlainTextResponse)
def export_project_matlab_fis(session_id: UUID) -> str:
    try:
        session = service.get(session_id)
        return export_matlab_fis(load_fis(session.project.root))
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No active FIS exists in this project.") from error
    except (FISError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/fis/canonical.json", response_class=PlainTextResponse)
def get_canonical_fis_json(session_id: UUID) -> str:
    try:
        spec = load_fis(service.get(session_id).project.root)
        return spec.model_dump_json(indent=2)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No active FIS exists in this project.") from error


@app.get("/api/projects/{session_id}/fis/canonical.yaml", response_class=PlainTextResponse)
def get_canonical_fis_yaml(session_id: UUID) -> str:
    try:
        spec = load_fis(service.get(session_id).project.root)
        return yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No active FIS exists in this project.") from error


@app.get("/api/projects/{session_id}/fis/revisions", response_model=list[FISSpec])
def get_project_fis_revisions(session_id: UUID) -> list[FISSpec]:
    try:
        session = service.get(session_id)
        return list_fis_revisions(session.project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No active FIS exists in this project.") from error
    except (FISError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/projects/fis/save", response_model=FISSpec)
def save_project_fis(request: SaveFISRequest) -> FISSpec:
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot modify a FIS.")
        return persist_fis(session.project.root, request.spec)
    except ProjectError as error:
        raise _project_error(error) from error
    except (FISError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error




@app.post("/api/projects/fis/expert-correction", response_model=ExpertCorrectionResult, status_code=201)
def create_project_expert_correction(request: ExpertCorrectionRequest) -> ExpertCorrectionResult:
    from ruflex.application.expert_correction import ExpertCorrectionError, refit_sugeno_consequents

    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot persist expert correction.")
        return refit_sugeno_consequents(
            session.project.root,
            locked_rule_ids=request.locked_rule_ids,
            seed=request.seed,
            validation_fraction=request.validation_fraction,
            test_fraction=request.test_fraction,
            source_explanation_id=request.source_explanation_id,
        )
    except ProjectError as error:
        raise _project_error(error) from error
    except (ExpertCorrectionError, FISError, ValueError, OSError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/fis/expert-correction/latest", response_model=ExpertCorrectionRevision)
def get_latest_project_expert_correction(session_id: UUID) -> ExpertCorrectionRevision:
    from ruflex.application.expert_correction import ExpertCorrectionError, load_latest_expert_correction

    try:
        return load_latest_expert_correction(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No expert correction exists in this project.") from error
    except (ExpertCorrectionError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/fis/expert-correction/{correction_id}", response_model=ExpertCorrectionRevision)
def get_project_expert_correction(session_id: UUID, correction_id: UUID) -> ExpertCorrectionRevision:
    from ruflex.application.expert_correction import ExpertCorrectionError, load_expert_correction

    try:
        return load_expert_correction(service.get(session_id).project.root, correction_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Expert correction not found: {correction_id}") from error
    except (ExpertCorrectionError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/fis/trace/latest", response_model=FISEvaluation)
def get_latest_project_fis_trace(session_id: UUID) -> FISEvaluation:
    try:
        session = service.get(session_id)
        return load_latest_trace(session.project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No FIS trace artifact exists in this project.") from error
    except (FISError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/projects/fis/evaluate", response_model=FISEvaluationResponse)
def evaluate_project_fis(request: EvaluateFISRequest) -> FISEvaluationResponse:
    try:
        session = service.get(request.session_id)
        evaluation = evaluate_fis(load_fis(session.project.root), request.inputs)
        trace_ref = None
        if request.persist_trace:
            if session.project.read_only:
                raise ProjectReadOnlyError("Project was opened read-only and cannot persist a trace artifact.")
            trace_ref = save_trace_artifact(session.project.root, evaluation)
        return FISEvaluationResponse(
            evaluation=evaluation,
            trace_artifact_sha256=None if trace_ref is None else trace_ref.sha256,
        )
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No active FIS exists in this project.") from error
    except (FISError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/projects/fis/response-surface", response_model=ResponseSurface)
def preview_project_fis_response_surface(request: ResponseSurfaceRequest) -> ResponseSurface:
    try:
        session = service.get(request.session_id)
        # The request carries the currently edited canonical FIS, so the surface
        # refreshes before an explicit save without creating a visual-only model.
        del session
        return evaluate_response_surface(
            request.spec, x_variable=request.x_variable, y_variable=request.y_variable,
            fixed_inputs=request.fixed_inputs, resolution=request.resolution,
        )
    except ProjectError as error:
        raise _project_error(error) from error
    except (FISError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/projects/fis/diagnostics", response_model=list[dict[str, object]])
def diagnose_project_fis(request: SaveFISRequest) -> list[dict[str, object]]:
    try:
        service.get(request.session_id)
        return diagnose_fis(request.spec)
    except ProjectError as error:
        raise _project_error(error) from error
    except (FISError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/projects/training/run", response_model=TrainingRun, status_code=201)
def run_training(request: TrainModelRequest) -> TrainingRun:
    from ruflex.application.training import TrainingError, train_model

    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot start a training run.")
        return train_model(
            session.project.root, model_kind=request.model_kind, seed=request.seed, split_seed=request.split_seed, training_seed=request.training_seed,
            max_epochs=request.max_epochs, learning_rate=request.learning_rate,
            batch_size=request.batch_size, patience=request.patience,
            validation_fraction=request.validation_fraction, test_fraction=request.test_fraction,
            max_rules=request.max_rules,
        )
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=422, detail="Confirm a DatasetContract before training.") from error
    except (TrainingError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/training/latest", response_model=TrainingRun)
def get_latest_training(session_id: UUID) -> TrainingRun:
    from ruflex.application.training import TrainingError, load_latest_training_run

    try:
        session = service.get(session_id)
        return load_latest_training_run(session.project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No completed training run exists in this project.") from error
    except (TrainingError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/training/runs", response_model=list[TrainingRun])
def get_training_runs(session_id: UUID) -> list[TrainingRun]:
    from ruflex.application.training import list_training_runs
    try:
        return list_training_runs(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error


@app.get("/api/projects/{session_id}/training/runs/{run_id}", response_model=TrainingRun)
def get_training_run(session_id: UUID, run_id: UUID) -> TrainingRun:
    from ruflex.application.training import load_training_run
    try:
        return load_training_run(service.get(session_id).project.root, run_id)
    except (ProjectError, FileNotFoundError, ValueError) as error:
        if isinstance(error, ProjectError):
            raise _project_error(error) from error
        raise HTTPException(status_code=404, detail=f"Training run not found: {run_id}") from error


@app.post("/api/projects/training/tree-path", response_model=TreePathEvidence, status_code=201)
def create_tree_path_trace(request: TreePathTraceRequest) -> TreePathEvidence:
    from ruflex.application.training import TrainingError, trace_decision_tree
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot persist evidence.")
        return trace_decision_tree(session.project.root, request.run_id, request.sample)
    except ProjectError as error:
        raise _project_error(error) from error
    except (TrainingError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/evidence/tree-path/latest", response_model=TreePathEvidence)
def get_latest_tree_path_trace(session_id: UUID) -> TreePathEvidence:
    from ruflex.application.training import load_latest_tree_path
    try:
        return load_latest_tree_path(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No persisted exact tree path exists in this project.") from error


@app.get("/api/projects/{session_id}/evidence/tree-path/{evidence_id}", response_model=TreePathEvidence)
def get_tree_path_trace(session_id: UUID, evidence_id: UUID) -> TreePathEvidence:
    from ruflex.application.training import load_tree_path
    try:
        return load_tree_path(service.get(session_id).project.root, evidence_id)
    except (ProjectError, FileNotFoundError, ValueError) as error:
        if isinstance(error, ProjectError):
            raise _project_error(error) from error
        raise HTTPException(status_code=404, detail=f"Tree evidence not found: {evidence_id}") from error


@app.post("/api/projects/evidence/explanations", response_model=ExplanationContract, status_code=201)
def create_posthoc_explanation(request: CreatePosthocExplanationRequest) -> ExplanationContract:
    from ruflex.application.evidence import (
        EvidenceError,
        create_gradient_shap_explanation,
        create_integrated_gradients_explanation,
        create_occlusion_explanation,
        create_permutation_shap_explanation,
        create_tree_shap_explanation,
    )

    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot persist an explanation.")
        if request.method == "integrated_gradients":
            return create_integrated_gradients_explanation(session.project.root, request.run_id, request.sample)
        if request.method == "gradient_shap":
            return create_gradient_shap_explanation(session.project.root, request.run_id, request.sample)
        if request.method == "shap":
            return create_permutation_shap_explanation(session.project.root, request.run_id, request.sample)
        if request.method == "tree_shap":
            return create_tree_shap_explanation(session.project.root, request.run_id, request.sample)
        return create_occlusion_explanation(session.project.root, request.run_id, request.sample)
    except ProjectError as error:
        raise _project_error(error) from error
    except (EvidenceError, ValueError, OSError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/projects/evidence/explanation-jobs", response_model=Job, status_code=202)
def start_posthoc_explanation_job(request: CreatePosthocExplanationRequest) -> Job:
    """Queue a persisted explanation operation without hiding its execution state."""
    from ruflex.application.evidence_jobs import EvidenceJobError, start_explanation_generation_job

    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot persist an explanation job.")
        return start_explanation_generation_job(
            session.project.root, run_id=request.run_id, sample=request.sample, method=request.method,
        )
    except ProjectError as error:
        raise _project_error(error) from error
    except (EvidenceJobError, ValueError, OSError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/evidence/explanation-jobs/{job_id}", response_model=Job)
def get_posthoc_explanation_job(session_id: UUID, job_id: UUID) -> Job:
    from ruflex.application.jobs import load_job
    try:
        return load_job(service.get(session_id).project.root, job_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except (ValueError, OSError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail=f"Explanation job not found: {job_id}") from error


@app.get("/api/projects/{session_id}/evidence/explanation-jobs", response_model=list[Job])
def list_posthoc_explanation_jobs(session_id: UUID) -> list[Job]:
    from ruflex.application.jobs import list_jobs
    try:
        return list_jobs(service.get(session_id).project.root, kind="explanation_generation")
    except ProjectError as error:
        raise _project_error(error) from error


@app.post("/api/projects/evidence/explanation-check-jobs", response_model=Job, status_code=202)
def start_posthoc_explanation_check_job(request: CheckExplanationRequest) -> Job:
    from ruflex.application.evidence_jobs import EvidenceJobError, start_explanation_check_job
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot persist an explanation-check job.")
        return start_explanation_check_job(session.project.root, explanation_id=request.explanation_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except (EvidenceJobError, ValueError, OSError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/projects/evidence/explanations/occlusion", response_model=ExplanationContract, status_code=201)
def create_posthoc_occlusion_explanation(request: CreateOcclusionExplanationRequest) -> ExplanationContract:
    from ruflex.application.evidence import EvidenceError, create_occlusion_explanation

    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot persist an explanation.")
        return create_occlusion_explanation(session.project.root, request.run_id, request.sample)
    except ProjectError as error:
        raise _project_error(error) from error
    except (EvidenceError, ValueError, OSError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/evidence/explanations/latest", response_model=ExplanationContract)
def get_latest_posthoc_explanation(session_id: UUID) -> ExplanationContract:
    from ruflex.application.evidence import EvidenceError, load_latest_explanation

    try:
        return load_latest_explanation(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No persisted post-hoc explanation exists in this project.") from error
    except (EvidenceError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/evidence/explanations", response_model=list[ExplanationContract])
def list_explanations_route(session_id: UUID) -> list[ExplanationContract]:
    from ruflex.application.reproducibility import list_explanations
    try:
        return list_explanations(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error


@app.get("/api/projects/{session_id}/evidence/explanations/{explanation_id}", response_model=ExplanationContract)
def get_posthoc_explanation(session_id: UUID, explanation_id: UUID) -> ExplanationContract:
    from ruflex.application.evidence import load_explanation
    try:
        return load_explanation(service.get(session_id).project.root, explanation_id)
    except (ProjectError, FileNotFoundError, ValueError) as error:
        if isinstance(error, ProjectError):
            raise _project_error(error) from error
        raise HTTPException(status_code=404, detail=f"Explanation not found: {explanation_id}") from error


@app.post("/api/projects/evidence/explanation-checks", response_model=ExplanationCheck, status_code=201)
def create_posthoc_explanation_check(request: CheckExplanationRequest) -> ExplanationCheck:
    from ruflex.application.evidence import EvidenceError, check_explanation

    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot persist an explanation check.")
        return check_explanation(session.project.root, request.explanation_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except (EvidenceError, ValueError, OSError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/evidence/explanation-checks/latest", response_model=ExplanationCheck)
def get_latest_posthoc_explanation_check(session_id: UUID) -> ExplanationCheck:
    from ruflex.application.evidence import EvidenceError, load_latest_explanation_check

    try:
        return load_latest_explanation_check(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No persisted explanation check exists in this project.") from error
    except (EvidenceError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/evidence/explanation-checks/{check_id}", response_model=ExplanationCheck)
def get_explanation_check(session_id: UUID, check_id: UUID) -> ExplanationCheck:
    from ruflex.application.evidence import load_explanation_check
    try:
        return load_explanation_check(service.get(session_id).project.root, check_id)
    except (ProjectError, FileNotFoundError, ValueError) as error:
        if isinstance(error, ProjectError):
            raise _project_error(error) from error
        raise HTTPException(status_code=404, detail=f"Explanation check not found: {check_id}") from error


@app.post("/api/projects/evidence/explanation-reproducibility", response_model=ExplanationReproducibilityAnalysis, status_code=201)
def create_explanation_reproducibility_route(request: CreateExplanationReproducibilityRequest) -> ExplanationReproducibilityAnalysis:
    from ruflex.application.reproducibility import ReproducibilityError, create_explanation_reproducibility
    try:
        session=service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot persist explanation reproducibility evidence.")
        return create_explanation_reproducibility(session.project.root, request.explanation_ids)
    except ProjectError as error:
        raise _project_error(error) from error
    except (ReproducibilityError, FileNotFoundError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/evidence/explanation-reproducibility/latest", response_model=ExplanationReproducibilityAnalysis)
def get_latest_explanation_reproducibility(session_id: UUID) -> ExplanationReproducibilityAnalysis:
    from ruflex.application.reproducibility import load_latest_explanation_reproducibility
    try:
        return load_latest_explanation_reproducibility(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No persisted explanation reproducibility analysis exists in this project.") from error

@app.post("/api/projects/evidence/exhaustive-lab", response_model=ExhaustiveLabResult, status_code=201)
def run_exhaustive_lab_route(request: RunExhaustiveLabRequest) -> ExhaustiveLabResult:
    from ruflex.application.exhaustive import ExhaustiveLabError, run_fis_grid_exhaustive, run_tree_exhaustive
    try:
        session=service.get(request.session_id)
        if session.project.read_only: raise ProjectReadOnlyError("Project was opened read-only and cannot persist Exhaustive Lab evidence.")
        if request.kind == "decision_tree_structure":
            if request.run_id is None: raise ExhaustiveLabError("A Decision Tree run is required.")
            return run_tree_exhaustive(session.project.root, request.run_id)
        return run_fis_grid_exhaustive(session.project.root, request.grid_points, request.max_states)
    except ProjectError as error: raise _project_error(error) from error
    except (ExhaustiveLabError, FileNotFoundError, ValueError, OSError) as error: raise HTTPException(status_code=422, detail=str(error)) from error

@app.get("/api/projects/{session_id}/evidence/exhaustive-lab/fis-grid-estimate")
def estimate_exhaustive_fis_grid(session_id: UUID, grid_points: int = 3, max_states: int = 10_000) -> dict:
    from ruflex.application.exhaustive import ExhaustiveLabError, estimate_fis_grid_states
    try:
        estimate = estimate_fis_grid_states(service.get(session_id).project.root, grid_points)
        return {"grid_points": grid_points, "state_estimate": estimate, "max_states": max_states, "allowed": estimate <= max_states}
    except ProjectError as error: raise _project_error(error) from error
    except (ExhaustiveLabError, FileNotFoundError, ValueError) as error: raise HTTPException(status_code=422, detail=str(error)) from error

@app.get("/api/projects/{session_id}/evidence/exhaustive-lab/latest", response_model=ExhaustiveLabResult)
def get_latest_exhaustive_lab(session_id: UUID) -> ExhaustiveLabResult:
    from ruflex.application.exhaustive import load_latest_exhaustive
    try: return load_latest_exhaustive(service.get(session_id).project.root)
    except ProjectError as error: raise _project_error(error) from error
    except FileNotFoundError as error: raise HTTPException(status_code=404, detail="No persisted Exhaustive Lab result exists in this project.") from error

@app.post("/api/projects/evidence/assurance-cases", response_model=AssuranceCase, status_code=201)
def create_assurance_case_route(request: SessionRequest) -> AssuranceCase:
    from ruflex.application.assurance import create_assurance_case
    try:
        session=service.get(request.session_id)
        if session.project.read_only: raise ProjectReadOnlyError("Project was opened read-only and cannot persist an AssuranceCase.")
        return create_assurance_case(session.project.root)
    except ProjectError as error: raise _project_error(error) from error


@app.post("/api/projects/evidence/assurance-jobs", response_model=Job, status_code=202)
def start_assurance_case_job_route(request: SessionRequest) -> Job:
    from ruflex.application.evidence_jobs import start_assurance_case_job
    try:
        session = service.get(request.session_id)
        if session.project.read_only: raise ProjectReadOnlyError("Project was opened read-only and cannot persist an AssuranceCase job.")
        return start_assurance_case_job(session.project.root)
    except ProjectError as error: raise _project_error(error) from error

@app.get("/api/projects/{session_id}/evidence/assurance-cases/latest", response_model=AssuranceCase)
def get_latest_assurance_case(session_id: UUID) -> AssuranceCase:
    from ruflex.application.assurance import load_latest_assurance_case
    try: return load_latest_assurance_case(service.get(session_id).project.root)
    except ProjectError as error: raise _project_error(error) from error
    except FileNotFoundError as error: raise HTTPException(status_code=404, detail="No persisted AssuranceCase exists in this project.") from error

@app.post("/api/projects/evidence/verification-bundles", response_model=dict, status_code=201)
def export_verification_bundle_route(request: SessionRequest) -> dict:
    from ruflex.application.verification_bundle import export_verification_bundle
    try:
        session=service.get(request.session_id)
        if session.project.read_only: raise ProjectReadOnlyError("Project was opened read-only and cannot export a VerificationBundle.")
        return export_verification_bundle(session.project.root)
    except ProjectError as error: raise _project_error(error) from error
    except FileNotFoundError as error: raise HTTPException(status_code=422, detail="Build an AssuranceCase before exporting a VerificationBundle.") from error


@app.post("/api/projects/evidence/verification-bundle-jobs", response_model=Job, status_code=202)
def start_verification_bundle_export_job_route(request: SessionRequest) -> Job:
    from ruflex.application.evidence_jobs import start_verification_bundle_export_job
    try:
        session = service.get(request.session_id)
        if session.project.read_only: raise ProjectReadOnlyError("Project was opened read-only and cannot persist a VerificationBundle job.")
        return start_verification_bundle_export_job(session.project.root)
    except ProjectError as error: raise _project_error(error) from error
    except FileNotFoundError as error: raise HTTPException(status_code=422, detail="Build an AssuranceCase before exporting a VerificationBundle.") from error


@app.post("/api/verification-bundles/validate", response_model=VerificationBundleValidation)
def validate_verification_bundle_route(request: ValidateVerificationBundleRequest) -> VerificationBundleValidation:
    """Inspect an exported or freshly extracted declarative evidence bundle."""
    from ruflex.application.verification_bundle import validate_verification_bundle
    return validate_verification_bundle(request.path)


@app.post("/api/projects/evidence/behavior-specs", response_model=BehaviorSpec, status_code=201)
def create_behavior_spec_route(request: CreateBehaviorSpecRequest) -> BehaviorSpec:
    from ruflex.application.behavior import BehaviorSpecError, create_behavior_spec
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot persist a BehaviorSpec.")
        return create_behavior_spec(session.project.root, request.model_dump())
    except ProjectError as error:
        raise _project_error(error) from error
    except (BehaviorSpecError, ValueError, OSError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/projects/evidence/behavior-specs/run", response_model=BehaviorSpecResult, status_code=201)
def run_behavior_spec_route(request: RunBehaviorSpecRequest) -> BehaviorSpecResult:
    from ruflex.application.behavior import BehaviorSpecError, run_behavior_spec
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot persist BehaviorSpec evidence.")
        return run_behavior_spec(session.project.root, request.spec_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except (BehaviorSpecError, ValueError, OSError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/evidence/behavior-specs/latest", response_model=BehaviorSpecResult)
def get_latest_behavior_result(session_id: UUID) -> BehaviorSpecResult:
    from ruflex.application.behavior import load_latest_behavior_result
    try:
        return load_latest_behavior_result(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No persisted BehaviorSpec result exists in this project.") from error


@app.get("/api/projects/{session_id}/evidence/behavior-specs", response_model=list[BehaviorSpec])
def list_behavior_specs_route(session_id: UUID) -> list[BehaviorSpec]:
    from ruflex.application.behavior import list_behavior_specs
    try:
        return list_behavior_specs(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error


@app.get("/api/projects/{session_id}/evidence/behavior-specs/results", response_model=list[BehaviorSpecResult])
def list_behavior_results_route(session_id: UUID) -> list[BehaviorSpecResult]:
    from ruflex.application.behavior import list_behavior_results
    try:
        return list_behavior_results(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error


@app.post("/api/projects/training/studies", response_model=TrainingStudy, status_code=201)
def run_multi_seed_training_study(request: MultiSeedStudyRequest) -> TrainingStudy:
    from ruflex.application.training import TrainingError, run_multi_seed_study
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot start a study.")
        return run_multi_seed_study(
            session.project.root, name=request.name, model_kind=request.model_kind, seeds=request.seeds, randomness_protocol=request.randomness_protocol, split_seed=request.split_seed, training_seed=request.training_seed,
            selection_metric=request.selection_metric, max_epochs=request.max_epochs,
            learning_rate=request.learning_rate, batch_size=request.batch_size,
            patience=request.patience, validation_fraction=request.validation_fraction,
            test_fraction=request.test_fraction, max_rules=request.max_rules,
        )
    except ProjectError as error:
        raise _project_error(error) from error
    except (TrainingError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/projects/training/study-jobs", response_model=StudyJob, status_code=202)
def start_multi_seed_study_job(request: MultiSeedStudyRequest) -> StudyJob:
    from ruflex.application.training import TrainingError, start_study_job
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot start a study.")
        return start_study_job(session.project.root, name=request.name, model_kind=request.model_kind, seeds=request.seeds, selection_metric=request.selection_metric, randomness_protocol=request.randomness_protocol, split_seed=request.split_seed, training_seed=request.training_seed, max_epochs=request.max_epochs, learning_rate=request.learning_rate, batch_size=request.batch_size, patience=request.patience, validation_fraction=request.validation_fraction, test_fraction=request.test_fraction, max_rules=request.max_rules)
    except ProjectError as error:
        raise _project_error(error) from error
    except (TrainingError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/training/study-jobs/{job_id}", response_model=StudyJob)
def get_study_job(session_id: UUID, job_id: UUID) -> StudyJob:
    from ruflex.application.training import load_study_job
    try:
        return load_study_job(service.get(session_id).project.root, job_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No Study job exists with this id.") from error


@app.get("/api/projects/{session_id}/training/study-jobs", response_model=list[StudyJob])
def list_persisted_study_jobs(session_id: UUID) -> list[StudyJob]:
    from ruflex.application.training import list_study_jobs
    try:
        return list_study_jobs(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error


@app.post("/api/projects/{session_id}/training/study-jobs/{job_id}/cancel", response_model=StudyJob)
def cancel_running_study_job(session_id: UUID, job_id: UUID) -> StudyJob:
    from ruflex.application.training import cancel_study_job
    try:
        session = service.get(session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot cancel a study.")
        return cancel_study_job(session.project.root, job_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No Study job exists with this id.") from error


@app.post("/api/projects/{session_id}/training/study-jobs/{job_id}/resume", response_model=StudyJob)
def resume_persisted_study_job(session_id: UUID, job_id: UUID) -> StudyJob:
    from ruflex.application.training import TrainingError, resume_study_job
    try:
        session = service.get(session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot resume a study.")
        return resume_study_job(session.project.root, job_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except (TrainingError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/training/studies/latest", response_model=TrainingStudy)
def get_latest_training_study(session_id: UUID) -> TrainingStudy:
    from ruflex.application.training import load_latest_training_study
    try:
        return load_latest_training_study(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No training study exists in this project.") from error


@app.get("/api/projects/{session_id}/training/studies/{study_id}", response_model=TrainingStudy)
def get_training_study(session_id: UUID, study_id: UUID) -> TrainingStudy:
    from ruflex.application.training import load_training_study
    try:
        return load_training_study(service.get(session_id).project.root, study_id)
    except (ProjectError, FileNotFoundError, ValueError) as error:
        if isinstance(error, ProjectError):
            raise _project_error(error) from error
        raise HTTPException(status_code=404, detail=f"Training study not found: {study_id}") from error


@app.post("/api/projects/analyses/stability", response_model=StudyStabilityAnalysis, status_code=201)
def create_study_stability_analysis_route(request: CreateStudyStabilityAnalysisRequest) -> StudyStabilityAnalysis:
    from ruflex.application.stability import create_study_stability_analysis
    from ruflex.application.training import TrainingError
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot create stability evidence.")
        return create_study_stability_analysis(session.project.root, request.study_id, evaluation_id=request.evaluation_id, threshold_id=request.threshold_id, high_confidence_threshold=request.high_confidence_threshold, unstable_agreement_threshold=request.unstable_agreement_threshold)
    except ProjectError as error:
        raise _project_error(error) from error
    except (TrainingError, FileNotFoundError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/analyses/stability", response_model=list[StudyStabilityAnalysis])
def list_study_stability_analyses_route(session_id: UUID) -> list[StudyStabilityAnalysis]:
    from ruflex.application.stability import list_study_stability_analyses
    try:
        return list_study_stability_analyses(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error


@app.get("/api/projects/{session_id}/analyses/stability/{analysis_id}", response_model=StudyStabilityAnalysis)
def get_study_stability_analysis_route(session_id: UUID, analysis_id: UUID) -> StudyStabilityAnalysis:
    from ruflex.application.stability import load_study_stability_analysis
    try:
        return load_study_stability_analysis(service.get(session_id).project.root, analysis_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Study Stability Analysis not found.") from error


@app.post("/api/projects/analyses/stability-policies", response_model=StabilityGatePolicy, status_code=201)
def create_stability_gate_policy_route(request: CreateStabilityGatePolicyRequest) -> StabilityGatePolicy:
    from ruflex.application.stability import create_stability_gate_policy
    from ruflex.application.training import TrainingError
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot create a Stability Gate policy.")
        return create_stability_gate_policy(session.project.root, request.analysis_id, request.evaluation_id, min_confidence=request.min_confidence, min_class_agreement=request.min_class_agreement, max_probability_std=request.max_probability_std, calibration_id=request.calibration_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except (TrainingError, FileNotFoundError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/analyses/stability-policies", response_model=list[StabilityGatePolicy])
def list_stability_gate_policies_route(session_id: UUID) -> list[StabilityGatePolicy]:
    from ruflex.application.stability import list_stability_gate_policies
    try:
        return list_stability_gate_policies(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error


@app.post("/api/projects/analyses/stability-policies/apply", response_model=StabilityGateApplication)
def apply_stability_gate_policy_route(request: ApplyStabilityGatePolicyRequest) -> StabilityGateApplication:
    from ruflex.application.stability import apply_stability_gate_policy
    from ruflex.application.training import TrainingError
    try:
        return apply_stability_gate_policy(service.get(request.session_id).project.root, request.policy_id, request.sample, metadata=request.metadata, generalization_contract_id=request.generalization_contract_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except (TrainingError, FileNotFoundError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/projects/analyses/evaluations", response_model=AnalysisEvaluation, status_code=201)
def create_analysis_evaluation(request: CreateAnalysisEvaluationRequest) -> AnalysisEvaluation:
    from ruflex.application.training import TrainingError, create_validation_evaluation
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot persist an analysis evaluation.")
        return create_validation_evaluation(session.project.root, request.run_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="The selected training run does not exist in this project.") from error
    except (TrainingError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/analyses/evaluations/latest", response_model=AnalysisEvaluation)
def get_latest_analysis_evaluation(session_id: UUID) -> AnalysisEvaluation:
    from ruflex.application.training import load_latest_validation_evaluation
    try:
        return load_latest_validation_evaluation(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No persisted analysis evaluation exists in this project.") from error


@app.get("/api/projects/{session_id}/analyses/evaluations/{evaluation_id}", response_model=AnalysisEvaluation)
def get_analysis_evaluation(session_id: UUID, evaluation_id: UUID) -> AnalysisEvaluation:
    from ruflex.application.training import load_validation_evaluation
    try:
        return load_validation_evaluation(service.get(session_id).project.root, evaluation_id)
    except (ProjectError, FileNotFoundError, ValueError) as error:
        if isinstance(error, ProjectError):
            raise _project_error(error) from error
        raise HTTPException(status_code=404, detail=f"Evaluation not found: {evaluation_id}") from error


@app.post("/api/projects/analyses/calibrations", response_model=CalibrationTransform, status_code=201)
def fit_analysis_calibration(request: FitAnalysisCalibrationRequest) -> CalibrationTransform:
    from ruflex.application.training import TrainingError, fit_validation_calibration
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot fit a calibration transform.")
        return fit_validation_calibration(session.project.root, request.evaluation_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="The selected validation evaluation does not exist in this project.") from error
    except (TrainingError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/analyses/calibrations/latest", response_model=CalibrationTransform)
def get_latest_analysis_calibration(session_id: UUID) -> CalibrationTransform:
    from ruflex.application.training import load_latest_validation_calibration
    try:
        return load_latest_validation_calibration(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No persisted calibration transform exists in this project.") from error


@app.get("/api/projects/{session_id}/analyses/calibrations/{calibration_id}", response_model=CalibrationTransform)
def get_analysis_calibration(session_id: UUID, calibration_id: UUID) -> CalibrationTransform:
    from ruflex.application.training import load_validation_calibration
    try:
        return load_validation_calibration(service.get(session_id).project.root, calibration_id)
    except (ProjectError, FileNotFoundError, ValueError) as error:
        if isinstance(error, ProjectError):
            raise _project_error(error) from error
        raise HTTPException(status_code=404, detail=f"Calibration not found: {calibration_id}") from error


@app.post("/api/projects/analyses/thresholds", response_model=DecisionThresholdPolicy, status_code=201)
def select_analysis_threshold(request: SelectAnalysisThresholdRequest) -> DecisionThresholdPolicy:
    from ruflex.application.training import TrainingError, select_validation_threshold
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot select a decision threshold.")
        return select_validation_threshold(
            session.project.root,
            request.evaluation_id,
            calibration_id=request.calibration_id,
            objective=request.objective,
        )
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="The selected validation evidence or calibration object does not exist.") from error
    except (TrainingError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/analyses/thresholds/latest", response_model=DecisionThresholdPolicy)
def get_latest_analysis_threshold(session_id: UUID) -> DecisionThresholdPolicy:
    from ruflex.application.training import load_latest_decision_threshold
    try:
        return load_latest_decision_threshold(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No persisted decision-threshold policy exists in this project.") from error


@app.get("/api/projects/{session_id}/analyses/thresholds/{threshold_id}", response_model=DecisionThresholdPolicy)
def get_analysis_threshold(session_id: UUID, threshold_id: UUID) -> DecisionThresholdPolicy:
    from ruflex.application.training import load_decision_threshold
    try:
        return load_decision_threshold(service.get(session_id).project.root, threshold_id)
    except (ProjectError, FileNotFoundError, ValueError) as error:
        if isinstance(error, ProjectError):
            raise _project_error(error) from error
        raise HTTPException(status_code=404, detail=f"Threshold not found: {threshold_id}") from error


@app.post("/api/projects/analyses/selective-policies", response_model=SelectivePredictionPolicy, status_code=201)
def create_selective_policy_route(request: CreateSelectivePolicyRequest) -> SelectivePredictionPolicy:
    from ruflex.application.selective import create_selective_policy
    from ruflex.application.training import TrainingError
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot select a review policy.")
        return create_selective_policy(session.project.root, request.evaluation_id, request.confidence_cutoff, request.calibration_id, request.threshold_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except (TrainingError, FileNotFoundError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/analyses/selective-policies/latest", response_model=SelectivePredictionPolicy)
def get_latest_selective_policy(session_id: UUID) -> SelectivePredictionPolicy:
    from ruflex.application.selective import load_latest_selective_policy
    try:
        return load_latest_selective_policy(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No persisted selective-review policy exists in this project.") from error


@app.post("/api/projects/analyses/selective-policies/apply", response_model=SelectiveDecision)
def apply_selective_policy_route(request: ApplySelectivePolicyRequest) -> SelectiveDecision:
    from ruflex.application.selective import apply_selective_policy
    from ruflex.application.training import TrainingError
    try:
        session = service.get(request.session_id)
        return apply_selective_policy(session.project.root, request.policy_id, request.sample, metadata=request.metadata, generalization_contract_id=request.generalization_contract_id)
    except ProjectError as error:
        raise _project_error(error) from error
    except (TrainingError, FileNotFoundError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

@app.post("/api/projects/evidence/condition-monitoring-demo", response_model=ConditionMonitoringDemo, status_code=201)
def run_condition_monitoring_demo_route(request: RunConditionMonitoringDemoRequest) -> ConditionMonitoringDemo:
    from ruflex.application.demo import run_condition_monitoring_demo
    try:
        session = service.get(request.session_id)
        if session.project.read_only: raise ProjectReadOnlyError("Project was opened read-only and cannot persist a condition-monitoring demo.")
        return run_condition_monitoring_demo(session.project.root, request.telemetry, policy_id=request.policy_id, metadata=request.metadata, generalization_contract_id=request.generalization_contract_id)
    except ProjectError as error: raise _project_error(error) from error
    except (FileNotFoundError, ValueError, OSError) as error: raise HTTPException(status_code=422, detail=str(error)) from error

@app.get("/api/projects/{session_id}/evidence/condition-monitoring-demo/latest", response_model=ConditionMonitoringDemo)
def get_latest_condition_monitoring_demo(session_id: UUID) -> ConditionMonitoringDemo:
    from ruflex.application.demo import load_latest_condition_monitoring_demo
    try: return load_latest_condition_monitoring_demo(service.get(session_id).project.root)
    except ProjectError as error: raise _project_error(error) from error
    except FileNotFoundError as error: raise HTTPException(status_code=404, detail="No persisted condition-monitoring demonstration exists.") from error


@app.post("/api/projects/analyses/final-test", response_model=FinalTestEvaluation, status_code=201)
def evaluate_analysis_final_test(request: EvaluateFinalTestRequest) -> FinalTestEvaluation:
    from ruflex.application.training import TrainingError, evaluate_final_test
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot evaluate the final-test split.")
        return evaluate_final_test(
            session.project.root,
            request.evaluation_id,
            calibration_id=request.calibration_id,
            threshold_id=request.threshold_id,
            selective_policy_id=request.selective_policy_id,
            stability_gate_policy_id=request.stability_gate_policy_id,
        )
    except (TrainingError, ProjectError) as error:
        raise _project_error(error) from error
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=404, detail="The selected validation/policy object does not exist in this project.") from error


@app.get("/api/projects/{session_id}/analyses/final-test/latest", response_model=FinalTestEvaluation)
def get_latest_analysis_final_test(session_id: UUID) -> FinalTestEvaluation:
    from ruflex.application.training import load_latest_final_test_evaluation
    try:
        return load_latest_final_test_evaluation(service.get(session_id).project.root)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=404, detail="No final-test evaluation exists in this project.") from error


@app.get("/api/projects/{session_id}/analyses/final-test/{final_test_id}", response_model=FinalTestEvaluation)
def get_analysis_final_test(session_id: UUID, final_test_id: UUID) -> FinalTestEvaluation:
    from ruflex.application.training import load_final_test_evaluation
    try:
        return load_final_test_evaluation(service.get(session_id).project.root, final_test_id)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=404, detail=f"Final-test evaluation not found: {final_test_id}") from error


@app.post("/api/projects/analyses/comparisons", response_model=AnalysisComparison, status_code=201)
def create_analysis_comparison(request: CreateAnalysisComparisonRequest) -> AnalysisComparison:
    from ruflex.application.training import TrainingError, create_validation_comparison
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot persist an analysis comparison.")
        return create_validation_comparison(
            session.project.root,
            request.run_ids,
            include_active_fis=request.include_active_fis,
        )
    except ProjectError as error:
        raise _project_error(error) from error
    except (TrainingError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/analyses/comparisons/latest", response_model=AnalysisComparison)
def get_latest_analysis_comparison(session_id: UUID) -> AnalysisComparison:
    from ruflex.application.training import load_latest_validation_comparison
    try:
        return load_latest_validation_comparison(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No persisted analysis comparison exists in this project.") from error
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/analyses/comparisons/{comparison_id}", response_model=AnalysisComparison)
def get_analysis_comparison(session_id: UUID, comparison_id: UUID) -> AnalysisComparison:
    from ruflex.application.training import load_validation_comparison
    try:
        return load_validation_comparison(service.get(session_id).project.root, comparison_id)
    except (ProjectError, FileNotFoundError, ValueError) as error:
        if isinstance(error, ProjectError):
            raise _project_error(error) from error
        raise HTTPException(status_code=404, detail=f"Comparison not found: {comparison_id}") from error


@app.post("/api/projects/analyses/slices", response_model=SliceAnalysis, status_code=201)
def create_validation_slice_analysis(request: CreateSliceAnalysisRequest) -> SliceAnalysis:
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot persist a Slice Analysis.")
        return create_slice_analysis(
            session.project.root,
            evaluation_id=request.evaluation_id,
            definitions=request.definitions,
            metric=request.metric,
            generalization_contract_id=session.project.manifest.active_generalization_contract_id,
        )
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="The selected Evaluation or dataset evidence does not exist.") from error
    except (GeneralizationContractError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/analyses/slices/latest", response_model=SliceAnalysis)
def get_latest_validation_slice_analysis(session_id: UUID) -> SliceAnalysis:
    try:
        return load_latest_slice_analysis(service.get(session_id).project.root)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No persisted Slice Analysis exists in this project.") from error
    except (GeneralizationContractError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/analyses/slices/{analysis_id}", response_model=SliceAnalysis)
def get_slice_analysis(session_id: UUID, analysis_id: UUID) -> SliceAnalysis:
    from ruflex.application.generalization import load_slice_analysis
    try:
        return load_slice_analysis(service.get(session_id).project.root, analysis_id)
    except (ProjectError, FileNotFoundError, ValueError) as error:
        if isinstance(error, ProjectError):
            raise _project_error(error) from error
        raise HTTPException(status_code=404, detail=f"Slice analysis not found: {analysis_id}") from error


@app.post("/api/projects/generalization/contracts", response_model=GeneralizationContractResponse, status_code=201)
def create_contract(request: CreateGeneralizationContractRequest) -> GeneralizationContractResponse:
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot receive a generalization contract.")
        dataset = load_dataset_contract(session.project.root)
        contract = create_generalization_contract(dataset, request.model_dump(exclude={"session_id"}))
        persist_generalization_contract(session.project.root, contract)
        session.project.manifest.active_generalization_contract_id = contract.contract_id
        service.save(request.session_id)
        return GeneralizationContractResponse(contract=contract, lint=lint_generalization_contract(contract, dataset), recommendations=recommend_split_families(contract))
    except (ProjectError, GeneralizationContractError, OSError) as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=422, detail="Confirm a DatasetContract before declaring generalization.") from error


@app.get("/api/projects/{session_id}/generalization/contracts/active", response_model=GeneralizationContractResponse)
def get_active_generalization_contract(session_id: UUID) -> GeneralizationContractResponse:
    """Restore the project manifest's active generalization contract.

    The contract is a persistent project object, so reopening a Studio project
    must restore it just like the active dataset/model/analysis objects.  Lint
    and split recommendations are recomputed against the currently persisted
    DatasetContract instead of being copied from transient UI state.
    """
    try:
        session = service.get(session_id)
        contract_id = session.project.manifest.active_generalization_contract_id
        if contract_id is None:
            raise FileNotFoundError("No active generalization contract is recorded in the project manifest.")
        dataset = load_dataset_contract(session.project.root)
        contract = load_generalization_contract(session.project.root, contract_id)
        return GeneralizationContractResponse(
            contract=contract,
            lint=lint_generalization_contract(contract, dataset),
            recommendations=recommend_split_families(contract),
        )
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="No active generalization contract exists in this project.") from error
    except (GeneralizationContractError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{session_id}/generalization/contracts/{contract_id}", response_model=GeneralizationContractResponse)
def get_generalization_contract(session_id: UUID, contract_id: UUID) -> GeneralizationContractResponse:
    """Open a specific persisted generalization contract from lineage/history."""
    try:
        session = service.get(session_id)
        dataset = load_dataset_contract(session.project.root)
        contract = load_generalization_contract(session.project.root, contract_id)
        return GeneralizationContractResponse(
            contract=contract,
            lint=lint_generalization_contract(contract, dataset),
            recommendations=recommend_split_families(contract),
        )
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Generalization contract not found: {contract_id}") from error
    except (GeneralizationContractError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post(
    "/api/projects/generalization/contracts/{contract_id}/classify",
    response_model=ScopeClassification,
)
def classify_generalization_sample(
    contract_id: UUID,
    request: ClassifyGeneralizationScopeRequest,
) -> ScopeClassification:
    """Classify one sample against the declared scope without evaluating a model.

    This endpoint is deliberately metadata-only.  It does not infer missing
    metadata, inspect final-test data, or turn an ALLOW result into evidence of
    predictive generalization.
    """
    try:
        session = service.get(request.session_id)
        contract = load_generalization_contract(session.project.root, contract_id)
        return classify_scope(contract, request.sample_metadata)
    except ProjectError as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Generalization contract not found: {contract_id}") from error
    except (GeneralizationContractError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/projects/generalization/contracts/{contract_id}/freeze", response_model=GeneralizationContractResponse)
def freeze_contract(contract_id: UUID, request: SessionRequest) -> GeneralizationContractResponse:
    try:
        session = service.get(request.session_id)
        if session.project.read_only:
            raise ProjectReadOnlyError("Project was opened read-only and cannot freeze a generalization contract.")
        dataset = load_dataset_contract(session.project.root)
        frozen = freeze_generalization_contract(load_generalization_contract(session.project.root, contract_id), dataset)
        persist_generalization_contract(session.project.root, frozen)
        session.project.manifest.active_generalization_contract_id = frozen.contract_id
        service.save(request.session_id)
        return GeneralizationContractResponse(contract=frozen, lint=lint_generalization_contract(frozen, dataset), recommendations=recommend_split_families(frozen))
    except (ProjectError, GeneralizationContractError, OSError) as error:
        raise _project_error(error) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Generalization contract was not found.") from error
