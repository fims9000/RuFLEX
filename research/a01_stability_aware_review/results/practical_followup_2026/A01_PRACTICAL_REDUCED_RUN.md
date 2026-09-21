# A01 practical reduced-run analysis

## Scientific boundary

This is a post-hoc validation-only practical analysis of already frozen A01 case-level predictions. The selected operational run is always retained. No model is retrained, no policy is refit, no final-test evidence is opened, and the frozen confirmatory results are unchanged.

## Reduced-run question

The full A01 reproducibility analysis uses 20 independently trained runs. For a total run budget K, this analysis keeps the selected operational model and samples K-1 auxiliary frozen runs from the remaining 19. The same confidence (0.90), selected-run agreement (0.80), and probability-standard-deviation (0.15) criteria are then recomputed from that reduced set and compared with the full 20-run Stability Gate.

| total runs K | auxiliary runs | repeat-fit fraction** | gate decision agreement | review recall | review Jaccard | HC-disagreement recall* | workload delta | agreement MAE |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 2 | 10.53% | 99.61% | 91.06% | 90.97% | 81.09% | -0.35% | 0.0049 |
| 5 | 4 | 21.05% | 99.74% | 93.35% | 93.33% | 72.32% | -0.25% | 0.0037 |
| 10 | 9 | 47.37% | 99.89% | 97.04% | 97.04% | 90.89% | -0.10% | 0.0021 |
| 15 | 14 | 73.68% | 99.98% | 99.87% | 99.85% | 94.30% | -0.01% | 0.0012 |
| 20 | 19 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% | 0.0000 |

\* HC-disagreement recall is macro-averaged only over cells where the full 20-run reference contains at least one high-confidence disagreement case.

\** Repeat-fit fraction is a run-count proxy: (K-1)/19 auxiliary fits relative to the full analysis. It is not a hardware-normalized runtime estimate.

## Illustrative Bank Marketing Decision Tree cases

These cases are high-confidence predictions that the full 20-run analysis flags for cross-run disagreement. They illustrate the intended operational role: the selected model still supplies the prediction; auxiliary runs only provide reproducibility evidence.

| case | target | prediction | correct | confidence | full agreement | prob. SD | K=3 detect | K=5 detect | K=10 detect | K=15 detect |
|---|---:|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| source:17908 | 0 | 1 | no | 100.00% | 10.00% | 0.3000 | 100.00% | 100.00% | 100.00% | 100.00% |
| source:19670 | 1 | 0 | no | 100.00% | 50.00% | 0.5000 | 78.95% | 74.90% | 98.10% | 100.00% |
| source:27736 | 1 | 0 | no | 100.00% | 75.00% | 0.4330 | 46.78% | 27.50% | 45.60% | 61.20% |
| source:28135 | 0 | 0 | yes | 100.00% | 10.00% | 0.3000 | 100.00% | 100.00% | 100.00% | 100.00% |
| source:12131 | 0 | 0 | yes | 100.00% | 75.00% | 0.4330 | 46.78% | 26.80% | 45.80% | 60.60% |

## Practical interpretation

The reduced-run results quantify the computational trade-off instead of assuming that 20 runs are always required. With K=10 total runs (9 auxiliary), the macro gate-decision agreement is 99.89% and review recall is 97.04% while using 47.37% of the auxiliary-fit count of the 20-run reference. K=15 reaches 99.98% gate-decision agreement and 99.87% review recall at 73.68% of the auxiliary-fit count. These are approximation results on frozen validation evidence, not new confirmatory claims.
