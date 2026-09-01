# Stability Lab RC1 source-release QA

Status: PASS.

## Source subject

- Source QA HEAD before this receipt-only update: `a006ade83194f27b7f84604f7d8350bbcf652da4`.
- Direct Stability Lab parent commits: `0331ab3 Add Stability Lab and split seed provenance`; `5a758c0 Add A01 stability review pre-freeze plan`.
- Hardening commit: `1d45b28 Harden Stability Lab evidence and review gate`.
- Visual baseline refresh: `e45c6ea Refresh verified Studio visual baselines`.
- A01: `PRE-FREEZE`; final test has not been accessed by A01.

## Checks executed from the local source checkout

| Check | Command | Result |
| --- | --- | --- |
| Python suite | `PYTHONPATH=src /home/lebedeffson/Code/venv/bin/python -m pytest -q` | PASS — 126 collected tests |
| Python compilation | `PYTHONPATH=src /home/lebedeffson/Code/venv/bin/python -m compileall -q src/ruflex` | PASS |
| Focused Stability/Lineage/Evidence | `pytest -q tests/test_stability_lab.py tests/test_training_product_route.py tests/test_lineage_product_route.py tests/test_evidence_product_route.py` | PASS — 31 tests |
| A01 design validator | `python research/a01_stability_aware_review/validate_pre_freeze.py` | PASS — no final-test access |
| Frontend unit | `cd frontend && npm run test -- --run` | PASS — 1 test |
| Production Studio build | `cd frontend && npm run build` | PASS |
| Storybook build | `cd frontend && npm run build-storybook` | PASS |
| Full Playwright | `cd frontend && PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers npx playwright test --reporter=line` | PASS — 25 tests |
| Visual regression | `e2e/visual-foundation.spec.ts` | PASS — 2 tests after a verified four-image glyph-raster baseline refresh; no layout/content change |
| FIS Workbench route | `e2e/product-golden-route.spec.ts` | PASS — 1 test, create/edit/save/run trace/close/reopen |
| Stability Lab route | `e2e/stability-lab.spec.ts` | PASS — 1 test, fixed split → analysis → frozen gate → close/reopen |
| Diff integrity | `git diff --check` | PASS |

## Archive smoke

The tracked-source ZIP was created with `git archive --format=zip HEAD -o release/RuFLEX_STABILITY_LAB_RC1_SOURCE.zip`, unpacked to a new temporary directory with no `.git` and no inherited `frontend/node_modules`, then verified there.

- `PYTHONPATH=src /home/lebedeffson/Code/venv/bin/python -m pytest -q tests/test_stability_lab.py`: PASS — 4 tests.
- `npm ci`: PASS — 260 packages, 0 vulnerabilities. The package manager reported the existing blocked `esbuild` postinstall policy; the subsequent production build passed.
- `npm run build`: PASS.
- With an explicit external `RUFLEX_PYTHON=/home/lebedeffson/Code/venv/bin/python` and the project-local browser cache, `e2e/product-golden-route.spec.ts`: PASS and `e2e/stability-lab.spec.ts`: PASS. They were run separately because an initial combined archive invocation produced a transient UI-server timeout; each focused real browser route then passed from the same clean extraction.

The final delivery checksum is reported alongside the final archive artifact. It is intentionally not embedded into this tracked source receipt because the receipt itself changes the `git archive HEAD` byte stream.

## Known limitations

- Cross-run gate probabilities are deliberately raw only. Calibrated cross-run aggregation is not silently substituted and is not yet implemented.
- Case-level agreement and HCIR are deliberately `NOT_APPLICABLE` for split/combined/legacy variability modes unless a separately declared alignment protocol exists.
- A01 is a pre-freeze plan, not an experimental result. RuFLEX therefore makes cross-run variability measurable; it does not claim to solve underspecification, guarantee stability, or establish risk reduction before A01 is executed.
