# Alpha guided model choice

RuFLEX Studio can persist a validation comparison of already trained models. For runs evaluated on the **same saved validation cases**, Analysis now records a reproducible shortlist suggestion: highest F1 for binary classification or lowest RMSE for regression, with exact ties resolved by the lowest run ID. The suggested run can be opened from the saved comparison after closing and reopening the project. A manual FIS remains visible as a separate subject, not silently ranked as a calibrated model.

This is not AutoML. It does not create candidate runs, search hyperparameters, pick a final-test winner, certify a model, or approve deployment. Mixed or unknown validation-case alignment produces no suggestion. The persisted schema-v3 suggestion is checked against its metric rows on reopen; older schema-v2 comparisons remain readable without a suggestion.

Current model-building boundaries are distinct: the manual FIS Workbench edits and persists explicit rules; flat neuro-fuzzy training optimizes membership parameters, rule gates and consequents for a fixed declared rule structure. Automatically changing the number or antecedent topology of rules, and comparing those structural revisions as candidates, is not yet a guided employee workflow.

Checks for this slice: focused validation-comparison and project-integrity Python tests passed; EvaluationWorkspace unit tests passed (42); TypeScript/Vite build passed; synthetic Studio browser route trained two different model families, saved the same-case comparison, opened the recommended run, then closed and reopened the project with the exact recommendation preserved. No final-test evaluation or frozen research artifact was changed.
