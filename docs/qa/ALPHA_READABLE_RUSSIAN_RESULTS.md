# Readable Russian analysis and checks — 2026-11-01

## Reported errors

The user's existing three-row project was inspected read-only. Its failed
Decision Tree StudyJob was created at `2026-11-01T18:06:30Z`; all three stored
errors were the old generic adapter-unavailable message. The original exception
was not persisted, so its exact cause cannot be recovered from that receipt.
The job and user dataset were not rewritten or rerun.

Native regression tests now explicitly run a three-seed Decision Tree Study on
synthetic three-row and 80-row datasets. The tiny case retains three specific
`TRAIN_REQUIRES_BOTH_BINARY_CLASSES` failures and creates no fitted model. The
80-row case produces three successful frozen runs. Historical generic errors
are not presented as evidence that the current Decision Tree adapter is absent.

## Presentation changes

- Russian StudyJob view gives one saved-result summary, successful-run count,
  and Data action; original job/per-seed errors remain in closed technical
  details. No scientific failure evidence is deleted or turned into PASS.
- Final-test copy explains the held-out check and the no-retuning rule in plain
  Russian. The explicit confirmation, frozen-threshold requirement, scope,
  recovery, read-only and backend boundary checks are unchanged.
- Slice labels, target/metric columns, missing-bound messages, state labels and
  calculation details are localized. Invalid inputs still produce no slice.
- Generated files, SHA-256 values, runtime/validator keys, model references and
  evaluation identifiers are kept in technical details, not the primary view.
- Explanation charts add a short largest-contribution description and explicitly
  distinguish contribution magnitude from accuracy and causality.
- Behavior checks show the observed output, declared bounds, a scale marker and
  the native PASS/FAIL meaning in Russian. A failed case remains visible with
  its input, expected condition and observed output. This is one evaluated
  requirement/input, not a universal model-quality or safety guarantee.
- Duplicate saved-specification and version-comparison cards are collapsed;
  additional engineering inspection tools remain accessible separately.
- Existing English-language automation stays available via `VITE_RUFLEX_UI_LANG=en`.
  User-provided names/data are not translated, and original backend audit text
  and canonical identifiers remain unchanged in technical inspection details.

No new dependency, scientific algorithm, persisted migration, model fit on user
data, frozen A01/S03 change or automatic final-test access was introduced.

## Verification

Commands use one browser worker and `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
MKL_NUM_THREADS=1`; native fits run serially on small synthetic fixtures.

- `pytest -q tests/test_training_input_preflight.py tests/test_runtime_model_adapter_matrix.py tests/test_runtime_explainer_matrix.py`: **25 passed**.
- `npm test -- --run`: **134 Vitest + 1 API-client passed**.
- `npm run build`: TypeScript/Vite PASS; existing large-chunk advisory retained.
- Russian `readable-russian-workflow.spec.ts` + `practice-project-full-route.spec.ts`: **3 passed** after final layout changes. Includes native training, validation, blank-range correction, explanation chart, passing/failing requirements, explicit fixture final test, reopen, dark theme, and an explicitly mocked historical-job presentation fixture.
- English `behavior-fis-trace.spec.ts` + `training-evaluate.spec.ts` + `project-lifecycle.spec.ts`: **31 passed**; exact FIS/negative/recovery cases were separately rerun after their presentation update: **4 passed** (included in the 31 unique scenarios).
- `git diff --check`: PASS.

The configured full Python suite was not rerun for this frontend-only production
change; the focused native training/explainer suite was run instead. This is not
a claim that every browser test or every arbitrary backend/plugin message is
localized or was tested. One early browser run ended with a closed runner channel;
a new test also initially used an incorrect action selector. Final corrected
commands above passed without skipping or weakening behavior assertions.

Actual Russian browser screenshot, inspected after layout correction:
[Readable range result](screenshots/readable-russian/behavior-range.png).
