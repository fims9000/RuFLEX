"""Typed declaration for the persisted local execution backend."""
from ruflex.runtime.contracts import ExecutionBackendDescriptor, RuntimeIdentity


LOCAL_EXECUTOR = ExecutionBackendDescriptor(
    identity=RuntimeIdentity(key="local_executor", version="1", provider="ruflex.builtin", kind="execution_backend"),
    supports_cancel=True,
    supports_resume=True,
)
