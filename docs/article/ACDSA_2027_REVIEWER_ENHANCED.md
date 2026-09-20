# ACDSA 2027 reviewer-enhanced manuscript state

## Manuscript

Title: **Cross-Run Disagreement in High-Confidence Predictions**

The current reviewer-enhanced manuscript remains a six-page ACDSA 2027 paper. It integrates reviewer-requested post-hoc checks and a practical reduced-run analysis while preserving the frozen confirmatory A01 result.

Artifact identities for the current submission copy:

- DOCX SHA-256: `91a0e235f72bf520c3bba7a4a1bb2f888131944d86e388400d83070b9e90e9ee`
- PDF SHA-256: `d04cce7d44a2594ce7ef3b2b0eb79d1b94d32422ef8211080dcd5a2e3a0a73ca`

The binary manuscript files are intentionally not used as scientific evidence. The reproducible evidence and analysis code are kept under `research/a01_stability_aware_review/`.

## Added evidence after reviewer feedback

Reviewer-requested exploratory checks are recorded in:

- `research/a01_stability_aware_review/results/reviewer_followup_2026/`
- `research/a01_stability_aware_review/results/practical_followup_2026/`

They include:

- HCIR sensitivity to confidence thresholds 0.85 / 0.90 / 0.95 and agreement thresholds 0.70 / 0.80 / 0.90;
- an independence reference for HCIR;
- probability-standard-deviation threshold sensitivity;
- a post-hoc Bank Marketing Decision Tree FNR readout;
- a reduced-run approximation study using K = 3, 5, 10, 15, 20 total frozen runs;
- illustrative Bank Marketing Decision Tree cases.

## Practical result

With 10 total frozen runs (one selected operational model plus nine auxiliary runs), the reduced analysis reaches 99.89% macro agreement with the full 20-run review-gate decisions and 97.04% macro review recall while using 9/19 = 47.37% of the full auxiliary-fit count. With 15 total runs, the corresponding values are 99.98% and 99.87% at 14/19 = 73.68%.

These are post-hoc approximation results on frozen validation evidence. They do not define a universal minimum number of runs or a hardware-normalized compute saving.

## Confirmatory boundary

The following remain unchanged:

- the 300 frozen A01 fits;
- the selected operational models;
- validation-derived thresholds and policies;
- the single final-test opening;
- `A01_FINAL_RESULTS.json`;
- the original confirmatory interpretation.

No model was retrained, no threshold or policy was refit, and no additional final-test opening was performed for the reviewer follow-up.
