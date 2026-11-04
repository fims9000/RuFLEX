# R6 — empirical and synthetic results

**Exploratory status.** A06/R5 outcomes were previously inspected. All signs below are paired comparison *observations*, not independent dataset-population hypothesis tests.

## Policy-switch decomposition (existing case-level R4/R5 evidence)

- **stream:** 40 correlated cells, 23 positive gains, 8 adverse gains, 9 exact ties; mean switch fraction 4.44%; 5 positive cells would lose their gain following one adversarial change in a switched-case error outcome. Median break-even conditional-risk shift among positive cells = 19.79 percentage points.
- **batch:** 40 correlated cells, 24 positive gains, 3 adverse gains, 13 exact ties; mean switch fraction 4.63%; 9 positive cells would lose their gain following one adversarial change in a switched-case error outcome. Median break-even conditional-risk shift among positive cells = 11.52 percentage points.

The retrospective conditional-shift epsilon is a sensitivity radius, not an estimated shift rate.

## Operating-cost dominance over all review prices

| Study | Mode | Cells | Augmented dominates | Baseline dominates | Identical | Cost-dependent |
|---|---|---:|---:|---:|---:|---:|
| A06 | batch | 32 | 18 | 3 | 11 | 0 |
| A06 | stream | 32 | 5 | 1 | 8 | 18 |
| R5 | batch | 8 | 6 | 0 | 2 | 0 |
| R5 | stream | 8 | 2 | 0 | 1 | 5 |

A claim of benefit at `lambda=.25` does not establish Pareto improvement when the methods use different numbers of human reviews.

## Known-risk simulation

| World | Source gain (pp) | Target gain (pp) | Cert. N | Activations / 200 |
|---|---:|---:|---:|---:|
| actionable | +5.00 | +5.00 | 100 | 17 |
| actionable | +5.00 | +5.00 | 400 | 199 |
| actionable | +5.00 | +5.00 | 1600 | 200 |
| neutral | +0.00 | +0.00 | 100 | 0 |
| neutral | +0.00 | +0.00 | 400 | 0 |
| neutral | +0.00 | +0.00 | 1600 | 0 |
| wrong_signal | -8.75 | -8.75 | 100 | 0 |
| wrong_signal | -8.75 | -8.75 | 400 | 0 |
| wrong_signal | -8.75 | -8.75 | 1600 | 0 |
| invisible_reversal | +5.00 | -12.50 | 100 | 16 |
| invisible_reversal | +5.00 | -12.50 | 400 | 200 |
| invisible_reversal | +5.00 | -12.50 | 1600 | 200 |

**Key mechanism:** In the invisible-reversal world, target gain is -12.5 pp despite +5.0 pp source gain. At N=400 source certification activates 200/200 times. The target observable distribution is exactly unchanged, so an unlabelled shift detector cannot resolve the sign. The exact sharp transport radius is `epsilon*rho=.70*.25=.175`.

## Newly held-out chronological studies

| Dataset | Frozen reference | N final | N labelled certification | Base cost | Augmented cost | Gain (pp) | Guard activated? |
|---|---|---:|---:|---:|---:|---:|---:|
| Sunspots | logistic_regression | 47 | 29 | 0.0957 | 0.0957 | +0.00 | No |
| Sunspots | decision_tree | 47 | 29 | 0.1277 | 0.1170 | +1.06 | No |
| Sunspots | random_forest | 47 | 29 | 0.0745 | 0.0798 | -0.53 | No |
| Sunspots | sgd_log_loss | 47 | 29 | 0.1649 | 0.1223 | +4.26 | No |
| U.S. macro | logistic_regression | 31 | 19 | 0.4839 | 0.4839 | +0.00 | No |
| U.S. macro | decision_tree | 31 | 19 | 0.2661 | 0.2742 | -0.81 | No |
| U.S. macro | random_forest | 31 | 19 | 0.2097 | 0.1855 | +2.42 | No |
| U.S. macro | sgd_log_loss | 31 | 19 | 0.4839 | 0.4839 | +0.00 | No |

There are **3 gains, 2 losses, and 3 ties** across these eight correlated model cells. The independent-certification rule chose baseline in **8/8**; this prevents an unsupported claim of a reliable deployment advantage. Nominal CP levels assume IID, which annual and quarterly time series do not establish. The heldout task sizes (47 and 31 per family) are too small for population-level inference.

## Reproducibility verification

- Case-level R4/A06 heldout masks and error counts were rederived and matched the immutable A06 policy output at tie seed 1.
- The new temporal experiments ran twice, reproducing five core CSV artifacts byte for byte across 136 model fits per run.
- The new temporal verifier reconstructed 8 certification decisions and all 312 final-case decisions from stored scores, masks, labels and fixed tie hashes; 192 labelled certification cases were checked.
- Mechanistic simulation has deterministic seed `20261104` and saved 4,000 episode-level rows and source/code SHA-256 receipts.
- The only source change after the first heldout run was adding detailed audit receipts and restructuring the in-memory stage access so heldout labels are not computed before certification; main numeric outputs did not change.

## Claims NOT supported

No new unconditional guarantee, no evidence of current real-world deployment safety, no theorem priority for known reject-option rules, no global statistically significant benefit of the augmented route, no proof that pseudorandom training seeds correspond to IID retrainings, and no conclusion about human reviewer accuracy or actual review cost.
