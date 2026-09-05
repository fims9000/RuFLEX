"""Persisted LocalExecutor orchestration for potentially expensive XAI work."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from ruflex.application.jobs import Job, JobStatus, load_job, persist_job
from ruflex.runtime.backends import resolve_execution_backend


class EvidenceJobError(ValueError):
    pass


def _new_job(kind: str, *, execution_backend_key: str = "local_executor", **values) -> Job:
    descriptor, _ = resolve_execution_backend(execution_backend_key)
    return Job(
        kind=kind,
        execution_backend_key=descriptor.identity.key,
        execution_backend_version=descriptor.identity.version,
        execution_backend_provider=descriptor.identity.provider,
        **values,
    )


def _submit(project_root: Path, job: Job) -> None:
    descriptor, backend = resolve_execution_backend(job.execution_backend_key or "local_executor")
    if (job.execution_backend_version, job.execution_backend_provider) != (descriptor.identity.version, descriptor.identity.provider):
        raise EvidenceJobError("Persisted job backend identity is incompatible with the active runtime.")
    backend.submit(project_root=project_root, job_id=job.job_id, operation=lambda: _execute(project_root, job.job_id))


def _append(job: Job, message: str) -> None:
    job.message = message
    job.log.append(message)


def _generate(project_root: Path, request: dict) -> str:
    from ruflex.application.evidence import create_runtime_explanation
    run_id = UUID(request["run_id"])
    sample = {str(name): float(value) for name, value in request["sample"].items()}
    result = create_runtime_explanation(project_root, explainer_key=request["method"], run_id=run_id, sample=sample)
    return str(result.explanation_id)


def _execute(project_root: Path, job_id: UUID) -> None:
    job = load_job(project_root, job_id)
    if job.status != JobStatus.QUEUED:
        return
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    _append(job, "Frozen execution backend started persisted evidence operation.")
    persist_job(project_root, job)
    try:
        if job.kind == "explanation_generation":
            output = {"explanation_id": _generate(project_root, job.request)}
        elif job.kind == "explanation_check":
            from ruflex.application.evidence import check_explanation
            result = check_explanation(project_root, UUID(job.request["explanation_id"]), validator_key=job.request["validator_key"])
            output = {"check_id": str(result.check_id)}
        elif job.kind == "assurance_case":
            from ruflex.application.assurance import create_assurance_case
            result = create_assurance_case(project_root)
            output = {"assurance_id": str(result.assurance_id)}
        elif job.kind == "verification_bundle_export":
            from ruflex.application.verification_bundle import export_verification_bundle
            result = export_verification_bundle(project_root)
            output = {key: str(value) for key, value in result.items()}
        else:
            raise EvidenceJobError(f"Unsupported evidence job kind {job.kind!r}.")
        job = load_job(project_root, job_id)
        job.output = output
        job.status = JobStatus.SUCCEEDED
        job.progress = 1.0
        _append(job, "Requested evidence operation persisted its canonical output.")
    except Exception as error:  # persisted operational evidence, re-raised nowhere from worker
        job = load_job(project_root, job_id)
        job.status = JobStatus.FAILED
        job.error = str(error)
        _append(job, "Evidence operation failed before a successful job result was recorded.")
    job.finished_at = datetime.now(timezone.utc)
    persist_job(project_root, job)


def start_explanation_generation_job(
    project_root: Path,
    *,
    run_id: UUID,
    sample: dict[str, float],
    method: str,
    execution_backend_key: str = "local_executor",
) -> Job:
    from ruflex.runtime import builtin_runtime_registry
    from ruflex.runtime.errors import RuntimeErrorBase
    try:
        builtin_runtime_registry().resolve_component("explainer", method)
    except RuntimeErrorBase as error:
        raise EvidenceJobError(f"Explanation runtime is unavailable: {error.code}: {error.message}") from error
    job = _new_job(
        kind="explanation_generation", execution_backend_key=execution_backend_key,
        request={"run_id": str(run_id), "sample": sample, "method": method},
        message="Queued for frozen execution backend.",
        log=["Request persisted before execution-backend submission."],
    )
    persist_job(project_root, job)
    _submit(project_root, job)
    return load_job(project_root, job.job_id)


def start_explanation_check_job(project_root: Path, *, explanation_id: UUID, validator_key: str = "native_explanation_validator", execution_backend_key: str = "local_executor") -> Job:
    from ruflex.runtime import builtin_runtime_registry
    from ruflex.runtime.errors import RuntimeErrorBase
    try:
        builtin_runtime_registry().resolve_component("explanation_validator", validator_key)
    except RuntimeErrorBase as error:
        raise EvidenceJobError(f"Validator runtime is unavailable: {error.code}: {error.message}") from error
    job = _new_job(
        kind="explanation_check", execution_backend_key=execution_backend_key,
        request={"explanation_id": str(explanation_id), "validator_key": validator_key},
        message="Queued for LocalExecutor.",
        log=["Request persisted before LocalExecutor submission."],
    )
    persist_job(project_root, job)
    _submit(project_root, job)
    return load_job(project_root, job.job_id)


def _start(project_root: Path, kind: str) -> Job:
    job = _new_job(kind, message="Queued for LocalExecutor.", log=["Request persisted before LocalExecutor submission."])
    persist_job(project_root, job)
    _submit(project_root, job)
    return load_job(project_root, job.job_id)


def start_assurance_case_job(project_root: Path) -> Job:
    return _start(project_root, "assurance_case")


def start_verification_bundle_export_job(project_root: Path) -> Job:
    return _start(project_root, "verification_bundle_export")
