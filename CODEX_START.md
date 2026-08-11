# TRACE — CODEX_START.md

Execute this repository as a one-shot TRACE v0.1 bootstrap.

## Start condition

TRACE genesis was declared by the human at `2026-08-11T11:09:00+09:00` and recorded in `GENESIS.json`.

## Required action

1. Read `TRACE_BOOTSTRAP.md` completely.
2. Read `HUMAN_DECISION_RUNTIME.md` as an observed runtime requirement. For v0.1, collect the minimum data needed for later measurement; do not broaden scope into a scheduler or orchestration framework.
3. Implement TRACE v0.1 exactly to that specification.
4. Do not recreate RTS or add a custom orchestration/runtime/governance layer.
5. Prefer the smallest standard-library-first implementation that preserves the invariants.
6. Build the deterministic three-episode fixture and all required contradictory derived claims.
7. Run the full destructive acceptance suite, including mutation, deletion, reordering, false-history injection, UNKNOWN preservation, timestamp anomaly, index deletion/rebuild, and recovery/export tests.
8. Fix implementation defects found by those tests and rerun until the mandatory suite passes or a concrete external blocker remains.
9. Produce `TRACE_V0_1_RESULT.md` containing:
   - implementation summary;
   - exact commands run;
   - acceptance-test results;
   - core line count;
   - remaining deferred responsibilities;
   - any UNKNOWN/CONFLICT or trust-boundary limitations;
   - final PASS / PARTIAL / BLOCKED verdict.
10. Keep raw evidence authoritative and all indexes/claims/semantic views derivative and rebuildable.
11. Stop before UI, cloud infrastructure, plugin frameworks, generalized orchestration, legal identity/notarization, or other non-v0.1 expansion.

## Completion rule

Do not stop at "code written". The first milestone is complete only after the implementation has been deliberately damaged and still demonstrates bounded reconstruction without canonicalizing the injected false histories.

If an ambiguous design choice appears, choose the smaller design that preserves the invariant.
