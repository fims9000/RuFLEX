# Amendment 001 — H1 underspecification

Status: RECORDED AFTER VALIDATION; FINAL TEST REMAINS CLOSED.

This amendment was made after A01 benchmark validation evidence had been
observed.  No A01 final-test data were opened, no model was retrained, and no
selected run, raw decision threshold, Stability Gate, or confidence-only
policy was changed.

## Defect

The frozen SAP required H1 to jointly describe a compact aggregate validation
F1 distribution and meaningful case-level disagreement.  The Phase 1
orchestrator instead assigned `PATTERN_OBSERVED` whenever any case had
`selected_run_agreement < 1`.  That rule tested only the second condition and
did not implement the written compactness condition.

Introducing a numerical compactness margin after validation has been viewed
would be post-hoc.  Therefore the original binary H1 labels are withdrawn,
not repaired by a new cutoff.

## Corrected interpretation

For all fifteen A01 cells, `H1_CONFIRMATORY_STATUS` is
`NOT_ASSESSABLE` with reason
`PRE_SPECIFIED_COMPACTNESS_RULE_UNDERSPECIFIED`.  The frozen F1
distributions, probability-dispersion distributions, pairwise disagreement,
and selected-run-agreement summaries remain valid descriptive exploratory
evidence and are retained unchanged.

## Scope

H2 remains numerically pre-specified and must be independently recomputed
from frozen case evidence.  H3's final-test protocol, matched-coverage
comparator, bootstrap plan, and policy inputs are unaffected.  This amendment
does not authorize final-test access.
