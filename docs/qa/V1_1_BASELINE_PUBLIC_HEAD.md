# RuFLEX V1.1 baseline — public product subject

## Subject

- Public reference commit: `b8bc941a22135287ef4ddeec6e81002eb4f84980`
- Working branch: `feature/v1.1-capability-runtime-product-hardening`
- Working-tree source changes at baseline: none. Existing article-package
  modifications were pre-existing user work and are outside the V1.1 scope.
- Platform: Linux `7.1.9-arch1-2` x86_64; Python `3.14.7`; Node `v26.7.0`;
  npm `12.0.2`.

## Results before V1.1 implementation

| Check | Result | Evidence / limitation |
| --- | --- | --- |
| Backend full suite, provisioned project runtime | FAIL | First failure is `tests/test_a01_phase1_5_scientific_freeze.py`: it expects ignored A01 Phase 1 project artifacts under `research/a01_stability_aware_review/artifacts/phase1-projects/`. The clean public source does not contain them. This is recorded, not skipped or weakened. |
| Backend compile | PASS | `PYTHONPATH=src /home/lebedeffson/Code/venv/bin/python -m compileall -q src/ruflex` |
| Clean frontend install | PASS | `frontend/npm ci`; 0 reported vulnerabilities. |
| Frontend unit baseline | PASS | One existing Node API-client test. This small coverage is a V1.1 gap, not sufficient frontend assurance. |
| Vite production build | PASS with warning | Existing production bundle exceeds the 500 kB chunk warning threshold. |
| Storybook production build | PASS with warning | Existing Storybook bundle exceeds the 500 kB chunk warning threshold. |
| Clean Python install | INCONCLUSIVE | `python -m venv .venv` and `pip install -e '.[dev,studio]'` began a fresh dependency installation but the Torch wheel transfer stalled after 554,623,549 bytes. The temporary installer was stopped; this is not a clean-install PASS. |

## Baseline interpretation

Historical RC2/A01 receipts are not used as proof that this public subject is
green. V1.1 must preserve frozen research evidence while making release QA
self-contained or explicitly packaging the required non-source evidence for
the checks that need it.
