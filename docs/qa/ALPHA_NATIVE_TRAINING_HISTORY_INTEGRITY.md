# Native one-shot training history integrity

Before this correction, the generic adapter service filled an empty fit trajectory with two identical synthetic epoch points. It copied a validation-derived proxy (`1 - accuracy` for classification or validation MSE for regression) into both `train_loss` and `validation_loss`. The built-in one-shot estimators do not expose measured epoch-wise training history, so those persisted points were not observations.

New native linear, tree, forest, and boosting runs retain their real validation metrics but persist an empty trajectory. Their summaries record a fit call (and estimator count for ensembles), not a fictitious best epoch or train loss. The Studio labels the history as unavailable. For historical one-shot native runs whose summary contains an empty history, it also suppresses the old synthetic plot without rewriting the saved run or its provenance.

The prior logistic-route test required `trajectory[0].epoch == 0` and thereby verified the incorrect fallback. It now verifies the actual adapter contract: empty trajectory, no fabricated training loss or best epoch, and unchanged validation metrics. Neuro-fuzzy runs still expose and test their measured epoch trajectory. This changes presentation/evidence integrity only; it does not refit any model or change validation/final-test predictions.

During full-suite verification, two pre-existing test fixtures were corrected without weakening their checks. The minimal A01 tie-break fixture now declares the fixed split seed required by current Study selection, and the final-test firewall test matches the current explicit rejection message while still requiring `TrainingError` after unlock.
