"""Typed adapter for the native replay/integrity validator."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from ruflex.runtime.contracts import RuntimeIdentity, ValidatorDescriptor, ValidatorRequest, ValidatorResult


NATIVE_EXPLANATION_VALIDATOR = ValidatorDescriptor(
    identity=RuntimeIdentity(key="native_explanation_validator", version="1", provider="ruflex.builtin", kind="explanation_validator"),
    checks=("identity", "replay_integrity", "numerical_completeness"),
    limitations=("Replay integrity checks bind persisted artifacts; they do not establish causal explanation validity.",),
)


@dataclass(frozen=True)
class _NativeExplanationValidatorAdapter:
    descriptor: ValidatorDescriptor = NATIVE_EXPLANATION_VALIDATOR

    def validate(self, request: ValidatorRequest) -> ValidatorResult:
        from ruflex.application.evidence import _native_check_explanation

        root = Path(request.input_bindings["project_root"])
        check = _native_check_explanation(root, UUID(request.explanation_id), validator_key=self.descriptor.identity.key)
        status = "FAIL" if check.status == "FAILED" else "PASS"
        return ValidatorResult(
            status=status,
            validator_identity=self.descriptor.identity,
            checks=[item.model_dump(mode="json") for item in check.checks],
            limits={"check_id": str(check.check_id)},
        )


def native_explanation_validator_adapter() -> _NativeExplanationValidatorAdapter:
    return _NativeExplanationValidatorAdapter()
