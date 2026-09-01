from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from ruflex.application.fis import FISError, persist_fis, with_semantic_hash
from ruflex.domain.fis import (
    AntecedentClause,
    FISSpec,
    FuzzyRule,
    FuzzyVariable,
    MembershipFunction,
    OperatorSet,
    SugenoConsequent,
    CentroidSampling,
)


@dataclass(frozen=True)
class CompatibilityIssue:
    source_construct: str
    ruflex_construct: str | None
    semantic_consequence: str
    severity: str
    status: str


@dataclass(frozen=True)
class FISImportResult:
    spec: FISSpec | None
    issues: list[CompatibilityIssue]


_MF_TYPES = {
    "trimf": "triangular", "trapmf": "trapezoidal", "gaussmf": "gaussian",
    "gbellmf": "bell", "sigmf": "sigmoid", "smf": "s_shape", "zmf": "z_shape", "pimf": "pi_shape",
}
_AND = {"min", "prod", "product", "lukasiewicz", "hamacher", "einstein"}
_OR = {"max", "probor", "probabilistic_sum", "sum", "bounded_sum", "hamacher", "einstein"}
_AND_MAP = {"prod": "product"}
_OR_MAP = {"probor": "probabilistic_sum", "sum": "bounded_sum"}
_MF_EXPORT = {value: key for key, value in _MF_TYPES.items()}
_AND_EXPORT = {"product": "prod"}
_OR_EXPORT = {"probabilistic_sum": "probor", "bounded_sum": "sum"}


def _unquote(value: str) -> str:
    value = value.strip()
    return ast.literal_eval(value) if value.startswith(("'", '"')) else value


def _numbers(value: str) -> tuple[float, ...]:
    match = re.search(r"\[([^]]*)\]", value)
    if not match:
        raise FISError(f"Expected numeric bracket list: {value}")
    try:
        return tuple(float(item) for item in match.group(1).replace(",", " ").split())
    except ValueError as error:
        raise FISError(f"Invalid numeric parameter list: {value}") from error


def _sections(source: str) -> dict[str, dict[str, str]]:
    current: dict[str, str] | None = None
    current_name = ""
    sections: dict[str, dict[str, str]] = {}
    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith(("%", "#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_name = line[1:-1].strip()
            current = sections.setdefault(current_name, {})
            continue
        if current is None:
            raise FISError(f"Malformed MATLAB FIS line: {line}")
        if current_name.lower() == "rules" and "=" not in line:
            current[f"rule-{len(current) + 1}"] = line
            continue
        if "=" not in line:
            raise FISError(f"Malformed MATLAB FIS line: {line}")
        key, value = line.split("=", 1)
        current[key.strip()] = value.strip()
    if "System" not in sections:
        raise FISError("MATLAB FIS source has no [System] section.")
    return sections


def _variable(section: dict[str, str], *, role: str) -> tuple[FuzzyVariable, list[CompatibilityIssue]]:
    issues: list[CompatibilityIssue] = []
    if "Name" not in section or "Range" not in section:
        raise FISError("FIS variable requires Name and Range.")
    minimum, maximum = _numbers(section["Range"])
    terms: list[MembershipFunction] = []
    for key, value in sorted(section.items()):
        match = re.fullmatch(r"MF(\d+)", key, flags=re.IGNORECASE)
        if not match:
            continue
        parsed = re.fullmatch(r"\s*('(?:[^']|'')*')\s*:\s*('(?:[^']|'')*')\s*,\s*(\[[^]]*\])\s*", value)
        if not parsed:
            raise FISError(f"Malformed {key} definition: {value}")
        name = _unquote(parsed.group(1))
        source_kind = _unquote(parsed.group(2)).lower()
        parameters = _numbers(parsed.group(3))
        kind = _MF_TYPES.get(source_kind)
        if kind is None:
            issues.append(CompatibilityIssue(f"{key} {source_kind}", None, "No canonical equivalent was imported.", "error", "UNSUPPORTED"))
            continue
        terms.append(MembershipFunction(name=name, kind=kind, parameters=parameters))
        issues.append(CompatibilityIssue(f"{key} {source_kind}", kind, "Exact parameter mapping.", "info", "SUPPORTED"))
    if not terms:
        raise FISError(f"FIS variable {_unquote(section['Name'])!r} has no supported membership functions.")
    return FuzzyVariable(name=_unquote(section["Name"]), minimum=minimum, maximum=maximum, terms=terms, role=role), issues


def import_matlab_fis(source: str) -> FISImportResult:
    sections = _sections(source)
    system = sections["System"]
    system_type = _unquote(system.get("Type", "mamdani")).lower()
    issues: list[CompatibilityIssue] = []
    if system_type not in {"mamdani", "sugeno"}:
        return FISImportResult(None, [CompatibilityIssue(f"System.Type={system_type}", None, "Only Type-1 Mamdani and Sugeno are supported.", "error", "UNSUPPORTED")])
    input_sections = [sections[name] for name in sorted(sections) if re.fullmatch(r"Input\d+", name, re.IGNORECASE)]
    output_sections = [sections[name] for name in sorted(sections) if re.fullmatch(r"Output\d+", name, re.IGNORECASE)]
    if len(output_sections) != 1:
        return FISImportResult(None, [CompatibilityIssue("Output count", "single-output FIS", "Product V1 imports exactly one output.", "error", "UNSUPPORTED")])
    inputs: list[FuzzyVariable] = []
    for section in input_sections:
        variable, variable_issues = _variable(section, role="input")
        inputs.append(variable); issues.extend(variable_issues)
    output, output_issues = _variable(output_sections[0], role="output")
    issues.extend(output_issues)
    if any(issue.status == "UNSUPPORTED" for issue in issues):
        return FISImportResult(None, issues)
    and_method = _unquote(system.get("AndMethod", "min")).lower()
    or_method = _unquote(system.get("OrMethod", "max")).lower()
    implication = _unquote(system.get("ImpMethod", "min")).lower()
    aggregation = _unquote(system.get("AggMethod", "max")).lower()
    defuzzification = _unquote(system.get("DefuzzMethod", "centroid")).lower()
    unsupported = []
    if and_method not in _AND: unsupported.append(("AndMethod", and_method))
    if or_method not in _OR: unsupported.append(("OrMethod", or_method))
    if system_type == "mamdani" and implication not in {"min", "prod", "product"}: unsupported.append(("ImpMethod", implication))
    if system_type == "mamdani" and aggregation not in _OR: unsupported.append(("AggMethod", aggregation))
    if system_type == "mamdani" and defuzzification != "centroid": unsupported.append(("DefuzzMethod", defuzzification))
    if unsupported:
        return FISImportResult(None, issues + [CompatibilityIssue(f"{key}={value}", None, "No semantics-preserving Product V1 mapping.", "error", "UNSUPPORTED") for key, value in unsupported])
    operators = OperatorSet(
        and_operator=_AND_MAP.get(and_method, and_method), or_operator=_OR_MAP.get(or_method, or_method),
        implication="product" if implication in {"prod", "product"} else "min",
        aggregation=_OR_MAP.get(aggregation, aggregation), centroid_sampling=CentroidSampling.MIDPOINT_CELLS,
    )
    if system_type == "mamdani":
        issues.append(CompatibilityIssue(
            "MATLAB .fis centroid discretization", "midpoint_cells",
            "The source names centroid but does not encode finite sampling. RuFLEX applies its documented midpoint-cell compatibility policy.",
            "warning", "APPROXIMATED",
        ))
    rules_section = sections.get("Rules", {})
    rule_lines = [value for _, value in sorted(rules_section.items())] if rules_section else []
    if not rule_lines and "Rules" in sections:
        rule_lines = list(sections["Rules"].values())
    if not rule_lines:
        raw_rules = source.split("[Rules]", 1)
        rule_lines = [line.strip() for line in raw_rules[1].splitlines() if line.strip() and not line.strip().startswith(("%", "#", ";"))] if len(raw_rules) == 2 else []
    rules: list[FuzzyRule] = []
    for ordinal, raw_rule in enumerate(rule_lines, 1):
        match = re.fullmatch(r"\s*([\d\s-]+)\s*,\s*([\d\s-]+)\s*\(([-+.\deE]+)\)\s*:\s*([12])\s*", raw_rule)
        if not match:
            return FISImportResult(None, issues + [CompatibilityIssue(f"Rule {ordinal}", None, f"Cannot parse: {raw_rule}", "error", "UNSUPPORTED")])
        antecedents = [int(value) for value in match.group(1).split()]
        consequents = [int(value) for value in match.group(2).split()]
        if len(antecedents) != len(inputs) or len(consequents) != 1 or any(value <= 0 for value in antecedents + consequents):
            return FISImportResult(None, issues + [CompatibilityIssue(f"Rule {ordinal}", None, "Negative, zero, multi-output, and negated rule indices are not imported silently.", "error", "UNSUPPORTED")])
        try:
            clauses = [AntecedentClause(variable=variable.name, term=variable.terms[index - 1].name) for variable, index in zip(inputs, antecedents)]
            output_term = output.terms[consequents[0] - 1].name
        except IndexError:
            return FISImportResult(None, issues + [CompatibilityIssue(f"Rule {ordinal}", None, "Rule index references a missing MF.", "error", "UNSUPPORTED")])
        connector = "and" if match.group(4) == "1" else "or"
        consequence = None
        if system_type == "sugeno":
            output_mf = output.terms[consequents[0] - 1]
            if output_mf.kind not in {"triangular", "trapezoidal"}:
                return FISImportResult(None, issues + [CompatibilityIssue(f"Rule {ordinal}", None, "Sugeno output MF must be parsed as constant or linear; source MF is not representable.", "error", "UNSUPPORTED")])
            consequence = SugenoConsequent(kind="constant", constant=output_mf.parameters[0])
        rules.append(FuzzyRule(name=f"Imported rule {ordinal}", clauses=clauses, connector=connector, output_term=output_term, weight=float(match.group(3)), sugeno_consequent=consequence))
    if not rules:
        return FISImportResult(None, issues + [CompatibilityIssue("Rules", None, "No parseable rules were supplied.", "error", "UNSUPPORTED")])
    spec = with_semantic_hash(FISSpec(name=_unquote(system.get("Name", "Imported FIS")), system_type=system_type, inputs=inputs, output=output, rules=rules, operators=operators))
    issues.append(CompatibilityIssue(f"System.Type={system_type}", system_type, "Canonical Type-1 semantics preserved for supported constructs.", "info", "SUPPORTED"))
    return FISImportResult(spec, issues)


def persist_imported_matlab_fis(project_root, source: str) -> FISImportResult:
    result = import_matlab_fis(source)
    if result.spec is not None:
        return FISImportResult(persist_fis(project_root, result.spec), result.issues)
    return result


def export_matlab_fis(spec: FISSpec) -> str:
    """Export only exact Product V1 MATLAB FIS semantics; fail closed otherwise."""
    if spec.system_type != "mamdani":
        raise FISError("MATLAB export is currently exact only for Type-1 Mamdani FIS; Sugeno export is blocked.")
    if spec.operators.centroid_sampling is not CentroidSampling.MIDPOINT_CELLS:
        raise FISError("MATLAB export is blocked for inclusive-node centroid sampling because .fis does not encode the finite sampling convention.")
    unsupported = [term.kind for variable in [*spec.inputs, spec.output] for term in variable.terms if term.kind not in _MF_EXPORT]
    if unsupported:
        raise FISError(f"MATLAB export blocked: unsupported membership family/families {sorted(set(unsupported))}.")
    def quoted(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"
    def numbers(values: tuple[float, ...]) -> str:
        return "[" + " ".join(f"{value:.16g}" for value in values) + "]"
    def variable_section(kind: str, ordinal: int, variable: FuzzyVariable) -> list[str]:
        lines = [f"[{kind}{ordinal}]", f"Name={quoted(variable.name)}", f"Range={numbers((variable.minimum, variable.maximum))}", f"NumMFs={len(variable.terms)}"]
        for term_index, term in enumerate(variable.terms, 1):
            lines.append(f"MF{term_index}={quoted(term.name)}:{quoted(_MF_EXPORT[term.kind])},{numbers(term.parameters)}")
        return lines
    lines = [
        "[System]", f"Name={quoted(spec.name)}", "Type='mamdani'", f"NumInputs={len(spec.inputs)}", "NumOutputs=1", f"NumRules={len(spec.rules)}",
        f"AndMethod={quoted(_AND_EXPORT.get(spec.operators.and_operator, spec.operators.and_operator))}",
        f"OrMethod={quoted(_OR_EXPORT.get(spec.operators.or_operator, spec.operators.or_operator))}",
        f"ImpMethod={quoted('prod' if spec.operators.implication == 'product' else 'min')}",
        f"AggMethod={quoted(_OR_EXPORT.get(spec.operators.aggregation, spec.operators.aggregation))}",
        "DefuzzMethod='centroid'", "",
    ]
    for index, variable in enumerate(spec.inputs, 1):
        lines.extend(variable_section("Input", index, variable)); lines.append("")
    lines.extend(variable_section("Output", 1, spec.output)); lines.extend(["", "[Rules]"])
    for rule in spec.rules:
        if not rule.enabled:
            raise FISError("MATLAB export blocked: disabled rules cannot be represented without changing the source rule base.")
        antecedents = []
        for variable in spec.inputs:
            clause = next((item for item in rule.clauses if item.variable == variable.name), None)
            if clause is None:
                raise FISError("MATLAB export blocked: every rule must reference each input in Product V1 export.")
            antecedents.append(str(next(index for index, term in enumerate(variable.terms, 1) if term.name == clause.term)))
        output_index = next(index for index, term in enumerate(spec.output.terms, 1) if term.name == rule.output_term)
        lines.append(f"{' '.join(antecedents)}, {output_index} ({rule.weight:.16g}) : {'1' if rule.connector == 'and' else '2'}")
    return "\n".join(lines) + "\n"
