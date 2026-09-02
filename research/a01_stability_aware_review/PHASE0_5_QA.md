# A01 Phase 0.5 statistical-analysis freeze QA receipt

Status: `A01 PHASE 0.5 STATISTICAL ANALYSIS FROZEN`.

This receipt covers a research-only freeze.  It contains no A01 benchmark
TrainingRun, validation result, FinalTestEvaluation, empirical H1/H2/H3
verdict, or risk-reduction claim.

## Immutable provenance inherited from Phase 0

| Input | SHA-256 / ID |
| --- | --- |
| Protocol | `bfcb27f48f1d1aa8552cdf5465c0b89b712c3d035d58ccc9d6088dcabd500469` |
| Dataset specification | `c5bc7d8d5842067147d28263fa96ae35374fe56afd411ff2ff7a286eace44b42` |
| Model specification | `7368bdf6707e2c5c3179c0544bcea5aee5e9a28e61d05ccbf4f483397e5924ef` |
| Execution plan | `5794a27071843af36aab1ce7aa179f40681b677d7d4253edfd8c19768679aa2e` |
| Phase 0 manifest | `ac3ba69bbca49a8214156aca9cf521e0bdb517d46677b7bab027765439fe5816` |

The Phase 0.5 manifest binds those inputs plus the exact statistical-analysis
plan. The final commit and source archive identifiers are appended only after
the archive QA finishes; they are not inputs to the scientific plan.

| Phase 0.5 statistical-analysis plan | `59c411cf345350e012bcb9011ba56192f4e796e787fe5ce40ed05a68fc8c707d` |
| Phase 0.5 manifest | `89d1618fb2ecab090ea6ca98ab6e54c91aa87f3a8be6a329696ba40c1dc838cd` |

## Checks executed

| Check | Result |
| --- | --- |
| Focused Phase 0 + Phase 0.5 tests | `28 passed` |
| Full Python suite | `157 passed` |
| Python collection | `157 tests collected` |
| `compileall` for `src/ruflex` and `research/a01_stability_aware_review` | pass |
| Fail-closed pre-freeze validator | pass |
| Deterministic Phase 0.5 manifest rebuild | pass |
| `git diff --check` | pass |

## Explicit non-execution scan

The validator rejects files in the declared A01 benchmark-training/result,
validation, study, and final-test artifact locations. The release QA also
performs that explicit scan before packaging.

`NO A01 BENCHMARK TRAINING RUNS EXECUTED.`

`NO A01 FINAL-TEST DATA ACCESSED.`

## Known limitations

- This freezes analysis definitions only; it does not provide empirical A01
  evidence.
- The planned final-test phase remains forbidden until a separate authorization.
- H1/H2/H3 use the frozen descriptive/uncertainty labels only after the planned
  execution matrix completes with 20/20 declared runs per cell.
