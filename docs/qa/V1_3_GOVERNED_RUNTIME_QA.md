# V1.3 governed-runtime QA receipt

This receipt records the local verification state of the governed runtime
development baseline. It is not a release tag or a claim of research validity.

## Exact-source procedure

The archive is created after this tracked receipt with
`git archive --format=zip HEAD`. The corresponding local release receipt
records the exact `HEAD` and SHA-256 alongside the generated archive. It
contains only tracked source; it has neither `.git` nor `frontend/node_modules`.

## Checks

| Scope | Command | Outcome |
| --- | --- | --- |
| Python product suite | `PYTHONPATH=src /home/lebedeffson/Code/venv/bin/python -m pytest -q -p no:cacheprovider` | PASS, reached 100% (285 collected tests) |
| Focused runtime/evidence | `pytest -q tests/test_evidence_product_route.py tests/test_runtime_registry.py tests/test_runtime_generic_training.py` | PASS, 46 tests |
| Python bytecode | `/home/lebedeffson/Code/venv/bin/python -m compileall -q src` | PASS |
| Frontend client and components | `cd frontend && npm run test` | PASS: API client 1; Vitest 6 |
| Production Studio build | `cd frontend && npm run build` | PASS |
| Storybook production build | `cd frontend && npm run build-storybook` | PASS |
| Browser acceptance | `cd frontend && npx playwright test` | PASS, 28 serial tests |
| Source diff hygiene | `git diff --check` | PASS |
| Fresh archive Python | extracted archive: focused runtime/evidence tests and `compileall` | PASS, 46 focused tests |
| Fresh archive frontend | extracted archive: `npm ci`, `npm run test`, `npm run build` | PASS |
| Fresh archive browser | extracted archive: `RUFLEX_PYTHON=/home/lebedeffson/Code/venv/bin/python PLAYWRIGHT_BROWSERS_PATH=/home/lebedeffson/Code/ruflex-v1.2/.playwright-browsers npx playwright test e2e/project-lifecycle.spec.ts --grep E2E-06` | PASS, 1 Studio route |

The archive browser command explicitly supplies the declared RuFLEX Python
environment and project-local browser cache. The archive intentionally does
not embed a virtual environment or browser binary cache.

## Scope and limitations

- Runtime selection is persisted for model adapters, explainers, validators and
  execution backends; an external component remains subject to the trusted
  plugin boundary and its declared capability contract.
- The frontend build emits a chunk-size warning above 500 kB. This is a
  delivery-performance limitation, not a scientific fallback.
- Browser acceptance is deliberately serial because the local Studio suite
  shares FastAPI and Vite processes; this affects QA throughput, not product
  semantics.
- This receipt does not claim causal XAI validity, universal leakage
  prevention, generalization validity or deployment certification.
