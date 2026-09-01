# Protocol (pre-freeze)

The final suite is locked only after fixture hashes, grid hashes, tolerance
classes, reference versions, and this document hash are materialized in
`config/locked_suite_manifest.json`. No final comparison is run before that
review.

The DEV suite contains analytic microcases and one declared Mamdani and one
declared Sugeno vertical slice. It may diagnose adapter defects but cannot be
used to tune a frozen final result.

All comparisons record finite/non-finite state before numerical tolerance.
Tolerance cannot convert an exception mismatch into a pass. For one-dimensional
fixtures the final grid includes both uniform nodes and critical MF/rule
boundary points; two-dimensional fixtures use a declared Cartesian grid.

## Pre-unlock review decision R01

The reference environment is pinned to CPython 3.12.12, NumPy 1.26.4, and
pyfuzzylite 8.0.6. Repeated DEV outputs are bitwise deterministic. The M01
Mamdani discrepancy is classified as `NUMERICAL_DISCRETIZATION_DIFFERENCE`:
RuFLEX uses an inclusive 401-node endpoint grid while pyfuzzylite's documented
`Centroid` uses midpoint-rectangle integration. Therefore Mamdani centroid
remains `PARTIAL` and is excluded from the primary `MATCH` matrix. Fixtures,
seeds, grids, metrics, and tolerances remain unchanged; TEST UNLOCK is still
forbidden pending explicit approval.

## Pre-unlock re-freeze R02 — V1.0.1 centroid semantics

The RC2.1 baseline and pre-unlock hashes were superseded before TEST UNLOCK by
the V1.0.1 pre-test implementation correction recorded in `DECISIONS.md`.
Standard Mamdani centroid evidence now declares 401 midpoint cells and may
enter the primary MATCH set only after the pinned reference DEV comparison.
Legacy inclusive nodes remain a separately labelled interoperability result.
No tolerance, fixture identity, seed, locked-grid definition, metric, or final
test result was changed. TEST UNLOCK remains forbidden pending the newly frozen
manifest and explicit protocol review.
