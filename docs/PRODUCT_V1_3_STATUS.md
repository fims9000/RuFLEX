# RuFLEX Product V1.3 Alpha status

Target branch: `feature/v1.3-data-governance-runtime`.

## Implemented in the current development baseline

- persisted `SplitContract` evidence for random, group, temporal and declared
  identity/holdout split families;
- persisted train-only `TransformPipelineContract`, including categorical
  treatment and preprocessing identity;
- persisted leakage-audit evidence and declared rigor profiles, surfaced
  through the Studio/API, reopen checks, Lineage, Assurance and verification
  bundles;
- unified runtime identities for model, explainer, validator and execution
  backend components, with a frozen startup snapshot and typed capability
  errors;
- generic adapter-routed training, evidence and final-test replay without
  lifecycle model-kind dispatch;
- persisted execution backend provenance and a complete
  `submit`/`is_active`/`status`/cooperative-`cancel`/`resume` lifecycle
  boundary, including Studio selection and immutable `StudyJob` backend
  identity;
- governed external-runtime golden-route coverage, including project reopen,
  lineage, Assurance and portable verification evidence;
- persisted behavior-revision comparison evidence and read-only Studio
  presentation;
- explicit Studio protocol text for training-, split- and combined-variability
  Stability Lab modes.
- revision-bound BehaviorSpec failure counterexamples and schema-versioned,
  persisted exact FIS computation traces, inspectable after project reopen;
  portable bundles check trace bindings but do not independently replay inference.

## Boundaries

V1.3 Alpha is a product/runtime development baseline, not a stable release or
a new research conclusion.
The core keeps TEST closed until a pre-existing frozen policy is applied. A
runtime adapter receives bounded requests; it cannot choose policies, alter
split roles or own project persistence. The platform makes evidence
inspectable; it does not prove causal explanations, universal leakage
prevention, generalization or deployment safety.

## Historical release records

`docs/PRODUCT_V1_2_STATUS.md` records the earlier V1.2 RC1 target and must be
read as historical provenance, not as the active branch status. Frozen research
protocols and results remain under `research/` and are not rewritten by this
product-runtime work.
