from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ruflex.domain.fis import FISSpec, MembershipFunction
from ruflex.domain.fis import CentroidSampling


class ReferenceUnavailable(RuntimeError):
    pass


def _fl():
    try:
        import fuzzylite as fl
    except ImportError as exc:
        raise ReferenceUnavailable("pyfuzzylite 8.0.6 is unavailable; use the pinned research environment.") from exc
    return fl


def _term(fl: object, term: MembershipFunction):
    mapping: dict[str, Callable[..., object]] = {
        "triangular": getattr(fl, "Triangle"), "trapezoidal": getattr(fl, "Trapezoid"),
        "gaussian": getattr(fl, "Gaussian"), "bell": getattr(fl, "Bell"),
        "s_shape": getattr(fl, "SShape"), "z_shape": getattr(fl, "ZShape"), "pi_shape": getattr(fl, "PiShape"),
    }
    if term.kind not in mapping:
        raise ReferenceUnavailable(f"No verified pyfuzzylite mapping for {term.kind}.")
    return mapping[term.kind](term.name, *term.parameters)


def evaluate(spec: FISSpec, inputs: dict[str, float], *, centroid_resolution: int = 401) -> float:
    """Evaluate only the declared minimal MATCH/DEV mapping.

    This function refuses unsupported operators instead of manufacturing a
    similarly named mapping. The resulting comparator remains DEV-only until
    the environment caveat and node convention receive protocol review.
    """
    fl = _fl()
    if spec.operators.and_operator != "min" or spec.operators.or_operator != "max" or spec.operators.implication != "min" or spec.operators.aggregation != "max":
        raise ReferenceUnavailable("Only min/max/min/max semantics are currently verified for the DEV adapter.")
    if spec.system_type == "mamdani" and spec.operators.centroid_sampling is not CentroidSampling.MIDPOINT_CELLS:
        raise ReferenceUnavailable("pyfuzzylite centroid comparisons require explicit midpoint-cell RuFLEX sampling.")
    if any(term.kind not in {"triangular", "trapezoidal"} for variable in [*spec.inputs, spec.output] for term in variable.terms):
        raise ReferenceUnavailable("Only triangular/trapezoidal terms are currently verified for the DEV adapter.")
    input_variables = [fl.InputVariable(v.name, minimum=v.minimum, maximum=v.maximum, terms=[_term(fl, t) for t in v.terms]) for v in spec.inputs]
    if spec.system_type == "mamdani":
        if centroid_resolution != spec.operators.centroid_resolution:
            raise ReferenceUnavailable("Reference centroid resolution must equal the canonical persisted FIS resolution.")
        output = fl.OutputVariable(spec.output.name, minimum=spec.output.minimum, maximum=spec.output.maximum, aggregation=fl.Maximum(), defuzzifier=fl.Centroid(centroid_resolution), terms=[_term(fl, t) for t in spec.output.terms])
    else:
        terms = []
        for rule in spec.rules:
            consequent = rule.sugeno_consequent
            if consequent is None or consequent.kind != "constant":
                raise ReferenceUnavailable("Only zero-order Sugeno consequents are currently verified for the DEV adapter.")
            terms.append(fl.Constant(rule.output_term + "_" + str(rule.rule_id), consequent.constant))
        output = fl.OutputVariable(spec.output.name, minimum=spec.output.minimum, maximum=spec.output.maximum, defuzzifier=fl.WeightedAverage(), terms=terms)
    engine = fl.Engine(spec.name, input_variables=input_variables, output_variables=[output])
    rules = []
    for rule in spec.rules:
        clauses = " and ".join(f"{c.variable} is {c.term}" for c in rule.clauses)
        target = rule.output_term if spec.system_type == "mamdani" else rule.output_term + "_" + str(rule.rule_id)
        suffix = "" if rule.weight == 1.0 else f" with {rule.weight}"
        rules.append(fl.Rule.create(f"if {clauses} then {spec.output.name} is {target}{suffix}", engine))
    block = fl.RuleBlock(conjunction=fl.Minimum(), disjunction=fl.Maximum(), implication=fl.Minimum(), activation=fl.General(), rules=rules)
    engine.rule_blocks.append(block)
    block.load_rules(engine)
    for variable in input_variables:
        variable.value = inputs[variable.name]
    engine.process()
    value = np.asarray(output.value, dtype=float).reshape(-1)
    if value.size != 1:
        raise ReferenceUnavailable(f"Reference produced {value.size} outputs for one scalar case.")
    return float(value[0])
