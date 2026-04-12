from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .enums import MembershipKind


@dataclass(frozen=True)
class MembershipFunctionSpec:
    kind: MembershipKind
    term_names: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def evaluate(self, values: np.ndarray) -> np.ndarray:
        raise NotImplementedError


@dataclass(frozen=True)
class GaussianMembershipSpec(MembershipFunctionSpec):
    centers: tuple[float, ...]
    spreads: tuple[float, ...]
    min_spread: float = 1e-3

    def __init__(
        self,
        centers: tuple[float, ...],
        spreads: tuple[float, ...],
        term_names: tuple[str, ...] | None = None,
        min_spread: float = 1e-3,
    ) -> None:
        if len(centers) != len(spreads):
            raise ValueError("centers and spreads must have the same length.")
        names = term_names or tuple(f"term_{index}" for index in range(len(centers)))
        object.__setattr__(self, "kind", MembershipKind.GAUSSIAN)
        object.__setattr__(self, "term_names", tuple(names))
        object.__setattr__(self, "centers", tuple(float(value) for value in centers))
        object.__setattr__(self, "spreads", tuple(max(float(value), min_spread) for value in spreads))
        object.__setattr__(self, "min_spread", float(min_spread))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "term_names": list(self.term_names),
            "centers": list(self.centers),
            "spreads": list(self.spreads),
            "min_spread": self.min_spread,
        }

    def evaluate(self, values: np.ndarray) -> np.ndarray:
        x = np.asarray(values, dtype=float).reshape(-1, 1)
        centers = np.asarray(self.centers, dtype=float).reshape(1, -1)
        spreads = np.asarray(self.spreads, dtype=float).reshape(1, -1)
        variances = np.maximum(spreads**2, self.min_spread**2)
        return np.exp(-((x - centers) ** 2) / (2.0 * variances))


@dataclass(frozen=True)
class GeneralizedBellMembershipSpec(MembershipFunctionSpec):
    centers: tuple[float, ...]
    widths: tuple[float, ...]
    slopes: tuple[float, ...]
    min_width: float = 1e-3
    min_slope: float = 1e-2

    def __init__(
        self,
        centers: tuple[float, ...],
        widths: tuple[float, ...],
        slopes: tuple[float, ...],
        term_names: tuple[str, ...] | None = None,
        min_width: float = 1e-3,
        min_slope: float = 1e-2,
    ) -> None:
        if not (len(centers) == len(widths) == len(slopes)):
            raise ValueError("centers, widths, and slopes must have the same length.")
        names = term_names or tuple(f"term_{index}" for index in range(len(centers)))
        object.__setattr__(self, "kind", MembershipKind.GENERALIZED_BELL)
        object.__setattr__(self, "term_names", tuple(names))
        object.__setattr__(self, "centers", tuple(float(value) for value in centers))
        object.__setattr__(self, "widths", tuple(max(float(value), min_width) for value in widths))
        object.__setattr__(self, "slopes", tuple(max(float(value), min_slope) for value in slopes))
        object.__setattr__(self, "min_width", float(min_width))
        object.__setattr__(self, "min_slope", float(min_slope))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "term_names": list(self.term_names),
            "centers": list(self.centers),
            "widths": list(self.widths),
            "slopes": list(self.slopes),
            "min_width": self.min_width,
            "min_slope": self.min_slope,
        }

    def evaluate(self, values: np.ndarray) -> np.ndarray:
        x = np.asarray(values, dtype=float).reshape(-1, 1)
        centers = np.asarray(self.centers, dtype=float).reshape(1, -1)
        widths = np.asarray(self.widths, dtype=float).reshape(1, -1)
        slopes = np.asarray(self.slopes, dtype=float).reshape(1, -1)
        normalized = np.maximum(np.abs((x - centers) / widths), 1e-12)
        return 1.0 / (1.0 + normalized ** (2.0 * slopes))


@dataclass(frozen=True)
class TriangularMembershipSpec(MembershipFunctionSpec):
    left: tuple[float, ...]
    center: tuple[float, ...]
    right: tuple[float, ...]

    def __init__(
        self,
        left: tuple[float, ...],
        center: tuple[float, ...],
        right: tuple[float, ...],
        term_names: tuple[str, ...] | None = None,
    ) -> None:
        if not (len(left) == len(center) == len(right)):
            raise ValueError("left, center, and right must have the same length.")
        names = term_names or tuple(f"term_{index}" for index in range(len(left)))
        object.__setattr__(self, "kind", MembershipKind.TRIANGULAR)
        object.__setattr__(self, "term_names", tuple(names))
        object.__setattr__(self, "left", tuple(float(value) for value in left))
        object.__setattr__(self, "center", tuple(float(value) for value in center))
        object.__setattr__(self, "right", tuple(float(value) for value in right))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "term_names": list(self.term_names),
            "left": list(self.left),
            "center": list(self.center),
            "right": list(self.right),
        }

    def evaluate(self, values: np.ndarray) -> np.ndarray:
        x = np.asarray(values, dtype=float).reshape(-1, 1)
        left = np.asarray(self.left, dtype=float).reshape(1, -1)
        center = np.asarray(self.center, dtype=float).reshape(1, -1)
        right = np.asarray(self.right, dtype=float).reshape(1, -1)
        rising = np.divide(x - left, center - left, out=np.zeros_like(x - left), where=(center - left) != 0)
        falling = np.divide(right - x, right - center, out=np.zeros_like(x - left), where=(right - center) != 0)
        return np.clip(np.minimum(rising, falling), 0.0, 1.0)


@dataclass(frozen=True)
class TrapezoidalMembershipSpec(MembershipFunctionSpec):
    left: tuple[float, ...]
    left_top: tuple[float, ...]
    right_top: tuple[float, ...]
    right: tuple[float, ...]

    def __init__(
        self,
        left: tuple[float, ...],
        left_top: tuple[float, ...],
        right_top: tuple[float, ...],
        right: tuple[float, ...],
        term_names: tuple[str, ...] | None = None,
    ) -> None:
        if not (len(left) == len(left_top) == len(right_top) == len(right)):
            raise ValueError("trapezoidal parameters must have the same length.")
        names = term_names or tuple(f"term_{index}" for index in range(len(left)))
        object.__setattr__(self, "kind", MembershipKind.TRAPEZOIDAL)
        object.__setattr__(self, "term_names", tuple(names))
        object.__setattr__(self, "left", tuple(float(value) for value in left))
        object.__setattr__(self, "left_top", tuple(float(value) for value in left_top))
        object.__setattr__(self, "right_top", tuple(float(value) for value in right_top))
        object.__setattr__(self, "right", tuple(float(value) for value in right))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "term_names": list(self.term_names),
            "left": list(self.left),
            "left_top": list(self.left_top),
            "right_top": list(self.right_top),
            "right": list(self.right),
        }

    def evaluate(self, values: np.ndarray) -> np.ndarray:
        x = np.asarray(values, dtype=float).reshape(-1, 1)
        left = np.asarray(self.left, dtype=float).reshape(1, -1)
        left_top = np.asarray(self.left_top, dtype=float).reshape(1, -1)
        right_top = np.asarray(self.right_top, dtype=float).reshape(1, -1)
        right = np.asarray(self.right, dtype=float).reshape(1, -1)
        rising = np.divide(x - left, left_top - left, out=np.zeros_like(x - left), where=(left_top - left) != 0)
        falling = np.divide(right - x, right - right_top, out=np.zeros_like(x - left), where=(right - right_top) != 0)
        plateau = np.where((x >= left_top) & (x <= right_top), 1.0, 0.0)
        return np.clip(np.maximum(np.minimum(rising, 1.0), np.minimum(falling, 1.0)) * (1.0 - plateau) + plateau, 0.0, 1.0)


def membership_from_dict(config: dict[str, Any]) -> MembershipFunctionSpec:
    kind = MembershipKind(config["kind"])
    if kind is MembershipKind.GAUSSIAN:
        return GaussianMembershipSpec(
            centers=tuple(config["centers"]),
            spreads=tuple(config["spreads"]),
            term_names=tuple(config.get("term_names", ())),
            min_spread=config.get("min_spread", 1e-3),
        )
    if kind is MembershipKind.GENERALIZED_BELL:
        return GeneralizedBellMembershipSpec(
            centers=tuple(config["centers"]),
            widths=tuple(config["widths"]),
            slopes=tuple(config["slopes"]),
            term_names=tuple(config.get("term_names", ())),
            min_width=config.get("min_width", 1e-3),
            min_slope=config.get("min_slope", 1e-2),
        )
    if kind is MembershipKind.TRIANGULAR:
        return TriangularMembershipSpec(
            left=tuple(config["left"]),
            center=tuple(config["center"]),
            right=tuple(config["right"]),
            term_names=tuple(config.get("term_names", ())),
        )
    if kind is MembershipKind.TRAPEZOIDAL:
        return TrapezoidalMembershipSpec(
            left=tuple(config["left"]),
            left_top=tuple(config["left_top"]),
            right_top=tuple(config["right_top"]),
            right=tuple(config["right"]),
            term_names=tuple(config.get("term_names", ())),
        )
    raise ValueError(f"Unsupported membership kind: {kind}.")

