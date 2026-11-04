# R5 observed evidence: conditional decision value

**Status:** new temporal challenge completed and independently replayed; no externally preregistered confirmatory claim. R4 and R3 source papers and original A01 experiments are unchanged.

## Temporal challenge: 248 fits; 8 cells; 2,820 held-out case–model predictions

The locally frozen R5 protocol SHA-256 is `791ee6dd60c84cf09e02cd01571d14c9f646ae46c45f638bd92565aa98804291`. The first source run caught a missing tie-seed dictionary key *before any held-out policy outcome was computed*. The correction used exactly the seed already declared in the fixed protocol (55043), with an explicit `SOURCE_AMENDMENT_001.json`. No model, threshold, outcome, sample or hypothesis was changed.

### Primary late block: streamed, validation-frozen 20% review policy

All values are the per-case *joint cost*, i.e., automated errors plus 0.25 times the review count, divided by held-out count. The test review counts are realized, not forced to 20%.

| Fixed reference family | Confidence-only cost | Conditional cost | Difference (percentage points) | Review counts (base → conditional) |
|---|---:|---:|---:|---:|
| Logistic regression | 0.2372 | 0.2372 | 0.00 | 70 → 70 |
| Decision tree | 0.3239 | 0.3118 | −1.21 | 68 → 71 |
| Random forest | 0.3970 | 0.3629 | −3.41 | 63 → 71 |
| SGD log-loss | 0.4972 | 0.4886 | −0.85 | 4 → 8 |

There are **3 observed cost improvements, 1 exact tie, no deterioration** in the primary late block, but four model families share one data source and are not independent datasets. The supervised confidence-only SGD gate rejected only 4/352 held-out cases due to validation-to-test score drift, despite a 20% validation budget. This illustrates failure of frozen-threshold workload transfer and limits operational interpretation.

At **exactly matched batch review count** (71/352 each), the conditional risk score reduced retained erroneous predictions by 0/2/6/2 for logistic/tree/forest/SGD, respectively, versus the separately trained confidence-only ranker. These are descriptive comparisons of score ranking **not streaming implementation claims**. The simple raw-confidence baseline still beat the augmented score for Decision Tree in this late window: operational 0.3111 versus 0.3118 and exact-budget 0.3061 versus 0.3118. Consequently no claim of dominance over all baselines is supported.

The 26-week moving-block percentile intervals for conditional-minus-confidence **cost** were: Decision Tree [−0.02344, 0.00428]; Random Forest [−0.06676, −0.00852]; SGD [−0.01492, 0]; Logistic [0,0]. These are **descriptive**, unadjusted for four families, and temporal nonstationarity is not ruled out.

### Secondary early window

The outcome is **3 improvements and 1 deterioration** in stream mode. The detriment is Logistic Regression, conditional-minus-confidence +0.354 percentage points, with nonzero predicted risk-boundary crossings. A theoretical positive value-of-information guarantee for *true Bayes risks* therefore does **not** imply benefit from a fitted error-risk ranker. On the other families the cost decreases by 0.85, 0.14 and 1.70 percentage points respectively (Decision Tree, Forest, SGD).

### Failure cases and mechanism ablations

On the late Decision Tree block, 88 test cases were **wrong, had reference confidence ≥0.90 and zero observed retraining disagreement**. This concretely falsifies any notion that repeatability by itself can certify correctness. Other model families have fewer or zero such cases; do not generalize this proportion to all learners.

A post-hoc factor ablation tests confidence+D, confidence+probability-dispersion, and both. The late Forest joint costs were 0.3970 (confidence-only), 0.3608 (confidence+D), 0.3984 (confidence+std), 0.3629 (both), while late Decision Tree costs were 0.3239, 0.3175, 0.3118 and 0.3118. Thus the useful auxiliary signal is **family-dependent**: Forest benefits primarily from disagreement, but Decision Tree improves more with the probability-dispersion component. Additional features can hurt, so no monotonic benefit is asserted for estimated risk models.

## Historical A06 reanalysis (not independent confirmation)

Reused 32 R4 externally packaged dataset/model/split cells, with identical validation-only error-risk fitting and a 20% review budget, cost 0.25. The R4 labels had been inspected before the R5 hypothesis was proposed.

| Setting | Improved | Tied | Worsened | Descriptive mean conditional-minus-confidence cost |
|---|---:|---:|---:|---:|
| Validation-frozen streaming | 13 | 4 | 15 | −0.00551 |
| Exact-budget batch ranking | 12 | 9 | 11 | −0.00630 |

RAND HIE has a slightly **adverse** mean difference on these models in stream mode. The dataset-model-split cells are dependent, and these heterogeneous results provide no pooled independent-replication significance test.

## Verification and limits

- Original protocol hash and model source hashes archived; nonsemantic run-time bug documented transparently.
- Independent replay reconstructed **64 policies and 2,820 distinct case–model held-out predictions** from saved scores and frozen thresholds. Exact batch quotas and deterministic stream ties matched.
- A second full **248-fit** execution produced **byte-identical** `CASE_LEVEL_TEMPORAL.csv`, `POLICY_OUTCOMES.csv`, and `FROZEN_THRESHOLDS.csv` (SHA-256 compared).
- All 8 `test_core.py` unit tests passed. The full exploratory A06 and post-hoc ablation rows are included in the archive.
- Fixed integer random seeds support repeatable software execution, not a mathematical guarantee of independent random draws.
- CO₂ data are historical time series from *one* station, not four independent real-world applications; two temporal folds overlap.
- Error-cost lambda is a hypothetical accounting parameter, not measured human-review cost or clinical benefit.
- Scores selected/fitted on the validation period may be miscalibrated after time shift. Future experiments should separate risk fitting and calibration and include multiple independent domains.
