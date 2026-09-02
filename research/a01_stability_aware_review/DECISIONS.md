# A01 decisions

## Phase 0 — pre-freeze hardening

- Product subject: RC2 source snapshot `c610f5740f2b26d60eabd9069a298dc6022c9548`.
- The benchmark data sources are materialized deterministically only to establish source/table identities. No A01 TrainingStudy, validation result, final-test evaluation, or empirical claim is created in this phase.
- `max_probability_std = 0.15`, `min_confidence = 0.90`, and `min_class_agreement = 0.80` are pre-specified pre-final-test constants. They are not fitted after A01 validation inspection.
- Operational class labels use the exact raw validation-derived threshold. HCIR and `RUN_DISAGREEMENT` use selected-run agreement, never majority consensus.
- Each primary dataset/model family requires twenty declared seed runs; fewer successful runs are `INCOMPLETE_DECLARED_RUN_SUPPORT`, not a 19/20 result.
- Bank Marketing `duration` and AI4I component-failure columns are excluded before product import for the declared target-leakage reasons in the dataset spec.
