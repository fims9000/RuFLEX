"""Execute the frozen Study 01 matrix and emit inspection-first evidence.

This is research orchestration, not product inference code. It rejects a changed
manifest before evaluating a case and preserves every observed failure class.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from research.study01_conformance_trace.adapters.pyfuzzylite_adapter import _fl, _term
from research.study01_conformance_trace.adapters.ruflex_adapter import evaluate as subject_evaluate
from research.study01_conformance_trace.core.critical_points import input_critical_points
from research.study01_conformance_trace.core.grids import grid_with_critical_points, uniform_grid
from research.study01_conformance_trace.core.metrics import compare
from research.study01_conformance_trace.core.roundtrip import canonical_roundtrip, preserves_semantics
from research.study01_conformance_trace.core.trace_reconstructor import reconstruct
from research.study01_conformance_trace.scripts.freeze_protocol import build_manifest


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "artifacts" / "locked"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evidence_number(value: float) -> float | str:
    """Keep evidence portable JSON; nonfinite comparator outputs are explicit."""
    return value if math.isfinite(value) else "NaN"


def _load_fixtures() -> list[tuple[str, object, str]]:
    from ruflex.domain.fis import FISSpec

    result = []
    for folder in ("curated", "generated"):
        for path in sorted((ROOT / "fixtures" / folder).glob("*.json")):
            payload = json.loads(path.read_text())
            result.append((payload["fixture_id"], FISSpec.model_validate(payload["model"]), _sha(path)))
    return result


class _ReferenceEngine:
    """Pinned pyfuzzylite scalar/vector evaluator built once per frozen FIS."""

    def __init__(self, spec):
        fl = _fl()
        input_variables = [fl.InputVariable(v.name, minimum=v.minimum, maximum=v.maximum, terms=[_term(fl, t) for t in v.terms]) for v in spec.inputs]
        if spec.system_type == "mamdani":
            output = fl.OutputVariable(spec.output.name, minimum=spec.output.minimum, maximum=spec.output.maximum, aggregation=fl.Maximum(), defuzzifier=fl.Centroid(spec.operators.centroid_resolution), terms=[_term(fl, t) for t in spec.output.terms])
        else:
            terms = [fl.Constant(rule.output_term + "_" + str(rule.rule_id), rule.sugeno_consequent.constant) for rule in spec.rules]
            output = fl.OutputVariable(spec.output.name, minimum=spec.output.minimum, maximum=spec.output.maximum, defuzzifier=fl.WeightedAverage(), terms=terms)
        self.inputs, self.output = input_variables, output
        self.engine = fl.Engine(spec.name, input_variables=input_variables, output_variables=[output])
        rules = []
        for rule in spec.rules:
            clauses = " and ".join(f"{c.variable} is {c.term}" for c in rule.clauses)
            target = rule.output_term if spec.system_type == "mamdani" else rule.output_term + "_" + str(rule.rule_id)
            suffix = "" if rule.weight == 1.0 else f" with {rule.weight}"
            rules.append(fl.Rule.create(f"if {clauses} then {spec.output.name} is {target}{suffix}", self.engine))
        block = fl.RuleBlock(conjunction=fl.Minimum(), disjunction=fl.Maximum(), implication=fl.Minimum(), activation=fl.General(), rules=rules)
        self.engine.rule_blocks.append(block)
        block.load_rules(self.engine)

    def evaluate_batch(self, cases: list[dict[str, float]]) -> list[float]:
        for variable in self.inputs:
            variable.value = np.asarray([case[variable.name] for case in cases], dtype=float)
        self.engine.process()
        values = np.asarray(self.output.value, dtype=float).reshape(-1)
        if values.size != len(cases):
            raise RuntimeError(f"Reference output length {values.size} differs from input cases {len(cases)}")
        return [float(value) for value in values]


def _cases(spec) -> list[dict[str, float]]:
    axes = [grid_with_critical_points(v.minimum, v.maximum, 10001 if len(spec.inputs) == 1 else 201, input_critical_points(spec, v.name)) for v in spec.inputs]
    if len(axes) == 1:
        return [{spec.inputs[0].name: value} for value in axes[0]]
    return [{spec.inputs[0].name: x, spec.inputs[1].name: z} for x in axes[0] for z in axes[1]]


def _tolerance(spec) -> tuple[float, float]:
    config = json.loads((ROOT / "config" / "tolerances.json").read_text())
    item = config["classes"]["MAMDANI_DEFUZZIFICATION" if spec.system_type == "mamdani" else "SUGENO_CROSS_ENGINE"]
    return float(item["atol"]), float(item["rtol"])


def _bootstrap_ci(values: list[float], *, seed: int = 20260901) -> list[float]:
    if not values:
        return [None, None]
    rng = np.random.default_rng(seed)
    matrix = rng.choice(np.asarray(values), size=(2000, len(values)), replace=True).mean(axis=1)
    return [float(np.quantile(matrix, 0.025)), float(np.quantile(matrix, 0.975))]


def _write_table(rows: list[dict[str, object]]) -> Path:
    path = ROOT / "tables" / "T01_locked_system_summary.csv"
    path.parent.mkdir(exist_ok=True)
    columns = ["fixture_id", "system_type", "case_count", "conformance_pass_fraction", "max_cross_engine_error", "trace_pass_fraction", "roundtrip_pass_fraction", "failure_count"]
    lines = [",".join(columns)]
    lines.extend(",".join(str(row[column]) for column in columns) for row in rows)
    path.write_text("\n".join(lines) + "\n")
    return path


def _write_figure(rows: list[dict[str, object]]) -> Path:
    path = ROOT / "figures" / "F01_locked_system_max_error.svg"
    path.parent.mkdir(exist_ok=True)
    width, height = 1000, 360
    max_error = max([float(row["max_cross_engine_error"]) for row in rows] + [1e-12])
    bars = []
    for index, row in enumerate(rows):
        error = float(row["max_cross_engine_error"])
        bar = 260 * (math.log10(max(error, 1e-16)) - math.log10(1e-16)) / (math.log10(max_error) - math.log10(1e-16) or 1)
        x = 35 + index * 18
        bars.append(f'<rect x="{x}" y="{320-bar:.3f}" width="12" height="{bar:.3f}" fill="#2563eb"/><text x="{x}" y="345" font-size="7" transform="rotate(60 {x} 345)">{row["fixture_id"]}</text>')
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="white"/><text x="24" y="28" font-size="18">Study 01 locked systems: maximum absolute cross-engine error</text><line x1="25" y1="320" x2="975" y2="320" stroke="#111"/>{"".join(bars)}</svg>\n')
    return path


def run() -> dict[str, object]:
    frozen = json.loads((ROOT / "config" / "locked_suite_manifest.json").read_text())
    rebuilt = build_manifest()
    if frozen["manifest_hash"] != rebuilt["manifest_hash"]:
        raise RuntimeError("Locked manifest changed after TEST UNLOCK; refusing execution.")
    if frozen["test_unlock"] != "FORBIDDEN_PENDING_PROTOCOL_REVIEW":
        raise RuntimeError("Unexpected frozen manifest unlock state.")
    fixtures = _load_fixtures()
    if [fixture_id for fixture_id, _, _ in fixtures] != frozen["fixture_ids"]:
        raise RuntimeError("Fixture identity/order does not match locked manifest.")
    summaries, failures, all_failure_types = [], [], Counter()
    for fixture_id, spec, fixture_sha in fixtures:
        if frozen["fixture_hashes"].get(f"{fixture_id}.json") != fixture_sha:
            raise RuntimeError(f"Fixture hash mismatch: {fixture_id}")
        cases = _cases(spec)
        reference = _ReferenceEngine(spec)
        reference_values: list[float] = []
        for start in range(0, len(cases), 2048):
            reference_values.extend(reference.evaluate_batch(cases[start:start + 2048]))
        atol, rtol = _tolerance(spec)
        max_error, conformance_pass, trace_pass, roundtrip_pass = 0.0, 0, 0, 0
        types: Counter[str] = Counter()
        roundtrip_spec = canonical_roundtrip(spec)
        semantic_roundtrip = preserves_semantics(spec)
        for index, (case, reference_value) in enumerate(zip(cases, reference_values, strict=True)):
            try:
                subject = subject_evaluate(spec, case)
                comparison = compare(subject.output, reference_value, output_range=spec.output.maximum-spec.output.minimum, atol=atol, rtol=rtol)
                if comparison.absolute_error is not None:
                    max_error = max(max_error, comparison.absolute_error)
                if comparison.passed:
                    conformance_pass += 1
                else:
                    classification = "CROSS_ENGINE_MISMATCH" if comparison.finite_state == "BOTH_FINITE" else comparison.finite_state
                    types[classification] += 1
                    all_failure_types[classification] += 1
                    failures.append({"fixture_id": fixture_id, "phase": "A", "case": case, "classification": classification, "subject": _evidence_number(subject.output), "reference": _evidence_number(reference_value), "absolute_error": comparison.absolute_error, "finite_state": comparison.finite_state})
                try:
                    reconstructed = reconstruct(subject.trace, spec)
                    trace_cmp = compare(subject.output, reconstructed, output_range=spec.output.maximum-spec.output.minimum, atol=1e-12, rtol=1e-12)
                    trace_pass += int(trace_cmp.passed)
                    if not trace_cmp.passed:
                        types["TRACE_RECONSTRUCTION_MISMATCH"] += 1
                        all_failure_types["TRACE_RECONSTRUCTION_MISMATCH"] += 1
                except Exception as exc:  # evidence must preserve an unexpected trace failure
                    types["TRACE_RECONSTRUCTION_ERROR"] += 1
                    all_failure_types["TRACE_RECONSTRUCTION_ERROR"] += 1
                    failures.append({"fixture_id": fixture_id, "phase": "B", "case": case, "classification": "TRACE_RECONSTRUCTION_ERROR", "error": repr(exc)})
                try:
                    rt_output = subject_evaluate(roundtrip_spec, case).output
                    rt_cmp = compare(subject.output, rt_output, output_range=spec.output.maximum-spec.output.minimum, atol=1e-12, rtol=1e-12)
                    passed = semantic_roundtrip and rt_cmp.passed
                    roundtrip_pass += int(passed)
                    if not passed:
                        types["ROUNDTRIP_MISMATCH"] += 1
                        all_failure_types["ROUNDTRIP_MISMATCH"] += 1
                except Exception as exc:
                    types["ROUNDTRIP_ERROR"] += 1
                    all_failure_types["ROUNDTRIP_ERROR"] += 1
                    failures.append({"fixture_id": fixture_id, "phase": "C", "case": case, "classification": "ROUNDTRIP_ERROR", "error": repr(exc)})
            except Exception as exc:
                reference_state = "REFERENCE_NONFINITE" if not math.isfinite(reference_value) else "REFERENCE_FINITE"
                classification = "SUBJECT_UNDEFINED_NO_RULE_" + reference_state if "No rule produced" in str(exc) else "SUBJECT_ERROR_" + reference_state
                types[classification] += 1
                all_failure_types[classification] += 1
                failures.append({"fixture_id": fixture_id, "phase": "A", "case": case, "classification": classification, "error": repr(exc), "reference": _evidence_number(reference_value)})
        count = len(cases)
        summaries.append({"fixture_id": fixture_id, "system_type": spec.system_type, "case_count": count, "conformance_pass_fraction": conformance_pass / count, "max_cross_engine_error": max_error, "trace_pass_fraction": trace_pass / count, "roundtrip_pass_fraction": roundtrip_pass / count, "failure_count": sum(types.values()), "failure_taxonomy": dict(types)})
    table, figure = _write_table(summaries), _write_figure(summaries)
    by_type = {kind: [row for row in summaries if row["system_type"] == kind] for kind in ("mamdani", "sugeno")}
    summary = {
        "schema_version": 1, "study_id": "study01_conformance_trace", "status": "RESULT_FREEZE", "generated_at": datetime.now(UTC).isoformat(),
        "product_baseline": frozen["product_baseline"], "protocol_hash": frozen["protocol_hash"], "locked_manifest_hash": frozen["manifest_hash"],
        "locked_system_count": len(summaries), "locked_case_count": sum(int(row["case_count"]) for row in summaries), "systems": summaries,
        "failure_taxonomy": dict(all_failure_types), "failure_examples": failures,
        "system_level_uncertainty": {kind: {"conformance_fraction_95pct_bootstrap_ci": _bootstrap_ci([float(row["conformance_pass_fraction"]) for row in rows])} for kind, rows in by_type.items()},
        "tables": [str(table.relative_to(ROOT))], "figures": [str(figure.relative_to(ROOT))],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    output = RESULTS / "locked_study_results.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    provenance = {"schema_version": 1, "figure": str(figure.relative_to(ROOT)), "table": str(table.relative_to(ROOT)), "source": str(output.relative_to(ROOT)), "source_sha256": _sha(output), "manifest_hash": frozen["manifest_hash"]}
    (ROOT / "artifacts" / "aggregated" / "locked_evidence_provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    return summary


if __name__ == "__main__":
    result = run()
    print(json.dumps({"status": result["status"], "systems": result["locked_system_count"], "cases": result["locked_case_count"], "failures": len(result["failure_examples"])}, sort_keys=True))
