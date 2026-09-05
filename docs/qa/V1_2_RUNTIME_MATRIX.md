# V1.2 runtime compatibility matrices

The V1.2 test suite derives these matrices from the frozen runtime registry.
They are compatibility evidence for a local product installation, not quality,
safety, calibration, causal-validity, or benchmark claims.

## Model adapter matrix

`tests/test_runtime_model_adapter_matrix.py` enumerates every registered model
adapter that declares both `available` and `fit`, across every declared task.
For each pair it verifies core-owned training, artifact validation, adapter
prediction, read-only project reopen and exact persisted runtime binding.

At RC1 this is 12 available adapter/task pairs: Flat Neuro-Fuzzy (2), linear
(2), Decision Tree (2), Random Forest (2), and Gradient Boosting (2).
Adding a compatible registered model adapter automatically adds its declared
pairs to the matrix.

## Explainer compatibility matrix

`tests/test_runtime_explainer_matrix.py` creates persisted runs for the five
built-in binary-classification model kinds and evaluates all 25 combinations
with the five registered explainers. Capability declarations are the source of
truth:

- 15 available pairs create, persist, reopen and validate an
  `ExplanationContract`;
- 10 unavailable pairs reject through the typed capability boundary;
- no generic SHAP fallback is substituted for TreeSHAP;
- a decision-tree structural path remains separate from post-hoc explanation.

The matrix is deliberately run-bound. A descriptor appearing in the runtime
catalog does not make an explainer applicable to every artifact.

## Studio and accessibility gates

`frontend/e2e/action-inventory.spec.ts` compares every source
`data-ruflex-action` attribute to the versioned inventory, so a new declared
primary action without inventory coverage fails the browser gate.

`frontend/e2e/accessibility-baseline.spec.ts` runs axe against Project, Data,
Training/Stability Lab, Evaluation and Evidence/Assurance/Bundle workspaces,
failing on detected `critical` or `serious` violations. It is an accessibility
baseline, not a WCAG certification.
