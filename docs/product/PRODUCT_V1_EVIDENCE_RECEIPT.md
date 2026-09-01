# RuFLEX Product V1 Evidence & Demonstration Pack receipt

- Frozen source release: `release/RuFLEX_PRODUCT_V1_RC2_SOURCE.zip`
- Source SHA-256: `56c603c409f84e7845cbb8c24a26516e432753fd0ffaa02b587329d210ff1e50`
- Capture date/time: 2026-08-31 Europe/Moscow
- Screenshot count: 19 PNG files, light Studio viewport 1440×900
- Capture command: `cd frontend && RUFLEX_PYTHON=/home/lebedeffson/Code/venv/bin/python PLAYWRIGHT_BROWSERS_PATH=/home/lebedeffson/Code/RuFLEX_ASSISTANT_DIRECT_BUILD_v3/.playwright-browsers npx playwright test e2e/product-evidence-capture.spec.ts`

## Executed verification

- `PYTHONPATH=src /home/lebedeffson/Code/venv/bin/python -m pytest -q` — PASS, 111 tests.
- `PYTHONPATH=src /home/lebedeffson/Code/venv/bin/python -m compileall -q src` — PASS.
- `cd frontend && npm test` — PASS, 1 test.
- `cd frontend && npm run build` — PASS.
- `cd frontend && npm run build-storybook` — PASS.
- `cd frontend && … npx playwright test` — PASS, 23 tests including visual regression and `product-evidence-capture.spec.ts`.

## Scope and limitations

The package adds documentation, a deterministic Playwright evidence route, generated real-Studio screenshots, and capture provenance only. It introduces no new Product V1 scientific or product functionality and does not change model behaviour, scientific semantics, or visual baselines.

The screenshots prove their captured persisted route, not universal performance, causal explanation, exhaustive continuous-model explanation, or unrestricted safe deployment. Vite reports a non-blocking production chunk-size warning above 500 kB. Playwright is intentionally serial because the stateful acceptance suite shares one FastAPI/Vite server pair.

Product implementation evidence is under `docs/product/`; old research/article material remains under `docs/article/` and is not presented as validation of these newly captured product routes.
