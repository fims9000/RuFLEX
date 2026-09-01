# Limitations at protocol freeze

- The primary claim is restricted to the declared semantic intersection.
- The comparator is limited to the isolated CPython 3.12.12 / NumPy 1.26.4 /
  pyfuzzylite 8.0.6 environment captured in `config/environments.json`.
- MATLAB is not available in this environment.
- V1.0.1 midpoint-cell centroid has DEV-only M01 agreement with pyfuzzylite;
  this does not establish arbitrary Mamdani or continuous-model equivalence.
- Legacy inclusive-node centroid remains a documented numerical-discretization
  difference and is not converted to a pass by tolerance.
- No training-quality claim, human evaluation, or formal verification claim
  exists.
- The locked suite now supplies computational evidence only. It contains 4,056
  no-rule cases: 3,254 subject-exception/reference-NaN cases and 802
  subject-exception/reference-finite cases. Therefore it does not support
  universal RuFLEX/pyfuzzylite equivalence or no-rule-policy equivalence.
