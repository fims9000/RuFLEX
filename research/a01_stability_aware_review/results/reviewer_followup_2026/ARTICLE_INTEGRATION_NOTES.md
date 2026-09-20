# A01 article integration notes for reviewer follow-up

These additions are reviewer-requested **post-hoc / exploratory** analyses. They must be labelled as such and must not be presented as part of the pre-specified confirmatory protocol.

## Suggested validation sensitivity paragraph

As a post-hoc validation-only sensitivity check, we varied the high-confidence threshold over 0.85, 0.90, and 0.95 and the selected-run agreement threshold over 0.70, 0.80, and 0.90 while keeping the frozen case-level predictions unchanged. Non-zero HCIR occurred in 4 of 15 cells at confidence thresholds 0.90 and 0.95 and in 6 of 15 cells at 0.85. For a fixed confidence threshold, the number of non-zero cells did not change across the three agreement cutoffs, although the largest HCIR varied from 4.922% to 7.413%. Thus, the qualitative observation that high-confidence disagreement is concentrated in a minority of dataset-model cells persists over the tested threshold range, while the exact count is sensitive to the lower 0.85 confidence cutoff.

## Suggested HCIR reference paragraph

We also computed a descriptive independence reference on validation data. The selected-run class and confidence were kept fixed, while each of the other 19 runs was replaced analytically by an independent label source preserving that run's observed positive-class frequency. This removes case-specific cross-run correspondence while retaining run-level class marginals. For each of the four cells with non-zero HCIR at the original 0.90/0.80 thresholds, the expected HCIR under this simple independence reference exceeded the observed HCIR. The comparison therefore provides no basis for interpreting the observed HCIR values as large relative to chance; HCIR remains a descriptive measure of disagreement in the actual retraining system rather than a calibrated significance statistic.

## Suggested probability-dispersion sensitivity sentence

Changing the maximum probability-standard-deviation criterion of the Stability Gate from 0.15 to 0.10 or 0.20 changed validation coverage by at most 0.097 percentage points across the 15 cells, indicating little sensitivity to this criterion within the tested range.

## Suggested Bank Marketing Decision Tree FNR paragraph

For completeness, a post-hoc descriptive calculation was also performed for the Bank Marketing Decision Tree cell. The accepted-case FNR was 65.13% with no review, 100.00% under confidence-only routing, and 69.28% under stability-aware routing; the difference between stability-aware and confidence-only FNR was -0.3072 with a paired-bootstrap 95% CI of [-0.3406, -0.2746]. This endpoint was not pre-specified for Bank Marketing, and final-test coverage differed between the policies (91.32% versus 86.49%), so the result is descriptive and does not identify a causal effect of cross-run disagreement at equal coverage.

## Suggested F1-selection limitation

The operational run was selected by maximum validation F1. In imbalanced settings, this criterion can favor runs with a particular precision-recall and confidence profile; the present study does not evaluate whether alternative model-selection criteria would lead to different stability or routing results.


## Suggested practical reduced-run paragraph

A post-hoc validation-only subsampling analysis retained the selected operational run and replaced the other 19-run reproducibility calculation by smaller frozen subsets. With 10 total runs (the selected run plus nine auxiliary runs), the reduced gate reproduced the full 20-run gate decision with 99.89% macro agreement across the 15 cells and recovered 97.04% of full-reference review cases while using 9/19 = 47.37% of the auxiliary-fit count. With 15 total runs, gate-decision agreement reached 99.98% and review recall 99.87% at 14/19 = 73.68% of the auxiliary-fit count. These values quantify approximation to the frozen 20-run reference; they do not establish a universal minimum run count or hardware-normalized compute saving.

## Practical interpretation

The deployed class still comes exclusively from the selected model. Auxiliary runs provide reproducibility evidence only; they do not vote on or replace the prediction. The reduced-run experiment therefore addresses the practical cost of measuring the diagnostic signal rather than changing the predictor.

Five Bank Marketing Decision Tree examples were retained as illustrative cases. The set intentionally contains both correct and incorrect 100%-confidence selected-model predictions with full-run agreement ranging from 10% to 75%. This is useful precisely because it shows that disagreement is a review diagnostic rather than an error label.

## What should not be changed

The frozen confirmatory claims, `A01_FINAL_RESULTS.json`, thresholds, policies, model fits, and final-test results should remain unchanged. The exploratory checks above are supplementary evidence added after reviewer feedback.
