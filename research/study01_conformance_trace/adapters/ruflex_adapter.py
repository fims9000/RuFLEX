from __future__ import annotations

from ruflex.application.fis import evaluate_fis
from ruflex.domain.fis import FISEvaluation, FISSpec


def evaluate(spec: FISSpec, inputs: dict[str, float], *, grid_size: int = 401) -> FISEvaluation:
    """Invoke the frozen subject through its public application boundary."""
    return evaluate_fis(spec, inputs, grid_size=grid_size)
