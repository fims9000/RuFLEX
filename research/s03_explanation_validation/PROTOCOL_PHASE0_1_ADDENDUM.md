# S03 Phase 0.1 protocol-to-implementation conformance addendum

This pre-execution addendum preserves the original S03 question and Phase 0
provenance. It freezes a single declared model fit for each dataset/model family
with `split_seed=3003`, `training_seed=3003`, train-only preprocessing, no HPO,
no seed selection, and validation-only explanation samples. Phase 1 will first
freeze 15 model artifacts, then select eight validation cases per dataset/model
by `stratified_by_true_and_predicted_class_then_source_row` with its frozen
fallback; it must freeze all 120 sample identities before any explanation check.

The primary scientific paired unit is `pair_id`. A clean/corrupt artifact pair
is created once; the same persisted corrupt artifact is then evaluated by
`IDENTITY_ONLY`, `METRIC_ONLY`, and `COMBINED`. Validator mode is not an
artifact identity. Duplicate/equivalent severity realizations are
`NOT_APPLICABLE`, never independent observations.

`IDENTITY_ONLY` contains only declared identity checks. `METRIC_ONLY` contains
replay integrity, native numerical completeness where applicable, and frozen
external Quantus paired rules where available. Repeatability is classified as
replay integrity, not generic explanation faithfulness. `COMBINED` is the OR of
all applicable declared components. Generic `FAILED` is detection but not
correct localization.

The external Quantus comparison uses only `quantus==0.6.0` and the fixed
inventory/parameters in `config/quantus_spec.json`. A continuous score signals
a matched-pair detection only when the corrupt score worsens in the declared
direction by more than the frozen numerical epsilon. No ROC cutoff, F1 cutoff,
or corruption-trained threshold is permitted.
