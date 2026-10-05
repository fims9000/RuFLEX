# Changelog

## 1.3.0-alpha.0 — active local development baseline

This is a development checkpoint, not a stable release. It consolidates
governed dataset/split/preprocessing evidence, adapter-routed runtime replay,
job lifecycle provenance, and persisted evidence navigation in Studio.
Validation and known scientific limitations are recorded in
`docs/PRODUCT_V1_3_STATUS.md`.

## 1.2.0-rc1 — local runtime release candidate

### Added

- Typed adapter identities, immutable runtime snapshots and read-only runtime
  introspection for model adapters, explainers, validators and backends.
- Core-owned generic `FitRequest`/`FitResult` persistence for built-in and
  trusted installed entry-point adapters, with a registry-driven matrix.
- Persisted runtime provenance for new runs, studies, jobs, explanations and
  explanation checks, with read-time legacy compatibility.
- Stable Studio primary action identifiers and a machine-readable inventory.

### Unchanged boundaries

- Dataset roles, train-only preprocessing, final-test firewall, Stability Lab
  semantics and frozen research artifacts are unchanged.

## 1.1.0 — unreleased local release candidate

### Added

- A single inspectable runtime contract for built-in model families, supported
  tasks, accepted parameters, XAI applicability, evidence objects and limits.
- Dynamic Studio model selection and parameter controls driven by that contract.
- Typed capability API endpoints: `/api/models`, `/api/capabilities`, and
  fail-closed individual model/plugin lookups.
- Strict trusted package entry-point discovery for `ruflex.plugins`.
- GitHub CI checks for backend, frontend, core Studio E2E and fresh tracked
  source-archive smoke validation.

### Changed

- The capability contract now reports only tasks that canonical training
  adapters actually support; unsupported multiclass training is not advertised.
- Source-only A01 audit verification fails closed when its separate frozen
  artifact store is unavailable, rather than treating absence as a successful
  scientific audit.

### Unchanged boundaries

- Frozen S01/S02/A01/S03 records are historical scientific evidence and are
  not product-version inputs.
- Validation/final-test separation, Stability Lab semantics, XAI limitations
  and Assurance claim boundaries are unchanged.

## 1.0.1

Product V1.0.1 baseline. See the historical release receipts in `docs/`.
