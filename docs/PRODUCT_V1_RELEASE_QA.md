# RuFLEX Product V1 release QA

Release evidence was executed from a fresh extraction of
`release/RuFLEX_PRODUCT_V1_RC2_SOURCE.zip`.

- Python suite: `PYTHONPATH=src /home/lebedeffson/Code/venv/bin/python -m pytest -q` — passed.
- Python `compileall`: passed.
- Frontend clean install: `npm ci` — passed.
- Frontend unit: `npm test` — passed.
- TypeScript/Vite: `npm run build` — passed.
- Storybook static build: `npm run build-storybook` — passed.
- Browser acceptance (including visual baselines and safe condition-monitoring demo): `RUFLEX_PYTHON=… PLAYWRIGHT_BROWSERS_PATH=… npx playwright test` — 22 passed.
- Archive integrity: `unzip -t` — passed; the source archive excludes Python caches, node_modules and generated build products.

The final archive checksum is emitted by `scripts/build_product_v1_rc2_release.py` and recorded alongside the release artifact.

The Studio retains scientific boundaries: validation-only calibration, thresholds and selective review; final-test firewall; exact finite/grid labels only where justified; and independent AssuranceCase gates rather than a trust score.

Known limitation: the production JavaScript bundle emits a size warning above 500 kB. This is a delivery-performance concern, not a scientific fallback or test failure.
