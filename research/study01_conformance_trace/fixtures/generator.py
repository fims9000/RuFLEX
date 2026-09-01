from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from ruflex.application.fis import with_semantic_hash
from ruflex.domain.fis import AntecedentClause, FISSpec, FuzzyRule, FuzzyVariable, MembershipFunction, SugenoConsequent

from research.study01_conformance_trace.fixtures.catalog import dev_mamdani, dev_sugeno


ROOT = Path(__file__).resolve().parent


def _uuid(label: str):
    return uuid5(NAMESPACE_URL, "ruflex-study01/" + label)


def _terms(prefix: str, middle: float = 0.5) -> list[MembershipFunction]:
    return [
        MembershipFunction(name=f"{prefix}_low", kind="triangular", parameters=(0.0, 0.0, middle)),
        MembershipFunction(name=f"{prefix}_high", kind="triangular", parameters=(middle, 1.0, 1.0)),
    ]


def _one_dimensional(identifier: str, *, system_type: str, middle: float, weight: float = 1.0) -> FISSpec:
    x = FuzzyVariable(name="x", minimum=0.0, maximum=1.0, terms=_terms("x", middle))
    output = FuzzyVariable(name="y", minimum=0.0, maximum=1.0, role="output", terms=_terms("y", 0.5))
    rules = []
    for index, (term, constant) in enumerate((("x_low", 0.2), ("x_high", 0.8))):
        consequent = SugenoConsequent(kind="constant", constant=constant) if system_type == "sugeno" else None
        rules.append(FuzzyRule(rule_id=_uuid(f"{identifier}/r/{index}"), name=f"{term} rule", clauses=[AntecedentClause(variable="x", term=term)], output_term="y_low" if index == 0 else "y_high", weight=weight, sugeno_consequent=consequent))
    return with_semantic_hash(FISSpec(fis_id=_uuid(identifier), name=identifier, system_type=system_type, inputs=[x], output=output, rules=rules))


def _two_dimensional(identifier: str, *, system_type: str, middle: float) -> FISSpec:
    x = FuzzyVariable(name="x", minimum=0.0, maximum=1.0, terms=_terms("x", middle))
    z = FuzzyVariable(name="z", minimum=0.0, maximum=1.0, terms=_terms("z", 1.0 - middle / 2.0))
    output = FuzzyVariable(name="y", minimum=0.0, maximum=1.0, role="output", terms=_terms("y", 0.5))
    rules = []
    for index, (xt, zt, term, constant) in enumerate((("x_low", "z_low", "y_low", 0.1), ("x_low", "z_high", "y_low", 0.35), ("x_high", "z_low", "y_high", 0.65), ("x_high", "z_high", "y_high", 0.9))):
        consequent = SugenoConsequent(kind="constant", constant=constant) if system_type == "sugeno" else None
        rules.append(FuzzyRule(rule_id=_uuid(f"{identifier}/r/{index}"), name=f"{xt} and {zt}", clauses=[AntecedentClause(variable="x", term=xt), AntecedentClause(variable="z", term=zt)], output_term=term, sugeno_consequent=consequent))
    return with_semantic_hash(FISSpec(fis_id=_uuid(identifier), name=identifier, system_type=system_type, inputs=[x, z], output=output, rules=rules))


def curated_fixtures() -> dict[str, FISSpec]:
    fixtures = {"M01": dev_mamdani(), "S01": dev_sugeno()}
    for index in range(2, 7):
        fixtures[f"M{index:02d}"] = _one_dimensional(f"M{index:02d}", system_type="mamdani", middle=0.35 + index * 0.05) if index == 2 else _two_dimensional(f"M{index:02d}", system_type="mamdani", middle=0.35 + index * 0.04)
        fixtures[f"S{index:02d}"] = _one_dimensional(f"S{index:02d}", system_type="sugeno", middle=0.35 + index * 0.05) if index == 2 else _two_dimensional(f"S{index:02d}", system_type="sugeno", middle=0.35 + index * 0.04)
    return fixtures


def generated_fixtures(family: str, *, seed: int, count: int = 20) -> dict[str, FISSpec]:
    if family not in {"mamdani", "sugeno"}:
        raise ValueError("family must be mamdani or sugeno")
    rng = random.Random(seed)
    prefix = "GM" if family == "mamdani" else "GS"
    result = {}
    for index in range(1, count + 1):
        middle = round(rng.uniform(0.3, 0.7), 6)
        identifier = f"{prefix}-{index:02d}-{seed}"
        result[identifier] = _one_dimensional(identifier, system_type=family, middle=middle, weight=round(rng.uniform(0.5, 1.0), 6))
    return result


def fixture_payload(identifier: str, spec: FISSpec, *, provenance: str) -> dict[str, object]:
    model = spec.model_dump(mode="json")
    raw = json.dumps(model, sort_keys=True, separators=(",", ":")).encode()
    return {"schema_version": 1, "fixture_id": identifier, "fixture_hash": hashlib.sha256(raw).hexdigest(), "provenance": provenance, "expected_reference_support": "PENDING_SEMANTIC_INTERSECTION", "model": model}


def write_fixture_inventory() -> dict[str, str]:
    outputs: dict[str, str] = {}
    for identifier, spec in curated_fixtures().items():
        path = ROOT / "curated" / f"{identifier}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fixture_payload(identifier, spec, provenance="curated protocol fixture"), indent=2, sort_keys=True) + "\n")
        outputs[identifier] = str(path.relative_to(ROOT.parent))
    for family, seed in (("mamdani", 20260831), ("sugeno", 20260901)):
        for identifier, spec in generated_fixtures(family, seed=seed).items():
            path = ROOT / "generated" / f"{identifier}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(fixture_payload(identifier, spec, provenance=f"deterministic seed {seed}"), indent=2, sort_keys=True) + "\n")
            outputs[identifier] = str(path.relative_to(ROOT.parent))
    return outputs
