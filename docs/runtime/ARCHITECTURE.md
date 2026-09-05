# V1.2 unified runtime architecture

RuFLEX remains a single local-first product. The runtime layer separates
canonical scientific/product evidence from replaceable computation adapters.

## Core-owned invariants

The core owns `DatasetContract`, TRAIN/VALIDATION/TEST role separation,
train-only preprocessing, artifact hashing, `TrainingRun`, `TrainingStudy`,
evaluation, explanation, policy, lineage and bundle persistence. An adapter is
never handed final-test data or a project root and cannot select a policy.

## Runtime-owned computation

Trusted model adapters implement bounded `fit(FitRequest)` and
`predict(PredictionRequest)` calls. Explainer adapters implement
`supports(run_capabilities, task, artifact)` and `explain(ExplainerRequest)`;
validator adapters return a typed `ValidatorResult`; execution backend adapters
provide `submit`, `is_active`, `status`, cooperative `cancel`, and `resume`
over persisted work. The core saves
`FitResult` bytes through `ArtifactStore`, computes canonical validation
evidence, and binds resulting objects to immutable `RuntimeIdentity` (`key`,
`version`, `provider`, `kind`).

Runtime startup registers built-ins and validates installed category-specific
entry points (`ruflex.plugins`/`ruflex.model_adapters`, `ruflex.explainers`,
`ruflex.validators`, and `ruflex.execution_backends`) before freezing one
deterministic snapshot containing models, explainers, validators and execution
backends. Missing optional
runtimes affect replay operations only; inspectability of persisted projects is
preserved. The public runtime catalog is read-only and never executes uploaded
or arbitrary Python code.

## Evidence routes

Explainer identities are persisted on new `ExplanationContract` records and
validator identities on new `ExplanationCheck` records. New evidence jobs and
study jobs also record the canonical execution backend identity. Capability
negotiation is run-bound: persisted adapter identity, runtime availability,
task and artifact determine whether an action is available. Availability is
neither a quality nor a causal-validity claim.
