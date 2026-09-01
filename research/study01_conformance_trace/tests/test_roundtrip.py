from __future__ import annotations

import pytest

from research.study01_conformance_trace.adapters.ruflex_adapter import evaluate
from research.study01_conformance_trace.core.roundtrip import canonical_roundtrip, preserves_semantics
from research.study01_conformance_trace.fixtures.catalog import dev_mamdani, dev_sugeno


@pytest.mark.parametrize("fixture", [dev_mamdani(), dev_sugeno()])
def test_roundtrip_preserves_semantics(fixture) -> None:
    assert preserves_semantics(fixture)


@pytest.mark.parametrize("fixture", [dev_mamdani(), dev_sugeno()])
def test_roundtrip_preserves_outputs(fixture) -> None:
    assert evaluate(fixture, {"x": 0.25}).output == pytest.approx(evaluate(canonical_roundtrip(fixture), {"x": 0.25}).output, abs=1e-12)
