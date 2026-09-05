# RuFLEX V1.1 product status

Status: **local release candidate in verification**.

## Scope

V1.1 strengthens the live Studio product without rewriting scientific studies:

- one runtime source of truth for built-in model capability metadata;
- dynamic model selection and configuration in the React Studio;
- strict, declared plugin entry-point discovery;
- typed capability negotiation and fail-closed unavailable operations;
- CI, browser-route and fresh-source archive release checks.

## Product contracts

`GET /api/models` returns the canonical declarations. `GET /api/models/{key}`
resolves a concrete training key, including `logistic_regression` and
`linear_regression` through the `linear` adapter. `GET /api/capabilities`
returns the same model declarations in a versioned envelope.

The contract intentionally distinguishes availability from applicability. A
registered adapter can be available while a particular operation is not
applicable to its task, persisted artifact, or evidence route.

## Verification policy

- Product tests use synthetic/local project fixtures and may run from a fresh
  tracked source archive.
- The full A01 Phase 1.5 scientific audit requires its separately retained,
  non-source model/evidence artifacts. Without them the audit raises rather
  than producing a partial result; the source-only regression test verifies
  this failure boundary.
- Browser QA must exercise actual React Studio routes through FastAPI. A build
  alone is not considered UI acceptance.

## Scientific boundaries

V1.1 does not claim that capability negotiation proves model quality, that XAI
is causal, that stability review is universally beneficial, or that a software
boundary detects every possible leakage route. Frozen studies remain available
under `research/` with their own provenance and limitations.
