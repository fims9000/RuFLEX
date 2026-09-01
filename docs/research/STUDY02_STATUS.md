# Study 02 status

## Frozen Product subject

Study 02 uses RuFLEX Product V1.0.1, SHA-256 `772270a076e77b9c36d07e51bae8e45f5a3b1eddd69045176e63dc83834a3224`.

## Study 02 R1

R1 remains immutable. Its V01 result is audit-qualified and narrow: the canonical logistic-training route derives preprocessing from the training partition and does not expose an effective broader `preprocessing_fit_scope` override. R1's V06 and V07 interventions are `NOT_ESTABLISHED_BY_R1_INTERVENTION`, because they used nonexistent UUIDs, not persisted final-test artifacts. Its label-driven basic-manifest result is `LABEL_DRIVEN_BASELINE_NOT_COMPARATIVE_EVIDENCE`.

## Study 02 R2 confirmatory result

R2 frozen identifiers are protocol SHA-256 `8f0e56371343a454a6af83830c5af6fdae481059e4cf5bfef746ff732af67440`, manifest ID `c6d892f648728684a9c4f48f112c8bea12b9bae9b961c80baf68b5b1c4ba1544`, and execution-plan SHA-256 `c0ecc52380d5058fc62dfa40f8a20c41f883c10ba490589b1439e98aad63c2ab`.

The locked R2 suite contains 40 matched pairs (20 V06 and 20 V07) and 80 scenario executions. Every clean request used a persisted validation `AnalysisEvaluation` and was allowed. Every corrupt request first created a legitimate persisted `FinalTestEvaluation`, supplied its exact identifier to the validation-only interface, and was prevented because that interface does not resolve it as an `AnalysisEvaluation`. All 80 reopen checks passed.

## Allowed claims

- Canonical Product V1.0.1 preprocessing construction prevented the tested broader preprocessing-scope violation by construction (qualified R1 V01).
- The tested validation-only threshold and calibration interfaces rejected actual persisted `FinalTestEvaluation` identifiers across the frozen R2 V06/V07 suite.

## Forbidden claims

Study 02 does not establish universal leakage detection, a generic experimental-integrity guarantee, generic final-test semantic detection, group-leakage detection, best-seed reporting detection, or arbitrary evidence/sample-identity validation.

## Next research study

S03 should be independently designed and protocol-reviewed before any new locked execution. It must not reinterpret or overwrite Study 02 R1/R2 evidence.
