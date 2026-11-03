# When High Confidence Is Not Reproducible — Research Release R3

**Status:** complete reproducible *exploratory* extension of a rejected ACDSA 2027 submission (paper 1326). This release is **not** a claim of acceptance by ACDSA, clinical validation, proof of universal risk improvement, or an independently preregistered confirmatory study.

## What is in this release

- `manuscript/When_High_Confidence_Is_Not_Reproducible_REVISED_R3.docx`: integrated 10-page, anonymous, two-column research manuscript; preserves the A01 frozen observations and adds A02–A05.
- `code/a03_protocol.json`: locally frozen **before execution** of the A03 batch experiment (not an external preregistration).
- `code/a03_heldout.py`: all A03 dataset specifications, fixed models, held-out splits, review masks, and per-cell bootstrap; seed-controlled benchmark.
- `code/verify_a03.py`, `code/analyze_a03.py`, `code/test_a03.py`: independent A03 replay, summaries, six unit tests.
- `code/a04_run_budget.py`, `code/verify_a04.py`: post-hoc 5/10/20/30-fit sensitivity and independent replay of saved per-seed predictions.
- `code/a05_protocol.json`, `code/a05_pseudorandom_certificates.py`, `code/verify_a05.py`: 100-audit-fit exploratory certificate experiment and independent Clopper–Pearson checks.
- `code/make_figures.py`, `code/build_manuscript_r3.py`: render plots and rebuild manuscript from the earlier R2 source; the latter depends on the R2 manuscript bundled here.
- `results/`: all A03 case-level validation/test scores, matched-budget dispositions and ties, A04 per-fit predictions/checkpoints, A05 row-level certificates, analysis tables, checksums and execution receipts.
- `figures/`: four independent plots derived from saved results.
- `r2_prior_release/`: original A02/R2 reproducibility package, including the earlier manuscript and per-case evidence. The A01 study is retained unchanged in the canonical RuFLEX repository.
- `REVIEWER_RESPONSE_R3.md`: detailed factual response to both reviewers, including what remains unresolved.
- `SHA256SUMS.txt`: content hashes of all the released files except the checksum manifest itself.

## Experimental evidence

### A01 — immutable original submitted study

Three UCI public datasets (AI4I, Bank Marketing, Wisconsin), five models and twenty fits per dataset–model cell (300 fits). A01 found high-confidence instability, but its validation-frozen stability review did not consistently lower risk. The only two directional effects arose in cells with unequal realized coverage; Bank Decision Tree also suffered from a machine-precision confidence tie. We **retain** those original results and their limitations. Original frozen artifacts: `research/a01_stability_aware_review/` in [RuFLEX](https://github.com/fims9000/RuFLEX).

### A02 — fixed-reference validation audit

Seven data regimes (three bundled public datasets plus four controlled synthetic regimes), five model families, 35 cells and 3,535 fits. It reports 6,125 validation case–model decisions, with 4,739 nominally certified (target agreement probability >= 0.90, 95% Bonferroni simultaneous level **within** each cell). The exploratory second split adds 1,414 fits in 14 Decision Tree/SGD cells. All A02 raw artifacts are in the prior-release directory, not silently rewritten into A01.

### A03 — new held-out equal-budget comparison

Four bundled public binary tasks (Iris, Wine, Digits and Wisconsin) and four synthetic separation/noise regimes; five model families; two stratified 60/20/20 splits; 80 cells, **2,480 actual model-fit calls** and **13,400 held-out case–model decisions**. Each cell has one fixed reference model and 30 auxiliary retrainings. Every review policy sees the same reference prediction and the same test instances; audit models never vote. At the prespecified primary target coverage of 0.90, all policies review exactly the same integer number of cases, using unlabeled top-k scores and deterministic label-blind ties.

| Review score | Calculation |
|---|---|
| Confidence-only | `1 - max(p, 1-p)` |
| Disagreement-only | `1 - fraction of 30 auxiliary fits matching reference class` |
| Combined | `1 - confidence + 0.5 * (1 - agreement)` |
| Dispersion | `1 - confidence + 0.5 * std(auxiliary class-1 probabilities)` |

For combined versus confidence-only at near-90% accepted coverage: **28 cells improved, 47 tied and 5 worsened**; unweighted cell mean risk difference **−0.005464** (−0.546 percentage points); Decision Tree mean **−0.018798** (−1.88 pp), Logistic Regression exactly tied in all 16 cells. Other budgets (target 80%, 95%) and 16 label-blind tie seeds were evaluated with pre-existing fixed scores. All statistics remain *descriptive* due to dependent cells, multiple comparisons and dataset reuse. Per-cell 2,000-replicate bootstrap intervals were computed with masks fixed and have **no** familywise multiplicity adjustment.

**Evaluation-design limitation:** top-k on the held-out batch guarantees exact budget **only for the batch**. It is an unlabeled transductive batch-ranking experiment; its results do not imply coverage control for one-by-one online predictions. We report this explicitly, not as a hidden deployment claim.

### A04 — extra fit budget, post-hoc

On the **already observed** A03 test partitions, independently retrained 32 Decision Tree/SGD cells at 5, 10, 20, 30 auxiliary-fit checkpoints, **992 fits** including references (some overlapping the configurations and seeds used in A03). A04 is a computational sensitivity test, not an extra independent final test. Example: ten audit fits yielded a mean reviewed-set Jaccard overlap with thirty fits of 0.904 for Decision Tree and 0.880 for SGD Logistic. This is a ranking observation, **not** enough for an A05-style 95% familywise certificate.

### A05 — fresh-seed class-repetition audit

Four public datasets, all five models, two splits: 40 cells, **4,040 fits** (fixed reference + 100 pseudo-randomly generated audit seeds per cell), **5,400 held-out decisions**. Exact one-sided Clopper–Pearson lower limits were Bonferroni-adjusted across held-out cases in each cell. **4,601** cases nominally met the replication target (probability >= 0.90, one-sided 95% *within-cell* simultaneous confidence). **184 certified predictions were incorrect**. A reproducibility certificate is **not** a correctness, calibration or safety certificate.

**Assumption to verify externally:** fixed PRNG streams are deterministic, and random_state values in scikit-learn are not themselves a mathematical demonstration of independent fitted-model draws. The frequentist probability interpretation assumes genuinely independent draws from a specified training-randomness distribution, fixed data/configuration, and a reference chosen before examining audit fits. This study is a transparent *conditional* empirical audit; it does not establish this statistical model experimentally or guarantee stability under data shift.

## Exact environment used

- CPython 3.13.5
- numpy 2.3.5, scipy 1.17.0, pandas 2.2.3, scikit-learn 1.8.0
- matplotlib 3.10.8, python-docx 1.2.0, pytest 9.0.2
- Operating system and BLAS/CPU may affect floating-point outputs and wall time. The release contains the exact case-level output and checksums for comparison; reproducing every floating-point bit on another machine is not guaranteed.

Set up, using Python 3.13:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-R3.txt
```

## Reproduce the saved results

Run commands from the **release root**. Reading the saved outputs is much faster than retraining.

```bash
# Minimal correctness / integrity checks, no model training:
python -m pytest -q code/test_a03.py
python code/verify_a03.py --protocol code/a03_protocol.json --parts results/split101 results/split202
python code/verify_a04.py
python code/verify_a05.py

# Read-only regeneration of summary and figures (changes only derived files):
python code/analyze_a03.py
python code/make_figures.py
```

To execute the model-training experiments anew, use *new output directories*; do not overwrite the frozen evidence under `results/`:

```bash
python code/a03_heldout.py --protocol code/a03_protocol.json --only-split 101 --out reruns/split101
python code/a03_heldout.py --protocol code/a03_protocol.json --only-split 202 --out reruns/split202
python code/a04_run_budget.py --out reruns/a04_budget
python code/a05_pseudorandom_certificates.py --protocol code/a05_protocol.json --out reruns/a05_certification
```

`verify_a04.py`, `verify_a05.py`, `analyze_a03.py`, `make_figures.py` by design inspect the fixed release tree; compare the rerun output manually or rerun these checks in a separate copied release tree, preserving paths. No A01 retraining or final-test access is required by R3 verification; the A01 study retains its own repository verifier.

## What is established, and what is not

- **Demonstrated:** confidence and repeatability are different axes; an independently fixed reference may be confidently wrong and repeatably wrong; on the tested held-out batches a fixed disagreement term often improved error capture at exactly matched review budgets, but sometimes harmed it.
- **Conditionally derived:** a deterministic score margin larger than twice a known uniform score drift bound preserves argmax; analogous class-threshold and sub-Gaussian score-drift conditions; a one-sided exact binomial lower bound conditional on independent training repetitions.
- **Not established:** a learned or empirically verified global score drift bound, new mathematical inequalities, simultaneous 95% coverage over all experiments, superiority on novel domains, operational streaming budget guarantees, safety/clinical validity, or human-review correctness/cost.

## Scientific provenance / anti-leakage

A01 is untouched. A02, A03 and A05 use deliberately different frozen reference strategies; their numbers must not be merged as though they were one randomized experiment. The A03 protocol was locally fixed before running its new test, but methods and dataset choice were informed by A01/A02. A04 explicitly reuses A03 results. The R3 manuscript and figures are a composition of archived measurements, not replacements for their immutable source tables. Never use final-test labels to tune or reorder the A03 candidate score; any future improvements require a freshly frozen experiment and independent new data.