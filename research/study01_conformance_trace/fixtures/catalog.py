from __future__ import annotations

from uuid import UUID

from ruflex.application.fis import with_semantic_hash
from ruflex.domain.fis import AntecedentClause, FISSpec, FuzzyRule, FuzzyVariable, MembershipFunction, OperatorSet, SugenoConsequent


def _term(name: str, *parameters: float) -> MembershipFunction:
    return MembershipFunction(name=name, kind="triangular", parameters=parameters)


def dev_mamdani() -> FISSpec:
    """One-dimensional, symmetric, declared 401-node centroid DEV system."""
    x = FuzzyVariable(name="x", minimum=0.0, maximum=1.0, terms=[_term("low", 0.0, 0.0, 1.0), _term("high", 0.0, 1.0, 1.0)])
    y = FuzzyVariable(name="y", minimum=0.0, maximum=1.0, role="output", terms=[_term("low", 0.0, 0.0, 1.0), _term("high", 0.0, 1.0, 1.0)])
    return with_semantic_hash(FISSpec(
        fis_id=UUID("00000000-0000-0000-0000-000000000101"), name="DEV M01 symmetric Mamdani", inputs=[x], output=y,
        rules=[
            FuzzyRule(rule_id=UUID("00000000-0000-0000-0000-000000001101"), name="low to low", clauses=[AntecedentClause(variable="x", term="low")], output_term="low"),
            FuzzyRule(rule_id=UUID("00000000-0000-0000-0000-000000001102"), name="high to high", clauses=[AntecedentClause(variable="x", term="high")], output_term="high"),
        ], operators=OperatorSet(),
    ))


def dev_sugeno() -> FISSpec:
    """One-dimensional zero-order Sugeno DEV system with derivable output."""
    x = FuzzyVariable(name="x", minimum=0.0, maximum=1.0, terms=[_term("low", 0.0, 0.0, 1.0), _term("high", 0.0, 1.0, 1.0)])
    y = FuzzyVariable(name="y", minimum=0.0, maximum=1.0, role="output", terms=[_term("constant", 0.0, 0.5, 1.0)])
    return with_semantic_hash(FISSpec(
        fis_id=UUID("00000000-0000-0000-0000-000000000201"), name="DEV S01 zero-order Sugeno", system_type="sugeno", inputs=[x], output=y,
        rules=[
            FuzzyRule(rule_id=UUID("00000000-0000-0000-0000-000000002101"), name="low to 0.2", clauses=[AntecedentClause(variable="x", term="low")], output_term="constant", sugeno_consequent=SugenoConsequent(kind="constant", constant=0.2)),
            FuzzyRule(rule_id=UUID("00000000-0000-0000-0000-000000002102"), name="high to 0.8", clauses=[AntecedentClause(variable="x", term="high")], output_term="constant", sugeno_consequent=SugenoConsequent(kind="constant", constant=0.8)),
        ], operators=OperatorSet(),
    ))


def curated_ids() -> tuple[str, ...]:
    return ("M01", "M02", "M03", "M04", "M05", "M06", "S01", "S02", "S03", "S04", "S05", "S06")
