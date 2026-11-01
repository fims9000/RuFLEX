# Alpha compact Studio shell

This slice makes the existing RuFLEX Studio usable at ordinary laptop widths without removing any of its five workbenches. The previous 1180 px minimum width and always-open 220 px jobs panel left too little room for the actual work. The shell now starts with Jobs hidden, opens Properties as an on-demand drawer below 1100 px, and opens the project tree as a drawer below 720 px. Tree, Details and Jobs have visible toolbar controls. The Project overview uses task-oriented entry points and keeps the full integrity explanation available on demand; a warning or failure opens those details automatically.

The reference image informed the compact, persistent workbench/navigation structure. This is not a reproduction of its old desktop chrome. Scientific calculations, saved evidence, policy semantics and routes are unchanged. The Gravity UI component theme now follows the Studio light/dark setting, avoiding a mixed-theme display.

Browser screenshot baselines live in `frontend/e2e/studio-compact-shell.spec.ts-snapshots/` for 920 px and 640 px, and in `frontend/e2e/visual-foundation.spec.ts-snapshots/` for the desktop light/dark shells. The compact browser route checks that every workbench and optional panel remains reachable, the page has no horizontal overflow at 640 px, and the project can be created. Adjacent browser routes cover FIS work, Stability Lab, project close/reopen, and accessibility.

This is a shell and entry-workflow improvement, not a claim that every deep technical form has been simplified or localized. Further employee-facing work should use progressive disclosure in the dense workbenches, while preserving exact scientific provenance and the final-test boundary.

## Verification and verifier mismatch

Frontend unit tests passed: 126 Vitest tests in 14 files plus the API-client test. TypeScript/Vite and Storybook production builds passed. The full serial Playwright run completed with 102/105 passing; the focused project-lifecycle suite passed 18/18, and the compact, FIS, Stability, visual and light/dark accessibility routes passed. Vite reports an existing large-chunk warning.

Three unchanged broad-suite tests remain red and are not accepted as grounds to weaken scientific or session boundaries:

- `dataset-confirm-session-race.spec.ts` expects Close to work while a dataset confirmation write is still unresolved. The current Studio disables Close during the write, serializing project mutations; the test times out on the disabled button.
- `project-open-race.spec.ts` expects a second Open request while the first is unresolved. The current Studio disables Open during that operation; the test times out waiting for a second Open button. This is also consistent with serialized project operations.
- `product-evidence-capture.spec.ts` opens final test, then tries to train another model and expects four explanations across two runs. The post-test training boundary prevents that new fit; the captured four explanations all belong to one run, so the reproducibility POST did not persist the required cross-run analysis. The test's route stub masked the backend status with a synthetic 503 and its later lookup found no saved analysis.

These are verifier-design mismatches in scenarios outside this shell change, not evidence that the new layout lost a workbench. The tests have not been deleted, skipped or loosened. A subsequent bounded test-maintenance slice should rewrite them around the current serialized operations and pre-final-test evidence ordering while retaining their negative assertions.
