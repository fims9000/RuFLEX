# A01 executable master specification

This directory defines A01 before any benchmark training or final-test access. The scientific subject is the frozen RuFLEX RC2 product snapshot `c610f5740f2b26d60eabd9069a298dc6022c9548`; the harness calls its native Dataset/TrainingStudy/Evaluation/DecisionThreshold/StabilityAnalysis/StabilityGate services and does not reimplement those semantics.

## Locked primary matrix

`TRAINING_VARIABILITY`, fixed `split_seed = 42`, fractions TRAIN/VALIDATION/final-test = 0.60/0.20/0.20, and `training_seed = 0..19` yield 300 declared runs: three datasets × five model families × twenty seeds. `locked_execution_plan.jsonl` gives every run a deterministic UUID5 identity. The split ablation is explicitly secondary and cannot produce HCIR or a Stability Gate.

## Data and preprocessing

`dataset_specs.json` records raw and canonical-table SHA-256 identities, source URLs, targets, positive mapping, row identity, declared feature order, exclusions and categorical transformation. Materialization rejects hash, feature-order and missing-data mismatches. It produces only canonical numeric CSV input; train-only standard normalization and median imputation remain product-native training behavior.

## Frozen decisions

The selected run is maximum validation F1; exact ties select the lowest training seed. Its raw validation F1 threshold is the only operational class threshold. Gate constants are pre-specified: confidence `0.90`, selected-run agreement `0.80`, and raw probability standard deviation `0.15`. HCIR uses selected-run agreement and is null/N/A for a zero high-confidence denominator. Majority agreement is descriptive only.

## Failure and claim discipline

Every primary cell requires all twenty declared runs. A failed run is retained and makes the cell `INCOMPLETE_DECLARED_RUN_SUPPORT`; replacement seeds and silent partial-support results are forbidden. A01 remains PRE-FREEZE: no empirical claim, result table or final-test artifact is allowed.
