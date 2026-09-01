"""Independent post-freeze reproduction with complete portable raw case rows."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from ruflex.application.fis import membership_degree

from research.study01_conformance_trace.adapters.ruflex_adapter import evaluate as subject_evaluate
from research.study01_conformance_trace.core.metrics import compare
from research.study01_conformance_trace.core.roundtrip import canonical_roundtrip, preserves_semantics
from research.study01_conformance_trace.core.trace_reconstructor import reconstruct
from research.study01_conformance_trace.scripts.execute_locked_study import _ReferenceEngine, _cases, _load_fixtures, _tolerance
from research.study01_conformance_trace.scripts.freeze_protocol import build_manifest


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "raw" / "locked_cases.csv.gz"


def _activation_sum(spec, case: dict[str, float]) -> float:
    values = {}
    for variable in spec.inputs:
        for term in variable.terms:
            values[(variable.name, term.name)] = float(membership_degree(np.asarray([case[variable.name]]), term)[0])
    return sum(min(values[(clause.variable, clause.term)] for clause in rule.clauses) * rule.weight for rule in spec.rules)


def _boundary(spec, case: dict[str, float]) -> bool:
    return any(any(math.isclose(case[variable.name], point, abs_tol=1e-15, rel_tol=0.0) for point in [variable.minimum, variable.maximum, *(p for term in variable.terms for p in term.parameters)]) for variable in spec.inputs)


def _number(value: float | None) -> str:
    return "" if value is None or not math.isfinite(value) else repr(value)


def run() -> dict[str, object]:
    frozen = json.loads((ROOT / "config" / "locked_suite_manifest.json").read_text())
    if build_manifest()["manifest_hash"] != frozen["manifest_hash"]:
        raise RuntimeError("Frozen manifest mismatch; reproduction refused.")
    original = json.loads((ROOT / "artifacts" / "locked" / "locked_study_results.json").read_text())
    fixtures = _load_fixtures()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    total = defined = negative = 0
    max_error = 0.0
    with gzip.open(OUT, "wt", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["fixture_id", "system_type", "case_id", "x", "z", "subject_defined", "reference_defined", "subject_output", "reference_output", "absolute_error", "conformance_pass", "trace_reconstruction_pass", "roundtrip_pass", "failure_class", "boundary_case", "rule_activation_sum", "error"])
        writer.writeheader()
        for fixture_id, spec, fixture_sha in fixtures:
            if frozen["fixture_hashes"].get(f"{fixture_id}.json") != fixture_sha:
                raise RuntimeError(f"Fixture hash mismatch: {fixture_id}")
            cases = _cases(spec)
            reference = _ReferenceEngine(spec)
            reference_values = []
            for start in range(0, len(cases), 2048):
                reference_values.extend(reference.evaluate_batch(cases[start:start + 2048]))
            atol, rtol = _tolerance(spec)
            rt_spec, semantic_rt = canonical_roundtrip(spec), preserves_semantics(spec)
            for index, (case, ref) in enumerate(zip(cases, reference_values, strict=True)):
                total += 1
                activation = _activation_sum(spec, case)
                ref_defined = math.isfinite(ref)
                row = {"fixture_id": fixture_id, "system_type": spec.system_type, "case_id": f"{fixture_id}:{index}", "x": repr(case.get("x", "")), "z": repr(case.get("z", "")), "subject_defined": "false", "reference_defined": str(ref_defined).lower(), "subject_output": "", "reference_output": _number(ref), "absolute_error": "", "conformance_pass": "false", "trace_reconstruction_pass": "false", "roundtrip_pass": "false", "failure_class": "", "boundary_case": str(_boundary(spec, case)).lower(), "rule_activation_sum": repr(activation), "error": ""}
                try:
                    subject = subject_evaluate(spec, case)
                    row["subject_defined"] = "true"
                    row["subject_output"] = _number(subject.output)
                    comparison = compare(subject.output, ref, output_range=spec.output.maximum-spec.output.minimum, atol=atol, rtol=rtol)
                    row["absolute_error"] = _number(comparison.absolute_error)
                    row["conformance_pass"] = str(comparison.passed).lower()
                    max_error = max(max_error, comparison.absolute_error or 0.0)
                    trace_pass = compare(subject.output, reconstruct(subject.trace, spec), output_range=spec.output.maximum-spec.output.minimum, atol=1e-12, rtol=1e-12).passed
                    rt_pass = semantic_rt and compare(subject.output, subject_evaluate(rt_spec, case).output, output_range=spec.output.maximum-spec.output.minimum, atol=1e-12, rtol=1e-12).passed
                    row["trace_reconstruction_pass"] = str(trace_pass).lower()
                    row["roundtrip_pass"] = str(rt_pass).lower()
                    if comparison.passed and trace_pass and rt_pass:
                        defined += 1
                    else:
                        negative += 1; row["failure_class"] = "DEFINED_OUTPUT_MISMATCH"; counts[row["failure_class"]] += 1
                except Exception as exc:
                    negative += 1
                    if activation == 0.0:
                        base = "TRUE_ZERO_ACTIVATION"
                    elif activation <= 1e-12:
                        base = "ACTIVATION_CUTOFF_POLICY_DIFFERENCE"
                    else:
                        base = "OTHER_BOUNDARY_SEMANTIC_MISMATCH"
                    row["failure_class"] = base + ("_REFERENCE_FINITE" if ref_defined else "_REFERENCE_NONFINITE")
                    counts[row["failure_class"]] += 1
                    row["error"] = repr(exc)
                writer.writerow(row)
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    result = {"raw_artifact": str(OUT.relative_to(ROOT)), "sha256": digest, "systems": len(fixtures), "cases": total, "defined_cases": defined, "negative_cases": negative, "max_defined_error": max_error, "failure_taxonomy": dict(counts), "matches_original": {"systems": len(fixtures) == original["locked_system_count"], "cases": total == original["locked_case_count"], "defined_cases": defined == 760042, "negative_cases": negative == 4056, "max_error": max_error == 0.0}}
    path = ROOT / "artifacts" / "diagnostics" / "reproduction_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not all(result["matches_original"].values()):
        raise RuntimeError(f"Reproduction discrepancy: {result['matches_original']}")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
