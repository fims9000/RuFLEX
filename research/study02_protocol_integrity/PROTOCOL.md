# Protocol (pre-freeze, native-executor revision)

No locked execution occurs until product, generators, mutations, oracle schema,
detector and baseline rules, metrics, severity policy and manifest are frozen.
The hidden oracle is evaluation-side only; detector modules must not import it.

## Frozen-method requirements

The subject is the archived V1.0.1 product, invoked through canonical
application services. The unit of independence is a matched scenario pair. A
clean/corrupt pair shares base data and differs only in `protocol_mutation`, as
validated by `core.pair_diff`. Prevention means a real canonical entry point
cannot persist invalid evidence; retrospective detection requires a product
validator, never a research mapping. BASIC_MANIFEST_AUDIT is independent and
deliberately minimal. Scenario counts, catch/prevention, clean false block and
warning, family/stage classification are scenario-level metrics; no p-values or
population-generalization claims are made. BLOCK targets are 100% only for
families classified supported before lock. Persistence/reopen applies where a
product-native object supports it. Misses, false alerts, provenance gaps and
unsupported observability are retained under the declared failure taxonomy.

The executor, all generators/mutations, subject adapter, pair validator,
baseline, metrics/configuration and locked specifications are hash-bound in the
manifest. Result freeze will preserve raw evidence and permit only derived
tables/figures. Allowed claims concern this controlled observable scope, never
guaranteed leakage-free science or arbitrary semantic detection.

## Locked native execution

The primary locked scope is V01, V06 and V07 only: 20 independently seeded
matched pairs per family (60 pairs, 120 scenario identities). Every pair is
compiled before authorization into separate clean and corrupt
`ExecutionAttemptContract` values in
`artifacts/manifests/locked_execution_plan.jsonl`. A contract names the exact
Product V1.0.1 application entry point, allowed and forbidden source roles,
expected artifact, persistence obligation and an evaluation-reference ID. That
reference ID is never read by the product adapter.

Clean V01 trains through `train_model`; its persisted run must state train-only
normalization. Its corrupt counterpart sends the forbidden fit role to the
public service boundary; V1.0.1 has no supported path that can consume it, so a
train-only artifact is structural prevention, not detection. V06 and V07 clean
operations use a validation Evaluation. Their corrupt attempts pass a
final-test identity where a validation Evaluation is required; rejection and
absence of the policy/calibration artifact constitute firewall prevention.

The post-authorization executor verifies product/archive, protocol, manifest,
pair-plan hashes and dependency resolution; executes both counterparts; runs
the independent BASIC_MANIFEST_AUDIT; and appends one raw row per scenario. It
is restart-safe: stable scenario IDs already present in the raw file are not
executed again. Before authorization it only supports `--validate-plan` and
must refuse scientific execution.

`PREVENTED_STRUCTURALLY` and `PREVENTED_BY_FIREWALL` are prevention outcomes.
They are never relabelled as retrospective detection. BASIC MANIFEST AUDIT
declares only its own simple metadata rules and never calls RuFLEX integrity
functionality. Ground truth is joined only after execution by scenario ID. The
historical generic 10/10 report is retained but marked `SUPERSEDED_HARNESS_ONLY`;
it is excluded from primary aggregation.

## Materialization and authorization binding

Each frozen pair is materialized from its stored generator family, seed and
generator parameters before any Product service is invoked. The materialized
CSV input has a canonical hash embedded in both clean/corrupt contracts and in
the plan. Re-materializing a plan must reproduce that hash; clean and corrupt
members must have the same base input hash. A different frozen seed is expected
to generate a different input hash, so pair identifiers alone are never used as
an independence claim.

The manifest is immutable. Authorization is a separate, non-frozen record at
`.agent-state/STUDY02_TEST_AUTHORIZATION.json`; it must name an `AUTHORIZED`
status and exactly match the frozen Product SHA, protocol SHA, manifest ID and
execution-plan SHA. Missing or mismatched records refuse execution. Creating or
changing that record cannot modify any frozen byte.
