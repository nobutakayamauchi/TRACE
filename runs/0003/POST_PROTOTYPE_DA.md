# Run 0003 — Post-Prototype DA / Counter-DA

Status: `PRE-MERGE REVIEW`

## Prototype under review

- `tools/pr_lifecycle_reconcile.py`
- `tests/test_pr_lifecycle_reconcile.py`
- WebAI-Bridge PR #7/#8/#9 point-in-time fixture
- derived merge-to-main claim fixture

The prototype is intentionally read-only. It reports evidence findings and has no GitHub write, merge, deployment, or governance authority.

## DA findings after prototype

### P1 — freshness-free source comparison could create false conflict

Initial prototype logic could compare a TRACE state and GitHub state even when one or both observation times were missing.

Failure mode:

```text
old/unknown-time GitHub snapshot
vs
newer TRACE merge record
→ false SOURCE_CONFLICT
```

Resolution:

Comparable source conflict now requires orderable freshness. If state differs and freshness cannot be established, emit `STATE_FRESHNESS_UNKNOWN` and preserve uncertainty.

### P2 — ingest order is not real-world state order

A retrospective record may be ingested after a newer live record. Larger `source_order` cannot automatically mean newer PR state.

Resolution:

State selection prefers explicit observation time, then source timestamp, then capture timestamp. `source_order` is only a tie/fallback inside the archive when event time is absent; it is not used to prove external chronology.

### P3 — an older snapshot cannot refute a newer lifecycle claim

Initial claim checking needed an explicit freshness guard.

Resolution:

If the GitHub snapshot predates the claim, result is `CLAIM_UNCHECKED`, not conflict.

### P4 — missing claim/snapshot ordering must stay UNKNOWN

If neither timestamp nor a bounded capture sequence can order the claim and snapshot, declaring conflict would invent chronology.

Resolution:

Add optional reconciliation-packet `capture_order`. When neither timestamp nor capture order establishes sequence, emit `CLAIM_UNCHECKED`.

### P5 — non-null `merge_commit_sha` is a trap

The real WebAI-Bridge PR #7 and #8 snapshots are OPEN and `merged=false` while also exposing non-null `merge_commit_sha` values.

Resolution:

The implementation ignores `merge_commit_sha` as merge authority. Explicit `merged` / `merged_at` remains authoritative for the captured GitHub PR state.

### P6 — closed does not imply merged

Resolution verified by a dedicated regression: `closed + merged=false` remains `CLOSED_UNMERGED` and conflicts with a TRACE merge record only when the source observations are temporally comparable.

### P7 — missing TRACE records are coverage failures, not negative lifecycle facts

The real fixture contains PR #7/#8/#9, while run 0002 does not contain lifecycle records for those WebAI-Bridge PRs.

Resolution:

Emit `TRACE_COVERAGE_GAP` for each absent PR. Do not infer `NOT_MERGED`, do not silently omit it, and do not rewrite historical run 0002.

## Counter-DA

### Does this become a GitHub mirror?

No. The prototype consumes explicit point-in-time snapshots supplied at material boundaries. It does not poll or persist all GitHub metadata.

### Does this make TRACE a merge gate?

No. Findings are evidence only. A separate workload may choose to fail closed on a `CLAIM_CONFLICT` or coverage gap, but that authority is not inside TRACE.

### Does it overfit WebAI-Bridge?

The fixture is WebAI-Bridge-specific; the reconciliation key and lifecycle rules are repository/PR generic.

### Should TRACE auto-repair run 0002?

No. Run 0002 is sealed. The newly discovered missing transitions/coverage are evidence about the observer, not permission to rewrite sealed history.

## Verification

Local deterministic test command:

```bash
python3 -m unittest discover -s tests -v
```

Result after post-prototype fixes: `10 tests PASS`.

Real fixture result:

- PR #7: `TRACE_COVERAGE_GAP` + `CLAIM_CONFLICT` because GitHub snapshot says OPEN;
- PR #8: `TRACE_COVERAGE_GAP` + `CLAIM_CONFLICT` because GitHub snapshot says OPEN;
- PR #9: `TRACE_COVERAGE_GAP`; merge-to-main claim is supported by the snapshot and therefore produces no claim conflict.

Total: `5 findings`.

## Gate

`MERGE_READY / STOP_BEFORE_MERGE`

The bounded lifecycle evidence problem is represented in specification, executable prototype, deterministic regressions, and a real incident fixture. No external deployment or WebAI-Bridge product work is included.
