# A01 Phase 1.5 scientific freeze audit

Status: **SCIENTIFIC FREEZE AUDITED — H3 INPUTS LOCKED — FINAL TEST READY BUT CLOSED**.

## Preserved Phase 1 evidence

All 300 declared validation-only fits and all 15 complete cells are retained
unchanged.  The audit independently reloaded the persisted case/run evidence,
selected-run chains, raw threshold policies, Stability Gates, and comparator
policies.  It verified 300 model artifact hashes and their metadata.

## Amendment 001

The original Phase 1 H1 binary labels are withdrawn because the pre-specified
compactness condition was underspecified and the implementation tested only
for disagreement.  Every cell is now `NOT_ASSESSABLE` for confirmatory H1,
with `PRE_SPECIFIED_COMPACTNESS_RULE_UNDERSPECIFIED`; the underlying F1 and
case-level distributions are retained as descriptive exploratory evidence.

## Valid findings and pending questions

H2 is independently recomputed from frozen case evidence using selected-run
agreement.  H3, accepted-case risk, false-negative rate, and bootstrap CIs
remain pending because A01 final test has not been opened.  The audit found no
Flat Neuro-Fuzzy class-orientation or threshold-semantic defect: the two
default-0.50 F1=0 observations remain negative evidence, while their already
frozen validation thresholds reproduce their persisted F1 values.

## Boundaries

No model was retrained.  No policy was changed.  No A01 final-test data,
predictions, evaluation, unlock receipt, or final-result figure was created.
The evidence bundle is portable validation evidence; the runtime bundle is a
separate frozen-model package and contains no final-test rows.
