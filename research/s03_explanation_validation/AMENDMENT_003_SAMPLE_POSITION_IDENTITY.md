# Amendment 003 — persisted validation-row identity

The R5 CLEAN baseline stopped before its freeze after 15 model fits and 176
unfrozen CLEAN explanations.  No corrupt artifact, detection/localization
result, or final-test access occurred.

`TrainingRun.prediction_preview.source_row` is the persisted zero-based table
position used by the product split evidence.  It is not necessarily the source
identifier column declared by a dataset.  Wisconsin Diagnostic uses external
patient identifiers, so resolving `source_row=37` through its `id` column was
incorrect.  The affected executor failed closed instead of substituting a row.

The corrected R6 executor resolves frozen prediction evidence by canonical
materialized-table position (`frame.iloc[source_row]`) and verifies that its
target matches the persisted validation truth.  The original dataset source-ID
columns remain part of DatasetContract provenance; this amendment only makes
the sample-materialization implementation match the product-native prediction
evidence identity.

This is a pre-CLEAN-freeze implementation correction.  No model, explainer,
validator, corruption, severity, sample-selection rule, dataset, or scientific
outcome is changed.  R5 is historical interrupted execution only.
