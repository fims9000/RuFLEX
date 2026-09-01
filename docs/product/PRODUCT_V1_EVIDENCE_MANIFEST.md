# RuFLEX Product V1 evidence manifest

This is **product implementation evidence**, captured from the frozen RC2.1 React Studio by `frontend/e2e/product-evidence-capture.spec.ts`. It is not a research benchmark package; `docs/article/` remains separate research material. Runtime UUIDs for the capture project are recorded in `PRODUCT_V1_EVIDENCE_RUNTIME.json`.

| Screenshot | Capability / persisted objects | Evidence class | Proves | Does not prove | Route and coverage |
|---|---|---|---|---|---|
| 01_project_explorer.png | Project, Explorer groups | operational | An open project exposes object-centric Data/Models/Studies/Analyses/Evidence inventory | Every object is scientifically validated | capture; project-lifecycle E2E |
| 02_dataset_contract.png | DatasetContract, audit | structural | Confirmed dataset schema, target/task, profile and audit are persisted | No leakage or fitness beyond displayed checks | capture; dataset contract tests |
| 03_fis_designer.png | FIS revision | structural | Editable variables, MFs and rules are present in the canonical designer | A post-hoc attribution is exact | capture; FIS designer tests |
| 04_exact_fis_trace.png | FIS evaluation / trace | exact | Native FIS computation trace is separately identified | Continuous state-space exhaustiveness | capture; FIS trace tests |
| 05_training_and_study.png | TrainingRun, TrainingStudy, SeedRuns | statistical | Real training and validation-only multi-seed distribution are persisted | Final test selected the model | capture; multiseed E2E |
| 06_evaluation_and_calibration.png | Evaluation, CalibrationTransform | statistical | Validation predictive metrics and calibration are distinct persisted evidence | Calibration guarantees field performance | capture; calibration E2E |
| 07_decision_threshold.png | DecisionThresholdPolicy | behavioral | Threshold derives from validation provenance while final test remains locked | A universal operating threshold | capture; calibration/threshold E2E |
| 08_generalization_and_slices.png | GeneralizationContract, SliceAnalysis | operational/statistical | Declared scope and validation slice evidence are separate | Unbounded generalization | capture; scope/slice tests |
| 09_xai_and_explanation_check.png | Explanation, ExplanationCheck | post-hoc | Compatible attribution and available checks are labelled post-hoc | Causality or exact computation | capture; evidence E2E |
| 10_cross_run_reproducibility.png | ExplanationReproducibilityAnalysis | statistical | Prediction and explanation agreement, pairwise values and variability are separate | Predictive stability implies explanation stability | capture; reproducibility E2E |
| 11_behavior_specs.png | BehaviorSpec, BehaviorSpecResult | behavioral | Executed PASS/FAIL requirement remains bound to a persisted revision/run | Exhaustive functional correctness | capture; BehaviorSpec E2E |
| 12_selective_review_policy.png | SelectivePredictionPolicy | behavioral | Validation-derived ACCEPT/REVIEW cutoff is distinct from class threshold | Automatic acceptance is always appropriate | capture; selective policy E2E |
| 13_exhaustive_lab.png | ExhaustiveLabResult | exact finite structure | Exact decision-tree finite paths are enumerated and labelled honestly | Arbitrary continuous model exhaustiveness | capture; Exhaustive Lab E2E |
| 14_expert_correction.png | ExpertCorrectionRevision | structural/behavioral | FIS revision retains expert structure while fitting unlocked consequents on TRAIN only | Improvement on the locked final test | capture; expert correction tests |
| 15_lineage.png | LineageGraph, FIS revision, BehaviorSpec, BehaviorSpecResult | structural | Saved references include the RC2.1 FIS revision → BehaviorSpec → result chain after reopen | A causal graph or execution prescription | capture; lineage regression test |
| 16_assurance_case.png | AssuranceCase | operational | Independent PASS/WARN/FAIL/NOT_AVAILABLE gates and risks, without a trust score | A scalar safety/trust conclusion | capture; assurance E2E |
| 17_verification_bundle.png | VerificationBundle | operational | Inspection-first declarative export reports entry checksum | Export contains executable models or sensitive raw data | capture; assurance E2E |
| 18_condition_monitoring_demo.png | DemoDecision with linked evidence | operational | Safe telemetry decision support yields ACCEPT/REVIEW/OUT_OF_SCOPE and names evidence links | Targeting, actuator control, or autonomous command | capture; demo E2E |
| 19_close_reopen_restored.png | Reopened project evidence | operational | Assurance and central persisted state survive close/reopen | Every possible external deployment restart condition | capture; lifecycle and route E2E |

All screenshots use a 1440×900 light Studio viewport. The capture test fails instead of silently omitting a required route.
