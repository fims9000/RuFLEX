# RuFLEX V1.2 RC1 release QA

This receipt records the V1.2 RC implementation gate. It is product QA, not a
research result or a claim of model quality, safety, causal explanation or
universal leakage prevention.

## Verified implementation scope

- One frozen runtime catalog contains model adapters, explainers, the native
  explanation validator and the local execution backend.
- `train_model()` resolves its adapter through the registry; the core retains
  DatasetContract roles, TRAIN-only preprocessing and all canonical persistence.
- New runs, studies, explanation contracts, checks and evidence jobs persist
  their runtime identities. Legacy persisted objects remain readable without a
  silent rewrite.
- The model matrix covers 12 available adapter/task pairs. The explainer matrix
  covers all 25 built-in binary run/explainer pairs: 15 create and reopen
  evidence; 10 reject as not applicable.
- Studio source action inventory is checked against all declared primary action
  attributes, and an axe baseline covers Project, Data, Training/Stability,
  Evaluation and Evidence/Assurance/Bundle workspaces.

## Local checks

| Check | Result |
|---|---|
| Python collection | PASS — 258 tests |
| Full Python suite, bounded groups | PASS — 258/258 |
| `compileall` | PASS |
| Frontend unit | PASS — 1/1 |
| Vite production build | PASS |
| Storybook production build | PASS |
| Playwright full suite, bounded groups | PASS — 28/28 |
| Axe critical/serious baseline | PASS |
| `git diff --check` | PASS |
| Frozen research path diff from V1.1 baseline | PASS — no changes |
| Fresh tracked-source archive smoke | PASS — install, 52 focused runtime tests, npm ci, unit, Vite and Storybook |

## Archive and worktree rules

The exact committed source archive and its SHA-256 are created after this
tracked receipt, under ignored `release/`, and recorded in the release-side
receipt distributed with the archive. User-owned `docs/article/` worktree
changes are deliberately excluded from V1.2 commits.

## Known non-blocking limitations

- Vite and Storybook emit their existing large-chunk warnings; no behavior is
  hidden or disabled to suppress them.
- The axe gate is a detectable-violation baseline, not a WCAG certification.
- External runtime discovery is intentionally limited to declared, trusted
  `ruflex.plugins` entry points; arbitrary Python upload is not supported.
