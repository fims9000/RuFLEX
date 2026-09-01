from __future__ import annotations

import inspect
import ast

import pytest

from research.study01_conformance_trace.adapters.ruflex_adapter import evaluate
from research.study01_conformance_trace.core.trace_reconstructor import reconstruct
from research.study01_conformance_trace.fixtures.catalog import dev_mamdani, dev_sugeno


def test_trace_reconstructor_does_not_call_inference() -> None:
    tree = ast.parse(inspect.getsource(reconstruct))
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "evaluate_fis" not in calls


@pytest.mark.parametrize("fixture", [dev_mamdani(), dev_sugeno()])
def test_trace_reconstructs_dev_fixture(fixture) -> None:
    evaluation = evaluate(fixture, {"x": 0.25})
    assert reconstruct(evaluation.trace, fixture) == pytest.approx(evaluation.output, abs=1e-12)
