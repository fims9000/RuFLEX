# RuFLEX Product V1.0.1 — centroid-semantics correction

V1.0.1 is a pre-test numerical-semantics correction discovered during Study 01
DEV validation. RC2.1 used an undocumented inclusive 401-node centroid grid.
V1.0.1 makes the sampling convention explicit and defaults newly created
Mamdani FIS models to midpoint cells, compatible with the declared FuzzyLite
centroid convention.

Existing projects without an explicit sampling value migrate to inclusive nodes
and retain RC2.1 numerical behavior. The two modes have different semantic
hashes and every new Mamdani trace records its complete centroid configuration.

The RC2.1 archive and receipt remain historical provenance. V1.0.1 is the new
Study 01 candidate baseline; no locked Study 01 case was executed before this
correction.

## Release verification

- Fresh-source Python suite: 122 tests passed.
- `compileall`: passed.
- Frontend unit test, Vite production build, Storybook build: passed.
- Fresh-source Playwright suite: 24/24 passed using the pinned full Chromium
  visual-baseline executable.
- Verification bundles now include declarative FIS revision JSON, including
  centroid sampling semantics, while excluding executable artifacts.
