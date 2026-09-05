"""Read-time compatibility mapping for pre-runtime persisted objects."""
from __future__ import annotations

from ruflex.domain.training import TrainingRun
from ruflex.runtime.contracts import RuntimeIdentity
from ruflex.runtime.registry import builtin_runtime_registry


def resolved_run_identity(run: TrainingRun) -> RuntimeIdentity | None:
    """Return a bound or legacy-compatible identity without mutating evidence."""
    if all((run.adapter_key, run.adapter_version, run.adapter_provider, run.adapter_kind)):
        return RuntimeIdentity(
            key=run.adapter_key, version=run.adapter_version,
            provider=run.adapter_provider, kind=run.adapter_kind,
        )
    try:
        return builtin_runtime_registry().resolve_training_model_kind(run.model_kind).descriptor.identity
    except Exception:
        return None


def bind_new_run_to_runtime(run: TrainingRun) -> TrainingRun:
    """Attach identity to a new run; legacy data is never rewritten on read."""
    adapter = builtin_runtime_registry().resolve_training_model_kind(run.model_kind)
    identity = adapter.descriptor.identity
    snapshot = builtin_runtime_registry().snapshot()
    run.schema_version = 3
    run.adapter_key = identity.key
    run.adapter_version = identity.version
    run.adapter_provider = identity.provider
    run.adapter_kind = identity.kind
    run.runtime_capability_snapshot_hash = snapshot["sha256"]
    return run
