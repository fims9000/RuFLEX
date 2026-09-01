# Study 01 results — RESULT FREEZE

The accepted V1.0.1 baseline was evaluated against locked manifest
`ec75f178661cd32e8c418461ac782ece3708fb5641fed51baf9b850cf4b18580`.
There were 52 systems and 764,098 declared-grid cases: 26 Mamdani and 26
zero-order Sugeno systems, 382,049 cases per family.

For the 760,042 cases where RuFLEX produced a defined output, cross-engine
conformance, independent trace reconstruction, and canonical round-trip each
passed exactly (maximum absolute cross-engine error 0.0). The remaining 4,056
cases are preserved negative evidence: 3,254 are RuFLEX no-rule exceptions
against pyfuzzylite `NaN`; 802 are RuFLEX no-rule exceptions where pyfuzzylite
returns a finite default. They are outside the declared no-rule MATCH scope and
prevent a universal-equivalence claim.

See `artifacts/locked/locked_study_results.json`, `tables/T01_locked_system_summary.csv`,
and `figures/F01_locked_system_max_error.svg`.
