# R7 — What counts as independent evidence?

## Central hypothesis (new proposal)

The reliability of a learned reproducibility-aware review policy depends not only on its per-case error enrichment but also on the **unit at which the incremental value is statistically identified**. Correlated records can create an arbitrarily strong yet invalid sequential evidence signal even under a zero-mean group-level null.

The research question is whether a label-fed sequential audit of *paired policy-switch gains*, aggregated into defensible time units, can avoid the pseudo-replication failure of rowwise auditing and provide an operationally informative decision to promote a new policy.

**H7a, falsifiable in a known-risk null world:** treating perfectly correlated country observations within a year as independent sequential trials produces a false-activation frequency above nominal alpha 0.05. Aggregating to the independent year unit restores the conditions under which the betting supermartingale is valid.

**H7b, real-world exploratory:** annual-unit evidence on an untouched World Bank country panel can reach a prespecified 1/alpha threshold and safely justify a promotion. This hypothesis must be reported **as structurally untestable in our frozen six-year protocol**: even X_t=+1 for all six years yields maximum e-value 5.3224, below the threshold 20. Zero promotions are inevitable and contain no empirical evidence against the candidate policy.

**H7c, operational utility (descriptive):** a supervised confidence+reproducibility risk model changes the review objective relative to a separately fitted supervised confidence-only ranker in previously unseen calendar years. The cost proxy is unresolved reference-model errors plus lambda=0.25 times reviewed cases. Future cost is counterfactual; the frozen gate is used for actual deployment-choice accounting. No dominance over raw confidence or simple disagreement is presupposed.

## Formal estimands

For a fixed predictor and two frozen review masks b(z), a(z) in {0,1}, define the reference-model error e in {0,1}. The **paired incremental gain** is

    X = (a-b)(e-lambda), lambda in [0,1], -1 <= X <= 1.

The empirical identity E[X] = L(b)-L(a) holds for matched observations. It does not supply a confidence statement.

For sequential *group-level* X_t, take a finite prior mixture over fixed stakes eta in (0,1):

    K_t = (1/K) sum_eta prod_{s<=t} (1+eta X_s).

If the masks were fixed before the monitored feedback, if X_t is revealed after its decision, and under the null E[X_t | history_{t-1}] <= 0 for every monitored t, then K_t is a nonnegative supermartingale with K_0=1. Thus P(max_t K_t >=1/alpha) <= alpha (Ville's inequality). This result is *known sequential-testing theory*, not a claimed new theorem. It does **not** imply that the sign of gain on a later unseen block is preserved.

When all countries in a year share one fair shock S_t in {-0.5,+0.5}, each year has conditional mean zero, but after seeing its first country the other country-level gains have positive conditional expectation whenever S_t=+0.5. Consequently rowwise betting has no valid conditional-mean null. With 200 perfectly correlated country rows in a year, the *first positive year alone* forces the largest-stake component above the 20 threshold (even after mixture averaging), so the false-activation probability is at least 1/2.

## Protocol integrity and negative results

The fixed new-panel protocol SHA-256 was recorded in GitHub before training: `fb047cc115129cf66b00d9ddd9206463d88cd9580beaea8ba1c7fd47932edbac`. The `SOURCE_AMENDMENT_001.json` documents a year-column string-indexing bug fixed before any fit. A later power-feasibility audit and the simpler raw-confidence/disagreement baselines are **post-hoc diagnostics**, never described as preregistered R7 analyses.

The data are historical World Bank **estimated** fertility rates, not contemporaneous independently sampled clinical measurements. Countries/territories may be correlated within and across years; country ISO3 membership does not establish independence. The group-level e-process would have an anytime-valid type-I bound **only if its conditional-mean null and predictability hold**. Neither is verified by the mere choice of a year as the group unit.

## Novelty boundary

Known ingredients: selective classification, value of information, paired policy comparison, betting supermartingales/e-processes, Ville's inequality and cluster-aware analysis. Potential contribution: a fully auditable falsification showing how a seemingly strong fixed-reference retraining signal loses inferential legitimacy under pseudo-replication, plus a mandatory **pre-execution e-value reachability check** and prospective policy-switch evaluation. No claim of novelty for the elementary betting proof itself.

## Key references

- Waudby-Smith and Ramdas (2023), *Estimating means of bounded random variables by betting*, JRSSB, https://doi.org/10.1093/jrsssb/qkad009.
- Timans et al. (2025), *On Continuous Monitoring of Risk Violations under Unknown Shift*, UAI / PMLR, https://proceedings.mlr.press/v286/timans25a.html.
- Franc, Prusa and Voracek (2023), *Optimal Strategies for Reject Option Classifiers*, JMLR, https://www.jmlr.org/papers/v24/21-0048.html.
- World Bank World Development Indicators fertility data, bundled in statsmodels, https://www.statsmodels.org/stable/datasets/generated/fertility.html.
