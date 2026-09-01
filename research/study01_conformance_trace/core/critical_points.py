from __future__ import annotations

from ruflex.domain.fis import FISSpec


def input_critical_points(spec: FISSpec, input_name: str) -> list[float]:
    variable = next(item for item in spec.inputs if item.name == input_name)
    points = {variable.minimum, variable.maximum}
    for term in variable.terms:
        points.update(term.parameters)
    return sorted(point for point in points if variable.minimum <= point <= variable.maximum)
