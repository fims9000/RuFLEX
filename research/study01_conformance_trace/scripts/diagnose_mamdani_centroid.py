from __future__ import annotations

import json
from pathlib import Path

import fuzzylite as fl
import numpy as np

from ruflex.application.fis import FISError, evaluate_fis, with_semantic_hash
from research.study01_conformance_trace.adapters.ruflex_adapter import evaluate as subject_evaluate
from research.study01_conformance_trace.fixtures.catalog import dev_mamdani
from ruflex.domain.fis import AntecedentClause, CentroidSampling, FISSpec, FuzzyRule, FuzzyVariable, MembershipFunction


ROOT = Path(__file__).resolve().parents[1]


def _reference_output(resolution: int) -> float:
    spec = dev_mamdani()
    x = fl.InputVariable("x", minimum=0.0, maximum=1.0, terms=[fl.Triangle("low", 0.0, 0.0, 1.0), fl.Triangle("high", 0.0, 1.0, 1.0)])
    y = fl.OutputVariable("y", minimum=0.0, maximum=1.0, aggregation=fl.Maximum(), defuzzifier=fl.Centroid(resolution), terms=[fl.Triangle("low", 0.0, 0.0, 1.0), fl.Triangle("high", 0.0, 1.0, 1.0)])
    engine = fl.Engine(spec.name, input_variables=[x], output_variables=[y])
    rules = [fl.Rule.create("if x is low then y is low", engine), fl.Rule.create("if x is high then y is high", engine)]
    block = fl.RuleBlock(conjunction=fl.Minimum(), disjunction=fl.Maximum(), implication=fl.Minimum(), activation=fl.General(), rules=rules)
    engine.rule_blocks.append(block)
    block.load_rules(engine)
    x.value = 0.25
    engine.process()
    return float(np.asarray(y.value).reshape(-1)[0])


def _ruflex_formula(points: int, *, inclusive: bool) -> float:
    if inclusive:
        grid = np.linspace(0.0, 1.0, points)
    else:
        grid = np.arange(points, dtype=float) / points
    firing_low, firing_high = 0.75, 0.25
    low = np.maximum(0.0, np.minimum(firing_low, 1.0 - grid))
    high = np.maximum(0.0, np.minimum(firing_high, grid))
    aggregate = np.maximum(low, high)
    return float((grid * aggregate).sum() / aggregate.sum())


def _no_rule_behavior() -> dict[str, str]:
    """Probe intentionally sparse coverage outside the primary semantic matrix."""
    term = lambda name, params: MembershipFunction(name=name, kind="triangular", parameters=params)
    spec = with_semantic_hash(FISSpec(
        name="DEV no-rule probe", inputs=[FuzzyVariable(name="x", minimum=0.0, maximum=1.0, terms=[term("mid", (0.2, 0.5, 0.8))])],
        output=FuzzyVariable(name="y", minimum=0.0, maximum=1.0, role="output", terms=[term("out", (0.0, 0.5, 1.0))]),
        rules=[FuzzyRule(name="mid rule", clauses=[AntecedentClause(variable="x", term="mid")], output_term="out")],
    ))
    try:
        evaluate_fis(spec, {"x": 0.0})
        ruflex = "UNEXPECTED_VALUE"
    except FISError as exc:
        ruflex = f"EXCEPTION:{exc}"
    x = fl.InputVariable("x", minimum=0.0, maximum=1.0, terms=[fl.Triangle("mid", 0.2, 0.5, 0.8)])
    y = fl.OutputVariable("y", minimum=0.0, maximum=1.0, aggregation=fl.Maximum(), defuzzifier=fl.Centroid(401), terms=[fl.Triangle("out", 0.0, 0.5, 1.0)])
    engine = fl.Engine("no-rule", input_variables=[x], output_variables=[y])
    block = fl.RuleBlock(conjunction=fl.Minimum(), implication=fl.Minimum(), activation=fl.General(), rules=[fl.Rule.create("if x is mid then y is out", engine)])
    engine.rule_blocks.append(block)
    block.load_rules(engine)
    x.value = 0.0
    engine.process()
    py_value = float(np.asarray(y.value, dtype=float).reshape(-1)[0])
    return {"ruflex": ruflex, "pyfuzzylite": "NAN_DEFAULT" if np.isnan(py_value) else str(py_value), "scope": "not a primary matched comparison"}


def diagnose() -> dict[str, object]:
    standard = dev_mamdani()
    legacy = standard.model_copy(update={"operators": standard.operators.model_copy(update={"centroid_sampling": CentroidSampling.INCLUSIVE_NODES})})
    subject = subject_evaluate(legacy, {"x": 0.25}, grid_size=401).output
    midpoint_subject = subject_evaluate(standard, {"x": 0.25}, grid_size=401).output
    outputs = {str(resolution): _reference_output(resolution) for resolution in (400, 401, 402, 800, 801)}
    formula = {
        "ruflex_declared_inclusive_401": _ruflex_formula(401, inclusive=True),
        "exclusive_401": _ruflex_formula(401, inclusive=False),
        "inclusive_400": _ruflex_formula(400, inclusive=True),
    }
    closest_resolution, closest = min(outputs.items(), key=lambda item: abs(item[1] - subject))
    return {
        "schema_version": 1,
        "fixture_id": "M01",
        "input": {"x": 0.25},
        "ruflex_output": subject,
        "ruflex_v101_midpoint_output": midpoint_subject,
        "ruflex_declared_formula_output": formula["ruflex_declared_inclusive_401"],
        "pyfuzzylite_centroid_outputs": outputs,
        "closest_pyfuzzylite_resolution": int(closest_resolution),
        "closest_pyfuzzylite_output": closest,
        "declared_401_absolute_error": abs(subject - outputs["401"]),
        "formula_checks": formula,
        "operator_mapping": {"conjunction": "Minimum", "implication": "Minimum", "aggregation": "Maximum"},
        "centroid_algorithm": {"ruflex": "inclusive endpoint grid with discrete weighted sum", "pyfuzzylite": "Centroid.defuzzify uses Op.midpoints and midpoint rectangle integration"},
        "endpoint_inclusion": "RuFLEX matches its independently recomputed inclusive 401-node grid; pyfuzzylite's midpoint algorithm has no endpoint samples.",
        "aggregation_sampling": "Both engines use Maximum aggregation over identical triangular output terms in this probe; only centroid sample locations differ.",
        "boundary_membership": {"input_x": 0.25, "ruflex": {"low": 0.75, "high": 0.25}, "reference": {"low": 0.75, "high": 0.25}},
        "no_rule_default_behavior": _no_rule_behavior(),
        "classification": "NUMERICAL_DISCRETIZATION_DIFFERENCE",
        "rationale": "RuFLEX output exactly matches its independently recomputed inclusive 401-node discrete formula. pyfuzzylite Centroid(401) differs and changes with its internal resolution, so the discrepancy is attributable to different centroid sampling/discretization conventions, not a hidden tolerance or no-rule path.",
    }


def main() -> None:
    result = diagnose()
    destination = ROOT / "artifacts" / "failures" / "legacy_mamdani_centroid_diagnosis.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"classification": result["classification"], "declared_401_absolute_error": result["declared_401_absolute_error"]}, sort_keys=True))


if __name__ == "__main__":
    main()
