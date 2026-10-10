# Exact Decision Tree input and preprocessing integrity

The Studio previously converted a cleared tree feature field to zero because JavaScript evaluates `Number("")` as `0`. It could therefore persist an exact path for a sample the user had not supplied. The control now marks a blank/non-finite feature invalid, disables tracing, and submits no request until the value is corrected. The Python service independently rejects non-finite input before any tree-path evidence is written.

The tree-path service also previously replayed only standard scaling. For runs frozen with min–max scaling, it traversed the trained tree using raw values while labelling the result an exact path. It now reconstructs the persisted `NormalizationArtifact`, verifies frozen feature order, and transforms the supplied numeric vector before traversal. Tests compare the traced class probability to independent persisted-model inference under none, standard, and min–max scaling, then reopen the trace.

The tree-path API accepts numeric feature coordinates. For a categorical feature, the Studio now presents category choices from the exact run-bound TRAIN-frozen `OrdinalEncoder` and submits the corresponding numeric code. Until that transform is successfully reopened, categorical tracing is disabled rather than guessing an encoding. Persisted `input_sample` records numeric model coordinates, not the category label; API callers must supply those coordinates explicitly.

Studio also rejects a reopened `TransformPipelineContract` if its preprocessing-artifact SHA differs from the selected run, even when its pipeline ID and dataset fingerprint match. This prevents a category selector from borrowing a different run's codebook.
