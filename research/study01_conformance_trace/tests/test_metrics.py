from __future__ import annotations

from research.study01_conformance_trace.core.metrics import compare


def test_error_metric_near_zero() -> None:
    assert compare(1e-13, 0.0, output_range=1.0, atol=1e-12, rtol=0.0).passed


def test_nonfinite_mismatch_not_hidden_by_tolerance() -> None:
    assert not compare(float("nan"), 1.0, output_range=1.0, atol=999.0, rtol=999.0).passed
