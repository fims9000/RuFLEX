"""Typed runtime errors safe to expose through application/API boundaries."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(eq=False)
class RuntimeErrorBase(RuntimeError):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


class RuntimeNotFoundError(RuntimeErrorBase):
    def __init__(self, key: str) -> None:
        super().__init__("RUNTIME_NOT_FOUND", f"Runtime component {key!r} is not registered.")


class RuntimeDuplicateError(RuntimeErrorBase):
    def __init__(self, key: str) -> None:
        super().__init__("RUNTIME_DUPLICATE", f"Runtime component {key!r} is already registered.")


class RuntimeUntrustedError(RuntimeErrorBase):
    def __init__(self, key: str) -> None:
        super().__init__("RUNTIME_UNTRUSTED", f"Runtime component {key!r} is not trusted for execution.")


class RuntimeVersionMismatchError(RuntimeErrorBase):
    def __init__(self, key: str, version: str) -> None:
        super().__init__("RUNTIME_VERSION_MISMATCH", f"Runtime component {key!r} does not provide version {version!r}.")


class RuntimeDependencyMissingError(RuntimeErrorBase):
    def __init__(self, key: str, dependency: str) -> None:
        super().__init__("RUNTIME_DEPENDENCY_MISSING", f"Runtime component {key!r} requires unavailable dependency {dependency!r}.")


class RuntimeIncompatibleError(RuntimeErrorBase):
    def __init__(self, message: str) -> None:
        super().__init__("RUNTIME_INCOMPATIBLE", message)


class RuntimeExecutionError(RuntimeErrorBase):
    def __init__(self, key: str) -> None:
        super().__init__("RUNTIME_EXECUTION_FAILED", f"Runtime component {key!r} failed during execution.")


class CapabilityUnavailableError(RuntimeErrorBase):
    def __init__(self, message: str) -> None:
        super().__init__("CAPABILITY_UNAVAILABLE", message)
