# A01 final confirmatory results

## 1. Research question

Does a validation-frozen Stability Gate change accepted-case risk relative to a validation-matched frozen confidence-only policy? This report is a **POST_EXECUTION_READ_ONLY** presentation of the immutable final result.

## 2. Frozen protocol

Three datasets × five model families were evaluated using 300 pre-frozen fitted runs, validation-derived raw thresholds and policies, and one logical 15-cell final-test batch. No policy, threshold, selected run, preprocessing transform, or model was changed after opening.

## 3. Pre-final-test history

Phase 0 locked the executable protocol; Phase 0.5 locked the statistical analysis plan; Phase 1 froze validation evidence and policies; Phase 1.5 audited the H1 defect and retained H2; Phase 1.75 froze the executor and dry route. H1 remains `NOT_ASSESSABLE` because `PRE_SPECIFIED_COMPACTNESS_RULE_UNDERSPECIFIED`.

## 4. One-time final-test opening

Unlock SHA-256: `8ef117f72114470d45bb39ba69efc930b3400ea6911aa4451ee2dbdb904a3053`
Opening receipt SHA-256: `21edd26dbf282fdf6d6eef1b970162b8fafd24efb4dc3ea93a71c2337e23ec1c`

## 5. H2 frozen validation interpretation

The Phase 1.5 independent validation audit retained 4 `PATTERN_OBSERVED` and 11 `PATTERN_NOT_OBSERVED` cells. H2 is not redefined from final-test data.

## 6. Final policy outcomes and H3

| Dataset | Model | No-review risk | Confidence risk | Stability risk | Delta_R | 95% CI | H3 |
|---|---|---:|---:|---:|---:|---|---|
| ai4i_2020 | logistic_regression | 0.038500 | 0.011407 | 0.011407 | 0.000000 | [0.000000, 0.000000] | INCONCLUSIVE |
| ai4i_2020 | decision_tree | 0.026000 | 0.026000 | 0.018820 | -0.007180 | [-0.011163, -0.003715] | SUPPORTS_H3 |
| ai4i_2020 | random_forest | 0.023500 | 0.005382 | 0.005382 | 0.000000 | [0.000000, 0.000000] | INCONCLUSIVE |
| ai4i_2020 | gradient_boosting | 0.021000 | 0.007361 | 0.007361 | 0.000000 | [0.000000, 0.000000] | INCONCLUSIVE |
| ai4i_2020 | flat_neuro_fuzzy | 0.071000 | 0.023099 | 0.022561 | -0.000538 | [-0.001668, 0.000033] | INCONCLUSIVE |
| uci_bank_marketing | logistic_regression | 0.133528 | 0.052857 | 0.052840 | -0.000017 | [-0.000044, 0.000000] | INCONCLUSIVE |
| uci_bank_marketing | decision_tree | 0.168245 | 0.085053 | 0.134920 | 0.049867 | [0.044550, 0.055329] | CONTRADICTS_H3 |
| uci_bank_marketing | random_forest | 0.137533 | 0.054215 | 0.054106 | -0.000109 | [-0.000468, 0.000095] | INCONCLUSIVE |
| uci_bank_marketing | gradient_boosting | 0.130250 | 0.053356 | 0.053331 | -0.000025 | [-0.000057, 0.000000] | INCONCLUSIVE |
| uci_bank_marketing | flat_neuro_fuzzy | 0.596990 | 0.052299 | 0.052299 | 0.000000 | [0.000000, 0.000000] | INCONCLUSIVE |
| wisconsin_diagnostic | logistic_regression | 0.017544 | 0.009615 | 0.009615 | 0.000000 | [0.000000, 0.000000] | INCONCLUSIVE |
| wisconsin_diagnostic | decision_tree | 0.052632 | 0.052632 | 0.044643 | -0.007989 | [-0.025605, 0.001185] | INCONCLUSIVE |
| wisconsin_diagnostic | random_forest | 0.043860 | 0.000000 | 0.000000 | 0.000000 | [0.000000, 0.000000] | INCONCLUSIVE |
| wisconsin_diagnostic | gradient_boosting | 0.043860 | 0.018349 | 0.018349 | 0.000000 | [0.000000, 0.000000] | INCONCLUSIVE |
| wisconsin_diagnostic | flat_neuro_fuzzy | 0.061404 | 0.010870 | 0.010870 | 0.000000 | [0.000000, 0.000000] | INCONCLUSIVE |

Global H3 counts: `SUPPORTS_H3=1`, `CONTRADICTS_H3=1`, `INCONCLUSIVE=13`, `NOT_ASSESSABLE=0`.

## 7. AI4I FNR

AI4I FNR values and accepted-positive denominators are in immutable `T07_ai4i_fnr.csv` and F07. N/A values, if any, are not represented as zero.

## 8. Negative and inconclusive findings

The result is heterogeneous: AI4I Decision Tree supports H3; the other four primary AI4I families are inconclusive. Bank Marketing Decision Tree contradicts H3; all remaining secondary cells are inconclusive. Flat Neuro-Fuzzy remains included as frozen negative validation evidence; its Phase 1.5 audit found probability/class semantics and frozen threshold replay valid despite F1=0 at the standard 0.5 operating point on AI4I and Bank.

## 9. Independent recomputation

Status: `INDEPENDENT_RECOMPUTATION_PASS`. It recomputed policy dispositions, risks, FNR where applicable, all paired 10,000-replicate bootstrap quantities (seed 20260902), and H3 labels from persisted product final-test case evidence rather than result summaries.

## 10. Allowed claim

In this pre-specified confirmatory experiment, stability-aware selective review was not universally advantageous. On primary AI4I, a statistically supported reduction in accepted-case risk was observed for Decision Tree, while the other four frozen model families were inconclusive. For Bank Marketing Decision Tree the effect was in the opposite direction; the remaining secondary cells were predominantly inconclusive. Cross-run stability therefore behaved as a regime-dependent review signal, not a universal substitute for confidence-based abstention.

## 11. Forbidden claims

This study does not establish universal risk reduction, universal H3 confirmation, superiority of RuFLEX over confidence-only review, or domain validation for industrial, financial, or clinical deployment.
