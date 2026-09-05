"""Typed declaration for the persisted local execution backend."""
from ruflex.runtime.contracts import ExecutionBackendDescriptor, RuntimeIdentity


LOCAL_EXECUTOR = ExecutionBackendDescriptor(
    identity=RuntimeIdentity(key="local_executor", version="1", provider="ruflex.builtin", kind="execution_backend"),
    supports_cancel=True,
    supports_resume=True,
)


def resolve_execution_backend(key: str = "local_executor"):
    """Resolve a frozen backend descriptor before exposing its implementation.

    The application owns persisted Job state; this function only bridges the
    trusted runtime identity to the local product-native executor.
    """
    from ruflex.runtime import builtin_runtime_registry
    from ruflex.runtime.errors import RuntimeNotFoundError

    descriptor = builtin_runtime_registry().resolve_component("execution_backend", key)
    if descriptor.identity.key != LOCAL_EXECUTOR.identity.key:
        raise RuntimeNotFoundError(key)
    from ruflex.application.execution import local_executor

    return descriptor, local_executor
