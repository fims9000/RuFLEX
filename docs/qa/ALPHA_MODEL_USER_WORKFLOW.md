# Studio model workflow acceptance — 2026-11-01

Scope: use the built-in practice data, choose a supported model, train, inspect
validation evidence and explanation charts, explicitly evaluate the final test,
close/reopen, then import a user's CSV/XLSX without mixing previous results.
All generated evidence is synthetic product QA, not A01/S03 empirical evidence.

## Defects corrected

- The reported Decision Tree adapter error was actually an invalid TRAIN split:
  the three-row editor example yields only one TRAIN class. All native binary
  adapters now reject this before fitting, with a specific data error. Invalid
  binary labels are not silently cast. Splits are never automatically changed.
- Training errors preserve their cause; filesystem errors retain their category.
- An already saved three-row example can explicitly load an 80-row practice
  draft, inspect it and confirm it. Loading a draft does not overwrite data.
- The model selector and primary training action stay visible. Optional training,
  experiment, capability and provenance details are collapsed. Saved metrics
  identify the actual fitted model rather than the newly selected model.
- Final-test status must be known and closed before fitting. Opened, loading and
  error states disable fitting; errors expose retry. The backend remains the
  authoritative final-test boundary.
- After replacing practice data with another dataset, old validation, threshold,
  calibration and final-test tree entries move to collapsed previous-results
  history. Persisted evidence is retained, not overwritten or relabeled.
- Training provides direct Analysis/Explain navigation. Action buttons retain
  readable contrast in both themes without Gravity theme-token overrides.

## Native model matrix

The machine receipt [ALPHA_MODEL_USER_WORKFLOW_MATRIX.json](ALPHA_MODEL_USER_WORKFLOW_MATRIX.json)
preserves twelve run/model hashes, metrics, explanation checks and reopen results.
Binary classification uses Logistic Regression, Decision Tree, Random Forest,
Gradient Boosting, MLP and Flat Neuro-Fuzzy. Regression uses Linear Regression
and the same other five families. All twelve routes use actual product training,
validation, explanation generation/checking, explicit final evaluation and reopen.

Every route checks Occlusion. Classification additionally checks SHAP for
Logistic Regression/Random Forest/MLP, TreeSHAP for Decision Tree/Gradient
Boosting, and Integrated Gradients/GradientSHAP for Flat Neuro-Fuzzy.
Nineteen explanation checks: eighteen passed available checks; GradientSHAP
retained a numerical completeness WARNING, not a fabricated PASS.

CSV regression includes categorical values, missing values, an explicit ID and
an excluded column. XLSX classification checks import, roles, native fit and
reopen. Another route completes the practice final test, imports a different
user dataset in the same project and verifies a new dataset-bound result while
the previous model artifact remains unchanged.

## Checks

Run serially with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`.
No parallel model fits, new dependencies, benchmark fits or user-project edits.

- `.venv/bin/python -m pytest -q`: **484 passed**, full Python suite.
- Focused training/input/model/explainer checks: **45 passed**, also in full suite.
- `python -m compileall -q src/ruflex tests/test_training_input_preflight.py tests/test_training_runtime_error_identity.py`: PASS.
- `cd frontend && npm test -- --run`: **130 Vitest + 1 API-client passed**.
- `cd frontend && npm run build`: TypeScript and Vite PASS.
- Russian Playwright model/practice/navigation acceptance: **17 passed**.
- English workflow regression: **53 unique scenarios passed** (51 in the broader
  run, two in a targeted follow-up after correcting disclosure locators and
  preparing the final-boundary fixture before injecting read errors).
- Final Explorer change: user-file transition and binary Logistic Regression
  routes rechecked: **2 passed**; frontend unit/build rerun and passed.
- `git diff --check`: PASS.

The 70 unique browser scenarios include FIS editing/import/inference/reopen,
dataset import, native MLP, Study recovery/randomness, Stability Lab and
final-test negative paths. This is **not** a claim that the entire repository
Playwright suite was run. Raw local Playwright JSON reports remain under ignored
`release/qa/`; the compact native run receipt is tracked above.

## Screenshots

Actual Russian browser captures, not mockups:

- [Model choice and compact training](screenshots/model-matrix/trained-logistic_regression.png)
- [MLP](screenshots/model-matrix/trained-mlp.png)
- [Neuro-fuzzy model](screenshots/model-matrix/trained-flat_neuro_fuzzy.png)
- [Imported XLSX](screenshots/model-matrix/uploaded-xlsx.png)
- [Practice to own CSV, previous analyses collapsed](screenshots/model-matrix/practice-to-own-csv.png)
- [Explanation chart](screenshots/practice-03-explanation.png)
- [Dark explanation view](screenshots/practice-05-explanation-dark.png)

## Boundaries

Short synthetic fits test mechanics, not model quality. MLP convergence warnings
are expected at the deliberately small smoke budget. GradientSHAP completeness
reported a difference of 0.135355 against the existing 0.05 tolerance; the warning
is visible and no scientific threshold or algorithm was retuned. Vite retains
its existing large-bundle advisory. Arbitrary third-party estimators/file formats
are not promised. The legacy product-evidence capture route was not rerun here.
Frozen research artifacts and unrelated article edits were left untouched.
No push, merge or release was performed.
