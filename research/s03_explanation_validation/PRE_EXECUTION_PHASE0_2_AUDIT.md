# S03 Phase 0.2 final pre-benchmark executability audit

This is a superseding pre-execution layer over Phase 0.1. No S03 benchmark
model, explanation, detection result, or clean false-rejection observation was
created before this audit.

The Phase 0.1 builder accidentally omitted clean controls. Phase 0.2 restores
the 264 unique clean artifact keys and evaluates each through all three frozen
validator modes: 792 clean evaluations. The plan is therefore 5,808 corrupt
artifacts, 264 clean controls, 17,424 corrupt evaluations, and 18,216 total
validator evaluations.

The frozen sample fallback is exact: use strata `00`, `01`, `10`, `11` in that
order; take up to two lowest `source_row` cases in each; then fill to eight from
unused validation rows in ascending `source_row`; validation support under eight
is fail closed. Numerical completeness remains descriptive because current
Product V1 emits `WARN`, not `FAIL`, for excess error.

Quantus 0.6.0 is installed only in the research venv. Its two frozen metrics
were invoked on synthetic tabular product-adapter/explanation shapes for every
planned model/explainer route. This establishes call compatibility only, not a
benchmark score or calibration.
