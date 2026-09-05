# AGENTS.md

## Repository role
TRACE is a replaceable evidence observer and reconstruction substrate. It records observable facts and supports replay/reconstruction; it is not promotion authority, policy authority, or deployment authority.

## Canonical load order
1. Read `README.md`.
2. Read `CODEX_START.md` for the operator/Codex entrypoint.
3. Load the single protocol relevant to the active evidence question, such as `COMPLETION_PROTOCOL.md`, `HUMAN_DECISION_RUNTIME.md`, `PR_LIFECYCLE_EVIDENCE_V0.md`, or `ULTIMATE_LOOP_OBSERVER.md`.
4. Read targeted `runs/`, `tests/`, or `tools/` only when the active diagnosis/reconstruction requires them.
5. Read `TRACE_BOOTSTRAP.md` only for bootstrap/reconstruction work; do not ingest it by default.

## Source of truth
- Observed evidence and explicit protocol records outrank generated summaries.
- Recorded state is not automatically verified state.
- TRACE may report evidence but must not promote an implementation or decision merely because it observed it.
- Preserve UNKNOWN/CONFLICT and defective-observer/test history.

## Context budget
- Do not scan every root protocol or all historical runs before acting.
- Start from the question being verified and load the narrowest protocol plus the exact run/test evidence needed.
- Do not recursively load Ultimate Loop or other repositories unless the current evidence boundary requires a specific canonical definition.

## Human gates
External mutation, publication, deletion, permission changes, production actions, or changing governance/promotion authority require explicit human approval.

## Stop conditions
Stop when deployment identity is missing, observation cannot distinguish code existence from runtime evidence, required evidence is unavailable, or a task asks TRACE to become the governor it is supposed to observe.