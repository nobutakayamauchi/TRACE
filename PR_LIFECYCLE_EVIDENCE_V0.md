# TRACE PR Lifecycle Evidence Profile v0

Status: `PROTOTYPE / BOUNDED`

## Mission

Preserve and reconcile pull-request lifecycle evidence without collapsing development completion into repository integration.

This profile extends the Ultimate Loop observer contract. It does not turn TRACE into a GitHub mirror, CI system, deployment monitor, or merge governor.

## Core invariant

```text
IMPLEMENTATION_COMPLETE != TEST_PASS != MERGE_READY
!= PR_MERGED != TARGET_BRANCH_INTEGRATED
!= DEPLOYED != LIVE_ACCEPTED
```

Each transition requires its own evidence.

## Source event: `PR_STATE_OBSERVED`

Recommended payload:

```json
{
  "event": "PR_STATE_OBSERVED",
  "repository": "owner/repo",
  "pr": 123,
  "observed_at": "2026-08-16T20:14:00+09:00",
  "state": "open",
  "draft": false,
  "merged": false,
  "base": "main",
  "head": "goal/example",
  "base_sha": "...",
  "head_sha": "...",
  "merge_commit_sha": "... or null",
  "merged_at": null
}
```

Rules:

1. `repository + pr` is the durable PR identity.
2. The snapshot is true only at `observed_at`; it is not timeless state.
3. `merged=true` or an explicit `merged_at` establishes GitHub merge state when present in the captured source.
4. A non-null `merge_commit_sha` alone MUST NOT establish merge. GitHub may expose a synthetic/test merge commit for an open PR.
5. `state=closed` alone MUST NOT establish merge. `closed + merged=false` is `CLOSED_UNMERGED`.
6. Missing/ambiguous merge fields preserve `UNKNOWN`.
7. Base branch is part of the claim boundary. `PR_MERGED` does not automatically mean "merged to main" if the observed base is different.

Existing `PR_CREATED` and `MERGE_RECORDED` records remain valid historical event types. New capture should prefer explicit `PR_STATE_OBSERVED` at material lifecycle boundaries.

## Derived lifecycle claims

Semantic claims are derived, for example:

```json
{
  "event": "PR_LIFECYCLE_CLAIM",
  "repository": "owner/repo",
  "pr": 123,
  "claim": "MERGED_TO_TARGET",
  "target_branch": "main",
  "source_refs": ["r42"],
  "claimed_at": "2026-08-16T20:13:00+09:00"
}
```

A human-visible statement may be preserved as source evidence, but the lifecycle interpretation remains derived.

## Ordering and freshness

Three notions remain separate:

- `source_order`: archive ingest order;
- source/event time: when the underlying event is reported to have happened;
- `observed_at` / `captured_at`: when TRACE observed or captured the state.

For current-state reconciliation, prefer explicit `observed_at`, then source timestamp, then capture timestamp. Do not treat later ingest order as proof of later real-world state.

If a GitHub snapshot predates a claim or a newer TRACE observation, it cannot refute that later claim/observation.

## Reconciliation outcomes

The prototype may emit:

- `TRACE_COVERAGE_GAP` — GitHub snapshot includes a PR but TRACE has no lifecycle record;
- `MISSING_MERGE_TRANSITION` — newer GitHub evidence says merged but TRACE latest lifecycle evidence does not;
- `SOURCE_CONFLICT` — comparable point-in-time source evidence disagrees;
- `CLAIM_CONFLICT` — a derived lifecycle claim is unsupported by a sufficiently new GitHub snapshot;
- `CLAIM_UNCHECKED` — snapshot is missing, older than the claim, or does not establish the required state.

These are evidence findings, not merge/veto decisions.

## Material capture boundaries

Capture is recommended when one of these happens:

- PR created;
- draft/ready state materially changes;
- merge-ready or similar semantic gate is declared;
- PR merged;
- PR closed without merge;
- run stops at an external boundary;
- an audit explicitly checks repository integration state.

Continuous polling is not required by v0.

## Bounded acceptance cases

The profile must demonstrate all of the following:

1. open PR with non-null `merge_commit_sha` remains OPEN;
2. closed-unmerged remains distinct from merged;
3. GitHub says merged after TRACE only captured PR creation -> `MISSING_MERGE_TRANSITION`;
4. PR present in GitHub evaluation set but absent from TRACE -> `TRACE_COVERAGE_GAP`;
5. human/derived `MERGED_TO_TARGET(main)` claim vs open PR -> `CLAIM_CONFLICT`;
6. older GitHub snapshot does not refute a newer TRACE merge observation;
7. retrospective later ingest does not outrank a newer event merely because `source_order` is larger;
8. snapshot older than a lifecycle claim -> `CLAIM_UNCHECKED`, not conflict.

## Non-goals

This profile does not:

- poll GitHub continuously;
- prove deployment/runtime state;
- prove file-level equivalence after arbitrary cherry-pick/rebase/squash history;
- infer semantic completion from CI or PR text;
- require a specific GitHub merge method;
- make TRACE a release authority.
