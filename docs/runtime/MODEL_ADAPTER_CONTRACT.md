# Model adapter contract

`FitRequest` contains only core-prepared TRAIN/VALIDATION arrays, feature names,
split identity/seeds, validated parameters and preprocessing identity. It has no
test partition or project persistence handle.

`FitResult` returns serialized model bytes, media type, model specification,
training summary/trajectory and raw validation predictions (with optional
classification probabilities). The core owns artifact persistence, canonical
metrics, prediction evidence and `TrainingRun` construction.

`PredictionResult` distinguishes `prediction`, `score`, `probability` and
`raw_score`. Regression adapters must not label a numerical prediction as a
probability.

New adapters must declare immutable `ModelAdapterDescriptor` metadata and are
included automatically in the registry-driven adapter matrix when available.
