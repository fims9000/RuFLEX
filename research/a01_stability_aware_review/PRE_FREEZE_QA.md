# A01 Phase 0 pre-freeze QA receipt

Status: `A01 PROTOCOL LOCK READY — FINAL TEST NOT ACCESSED`.

## Scope and scientific boundary

- Product starting snapshot: Stability Lab RC2 `c610f5740f2b26d60eabd9069a298dc6022c9548`.
- This phase materialized and hash-verified source tables, generated a 300-run execution plan, and exercised only a temporary synthetic smoke project.
- It did **not** train an A01 benchmark study, create A01 validation results, create an A01 `FinalTestEvaluation`, compute final-test metrics, or make H1/H2/H3/risk-reduction claims.

## Locked identities

The exact values are in `config/locked_manifest.json`; the validator recomputes every listed identity from the actual protocol, dataset spec, model spec and JSONL plan.

- Primary protocol: `TRAINING_VARIABILITY`; split seed `42`; train/validation/final-test fractions `0.60/0.20/0.20`.
- Three datasets × five model families × twenty seeds `0..19` = 300 deterministic UUID5 planned executions.
- Each dataset has raw-source, canonical-table, and train/validation/final-test row-identity SHA-256 values.
- Selected run: maximum validation F1, then lowest training seed on exact ties.
- Raw validation F1 threshold only; gate constants are fixed at confidence `0.90`, selected-run agreement `0.80`, and probability standard deviation `0.15`.
- A01 cells fail closed as `INCOMPLETE_DECLARED_RUN_SUPPORT` when any declared seed does not yield required validation evidence.

## Commands executed

| Check | Result |
| --- | --- |
| `python research/a01_stability_aware_review/scripts/build_locked_protocol.py` | PASS — deterministic 300-row plan and manifest |
| `python research/a01_stability_aware_review/validate_pre_freeze.py` | PASS — final test not accessed |
| Declared-source materialization, SHA and split-identity recheck | PASS — three datasets; no training/evaluation |
| `python research/a01_stability_aware_review/scripts/run_smoke.py` | PASS — product-native synthetic route through Study → Evaluation → raw Threshold → StabilityAnalysis → Gate → reopen/lineage/assurance/bundle; no final test |
| Focused A01/Stability/Training/Lineage/Evidence pytest | PASS |
| Full Python suite | PASS — 139 collected tests |
| `compileall` for RuFLEX and A01 | PASS |
| Frontend unit / Vite / Storybook | PASS |
| Full Playwright including visual foundation | PASS — 25 tests |
| `git diff --check` | PASS |

## Known limitations

- The 300-run A01 matrix is locked but deliberately unexecuted. There are no empirical A01 results.
- Cross-run gate probabilities remain raw only; calibration and explanation stability remain separate descriptive evidence channels.
- A future confirmatory final-test batch requires a separate authorization and may only apply the frozen raw threshold and frozen Stability Gate.
