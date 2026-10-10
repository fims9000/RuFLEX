# Native linear model-kind/task contract

This product-runtime correction is separate from frozen A01/S03 research.

## Reproduction and cause

Before the correction, a direct training request for `linear_regression` on a
binary-classification DatasetContract returned HTTP 201. The `native_linear`
adapter fitted `LogisticRegression` according to the dataset task, while the
persisted TrainingRun claimed `model_kind=linear_regression`. Conversely, the
adapter could fit `LinearRegression` while a regression run claimed
`logistic_regression`. The catalog described both kinds and both tasks but did
not express which pair was valid.

## Resolution

The adapter descriptor and catalog now declare the exact pairs:

- `logistic_regression` → `binary_classification`;
- `linear_regression` → `regression`.

Core training, synchronous Study submission, new and resumed StudyJobs reject
unsupported pairs before fitting. The native adapter also checks the requested
model kind, and the core rejects a JSON artifact that claims a different kind.
Studio selects a kind using the catalog's per-kind task mapping. Reopening a
historical run with an unsupported kind/task pair fails adapter compatibility
and Project Integrity; persisted evidence is not rewritten or silently
reinterpreted.

The real regression browser route also exposed a presentation failure: an
almost exact linear fit produced loss near `3e-29`, which caused ECharts'
automatic scaled axis to throw and blank Studio. The trajectory plot now uses
a display-only non-negative axis with a `1e-12` span floor for such tiny
losses; underlying loss evidence is unchanged. Reopened Studio selection now
reflects the compatible persisted run kind instead of an unrelated default.

The previous runtime-matrix test generated a Cartesian product of kinds and
tasks, thereby treating the invalid native-linear pairs as positive examples.
It now enumerates declared pairs for positive coverage and explicitly asserts
that undeclared pairs fail before a run is persisted. An unrelated typed-error
test fixture was also corrected to create the DatasetContract required by the
existing product preflight; that test still asserts the exact typed error.

## Verification

Focused runtime/catalog/training/integrity Python tests, the Training Studio
component suite, synthetic classification and regression training/reopen
browser routes, TypeScript/
Vite build, `compileall`, and `git diff --check` were run. No benchmark model
was fitted and no frozen research artifact was changed.
The regression browser route also saved and reopened its exact validation
Evaluation, then applied an explicit synthetic final-test opening and reopened
the resulting FinalTestEvaluation; it did not access benchmark test data.
