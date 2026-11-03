# Reviewer-response record for research revision R2

Original submission: ACDSA 2027 paper 1326, *When High Confidence Is Not Reproducible*. The original decision was rejection. This document records the technical changes made for a **new** revision; it is not an appeal, editorial correspondence or claim that ACDSA has accepted a revised paper.

## Reviewer 3

**Comment:** The manuscript did not adequately answer the question posed in the title; an a priori definition of reproducibility and conditions that ensure it would materially improve the research.

**Change:** Added a reference-conditional estimand

\[
  r(x) = \Pr_{S}\{h_S(x)=h_0(x)\mid D,\mathcal C,h_0\},
\]

where \(h_0\) is fixed before the audit and \(S\) varies only the stochastic training mechanism at fixed data and configuration. The new section explicitly distinguishes this quantity from individual-model probability/confidence, from the agreement of two fresh models, and from prediction correctness.

Two sufficient-condition constructions are now separated:

1. **Deterministic:** a strictly positive argmax score gap greater than twice a *uniformly justified* retraining drift bound guarantees unchanged argmax. For binary classification using threshold \(t\), a reference probability margin strictly greater than the corresponding maximum drift is sufficient. Observed drift over a finite sample does **not** justify a uniform bound over all possible retrainings.
2. **Finite-sample statistical:** after fixing the reference and its cases, \(k\) agreements among \(n\) fresh IID retrainings give an exact one-sided Clopper–Pearson lower limit. A Bonferroni adjustment across the fixed cases in each dataset/model cell gives nominal simultaneous confidence for the conditional class-replication probability. This does not guarantee the same label on every retraining, nor does it guarantee the label is correct.

**Limitation retained:** Exact confidence interpretation requires a well-specified independent-draw law for fresh retrainings; distinct deterministic pseudorandom integer seeds alone do not establish that law. The finite-sample result uses a standard interval and is not presented as a new theorem. A01's 19 auxiliary fits cannot be reused for this exact audit conditional on choosing the reference by validation F1.

## Reviewer 4

**Comment:** Three public datasets and limited model configurations restrict generalization despite sound experimental control.

**Change:** Retained A01's original three-dataset/five-family 300-fit matrix, then added a separate A02 exploratory matrix with seven data regimes (three public scikit-learn datasets plus four related synthetic stress conditions) and five model families. A02 uses one independently fixed reference and 100 audit retrainings per cell: 35 cells, 3,535 training fits and 6,125 validation case–model predictions. A second, post-hoc split-sensitivity run covers Decision Tree and SGD Logistic over the same seven regimes, with 1,414 further fits and 2,450 validation case–model predictions.

**Finding:** At the A02 90% replication target, nominal 95% within-cell simultaneous lower-bound certification applies to 4,739/6,125 validation case–model observations (main split only). High-confidence instability among first-split Decision Tree predictions was 104/1,225, and among first-split SGD Logistic predictions 138/990; both groups had higher observed error rates than stable high-confidence predictions. The corresponding instability counts on the second split were 115/1,225 and 73/956; the variation in the latter demonstrates that the effect size depends materially on the split.

**Remaining limitation:** The data regimes are not seven independent application domains; the synthetic cases are generated from one family, all analyses use fixed validation subsets, and the second split was planned after inspecting the first. The new observations do not establish performance under distribution shift, error-correction by reviewers, or statistical superiority of a proposed routing rule at matched final-test coverage.

## Boundaries on the revised paper

- Historical A01 results and frozen final-test outcome are unchanged. A01 remains heterogeneous and does not justify a universal review-policy improvement.
- A02 certificate evidence is exploratory validation evidence, not a second A01 confirmatory test.
- A01's validation-selected reference and A02's seed-fixed reference are different protocols; their certificates and empirical risk comparisons cannot be pooled without a new statistical plan.
- Neither reviewer proposed a straightforward mandatory typographical correction. The revision addresses scientific scope and experimental breadth, and publication at a different venue would still require a complete editorial review.