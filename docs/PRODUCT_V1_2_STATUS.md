# Product V1.2 status

Target: `1.2.0-rc1` on `feature/v1.2-unified-runtime`.

## Implemented runtime foundation

- immutable runtime identities/snapshots and typed error boundary;
- built-in Flat Neuro-Fuzzy, linear, Decision Tree, Random Forest and Gradient
  Boosting adapters under the common fit/predict contracts;
- core-owned generic adapter training persistence with train-only preprocessing
  and no TEST input in `FitRequest`;
- read-time compatibility for legacy run evidence and persisted runtime fields
  for new runs/studies/jobs/explanations/checks;
- runtime introspection API, external entry-point fixture coverage, model matrix,
  registry-routed explanation creation and Studio primary-action inventory.

## Still required before RC completion

The release remains in progress until full regression/browser/archive QA,
accessibility baseline, complete runtime compatibility matrices and the final
release receipt are generated from exact HEAD. This document must not be used
as a scientific-result claim.

## Boundaries retained

V1.2 does not alter frozen research results, DatasetContract scientific roles,
the final-test firewall, Stability Gate semantics, or XAI epistemic limits.
