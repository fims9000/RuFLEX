# Amendment 002 — TreeSHAP execution conformance

## Discovery and scope

This implementation defect was found while attempting the un-frozen R4 CLEAN
baseline.  Fifteen declared model fits and 175 unfrozen CLEAN artifacts existed;
the CLEAN baseline had not been frozen, no corrupt artifact had been generated,
no detection or localization result existed, and no final-test data was accessed.

For a persisted Bank Marketing Random Forest, SHAP 0.51's interventional
multi-output custom-tree route produced a class-output additivity mismatch even
though the declarative product predictor returned the persisted probability.  A
single constituent tree demonstrated the issue: the SHAP reconstruction selected
the opposite class output.  This was an execution-path defect, not a benchmark
outcome and not a model or data-selection result.

## Corrected implementation

RuFLEX declarative TreeSHAP now uses `tree_path_dependent` perturbation over the
persisted train-partition tree-node frequencies.  It does not consume validation
or final-test rows and its reconstruction is checked against the persisted
product-native prediction.  The former finite interventional background setting
is not used by this route.

`L1_LOW_FIDELITY/reduced_budget` is consequently `NOT_APPLICABLE` for TreeSHAP:
there is no honest reduced finite-background budget under the corrected route.
The artifact/evaluation matrix preserves the planned rows and records that
applicability explicitly; it does not create a fake low-fidelity TreeSHAP
artifact.

## Scientific consequences

The S03 question, datasets, models, sample rule, corruption definitions,
severity levels, validator modes, Quantus inventory, and all decision rules are
unchanged.  R4 is retained only as an interrupted implementation attempt and is
not part of any S03 denominator.  A new coherent R5 CLEAN baseline starts from
newly fitted declared models and is required before any corrupt execution.
