# Decisions

## D01 — subject isolation

The RC2.1 source archive is the subject under test.  Study code lives below
`research/study01_conformance_trace` and does not alter product semantics.

## D02 — comparator boundary

pyfuzzylite is used only for operations explicitly recorded as `MATCH` in
`config/semantic_intersection.json`. Its `Centroid(401)` is configured to
mirror RuFLEX's declared 401-node discrete output grid, then independently
checked on DEV cases. Operations with divergent boundary or discretization
semantics remain `PARTIAL`, not silently tolerated.

## D03 — environment caveat

The host runs Python 3.14 while pyfuzzylite declares `numpy<2`; it is not used
as the comparator runtime. A dedicated CPython 3.12.12 environment pins NumPy
1.26.4 and pyfuzzylite 8.0.6. Its exact package inventory is captured in
`config/environments.json` and repeated DEV outputs are deterministic.

## D04 — Mamdani centroid classification

M01 at x=0.25 confirms the RuFLEX output exactly matches an independently
recomputed inclusive 401-node discrete centroid. pyfuzzylite's documented
`Centroid` uses midpoint rectangle integration, yielding a different value.
This is `NUMERICAL_DISCRETIZATION_DIFFERENCE`; Mamdani centroid stays
`PARTIAL`, is excluded from primary MATCH comparisons, and is not resolved by
changing tolerance.

## D05 — pre-test implementation correction

The DEV-only M01 discrepancy identified a `NUMERICAL_DISCRETIZATION_DIFFERENCE`:
RC2.1 used inclusive endpoint nodes while pyfuzzylite `Centroid(401)` uses
midpoint cells. No locked Study 01 case had been executed. RuFLEX V1.0.1 makes
centroid sampling explicit, adopts midpoint cells for new standard Mamdani FIS
definitions, and preserves missing legacy sampling as inclusive nodes.

The old protocol and locked-manifest hashes are superseded records, not deleted.
Fixture identities, seeds, grids, metrics, and numerical tolerance values remain
unchanged. This is a pre-test implementation correction, not post-test tuning.
