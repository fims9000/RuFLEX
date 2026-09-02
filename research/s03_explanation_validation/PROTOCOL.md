# S03 — Contract-Bound Validation of Post-hoc Explanations

Status: **PRE-FREEZE PROTOCOL; NO BENCHMARK RESULTS GENERATED**.

S03 asks how specified RuFLEX validation mechanisms behave against constructed, matched clean/corrupt post-hoc explanation evidence. It does not claim that RuFLEX verifies explanations, guarantees correct XAI, establishes causal validity, or certifies any explainer.

The unit is one matched `clean ExplanationContract ↔ corrupt ExplanationContract` pair. The clean contract binds run/model artifact SHA, preprocessing identity, sample/target identity, explainer method, and train-reference/background declaration. A corrupt contract is derived with one deterministic declared mutation and a mutation receipt; it never mutates the clean object in place.

Families are CLEAN; M1 model mismatch; P1 preprocessing mismatch; S1 sample/target mismatch; R1 reference/background mismatch; A1 attribution mutation; L1 low fidelity; and ADV explainer-aware attribution failure. R1 is `NOT_APPLICABLE` when the selected explainer has no background/reference concept. Applicability outcomes are PASS, FAIL, NOT_APPLICABLE, NOT_AVAILABLE, and INVALID_INPUT; absent capability is never silently counted as a miss.

The subject is product-native RuFLEX: `ExplanationContract`, `check_explanation` / `ExplanationCheck`, persisted evidence, replay/additivity checks, reproducibility analysis, lineage, assurance and verification bundle. Research code orchestrates, mutates copies, locks specifications, and compares the product output to a hidden oracle. It does not implement a shadow RuFLEX detector.

Validator ablation is IDENTITY_ONLY, METRIC_ONLY, and COMBINED. Identity-only is limited to available product provenance checks. Metric-only is limited to available native replay/additivity metrics and an explicitly scoped Quantus external metric baseline where a counterpart is valid. Combined reports both. `PASSED_AVAILABLE_CHECKS` never means universally correct, causal, or certified.

The frozen matrix uses three reproducible tabular datasets, five model classes, only compatible native explainer routes, eight deterministic samples per dataset/model, the declared failure taxonomy, validator mode, and repeat identity. Training/split materialization is separate from A01: S03 uses split seed 3003. Sample selection is stratified deterministic selection before any explanation-quality outcome is observed.

Future outcomes: detection rate = detected corrupt / applicable corrupt; clean false rejection = rejected clean / applicable clean; coverage; correct failure localization; reopen/replay agreement; and runtime. Quantitative A1/L1/ADV severity is fixed at LOW=.05, MEDIUM=.25, HIGH=.75. No severity or explainer will be adjusted after observations.

Before any S03 execution, the fail-closed validator must confirm hashes, complete deterministic matrix, required fields, and that no benchmark result artifact exists. A synthetic native-product smoke route is permitted but is explicitly non-evidence. Benchmark execution requires a later frozen authorization; this Phase 0 protocol has no empirical detection result.
