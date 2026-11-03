# A02 R2 — scientific extension to ACDSA paper 1326

The main objective is to address the two reviews of *When High Confidence Is Not Reproducible* without altering the original A01 evidence. This is an **exploratory manuscript revision**, not an accepted ACDSA 2027 camera-ready paper. ACDSA rejected the original submission; there is no approved resubmission route here.

## What was added

1. An a priori estimand for a fixed reference classifier: the conditional probability that a fresh training run reproduces its label on a fixed case.
2. Two **standard** sufficient-condition constructions: deterministic score-gap versus a justified uniform perturbation bound, and a one-sided exact Clopper–Pearson lower confidence bound with Bonferroni family correction within a fixed model/data cell. No novelty is claimed for the inequalities themselves.
3. A02 exploratory validation on 7 data regimes (3 scikit-learn data sets and 4 related synthetic settings), 5 model families, 35 cells, one reference fit + 100 fresh fits per cell: 3,535 fits and 6,125 case–model validation predictions.
4. A post-hoc split-sensitivity run on split 73 for Decision Tree and SGD Logistic on the same seven data regimes: 14 cells, 1,414 more fits and 2,450 validation case–model predictions. The second split was introduced after inspecting split 42 and is not a confirmatory experiment.
5. Integrity checks that re-compute every case's reported exact lower bounds and validate aggregate counts, split identities and error flags. New negative and replay tests.
6. A complete eight-page revised double-blind manuscript DOCX preserving A01's frozen results and tables.

In total the A02 exploratory work uses **4,949 fits and 8,575 validation case–model observations**; 4,739/6,125 certified cases and 242/4,068 high-confidence unstable cases refer **only to the main split-42 matrix**, not to the pooled two-split total.

## Headline data: main A02 validation split 42

| Family | Case–model pairs | Certified at nominal 0.90 | HC unstable / HC cases |
|---|---:|---:|---:|
| Logistic Regression | 1,225 | 1,225 | 0 / 693 |
| Decision Tree | 1,225 | 1,094 | 104 / 1,225 |
| Random Forest | 1,225 | 967 | 0 / 585 |
| Extra Trees | 1,225 | 961 | 0 / 575 |
| SGD Logistic | 1,225 | 492 | 138 / 990 |
| **Total** | **6,125** | **4,739** | **242 / 4,068** |

The nominal 95% simultaneous one-sided coverage is **per dataset-model cell only**, conditional on independent identically distributed fresh draws of the specified training-randomness law. Fixed pseudorandom integers are not themselves a proof of statistical independence or validity of that law.

**Error enrichment in high-confidence cases (split 42):** Decision Tree unstable 46/104 (44.2%) versus stable 120/1,121 (10.7%); SGD Logistic unstable 59/138 (42.8%) versus stable 66/852 (7.7%). These contrasts are **descriptive**, and do not establish review-policy superiority at matched coverage.

## Split sensitivity

| Model | Split | HC unstable / HC | Certified / total | Unstable errors | High-stable errors |
|---|---:|---:|---:|---:|---:|
| Decision Tree | 42 | 104/1,225 | 1,094/1,225 | 46/104 | 120/1,121 |
| Decision Tree | 73 | 115/1,225 | 1,078/1,225 | 49/115 | 143/1,110 |
| SGD Logistic | 42 | 138/990 | 492/1,225 | 59/138 | 66/852 |
| SGD Logistic | 73 | 73/956 | 497/1,225 | 26/73 | 57/883 |

## Reproduce

Use Python 3.11–3.13 with NumPy, scikit-learn, SciPy and pytest as declared in `requirements.txt` (observed local environment: NumPy 2.3.5, scikit-learn 1.8.0, SciPy 1.17.0). Run from the extracted bundle's root:

```bash
python -m pip install -r requirements.txt
pytest -q test_certificates.py test_protocol.py

# New split run, or run original 42 using the default seed options:
python benchmark.py --output-dir results_split73_stress --mode stress \
  --families decision_tree,sgd_log_loss --n-seeds 100 \
  --split-seed 73 --reference-seed 27000 --fresh-seed-start 30000
python benchmark.py --output-dir results_split73_public --mode bundled \
  --families decision_tree,sgd_log_loss --n-seeds 100 \
  --split-seed 73 --reference-seed 27000 --fresh-seed-start 30000

python verify_experiment.py --parts results_split73_stress results_split73_public
python analyze_results.py \
  --split42 results/A02_CASE_LEVEL_VALIDATION.csv \
  --split73 results_split73_stress/case_level_validation.csv results_split73_public/case_level_validation.csv \
  --output results_analysis
```

For the main split 42 there are four stored partial batches, which can be recreated using `--mode bundled` or `--mode stress` with `--families logistic_regression,decision_tree,random_forest` and `--families extra_trees,sgd_log_loss`, respectively; use the default split/reference/audit seeds. Combine using `report.py`. The original results and all of their frozen hashes must remain unchanged.

## Scientific boundary

The test partition of A02 is untouched. The A01 confirmatory test was opened once in the historical frozen analysis and is **not** reopened or modified. The case-wise agreement guarantee concerns fresh retrainings of a fixed data/configuration/reference, **not correctness, confidence calibration, distribution shift or model selection**. The second split is post-hoc sensitivity evidence only. These results do not establish a new method outperforming confidence-only routing at equal coverage and do not prove cross-domain generality.

## Research status

- Done: reproducible additional experiments, independent verification of stored case-level statistics, full revised manuscript and split-sensitivity analysis.
- Not done: new externally sourced domains, several data splits across **all** 5 model families, a locked matched-coverage review-policy evaluation on a separate test set, and conference-specific camera-ready formatting for a new venue.