# RuFLEX Product V1 demonstration

## 1. What RuFLEX V1 is

RuFLEX V1 is an evidence-centred model-engineering Studio: React/TypeScript is the user surface, FastAPI is the boundary, and canonical Python objects persist the scientific and operational evidence. It is not a recreation of a legacy Streamlit interface or a single “trust score”.

## 2. Demonstration project and protocol

`product-evidence-capture.spec.ts` creates a deterministic equipment-health telemetry project, confirms its DatasetContract, declares an intended scope, and saves all objects before reopening. The demonstration uses validation for selection, calibration, thresholds and review policies. The final test is explicit and follows policy freeze.

## 3. Data and modelling

The project imports telemetry, profiles/audits it, and persists a DatasetContract ([dataset contract](screenshots/02_dataset_contract.png)). An editable FIS is then created from the dataset ([designer](screenshots/03_fis_designer.png)); FIS revisions are canonical persisted objects, not screenshots of a simulated editor.

## 4. Exact trace and training

The Studio reports the native FIS calculation as an exact computation trace ([trace](screenshots/04_exact_fis_trace.png)). This exactness is distinct from post-hoc attribution. Real logistic and Decision Tree runs, plus a validation-only multi-seed Study, are persisted ([training and study](screenshots/05_training_and_study.png)).

## 5. Evaluation, calibration and policies

For binary models, save the validation Evaluation to persist raw-model ROC and
precision–recall operating curves alongside the complete validation prediction
evidence. These curves are descriptive validation evidence; they do not choose
a decision threshold and do not access the locked final-test split.

Validation predictive metrics and calibration are separately visible ([evaluation](screenshots/06_evaluation_and_calibration.png)). A class threshold is selected from validation evidence and records its provenance while final-test data remain locked ([threshold](screenshots/07_decision_threshold.png)). The confidence cutoff for ACCEPT/REVIEW is a separate validation-derived policy ([selective review](screenshots/12_selective_review_policy.png)); it is not another class threshold.

## 6. Scope, slices, explanations and reproducibility

The GeneralizationContract declares support and out-of-scope handling, while Slice Lab measures a stated validation subset ([scope and slices](screenshots/08_generalization_and_slices.png)). Post-hoc XAI is labelled as attribution, with available explanation checks—not as causal or exact explanation ([XAI](screenshots/09_xai_and_explanation_check.png)). Cross-run evidence reports prediction and explanation reproducibility separately ([reproducibility](screenshots/10_cross_run_reproducibility.png)); predictive agreement alone is not evidence of explanation stability.

## 7. Engineering evidence

BehaviorSpecs execute persisted PASS/FAIL requirements ([BehaviorSpecs](screenshots/11_behavior_specs.png)). Exhaustive Lab labels only finite tree structure or a declared discrete grid as exact ([Exhaustive Lab](screenshots/13_exhaustive_lab.png)); it does not claim to exhaust arbitrary continuous models. Expert correction refits only unlocked Sugeno consequents on TRAIN while preserving expert structure ([correction](screenshots/14_expert_correction.png)).

## 8. Final-test firewall, lineage and assurance

The demonstration opens final test only after the validation policy is frozen. Saved provenance is visible in [Lineage](screenshots/15_lineage.png), including the RC2.1 `FIS revision → BehaviorSpec → BehaviorSpecResult` edge. [AssuranceCase](screenshots/16_assurance_case.png) presents independent evidence gates and unresolved risks rather than a scalar trust number. [VerificationBundle](screenshots/17_verification_bundle.png) is inspection-first and excludes executable model objects, raw datasets, credentials and caches.

## 9. Condition monitoring and persistence

The safe condition-monitoring demonstration links telemetry prediction, declared scope, explanation/check, AssuranceCase and VerificationBundle to an ACCEPT, REVIEW, or OUT_OF_SCOPE result ([demo](screenshots/18_condition_monitoring_demo.png)). It contains no targeting, weapon, actuator, or autonomous-control command. After close/open, central persisted evidence is restored ([reopen](screenshots/19_close_reopen_restored.png)).

## 10. Known limitations

These screenshots prove only the captured persisted route. They do not prove field accuracy, causal explanation, universal coverage, unrestricted generalization, or safe deployment in every environment. Product evidence is deliberately separate from research/article benchmark material under `docs/article/`.
