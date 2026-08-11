# TRACE — Human Decision Runtime Requirements

Status: OBSERVED DURING RUN 0001

This document records runtime requirements discovered while TRACE itself is being developed.
It is intentionally abstract and contains no private operator location or medical detail.

## Core problem

External AI execution can continue while the human operator is temporarily unavailable, resting, moving, or otherwise operating at reduced capacity.
The runtime should therefore optimize not only for machine throughput, but for the timing and quality of the next human decision.

The key question is:

> When will the next consequential human judgment be required, and how much safe recovery / preparation time exists before then?

## Required concepts

### 1. Decision Deadline

For each externally executing task, record enough timing data to estimate when the next human judgment is likely to be required.

Minimum observations:
- run start time;
- task class;
- completion / result time;
- time at which human judgment became necessary;
- result class: PASS / PARTIAL / BLOCKED / FAILED / UNKNOWN;
- estimated human judgment load: LOW / MEDIUM / HIGH.

Do not invent a prediction model before enough observations exist.

### 2. Recovery Budget

Treat external execution latency as potentially usable operator recovery / preparation time.

Once empirical data exists, derive bounded timing estimates such as:
- T50: typical return point;
- T80: reasonable first-check point;
- T95: point at which delay or failure should begin to be suspected.

These are empirical percentiles, not promises.
Until enough comparable runs exist, report UNKNOWN rather than fabricated precision.

### 3. Degraded Operator Mode

TRACE must remain usable when the human operator can provide only sparse, high-level decisions.

Desired behavior:
- keep execution external where possible;
- avoid requiring continuous screen watching;
- preserve state in GitHub / durable records;
- allow the operator to resume from a compact decision surface;
- do not require a desktop environment;
- fail closed when state is ambiguous.

### 4. Parallel machines, serial human judgment

External workers may run in parallel.
Human judgment should be treated as a scarce serial resource.

Before launching additional work, consider whether multiple tasks are likely to return HIGH-load decisions at the same time.
The runtime should eventually help answer:
- which task will require the human next;
- approximately when;
- with what expected decision load.

Do not build a generalized scheduler yet.
First collect evidence that such coordination is actually needed.

### 5. Completion-state ambiguity

A missing final result can currently mean several different things:
- still running;
- stopped / failed;
- finished but not published back to GitHub.

This ambiguity is an observed gap.
Do not solve it with a large orchestration layer.
If repeated runs show material cost, prefer the smallest possible status mechanism (for example START / optional STATUS / RESULT records).

### 6. Anti-overrun invariant

The runtime must not optimize machine parallelism at the expense of human review capacity.

A useful future invariant is:

> New externally executed work should not be launched when its likely return would create an avoidable pile-up of unresolved high-load human decisions.

This is a runtime safety / quality property, not a moral judgment about the operator.

## Data-first implementation rule

For TRACE v0.1, prioritize recording the data needed to measure these behaviors.
Do NOT expand scope into:
- custom agent orchestration;
- bespoke scheduler infrastructure;
- dashboards;
- provider-specific runtime control;
- generalized task queues;
- automatic health or personal-state inference.

First collect real run data. Promote only repeatedly observed needs into implementation.

## Initial measurement target

Use TRACE development itself as the first workload.
For each run, preserve timing and result data so later runs can estimate:

`external execution time -> next human decision time -> available recovery budget`

The purpose is not to maximize continuous human work.
The purpose is to make the next required human decision predictable enough that the operator can safely disengage until needed.
