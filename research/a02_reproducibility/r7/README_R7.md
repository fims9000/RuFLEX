# R7: Group-Respecting Sequential Review Evidence

This is a new **exploratory research extension** following R6; it is not a conference acceptance, a clinical deployment validation, or a new mathematical discovery of standard e-processes. The R6/R5/A01 results remain unchanged in their parent branches.

## Materials

- `PROTOCOL_R7.json`: frozen local plan. SHA-256 `fb047cc115129cf66b00d9ddd9206463d88cd9580beaea8ba1c7fd47932edbac` recorded in GitHub *before model fits*. `SOURCE_AMENDMENT_001.json`: fix of year-column pandas indexing before any fit.
- `HYPOTHESIS_R7.md`, `RESULTS_R7.md`, `SOURCE_AMENDMENT_002.md`: claims, post-freeze power-audit correction, results and caveats.
- `code/evidence.py`: switch accounting, deterministic label-blind ties, bounded-gain mixture e-process and correlated-group simulator.
- `code/power_audit.py`: test whether the chosen e-process can even cross the declared alpha threshold within the available number of groups.
- `code/run_panel.py`: all 64 fixed-reference and retraining fits on the bundled World Bank fertility panel, chronological splits, frozen supervised risk scores, label-free threshold calibration and annual evidence.
- `code/run_simulations.py`: 1,000 null-world Monte Carlo replicates.
- `code/verify_panel.py`: independent replay of all stored review masks and costs from frozen scores, without retraining.
- `code/benchmark_baselines.py`: post-hoc raw confidence/disagreement controls (NOT a preregistered R7 comparison).
- `code/figures_r7.py`, `code/analyze_panel.py`: figures and descriptive checks.
- `code/test_evidence.py`, `code/test_panel.py`: 13 deterministic positive/negative tests.
- `results/panel`, `results/simulation`, `results/analysis`: case-level evidence and SHA receipts.
- `article`: the stand-alone R7 research note DOCX/PDF, not an IEEE camera-ready submission.

## Reproduction

Use Python 3.13 and versions pinned in `requirements-R7.txt`. The new data are bundled with statsmodels; no web fetch is needed.

```sh
python -m pip install -r requirements-R7.txt
cd code
python -m pytest -q test_evidence.py test_panel.py
python power_audit.py
python run_simulations.py --out ../results/simulation_replay
python run_panel.py --protocol ../PROTOCOL_R7.json --out ../results/panel_replay
python verify_panel.py --results ../results/panel_replay --protocol ../PROTOCOL_R7.json
python analyze_panel.py --results ../results/panel_replay --out ../results/analysis_replay
```

Compare the four frozen CSVs listed in `results/panel/R7_RECEIPT.json` by SHA-256. The source code (not a post-hoc rewritten description) is uploaded to the R7 branch of RuFLEX. Output paths/elapsed seconds in receipts may differ, but the declared CSV outputs should remain identical.

## Critically important inference restriction

For each *year-aggregated* gain `X_t` in [-1,1], the mixture e-process has a standard Ville 5%-level crossing guarantee only under a fixed policy and a **conditional-mean null at each year**. Aggregation by year does **not by itself prove** that assumption. In the synthetic simulation the years really were generated independently; in the historical fertility panel there is no such verification. The per-country e-process is invalid under the constructed common-shock null and may be invalid in the real panel.

The six-year R7 annual monitor could never reach its e-value threshold even under maximum gains. This power failure was discovered after the protocol freeze and must be reported. None of the four "not promoted" decisions can be interpreted as a tested rejection of the augmented risk ranker. A deliberately conservative policy and an informatively validated policy are different.

The cost uses an accounting **proxy** (automated errors + 0.25 times review decisions). Human reviewer performance, workload and prices were not observed. The World Bank fertility values are observational estimates, not independent randomized institutional measurements.

## References / data lineage

- World Bank WDI fertility (fertility rate, births per woman), packaged by statsmodels; https://www.statsmodels.org/stable/datasets/generated/fertility.html.
- Waudby-Smith and Ramdas, bounded mean betting; https://doi.org/10.1093/jrsssb/qkad009.
- Timans et al., continuous risk monitoring under unknown shifts; https://proceedings.mlr.press/v286/timans25a.html.
- Franc, Prusa and Voracek, reject-option classifiers; https://www.jmlr.org/papers/v24/21-0048.html.
