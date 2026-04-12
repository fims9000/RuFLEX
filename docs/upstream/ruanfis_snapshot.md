# Vendored `ruanfis` Snapshot

- upstream repository: `https://github.com/lebedeffson/deep-neuro-fuzzy.git`
- vendored commit: `ec7afdaf54dd35caddd0491d1bd90a0d07822689`
- purpose: keep a local, controllable deep fuzzy backend snapshot inside `RuFLEX`

The copy under `src/ruanfis` should stay as close to upstream as possible.
RuFLEX-specific behavior belongs under `src/ruflex`, not inside the vendored backend,
unless a compatibility fix is truly unavoidable.
