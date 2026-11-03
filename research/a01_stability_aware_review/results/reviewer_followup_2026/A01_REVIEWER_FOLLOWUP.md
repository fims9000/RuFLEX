# A01 reviewer follow-up — post-hoc exploratory analyses

## Status and scientific boundary

This package is **post hoc / exploratory**. It reads frozen A01 evidence only. It does not retrain a model, refit a threshold or policy, alter `A01_FINAL_RESULTS.json`, or reopen the final test.

- Validation evidence bundle SHA-256: `435ed839fd7e5e97daaa227adf2f652777908e99e5a19f93fb171ad947c980d8`
- Final evidence bundle SHA-256: `3f12fb95f6027d3eb6e978d3cd3d64c832a49725d772caacc209807a30715f1d`
- Validation cells inspected: 15

## 1. HCIR threshold sensitivity on validation data

The original A01 point is confidence >= 0.90 and selected-run agreement < 0.80. The grid below changes only the descriptive thresholds on the already frozen validation case evidence.

| confidence | agreement | cells with non-zero HCIR | maximum HCIR |
|---:|---:|---:|---:|
| 0.85 | 0.70 | 6/15 | 4.922% |
| 0.85 | 0.80 | 6/15 | 6.192% |
| 0.85 | 0.90 | 6/15 | 7.413% |
| 0.90 | 0.70 | 4/15 | 4.922% |
| 0.90 | 0.80 | 4/15 | 6.192% |
| 0.90 | 0.90 | 4/15 | 7.413% |
| 0.95 | 0.70 | 4/15 | 4.922% |
| 0.95 | 0.80 | 4/15 | 6.192% |
| 0.95 | 0.90 | 4/15 | 7.413% |

At the original 0.90/0.80 point, the non-zero cells are:

- `uci_bank_marketing / decision_tree`: 507/8188 = 6.192%.
- `ai4i_2020 / decision_tree`: 18/2000 = 0.900%.
- `wisconsin_diagnostic / decision_tree`: 1/114 = 0.877%.
- `uci_bank_marketing / random_forest`: 6/5796 = 0.104%.

## 2. HCIR independence reference on validation data

For each cell, the selected-run class and confidence are kept fixed. Each of the other 19 runs is replaced by an independent label source with the same validation positive-class frequency as that run. This preserves run-level class marginals but removes case-specific agreement. The resulting value is a descriptive independence reference, not a confirmatory null test.

| dataset / model | observed HCIR | independence reference | observed - reference |
|---|---:|---:|---:|
| uci_bank_marketing / decision_tree | 6.192% | 20.136% | -13.944% |
| ai4i_2020 / decision_tree | 0.900% | 3.319% | -2.419% |
| wisconsin_diagnostic / decision_tree | 0.877% | 96.899% | -96.022% |
| uci_bank_marketing / random_forest | 0.104% | 8.057% | -7.953% |

## 3. Probability-dispersion threshold sensitivity on validation data

The Stability Gate is recomputed descriptively from frozen case evidence with confidence >= 0.90 and agreement >= 0.80 while changing only the maximum probability standard deviation (0.10, 0.15, 0.20). No policy is refit or persisted.

Largest coverage ranges across the tested standard-deviation thresholds:

- `uci_bank_marketing / decision_tree`: 90.641% to 90.738% (range 0.097%).
- `ai4i_2020 / gradient_boosting`: 95.000% to 95.050% (range 0.050%).
- `uci_bank_marketing / random_forest`: 70.260% to 70.284% (range 0.024%).
- `ai4i_2020 / decision_tree`: 98.850% to 98.850% (range 0.000%).
- `ai4i_2020 / flat_neuro_fuzzy`: 89.350% to 89.350% (range 0.000%).

## 4. Bank Marketing Decision Tree FNR — post-hoc descriptive final-test readout

- No review: 609/935 = 65.134%.
- Confidence-only: 606/606 = 100.000%.
- Stability-aware: 539/778 = 69.280%.
- Delta FNR (stability - confidence): -0.307198; paired bootstrap 95% CI [-0.340645, -0.274638].
- Final-test coverage: confidence-only 86.489%; stability-aware 91.321%.

This endpoint was not pre-specified for Bank Marketing. Because final-test coverage differs between the two policies, the FNR difference is descriptive and does not identify a causal effect of the stability signal at equal coverage.

## Article-use boundary

These analyses may be reported as reviewer-requested post-hoc/exploratory checks. They must not be described as part of the frozen confirmatory protocol or used to retroactively redefine the primary A01 hypotheses.
