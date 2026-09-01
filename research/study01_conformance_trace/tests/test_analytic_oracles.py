from __future__ import annotations

from research.study01_conformance_trace.adapters.analytic_oracle import linear_sugeno, symmetric_mamdani_centroid, zero_order_sugeno


def test_analytic_mamdani_microcase() -> None:
    assert symmetric_mamdani_centroid().final_output == 0.5


def test_analytic_sugeno_zero_order() -> None:
    result = zero_order_sugeno(0.25)
    assert result.final_output == 0.35
    assert result.normalized_weights == {"low to 0.2": 0.75, "high to 0.8": 0.25}


def test_analytic_sugeno_linear() -> None:
    assert linear_sugeno(2.0).final_output == 3.5
