from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Comparison:
    absolute_error: float | None
    normalized_error: float | None
    finite_state: str
    passed: bool


def compare(value: float, reference: float, *, output_range: float, atol: float, rtol: float) -> Comparison:
    if not (math.isfinite(value) and math.isfinite(reference)):
        state = "BOTH_NONFINITE" if (not math.isfinite(value) and not math.isfinite(reference)) else "FINITE_NONFINITE_MISMATCH"
        return Comparison(None, None, state, False)
    error = abs(value - reference)
    return Comparison(error, error / max(output_range, 1e-12), "BOTH_FINITE", error <= atol + rtol * abs(reference))
