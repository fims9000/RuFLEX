# R6 — The Hidden-Shift Limit of Reproducibility-Aware Review

**Research release, 4 November 2026.** This is a new methodological and exploratory project, not an accepted publication or proof of real-world safety. Its base is the unchanged R5 revision of RuFLEX; historical A01–A06 outcomes are not refitted or represented as independent R6 confirmations.

## Main scientific result

The incremental value of an audit-only retraining signal is determined by **which frozen review decisions change** and by the **error probabilities in precisely those switched cases**, not by overall disagreement. We derive an exact paired accounting identity, an observable non-identification counterexample under conditional-label drift, a sharp conditional-risk shift radius, and an IID-only conservative confidence certificate based on independent labels.

Two populations may have exactly the same observable confidence / disagreement distribution, but opposite signs of the incremental review value. The example gives +0.050 source gain and -0.125 target gain at hypothetical review price 0.25. A source-only lower-confidence check can become **more likely to authorize the harmful target rule** as the source calibration sample grows. This is a controlled finite-world counterexample, not an estimate of frequency in deployment.

### Data lineage and epistemic limits

* Historical A06 and R5 outputs **already inspected before R6**: 40 correlated cells in streaming and 40 in batch review; reconstruct frozen decisions and verify them against A06 summary records. Data not treated as confirmatory.
* Mechanistic simulation: five known-risk worlds, 100 / 400 / 1600 / 6400 independent source-label samples, 200 repeated certifications per point (4,000 episodes). No models trained; known-world risk is not assumed to estimate actual downstream shift.
* New temporal challenge: annual sunspot activity and quarterly U.S. macroeconomic data, sourced from packaged statsmodels v0.14.6 (actual historical data), four model families per dataset, one reference plus sixteen auxiliary retrainings: **136 fit calls**. Five strictly chronological partitions for base fitting, risk fitting, unlabelled threshold calibration, separate labelled policy certification, and final holdout. Exactly **8 correlated model cells**, with 3 cost gains / 2 losses / 3 ties and no certified switch (0/8). The certification intervals have a mathematical guarantee only for IID calibration/evaluation data; these time series do not establish IID, so the guard here is a diagnostic, not a deployment guarantee.

The per-case objective assumes perfect removal of an automatic prediction on review and charges review a **hypothetical cost** `lambda=0.25`. We have not measured human review accuracy, cost, operating capacity, drift bound, or causal effects. Never interpret the conditional-risk transport bound as empirical evidence that its assumptions hold.

## Exact release layout

* `code/switch_theory.py`: exact paired policy-switch identity, transport sensitivity, exact confidence certificates.
* `code/audit_policy_switches.py`: retrospective A06/R5 case-level audit, checks published frozen A06 masks and counts.
* `code/compute_cost_frontier.py`: review cost dominance for every possible lambda in `[0,1]` for frozen decisions.
* `code/simulate_switch_worlds.py`: known-risk counterexamples and calibration-size sensitivity.
* `code/run_new_temporal.py`: original 136-fit chronological challenge, separate 5-stage split.
* `code/verify_r6.py`: independent new-temporal score/threshold/mask/certificate replay and hashes.
* `code/test_switch_theory.py`, `code/test_temporal.py`: positive and adversarial protocol tests.
* `code/figures_r6.py`, `code/build_r6_manuscript.py`: deterministic rendering.
* `results/`: experiments, manifest, policy-switch summaries, 4,000 simulation episodes and case-level chronological outputs. `results/new_temporal_replay/` is a separate byte-identical repeated run.
* `historical_evidence/`: original R4/A06 per-case historical experiment evidence and R5 CO2 case-level evidence used **only for retrospective replay**, kept as provided, not modified. The original A01/older studies remain in previous release branches.
* `article/`: R6 manuscript in DOCX and PDF plus three figure PNGs.
* `PROTOCOL_R6.json`, `PROTOCOL_R6_FREEZE.json`: local protocol and original hash; no external preregistration claim.
* `SOURCE_AMENDMENT_R6.md`, `HYPOTHESIS_R6.md`, `RESULTS_R6.md`, `REVIEWER_RESPONSE_R6.md` and SHA-256 content manifest.

## Reproduction from the extracted ZIP

Run from the extracted root directory (on Unix):

```bash
python -m pip install -r requirements-R6.txt
cd code
python -m pytest -q test_switch_theory.py test_temporal.py
python verify_r6.py --protocol ../PROTOCOL_R6.json --results ../results/new_temporal
python audit_policy_switches.py \
  --a06-root ../historical_evidence/ACDSA_R4_complete_research_package \
  --r5-case-level ../historical_evidence/R5_CASE_LEVEL_TEMPORAL.csv \
  --out ../results/retrospective_replay
python compute_cost_frontier.py --help
python simulate_switch_worlds.py --help
python run_new_temporal.py --help
```

**For the complete fresh temporal training replay**, see `python code/run_new_temporal.py --help` for exact arguments and specify a new output directory; compare five core CSV SHA-256s to the frozen `results/new_temporal/` files, not the receipt containing output paths and provenance. New temporal case-level verification consumes only saved predictions; it does not itself train.

The top-level `SHA256SUMS.txt` contains hashes of all release files except itself; check using `sha256sum -c SHA256SUMS.txt`. The ZIP can be re-extracted to an empty folder and verified. An unqualified `SOURCE_PASS` is not a scientific p-value.

## Versioning

Parent research PR: https://github.com/fims9000/RuFLEX/pull/8
R6 branch / PR: see GitHub project once published. Local freeze SHA-256 of `PROTOCOL_R6.json`: `b5be179434b89f3827df797463069f18d45dad14a25243678bf17e871d4bf15d`.

## Scientific novelty boundary

The switch identity, epsilon-rho transport bound, the two-population non-identification construction, and binomial Clopper-Pearson intervals are derived from standard probability and decision theory. They are **not universally novel mathematical theorems**. The research contribution under evaluation is the mechanistic, review-switch-localized characterization of fixed-reference retraining audits, quantification of fragility, explicit demonstration of harmful source-only certification under invisible conditional shift, and guarded evaluation that can correctly report **no reliable evidence**.
