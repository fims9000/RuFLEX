# A01 Phase 1 — validation-only execution and policy freeze

Status: `A01 PHASE 1 VALIDATION EXECUTION COMPLETE — POLICIES FROZEN — FINAL TEST CLOSED`.

This is the frozen 300-run `TRAINING_VARIABILITY` matrix: one split
(`split_seed=42`) and twenty declared training seeds (`0..19`) for each
dataset/model cell. It is validation evidence, not a confirmatory final-test
result. H3 is `NOT_ASSESSABLE` for every cell because the final test remains
closed.

## Frozen validation results

| Dataset | Model | Selected seed | Validation F1 mean ± SD | Raw threshold | HCIR | Stability coverage | Confidence cutoff | Confidence coverage | Gap | H1 | H2 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| AI4I 2020 | Logistic Regression | 0 | 0.3200 ± 0.0000 | 0.19 | 0.0000 | 0.9165 | 0.900214 | 0.9165 | 0.0000 | PATTERN_NOT_OBSERVED | PATTERN_NOT_OBSERVED |
| AI4I 2020 | Decision Tree | 7 | 0.6460 ± 0.0149 | 0.50 | 0.0090 | 0.9885 | 1.000000 | 1.0000 | 0.0115 | PATTERN_OBSERVED | PATTERN_OBSERVED |
| AI4I 2020 | Random Forest | 10 | 0.6369 ± 0.0192 | 0.32 | 0.0000 | 0.9295 | 0.920000 | 0.9295 | 0.0000 | PATTERN_OBSERVED | PATTERN_NOT_OBSERVED |
| AI4I 2020 | Gradient Boosting | 1 | 0.6826 ± 0.0097 | 0.33 | 0.0000 | 0.9505 | 0.901058 | 0.9505 | 0.0000 | PATTERN_OBSERVED | PATTERN_NOT_OBSERVED |
| AI4I 2020 | Flat Neuro-Fuzzy | 0 | 0.0000 ± 0.0000 | 0.14 | 0.0000 | 0.8935 | 0.900181 | 0.8935 | 0.0000 | PATTERN_OBSERVED | PATTERN_NOT_OBSERVED |
| Bank Marketing | Logistic Regression | 0 | 0.3587 ± 0.0000 | 0.21 | 0.0000 | 0.7649 | 0.900095 | 0.7649 | 0.0000 | PATTERN_NOT_OBSERVED | PATTERN_NOT_OBSERVED |
| Bank Marketing | Decision Tree | 18 | 0.3239 ± 0.0050 | 0.50 | 0.0619 | 0.9068 | 1.000000 | 0.8672 | 0.0396 | PATTERN_OBSERVED | PATTERN_OBSERVED |
| Bank Marketing | Random Forest | 14 | 0.3997 ± 0.0086 | 0.31 | 0.0010 | 0.7028 | 0.900000 | 0.7036 | 0.0007 | PATTERN_OBSERVED | PATTERN_OBSERVED |
| Bank Marketing | Gradient Boosting | 0 | 0.3541 ± 0.0000 | 0.18 | 0.0000 | 0.7856 | 0.900000 | 0.7856 | 0.0000 | PATTERN_NOT_OBSERVED | PATTERN_NOT_OBSERVED |
| Bank Marketing | Flat Neuro-Fuzzy | 0 | 0.0000 ± 0.0000 | 0.12 | 0.0000 | 0.2088 | 0.941847 | 0.2088 | 0.0000 | PATTERN_NOT_OBSERVED | PATTERN_NOT_OBSERVED |
| Wisconsin Diagnostic | Logistic Regression | 0 | 0.9655 ± 0.0000 | 0.76 | 0.0000 | 0.8947 | 0.915641 | 0.8947 | 0.0000 | PATTERN_NOT_OBSERVED | PATTERN_NOT_OBSERVED |
| Wisconsin Diagnostic | Decision Tree | 0 | 0.9181 ± 0.0059 | 0.50 | 0.0088 | 0.9737 | 1.000000 | 1.0000 | 0.0263 | PATTERN_OBSERVED | PATTERN_OBSERVED |
| Wisconsin Diagnostic | Random Forest | 6 | 0.9352 ± 0.0132 | 0.57 | 0.0000 | 0.7895 | 0.920000 | 0.7895 | 0.0000 | PATTERN_OBSERVED | PATTERN_NOT_OBSERVED |
| Wisconsin Diagnostic | Gradient Boosting | 0 | 0.9417 ± 0.0042 | 0.78 | 0.0000 | 0.9211 | 0.905157 | 0.9211 | 0.0000 | PATTERN_NOT_OBSERVED | PATTERN_NOT_OBSERVED |
| Wisconsin Diagnostic | Flat Neuro-Fuzzy | 3 | 0.9061 ± 0.0060 | 0.61 | 0.0000 | 0.7895 | 0.902971 | 0.7895 | 0.0000 | PATTERN_OBSERVED | PATTERN_NOT_OBSERVED |

## Interpretation boundaries

- Validation H1/H2 labels are descriptive outputs of the locked plan.
- Decision Tree and Random Forest show nonzero validation HCIR in the listed
  cells; all remaining cells retain their observed zero HCIR rather than being
  tuned for a more dramatic pattern.
- Flat Neuro-Fuzzy produced zero validation F1 on AI4I and Bank Marketing in
  this frozen configuration. This negative result is retained.
- No final-test prediction, metric, accepted-case risk, FNR, bootstrap CI, or
  H3 verdict was computed. `H3 = NOT_ASSESSABLE / FINAL_TEST_NOT_OPENED` for
  every cell.

## Evidence layout

Compact frozen receipts, tables, figures, checksums, and object hashes are in
`results/phase1_validation/`. Full case-level product evidence is persisted in
the corresponding canonical project workspaces and duplicated only under the
ignored aggregated-evidence directory; it is intentionally not committed as a
large raw-prediction source artifact.
