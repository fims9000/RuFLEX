# Response to ACDSA 2027 reviews — paper 1326

**Manuscript:** *When High Confidence Is Not Reproducible*  
**Revised working title:** *When High Confidence Is Not Reproducible: Conditional Certificates and Held-Out Selective Review*

The original ACDSA 2027 submission was **rejected**. This document describes a substantially expanded research manuscript for a future submission or for requesting permission to resubmit; it does not imply an invitation to submit a revision, any changed conference decision, or an accepted appeal.

## Reviewer #3

> The authors failed to answer the question posed in the article's title. An a priori definition of reproducibility and the identification of conditions ensuring it would represent an interesting extension.

**Response:** We agree that the original experiment established the *existence* of high-confidence model churn without formally specifying when a future training run should reproduce a given decision. The revised paper now fixes the training data, model configuration, decision threshold, a test case, and an operational reference **before** collecting audit predictions, and defines

`r(x) = P_S[h_S(x) = h_ref(x) | fixed data, configuration, reference]`.

This is deliberately **not** (i) confidence of the reference model, (ii) correctness of its label, (iii) pairwise agreement between two random fresh models, or (iv) stability under dataset shift. The operational predictor never votes with its audits.

We establish two *sufficient* conditions and explain their premises:

1. **Deterministic score bound.** If every retraining changes each class score by at most `epsilon(x)`, a strict reference top-two score gap larger than `2*epsilon(x)` preserves the predicted class. A binary decision at threshold `t` is stable if `|p_ref(x)-t| > epsilon(x)` under a corresponding probability drift bound. Observed worst-case drift among sampled models is *not* sufficient evidence of a bound over all possible retrainings.
2. **Conditional probabilistic bound.** If the random pairwise score-drift difference against each competing class is sub-Gaussian with *known* mean/scale, a union-bound concentration inequality gives a sufficient margin for replication probability at least `1-delta`. This is not presented as a new inequality; its parameters are not empirically validated in these benchmarks, and it does not automatically apply to trees.

When these strong score-drift assumptions are not available, a **separate conditional statistical route** is supplied: a one-sided exact Clopper–Pearson lower confidence bound for the probability of repeating the already fixed class over fresh training draws, with Bonferroni correction for the set of cases within each cell. Certificates require **independent** fresh draws and a reference selected without using those draws. In A05, 4,601 of 5,400 held-out case–model decisions satisfied the nominal 90%/95% within-cell criterion; 184 of those certified decisions were wrong. This demonstrates why a repeatability certificate does not imply reliable *classification*.

**Where to find this:** revised Sec. III-C through III-E (definition, sufficient conditions, finite-sample certification); Sec. VI-E (A05); Sec. VIII (sampling assumptions and scope). The implementation, exact case-level evidence and independent recomputation are included in this release.

## Reviewer #4

> The experimental protocol is transparent and technically sound. The main limitation is evaluation on only three public datasets and a limited set of model configurations; generalizability remains uncertain.

**Response:** We preserved the original A01 three-dataset, five-family, 300-fit result and its negative findings unchanged. We then performed separate, clearly labeled experiments:

- **A02 exploratory validation:** seven data regimes, five model families, 3,535 fits; 1,414 additional fits on a second stratified split for two families. The seven regimes include only **three public** datasets and four correlated synthetic regimes; we do not describe them as seven independent application domains.
- **A03 held-out comparison:** four bundled public datasets and four synthetic regimes, five model families, two stratified splits, 80 dataset–model–split cells, 2,480 fits and 13,400 held-out case–model decisions. Review capacity is identical across methods in each cell. The combined score improves risk in 28 cells, ties in 47 and worsens it in five at nominal 90% coverage. Logistic Regression, which is effectively deterministic on fixed data, has no benefit. Results remain heterogeneous: among the 40 public-data cells there were 10 improvements, 2 deteriorations and 28 ties (mean difference -0.34 percentage points); among the 40 synthetic cells there were 18, 3 and 19 respectively (mean -0.75 points). The stronger synthetic effect should not be mistaken for external generalization.
- **A04 cost/fit-budget ablation:** 32 Decision Tree/SGD cells, 5/10/20/30 fits and 992 fit calls; *post hoc* on A03's already examined cases, not an independent confirmatory test.
- **A05 held-out reproducibility audit:** 40 public-data cells, 4,040 fits and 5,400 held-out case–model decisions, testing the new formal replication target with independent recomputation.

Strong baselines now include confidence-only, disagreement-only, and probability-dispersion ranking using the **same frozen reference** at an **exactly equal integer review budget**. A03 additionally reports 80%, 90% and 95% target acceptance budgets and 16 deterministic, label-blind numerical tie resolutions. This resolves the original A01 problem whereby validation-frozen confidence cutoffs generated unequal final-test coverage; we neither erase nor reinterpret those old results.

The revised work reports negative and boundary cases explicitly. For example, on one Wisconsin/Decision Tree split, a repeatably wrong high-confidence case is automatically accepted by the combined rule but reviewed under the confidence-only tie-breaking order. Other tested cells also show cases where reproducibility-aware review performs worse. We report per-cell uncertainty without treating 80 correlated cells as 80 independent experiments, and do not assert multiplicity-corrected significance.

**Where to find this:** Sec. VI-A through VI-D, Figs. 3–5, Sec. VIII, and the CSVs `A03_TOP_SUCCESS_AND_FAILURE_CELLS.csv`, `A03_POLICY_SWITCH_FAILURE_CASES.csv`, `A03_TIE_VARIABILITY.csv`. The full model-training and independent-verification scripts are included.

## Remaining boundaries (not claimed resolved)

No external preregistration was conducted; A03 was locally frozen but still chosen after earlier analyses. The four A03 synthetic regimes share one generator, and two splits of the same public data are correlated. There is no true out-of-domain or temporal-drift evaluation, independent clinical/industrial application, human reviewer study or operational stream-budget control. Formal statistical certificates require an independent training-randomness law, which a deterministic PRNG trace alone cannot prove. The theorem gives **conditional sufficient conditions**, not an empirically verified, unconditional prediction-stability guarantee.

We regard the revised manuscript as a stronger, fully auditable research contribution, **not** a guarantee of acceptance by ACDSA 2027 or any other venue.
