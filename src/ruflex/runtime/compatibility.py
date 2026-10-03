"""Strict read-time compatibility for persisted model runtime identities."""
from __future__ import annotations

from ruflex.domain.training import TrainingRun
from ruflex.runtime.contracts import RuntimeIdentity
from ruflex.runtime.errors import RuntimeIncompatibleError
from ruflex.runtime.registry import RuntimeRegistry, builtin_runtime_registry


LEGACY_MODEL_KIND_TO_ADAPTER: dict[str, tuple[str, str]] = {
    "flat_neuro_fuzzy": ("native_flat_neuro_fuzzy", "1"),
    "logistic_regression": ("native_linear", "1"),
    "linear_regression": ("native_linear", "1"),
    "decision_tree": ("native_decision_tree", "1"),
    "random_forest": ("native_random_forest", "1"),
    "gradient_boosting": ("native_gradient_boosting", "1"),
}


def _identity_fields_absent(run: TrainingRun) -> bool:
    return not any((run.adapter_key, run.adapter_version, run.adapter_provider, run.adapter_kind))


def resolve_run_adapter(run: TrainingRun, *, registry: RuntimeRegistry | None = None):
    """Resolve exact persisted identity, or map a wholly unbound legacy run.

    A partial or invalid identity is never treated as legacy. Legacy mapping is
    pure and read-only; it does not mutate the TrainingRun or its source JSON.
    """
    runtime_registry = registry or builtin_runtime_registry()
    if _identity_fields_absent(run) and run.schema_version < 3:
        legacy = LEGACY_MODEL_KIND_TO_ADAPTER.get(run.model_kind)
        if legacy is None:
            raise RuntimeIncompatibleError(
                f"Legacy model kind {run.model_kind!r} has no deterministic model-adapter mapping."
            )
        key, version = legacy
        adapter = runtime_registry.resolve_model_adapter(key, version=version)
    else:
        required = (run.adapter_key, run.adapter_version, run.adapter_provider, run.adapter_kind)
        if not all(required):
            raise RuntimeIncompatibleError("Persisted model adapter identity is partial; refusing model_kind fallback.")
        adapter = runtime_registry.resolve_model_adapter(run.adapter_key, version=run.adapter_version)
        identity = adapter.descriptor.identity
        if identity.provider != run.adapter_provider or identity.kind != run.adapter_kind:
            raise RuntimeIncompatibleError("Persisted model adapter provider/kind does not match the registered identity.")
    if run.model_kind not in adapter.descriptor.training_model_kinds:
        raise RuntimeIncompatibleError(
            f"Model adapter {adapter.descriptor.identity.key}@{adapter.descriptor.identity.version} "
            f"does not support model kind {run.model_kind!r}."
        )
    return adapter


def resolved_run_identity(
    run: TrainingRun, *, registry: RuntimeRegistry | None = None
) -> RuntimeIdentity | None:
    """Return a valid explicit or deterministic legacy identity, else None."""
    try:
        return resolve_run_adapter(run, registry=registry).descriptor.identity
    except Exception:
        return None


def bind_new_run_to_runtime(run: TrainingRun, *, registry: RuntimeRegistry | None = None) -> TrainingRun:
    """Bind a new run or validate its existing immutable adapter provenance."""
    registry = registry or builtin_runtime_registry()
    if _identity_fields_absent(run):
        legacy = LEGACY_MODEL_KIND_TO_ADAPTER.get(run.model_kind)
        if legacy is None:
            raise RuntimeIncompatibleError(f"No built-in adapter is declared for model kind {run.model_kind!r}.")
        adapter = registry.resolve_model_adapter(legacy[0], version=legacy[1])
        identity = adapter.descriptor.identity
        run.schema_version = max(run.schema_version, 3)
        run.adapter_key = identity.key
        run.adapter_version = identity.version
        run.adapter_provider = identity.provider
        run.adapter_kind = identity.kind
        run.runtime_capability_snapshot_hash = registry.snapshot()["sha256"]
    else:
        adapter = resolve_run_adapter(run, registry=registry)
        identity = adapter.descriptor.identity
        if not run.runtime_capability_snapshot_hash:
            raise RuntimeIncompatibleError("A newly persisted run requires a runtime capability snapshot identity.")
    return run
