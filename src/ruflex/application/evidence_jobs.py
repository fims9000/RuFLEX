"""Persisted LocalExecutor orchestration for potentially expensive XAI work."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from ruflex.application.execution import local_executor
from ruflex.application.jobs import Job, JobStatus, load_job, persist_job


class EvidenceJobError(ValueError):
    pass


_METHODS = {"occlusion", "integrated_gradients", "gradient_shap", "shap", "tree_shap"}


def _append(job: Job, message: str) -> None:
    job.message = message
    job.log.append(message)


def _generate(project_root: Path, request: dict) -> str:
    from ruflex.application.evidence import (
        create_gradient_shap_explanation,
        create_integrated_gradients_explanation,
        create_occlusion_explanation,
        create_permutation_shap_explanation,
        create_tree_shap_explanation,
    )
    run_id = UUID(request["run_id"])
    sample = {str(name): float(value) for name, value in request["sample"].items()}
    method = request["method"]
    if method == "integrated_gradients":
        result = create_integrated_gradients_explanation(project_root, run_id, sample)
    elif method == "gradient_shap":
        result = create_gradient_shap_explanation(project_root, run_id, sample)
    elif method == "shap":
        result = create_permutation_shap_explanation(project_root, run_id, sample)
    elif method == "tree_shap":
        result = create_tree_shap_explanation(project_root, run_id, sample)
    else:
        result = create_occlusion_explanation(project_root, run_id, sample)
    return str(result.explanation_id)


def _execute(project_root: Path, job_id: UUID) -> None:
    job = load_job(project_root, job_id)
    if job.status != JobStatus.QUEUED:
        return
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    _append(job, "LocalExecutor started persisted evidence operation.")
    persist_job(project_root, job)
    try:
        if job.kind == "explanation_generation":
            output = {"explanation_id": _generate(project_root, job.request)}
        elif job.kind == "explanation_check":
            from ruflex.application.evidence import check_explanation
            result = check_explanation(project_root, UUID(job.request["explanation_id"]))
            output = {"check_id": str(result.check_id)}
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
) -> Job:
    if method not in _METHODS:
        raise EvidenceJobError(f"Unsupported explanation method {method!r}.")
    job = Job(
        kind="explanation_generation",
        request={"run_id": str(run_id), "sample": sample, "method": method},
        message="Queued for LocalExecutor.",
        log=["Request persisted before LocalExecutor submission."],
    )
    persist_job(project_root, job)
    local_executor.submit(project_root=project_root, job_id=job.job_id, operation=lambda: _execute(project_root, job.job_id))
    return load_job(project_root, job.job_id)


def start_explanation_check_job(project_root: Path, *, explanation_id: UUID) -> Job:
    job = Job(
        kind="explanation_check",
        request={"explanation_id": str(explanation_id)},
        message="Queued for LocalExecutor.",
        log=["Request persisted before LocalExecutor submission."],
    )
    persist_job(project_root, job)
    local_executor.submit(project_root=project_root, job_id=job.job_id, operation=lambda: _execute(project_root, job.job_id))
    return load_job(project_root, job.job_id)
