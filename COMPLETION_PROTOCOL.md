# TRACE Completion Protocol

Purpose: bridge Codex completion back into the ChatGPT-driven development loop through GitHub.

## Required completion artifact

Every Codex implementation run MUST finish by writing:

`runs/<run_id>/RESULT.json`

with at least:

- `run_id`
- `status`: `PASS` | `PARTIAL` | `FAIL`
- `started_from_commit`
- `result_commit`
- `summary`
- `tests_run`
- `tests_passed`
- `tests_failed`
- `acceptance_tests`
- `changed_files`
- `known_failures`
- `deferred_items`
- `next_recommended_action`
- `completed_at`

If human-readable detail is useful, also write:

`runs/<run_id>/RESULT.md`

## Authority boundary

The RESULT files are completion reports, not independent proof that a claim is true. Test outputs, diffs, commits, runtime probes, and other source evidence remain inspectable separately.

## ChatGPT handoff

When the user says words equivalent to:

- `判断返ってきた`
- `Codex終わった`
- `結果見て`

ChatGPT should fetch the newest `runs/*/RESULT.json`, inspect the referenced commit/tests/diffs where needed, then continue the development loop from that evidence.

No manual copy/paste of the Codex result should be required when the result exists in GitHub.

## Failure behavior

If RESULT.json is absent, ChatGPT must report that completion is not yet evidenced in GitHub rather than guessing that Codex finished.

If RESULT.json says PASS but referenced tests or commits disagree, preserve the conflict and do not silently accept PASS.
