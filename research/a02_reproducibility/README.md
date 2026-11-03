# A02 — a priori decision reproducibility

This is an **independent exploratory extension** of A01, developed in response to the two reviews of ACDSA 2027 paper #1326, *When High Confidence Is Not Reproducible*. A01's 300 fits and frozen final-test conclusions are **not changed**.

## Estimand and guarantee

Fix the training set, configuration, class threshold, a case x, and one reference predictor before running the audit. Let S be fresh training randomness. The estimand is:

p_ref(x) = P_S[h_S(x) = h_ref(x) | fixed data, configuration, reference].

This is a probability of **decision agreement**, not correctness, calibration, or out-of-distribution reliability.

For n genuinely independent retrainings with k agreements, `certificates.py` computes the exact one-sided Clopper–Pearson lower confidence bound. Bonferroni correction across m fixed cases in one dataset–model cell uses alpha/m. At confidence 95%, a case is designated certified for replication probability >= 0.90 only if its adjusted lower limit is >= 0.90.

Important: a fixed list of software PRNG seeds does **not** itself prove independence under an assumed training-randomness law; certificate validity is conditional on that sampling assumption. The original A01 validation-F1-selected reference and its remaining 19 runs cannot automatically be reused as an IID audit.

The elementary deterministic sufficient condition `top-two score gap > 2 epsilon` requires an independently justified global score perturbation bound. Observed maximal drift is not such a bound.

## CLI

```bash
python -m pip install -r requirements.txt
python -m pytest -q test_certificates.py
python certificates.py --reference fixed_reference.csv --calibration new_fits.csv \
  --seeds 10000:10100 --target 0.90 --alpha 0.05 --correction bonferroni \
  --output audit.json
```

Reference CSV: `case_id,reference_class,reference_seed`. Calibration CSV: `case_id,seed,prediction`. Missing/duplicate seeds or cases, and reused reference seeds, raise errors.

## New exploratory benchmark

A separate, reproducible companion bundle contains `benchmark.py`, `report.py`, the datasets/protocol details, cell-level and case-level CSV outputs and a two-page research addendum. The new 7 data regimes x 5 model families x 101 fits produce **3,535 model trainings**. The A02 validation audit has **6,125 case–model pairs**, of which **4,739** meet the 90% replication target at nominal 95% familywise confidence **within each dataset–model cell**; **242/4,068** high-confidence case–model pairs have cross-run agreement below 80%.

These are exploratory, fixed-seed observations, not a second A01 confirmatory final-test result, and not a universal prediction guarantee. Reproduction requires independently running the companion `benchmark.py` rather than copying the aggregate numbers above.

No ACDSA acceptance, new final-test superiority, or mathematical novelty from standard confidence bounds is claimed.
