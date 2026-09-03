# RuFLEX Product V1 RC2 status

> **Historical document.** It does not describe the current Product V1.0.1
> state. See [README](../README.md) and
> [docs/CURRENT_STATE.md](CURRENT_STATE.md).

The canonical product is the React/TypeScript Studio over FastAPI and persisted
Python domain objects. Streamlit remains legacy-only.

RC2 evidence includes validation-only calibration/threshold and selective
review policies, persisted BehaviorSpecs, cross-run explanation reproducibility,
Exhaustive Lab, semantic AssuranceCase gates, lineage and inspection-first
VerificationBundles. Assurance is a set of independent PASS/WARN/FAIL/NOT
AVAILABLE gates, never a trust score. Final test is opened only by explicit
frozen-policy evaluation.

Release status is determined only by the fresh-release-archive gate documented
in `docs/PRODUCT_V1_RELEASE_QA.md`; developer-checkout tests are not release
evidence by themselves.
