# A01 Statistical Analysis Plan — Phase 0.5 freeze

Status: `PRE_EXECUTION_STATISTICAL_FREEZE`. This plan defines future analysis; it contains no A01 benchmark result.

## Unit and scope

The primary matrix has 15 cells: `dataset_id × model_family`. A TrainingRun is an independent model fit, not an independent dataset. Case-level analysis uses the same materialized fixed-split case across the 20 fits. AI4I is the primary engineering benchmark. Bank Marketing and Wisconsin Diagnostic Breast Cancer provide secondary generality evidence only; the latter is not clinical validation.

## H1 and H2

H1 reports aggregate validation-F1 distribution (mean, median, standard deviation, range, IQR) together with individual decision disagreement. It has no arbitrary post-hoc “close F1” margin. The permitted statuses are `PATTERN_OBSERVED`, `PATTERN_NOT_OBSERVED`, and `NOT_ASSESSABLE`.

H2 fixes high confidence at `0.90` and instability at selected-run agreement `< 0.80`. HCIR is the count meeting both conditions divided by high-confidence cases. A zero denominator is null/N/A with `ZERO_HIGH_CONFIDENCE_DENOMINATOR`, never zero. Majority agreement is descriptive only.

## H3 confirmatory comparison

Policy A is the frozen raw Stability Gate: selected-run confidence `0.90`, selected-run agreement `0.80`, raw probability standard deviation `0.15`, and the exact raw validation F1 DecisionThresholdPolicy. Policy B is a confidence-only comparator using the same selected run, raw threshold and scope, but no cross-run information.

Policy B’s cutoff is selected only on validation: choose among distinct validation selected-run confidence values by minimum absolute gap from Stability Gate validation coverage; ties choose the higher cutoff and then deterministic numeric ordering. It freezes before final-test access and is never retuned to final-test coverage.

Accepted-case risk is errors among ACCEPT cases divided by ACCEPT count. A zero accepted denominator is null/N/A. The primary effect is `Delta_R = R_stability - R_confidence`; negative means lower Stability Gate accepted-case risk. Relative risk is omitted when comparator risk is zero.

For each AI4I cell, the secondary endpoint is accepted-case false-negative rate. Zero accepted positives is null/N/A, not zero.

## Uncertainty and interpretation

Final-test uncertainty uses a paired case bootstrap: 10,000 replicates, RNG seed `20260902`, 95% two-sided percentile confidence interval. Both policies are recomputed on the same sampled cases. A replicate with a zero accepted denominator for either policy is invalid for that statistic. Fewer than 90% valid replicates gives `UNSTABLE_OR_NOT_ESTIMABLE` and no strong inferential claim.

H3 is family-specific. Its permitted helper statuses are `SUPPORTS_H3` only when the Delta-risk CI lies below zero, `CONTRADICTS_H3` only when above zero, `INCONCLUSIVE` when it includes zero, and `NOT_ASSESSABLE` when risk/CI is undefined. There is no generic “RuFLEX H3 PASS” and no global uncorrected p-value. Any optional secondary p-values use Holm correction within their predeclared family.

## Required reporting

The frozen figure order is F01–F08 and table order is T01–T08 in `config/statistical_analysis_plan.json`. Illustrative unstable cases are selected deterministically by selected-run agreement ascending, confidence descending, then case ID. Negative, inconclusive, failed, and undefined results are required outputs.

## Amendment rule

Changing an endpoint, formula, comparator, bootstrap procedure, interpretation, figure-selection rule, or handling rule requires `AMENDMENT_001.md` (or a later numbered amendment) with defect, discovery timing, validation/final-test access state, affected artifacts, and necessity. An amendment after benchmark validation cannot be presented as wholly original pre-specification; an amendment after final-test access closes original confirmatory A01 and requires R2.
