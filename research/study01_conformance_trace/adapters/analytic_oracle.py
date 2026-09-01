from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class OracleResult:
    memberships: dict[str, float]
    firing_strengths: dict[str, float]
    normalized_weights: dict[str, float]
    consequent_values: dict[str, float]
    final_output: float
    derivation: str


def zero_order_sugeno(x: float) -> OracleResult:
    """Independent derivation for the DEV S01 two-rule system.

    μ_low=1-x, μ_high=x, hence y=((1-x)*0.2+x*0.8)/((1-x)+x).
    """
    if not 0.0 <= x <= 1.0:
        raise ValueError("DEV oracle domain is [0,1].")
    low, high = 1.0 - x, x
    denominator = low + high
    return OracleResult(
        memberships={"x.low": low, "x.high": high}, firing_strengths={"low to 0.2": low, "high to 0.8": high},
        normalized_weights={"low to 0.2": low / denominator, "high to 0.8": high / denominator},
        consequent_values={"low to 0.2": 0.2, "high to 0.8": 0.8}, final_output=0.2 + 0.6 * x,
        derivation="y=((1-x)*0.2+x*0.8)/((1-x)+x)=0.2+0.6x",
    )


def linear_sugeno(x: float) -> OracleResult:
    """Independent equal-firing linear Sugeno micro-oracle: (x + (2x+1))/2."""
    return OracleResult(
        memberships={"a": 1.0, "b": 1.0}, firing_strengths={"r1": 1.0, "r2": 1.0},
        normalized_weights={"r1": 0.5, "r2": 0.5}, consequent_values={"r1": x, "r2": 2.0 * x + 1.0},
        final_output=(3.0 * x + 1.0) / 2.0, derivation="equal weights: (x + (2x+1))/2",
    )


def symmetric_mamdani_centroid() -> OracleResult:
    """A symmetry oracle: mirrored equal clipped output sets have centroid 0.5."""
    return OracleResult(
        memberships={"x.low": 0.5, "x.high": 0.5}, firing_strengths={"low": 0.5, "high": 0.5},
        normalized_weights={}, consequent_values={}, final_output=0.5,
        derivation="The aggregated membership curve is mirror-symmetric about 0.5; its discrete inclusive symmetric grid centroid is 0.5.",
    )


def assert_finite(result: OracleResult) -> None:
    if not math.isfinite(result.final_output):
        raise AssertionError("Analytic oracle produced a non-finite output.")
