from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .enums import NormalizationMode, VariableRole
from .membership import MembershipFunctionSpec, membership_from_dict


@dataclass(frozen=True)
class VariableSpec:
    name: str
    membership: MembershipFunctionSpec
    value_range: tuple[float, float] | None = None
    data_type: str = "continuous"
    role: VariableRole = VariableRole.INPUT
    normalization: NormalizationMode = NormalizationMode.STANDARD

    @property
    def term_names(self) -> tuple[str, ...]:
        return self.membership.term_names

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "membership": self.membership.to_dict(),
            "value_range": list(self.value_range) if self.value_range is not None else None,
            "data_type": self.data_type,
            "role": self.role.value,
            "normalization": self.normalization.value,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VariableSpec":
        value_range = payload.get("value_range")
        return cls(
            name=payload["name"],
            membership=membership_from_dict(payload["membership"]),
            value_range=None if value_range is None else (float(value_range[0]), float(value_range[1])),
            data_type=payload.get("data_type", "continuous"),
            role=VariableRole(payload.get("role", VariableRole.INPUT.value)),
            normalization=NormalizationMode(payload.get("normalization", NormalizationMode.STANDARD.value)),
        )

