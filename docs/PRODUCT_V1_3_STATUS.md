# RuFLEX Product V1.3 Alpha status

Target branch: `feature/v1.3-data-governance-runtime`.

## Implemented in the current development baseline

- persisted `SplitContract` evidence for random, group, temporal and declared
  identity/holdout split families;
- persisted train-only `TransformPipelineContract`, including categorical
  treatment and preprocessing identity;
- persisted leakage-audit evidence and declared rigor profiles, surfaced
  through the Studio/API, reopen checks, Lineage, Assurance and verification
  bundles;
- unified runtime identities for model, explainer, validator and execution
  backend components, with a frozen startup snapshot and typed capability
  errors;
- generic adapter-routed training, evidence and final-test replay without
  lifecycle model-kind dispatch;
- persisted execution backend provenance and a complete
  `submit`/`is_active`/`status`/cooperative-`cancel`/`resume` lifecycle
  boundary, including Studio selection and immutable `StudyJob` backend
  identity;
- governed external-runtime golden-route coverage, including project reopen,
  lineage, Assurance and portable verification evidence;
- persisted behavior-revision comparison evidence and read-only Studio
  presentation;
- explicit Studio protocol text for training-, split- and combined-variability
  Stability Lab modes.
- revision-bound BehaviorSpec failure counterexamples and schema-versioned,
  persisted exact FIS computation traces, inspectable after project reopen;
  portable bundles check trace bindings but do not independently replay inference.
- Studio authoring of BehaviorSpecs against either a persisted TrainingRun or
  an exact saved FIS semantic revision, with explicit FIS inputs, uncertain
  creation recovery and close/reopen inspection.
- Failed saved-model reads are distinguished from an empty project in the
  Models and Evidence workspaces; both pause writes and offer a retry.
- Analysis can compare one persisted TrainingRun with one saved manual FIS on
  the run's exact validation cases. The request binds the FIS semantic revision;
  stale revisions are rejected, while older persisted comparisons remain
  inspectable after later FIS edits. Failed FIS reads pause manual-FIS
  comparison and expose retry rather than implying that no FIS exists.
- Analysis comparison drafts and uncertain-response recovery are scoped to the
  current project session; a late response from another project cannot reopen
  its recovery controls in the active Studio view.
- Slice Lab drafts and save/recovery callbacks are likewise session-scoped;
  the real validation slice route persists and reopens without carrying a
  prior project's draft into the new project.
- Analysis mounts per project session. Final-test confirmation and uncertain
  result recovery cannot carry into another project, and a late response from
  the previous session is ignored by the active view. This changes Studio
  lifecycle behavior, not the frozen final-test evaluation semantics.
- The validation-only selective-policy form rejects blank, non-finite and
  out-of-range confidence cutoffs before any evaluation or policy write. A
  rejected draft does not enter uncertain-write recovery and can be corrected.
- A definitive HTTP 422 when creating a selective policy is shown as a
  correctable validation refusal, not as an uncertain persistence outcome.
  Lost responses and server-side persistence failures still use exact-binding
  lookup before any explicit repeat.
- The same definitive-refusal distinction applies to validation calibration
  and decision-threshold selection. These routes validate before their first
  persisted write; HTTP 403/404/409/422 does not create a false recovery lock,
  while ambiguous persistence failures still require exact-object lookup.
- Run-bound validation Evaluation creation also leaves no uncertain-write lock
  after a definite API refusal. Pointer-write failures and lost responses still
  preserve the exact run-bound recovery path.
- Manual Slice Lab source-row input is now exact and fail-closed: blank, malformed,
  duplicate, or unsafe IDs cannot be silently dropped or coerced to row zero.
  The real Studio route rejects such a draft without a write, then persists the
  corrected original-row list and restores its saved analysis after reopen.
- Other Slice Lab forms reject blank categorical/group entries and numeric or
  temporal slices without either bound before creating evidence. This keeps a
  mistaken draft from changing the declared subgroup or creating an unrelated
  validation Evaluation first.
- Stability Map now displays the full 0–100% selected-run-agreement range, so
  confident minority decisions are visible. Undefined agreement is omitted
  from the plot and shown as N/A in Case Inspector, never fabricated as zero.
  The policy chart explicitly distinguishes full-coverage no-review from the
  descriptive matched-count confidence/random references; it is not the
  frozen A01 confirmatory comparator.
- Stability Lab's local case selection and uncertain-save recovery remount with
  the project session, so a pending chain from a closed project cannot be
  offered as a recovery action in the next project.
- A reopened Stability Analysis must match the selected Study's exact runs,
  model/task, randomness protocol and dataset/source-artifact identities before
  Studio displays it as active. A mismatch is shown as an integrity problem and
  blocks new analysis writes until the saved read is retried or investigated.
  The same binding controls what Stability Lab publishes to other Studio
  workspaces; a malformed saved analysis or gate is not exported as active
  evidence through component callbacks.
- The one-command local Studio launcher now permits browser requests from its
  selected loopback Studio port as well as the built-in development ports.
  A live non-default-port launcher run created, closed and reopened a project;
  unrelated web origins remain outside the API CORS allowlist.
- Project Integrity, Assurance and portable bundles reject missing or malformed
  manual-FIS comparison rows and mismatched semantic-revision provenance.
  A portable bundle excludes raw dataset rows, so it checks the frozen row's
  provenance and structure rather than independently replaying its FIS scores.

## Boundaries

V1.3 Alpha is a product/runtime development baseline, not a stable release or
a new research conclusion.
The core keeps TEST closed until a pre-existing frozen policy is applied. A
runtime adapter receives bounded requests; it cannot choose policies, alter
split roles or own project persistence. The platform makes evidence
inspectable; it does not prove causal explanations, universal leakage
prevention, generalization or deployment safety.

## Historical release records

`docs/PRODUCT_V1_2_STATUS.md` records the earlier V1.2 RC1 target and must be
read as historical provenance, not as the active branch status. Frozen research
protocols and results remain under `research/` and are not rewritten by this
product-runtime work.
