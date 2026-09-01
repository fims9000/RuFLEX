from __future__ import annotations

import pytest
from ruflex.application.fis import diagnose_fis, evaluate_fis, evaluate_response_surface, list_fis_revisions, load_fis, persist_fis
from ruflex.domain.fis import AntecedentClause, FISSpec, FuzzyRule, FuzzyVariable, MembershipFunction, SugenoConsequent


@pytest.mark.parametrize(("kind", "parameters"), [
    ("triangular", (0.0, 0.5, 1.0)), ("trapezoidal", (0.0, 0.25, 0.75, 1.0)),
    ("gaussian", (0.5, 0.2)), ("bell", (0.2, 2.0, 0.5)), ("sigmoid", (8.0, 0.5)),
    ("s_shape", (0.2, 0.8)), ("z_shape", (0.2, 0.8)), ("pi_shape", (0.1, 0.3, 0.7, 0.9)),
])
def test_canonical_membership_families_validate_their_real_parameter_shapes(kind, parameters) -> None:
    assert MembershipFunction(name="term", kind=kind, parameters=parameters).kind == kind


def test_membership_family_rejects_invalid_order_and_nonpositive_width() -> None:
    with pytest.raises(ValueError): MembershipFunction(name="bad", kind="gaussian", parameters=(0.5, 0.0))
    with pytest.raises(ValueError): MembershipFunction(name="bad", kind="trapezoidal", parameters=(0.5, 0.2, 0.7, 1.0))


def test_sugeno_constant_and_linear_consequents_are_exactly_executable(tmp_path) -> None:
    source = FuzzyVariable(
        name="temperature", minimum=0, maximum=10,
        terms=[MembershipFunction(name="Warm", parameters=(0, 5, 10))],
    )
    output = FuzzyVariable(
        name="risk", minimum=0, maximum=20,
        terms=[MembershipFunction(name="placeholder", parameters=(0, 10, 20))], role="output",
    )
    constant = FISSpec(
        name="constant", system_type="sugeno", inputs=[source], output=output,
        rules=[FuzzyRule(name="constant", clauses=[AntecedentClause(variable="temperature", term="Warm")], output_term="placeholder", sugeno_consequent=SugenoConsequent(kind="constant", constant=7.0))],
    )
    linear = constant.model_copy(update={"rules": [constant.rules[0].model_copy(update={"sugeno_consequent": SugenoConsequent(kind="linear", coefficients={"temperature": 2.0}, intercept=1.0)})]})
    assert evaluate_fis(constant, {"temperature": 5}).output == pytest.approx(7.0)
    evaluated = evaluate_fis(linear, {"temperature": 5})
    assert evaluated.output == pytest.approx(11.0)
    assert evaluated.trace.rules[0].consequent_value == pytest.approx(11.0)
    (tmp_path / "models" / "fis").mkdir(parents=True)
    persisted = persist_fis(tmp_path, linear)
    restored = load_fis(tmp_path)
    assert restored.semantic_hash == persisted.semantic_hash
    assert evaluate_fis(restored, {"temperature": 5}).output == pytest.approx(11.0)


def test_sugeno_rejects_missing_or_unknown_linear_consequents() -> None:
    source = FuzzyVariable(name="x", minimum=0, maximum=1, terms=[MembershipFunction(name="mid", parameters=(0, .5, 1))])
    output = FuzzyVariable(name="y", minimum=0, maximum=1, terms=[MembershipFunction(name="out", parameters=(0, .5, 1))], role="output")
    rule = FuzzyRule(name="r", clauses=[AntecedentClause(variable="x", term="mid")], output_term="out")
    with pytest.raises(ValueError, match="Sugeno"):
        FISSpec(name="invalid", system_type="sugeno", inputs=[source], output=output, rules=[rule])
    with pytest.raises(ValueError, match="unknown input"):
        FISSpec(
            name="unknown", system_type="sugeno", inputs=[source], output=output,
            rules=[rule.model_copy(update={"sugeno_consequent": SugenoConsequent(kind="linear", coefficients={"missing": 1.0}, intercept=0.0)})],
        )


def test_response_surface_is_real_canonical_evaluation_over_selected_inputs() -> None:
    x = FuzzyVariable(name="x", minimum=0, maximum=1, terms=[MembershipFunction(name="mid", parameters=(0, .5, 1))])
    y = FuzzyVariable(name="y", minimum=0, maximum=1, terms=[MembershipFunction(name="mid", parameters=(0, .5, 1))])
    output = FuzzyVariable(name="risk", minimum=0, maximum=1, terms=[MembershipFunction(name="out", parameters=(0, .5, 1))], role="output")
    spec = FISSpec(name="surface", system_type="sugeno", inputs=[x, y], output=output, rules=[FuzzyRule(name="r", clauses=[AntecedentClause(variable="x", term="mid"), AntecedentClause(variable="y", term="mid")], output_term="out", sugeno_consequent=SugenoConsequent(kind="linear", coefficients={"x": 1, "y": 2}, intercept=0))])
    surface = evaluate_response_surface(spec, x_variable="x", y_variable="y", resolution=3)
    assert len(surface.samples) == 9
    assert surface.samples[4].output == pytest.approx(1.5)
    assert surface.samples[0].output is None


def test_saved_fis_preserves_named_immutable_revision_history(tmp_path) -> None:
    source = FuzzyVariable(name="x", minimum=0, maximum=1, terms=[MembershipFunction(name="mid", parameters=(0, .5, 1))])
    output = FuzzyVariable(name="y", minimum=0, maximum=1, terms=[MembershipFunction(name="out", parameters=(0, .5, 1))], role="output")
    spec = FISSpec(name="revision", inputs=[source], output=output, rules=[FuzzyRule(name="r", clauses=[AntecedentClause(variable="x", term="mid")], output_term="out")])
    persist_fis(tmp_path, spec)
    changed = spec.model_copy(update={"rules": [spec.rules[0].model_copy(update={"weight": .6})]})
    saved = persist_fis(tmp_path, changed)
    revisions = list_fis_revisions(tmp_path, str(saved.fis_id))
    assert len(revisions) == 2
    assert revisions[-1].semantic_hash == saved.semantic_hash
    assert revisions[0].rules[0].weight == pytest.approx(1.0)


def test_fis_diagnostics_are_structural_warnings_not_mutations() -> None:
    source = FuzzyVariable(
        name="x", minimum=0, maximum=1,
        terms=[
            MembershipFunction(name="one", parameters=(0, 0, 0.2)),
            MembershipFunction(name="one-copy", parameters=(0, 0, 0.2)),
        ],
    )
    output = FuzzyVariable(name="y", role="output", minimum=0, maximum=1, terms=[MembershipFunction(name="out", parameters=(0, .5, 1))])
    spec = FISSpec(name="diagnostics", inputs=[source], output=output, rules=[FuzzyRule(name="r", clauses=[AntecedentClause(variable="x", term="one")], output_term="out")])
    findings = diagnose_fis(spec)
    assert {finding["code"] for finding in findings} >= {"UNCOVERED_INTERVAL", "EXCESSIVE_OVERLAP", "NEAR_DUPLICATE_TERM"}
    assert spec.inputs[0].terms[0].name == "one"


def test_membership_lock_persists_without_changing_executable_semantic_hash(tmp_path) -> None:
    source = FuzzyVariable(
        name="x", minimum=0, maximum=1,
        terms=[MembershipFunction(name="mid", parameters=(0, .5, 1), locked=False)],
    )
    output = FuzzyVariable(
        name="y", minimum=0, maximum=1, role="output",
        terms=[MembershipFunction(name="out", parameters=(0, .5, 1))],
    )
    spec = FISSpec(
        name="lock-metadata", inputs=[source], output=output,
        rules=[FuzzyRule(name="r", clauses=[AntecedentClause(variable="x", term="mid")], output_term="out")],
    )
    first = persist_fis(tmp_path, spec)
    locked = first.model_copy(deep=True)
    locked.inputs[0].terms[0].locked = True
    second = persist_fis(tmp_path, locked)
    assert second.semantic_hash == first.semantic_hash
    assert load_fis(tmp_path).inputs[0].terms[0].locked is True
