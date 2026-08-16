import unittest

from tools.pr_lifecycle_reconcile import reconcile


class ReconcileTests(unittest.TestCase):
    def test_actual_shape_distinguishes_open_from_merged_even_with_merge_commit_sha(self):
        trace = [
            {"record_id": "r1", "source_order": 1, "captured_at": "2026-08-16T20:00:00+09:00", "payload": {"event": "PR_CREATED", "repository": "nobutakayamauchi/WebAI-Bridge", "pr": 7}},
            {"record_id": "r2", "source_order": 2, "captured_at": "2026-08-16T20:00:00+09:00", "payload": {"event": "PR_CREATED", "repository": "nobutakayamauchi/WebAI-Bridge", "pr": 9}},
        ]
        github = {"observed_at": "2026-08-16T20:10:00+09:00", "prs": [
            {"repository": "nobutakayamauchi/WebAI-Bridge", "pr": 7, "state": "open", "merged": False, "base": "main", "merge_commit_sha": "synthetic-test-merge"},
            {"repository": "nobutakayamauchi/WebAI-Bridge", "pr": 9, "state": "closed", "merged": True, "base": "main", "merge_commit_sha": "real-merge"},
        ]}
        result = reconcile(trace, github)
        types = {(f["pr"], f["type"]) for f in result["findings"]}
        self.assertNotIn((7, "SOURCE_CONFLICT"), types)
        self.assertIn((9, "MISSING_MERGE_TRANSITION"), types)

    def test_missing_trace_records_are_coverage_gaps(self):
        result = reconcile([], {"prs": [
            {"repository": "r/x", "pr": 8, "state": "open", "merged": False, "base": "main"}
        ]})
        self.assertEqual(result["findings"][0]["type"], "TRACE_COVERAGE_GAP")

    def test_human_merge_claim_conflicts_with_open_pr(self):
        github = {"prs": [
            {"repository": "r/x", "pr": 7, "state": "open", "merged": False, "base": "main"}
        ]}
        claims = [{"repository": "r/x", "pr": 7, "claim": "MERGED_TO_TARGET", "target_branch": "main", "source_ref": "human-message", "capture_order": 1}]
        github["capture_order"] = 2
        result = reconcile([], github, claims)
        self.assertTrue(any(f["type"] == "CLAIM_CONFLICT" for f in result["findings"]))

    def test_merged_to_main_claim_supported_only_when_merged_and_base_matches(self):
        github = {"prs": [
            {"repository": "r/x", "pr": 9, "state": "closed", "merged": True, "base": "main"}
        ]}
        claims = [{"repository": "r/x", "pr": 9, "claim": "MERGED_TO_TARGET", "target_branch": "main", "capture_order": 1}]
        github["capture_order"] = 2
        result = reconcile([], github, claims)
        self.assertFalse(any(f["type"] == "CLAIM_CONFLICT" for f in result["findings"]))

    def test_closed_without_merged_is_not_merge(self):
        trace = [{"record_id": "r1", "source_order": 1, "captured_at": "2026-08-16T20:00:00+09:00", "payload": {"event": "MERGE_RECORDED", "repository": "r/x", "pr": 4}}]
        github = {"observed_at": "2026-08-16T20:10:00+09:00", "prs": [{"repository": "r/x", "pr": 4, "state": "closed", "merged": False, "base": "main"}]}
        result = reconcile(trace, github)
        self.assertTrue(any(f["type"] == "SOURCE_CONFLICT" for f in result["findings"]))

    def test_older_snapshot_does_not_refute_newer_trace_merge(self):
        trace = [{
            "record_id": "r2", "source_order": 2, "captured_at": "2026-08-16T20:20:00+09:00",
            "payload": {"event": "MERGE_RECORDED", "repository": "r/x", "pr": 4}
        }]
        github = {"observed_at": "2026-08-16T20:10:00+09:00", "prs": [
            {"repository": "r/x", "pr": 4, "state": "open", "merged": False, "base": "main"}
        ]}
        result = reconcile(trace, github)
        self.assertFalse(any(f["type"] == "SOURCE_CONFLICT" for f in result["findings"]))

    def test_newer_observation_time_beats_later_ingest_order(self):
        trace = [
            {"record_id": "new", "source_order": 1, "captured_at": "2026-08-16T20:20:00+09:00", "payload": {"event": "MERGE_RECORDED", "repository": "r/x", "pr": 4}},
            {"record_id": "old-retro", "source_order": 2, "captured_at": "2026-08-16T20:30:00+09:00", "source_timestamp": "2026-08-16T20:00:00+09:00", "payload": {"event": "PR_STATE_OBSERVED", "repository": "r/x", "pr": 4, "state": "open", "merged": False}},
        ]
        github = {"observed_at": "2026-08-16T20:25:00+09:00", "prs": [
            {"repository": "r/x", "pr": 4, "state": "closed", "merged": True, "base": "main"}
        ]}
        result = reconcile(trace, github)
        self.assertFalse(any(f["type"] == "MISSING_MERGE_TRANSITION" for f in result["findings"]))

    def test_snapshot_predating_claim_is_unchecked_not_conflict(self):
        github = {"observed_at": "2026-08-16T20:10:00+09:00", "prs": [
            {"repository": "r/x", "pr": 7, "state": "open", "merged": False, "base": "main"}
        ]}
        claims = [{"repository": "r/x", "pr": 7, "claim": "MERGED_TO_TARGET", "target_branch": "main", "claimed_at": "2026-08-16T20:20:00+09:00"}]
        result = reconcile([], github, claims)
        self.assertTrue(any(f["type"] == "CLAIM_UNCHECKED" for f in result["findings"]))
        self.assertFalse(any(f["type"] == "CLAIM_CONFLICT" for f in result["findings"]))

    def test_missing_freshness_does_not_create_source_conflict(self):
        trace = [{"record_id": "r1", "source_order": 1, "payload": {"event": "MERGE_RECORDED", "repository": "r/x", "pr": 4}}]
        github = {"prs": [{"repository": "r/x", "pr": 4, "state": "open", "merged": False, "base": "main"}]}
        result = reconcile(trace, github)
        self.assertTrue(any(f["type"] == "STATE_FRESHNESS_UNKNOWN" for f in result["findings"]))
        self.assertFalse(any(f["type"] == "SOURCE_CONFLICT" for f in result["findings"]))

    def test_claim_without_time_or_order_is_unchecked(self):
        github = {"prs": [{"repository": "r/x", "pr": 7, "state": "open", "merged": False, "base": "main"}]}
        claims = [{"repository": "r/x", "pr": 7, "claim": "MERGED_TO_TARGET", "target_branch": "main"}]
        result = reconcile([], github, claims)
        self.assertTrue(any(f["type"] == "CLAIM_UNCHECKED" for f in result["findings"]))
        self.assertFalse(any(f["type"] == "CLAIM_CONFLICT" for f in result["findings"]))


if __name__ == "__main__":
    unittest.main()
