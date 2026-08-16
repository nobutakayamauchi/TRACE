# Run 0003 — Prototype Result

Status: `MERGE_READY / STOP_BEFORE_MERGE`

## Scope

TRACE PR lifecycle evidence only.

No WebAI-Bridge feature change, deployment, Stripe, provider call, iPhone test, or runtime promotion is included.

## Prototype

`tools/pr_lifecycle_reconcile.py`

Inputs:

- TRACE event JSONL;
- point-in-time GitHub PR snapshot JSON;
- optional derived lifecycle claims JSON.

Output:

- machine-readable evidence findings only.

## Deterministic verification

```bash
python3 -m unittest discover -s tests -v
```

Result: `10/10 PASS` after post-prototype DA fixes.

Covered regressions:

- open PR with synthetic/non-null merge commit SHA;
- merged transition missing from TRACE;
- TRACE coverage gap;
- human/derived merge claim conflict;
- target branch match;
- closed-unmerged distinction;
- older snapshot vs newer TRACE observation;
- retrospective ingest order vs event time;
- older snapshot vs newer claim;
- missing freshness/order preserves UNKNOWN.

## Real WebAI-Bridge fixture

Evaluation snapshot:

- PR #7: OPEN, `merged=false`, base `main`;
- PR #8: OPEN, `merged=false`, base `main`;
- PR #9: CLOSED, `merged=true`, base `main`.

Important adversarial detail: PR #7 and #8 both expose non-null `merge_commit_sha` values despite being open and unmerged. The prototype does not use that field as merge authority.

Run 0002 contains no WebAI-Bridge PR #7/#8/#9 lifecycle records, so reconciliation reports:

```text
PR #7 TRACE_COVERAGE_GAP
PR #8 TRACE_COVERAGE_GAP
PR #9 TRACE_COVERAGE_GAP
PR #7 CLAIM_CONFLICT: MERGED_TO_TARGET(main) vs OPEN
PR #8 CLAIM_CONFLICT: MERGED_TO_TARGET(main) vs OPEN
```

PR #9's merge-to-main claim is supported by the snapshot, so it does not produce a claim conflict.

Total: `5 findings`.

## Surviving rule

```text
IMPLEMENTATION_COMPLETE != TEST_PASS != MERGE_READY
!= PR_MERGED != TARGET_BRANCH_INTEGRATED
!= DEPLOYED != LIVE_ACCEPTED
```

This rule is the minimal TRACE strengthening that survived the bounded Ultimate Loop pass.
