# Teaching datasets, SHAP discovery and saved-object history

Scope: Studio presentation/orchestration only. Scientific implementations, persisted schemas, frozen research and user datasets are unchanged.

Working branch: `feature/v1.3-data-governance-runtime`; implementation based on `3644197fde0f72db3c2a98404a25e830b39a96ac`. Existing unrelated article changes and user project `1/` are preserved. No push is part of this task.

## Delivered

- Three deterministic synthetic fixtures: soil settlement (144 rows, 9 features), equipment condition (160 rows, 10 features), building energy (128 rows, 8 features). Explicit targets/tasks/ID roles pass through the normal DatasetContract workflow. Exact registered source hashes preserve the synthetic label after reopen; unknown/changed uploads do not acquire that label.
- These are teaching data, not field observations, engineering validation or empirical research evidence. Soil settlement is an illustrative formula, not a geotechnical calculation.
- Three existing native SHAP routes are discoverable: permutation SHAP, TreeSHAP and GradientSHAP. Model compatibility remains authoritative; unavailable methods are disabled, not substituted. A saved chart from another method is explicitly identified.
- Classification probability histograms and regression actual-versus-predicted scatterplots use persisted validation evidence. Before evaluation is saved, the limited run preview is explicitly labeled. No final-test access is introduced.
- History offers a readable Russian object list and relationship graph. Opening run-bound evidence loads its exact saved model/evaluation context; opening an older result does not train, mutate policies or change the persisted latest-run pointer. Referenced-object read failures remain visible and retryable. Preprocessing metadata is inspected without pretending to open an unrelated workspace.

## Verification

- `npm run build`: TypeScript/Vite PASS; existing large-chunk warning remains.
- `npm test -- --run`: 138 Vitest tests and 1 API-client test PASS.
- `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python -m pytest tests/test_lineage_product_route.py tests/test_runtime_explainer_matrix.py -q`: 6 PASS; existing SHAP colormap deprecation warnings.
- Russian native browser routes: 5/5 PASS (three new datasets, all three SHAP methods, exact historical-model restore, failed-read retry, graph/list switching, close/reopen, and the existing synthetic practice route).
- Adjacent browser regressions: `project-lifecycle.spec.ts training-evaluate.spec.ts stability-lab.spec.ts synthetic-practice-route.spec.ts`: 30/30 PASS (1.3 minutes), including Assurance/VerificationBundle, saved policies, training/validation reopen, tree preprocessing and final-test mutation boundaries.
- `python -m compileall -q src/ruflex`: PASS.
- `git diff --check`: PASS.

Runs are serial with single-thread numerical libraries. No A01/S03 experiment is executed. Screenshots are real browser captures under `docs/qa/screenshots/dataset-library/`.

Regression-test correction: the existing Stability Lab browser test explicitly expected history to open a gate with a mismatched current run/evaluation. Restoring the gate's exact saved chain intentionally removes that defect. The assertion now requires the active validation-derived gate, no mismatch warning, and no additional gate creation. The separate negative unit test still verifies that genuinely mismatched gates are rejected. An initial browser batch was interrupted by development-server reload during source editing; the clean-source rerun exposed this obsolete assertion rather than a native scientific failure.

## Limits

The library contains synthetic fixtures only. Real engineering datasets require an authorized source and their own provenance. SHAP methods have different native compatibility and computational cost. This task does not claim every model accepts every explanation method, or that replay establishes causal validity. Full research suites and full browser suites are not claimed by this scoped receipt.
