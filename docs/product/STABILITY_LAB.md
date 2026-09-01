# Stability Lab and Stability-Aware Review

RuFLEX records distinct sources of randomness. `split_seed` controls only data-partition membership; `training_seed` controls model fitting randomness. The legacy `seed` field is retained for compatibility: persisted objects without explicit seeds resolve it as both values and are labelled `LEGACY_COMBINED`.

`TRAINING_VARIABILITY` fixes one split and varies only training seeds. This is the required protocol for a `StudyStabilityAnalysis`, because every run must share the same dataset revision and exact validation-case identity. `SPLIT_VARIABILITY` and `COMBINED_VARIABILITY` are useful sensitivity protocols but are not interchangeable with a pure training-randomness comparison.

`StudyStabilityAnalysis` is validation-only persisted evidence. It reports aggregate metric distributions and per-case prediction disagreement, including class agreement, probability dispersion, vote entropy, and High-Confidence Instability Rate (HCIR). Close mean metrics, and high confidence from the selected run, do not prove stable individual decisions.

`StabilityGatePolicy` is a separately persisted validation-derived policy. It sends a case to `REVIEW` for low confidence, independent-run disagreement, or excessive probability dispersion. A `GeneralizationContract` block takes precedence as `BLOCK`. Explanation reproducibility is intentionally not a gate input: explanation stability is a separate evidence channel and is never inferred from prediction agreement.

The final-test route can bind an already frozen Stability Gate policy to final-test evidence, but cannot fit or retune it. Any policy created after final-test access is rejected by the same dataset-level final-test firewall.
