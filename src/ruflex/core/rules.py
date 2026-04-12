from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AntecedentSpec:
    variable_name: str
    term_name: str

    def to_dict(self) -> dict[str, Any]:
        return {"variable_name": self.variable_name, "term_name": self.term_name}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AntecedentSpec":
        return cls(variable_name=payload["variable_name"], term_name=payload["term_name"])


@dataclass(frozen=True)
class RuleSpec:
    identifier: str
    antecedents: tuple[AntecedentSpec, ...]
    aggregation: str = "product"
    weight: float = 1.0
    consequent: dict[str, float] = field(default_factory=dict)
    layer_name: str | None = None
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "identifier": self.identifier,
            "antecedents": [antecedent.to_dict() for antecedent in self.antecedents],
            "aggregation": self.aggregation,
            "weight": self.weight,
            "consequent": dict(self.consequent),
            "layer_name": self.layer_name,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuleSpec":
        return cls(
            identifier=payload["identifier"],
            antecedents=tuple(AntecedentSpec.from_dict(item) for item in payload["antecedents"]),
            aggregation=payload.get("aggregation", "product"),
            weight=float(payload.get("weight", 1.0)),
            consequent=dict(payload.get("consequent", {})),
            layer_name=payload.get("layer_name"),
            active=bool(payload.get("active", True)),
        )


@dataclass(frozen=True)
class RuleBaseSpec:
    rules: tuple[RuleSpec, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"rules": [rule.to_dict() for rule in self.rules]}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuleBaseSpec":
        return cls(rules=tuple(RuleSpec.from_dict(item) for item in payload.get("rules", ())))

    @property
    def active_rules(self) -> tuple[RuleSpec, ...]:
        return tuple(rule for rule in self.rules if rule.active)

