# V1.1 Studio action inventory and QA map

This inventory is a release QA map, not a claim that every control is a
separate scientific capability. It maps user-facing actions to their canonical
object boundary and browser coverage so that regression work does not stop at a
successful TypeScript build.

| Studio area | Primary user action | Canonical outcome | Browser route |
| --- | --- | --- | --- |
| Project | Create, open, save, close | persisted project session | `project-lifecycle.spec.ts` |
| Data | Inspect and confirm CSV/XLSX contract | DatasetContract, audit, source artifact | `training-evaluate.spec.ts`, `product-evidence-capture.spec.ts` |
| FIS | Design, save, import/export MATLAB subset, evaluate | FIS revision and trace | `matlab-fis.spec.ts`, `product-evidence-capture.spec.ts` |
| Training | Select runtime-compatible adapter; train or create Study | TrainingRun/Study with train-only preprocessing | `training-evaluate.spec.ts`, `multi-seed-study.spec.ts` |
| Evaluation | Save validation evidence; calibration/threshold/selective review | AnalysisEvaluation and validation-derived policies | `training-evaluate.spec.ts`, `analysis-calibration.spec.ts` |
| Final test | Apply already frozen policy after explicit confirmation | FinalTestEvaluation | `project-lifecycle.spec.ts` |
| Stability Lab | Create analysis, inspect case evidence, freeze gate | StudyStabilityAnalysis and StabilityGatePolicy | `stability-lab.spec.ts` |
| Evidence | Generate/check explanation, evaluate behavior, export bundle | ExplanationContract/Check, AssuranceCase, VerificationBundle | `evidence-capture.spec.ts`, `product-evidence-capture.spec.ts` |
| Lineage | Inspect restored linked objects | read-only lineage graph | `project-lifecycle.spec.ts`, `product-evidence-capture.spec.ts` |

## Runtime-catalog acceptance

`training-evaluate.spec.ts` additionally verifies that the Training workspace
receives the runtime model catalog, exposes exactly task-compatible model
options, and switches the visible form from Flat Neuro-Fuzzy controls to
Decision Tree controls without a hard-coded frontend model list.

## Accessibility baseline

The listed routes use labelled form controls, named primary actions and role
alerts for errors. Full keyboard/screen-reader conformance is a separate
accessibility audit; no such certification claim is made by this inventory.
