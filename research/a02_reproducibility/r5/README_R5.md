# R5 — conditional decision value of prediction reproducibility

This is an *independent research extension* of `research/a01_stability_aware_review` and R4, not a modified version of their results. The project asks **when** audit disagreement across repeated fits is worth using for selective review, not whether confidence and reproducibility are always correlated.

## Main estimand

Reference classifier prediction is fixed. Extra audit training runs provide disagreement and probability dispersion; they do not vote. We compare two *equally supervised* validation-fitted error-risk models, one using confidence plus predicted class and the other also using retraining disagreement and dispersion. The decision-value identity for *true* risks is familiar Bayesian decision theory; our hypothesis concerns how well a **fitted** audit-based risk predictor can approximate that value out of time.

## Files

- `HYPOTHESIS_R5.md`: mechanism, formal value and capacity dual, explicit testable hypotheses, novelty boundary and citations.
- `PROTOCOL_R5.json` and `PROTOCOL_FREEZE_RECEIPT.json`: locally frozen new temporal challenge; SHA-256 `791ee6dd60c84cf09e02cd01571d14c9f646ae46c45f638bd92565aa98804291`.
- `SOURCE_FREEZE_RECEIPT.json`, `SOURCE_AMENDMENT_001.json`: precise record of one nonsemantic key lookup correction (seed 55043 unchanged); **not externally preregistered**.
- `code/r5_core.py`: frozen-budget review, risk features, error-risk models and descriptive block bootstrap.
- `code/run_temporal_co2.py`: chronology-first CO₂ validation/test, four models, 30 audit fits per reference, 248 total fit calls.
- `code/verify_r5.py`: independent reconstruction of 64 saved policy outcomes from case-level scores and cutoffs.
- `code/analyze_a06_historical.py`: R4 held-out reanalysis, explicitly exploratory because those outcomes were already inspected.
- `code/ablate_r5.py`: **post-hoc** disagreement/dispersion ablation, not part of frozen primary protocol.
- `code/build_report.py` and `code/build_appendix_docx.py`: artifact regeneration.
- `results/temporal_co2/`: released case-level scores, frozen policies and receipt; not all large CSVs live in GitHub.
- `results/R5_PRIMARY_CONTRASTS.csv`, `results/R5_A06_EXPLORATORY_REANALYSIS.csv`, `results/R5_POSTHOC_ABLATIONS.csv`, `results/R5_SUMMARY.json`.
- `manuscript/R5_Conditional_Decision_Value_Research_Appendix.docx`: article-ready, three-page scientific appendix.

## Fully reproduce the new temporal challenge

Python 3.13, with packages from `requirements-R5.txt`. Source data are **bundled with statsmodels**; no network request is performed. Run from `code/`:

```sh
python -m pip install -r ../requirements-R5.txt
python -m pytest -q test_core.py
python run_temporal_co2.py --protocol ../PROTOCOL_R5.json --out ../results_new
python verify_r5.py --protocol ../PROTOCOL_R5.json --results ../results_new
python build_report.py
```

The last `build_report.py` reads the released `results/` location, not the alternative `results_new`; using a fresh destination first prevents accidental overwriting of the frozen evidence. To regenerate R4 historical reanalysis from the prior full R4 ZIP, see:

```sh
python analyze_a06_historical.py --r4-results /path/to/R4/results --out ../results
```

The original released R5 files have SHA-256 identities in `results/temporal_co2/R5_TEMPORAL_RECEIPT.json`. A second complete 248-fit execution on the same pinned stack yielded **identical bytes** for all three canonical main CSVs.

## Results, including contradictions

- New CO₂ late block: 3 lower, 1 tied, 0 higher joint streaming cost among four dependent model families. At exactly matched test budget: accepted errors reduced by 0/2/6/2 for Logistic/Tree/Forest/SGD.
- New CO₂ earlier dependent block: 3 lower, 0 tied, **1 higher** streaming cost (Logistic Regression).
- Previously inspected A06 cells: **13 better / 4 tied / 15 worse** streaming costs; this is **not independent confirmation**.
- Late Tree included 88 confidently (>=0.90) but unanimously wrong case-level predictions (zero observed disagreement), showing why reproducibility cannot certify correctness.
- The already inspectable ablation shows that the best audit covariate differs across model families. Both signals together are **not guaranteed** better than a subset.
- The 26-week moving-block intervals are descriptive rather than formal population coverage guarantees under nonstationary time series. No global p-value, familywise superiority or deployable human-review gain is claimed.

## Independent replication caveats

The historical CO₂ data have only **one temporal source**, and the two time folds overlap. The 248 fits and 2,820 test case–model decisions are *not* 248 or 2,820 independent application replications. Pseudorandom integer seeds are not an IID certificate. The λ=0.25 review accounting proxy is not human-review measured performance; actual streaming coverage can drift from validation. No automatic external-acceptance or scientific novelty claim follows from a known Jensen inequality.

## Prior art

See `HYPOTHESIS_R5.md` for citations, particularly Franc–Prusa–Voracek (JMLR 2023), Black–Leino–Fredrikson (ICLR 2022), and Paplhám et al. (2026). The **novel empirical question** is the conditional, fixed-reference reproducibility signal under prospective budget and temporal shift; priority against all existing work remains to be established.
