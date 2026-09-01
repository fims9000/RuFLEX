from __future__ import annotations

import numpy as np

from ruflex.application.fis import membership_degree
from ruflex.domain.fis import FISSpec, FISTrace


class TraceReconstructionError(ValueError):
    pass


def reconstruct(trace: FISTrace, spec: FISSpec) -> float:
    """Reconstruct output only from persisted trace arrays and declared formula.

    The function intentionally does not import or invoke `evaluate_fis`.
    """
    if trace.fis_id != spec.fis_id:
        raise TraceReconstructionError("Trace belongs to a different FIS.")
    if trace.inference_kind == "sugeno":
        numerator = sum(rule.weighted_firing_strength * (rule.consequent_value or 0.0) for rule in trace.rules)
        denominator = sum(rule.weighted_firing_strength for rule in trace.rules)
        if denominator <= 1e-12:
            raise TraceReconstructionError("Sugeno trace has no nonzero firing strength.")
        return numerator / denominator
    if trace.output_domain is None or trace.centroid_resolution is None or trace.centroid_sampling is None:
        raise TraceReconstructionError("Mamdani trace lacks declared centroid sampling evidence.")
    minimum, maximum = trace.output_domain
    if trace.centroid_sampling.value == "inclusive_nodes":
        if trace.centroid_resolution < 2:
            raise TraceReconstructionError("Inclusive-node trace has invalid resolution.")
        expected = minimum + np.arange(trace.centroid_resolution, dtype=float) * ((maximum - minimum) / (trace.centroid_resolution - 1))
    else:
        expected = minimum + (np.arange(trace.centroid_resolution, dtype=float) + 0.5) * ((maximum - minimum) / trace.centroid_resolution)
    grid = np.asarray(trace.output_grid, dtype=float)
    aggregate = np.asarray(trace.aggregated_membership, dtype=float)
    if grid.size == 0 or grid.shape != aggregate.shape or grid.shape != expected.shape or not np.allclose(grid, expected, atol=1e-14, rtol=0.0):
        raise TraceReconstructionError("Mamdani trace has invalid persisted grid arrays.")
    denominator = float(aggregate.sum())
    if denominator <= 1e-12:
        raise TraceReconstructionError("Mamdani trace has no aggregate support.")
    return float((grid * aggregate).sum() / denominator)


def declared_output_membership(spec: FISSpec, output_term: str, grid: list[float]) -> list[float]:
    term = next(item for item in spec.output.terms if item.name == output_term)
    return [float(v) for v in membership_degree(np.asarray(grid), term)]
