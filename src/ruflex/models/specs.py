from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ruflex.core.rules import RuleBaseSpec
from ruflex.core.variables import VariableSpec


@dataclass(frozen=True)
class TransparentBlockSpec:
    name: str
    input_indices: tuple[int, ...]
    variables: tuple[VariableSpec, ...]
    n_concepts: int
    concept_names: tuple[str, ...] | None = None
    max_rule_arity: int | None = None
    max_rules: int | None = None
    gate_init: float = 0.0
    rule_base: RuleBaseSpec | None = None
    rule_generation_mode: str = "prototype"
    prototype_term_limit: int = 2
    prototype_variable_pool_size: int | None = None
    prototype_sample_size: int | None = 256

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "input_indices": list(self.input_indices),
            "variables": [variable.to_dict() for variable in self.variables],
            "n_concepts": self.n_concepts,
            "concept_names": list(self.concept_names) if self.concept_names is not None else None,
            "max_rule_arity": self.max_rule_arity,
            "max_rules": self.max_rules,
            "gate_init": self.gate_init,
            "rule_base": None if self.rule_base is None else self.rule_base.to_dict(),
            "rule_generation_mode": self.rule_generation_mode,
            "prototype_term_limit": self.prototype_term_limit,
            "prototype_variable_pool_size": self.prototype_variable_pool_size,
            "prototype_sample_size": self.prototype_sample_size,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TransparentBlockSpec":
        concept_names = payload.get("concept_names")
        return cls(
            name=payload["name"],
            input_indices=tuple(int(index) for index in payload["input_indices"]),
            variables=tuple(VariableSpec.from_dict(item) for item in payload["variables"]),
            n_concepts=int(payload["n_concepts"]),
            concept_names=None if concept_names is None else tuple(concept_names),
            max_rule_arity=payload.get("max_rule_arity"),
            max_rules=payload.get("max_rules"),
            gate_init=float(payload.get("gate_init", 0.0)),
            rule_base=(
                None if payload.get("rule_base") is None else RuleBaseSpec.from_dict(payload["rule_base"])
            ),
            rule_generation_mode=payload.get("rule_generation_mode", "prototype"),
            prototype_term_limit=int(payload.get("prototype_term_limit", 2)),
            prototype_variable_pool_size=payload.get("prototype_variable_pool_size"),
            prototype_sample_size=payload.get("prototype_sample_size"),
        )


@dataclass(frozen=True)
class StageSpec:
    name: str
    blocks: tuple[TransparentBlockSpec, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "blocks": [block.to_dict() for block in self.blocks]}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StageSpec":
        return cls(
            name=payload["name"],
            blocks=tuple(TransparentBlockSpec.from_dict(item) for item in payload["blocks"]),
        )


@dataclass(frozen=True)
class DecisionLayerSpec:
    name: str
    variables: tuple[VariableSpec, ...]
    output_dim: int
    output_names: tuple[str, ...] | None = None
    max_rule_arity: int | None = None
    max_rules: int | None = None
    gate_init: float = 0.0
    rule_base: RuleBaseSpec | None = None
    rule_generation_mode: str = "prototype"
    prototype_term_limit: int = 2
    prototype_variable_pool_size: int | None = None
    prototype_sample_size: int | None = 256

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "variables": [variable.to_dict() for variable in self.variables],
            "output_dim": self.output_dim,
            "output_names": list(self.output_names) if self.output_names is not None else None,
            "max_rule_arity": self.max_rule_arity,
            "max_rules": self.max_rules,
            "gate_init": self.gate_init,
            "rule_base": None if self.rule_base is None else self.rule_base.to_dict(),
            "rule_generation_mode": self.rule_generation_mode,
            "prototype_term_limit": self.prototype_term_limit,
            "prototype_variable_pool_size": self.prototype_variable_pool_size,
            "prototype_sample_size": self.prototype_sample_size,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DecisionLayerSpec":
        output_names = payload.get("output_names")
        return cls(
            name=payload["name"],
            variables=tuple(VariableSpec.from_dict(item) for item in payload["variables"]),
            output_dim=int(payload["output_dim"]),
            output_names=None if output_names is None else tuple(output_names),
            max_rule_arity=payload.get("max_rule_arity"),
            max_rules=payload.get("max_rules"),
            gate_init=float(payload.get("gate_init", 0.0)),
            rule_base=(
                None if payload.get("rule_base") is None else RuleBaseSpec.from_dict(payload["rule_base"])
            ),
            rule_generation_mode=payload.get("rule_generation_mode", "prototype"),
            prototype_term_limit=int(payload.get("prototype_term_limit", 2)),
            prototype_variable_pool_size=payload.get("prototype_variable_pool_size"),
            prototype_sample_size=payload.get("prototype_sample_size"),
        )


@dataclass(frozen=True)
class HierarchicalModelSpec:
    input_dim: int
    stages: tuple[StageSpec, ...]
    decision_layer: DecisionLayerSpec

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "deep_fuzzy_feature_learning",
            "input_dim": self.input_dim,
            "stages": [stage.to_dict() for stage in self.stages],
            "decision_layer": self.decision_layer.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HierarchicalModelSpec":
        return cls(
            input_dim=int(payload["input_dim"]),
            stages=tuple(StageSpec.from_dict(item) for item in payload["stages"]),
            decision_layer=DecisionLayerSpec.from_dict(payload["decision_layer"]),
        )


@dataclass(frozen=True)
class ShallowModelSpec:
    input_dim: int
    feature_block: TransparentBlockSpec
    decision_layer: DecisionLayerSpec
    stage_name: str = "flat_stage"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "flat_neuro_fuzzy",
            "input_dim": self.input_dim,
            "feature_block": self.feature_block.to_dict(),
            "decision_layer": self.decision_layer.to_dict(),
            "stage_name": self.stage_name,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ShallowModelSpec":
        return cls(
            input_dim=int(payload["input_dim"]),
            feature_block=TransparentBlockSpec.from_dict(payload["feature_block"]),
            decision_layer=DecisionLayerSpec.from_dict(payload["decision_layer"]),
            stage_name=payload.get("stage_name", "flat_stage"),
        )


def model_spec_from_dict(payload: dict[str, Any]) -> HierarchicalModelSpec | ShallowModelSpec:
    kind = payload["kind"]
    if kind == "deep_fuzzy_feature_learning":
        return HierarchicalModelSpec.from_dict(payload)
    if kind == "flat_neuro_fuzzy":
        return ShallowModelSpec.from_dict(payload)
    raise ValueError(f"Unsupported model spec kind: {kind!r}.")
