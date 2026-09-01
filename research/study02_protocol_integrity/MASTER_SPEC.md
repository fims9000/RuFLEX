# Master specification

The unit is a matched clean/corrupt scenario pair with exactly one planted,
oracle-hidden violation. Primary outcomes are scenario-level prevention,
retrospective detection, clean false blocks/warnings, family classification and
stage localization. Individual alerts are not independent observations.

## Frozen result row and review boundary

Each outcome row contains study/product/protocol/manifest/plan identity; stable
pair and scenario identity; requested and resolved data roles; actual Product
outcome and normalized exception; artifact and provenance identity; independent
baseline outcome; persistence/reopen state; false-block/warning values; and
runtime. It never contains hidden ground truth. The complete raw schema is
defined in `core.execution_contract.RAW_RESULT_FIELDS` before authorization.

The locked executor is an executable plan, not a placeholder: after a future
authorization it can resume interrupted runs while preserving previous rows.
Until that review authorization, all scientific outcome execution is forbidden.
