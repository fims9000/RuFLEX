# Changelog

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
