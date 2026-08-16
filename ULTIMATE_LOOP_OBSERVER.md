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

## Source-event semantics

Source records must say only what the source itself establishes.

Examples:

```text
GITHUB MERGE/COMMIT EVIDENCE -> MERGE_RECORDED / CHANGE_RECORDED
ULTIMATE LOOP PROMOTION CLAIM -> DERIVED DECISION RECORD WITH SOURCE REFERENCES
```

A commit existing on a branch does not by itself prove that a candidate won METEOR, that a deployment became correct, or that a human approved a semantic promotion.

GitHub records must identify the repository as well as the SHA. SHA without repository context is insufficient for durable reconstruction.

When the source actor is not established, actor remains null/UNKNOWN instead of being invented as `system`, `human`, or an AI identity.

## Minimum Ultimate Loop events

Recommended event types:

`RUN_STARTED`, `GOAL_FROZEN`, `DISCOVERY_FOUND`, `GATE_ENTERED`, `GATE_PASSED`, `GATE_FAILED`, `FINDING_OPENED`, `FINDING_REJECTED`, `FINDING_RESOLVED`, `COUNTER_DA_RESULT`, `INVARIANT_ADDED`, `TEST_ADDED`, `TEST_RESULT`, `CHANGE_APPLIED`, `COMMIT_CREATED`, `PR_CREATED`, `PR_MERGED`, `DEPLOYMENT_IDENTITY`, `HUMAN_DECISION`, `HUMAN_OVERRIDE`, `UNKNOWN_PRESERVED`, `CONFLICT_PRESERVED`, `EXTERNAL_EVIDENCE_REQUIRED`, `RUN_STOPPED`.

## Build / seal lifecycle

A new run may need to ingest retrospective evidence before the initial archive is stable. TRACE therefore distinguishes construction from sealed evidence.

```text
BUILDING
→ validate sources / ordering / hashes
→ FIRST SEAL
→ APPEND-ONLY
```

Rules:

1. While `BUILDING`, an initial event set may be regenerated to correct capture/schema mistakes.
2. A BUILDING manifest is not an authoritative integrity seal.
3. The first `SEALED` manifest freezes all existing event records.
4. After first seal, existing records must not be edited, reordered, or deleted in normal operation.
5. Post-seal corrections are new append-only records that cite the record being corrected.
6. Re-sealing after append updates the head hash but never rewrites the already sealed prefix.
7. Git history may preserve pre-seal drafts, but those drafts must not be presented as the sealed TRACE record.

This boundary prevents bootstrap cleanup from being mislabeled as append-only preservation.

## Observer self-reference boundary

TRACE must not create an infinite recursion by requiring every integrity-maintenance write to be recorded inside the same event chain that write changes.

```text
APPEND EVENT
→ UPDATE SEAL
→ MUST APPEND "SEAL UPDATED"
→ UPDATE SEAL
→ ...
```

is forbidden as a mandatory rule.

Seal/reseal metadata is integrity metadata about the chain, not automatically a workload event inside that same chain. Git history or a separate seal lineage may preserve those maintenance operations when useful.

During dogfood, material observer implementation changes may still be recorded as ordinary events. The act of updating the manifest solely to seal the new head does not itself require another event in the same chain.

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
- test-count growth and promotion interpretations are derived records, not GitHub source facts;
- external runtime facts remain unproven until separately observed;
- the first seal has been created; records `r1-r25` are the frozen first-seal prefix;
- post-seal observations append after `r25` and must not rewrite that prefix.

Ultimate Loop canonical method repository:

- https://github.com/nobutakayamauchi/Ultimate-Loop
