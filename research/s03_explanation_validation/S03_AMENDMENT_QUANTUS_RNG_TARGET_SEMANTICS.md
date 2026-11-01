# S03 Amendment: Quantus RNG and contract-relative target semantics

This amendment was discovered after the immutable R6 CLEAN freeze and before
the first corrupt artifact. R6 CLEAN contracts, models, samples, corruption
universe, metric inventory, directions, epsilon, validator rules and
statistical plan remain unchanged. No corrupt outcome had been generated or
viewed.

Quantus 0.6.0 does not accept the frozen study seed as a constructor argument.
For each `(clean_artifact_key, metric_name)`, R6 now derives
`uint32(first_32_bits(SHA256("S03|R6|3003|" + clean_artifact_key + "|" + metric_name)))`.
The executor snapshots, seeds and restores Python, NumPy, PyTorch CPU and,
when active, CUDA RNG state. Every corrupt child of that CLEAN parent uses the
same metric seed, implementing common-random-number pairing.

Quantus evaluates the model declared by the contract: `resolve(contract.run_id)`.
Thus an artifact-SHA swap remains evaluated against its unchanged declared run,
while an M1 run-identity swap is evaluated against the swapped declared run.
For binary product explanations Quantus output class is fixed to positive class
`1`, because `ExplanationContract.prediction` is the persisted positive-class
probability. This is never chosen from results.

FaithfulnessCorrelation requires a compatible target prediction adapter.
MaxSensitivity additionally requires that the persisted explainer can be
replayed on the declared target. Incompatible swapped-run/explainer routes are
`NOT_APPLICABLE`, not failures. A Quantus assertion, non-finite score or other
route rejection is `NOT_AVAILABLE`, never detection.
