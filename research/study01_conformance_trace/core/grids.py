from __future__ import annotations

import hashlib
import json

import numpy as np


def uniform_grid(minimum: float, maximum: float, points: int) -> list[float]:
    if points < 2 or not minimum < maximum:
        raise ValueError("Grid requires an ordered finite domain and at least two points.")
    return [float(v) for v in np.linspace(minimum, maximum, points)]


def grid_with_critical_points(minimum: float, maximum: float, points: int, critical_points: list[float]) -> list[float]:
    values = set(uniform_grid(minimum, maximum, points))
    values.update(point for point in critical_points if minimum <= point <= maximum)
    return sorted(values)


def grid_hash(values: list[float]) -> str:
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()
