# Stability Lab RC2 source-release QA

Status: PASS.

## Source subject

- Source QA HEAD before this receipt-only update: `daf9842ea65b4b1da502a8a520fd55f5c34b9094`.
- Direct Stability Lab parent commits: `0331ab3 Add Stability Lab and split seed provenance`; `5a758c0 Add A01 stability review pre-freeze plan`.
- Hardening commit: `1d45b28 Harden Stability Lab evidence and review gate`.
- Visual baseline refresh: `e45c6ea Refresh verified Studio visual baselines`.
- Scientific-correctness hotfix: `daf9842 Correct Stability Gate agreement and threshold provenance`.
- A01: `PRE-FREEZE`; final test has not been accessed by A01.

## Checks executed from the local source checkout

| Check | Command | Result |
| --- | --- | --- |
| Python suite | `PYTHONPATH=src /home/lebedeffson/Code/venv/bin/python -m pytest -q` | PASS — 129 collected tests |
| Python compilation | `PYTHONPATH=src /home/lebedeffson/Code/venv/bin/python -m compileall -q src/ruflex` | PASS |
| Focused Stability/Lineage/Evidence | `pytest -q tests/test_stability_lab.py tests/test_training_product_route.py tests/test_lineage_product_route.py tests/test_evidence_product_route.py` | PASS — 34 tests |
| A01 design validator | `python research/a01_stability_aware_review/validate_pre_freeze.py` | PASS — no final-test access |
| Frontend unit | `cd frontend && npm run test -- --run` | PASS — 1 test |
| Production Studio build | `cd frontend && npm run build` | PASS |
| Storybook build | `cd frontend && npm run build-storybook` | PASS |
| Full Playwright | `cd frontend && PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers npx playwright test --reporter=line` | PASS — 25 tests |
| Visual regression | `e2e/visual-foundation.spec.ts` | PASS — 2 tests after a verified four-image glyph-raster baseline refresh; no layout/content change |
| FIS Workbench route | `e2e/product-golden-route.spec.ts` | PASS — 1 test, create/edit/save/run trace/close/reopen |
| Stability Lab route | `e2e/stability-lab.spec.ts` | PASS — 1 test, fixed split → raw threshold-bound analysis → frozen gate → close/reopen |
| Diff integrity | `git diff --check` | PASS |

## RC2 correctness coverage

- `majority_class_agreement` and `selected_run_agreement` are persisted separately. HCIR and `RUN_DISAGREEMENT` use only selected-run agreement.
- The regression fixture has 20 frozen runs where the selected run predicts class 1 at 0.90 while 19 predict class 0 at 0.49: majority consensus is 0.95, selected-run agreement is 0.05, and the policy returns `REVIEW` with `RUN_DISAGREEMENT`.
- Operational gate labels use an exact raw validation-derived `DecisionThresholdPolicy`, not a hidden `0.5`; a non-0.5 regression fixture verifies this.
- Final-test evaluation can only apply the exact frozen gate/threshold pair and persists per-case frozen-run evidence plus accepted coverage/error/FN metrics and a matched-coverage confidence-only comparator. It performs no fitting.
- HCIR is `N/A` when no validation case meets the pre-specified high-confidence criterion.

## Archive smoke

The tracked-source ZIP is created with `git archive --format=zip HEAD -o release/RuFLEX_STABILITY_LAB_RC2_SOURCE.zip`, unpacked to a new temporary directory with no `.git` and no inherited `frontend/node_modules`, then verified there. The exact smoke outcomes and archive SHA-256 are reported with the delivery artifact; embedding the checksum in this tracked file would alter the archive byte stream.

- The archive verification is intentionally performed after this receipt is committed, so its commands exercise the exact delivery HEAD. The final checksum is reported alongside the delivery artifact rather than embedded in this tracked receipt, because embedding it would change the archived byte stream.

## Known limitations

- Cross-run gate probabilities are deliberately raw only. Calibrated cross-run aggregation is not silently substituted and is not yet implemented.
- The stability gate operationally requires every frozen study run to produce a probability for the case. Partial-support application is rejected rather than represented as a complete gate decision.
- Case-level agreement and HCIR are deliberately `NOT_APPLICABLE` for split/combined/legacy variability modes unless a separately declared alignment protocol exists.
- A01 is a pre-freeze plan, not an experimental result. RuFLEX therefore makes cross-run variability measurable; it does not claim to solve underspecification, guarantee stability, or establish risk reduction before A01 is executed.
