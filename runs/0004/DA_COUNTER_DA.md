# Run 0004 — Explosive Rotation Measurement DA / Counter-DA

Status: `PRE-PROTOTYPE REVIEW`

## Question from the operator

Can TRACE actually measure the explosive high-speed rotation of Ultimate Loop, capture the necessary evidence without material omission, and avoid collecting so much data that observation itself becomes wasteful or distorting?

## Frozen workload

Evaluate measurement capability only.

Do not add orchestration authority, model reasoning capture, continuous GitHub mirroring, deployment work, UI, scheduler, cloud infrastructure or a generalized telemetry platform.

## Initial verdict

**Current PR #2 before this run: NOT SUFFICIENT.**

The PR lifecycle reconciler can distinguish repository integration state, but GitHub/PR transitions are too coarse to measure the internal rotation of:

```text
DA → Counter-DA → build → test → finding → reopen → next iteration
```

Several internal iterations can occur between two commits. Commit/PR density is output evidence, not loop-iteration evidence.

## DA findings

### D1 — GitHub output cannot be the rotation clock

Commit and PR timestamps establish repository output events. They do not establish how many internal Ultimate Loop iterations occurred between them.

Required rule:

`GITHUB OUTPUT != LOOP ROTATION`.

### D2 — no explicit cycle boundary means exact cycle rate is unknowable

A measurement system needs an outer iteration identity. Without `LOOP_ITERATION` start/finish, a later analyst can invent cycles from findings or commits.

Required: explicit completed outer spans.

### D3 — a linear trace can hide parallel work

Two agents/workstreams may be running simultaneously. A single integer sequence across the whole run would serialize concurrency that never existed.

Required: `workstream_id` plus per-workstream `cycle_seq`, and interval-based parallelism derived from completed outer spans.

### D4 — high-speed timing can outrun coarse wall timestamps

Several events may share the same wall-clock second. Source order can preserve sequence but cannot prove duration.

Required: high-resolution `observed_at`; recommend `clock_domain + monotonic_ns` for same-process span duration. If wall elapsed is zero/unorderable, do not fabricate wall throughput.

### D5 — real-world waiting can look like slow AI

SSH availability, external provider state, approval or a human pause can dominate wall time.

Required: explicit `EXTERNAL_WAIT` spans when known. Do not silently subtract unspecified idle time.

### D6 — reopen count without causality loses the reason the loop rotated

Counting another iteration is insufficient if the question is why the previous result failed.

Required on `LOOP_REOPENED`: `from_cycle_seq`, `to_cycle_seq`, `workstream_id`, and `cause_event_ids`.

### D7 — missing/duplicate measurement events can produce plausible but false speed

A dropped iteration silently undercounts. A duplicate iteration silently overcounts.

Required: stable `event_uid`, stable `span_id`, duplicate detection, cycle identity uniqueness, and internal cycle-sequence gap detection.

### D8 — complete run and observed window are different claims

TRACE may attach after a run starts or stop observing before the run ends.

Required: `COMPLETE_RUN` only with exactly one observed `RUN_STARTED` and `RUN_STOPPED`; otherwise label the result `OBSERVED_WINDOW` / partial.

### D9 — archive ingest order is not execution chronology

Retrospective events can be written after newer events.

Required: durations use event/observation clocks, not JSONL position or later ingest order.

### D10 — exhaustive telemetry would create a new failure mode

Capturing every token, tool call, stdout byte, command and diff is not necessary to answer the rotation question. It increases storage, privacy surface and observer overhead, and recreates SimCity.

Required: capture only the material measurement spine and link external artifacts at checkpoints.

### D11 — observer effect cannot be wished away

An instrumented run is not automatically identical to a hypothetical uninstrumented run.

Required claim boundary: report observed/instrumented wall throughput. Never silently subtract estimated TRACE overhead.

### D12 — historical run 0002 cannot be retroactively made exact

Run 0002 was attached after the burst progressed and has no explicit outer iteration spans.

Required result: exact historical rotation remains `INSUFFICIENT`; no commit-derived fake cycles.

## Candidate comparison

### Candidate A — use current TRACE + GitHub timestamps

Fails D1/D2/D3/D6. Good history, bad rotation measurement.

### Candidate B — log everything

Fails D10/D11. Excessive instrumentation with no demonstrated need.

### Candidate C — minimal material-event span profile

Survives DA:

- one outer `LOOP_ITERATION` span per actual iteration;
- optional material inner stage spans;
- material findings/reopens/human decisions;
- explicit run/window boundaries;
- external artifact checkpoints remain references;
- quality failures downgrade measurement rather than repairing data silently.

## Counter-DA

### Is `root_cause_id` mandatory?

No. Making it mandatory at finding-open time would pressure TRACE to invent a root cause too early. Stable `finding_id` and reopen causal event links are mandatory; root-cause classification is optional and evidence-bound.

### Must every Ultimate Loop stage be logged?

No. Outer iteration spans are the minimum needed for rotation count and rate. Inner stage metrics are explicitly `OBSERVED_SPANS_ONLY`; absence of a stage span does not mean the stage was skipped.

### Must TRACE continuously poll GitHub?

No. Repository state remains checkpoint/source evidence. Rotation measurement occurs at the loop boundary, not by inferring loops from GitHub.

### Does this make TRACE a controller?

No. Measurement status is evidence quality only. TRACE still has no promotion, veto, termination or merge authority.

## Prototype gate

Build only:

1. `LOOP_ROTATION_MEASUREMENT_V0.md`;
2. a stdlib-only read-only metrics tool;
3. adversarial tests for missing/duplicate/parallel/timing/causality cases;
4. an explicit assessment that run 0002 is historically insufficient for exact rotation measurement.

Then apply post-prototype DA before merge.
