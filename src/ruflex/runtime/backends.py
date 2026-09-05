"""Typed adapter for the persisted local execution backend."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from ruflex.runtime.contracts import ExecutionBackendAdapter, ExecutionBackendDescriptor, RuntimeIdentity


LOCAL_EXECUTOR = ExecutionBackendDescriptor(
    identity=RuntimeIdentity(key="local_executor", version="1", provider="ruflex.builtin", kind="execution_backend"),
    supports_cancel=True,
    supports_resume=True,
)


@dataclass(frozen=True)
class _LocalExecutionBackendAdapter:
    descriptor: ExecutionBackendDescriptor = LOCAL_EXECUTOR

    def submit(self, *, project_root: Path, job_id: UUID, operation: Callable[[], None]) -> bool:
        from ruflex.application.execution import local_executor

        return local_executor.submit(project_root=project_root, job_id=job_id, operation=operation)

    def is_active(self, *, project_root: Path, job_id: UUID) -> bool:
        from ruflex.application.execution import local_executor

        return local_executor.is_active(project_root=project_root, job_id=job_id)

    def status(self, *, project_root: Path, job_id: UUID) -> str:
        from ruflex.application.execution import local_executor
        return local_executor.status(project_root=project_root, job_id=job_id)

    def cancel(self, *, project_root: Path, job_id: UUID) -> bool:
        from ruflex.application.execution import local_executor
        return local_executor.cancel(project_root=project_root, job_id=job_id)

    def resume(self, *, project_root: Path, job_id: UUID, operation: Callable[[], None]) -> bool:
        from ruflex.application.execution import local_executor
        return local_executor.resume(project_root=project_root, job_id=job_id, operation=operation)


def local_execution_backend_adapter() -> _LocalExecutionBackendAdapter:
    return _LocalExecutionBackendAdapter()


def resolve_execution_backend(key: str = "local_executor"):
    """Resolve a frozen backend implementation behind persisted job state.

    The application, not a worker, owns the canonical StudyJob/Job evidence;
    a trusted backend only schedules, reports, cancels cooperatively or
    reattaches to that persisted request.
    """
    from ruflex.runtime import builtin_runtime_registry
    from ruflex.runtime.errors import RuntimeNotFoundError

    descriptor = builtin_runtime_registry().resolve_component("execution_backend", key)
    adapter = builtin_runtime_registry().resolve_component_implementation("execution_backend", key)
    if not isinstance(adapter, ExecutionBackendAdapter):
        raise RuntimeNotFoundError(key)
    return descriptor, adapter
