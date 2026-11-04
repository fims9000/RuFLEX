# R6 source amendment and provenance

The new R6 protocol `PROTOCOL_R6.json` was locally frozen before any new sunspot and macroeconomic model fits; it is not externally registered. Historical A06/R5 outcomes were already available and are retrospective.

During initial verification of the new temporal run, code used deterministic tie handling and the declared stage splits. After the first completed run, source was amended solely to store **per-case labelled certification receipts** and to move the in-memory construction of final-stage error labels until after certification was computed. No model, preprocessing, split, seed, objective, review score, threshold, label, statistical method, hyperparameter or outcome was changed.

The five saved numeric CSVs (case-level final, threshold scores, certification cases, certification summary, final results) were subsequently regenerated with the amended code in a second full 136-fit run, and their SHA-256 checksums match the archived first output byte for byte. The amended executable is the reproducibility source shipped with this release. This is a post-execution technical amendment, **not** a new pre-registered protocol.

A prior test assumed deterministic hash-tie selection would always deliver exactly the *expected* share of tied review cases. That assertion was invalid because a deterministic hash cutoff realizes a count that can differ from its expectation. The test was corrected to check the frozen probability and deterministic replay; no production mechanism was altered.
