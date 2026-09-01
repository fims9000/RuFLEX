# Centroid numerical semantics

RuFLEX V1.0.1 makes the finite sampling rule of a Mamdani centroid part of
the canonical FIS semantics. A centroid is evaluated from the persisted
`method`, `resolution`, and `sampling` configuration; the sampling convention
therefore contributes to the FIS semantic hash and trace evidence.

## Inclusive nodes — legacy RuFLEX

For `N >= 2`, `dx = (x_max - x_min)/(N - 1)` and
`x_i = x_min + i*dx`, `i = 0 … N-1`. This is the RC2.1 behavior. A persisted
RC2.1 FIS without sampling metadata is migrated to `inclusive_nodes`, so it
does not silently change numerical behavior on reopen.

## Midpoint cells — V1.0.1 default

For `N >= 1`, `dx = (x_max - x_min)/N` and
`x_i = x_min + (i + 0.5)*dx`, `i = 0 … N-1`. The aggregated membership is
sampled at these cell centres and the discrete weighted centroid is calculated
from the same samples. This matches the pinned pyfuzzylite 8.0.6 `Centroid(N)`
midpoint-rectangle convention for the declared compatible subset.

## Trace and interoperability

Mamdani traces persist method, output domain, resolution, sampling strategy,
`dx`, sample count, coordinates, and sampled aggregated membership. A trace
can consequently be reconstructed without invoking inference.

MATLAB `.fis` files declare `centroid` but not this finite-sampling convention.
RuFLEX imports them with the canonical midpoint-cell policy and an explicit
compatibility warning; this is not a claim that the source format specified
that convention. A known FuzzyLite adapter should choose midpoint cells.
