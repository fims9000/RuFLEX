# S03 Phase 0.1 pre-execution implementation audit

This audit was performed before materializing an S03 benchmark dataset, fitting
an S03 model, generating an S03 benchmark explanation, or observing any
detection outcome. `benchmark_results_seen`, `benchmark_explanations_generated`
and `scientific_outcomes_seen` are all `false`.

The historical Phase 0 plan is retained unchanged. Its implementation audit
found that several declared subtypes were aliases of another mutation: M1b
changed an artifact hash instead of `run_id`; P1b lacked a feature-order
contract field; S1b changed sample identity rather than target; severity did
not change sign-flip/permutation magnitude; permutation shuffled records rather
than feature-to-value mappings; and L1/ADV were not semantically distinct fresh
explanation operations.

Phase 0.1 corrects those pre-result conformance defects. `ExplanationContract`
schema v2 now persists feature-order identity and exact generation parameters,
while v1 persisted explanations remain readable and are explicitly marked as
legacy provenance by product checks. M1b is specified to use an existing,
deterministically mapped alternate run at execution time; its one declared
changed field is still only `run_id` even if downstream checks show multiple
consequences.

L1 is now a product-native, fresh reduced-budget explanation call; occlusion is
`NOT_APPLICABLE` because it has no declared fidelity budget. ADV permutes only
attribution values across fixed feature records and preserves the structural
fields declared in the corruption specification. Artifact pairs are generated
once and evaluated in three validator modes, preventing pseudo-replication.

Quantus is an optional research-only dependency pinned in the frozen spec. The
current isolated environment has no `quantus==0.6.0`, so the preflight state is
`NOT_AVAILABLE`; this is coverage information, not a successful or failed S03
benchmark result.
