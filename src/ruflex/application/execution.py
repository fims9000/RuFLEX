"""Local-first execution backends for persisted long-running product jobs."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Lock, Thread
from typing import Literal, Protocol
from uuid import UUID


class ExecutionBackend(Protocol):
    """Product lifecycle boundary; services retain canonical persisted job state."""

    name: str

    def submit(self, *, project_root: Path, job_id: UUID, operation: Callable[[], None]) -> bool: ...
    def is_active(self, *, project_root: Path, job_id: UUID) -> bool: ...
    def status(self, *, project_root: Path, job_id: UUID) -> Literal["ACTIVE", "IDLE"]: ...
    def cancel(self, *, project_root: Path, job_id: UUID) -> bool: ...
    def resume(self, *, project_root: Path, job_id: UUID, operation: Callable[[], None]) -> bool: ...


class LocalExecutor:
    """In-process backend with duplicate submission protection.

    The thread is deliberately not the canonical job state.  Services persist
    their complete job request before submission, so an interrupted process can
    be inspected and explicitly resumed without inventing a new experiment.
    """

    name = "LOCAL"
    _lock = Lock()
    _threads: dict[tuple[Path, UUID], Thread] = {}
    _cancel_requested: set[tuple[Path, UUID]] = set()

    def is_active(self, *, project_root: Path, job_id: UUID) -> bool:
        with self._lock:
            thread = self._threads.get((Path(project_root).resolve(), job_id))
            return bool(thread and thread.is_alive())

    def submit(self, *, project_root: Path, job_id: UUID, operation: Callable[[], None]) -> bool:
        key = (Path(project_root).resolve(), job_id)
        with self._lock:
            active = self._threads.get(key)
            if active is not None and active.is_alive():
                return False
            def runner() -> None:
                try:
                    operation()
                finally:
                    with self._lock:
                        self._threads.pop(key, None)
            thread = Thread(target=runner, name=f"ruflex-{job_id}", daemon=True)
            self._threads[key] = thread
            self._cancel_requested.discard(key)
            thread.start()
        return True

    def status(self, *, project_root: Path, job_id: UUID) -> Literal["ACTIVE", "IDLE"]:
        return "ACTIVE" if self.is_active(project_root=project_root, job_id=job_id) else "IDLE"

    def cancel(self, *, project_root: Path, job_id: UUID) -> bool:
        """Record a cooperative cancellation request without killing a thread.

        Persisted job services remain the source of truth and own the actual
        operation-specific stop state; this backend records delivery rather
        than claiming unsafe forceful thread termination.
        """
        key = (Path(project_root).resolve(), job_id)
        with self._lock:
            self._cancel_requested.add(key)
        return True

    def resume(self, *, project_root: Path, job_id: UUID, operation: Callable[[], None]) -> bool:
        return self.submit(project_root=project_root, job_id=job_id, operation=operation)


local_executor = LocalExecutor()
