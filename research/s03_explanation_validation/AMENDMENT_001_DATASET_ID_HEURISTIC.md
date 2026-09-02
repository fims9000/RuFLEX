# S03 Amendment 001 — Dataset ID-Column Heuristic

## Discovery and scope

The product dataset profiler was found to classify any column name ending in
`id` as an identifier. During the first, interrupted S03 Phase 1 attempt this
misclassified the frozen Bank Marketing feature `job_housemaid`, producing a
61-feature DatasetContract rather than the pre-specified 62-feature contract.

- Benchmark model fits observed before discovery: five AI4I fits only.
- Bank model fit: not started.
- CLEAN explanations: 0.
- CORRUPT explanations: 0.
- Empirical detection/localization outcomes: 0.
- Final-test access: false.

## Amendment

The implementation now recognizes only an exact `id` name or an explicit
`_id` token as an ID candidate. The frozen intended Bank feature set, datasets,
split, models, seed, explanation protocol, corruption taxonomy, and scientific
question are unchanged. This amendment corrects implementation conformance;
it is not post-result tuning because no explanation-validation outcome existed.

The five interrupted AI4I fits remain historical non-evidence in
`PHASE1_INTERRUPTED_RECEIPT.json`. They must not be reused by the coherent
Phase 1 restart.
