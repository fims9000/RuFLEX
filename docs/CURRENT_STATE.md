# RuFLEX current state

This is the short technical passport for the current Product V1.0.1 state.
Historical protocols and QA receipts retain the state at their original
freezes; use this file and the root [README](../README.md) for the current
platform summary.

## Reference

- **Product:** RuFLEX V1.0.1
- **Product reference commit:** `8bbd46b2a349db88b98f8cbbbe95e18650c17569`
- **Reference source archive:** `RuFLEX_PRODUCT_V1_0_1_SOURCE_8bbd46b.zip`
- **Archive SHA-256:**
  `382e06f3aab0689269498b14bf8496bf15dabeac62bbe691c5aef323ab0cd28c`

The reference commit identifies the product and frozen-evidence state. A later
documentation-only commit does not revise the source subject or any frozen
study.

## Architecture and implemented product surface

RuFLEX is a local-first React/TypeScript Studio over a FastAPI boundary and
canonical persisted Python domain objects. It supports fuzzy, neuro-fuzzy and
classical ML workflows with explicit DatasetContracts, train-only
preprocessing, training, validation evaluation, explainability, stability
analysis, selective review, final-test separation, lineage, assurance and
inspection-first verification bundles.

- `frontend/` — React/TypeScript Studio.
- `src/ruflex/` — domain model, application services, persistence, FastAPI and
  SDK.
- `src/ruanfis/` — neuro-fuzzy backend.
- `tests/` — product, integrity, persistence and browser-route tests.
- `docs/` — product and scientific documentation.
- `research/` — protocols, frozen configurations, result artifacts and
  limitations.

The Studio is the primary UI. Legacy Streamlit-oriented material is historical
or compatibility context, not the Product V1.0.1 entrypoint.

## Frozen research status

- **Stability Lab RC1:** complete historical checkpoint.
- **Stability Lab RC2:** complete; it strengthens RC1 by persisting
  selected-run agreement separately from majority consensus and binding the
  operational gate to an exact raw validation-derived decision threshold.
- **Study 01:** completed and frozen within its declared computational
  conformance and trace-reconstruction scope. See
  [`research/study01_conformance_trace/`](../research/study01_conformance_trace/).
- **Study 02 R2:** completed and frozen within its declared protocol-integrity
  scope. See [Study 02 status](research/STUDY02_STATUS.md).
- **A01 stability-aware review:** final confirmatory result frozen. It contains
  300 fixed fits over 15 dataset/model cells; H3 is `SUPPORTS_H3` in one cell,
  `CONTRADICTS_H3` in one, and `INCONCLUSIVE` in 13. See
  [`research/a01_stability_aware_review/`](../research/a01_stability_aware_review/).

## Interpretation limits

Stability-aware review is model- and data-dependent. The final-test boundary
is a product workflow control, not a universal leakage detector. Explanation
replay and consistency checks do not establish causality. RuFLEX does not
replace certification, domain validation or expert responsibility.

## Where to inspect evidence

- [Product demonstration](product/PRODUCT_V1_DEMONSTRATION.md) and
  [evidence manifest](product/PRODUCT_V1_EVIDENCE_MANIFEST.md) document the
  real Studio route and persisted objects.
- [Stability Lab technical note](product/STABILITY_LAB.md) describes the
  product semantics.
- [RC2 QA receipt](STABILITY_LAB_RELEASE_QA.md) is historical release
  provenance; its former A01 pre-freeze wording is not the current A01 status.
- `research/` contains the study protocols, amendments, result freezes and
  scope-specific limitations needed for scientific inspection.
