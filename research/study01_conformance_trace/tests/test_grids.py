from __future__ import annotations

from research.study01_conformance_trace.core.critical_points import input_critical_points
from research.study01_conformance_trace.core.grids import grid_with_critical_points, uniform_grid
from research.study01_conformance_trace.fixtures.catalog import dev_mamdani


def test_uniform_grid_deterministic() -> None:
    assert uniform_grid(0.0, 1.0, 3) == [0.0, 0.5, 1.0]


def test_critical_points_included() -> None:
    critical = input_critical_points(dev_mamdani(), "x")
    assert set(critical).issubset(grid_with_critical_points(0.0, 1.0, 3, critical))
