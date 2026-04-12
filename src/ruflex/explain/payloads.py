from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SerializablePayload:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TermMembershipPayload(SerializablePayload):
    term_name: str
    membership: float


@dataclass(frozen=True)
class VariableFuzzificationPayload(SerializablePayload):
    variable_name: str
    input_value: float
    memberships: tuple[TermMembershipPayload, ...]


@dataclass(frozen=True)
class RuleActivationPayload(SerializablePayload):
    rule_name: str
    rule_text: str
    normalized_weight: float
    raw_weight: float
    outputs: tuple[float, ...]


@dataclass(frozen=True)
class RuleContributionPayload(SerializablePayload):
    rule_name: str
    rule_text: str
    normalized_weight: float
    contribution: tuple[float, ...]


@dataclass(frozen=True)
class BlockDashboardPayload(SerializablePayload):
    stage_name: str | None
    block_name: str
    layer_kind: str
    input_values: tuple[float, ...]
    output_names: tuple[str, ...]
    output_values: tuple[float, ...]
    variable_fuzzification: tuple[VariableFuzzificationPayload, ...]
    top_rules: tuple[RuleActivationPayload, ...]


@dataclass(frozen=True)
class HiddenConceptPayload(SerializablePayload):
    stage_name: str
    block_name: str
    concept_name: str
    value: float
    top_rule_contributions: tuple[RuleContributionPayload, ...]


@dataclass(frozen=True)
class DecisionConceptContributionPayload(SerializablePayload):
    concept_name: str
    source_stage_name: str | None
    source_block_name: str | None
    concept_value: float
    contribution: tuple[float, ...]


@dataclass(frozen=True)
class SampleDashboardPayload(SerializablePayload):
    sample_index: int
    raw_inputs: dict[str, float] | None
    normalized_inputs: tuple[float, ...]
    prediction: tuple[float, ...]
    hidden_blocks: tuple[BlockDashboardPayload, ...]
    decision_block: BlockDashboardPayload
    hidden_concepts: tuple[HiddenConceptPayload, ...]
    decision_concept_contributions: tuple[DecisionConceptContributionPayload, ...]
    bias_contribution: tuple[float, ...]
    top_decision_rules: tuple[RuleContributionPayload, ...]


@dataclass(frozen=True)
class RuleRecordPayload(SerializablePayload):
    layer_kind: str
    stage_name: str | None
    block_name: str
    rule_index: int
    rule_name: str
    antecedent: str
    consequent: str
    gate_probability: float


@dataclass(frozen=True)
class ExplainabilityReportPayload(SerializablePayload):
    model_kind: str
    model_report: str
    rules: tuple[RuleRecordPayload, ...]

