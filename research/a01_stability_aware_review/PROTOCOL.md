# A01 — Stability-Aware Selective Review

Status: PRE-FREEZE DESIGN — no final-test data have been accessed.

## Question

With the data split, preprocessing, architecture, and hyperparameters fixed, do independently trained model fits retain close aggregate validation quality while differing on individual predictions? Can validation-derived cross-run prediction consistency reduce accepted-case risk at matched coverage relative to confidence-only review?

## Main protocol

The primary mode is `TRAINING_VARIABILITY`: one persisted `split_seed` determines the TRAIN / VALIDATION / final-test identities, while twenty `training_seed` values change only model randomness. No HPO, architecture change, preprocessing change, or final-test inspection is permitted while policies are chosen. Logistic Regression, Decision Tree, Random Forest, Gradient Boosting, and FlatNeuroFuzzy are evaluated as declared model families. AI4I 2020 predictive maintenance is the engineering scenario; UCI Bank Marketing and Wisconsin Diagnostic Breast Cancer are generality benchmarks, not clinical validation.

## Frozen definitions before final-test unlock

- High confidence: selected-run confidence >= 0.90.
- Prediction instability: selected-run agreement (not majority consensus) < 0.80, using the exact frozen validation-derived raw DecisionThresholdPolicy.
- HCIR: proportion of high-confidence validation cases whose selected-run agreement is below 0.80; it is undefined when no validation case meets the high-confidence criterion.
- Stability Gate: `BLOCK` for declared out-of-scope cases; otherwise `REVIEW` for low confidence, run disagreement, or probability dispersion above the validation-derived frozen limit; otherwise `ACCEPT`.
- Explanation reproducibility is a separate evidence channel and is not an operational review criterion.
- Primary model-level metric: validation F1 (with ROC-AUC, PR-AUC, Brier and ECE reported descriptively when defined). For AI4I, false-negative rate among accepted cases is also reported.
- Risk–coverage comparison: no review, confidence-only review, and Stability Gate are compared at the same accepted coverage; a deterministic random-review reference is descriptive only.
- Exclusions/failures: a run that cannot produce the declared validation evidence is recorded and excluded only under a predeclared execution-failure rule; the study reports the run count, reason, and any resulting loss of required support. No dataset, seed, model family or threshold is replaced after validation or final-test inspection.

## Primary hypotheses

- H1: fixed-split independent fits can have close aggregate validation metrics without perfect individual prediction agreement.
- H2: selected-run high-confidence cases can be unstable across independent fits.
- H3: at equal coverage, the Stability Gate can have lower accepted-case risk than confidence-only review.

H4 is secondary: prediction and explanation stability are not equivalent.

## Required evidence and claims boundary

Persist `TrainingStudy`, `StudyStabilityAnalysis`, selected-run validation evaluation, `StabilityGatePolicy`, risk-coverage rows, case-level evidence, data/split identities, and independent explanation reproducibility where available. The experiment may claim only observed benchmark behaviour under the frozen protocol. It may not claim to remove stochasticity, universal leakage detection, causal explanation validity, clinical validation, or a universal safety guarantee.

## Final-test firewall

Calibration, class threshold, confidence cutoffs, agreement limits, and maximum probability dispersion are selected from validation objects only. The policy is frozen before one explicit final-test evaluation. Any later retuning requires a new experiment/protocol and must not be presented as an unbiased final-test estimate.

## Split-variability ablation

After the primary analysis, a separate `SPLIT_VARIABILITY` ablation fixes the training seed and changes only `split_seed`; `COMBINED_VARIABILITY` changes both. These are reported separately and are never described as pure training-seed effects.
