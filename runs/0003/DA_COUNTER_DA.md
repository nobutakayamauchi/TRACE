# Run 0003 — PR Lifecycle Evidence DA / Counter-DA

Status: `PRE-PROTOTYPE REVIEW`

## Frozen workload

Evaluate TRACE against the 2026-08-16 WebAI-Bridge episode where semantic development completion and actual GitHub integration state diverged.

The bounded problem is narrow:

1. distinguish implementation/test completion from PR integration;
2. preserve point-in-time GitHub lifecycle state without turning TRACE into a GitHub mirror;
3. detect when a human/derived claim such as "merged to main" conflicts with source evidence;
4. preserve missing lifecycle capture as a TRACE coverage gap;
5. keep deployment/runtime evidence outside this change.

No WebAI-Bridge feature work, Oracle deployment, Stripe, provider call, iPhone test, scheduler, webhook listener, dashboard, or governance authority is authorized.

## Raison d'être

### DROP?

Rejected.

Run 0002 already separates source evidence from derived interpretation, but its PR lifecycle coverage is too coarse for the observed failure mode. A development stage can be `MERGE_READY` or internally complete while the PR remains open. If those states collapse, later reconstruction can falsely report code as integrated into `main`.

### EXTERNALIZE / COMPOSE?

Accepted in part.

GitHub remains the source of PR state. TRACE should not duplicate GitHub history. TRACE needs only a thin event contract plus a reconciliation check that compares TRACE lifecycle evidence/claims with a point-in-time GitHub snapshot.

### IRREDUCIBLE BUILD

A minimal lifecycle evidence profile and a small stdlib-only reconciliation prototype survive.

## METEOR candidates

### Candidate A — keep current event names only

Failure: `PR_CREATED` and `PR_MERGED` exist, but there is no explicit point-in-time state contract, freshness rule, or claim-vs-source reconciliation. Missing transitions can silently look complete in summaries.

### Candidate B — continuously mirror all GitHub PR metadata into TRACE

Failure: unnecessary duplication, monitoring complexity, rate-limit surface, and SimCity risk.

### Candidate C — thin `PR_STATE_OBSERVED` snapshots + derived lifecycle claims + reconciliation

Survives. It records only material lifecycle observations and detects divergence without making TRACE a controller.

## DA findings before prototype

### F1 — semantic completion can collapse into merge completion

`IMPLEMENTATION_COMPLETE`, `TEST_PASS`, `MERGE_READY`, `PR_MERGED`, target-branch integration, deployment and live acceptance are different states.

Required invariant:

```text
IMPLEMENTATION_COMPLETE != TEST_PASS != MERGE_READY
!= PR_MERGED != TARGET_BRANCH_INTEGRATED
!= DEPLOYED != LIVE_ACCEPTED
```

### F2 — `merge_commit_sha` is not merge proof

GitHub can expose a merge-test commit SHA for an open PR. Therefore a non-null `merge_commit_sha` MUST NOT establish `PR_MERGED`.

Required source signal: explicit `merged=true` and/or `merged_at`, with repository + PR identity and base branch.

### F3 — `closed` is not `merged`

A closed-unmerged PR is a distinct terminal state.

### F4 — a PR snapshot is point-in-time evidence

`state=open` observed at time T does not mean the PR stayed open forever. Later observations append; old snapshots remain historically true.

### F5 — archive order is not event time

A retrospective record can be appended after a newer live observation. `source_order` alone MUST NOT decide which lifecycle state is newer.

### F6 — missing TRACE coverage is not negative GitHub evidence

If a PR exists in the evaluation snapshot but TRACE has no lifecycle record, result is `TRACE_COVERAGE_GAP`, not `NOT_MERGED`, `UNKNOWN_PR`, or silent omission.

### F7 — human/derived claims do not outrank GitHub source facts

A visible human statement such as "PR #3-#9 were merged to main" is valuable source evidence of human belief/intent, but the semantic claim `MERGED_TO_TARGET` is derived and must be checked against GitHub state.

## Counter-DA

Do not make reconciliation a merge veto. TRACE reports `SUPPORTED`, `CONFLICT`, `UNKNOWN`, or coverage gaps. Ultimate Loop or a workload-specific policy may decide what to do with that evidence.

Do not require continuous polling. A snapshot can be captured at material boundaries: PR creation, ready-for-merge, merge/close, run stop, or explicit audit.

## Prototype gate

Proceed only with:

- a documented PR lifecycle source-event contract;
- a stdlib-only reconciliation CLI;
- deterministic tests covering F1-F7;
- a real WebAI-Bridge PR #7/#8/#9 fixture demonstrating the observed distinction.

Then run a second DA / Counter-DA before opening a draft PR.
