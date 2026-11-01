# Data → model workflow acceptance — 2026-11-01

The Data screen now offers **Next: choose a model**. It persists the declared
target/task/roles through the existing guarded CSV or file-import route, then
opens native model selection. It never starts training or opens the final test.
CSV schema preview runs automatically after a 450 ms editing pause; preview is
read-only. The existing explicit save/import controls remain available.

Repeated continuation of an unchanged saved dataset does not write it again.
Synchronous duplicate clicks share the existing mutation mutex. Failed target
validation stays on Data and can be corrected. A saved/imported file is never
silently replaced with the default CSV-editor example when only its roles/task
change: the user is asked to reselect the source file or paste replacement data.
Previews are invalidated before persistence and stale project continuations are
discarded. No scientific backend, frozen policy or research result was changed.

## Verification

Serial browser runs with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`:

- `VITE_RUFLEX_UI_LANG=ru npx playwright test e2e/data-next-step.spec.ts e2e/model-user-matrix.spec.ts --reporter=line --max-failures=1`: **18 passed**.
- Final `data-next-step.spec.ts` follow-up: **4 passed**, including the added
  saved-file/default-editor source guard. Nineteen unique scenarios across the
  two runs; the final four were rechecked after the guard was added.
- The matrix exercises real binary/regression fits, explanations, explicit
  final evaluation and reopen for all six supported native model families;
  CSV regression now uses the new continuation action, not separate import-save
  plus navigation. XLSX, practice replacement and same-project source switching
  remain covered. Only synthetic fixtures were used.
- `npm test -- --run`: **130 Vitest and 1 API-client test passed**.
- `npm run build`: TypeScript/Vite PASS; existing chunk-size advisory retained.
- `git diff --check`: PASS.

## Main integration verification

The current main branch is named `master`, not `main`. Historical main commits
were merged without changing their frozen research files; README conflicts were
resolved by preserving the V1.3 product description alongside the historical
V1.0.1/A01 reference. Backup refs preserve both pre-integration heads.
Uncommitted article files and R8 research work were not staged.

The merged-state configured Python product suite passed: **440 tests**, with
the repository's existing `--ignore=tests/upstream`. The 46 legacy upstream
tests are outside that configured suite, not silently claimed as executed.
Compileall passed. The prior workflow receipt's unrestricted collection count
was corrected to distinguish collection from execution.

Merged-state regression: `npx playwright test e2e/dataset-xlsx-import.spec.ts
e2e/project-lifecycle.spec.ts e2e/training-evaluate.spec.ts --reporter=line
--max-failures=1` with one worker: **33 passed**. It includes stale preview
invalidation, role isolation, rejected-file preservation, read-only/reopen,
uncertain-write serialization and final-test-state error recovery. Combined
with the Russian routes above, this task verified **52 unique browser scenarios**.

An initial new test fixture omitted the required project name; the UI correctly
refused to create it. The fixture was corrected, not the product validation.
Low-budget MLP convergence and approximate GradientSHAP warnings remain honest
warnings, not claims of model quality. This is a workflow acceptance run, not
the full repository browser suite. Previous broad model evidence is recorded in
[ALPHA_MODEL_USER_WORKFLOW.md](ALPHA_MODEL_USER_WORKFLOW.md).
