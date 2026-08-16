# Ultimate Loop Observer Profile — TRACE

Status: `DOGFOOD / v0`

## Mission

Attach TRACE to Ultimate Loop as a passive evidence recorder without turning TRACE into a controller.

```text
ULTIMATE LOOP = decision / challenge / implementation sequence
TRACE         = evidence preservation / reconstruction
```

## Hard boundaries

- TRACE does not authorize promotion.
- TRACE does not veto a merge.
- TRACE does not choose DA severity.
- TRACE does not terminate a run.
- TRACE does not infer hidden model chain-of-thought.
- TRACE does not rewrite retrospective reconstruction as live observation.
- TRACE source records remain distinct from derived claims and metrics.

## Capture modes

### LIVE

The event is captured at or near the time it occurs from an available source.

### RETROSPECTIVE

The event occurred before observer attachment and is reconstructed from surviving evidence.

Every retrospective run must include an explicit boundary record before reconstructed events.

### DERIVED

The record is an interpretation, metric, summary, causal reconstruction, or classification derived from one or more source records.

`DERIVED != SOURCE EVIDENCE`

## Minimum Ultimate Loop events

Recommended event types:

`RUN_STARTED`, `GOAL_FROZEN`, `DISCOVERY_FOUND`, `GATE_ENTERED`, `GATE_PASSED`, `GATE_FAILED`, `FINDING_OPENED`, `FINDING_REJECTED`, `FINDING_RESOLVED`, `COUNTER_DA_RESULT`, `INVARIANT_ADDED`, `TEST_ADDED`, `TEST_RESULT`, `CHANGE_APPLIED`, `COMMIT_CREATED`, `PR_CREATED`, `PR_MERGED`, `DEPLOYMENT_IDENTITY`, `HUMAN_DECISION`, `HUMAN_OVERRIDE`, `UNKNOWN_PRESERVED`, `CONFLICT_PRESERVED`, `EXTERNAL_EVIDENCE_REQUIRED`, `RUN_STOPPED`.

## v0 hash profile

For the first dogfood run, records use SHA-256 over UTF-8 canonical JSON:

- payload keys sorted;
- compact separators;
- `payload_sha256` hashes the canonical payload;
- `record_hash` hashes the canonical full record excluding `record_hash` itself;
- `previous_record_hash` links each record to the prior record.

This profile is intentionally small and may later be superseded. Existing evidence must retain the profile used when it was created.

## Observer failure

TRACE failure does not automatically stop Ultimate Loop.

But missing evidence must remain visible:

```text
TRACE GAP
→ RECONSTRUCTABILITY DEGRADED
→ NO CLAIM OF COMPLETE OBSERVATION
```

If auditability is mandatory for a frozen workload, that workload may explicitly fail closed on observer loss.

## First dogfood run

`runs/0002` records the 2026-08-16 WebAI-Bridge development episode.

- repository history before observer attachment is retrospective;
- the human directive to attach TRACE marks the live observation boundary;
- GitHub evidence is preserved as source-backed records;
- test-count growth and other summaries are derived records;
- external runtime facts remain unproven until separately observed.

Ultimate Loop canonical method repository:

- https://github.com/nobutakayamauchi/Ultimate-Loop
