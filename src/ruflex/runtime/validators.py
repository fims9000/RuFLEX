"""Typed declaration for the native replay/integrity validator."""
from ruflex.runtime.contracts import RuntimeIdentity, ValidatorDescriptor


NATIVE_EXPLANATION_VALIDATOR = ValidatorDescriptor(
    identity=RuntimeIdentity(key="native_explanation_validator", version="1", provider="ruflex.builtin", kind="explanation_validator"),
    checks=("identity", "replay_integrity", "numerical_completeness"),
    limitations=("Replay integrity checks bind persisted artifacts; they do not establish causal explanation validity.",),
)
