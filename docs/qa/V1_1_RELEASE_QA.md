# RuFLEX V1.1 release QA receipt

Status: **local candidate verified; no remote action performed**.

## Product checks

| Check | Result |
| --- | --- |
| Python suite | PASS — 224 tests, run in three bounded batches |
| Python compile | PASS — `src/ruflex` |
| Focused capability/runtime tests | PASS — API contracts, trusted plugin discovery, SDK and training adapter routing |
| Studio unit test | PASS — 1 test |
| Vite production build | PASS |
| Storybook production build | PASS |
| Playwright Studio matrix | PASS — 26 tests in 14 specs, including lifecycle, FIS, training, Study, Stability Lab, evidence, Assurance, bundle and visual routes |
| Fresh tracked-source archive smoke | PASS — focused backend, `npm ci`, unit test and Vite build |
| `git diff --check` | PASS before the archive handoff |

## Visual baseline decision

The V1.0.1 visual snapshots contained stale job-panel wording relative to the
already existing shell (`Local-first jobs`). The difference was inspected: it
was limited to that status text and affected no V1.1 capability content. The
four deterministic Linux baselines were regenerated with the declared
Playwright headless-shell runtime and the visual spec then passed.

## Known release limitations

- Production Vite and Storybook builds emit the existing large-chunk warning;
  it is a performance follow-up, not a failed build or a claimed optimization.
- The full Phase 1.5 A01 scientific audit requires its separate frozen
  evidence/runtime artifacts. A tracked source archive verifies that the audit
  refuses to produce a partial result when those artifacts are absent.
- This product release does not make a safety, causality, universal stability
  or universal leakage-detection claim.

## Scope protection

The QA route did not alter frozen S01/S02/A01/S03 source records. Unrelated
article-package changes present in the worktree were neither staged nor
included in this V1.1 release candidate.
