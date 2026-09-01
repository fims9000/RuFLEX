# Post-freeze scientific audit — Study 02 R1

R1 is preserved exactly as result-freeze evidence. Its raw artifact,
`THESIS_NUMBERS.json`, frozen identities, and archive are not modified.

## Qualification

V01 remains an audit-qualified narrow result: the canonical V1.0.1
logistic-training route derives preprocessing from the train-only split and an
effective `preprocessing_fit_scope` override is not exposed through this route.
This is prevention by canonical construction, not retrospective detection.

R1 V06/V07 corrupt calls supplied `uuid4()` values that did not identify a
persisted `FinalTestEvaluation`. The resulting `FileNotFoundError` establishes
only that the validation-evaluation namespace cannot resolve a nonexistent
identifier. It does **not** establish prevention on actual final-test evidence.
Their intended final-test prevention claims are therefore `NOT ESTABLISHED BY
R1 INTERVENTION`.

R1 BASIC_MANIFEST_AUDIT received `final_test_role_used` directly from the
clean/corrupt role. Its 60/60 corrupt alerts are retained as
`LABEL_DRIVEN_BASELINE_NOT_COMPARATIVE_EVIDENCE` and are not manuscript
comparative evidence.

## Consequence

`READY_FOR_MANUSCRIPT` for the intended full Study 02 claim is `NO` pending the
separate R2 confirmatory protocol. R2 has new protocol/manifest/plan identities
and does not overwrite R1.
