# R6 — The limits of reproducibility-aware review under hidden conditional-risk shift

**Research status:** R6 is a theory-guided exploratory extension to RuFLEX A01–R5. A06 and R5 labels were already inspected. The *new* sunspots and U.S. macroeconomic temporal tasks were specified in `PROTOCOL_R6.json` before the R6 model fits; this was a **local** freeze, not external preregistration. The numerical simulation is a mechanistic construction with known risks, not evidence from retrained classifiers.

## Research hypothesis

A retraining-disagreement signal should be used for error-sensitive routing **only if it changes the policy on cases with enough incremental conditional error risk to offset the review cost, and there is evidence that this advantage transfers to the deployment environment**. Agreement is not a correctness certificate. Even a statistically convincing *source* improvement need not survive unobserved shifts in the conditional label distribution.

This yields four falsifiable questions:

- **H6.1 / localization:** do paired policy improvements come exclusively from `S+` (newly reviewed by the augmented policy) and `S-` (reviewed by baseline but released by augmented)? They must by the accounting identity below.
- **H6.2 / nonidentification:** can two populations with exactly the same joint distribution of observable confidence, decisions, and disagreement exhibit opposite relative routing utility? Yes, under arbitrary conditional label shift; the construction is explicit and independently executable.
- **H6.3 / transfer radius:** under a specified uniform bound epsilon on conditional error-risk shift, how much extra advantage is needed before even the sign of the gain is robust?
- **H6.4 / finite-sample operational check:** can a four-way split using a separate, independent labeled certification set distinguish actionable evidence from noisy overfitting, and how does statistical power limit deployment?

## Mathematical objects and assumptions

A *fixed reference model* produces one prediction. Auxiliary retrainings only produce audit features. Let `e=1{reference prediction != ground truth}`. Let `b(z),a(z) in {0,1}` denote frozen baseline and augmented **review** rules based on a fully observable routing feature vector `z`, including any fixed hash-based tie variable. A reviewed case is assumed to incur a hypothetical cost `lambda in [0,1]`; no accuracy, workload, or real cost of a human reviewer has been measured. Joint per-case cost: `ell(g)=e(1-g)+lambda*g`.

### Proposition 1 — policy-switch identity (exact)

`G = L(b)-L(a) = E[(a-b)(e-lambda)]`.

Write `S+={a=1,b=0}`, `S-={a=0,b=1}` and `q±=P(S±)`, `r±=P(e=1|S±)` (undefined if a set is empty). Then

`G = q+*(r+ - lambda) - q-*(r- - lambda)`.

Proof: Expand `ell(b)-ell(a)` and partition into `S+`, `S-`, and the nonswitch set where `a-b=0`. Consequence: there is **no incremental cost difference on any of the other cases**, irrespective of how unstable those cases are. When review budgets are exactly matched, `q+=q-` and the review-cost term cancels. This identity is basic, not claimed as novel mathematics.

### Proposition 2 — observable nonidentification (impossibility without additional assumptions)

Fix a distribution `P(Z)` and two different routing rules. With no restrictions on `P(e=1|Z)`, any two conditional-error laws can be coupled to the same `P(Z)`. Consequently, observing more unlabelled `Z`, even infinitely many observations, cannot determine the sign of `G`.

Explicit counterexample: four equally common observable groups `(C,D) in {H,L}×{0,1}`. Baseline reviews both low-confidence groups; augmented reviews only the low-confidence/high-disagreement group, which means `S-={(L,0)}` with probability `1/4`. Source group-error risks are `[[.05,.05],[.05,.75]]`, where the second row is low confidence. Target risks are `[[.05,.05],[.75,.05]]`; **all observable feature probabilities are unchanged**. At review cost `.25`, the same fixed augmented rule has source gain `+0.05` and target gain `-0.125`. The input-distribution shift is **zero**; the conditional-label mechanism changes. The reference prediction may remain 0, with the conditional binary truth adjusted to realize these error risks.

The construction shows that any deployment claim based solely on unlabelled disagreement can be invalidated under arbitrary concept shift. This is a special-case illustration of a broader decision-theoretic nonidentification principle, not a claim that the principle was discovered here.

### Proposition 3 — sharp conditional-risk transport bound

Suppose the source and target share a common observable routing support and satisfy `|r_Q(z)-r_P(z)| <= epsilon` for all target-supported `z`, where `r_P(z)=P_P(e=1|Z=z)`, and the *frozen* review rules remain the same. Let

`G_{P -> Q} = E_{Z~Q}[(a(Z)-b(Z))*(r_P(Z)-lambda)]`,

`rho_Q = P_Q(a != b)`.

Then `|G_Q - G_{P->Q}| <= epsilon*rho_Q`.

Proof: subtract the expectations, use the triangle inequality, and note that `|a-b|=1` exactly on the policy-switch set. If an estimated source risk `rhat_P` has a validated pointwise error bound `eta`, the radius becomes `(epsilon+eta)*rho_Q`. **Only if the transported estimated gain exceeds this radius** is a positive target gain established under those assumptions. Neither epsilon nor eta can be inferred from unlabelled target features alone. For the explicit reversal above: `epsilon=.70`, `rho_Q=.25`, `epsilon*rho_Q=.175`, and the actual change `+.05 - (-.125)=.175` — hence the bound is **attained with equality** (sharp).

For a *retrospective* evaluation, define the break-even radius `epsilon* = G/rho` for positive gains and positive `rho`; it is a **what-if sensitivity**, not a measured upper bound on real-world drift.

### Proposition 4 — independent switch-set finite-sample check

When `(e_i,Z_i)` are IID from the same population to which the frozen policies will apply, and the policy parameters, thresholds, and any model selection were fixed **before** seeing the independent certification cases, estimate `q+`, `q-`, `r+`, `r-` using separate counts. Compute two-sided exact Clopper–Pearson binomial intervals for all four probabilities at confidence level `1-alpha/4`, and use a union bound. Over the Cartesian product of the four simultaneous intervals, find the lower possible value of `q+(r+-lambda) - q-(r--lambda)`. This produces a lower bound with coverage at least `1-alpha` for `G`. Empty switch sets use `r in [0,1]`, never `r=0` by convention. **Activate augmented review only when this lower bound is positive; otherwise fall back to baseline.**

This is a derived use of classical exact binomial intervals, not a novel universal concentration inequality. Its formal confidence interpretation fails without IID/exchangeability or another valid dependence-aware sampling model. It also provides only *relative improvement over baseline*; it does not guarantee baseline safety, correctness of deferred human decisions, or protection against shift.

## Prior research and novelty boundary

Bayes-optimal reject-option rules and confidence-based error-risk learning are established results (Franc, Prusa and Voracek, JMLR 2023). Selective ensembles (Black et al., 2022) and generalized selective classification under shift (Liang et al., TMLR 2024) already study closely related uncertainty and deferral mechanisms. Robust policy value under concept drift has been studied (Wang et al., ICML 2025). The contribution **to be critically evaluated** is the combination of a fixed reference prediction, auditable policy-switch locality, a sharp sensitivity radius, independently split finite-sample evidence, and explicit *failure* under invisible conditional-label shift. It should not be presented as the first robust selective-classification method or as mathematically unprecedented.

## Predeclared and retrospective evidence

- **Prior A06/R5 case-level analysis:** 40 dataset-model/fold cells and two routing modes. In streaming evaluation, mean policy-switch mass is 4.44%; in batch evaluation, 4.63%. These are **dependent**, previously inspected experiments.
- **Controlled mechanism check:** five synthetic regimes, four independently labeled certification sample sizes (100, 400, 1600, 6400), 200 replications per setting, totaling 4,000 simulation episodes. No model is trained in these mechanistic worlds; true error laws and routing policies are known.
- **New real-data challenge:** statsmodels packaged annual sunspots and U.S. quarterly macroeconomic records, four frozen classifier families, one reference plus 16 audit fits per cell, **136 new training fits**. Five disjoint chronological partitions keep base-model fitting, supervised error-risk fitting, threshold fitting (unlabelled), policy certification (labelled), and final evaluation separate. Small samples and temporal dependence preclude interpreting IID certification bounds as deployment guarantees.

## Core conclusions and decision rule

1. Disagreement is not an intrinsically safe error signal: the **location of policy switches** and their conditional risks determine joint benefit.
2. A source-data certificate cannot rule out **invisible conditional-label shift**: more source labels can make a harmful target choice more confidently selected.
3. A shift-radius claim is meaningful **only when the allowed conditional-risk shift is justified externally**; observational confidence and agreement alone cannot supply it.
4. Independent certification is often conservative: no R6 temporal model was authorized (0/8) despite some *observed* post-hoc gains, which is scientifically preferable to presenting weak evidence as a guarantee.
5. The scientifically relevant next step is not to maximize reported wins, but to design a genuinely independent multi-station or multi-institution prospective holdout and learn a defensible bound on conditional-risk drift using *labelled* refresh data, while reporting abstentions and human-review outcomes.

## References

1. Franc, V., Prusa, D., Voracek, V. (2023), "Optimal Strategies for Reject Option Classifiers," JMLR 24, 1–49. https://www.jmlr.org/papers/v24/21-0048.html
2. Black, E., Leino, K., Fredrikson, M. (2022), "Selective Ensembles for Consistent Predictions." https://arxiv.org/abs/2111.08230
3. Liang, H., Peng, L., Sun, J. (2024), "Selective Classification Under Distribution Shifts," TMLR. https://arxiv.org/abs/2405.05160
4. Wang, J., Ren, Z., Zhan, R., Zhou, Z. (2025), "Distributionally Robust Policy Learning under Concept Drifts," ICML. https://proceedings.mlr.press/v267/wang25cm.html
5. Statsmodels (data), annual sunspots 1700–2008 and U.S. macroeconomic 1959Q1–2009Q3. https://www.statsmodels.org/stable/datasets/index.html
