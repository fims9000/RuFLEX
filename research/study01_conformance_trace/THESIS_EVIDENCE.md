# Study 01 thesis evidence

| Claim | source / metric | allowed wording | forbidden wording | limitation |
|---|---|---|---|---|
| C1 defined-output conformance | `locked_cases.csv.gz`; 760042/760042, max error 0 | Exact agreement in declared defined-output scope | universal equivalence | no-rule excluded |
| C2 trace reconstruction | raw cases; 100% defined outputs | traces reconstruct independently | causal explanation | declared traces only |
| C3 canonical round-trip | raw cases; 100% defined outputs | canonical JSON preserved evaluated behavior | arbitrary file interoperability | canonical JSON only |
| C4 boundary evidence | diagnostics; 3254 zero + 802 cutoff | no-rule policy is negative evidence | hidden pass/tolerance result | no population claim |
| C5 legacy centroid DEV finding | legacy diagnosis artifact | inclusive vs midpoint differs numerically | post-test tuning | DEV-only provenance |

## Allowed claims

- For the declared midpoint-cell Mamdani and zero-order Sugeno semantic
  intersection, every case with a defined RuFLEX output matched the pinned
  pyfuzzylite 8.0.6 reference exactly in this locked matrix.
- Native traces were independently reconstructed and canonical declarative
  JSON round-trips preserved evaluated behavior for every defined-output case.
- The result is bound to the V1.0.1 archive, frozen protocol, and locked
  manifest listed in `THESIS_NUMBERS.json`.

## Forbidden claims

- No universal RuFLEX/FuzzyLite equivalence claim.
- No no-rule/default-policy equivalence claim.
- No claim about MATLAB, arbitrary membership functions/operators, symbolic
  continuous integration, training performance, causal explanation, or formal
  verification.

The negative no-rule observations are first-class result evidence, not removed
or converted through tolerance.
