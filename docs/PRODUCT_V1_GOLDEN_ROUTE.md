# Product V1 Golden Route

The persisted Golden Route is exercised by the Product browser routes and integrated backend journey.

1. Create a project, import telemetry CSV/XLSX, inspect audit findings and confirm `DatasetContract`.
2. Create/edit a FIS, execute exact FIS trace, compare revisions, and preserve the expert correction lineage.
3. Train ANFIS, Decision Tree and ordinary baselines; create a multi-seed Study and select by validation only. Long Studies persist their declared request and seed lifecycle through the local executor, so an interrupted project can be reopened and explicitly resumed without replacing seeds or changing fit configuration.
4. For a fixed-split `TRAINING_VARIABILITY` Study, create persisted Stability Lab evidence, inspect HCIR and a case-level disagreement, then freeze a validation-derived Stability Gate before final-test access. `SPLIT_VARIABILITY` and `COMBINED_VARIABILITY` remain separate aggregate-sensitivity protocols and do not claim fully matched case-level evidence.
4. Persist validation Evaluation, calibration, class threshold, compatible comparison, GeneralizationContract and slices.
5. Generate capability-compatible explanation evidence/checks. For compatible repeated cases, run cross-run reproducibility; prediction and explanation agreement remain separate.
6. Execute revision-bound BehaviorSpecs and a validation-only ACCEPT/REVIEW selective policy.
7. Use Exhaustive Lab only for `EXACT_FINITE_STRUCTURE` Decision Tree paths or `EXACT_ON_DECLARED_DISCRETE_GRID` FIS states.
8. Freeze policy and explicitly evaluate the final test. Later selective-policy tuning is blocked.
9. Build Lineage, AssuranceCase and the inspection-first VerificationBundle; validate its checksums, typed evidence and direct provenance references from the ZIP or a freshly extracted root; close and reopen the project.
10. On reopen, inspect the project integrity report. It validates DatasetContract/artifact and TrainingRun/model-artifact bindings without silently recreating missing evidence; broken references are shown as `FAIL`.

The safe condition-monitoring demonstration is executable in Evidence: it persists telemetry decision evidence, an occlusion explanation/check, AssuranceCase and VerificationBundle without emitting any actuator or targeting command.
