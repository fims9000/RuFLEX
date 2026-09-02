# S03 Phase 0.1 statistical-plan addendum

All original Phase 0 estimands remain: Wilson 95% intervals for detection and
false rejection, applicability coverage, localization, exact paired McNemar
comparisons when both outcomes are defined, and Holm correction inside each
predeclared comparison family. The Phase 0.1 unit for every paired comparison
is explicitly `pair_id`; validator-mode rows are evaluations of the same
artifact rather than independent corruptions. `NOT_APPLICABLE`,
`NOT_AVAILABLE`, invalid input, and severity-equivalent artifacts are excluded
from the corresponding detection denominator and reported as coverage.

No numeric Quantus cutoff is learned from S03 corruptions. The frozen paired
direction-and-epsilon rule is the only external metric detector. Detection and
localization remain distinct: generic failure does not earn localization credit.
