# RuFLEX V1.3 Alpha closeout QA

## Source state

- Product: `RuFLEX 1.3.0-alpha.0`
- Verified feature branch: `feature/v1.3-data-governance-runtime`
- Product changes through `3ec7ffbd78ffec3f723865b438c6e48e49c4e5cd`
- This receipt records a truthful Alpha closeout check; it does not claim a stable release.

## Verification

- Recent Training Studio component tests: 6 passed.
- Recent Alpha frontend unit suite: 12 passed.
- TypeScript/Vite production build: passed; existing bundle-size warning remains.
- Storybook production build: passed; existing chunk-size and Node deprecation warnings remain.
- Focused real Studio E2E for import/reopen, training choices, catalog failure/retry, and no implicit training: 2 passed.
- Python compileall and the full Python suite were attempted from the configured Python 3.14 environment. The suite reached 100%, with 4 failures in SHAP-dependent tests: installed SHAP 0.51 cannot import because installed Numba 0.63.1 rejects NumPy 2.5.3; SHAP routes consequently report unavailable. This is an environment compatibility failure, not a passing full-suite result.
- No dependency upgrade/downgrade was attempted as part of this low-impact Alpha closeout.
- Fresh exact-HEAD ZIP extraction: `unzip -t` passed; extracted Python compileall and focused Training/model-catalog tests passed (26); clean `npm ci`, frontend unit tests (12), and Vite build passed. The focused browser route passed on the same source state in the checkout; browser E2E was not launched from the `/tmp` extraction because no browser cache was provisioned there.

## Scope and limitations

This closeout covers the Alpha onboarding and Training Studio usability work documented in `PRODUCT_TASK_STATE.json`; it does not certify every optional explainer dependency in the current machine environment. The tracked source archive must be tested separately from a fresh extraction before it is treated as archive-verified. The working tree had pre-existing `docs/article/**` edits; those files are intentionally excluded from the product commit and source archive.

Known delivery warnings: Vite/Storybook report large JavaScript chunks; Storybook also reports a Node module deprecation warning; clean npm install reports two high-severity advisories. No dependency changes were made to suppress warnings. No push to `master`, merge, tag, or release was performed as part of the recorded verification.
