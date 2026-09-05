# RuFLEX V1.2 baseline receipt

Baseline source revision: `835690351272a18d9b74f9967367b2420b30f85d` (RuFLEX V1.1 RC).
Target branch: `feature/v1.2-unified-runtime`. This receipt records the
pre-migration state; it is not a V1.2 release claim.

## Environment

- Python: `3.14.7` (`/home/lebedeffson/Code/venv/bin/python`)
- Node: `v26.7.0`
- npm: `12.0.2`
- Worktree: `/home/lebedeffson/Code/ruflex-v1.2`

## Checks

| Check | Result | Evidence |
| --- | --- | --- |
| Python regression suite | PASS in bounded groups (224 tests) | V1.1 product, evidence, stability, lifecycle and SDK groups reached 100% before the first V1.2 patch. |
| Python compilation | PASS | `python -m compileall -q src/ruflex` with the declared project Python. |
| Frontend unit | PASS | `npm test -- --run`: 1/1. |
| Vite production build | PASS | `npm run build`. |
| Storybook production build | PASS | `npm run build-storybook`. |
| Fresh isolated Python dependency installation | INCONCLUSIVE | The fresh `.venv` install was interrupted during large optional Torch/CUDA downloads; it was not substituted for the project runtime verification. |
| Full Playwright baseline | PENDING V1.2 release gate | Must be run against the exact final commit, not inferred from this receipt. |

The only observed frontend warning was the existing large-chunk warning; it is
not treated as a failed build or as permission for an unreviewed UI rewrite.

## Isolation

The source worktree carried pre-existing user changes under `docs/article/`.
They are deliberately neither staged nor included in V1.2 commits. Frozen
research result directories are outside the V1.2 change scope.
