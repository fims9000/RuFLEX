# R7 results: inferential unit, newly held-out country panel and feasibility audit

**Status:** new World Bank panel trained after local freeze, 64 new model fits, 13 unit tests passed. Independent case-level verifier passed for 16,884 case×model records outside training. No external preregistration and no claim of independent institutions or universal model superiority.

## 1. Synthetic zero-mean experiment

- Twelve independent year shocks, each equal to +0.5 or -0.5 with equal probability, and **200 identical country gains per year**. Thus the true expected annual gain is zero, and rowwise observations are maximally dependent within year.
- 1,000 predeclared Monte Carlo repetitions, alpha=0.05, five equally weighted stakes (0.03, 0.07, 0.15, 0.30, 0.60).
- **Naive rowwise false activations: 769/1,000 = 76.9%; Wilson 95% descriptive interval [74.19%, 79.41%].** Such a method violates its claimed conditional-mean null.
- **Year-grouped false activations: 0/1,000.** For these particular +/-0.5 shocks and only 12 years the mixture cannot reach 20 even with all 12 shocks positive (maximum 6.7474): zero detections are structural, *not* evidence of adequate test power. Yearwise conditional supermartingale validity holds in this synthetic construction because years were explicitly generated independently.
- Analytic lower bound: with probability 1/2 the first year is positive, and a fixed stake eta=0.60 yields mixture wealth >= (1.3)^200/5 > 20 in the naive rowwise analysis. Hence the rowwise false activation probability is at least 50% in this null world.

## 2. New historical multi-entity panel

- Bundled World Bank fertility data 1960–2013; 7,992 complete rows with historical features and one-year-ahead label, ISO3166 alpha3-coded countries/territories (not independent draws). No interpolation or target leakage from future feature values.
- Chronological train 1965–1984; supervised error-risk fit 1986–1993; review score threshold calibration 1995–1997; labelled monitoring 1999–2004; untouched post-monitor future 2006–2012.
- Reference seed 71000 and fifteen auxiliary seeds 71100–71114 per model, four models: Logistic Regression, Decision Tree, Random Forest, Extra Trees; **64 fits**.
- 1,150 monitoring rows and 976 future rows per family (4,600 + 3,904 case×model observations). The other case×model rows belong to risk fit or threshold calibration.

| Family | Future confidence-only cost | Future augmented cost | Augmented gain (pp) | Annual max e | Promoted? |
|---|---:|---:|---:|---:|---|
| Logistic Regression | 0.09785 | 0.09529 | +0.26 | 1.006 | No |
| Decision Tree | 0.14908 | 0.08965 | +5.94 | 1.112 | No |
| Random Forest | 0.07172 | 0.06916 | +0.26 | 1.000 | No |
| Extra Trees | 0.09477 | 0.09580 | -0.10 | 1.003 | No |

A positive gain is a reduction of the hypothetical mean (automated errors + 0.25×reviews). The reported augmented costs are **counterfactual**: the frozen R7 gate would keep the confidence-only baseline in every family. Results are not human outcomes.

## 3. Critical e-process reachability failure

The monitoring window contains exactly six annual observations. With bounded |X_t|<=1, the largest theoretically possible mixture e-value at year 6 is **5.3223736828006**, which is below the threshold **20**. Therefore **0/4 promotions is mathematically forced regardless of model behaviour**. This was identified by a post-freeze audit and disclosed; it is neither evidence of conservative successful safety control nor a statistical rejection of the augmented policy. At least 10 years would be needed even if every annual gain attained the absolute maximum +1. Under a constant gain +0.05, 151 such years would be required with these frozen stakes. Even a statistically valid test can be operationally unusable without adequate independent information units.

The Decision Tree country-row naive e-process reaches a huge maximum, **3.62×10^16**, and crosses the threshold at row 91. In contrast, the year-aggregated e-process max is only **1.112**. The rowwise result is **not interpretable as an anytime-valid confirmation** unless the false assumption of rowwise conditional independence / nonpositive conditional gain holds. A large numerical e-value computed under a violated null is not evidence.

## 4. Post-hoc stronger baselines

After reading the main R7 outcomes, several simple scoring baselines were added using frozen validation-score thresholds (all labels held out). These are labelled exploratory and cannot validate a post-hoc winner.

| Family | Raw confidence | Disagreement only | Supervised confidence | Supervised augmented |
|---|---:|---:|---:|---:|
| Logistic Regression | 0.0848 | 0.1183 | 0.0978 | 0.0953 |
| Decision Tree | 0.1396 | **0.0879** | 0.1491 | 0.0897 |
| Random Forest | **0.0648** | 0.0930 | 0.0717 | 0.0692 |
| Extra Trees | 0.0904 | 0.1084 | 0.0948 | 0.0958 |

The supervised augmented rule does **not** dominate elementary baselines. This is explicitly part of the research outcome.

## 5. What can and cannot be claimed

Can: demonstrate mathematically why treating clustered rows as independent betting increments can produce severe false activation; provide exact frozen-gain accounting, controlled negative simulation, a new held-out multi-entity panel, and an auditable **feasibility correction**.

Cannot: claim novelty of betting supermartingales or cluster dependence; claim a successful protective gate when alarm crossing was impossible; claim populations or countries are independent; claim clinical, operational or human-review superiority; claim genuine future guarantee under arbitrary shifts; infer statistical significance from 4 model families using overlapping countries/years.

**Next confirmatory design:** specify feasible information units, either acquire genuinely separate target institutions/blocks or establish defensible dependence assumptions and block-level sequential evidence; run an a priori power simulation using plausible effect sizes; freeze risk fitting and threshold calibration before future labels; evaluate across independent datasets and holdout time periods without using them to select a winner.
