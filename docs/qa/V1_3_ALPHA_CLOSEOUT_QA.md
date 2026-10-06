# RuFLEX V1.3 Alpha closeout QA

## Source state

- Product: `RuFLEX 1.3.0-alpha.0`
- Verified feature branch: `feature/v1.3-data-governance-runtime`
- Product changes through `3ec7ffbd78ffec3f723865b438c6e48e49c4e5cd`; QA record added in following documentation-only commits.
- This receipt records a truthful Alpha closeout check; it does not claim a stable release.

## Verification

- Recent Training Studio component tests: 6 passed.
- Recent Alpha frontend unit suite: 12 passed.
- TypeScript/Vite production build: passed; existing bundle-size warning remains.
- Storybook production build: passed; existing chunk-size and Node deprecation warnings remain.
- Focused real Studio E2E for import/reopen, training choices, catalog failure/retry, and no implicit training: 2 passed.
- Python compileall and the full Python suite passed from an isolated Python 3.14 environment using NumPy 2.3.5 with the existing Numba 0.63.1 / SHAP 0.51.0 packages. No tracked dependency or lock file was changed.
- The shared Python environment still has NumPy 2.5.3, which Numba 0.63.1 rejects; running the full suite directly there yields 4 SHAP-dependent failures. This is a local environment compatibility warning, not a product-code change.
- No shared-environment package upgrade/downgrade was attempted as part of this resource-conscious closeout.
- Fresh exact-HEAD ZIP extraction: `unzip -t` passed; extracted Python compileall and focused Training/model-catalog tests passed (26); clean `npm ci`, frontend unit tests (12), and Vite build passed. The focused browser route passed on the same source state in the checkout; browser E2E was not launched from the `/tmp` extraction because no browser cache was provisioned there.

## Scope and limitations

This closeout covers the Alpha onboarding and Training Studio usability work documented in `PRODUCT_TASK_STATE.json`; it does not certify every optional explainer dependency in the shared machine environment. The working tree had pre-existing `docs/article/**` edits; those files are intentionally excluded from the product commit and source archive.

Known delivery warnings: Vite/Storybook report large JavaScript chunks; Storybook also reports a Node module deprecation warning; clean npm install reports two high-severity advisories. No dependency changes were made to suppress warnings. No merge, tag, or GitHub release was performed as part of the recorded verification.
