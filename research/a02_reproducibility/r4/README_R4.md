# R4: A06 external-domain frozen-threshold audit

This folder is an independent extension to the R3 article *When High Confidence Is Not Reproducible*. It does not overwrite A01-A05. The goal is to evaluate whether an exploratory confidence-plus-retraining-disagreement score remains useful when the **review threshold, including its randomized tie rule, is frozen using validation data**, rather than selecting exactly 10% of the held-out batch after observing its scores.

## Scientific design and status

The local JSON `code/protocol.json` was written before the first A06 model fit, SHA-256 `736ed5fa72f662307cb1e6534eaf134c7c6d2590c55a5414c4d76939b399e7fe`. This is not external preregistration, and the study hypothesis / method derives from earlier experiments A01-A05. It is therefore an exploratory out-of-domain robustness check, **not** a wholly independent confirmatory discovery.

Four older, public/package-bundled tasks from `statsmodels` 0.14.6 are newly used in A06 (not used in A01-A05): (a) presence of any affair in Fair survey; (b) at least one medical doctor visit in RAND Health Insurance Experiment; (c) chosen transport alternative in the mode-choice survey; (d) a recorded binary reported vote in ANES96. Features exclude each target; `individual` is excluded in modechoice and also used as a *group split* to keep all four alternatives for a traveller in the same train/validation/test partition. ANES96 `PID` is excluded to avoid a straightforward proxy for the vote outcome. These are historical/social datasets, **not** tests of medical clinical validity, modern electoral outcomes, deployment safety or transport-choice production readiness. RAND HIE may contain repeated observations without a disambiguating person ID in the packaged table, so per-row inference should not be treated as independent-person evidence. Modechoice is a simplified per-alternative binary decision, not a properly normalized choice-set model.

Two group-aware/stratified 60/20/20 splits (seeds 303 and 404), four fixed model families (logistic, decision tree, random forest, SGD log-loss), one fixed reference (seed 42000) and 15 independent *code-seeded* audit fits (seeds 43000-43014) yield 32 dataset-model-split cells, 512 total fit calls and 45,352 held-out case-model predictions. Audit models never vote on, or alter, the operational reference prediction.

The six review scores are confidence-only, fixed combined confidence+reference disagreement, probability dispersion, reference disagreement alone, audit-vote uncertainty, and entropy of the audit mean probability. The last two are intentionally stronger ensemble-type uncertainty baselines; their scores are audit-only, and they do not change the fixed reference model's class. The combined coefficient is frozen at 0.5 from R3, never tuned on A06 labels.

## Frozen operational rule

For a validation sample of size `N_val`, let `k = ceil(0.1*N_val)`. Set the **threshold** `t` to the k-th largest **validation** score, let `b = #validation scores > t` and `e = #validation scores == t`, and freeze `rho = (k-b)/e`. For each later single test case, review if score `s>t`, or if `s==t` and the SHA-256 pseudouniform hash of its case ID plus tie seed is less than `rho`. This specifies an expected validation budget; the realized test coverage need *not* be 0.9 and different policies may realize different test coverage. This deployment-oriented policy requires no test-batch size or labels and is invariant to the order of incoming cases. Eight tie seeds give descriptive sensitivity. The exact 90%-coverage held-out top-k procedure is reported **only** as a second, batch-based score-ranking diagnostic and never as streaming coverage control.

## Findings

Independent reconstruction of 1,728 policy outcomes from 90,696 saved validation+test case scores across the 32 cells passed. The streaming combined score had 17 lower, 8 equal and 7 higher accepted-case risk values than the confidence-only policy. The unweighted descriptive mean of their risk differences was -0.006245, but mean absolute within-cell realized coverage gap was 0.00798 and maximum gap was 0.03571, so the signed risk difference is **not** identified as a pure effect of the score. For exact-batch matched coverage, the same score had 18 lower, 11 equal and 3 higher risks, with a descriptive mean difference -0.006721. Individual datasets are resplit and models share data, so 32 cells are **not** 32 independent statistical replications.

The separate reference-audit entropy, dispersion, vote-uncertainty and disagreement-only baselines are included, along with negative results. In contrast to a universal method-superiority claim, ensemble entropy produced 12 gains / 9 ties / 11 losses under exact-budget selection, whereas vote uncertainty alone produced 8 gains / 5 ties / 19 losses. The original R3 experiments were more variable and also contain adverse cases.

For the exact-batch combined-vs-confidence comparison, a conditional 2,500-replicate fixed-mask paired bootstrap was computed per cell. Modechoice uses *individual-group bootstrap* rather than independent rows. Four of 32 unadjusted 95% intervals excluded zero in the beneficial direction. These intervals are not multiplicity-corrected and do not justify a population-wide claim; resplit overlap, model selection from prior R3, and incomplete clustering metadata in RAND HIE further limit inference. No test-label optimization or re-fitting was performed in A06.

## Post-hoc streaming review-cost sensitivity (supplementary)

The operational streaming policies can realize different held-out review fractions, so accepted-case risks alone are insufficient. A separate **post-hoc accounting proxy** avoids this comparison problem by evaluating

`L(lambda) = (number of incorrect accepted decisions + lambda * number reviewed) / number of held-out cases`,

where `lambda` is a hypothetical review workload cost in units of one automated classification error. This is **not** measured human-review utility, and no lambda was selected in advance. It does not assume that reviewed cases would be correctly resolved; it counts automated residual errors plus review effort. For the fixed tie seed, the combined policy was Pareto superior in 5 of 32 cells, Pareto inferior in 1, exactly equal in 8, and involved an error/workload tradeoff in 18. For lambda 0.1 it had 17 lower / 8 equal / 7 higher cost values; at lambda 0.5 the split was 19 / 8 / 5. The unweighted mean cost contrast across lambda 0 through 1 ranged from -0.534 to -0.502 error-equivalents per 100 cases. This is a descriptive sensitivity check on inspected outcomes, not a finding of optimal review policy. Full per-cell results are in `results/analysis/A06_REVIEW_COST_BY_CELL.csv`, the grid summary in `A06_REVIEW_COST_SUMMARY.csv`, and the exact recomputation in `code/a06_review_cost.py`.

## Reproduce

Tested locally on CPython 3.13.5, numpy 2.3.5, pandas 2.2.3, scipy 1.17.0, scikit-learn 1.8.0, statsmodels 0.14.6, matplotlib 3.10.8, python-docx 1.2.0 and pytest 9.0.2.

```bash
python -m pip install -r requirements-R4.txt
python -m pytest -q code/test_a06.py
python code/verify_a06.py --protocol code/protocol.json --results results
python code/analyze_a06.py --results results --out results/analysis
python code/a06_review_cost.py --results results --out results/analysis
python code/make_figures_a06.py
```

The `results/` directory includes the frozen case-level scores, immutable calibration policies, manifest files with input/data hashes, policy outcomes for eight tie seeds and exact-batch baselines, summary analyses and verification receipt. For fresh retraining, run four commands with new output destinations, e.g. `python code/a06_streaming.py --protocol code/protocol.json --out rerun/fair --dataset fair_affair_any`; do not overwrite released results. The packaged data source is loaded programmatically from installed `statsmodels`; no original respondent records are copied into this research archive. Test hashes may differ across numeric library revisions; comparisons should be made at case-level first.

## Next science, not claimed as done

The current work does not have a truly untouched external institution/time cohort, a production streaming deployment, an externally audited independent random fit distribution, or statistically established superiority across independent datasets. Formal lower bounds on score variation remain assumptions rather than experimentally verified conditions; the known margin and exact binomial formulas are not mathematical novelty. A genuinely stronger paper requires a new temporal/organizational dataset, external preregistration and larger independent cohorts, not merely more seeds on the same benchmark.

Sources: Seabold and Perktold (2010), *Statsmodels: Econometric and Statistical Modeling with Python*, SciPy; https://doi.org/10.25080/majora-92bf1922-011. `statsmodels` dataset descriptions, https://www.statsmodels.org/stable/datasets/index.html.
