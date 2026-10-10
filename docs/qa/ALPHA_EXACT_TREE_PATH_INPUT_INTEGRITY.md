# Exact Decision Tree input and preprocessing integrity

The Studio previously converted a cleared tree feature field to zero because JavaScript evaluates `Number("")` as `0`. It could therefore persist an exact path for a sample the user had not supplied. The control now marks a blank/non-finite feature invalid, disables tracing, and submits no request until the value is corrected. The Python service independently rejects non-finite input before any tree-path evidence is written.

The tree-path service also previously replayed only standard scaling. For runs frozen with min–max scaling, it traversed the trained tree using raw values while labelling the result an exact path. It now reconstructs the persisted `NormalizationArtifact`, verifies frozen feature order, and transforms the supplied numeric vector before traversal. Tests compare the traced class probability to independent persisted-model inference under none, standard, and min–max scaling, then reopen the trace.

The current tree-path API accepts numeric feature coordinates. For a categorical feature, those coordinates must already be the train-frozen ordinal code; the Studio does not yet offer a raw category-to-code input control. Do not describe manual categorical raw-value tracing as supported by this control.
