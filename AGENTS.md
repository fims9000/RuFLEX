# RuFLEX agent rules — autonomous full-platform build v3

## Mission
Implement the complete implementable RuFLEX platform defined by `02_RuFLEX_FULL_TECHNICAL_SPEC_v1.md` using verifier-first bounded loops. The canonical product is React/TypeScript RuFLEX Studio + FastAPI + Python application/domain services. Streamlit is legacy only.

## Mandatory skills/process
For long product work use the installed `engineering-loop` skill. Apply the
import trust boundary and scientific-integrity rules in this file directly;
the historical repository skill names are not present in this checkout.

## Minimal context loading
1. Read this file.
2. Read `.product-state/PRODUCT_TASK_STATE.json` when present.
3. Read directly relevant source/tests/failure logs.
4. Load long research/decision docs only on an unresolved dependency.

## Execution mode
- one ACTIVE module/slice at a time;
- after VERIFIED module, persist receipt/state, start fresh context and auto-advance to the next dependency-ready module;
- do not ask for confirmation after routine module completion;
- do not batch the whole roadmap into one giant patch;
- if the environment ends, persist exact resume state.

## Verifier protection
Never delete, skip, weaken, retry-away or rewrite a required verifier merely to get green. A wrong verifier requires evidence and a decision record.

## Two-fix rule
After two failed fixes of the same defect, build a minimal reproduction/root-cause record before another production fix.

## Scientific escalation
Stop for unresolved changes to target/data inclusion/generalization/split/final-test/primary metric/HPO budget/claim semantics or domain-expert meaning.

## Ownership escalation
Do not integrate unpublished/ownership-sensitive fuzzy-XAI operator internals. Keep only generic plugin boundaries unless explicitly authorized later.

## UI rule
A user-facing backend feature is incomplete without its React Studio route, states and browser E2E. Scientific logic remains below the frontend.

## Git/outward actions
Local reversible work is autonomous. No push/merge/release/destructive migration/external upload/publication without explicit authorization.

## END-OF-TURN CONTINUATION PROTOCOL

A tool/runtime/context boundary is not a project stopping condition. If a
module is incomplete, persist its implementation, `TASK_STATE` and `EVIDENCE`;
record the active bounded slice, last command/result, next exact action and
unresolved failures. Do not mark an incomplete module verified or emit a
progress report. The next turn resumes from that checkpoint rather than
rereading the module from scratch. Chat completion is not module completion;
module completion is not P0 release completion.
