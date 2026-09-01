# Post-freeze boundary diagnosis

The immutable frozen taxonomy is retained. Independent reproduction resolves all
4,056 negatives: 3,254 are literal zero activation with a nonfinite reference;
802 have `0 < activation sum <= 1e-12` and are rejected by RuFLEX's
`denominator <= 1e-12` policy while the reference is finite. The latter is an
undocumented numerical policy and a candidate V1.0.2 clarification issue. It
does not alter V1.0.1, tolerances, frozen verdicts, or original taxonomy.
