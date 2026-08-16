# TRACE Ultimate Loop Rotation Measurement Profile v0

Status: `PROTOTYPE / BOUNDED`

## Mission

Measure a high-speed Ultimate Loop run without collapsing it into GitHub output count and without turning TRACE into exhaustive telemetry.

The profile answers only evidence-supported questions such as:

- how many loop iterations completed in the observed run/window;
- wall-clock throughput;
- stage-span durations that were actually observed;
- maximum concurrent loop iterations;
- finding/open/resolution yield;
- which finding/event caused a loop reopen;
- human-decision count;
- explicit external-wait time;
- how much TRACE data was required to obtain those measurements.

It MUST NOT claim hidden reasoning, uninstrumented machine execution speed, or complete historical coverage when the measurement spine was not captured live.

## Core invariant

```text
GITHUB OUTPUT != LOOP ROTATION
COMMIT COUNT != ITERATION COUNT
INGEST ORDER != EVENT TIME
OBSERVED WINDOW != COMPLETE RUN
INSTRUMENTED WALL THROUGHPUT != UNINSTRUMENTED EXECUTION SPEED
```

## Why run 0002 is not enough

Run `0002` preserved useful GitHub, decision, finding and observer evidence, but it was attached after the WebAI-Bridge burst had already progressed and it did not capture explicit loop-iteration spans.

Therefore the exact rotation rate of that historical burst MUST remain `INSUFFICIENT` / bounded by surviving evidence. TRACE must not fabricate cycle boundaries from commits or PRs.

This profile is for future live capture and for honest assessment of older runs.

## Minimal live measurement spine

Every measurement-profile event should carry a stable `event_uid` and `run_id`.

A run starts with:

```json
{
  "event_uid": "evt-...",
  "run_id": "run-...",
  "event": "RUN_STARTED",
  "measurement_profile": "TRACE-UL-ROTATION-v0",
  "observed_at": "2026-08-16T20:30:00.123456+09:00"
}
```

### Loop/stage spans

Use `SPAN_STARTED` / `SPAN_FINISHED` for the outer `LOOP_ITERATION` span and for material inner stages that need duration measurement.

Required span identity:

- `span_id`;
- `stage`;
- `workstream_id`;
- `cycle_seq` within that workstream;
- `observed_at`;
- optional `parent_span_id` for nesting.

Recommended for high-speed same-process measurement:

- `clock_domain`;
- `monotonic_ns`.

When both endpoints share a `clock_domain`, monotonic time is preferred for duration. Wall-clock time remains necessary for cross-workstream throughput and chronology.

Typical stage labels include:

`LOOP_ITERATION`, `RAISON`, `DA`, `COUNTER_DA`, `BUILD`, `TEST`, `METEOR`, `REVIEW`, `MERGE`, `REALITY`, `EXTERNAL_WAIT`.

The label set is intentionally not a governor. Unknown/new stages may remain ordinary strings.

### Findings and reopen causality

`FINDING_OPENED` / `FINDING_RESOLVED` use stable `finding_id`.

`root_cause_id` is optional because TRACE must not invent a root cause before evidence supports one.

A reopen should preserve the minimal causal edge:

```json
{
  "event_uid": "evt-reopen-...",
  "run_id": "run-...",
  "event": "LOOP_REOPENED",
  "workstream_id": "main",
  "from_cycle_seq": 4,
  "to_cycle_seq": 5,
  "cause_event_ids": ["evt-finding-17"],
  "observed_at": "..."
}
```

Without the causal edge, TRACE may count reopens but must downgrade causal reconstruction.

### Human decisions and external waits

Capture `HUMAN_DECISION` only for material decision boundaries, not every human message.

Represent real external blocking time as an `EXTERNAL_WAIT` span when known. This prevents host access, provider waiting, approval waiting or similar real-world latency from being mislabeled as slow machine iteration.

## Concurrency

`workstream_id` separates concurrent lanes. `cycle_seq` is monotonic only inside one workstream.

TRACE MUST NOT flatten two simultaneous loop iterations into one linear iteration count. Maximum parallel loop iterations are derived only from orderable completed `LOOP_ITERATION` spans.

## Coverage and fail-closed measurement

The measurement tool reports one of:

- `MEASURED` — complete run boundaries and mandatory measurement spine are present;
- `PARTIAL` — useful metrics exist but coverage/identity/timing/causal quality is incomplete;
- `INSUFFICIENT` — no defensible completed loop-iteration measurement exists.

Coverage is separately labeled:

- `COMPLETE_RUN` — exactly one observed `RUN_STARTED` and one observed `RUN_STOPPED` for the requested run;
- `OBSERVED_WINDOW` — only a bounded observation window is available;
- `INSUFFICIENT`.

Cycle-sequence gaps, duplicate cycle identities, duplicate event IDs, unmatched span endpoints, missing profile identity, invalid reopen edges and unmeasurable wall throughput prevent a full `MEASURED` claim.

## Metrics

The v0 prototype derives:

- `completed_loop_iterations`;
- `wall_elapsed_seconds`;
- `loop_iterations_per_wall_hour`;
- `max_parallel_loop_iterations`;
- per-stage observed duration summaries;
- findings opened/resolved;
- findings per completed iteration;
- optional distinct-root-cause yield;
- loop-reopen count and causal-link status;
- human-decision count;
- explicit external-wait duration;
- material event count;
- events per completed iteration;
- observed JSON byte volume.

Stage breakdown is explicitly `OBSERVED_SPANS_ONLY`; missing stage spans are not silently interpreted as skipped stages.

## Anti-overcapture rule

The following are NOT required for v0 rotation measurement:

- hidden chain-of-thought;
- every token;
- every model message;
- every tool call;
- full stdout/stderr streams;
- every shell command;
- every file line/diff;
- continuous GitHub polling;
- per-event seal maintenance.

GitHub commits/PRs, test reports and runtime evidence remain separate source evidence/checkpoints and may be linked only at material boundaries.

The profile deliberately measures its own data volume (`events/iteration`, JSON bytes) so instrumentation growth is visible rather than silently becoming SimCity.

## Observer effect

Metrics describe the observed/instrumented run. They do not claim hypothetical uninstrumented execution speed.

If TRACE capture is placed synchronously on a hot path and benchmark-level overhead matters, observer overhead must be measured separately before subtracting or extrapolating it. v0 does not invent an overhead correction.

## Acceptance cases

The prototype must demonstrate:

1. a complete two-iteration run measures successfully;
2. historical records without loop spans return `INSUFFICIENT` rather than commit-derived fake cycles;
3. unmatched span endpoints downgrade coverage;
4. duplicate cycle identity does not inflate iteration count;
5. missing cycle sequence is surfaced as a gap;
6. reopen without a causal event downgrades causality;
7. parallel workstreams produce measurable parallelism;
8. `EXTERNAL_WAIT` is separated from loop duration;
9. sub-second monotonic spans survive coarse/equal wall timestamps while wall-throughput remains unclaimed when the wall window is zero;
10. mismatched span workstream/cycle identity is rejected;
11. missing stable event identity downgrades measurement;
12. observed-window capture cannot claim complete-run measurement;
13. duplicate event IDs are deduplicated and surfaced;
14. multiple run boundaries are surfaced;
15. missing measurement-profile identity prevents a full measurement claim.

## Non-goals

This profile does not estimate developer fatigue, hidden AI reasoning, semantic code quality, monetary value, or production correctness from rotation speed.

Fast is an observation, not a promotion authority.
