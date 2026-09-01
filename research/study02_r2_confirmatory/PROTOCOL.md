# Study 02 R2 — confirmatory protocol

R2 is a new pre-unlock confirmatory battery for V06 and V07 only: 20 matched
pairs per family. It preserves Product V1.0.1 and does not rewrite R1.

Each pair materializes deterministic tabular input from its frozen parameters.
The clean path uses a persisted validation `AnalysisEvaluation`. Before the
corrupt path, the same project creates a legitimate persisted
`FinalTestEvaluation` through `evaluate_final_test`. The exact resulting final
test ID is supplied to the validation-only threshold/calibration service.

The corrupt result is derived from the persisted source artifact, actual product
call, exception/result, and resulting artifact absence. A failure to resolve an
existing final-test ID in the validation-evaluation namespace is classified
`PREVENTED_BY_VALIDATION_ONLY_ARTIFACT_INTERFACE`, not a semantic firewall.
No comparative baseline is used in R2.

The expected locked result is fixed before authorization: each family requires
20 clean `ALLOWED_VALID` rows and 20 corrupt
`PREVENTED_BY_VALIDATION_ONLY_ARTIFACT_INTERFACE` rows for full confirmatory
support. Any deviation is a preserved negative result and downgrades only the
affected family verdict. No threshold, policy, or criterion is changed after
results. Every pair stores both execution identity (`base_input_hash`) and a
separate canonical-table-only `data_content_sha256`.

The frozen manifest is immutable. Authorization is external at
`.agent-state/STUDY02_R2_TEST_AUTHORIZATION.json` and must match all frozen
identities. Before authorization only plan validation/DEV work is allowed.
