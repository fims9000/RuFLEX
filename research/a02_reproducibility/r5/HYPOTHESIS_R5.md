# R5 — When is retraining disagreement worth paying for?

**Scientific hypothesis and protocol report.** New hypothesis formulated after inspecting A01–A06, so none of those data can be treated as a confirmatory test. The R5 CO₂ temporal challenge was specified in `PROTOCOL_R5.json` before the first new training fit. Its local SHA-256 was `791ee6dd60c84cf09e02cd01571d14c9f646ae46c45f638bd92565aa98804291`. This is a local freeze, **not external preregistration**.

## 1. From disagreement detection to conditional decision value

One fixed reference classifier produces the operational prediction. Independently retrained auxiliary fits do not vote, recalibrate that prediction, or change its class. Their disagreement and probability dispersion are additional *audit covariates*.

Let `E=1{h_ref(X) != Y}` be the error event, `C=max(p_ref,1-p_ref)` the reference confidence, `Yhat` the reference predicted class, and `D=1-M^{-1} sum_m 1{h_m(X)=h_ref(X)}` a case-wise audit disagreement fraction. Use `S=sd_m p_m(X)` as another audit statistic. Define the observable information sets:

- `F0 = sigma(C, Yhat)`, containing confidence and reference class;
- `F1 = sigma(C, Yhat, D, S)`, containing additional retraining information.

The conditional error risks are `r0(X)=P(E=1 | F0)` and `r1(X)=P(E=1 | F1)`.

**H-R5 (conditional decision-value hypothesis).** Retraining reproducibility improves selective review **when its incremental information distinguishes case-level error risks within confidence-and-class strata sufficiently to change the cost-effective review decisions at the relevant operating budget**. If the signal changes no actionable review ranking or risk threshold, observed disagreement alone cannot justify additional review.

This is stronger and falsifiable compared with “disagreement is sometimes associated with errors.” It also permits *reliably wrong* predictions (high confidence, high across-run agreement, wrong label).

## 2. Decision-theoretic conditions (existing mathematical principles, not a new theorem)

Let `g(X) in [0,1]` be the conditional review probability. The accounting proxy assumes one reviewed case has cost `lambda` relative to one unresolved automated error, without claiming human reviewers are infallible or measuring their accuracy. The per-case objective is:

`L_lambda(g) = E[E * (1-g) + lambda*g]`.

With no hard review-capacity constraint, the Bayes action given feature set `F` is `g*(F)=1{P(E=1|F) > lambda}` (ties arbitrary). Because `F0 ⊂ F1`, the reduction in optimal loss is:

`V_lambda = E[(r1-lambda)_+] - E[(r0-lambda)_+] >= 0`.

The inequality follows from conditional Jensen: `r0=E[r1|F0]` and `(z-lambda)_+` is convex. There is strict improvement when additional information moves conditional error risk across the review-cost boundary on a set with positive probability; changes entirely on the same side of that boundary need not have positive decision value. Positive conditional mutual information is therefore **insufficient** to guarantee benefit at a specified `lambda`.

For a *population review-capacity bound* `E[g] <= q`, define `W(F;q,lambda)=sup_{g F-measurable, 0<=g<=1, E[g]<=q} E[g*(r_F-lambda)]`. Its Lagrangian dual is:

`W(F;q,lambda) = inf_{nu>=0} {nu*q + E[(r_F-lambda-nu)_+]}`.

More information cannot lower the **optimal** value since every `F0`-measurable review rule is also feasible under `F1`. Under a binding budget, improvement depends on changes to the top-error-risk set around the **effective threshold** `lambda+nu`, not merely crossings of `lambda`. This is standard value-of-information / randomized Bayes selection reasoning (see Franc et al., JMLR 2023). A fitted logistic error-risk model is neither a Bayes oracle nor guaranteed to preserve this inequality.

**Two sanity examples.** With constant confidence and a balanced disagreement indicator, conditional error probabilities `(0.1,0.7)` and review cost `0.4` yield additional unconstrained ideal value `0.15`. By contrast, error probabilities `(0.1,0.3)` with review cost `0.4` have nonzero conditional dependence but zero incremental decision value, since both groups should be left automatic.

## 3. Falsifiable empirical hypotheses

- **H5a — conditional error ranking:** a validation-fitted error-risk model based on `(C,Yhat,D,S,C×D)` improves out-of-period proper error-scoring loss versus a separately fitted confidence-only `(C,Yhat)` model. A negative Brier difference means improvement; every family must be shown.
- **H5b — operational utility (R5 primary):** with validation-frozen review thresholds targeting 20% review on the validation period and hypothetical cost `lambda=0.25`, the conditional model reduces held-out `L_lambda` relative to supervised confidence-only risk. Its **realized test coverage is allowed to drift**, so we report review burden and errors together.
- **H5c — matched-budget ranking (secondary):** at a label-blind *exact* 20% test-batch review budget, the conditional model captures more reference-model errors than confidence-only, without claiming that batch top-k works for individual incoming cases.
- **H5d — failure boundary:** some confident and perfectly stable predictions will be wrong. Therefore neither an agreement threshold nor a replication probability certificate is a correctness guarantee.

The **nulls** are no incremental Brier-score performance for H5a and nonnegative excess expected review-cost for H5b. The current small, historically correlated test is not sufficient to reject dataset-population nulls with valid multiplicity-controlled inference.

## 4. Independent temporal challenge, fixed before fitting

Data: weekly Mauna Loa CO₂ measurements, `statsmodels.datasets.co2`. Target: whether the *next observed week* is strictly higher than the current observed week. Features use only current and past levels, lags 1/2/4/8, differences, past moving means, and known seasonality. The original target observations are not interpolated. Historical gaps are forward-filled for **feature lags only**. Two calendar-based folds use embargo gaps of at least eight weeks. The late fold (train through 1986; validation 1987–1994; test Apr 1995–2001) is primary; the earlier overlapping fold is secondary.

Four families (Logistic Regression, Decision Tree, Random Forest and SGD Logistic) use a fixed reference seed `54000` plus 30 auxiliary seeds `55000…55029`: **8 cells × 31 = 248 new fits**. Class predictions and class probabilities come only from the reference model. The confidence-only error model and augmented error model are both L2 logistic regressions trained exclusively on validation error labels. `StandardScaler` for the base model uses training data only; risk-model scalers use validation features only. Decision and review calibration never use held-out labels.

The review cost and 20% calibration budget were fixed before new execution. A descriptive moving-block bootstrap (26-week blocks, 2,000 samples) addresses short-range time dependence but **does not imply valid population inference under unknown long-range nonstationarity**.

## 5. Evidence, limits and next confirmatory experiment

See `RESULTS_R5.md` and `results/R5_PRIMARY_CONTRASTS.csv` for every outcome, including negative results, and `results/R5_POSTHOC_ABLATIONS.csv` for separable disagreement-vs-probability-dispersion checks. A06 is also reanalysed, but its labels were inspected before R5, so that comparison is **hypothesis-generating only**. Any ablation chosen after the temporal result is also **post-hoc**.

The next genuine confirmatory protocol must collect unseen target time windows or independent real-world institutions, fix the primary model family and operating utility **before** acquisition, separate risk fitting from threshold calibration, and treat datasets/institutions (not repeat training seeds or overlapping resplits) as independent units for overall generalization inference. In particular, model-based disagreement may lose value under deterministic algorithms and shared systematic biases; the gate must be allowed to abstain from claiming an advantage.

## 6. Novelty boundary and related work

The value-of-information/Jensen argument, the optimal threshold on conditional risk, Clopper–Pearson bounds, the score-margin invariance inequality, and selective ensembling are **not proposed as novel mathematics**. The research contribution to investigate is a *fixed-reference, conditionally supervised, cost-aware reproducibility audit* with explicit comparison against a supervised confidence-only model, a frozen streaming rule and an independent chronological falsification challenge. This must still be compared thoroughly with existing selective risk learning and uncertainty approaches before any priority claim.

Sources: Franc, Prusa and Voracek (2023), [Optimal Strategies for Reject Option Classifiers](https://www.jmlr.org/papers/v24/21-0048.html); Black, Leino and Fredrikson, [Selective Ensembles for Consistent Predictions](https://arxiv.org/abs/2111.08230); Hidey, Liu and Goel (2022), [Reducing Model Churn](https://aclanthology.org/2022.sigdial-1.2/); Paplhám et al. (2026), [Evaluating Epistemic Uncertainty: Beyond OOD Detection and Active Learning](https://arxiv.org/abs/2607.14817); `statsmodels` public dataset source, [CO₂](https://www.statsmodels.org/stable/datasets/generated/co2.html).
