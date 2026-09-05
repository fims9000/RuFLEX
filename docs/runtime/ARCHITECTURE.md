# V1.2 unified runtime architecture

RuFLEX remains a single local-first product. The runtime layer separates
canonical scientific/product evidence from replaceable computation adapters.

## Core-owned invariants

The core owns `DatasetContract`, TRAIN/VALIDATION/TEST role separation,
train-only preprocessing, artifact hashing, `TrainingRun`, `TrainingStudy`,
evaluation, explanation, policy, lineage and bundle persistence. An adapter is
never handed final-test data or a project root and cannot select a policy.

## Runtime-owned computation

Trusted adapters implement bounded `fit(FitRequest)` and
`predict(PredictionRequest)` calls. The core saves `FitResult` bytes through
`ArtifactStore`, computes canonical validation evidence, and binds resulting
objects to immutable `RuntimeIdentity` (`key`, `version`, `provider`, `kind`).

Runtime startup registers built-ins, validates installed `ruflex.plugins`
entry-points, then freezes a deterministic snapshot hash. Missing optional
runtimes affect replay operations only; inspectability of persisted projects is
preserved.

## Evidence routes

Explainer identities are persisted on new `ExplanationContract` records and
validator identities on new `ExplanationCheck` records. Capability negotiation
is run-bound: persisted adapter identity, runtime availability, task and
artifact determine whether an action is available. Availability is neither a
quality nor a causal-validity claim.
