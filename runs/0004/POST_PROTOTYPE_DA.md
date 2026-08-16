# Run 0004 — Post-Prototype DA / Counter-DA

Status: `FINAL PRE-MERGE REVIEW`

## Prototype under review

- `LOOP_ROTATION_MEASUREMENT_V0.md`
- `tools/loop_rotation_metrics.py`
- `tests/test_loop_rotation_metrics.py`

The tool is read-only and accepts one explicit `run_id`. It derives metrics from TRACE material-event spans and never writes, merges, deploys or governs.

## Post-prototype findings

### P1 — duplicate cycle identities initially could inflate completed iteration count

Fix: only the first unique `(workstream_id, cycle_seq)` contributes to completed iteration count; duplicates are surfaced and downgrade quality.

### P2 — cycle loss could remain invisible

A trace containing cycles `1, 3` could look like two legitimate cycles while cycle `2` was dropped.

Fix: detect internal sequence gaps per workstream and downgrade measurement.

### P3 — span endpoints could be joined across different workstreams/cycles

A shared `span_id` with mismatched endpoint identity could produce a bogus duration.

Fix: start/finish must agree on stage, run, workstream and cycle sequence or the span is rejected.

### P4 — generic wall range could include post-run audit events

Using min/max time across every same-run record could make later review/seal events artificially slow the measured run.

Fix: complete-run wall elapsed is defined by the unique `RUN_STARTED` / `RUN_STOPPED` boundary. Min/max is only an observed-window fallback.

### P5 — multiple run boundaries could still look complete

Fix: exactly one start and one stop are required for `COMPLETE_RUN`. Multiple boundaries are a quality failure.

### P6 — zero/coarse wall window could produce infinite or invented throughput

Fix: same-process monotonic clocks may still establish span duration, but wall throughput remains null and the overall measurement is downgraded if the run wall window is zero/unmeasurable.

### P7 — duplicate event capture could double-count findings

Fix: stable `event_uid` is deduplicated; duplication remains visible and prevents a full measurement claim.

### P8 — reopen count could lose its causal edge

Fix: missing `cause_event_ids`, workstream or valid cycle edge downgrades causal/overall measurement.

### P9 — stage breakdown could overclaim completeness

Fix: output explicitly labels stage timing as `OBSERVED_SPANS_ONLY`. The tool does not interpret an absent stage span as a skipped stage.

### P10 — historical evidence could be forced into the new schema

Fix: no migration fabricates old cycles. A historical run without explicit loop spans remains `INSUFFICIENT`.

## Counter-DA against overcapture

The surviving mandatory spine is intentionally small:

- run start/stop;
- two events per outer loop span;
- inner stage spans only when their duration matters;
- material findings/reopens/human decisions;
- artifact checkpoints rather than copied external payloads.

The tool reports `material_event_count`, `events_per_completed_iteration` and `observed_json_bytes`, making telemetry growth itself measurable.

No requirement was added for hidden reasoning, all token traffic, all tool calls, stdout streams, every shell command, full diffs, continuous polling or per-event seal writes.

## Verification

New deterministic rotation suite executed locally against the exact prototype logic:

`15 / 15 PASS`

Cases cover:

- complete measurement;
- insufficient historical/no-span data;
- unmatched spans;
- duplicate cycles;
- cycle gaps;
- missing reopen causality;
- parallel workstreams;
- external wait separation;
- coarse wall time with monotonic span duration;
- span identity mismatch;
- missing event identity;
- observed-window downgrade;
- duplicate event deduplication;
- multiple run boundaries;
- missing profile identity.

The earlier PR-lifecycle suite is unchanged and had already passed `10 / 10` before this measurement extension.

## Final adversarial question

Can a third party infer an exact historical rotation rate for run 0002 from this new tool?

**No — correctly.** The required live spine did not exist in the historical capture. The tool/profile explicitly refuses to manufacture it.

Can a future live Ultimate Loop run, captured with this profile, support a defensible measurement of explosive rotation while keeping capture bounded?

**Yes, within the stated evidence boundary.** It can measure completed outer iterations, observed wall throughput, parallelism, material stage durations, findings, reopens, human decisions, external waits and trace volume; missing identity/timing/cycle/causal evidence downgrades the claim instead of being silently repaired.

## Gate

`MERGE_READY` if the final branch diff contains only TRACE measurement/lifecycle evidence work and no unrelated product/runtime changes.
