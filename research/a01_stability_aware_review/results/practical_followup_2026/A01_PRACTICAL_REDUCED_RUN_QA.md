# A01 practical reduced-run QA

- Role: post-hoc / exploratory validation-only analysis.
- Validation evidence SHA-256: `435ed839fd7e5e97daaa227adf2f652777908e99e5a19f93fb171ad947c980d8`.
- Applicable frozen validation cells: 15.
- Selected operational run retained in every reduced-run subset: YES.
- Frozen 20-run Stability Gate replay against persisted decisions: PASS for all 15 cells.
- Model retraining: NO.
- Threshold or policy refitting: NO.
- Additional final-test opening: NO.
- Frozen confirmatory A01 results modified: NO.
- Reduced budgets: K = 3, 5, 10, 15, 20 total runs.
- K < 20 subset sampling: all subsets when at most 1,000 combinations exist; otherwise 1,000 deterministic unique subsets per cell and K.
- Focused A01 tests after the analysis: 41 passed.
- Practical headline: K=10 uses 9/19 = 47.37% of the auxiliary-fit count, with 99.89% macro gate-decision agreement and 97.04% macro review recall relative to the full 20-run reference.
- K=15 uses 14/19 = 73.68% of the auxiliary-fit count, with 99.98% gate-decision agreement and 99.87% review recall.
- The repeat-fit fraction is a run-count proxy, not a hardware-normalized compute estimate.
