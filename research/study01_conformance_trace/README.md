# Study 01 — computational conformance and trace reconstruction

This isolated research package studies the frozen RuFLEX Product V1.0.1
source archive. It is not product code and must not change RuFLEX inference
behavior.  Its three evidence streams are: explicitly derived micro-oracles,
pyfuzzylite 8.0.6 where semantics genuinely match, and canonical JSON
round-trip checks.

Run development checks with the isolated reference interpreter (kept outside
the research package so no virtualenv/cache is exported):

```bash
PYTHONPATH=src:. /home/lebedeffson/.cache/ruflex-study01-reference-env/cpython312-pyfuzzylite-8.0.6/bin/python -m pytest research/study01_conformance_trace/tests -q
```

The locked final suite must not be run until `PROTOCOL.md` is frozen and
reviewed.  MATLAB is optional and is reported as NOT_AVAILABLE when a licensed
engine is absent.
