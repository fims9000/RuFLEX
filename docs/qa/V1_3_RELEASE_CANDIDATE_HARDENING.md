# V1.3 release-candidate hardening

Status: LOCAL CODE GATES VERIFIED; source-package verification is recorded separately in the companion `release/RuFLEX_V1_3_RELEASE_CANDIDATE_QA.json`. This document alone is not a package PASS, a public release, or a claim that every platform/research roadmap item is complete.

Preservation correction: earlier statements that article files were unchanged are withdrawn. The checkout-preservation incident below takes precedence; the full-suite verifier itself regenerated article outputs. Research artifacts were not regenerated.

Prerelease publication scope: the user subsequently authorized finishing and pushing the code prerelease, then explicitly authorized merging it with master and deferring article work. Product verification is complete; article restoration remains a separate unresolved incident. Publish only committed product/source documentation, excluding dirty article outputs, user project `1/` and uncommitted R8 work. Fast-forward master from its owning worktree, preserve dirty files and a backup ref, and use ordinary pushes without force. This is not a stable-release claim or permission for scientific-result changes. See [prerelease notes](../releases/V1_3_ALPHA_PRERELEASE_RU.md).

## Scope and preservation

Base: `3644197fde0f72db3c2a98404a25e830b39a96ac`, branch `feature/v1.3-data-governance-runtime`.

Includes the preceding teaching-dataset/SHAP/history changes plus release verification and Russian Stability Lab presentation. Native scientific calculations, model parameters, persisted schemas and A01/S03 frozen artifacts are not modified. Existing article edits and user project `1/` are unrelated and must not be included in the product commit.

The release target is the existing native product: local Studio, CSV/XLSX data, declared native estimators, manual FIS workflows, validation evidence, supported explanations, frozen policies, explicit final-test evaluation, lineage, checks and portable evidence. It does not add AutoML search, arbitrary Python libraries, arbitrary classification targets, or production certification.

## Corrections found by the full audit

- Actual product defect: portable VerificationBundle relationship validation omitted `GeneralizationContract` from its object-identity index. A valid scope-bound SliceAnalysis was therefore falsely rejected even though its scope object was present and matched. A regression reproduced this before the fix. The correction adds only `GeneralizationContract: contract_id` to the index. Positive scope binding, missing scope and foreign-dataset scope are explicitly checked, along with a native exported archive. No slice calculation, scope rule, persisted schema or historical artifact is edited.
- The action inventory had 46 actions but Studio actually declared 49: dataset continuation and two model-navigation actions were missing from the inventory. All three already have native browser tests. The inventory is extended, not the equality/uniqueness verifier weakened.
- A BehaviorSpec browser assertion expected a model hash to be visible without opening its now-collapsed model-reference section. The test opens that section and retains the original exact-hash assertion.
- The expert-correction test delayed every subsequent GET, including hydration after its final save, leaving an unresolved route in the next test. Only the intended first recovery GET is now delayed; later requests use the real backend.
- The explanation-reproducibility scenario now opens the advanced input section before editing the actual example, retaining its original four-explanation pairing and persisted-replay checks.
- The legacy product-evidence capture opened the final test and then requested a second model fit and TRAIN-only FIS refit. The product correctly blocked it. Capture now finishes fitting first, restores the exact original saved policy through history, and only then explicitly opens the synthetic holdout. Product final-test restrictions remain unchanged.
- Stability Lab primary headings, actions, figures, statistics and case-inspection copy are translated for Russian users. Persisted scientific identifiers and calculations remain unchanged; original scientific notes remain inspectable.
- Actual narrow-screen defect: at 1100px the non-wrapping Stability toolbar pushed its action beneath the Properties inspector, which intercepted the user's click. A native Russian acceptance test reproduced it without forced clicks. Toolbar wrapping and responsive summary cards are scoped to Stability Lab; the test retains ordinary pointer interaction, three-run evidence, policy freeze, dark theme and close/reopen assertions.
- Root-cause refinement: wrapping alone did not resolve the click interception. CSS uses inclusive `max-width: 1100px/720px`, while initial panel state used strict `<` comparisons. Exactly at the breakpoint the Properties drawer was therefore open over the workspace by default. Initial state now uses matching `<=` comparisons, with explicit 720px/1100px native browser regressions for hidden defaults and manual show/hide. No forced click or larger timeout is used to hide the defect.
- The old light/dark visual baselines predated the new-project template selector. Actual and diff images were inspected: differences are the added selector and shifted controls, not a lost panel or changed contrast. The selector is also styled consistently with the existing light/dark fields before rebaselining. No screenshot tolerance is increased.

## Verification ledger

- Full configured Python suite: **442 passed**, 11 warnings, 92.78 seconds. Numerical-library threads limited to one. Warnings include short-budget fixture convergence and upstream SHAP deprecations; they are not concealed.
- Frontend build: TypeScript/Vite passed after localization. A focused unit assertion caught an omitted English `independent fits` suffix; the suffix was restored rather than weakening the test. Final unit rerun: **138 Vitest + 1 API-client passed**, with one Vitest worker. Storybook production build passed.
- Initial full English browser inventory: **100 passed / 28 language-specific skipped / 7 failures**, 6.9 minutes. Failures cover the listed stale inventory, hidden-field access, test-route lifetime, old post-test fitting sequence and two stale visual baselines. Explicit correction/rerun is required; this initial non-green result is retained rather than presented as a successful full run.
- Correction verification: 8/9 focused browser regressions passed; the ninth exposed the actual portable scope-index defect described above. After the narrow product correction and positive/negative Python regression, the complete product-evidence capture passed (1/1, 41.5 seconds), including its portable bundle and explicit final-test/reopen route.
- Final complete English inventory after all code corrections: **107 passed / 29 Russian-specific skipped / 0 failed**, 5.1 minutes. The Russian-only cases are verified separately, not counted as successful English tests. Both light/dark visual tests pass at the normal unchanged screenshot tolerance.
- Russian inventory: 28 existing cases passed, including twelve model/task routes, all three SHAP routes and user CSV/XLSX replacement. The added 29th case exposed the exact-breakpoint drawer defect. After correcting the inclusive breakpoint, the native Russian Stability freeze/dark/reopen test passed (13.5 seconds), and four English Stability/compact-layout tests passed (22 seconds), including both boundary widths.
- Final Russian Stability follow-up after visual polish: PASS (14.3 seconds), including collapsed/expanded run details, localized status, native analysis/policy creation, responsive dark theme and reopen. Combined with the existing 28 Russian cases, all 29 Russian scenarios have passing evidence. All twelve model/task combinations, three native SHAP routes and CSV/XLSX replacement were actually executed.
- Storybook, current frontend unit/build, focused portable-scope regressions and diff integrity: PASS. Exact-commit archive creation, extracted-source tests/import/build and final package checksum are intentionally recorded in the external companion receipt after this source snapshot is committed.

## Checkout-preservation incident

The final byte audit of the extracted `9223ee6` source found 13 changed article outputs. Root cause: `tests/test_article_package_scripts.py` invoked real document generators in the checkout. The earlier full-suite run also invoked that unsafe test in the working repository. Articles already had unrelated uncommitted edits; no exact pre-run binary backup was captured, so preservation of those pre-existing bytes cannot be asserted. Do not restore them from Git or another worktree without the user's direction.

Current articles are preserved in `release/RuFLEX_ARTICLE_PRESERVATION_20261102_021142.zip`, SHA-256 `27e31ee31c10015195740f99144dc6cb4b0bbbd60978c43bd1defc4bf506e74f`; ZIP integrity passes. This is a post-incident preservation copy, not proof of pre-run content. The affected test now uses independent temporary script/article copies, a separate LibreOffice profile, and a source-byte hash guard without weakening document/readiness assertions. Claims of article preservation and stable-release closure remain conditional on explicitly resolving this incident; the separately authorized code prerelease excludes these dirty outputs. No article outputs are included in product commits.

Isolation verification: all three document tests pass with the byte guard; the full configured Python suite then passes **442 tests / 11 warnings in 125.55 seconds**. The post-incident checkout article diff remains byte-identical to its preservation hash throughout these runs. `compileall` and `git diff --check` pass. The safety patch changes only tests, the project rule and QA/state records; product/frontend blobs remain identical to the freshly tested `9223ee6` snapshot (109 English browser tests, 29 Russian native production-preview tests, 138 Vitest + 3 Node checks, Vite/Storybook builds, installed-wheel smoke 9, npm audit zero). New exact-source archive verification is recorded separately, not inferred from these checkout results.

## Resource policy

One test worker; BLAS/OpenMP/MKL threads = 1; no benchmark/research execution. Browser, Python suite and builds are run sequentially because this laptop has heavily used memory/swap. Fresh archive dependency installation should use an ignored on-disk release directory, not a large tmpfs copy.
Vitest now defaults to one worker as well, so an ordinary `npm test` does not create one jsdom environment per CPU concurrently. This changes verification resource usage, not product model behavior. The tested environment is recorded in `V1_3_TESTED_ENVIRONMENT.json`.

## Scientific/product limits

Synthetic fixtures are not real field data. Method/model compatibility is explicit. A valid persisted explanation/replay does not establish causality. Assurance is a collection of scoped checks, not a universal reliability or safety certificate. A software final-test boundary is not a universal leakage detector. Native inference and evaluation do not authorize post-test tuning. Full AutoML and trained neuro-fuzzy rule-topology editing remain outside this release-hardening scope.

## Fresh-install security gate

The first exact-source candidate `e27ea1b` passed extracted Python (442), frontend units and both builds, but its fresh `npm ci` reported 9 advisories (1 critical, 2 high, 6 moderate). That ZIP is retained as a superseded QA checkpoint, **not** the final release candidate.

The dependency refresh leaves scientific Python code and model settings untouched and updates existing tooling: Vite 8.2.4, Vitest 5.0.5, Storybook/react-vite 10.6.5 and the compatible Undici patch 8.12.3. The docgen plugin still declares Glob 13, so a narrowly scoped override selects Glob 14.0.3 for that plugin only; its Minimatch resolves to 11.0.3. Refreshed clean install, 138 Vitest checks, Node version checks, Vite and Storybook compilation passed; full installed dependency audit reports zero advisories. Native browser/archive gates are repeated on the final source snapshot before handoff. No `audit fix --force` or major Storybook downgrade is used.

Primary advisory references: [Storybook origin validation](https://github.com/advisories/GHSA-f2ph-cmg5-wxc8), [Vite filesystem boundary](https://github.com/advisories/GHSA-rq7h-c2jc-7f22). The actual npm audit JSON is part of the companion local QA evidence; zero reported advisories is not a general security certification.

The existing jsdom tool dependency requires newer Node branches than the old launcher allowed. Package engines, a tested launcher version guard and CI now agree on the supported branches; local verification uses Node 26.12.0. CI also explicitly runs the Russian-only routes instead of leaving their language skips untested. Remote CI is not claimed as executed without a push.

The old API-client test asserted only that a hardcoded URL began with another literal, not the actual client configuration. The strengthened test reads the real declaration and caught a second startup defect: the built frontend defaulted to port 8000 while the documented launcher/backend use 8010. The fallback now matches 8010; the explicit environment override remains supported. Native integration tests already use 8010; the final production-preview smoke additionally verifies the no-override build path.
