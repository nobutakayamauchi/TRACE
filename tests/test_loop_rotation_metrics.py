from __future__ import annotations

import unittest

from tools.loop_rotation_metrics import measure


def ev(uid: str, event: str, t: str, **extra):
    payload = {"event_uid": uid, "run_id": "R", "event": event, "observed_at": t}
    if event == "RUN_STARTED":
        payload["measurement_profile"] = "TRACE-UL-ROTATION-v0"
    payload.update(extra)
    return {"record_id": uid, "payload": payload}


def good_run():
    return [
        ev("e1", "RUN_STARTED", "2026-08-16T20:00:00+09:00"),
        ev("e2", "SPAN_STARTED", "2026-08-16T20:00:01+09:00", span_id="l1", stage="LOOP_ITERATION", workstream_id="main", cycle_seq=1, clock_domain="c", monotonic_ns=1_000_000_000),
        ev("e3", "FINDING_OPENED", "2026-08-16T20:00:05+09:00", finding_id="F1", root_cause_id="RC1"),
        ev("e4", "SPAN_FINISHED", "2026-08-16T20:00:11+09:00", span_id="l1", stage="LOOP_ITERATION", workstream_id="main", cycle_seq=1, clock_domain="c", monotonic_ns=11_000_000_000),
        ev("e5", "SPAN_STARTED", "2026-08-16T20:00:12+09:00", span_id="l2", stage="LOOP_ITERATION", workstream_id="main", cycle_seq=2, clock_domain="c", monotonic_ns=12_000_000_000),
        ev("e6", "LOOP_REOPENED", "2026-08-16T20:00:13+09:00", cause_event_ids=["e3"], workstream_id="main", from_cycle_seq=1, to_cycle_seq=2),
        ev("e7", "SPAN_FINISHED", "2026-08-16T20:00:22+09:00", span_id="l2", stage="LOOP_ITERATION", workstream_id="main", cycle_seq=2, clock_domain="c", monotonic_ns=22_000_000_000),
        ev("e8", "RUN_STOPPED", "2026-08-16T20:00:23+09:00"),
    ]


class RotationMetricsTests(unittest.TestCase):
    def test_complete_run_is_measured(self):
        result = measure(good_run(), "R")
        self.assertEqual(result["metric_status"], "MEASURED")
        self.assertEqual(result["coverage_scope"], "COMPLETE_RUN")
        self.assertEqual(result["completed_loop_iterations"], 2)
        self.assertEqual(result["max_parallel_loop_iterations"], 1)

    def test_no_loop_spans_is_insufficient(self):
        result = measure([
            ev("a", "RUN_STARTED", "2026-08-16T20:00:00+09:00"),
            ev("b", "RUN_STOPPED", "2026-08-16T20:00:01+09:00"),
        ], "R")
        self.assertEqual(result["metric_status"], "INSUFFICIENT")

    def test_unmatched_span_is_not_silently_counted(self):
        result = measure([
            ev("a", "RUN_STARTED", "2026-08-16T20:00:00+09:00"),
            ev("b", "SPAN_STARTED", "2026-08-16T20:00:01+09:00", span_id="x", stage="LOOP_ITERATION", workstream_id="m", cycle_seq=1),
            ev("c", "RUN_STOPPED", "2026-08-16T20:00:02+09:00"),
        ], "R")
        self.assertEqual(result["metric_status"], "INSUFFICIENT")
        self.assertEqual(result["quality"]["unmatched_spans"], 1)

    def test_duplicate_cycle_does_not_inflate_count(self):
        rows = [ev("a", "RUN_STARTED", "2026-08-16T20:00:00+09:00")]
        for i, sid in enumerate(("x", "y"), 1):
            rows.extend([
                ev(f"s{i}", "SPAN_STARTED", f"2026-08-16T20:00:0{i}+09:00", span_id=sid, stage="LOOP_ITERATION", workstream_id="m", cycle_seq=1),
                ev(f"f{i}", "SPAN_FINISHED", f"2026-08-16T20:00:1{i}+09:00", span_id=sid, stage="LOOP_ITERATION", workstream_id="m", cycle_seq=1),
            ])
        rows.append(ev("z", "RUN_STOPPED", "2026-08-16T20:00:20+09:00"))
        result = measure(rows, "R")
        self.assertEqual(result["completed_loop_iterations"], 1)
        self.assertEqual(result["metric_status"], "PARTIAL")

    def test_cycle_gap_is_visible(self):
        rows = [
            ev("a", "RUN_STARTED", "2026-08-16T20:00:00+09:00"),
            ev("s1", "SPAN_STARTED", "2026-08-16T20:00:01+09:00", span_id="x", stage="LOOP_ITERATION", workstream_id="m", cycle_seq=1),
            ev("f1", "SPAN_FINISHED", "2026-08-16T20:00:02+09:00", span_id="x", stage="LOOP_ITERATION", workstream_id="m", cycle_seq=1),
            ev("s3", "SPAN_STARTED", "2026-08-16T20:00:03+09:00", span_id="z", stage="LOOP_ITERATION", workstream_id="m", cycle_seq=3),
            ev("f3", "SPAN_FINISHED", "2026-08-16T20:00:04+09:00", span_id="z", stage="LOOP_ITERATION", workstream_id="m", cycle_seq=3),
            ev("b", "RUN_STOPPED", "2026-08-16T20:00:05+09:00"),
        ]
        result = measure(rows, "R")
        self.assertEqual(result["metric_status"], "PARTIAL")
        self.assertEqual(result["quality"]["cycle_gap_count"], 1)

    def test_reopen_without_cause_downgrades_causality(self):
        rows = good_run()
        rows[5] = ev("e6", "LOOP_REOPENED", "2026-08-16T20:00:13+09:00", workstream_id="main", from_cycle_seq=1, to_cycle_seq=2)
        result = measure(rows, "R")
        self.assertEqual(result["metric_status"], "PARTIAL")
        self.assertEqual(result["causal_link_status"], "PARTIAL")

    def test_parallel_workstreams_are_counted(self):
        rows = [
            ev("a", "RUN_STARTED", "2026-08-16T20:00:00+09:00"),
            ev("s1", "SPAN_STARTED", "2026-08-16T20:00:01+09:00", span_id="x", stage="LOOP_ITERATION", workstream_id="a", cycle_seq=1),
            ev("s2", "SPAN_STARTED", "2026-08-16T20:00:02+09:00", span_id="y", stage="LOOP_ITERATION", workstream_id="b", cycle_seq=1),
            ev("f1", "SPAN_FINISHED", "2026-08-16T20:00:05+09:00", span_id="x", stage="LOOP_ITERATION", workstream_id="a", cycle_seq=1),
            ev("f2", "SPAN_FINISHED", "2026-08-16T20:00:06+09:00", span_id="y", stage="LOOP_ITERATION", workstream_id="b", cycle_seq=1),
            ev("z", "RUN_STOPPED", "2026-08-16T20:00:07+09:00"),
        ]
        self.assertEqual(measure(rows, "R")["max_parallel_loop_iterations"], 2)

    def test_external_wait_is_separate(self):
        rows = good_run()
        rows.insert(-1, ev("w1", "SPAN_STARTED", "2026-08-16T20:00:22+09:00", span_id="wait", stage="EXTERNAL_WAIT", workstream_id="main", cycle_seq=2))
        rows.insert(-1, ev("w2", "SPAN_FINISHED", "2026-08-16T20:00:23+09:00", span_id="wait", stage="EXTERNAL_WAIT", workstream_id="main", cycle_seq=2))
        self.assertEqual(measure(rows, "R")["external_wait"]["count"], 1)

    def test_equal_wall_timestamps_do_not_fake_wall_throughput(self):
        t = "2026-08-16T20:00:00+09:00"
        rows = [
            ev("a", "RUN_STARTED", t),
            ev("s", "SPAN_STARTED", t, span_id="x", stage="LOOP_ITERATION", workstream_id="m", cycle_seq=1, clock_domain="c", monotonic_ns=0),
            ev("f", "SPAN_FINISHED", t, span_id="x", stage="LOOP_ITERATION", workstream_id="m", cycle_seq=1, clock_domain="c", monotonic_ns=1_000_000),
            ev("z", "RUN_STOPPED", t),
        ]
        result = measure(rows, "R")
        self.assertEqual(result["metric_status"], "PARTIAL")
        self.assertIsNone(result["loop_iterations_per_wall_hour"])

    def test_span_identity_mismatch_is_rejected(self):
        rows = [
            ev("a", "RUN_STARTED", "2026-08-16T20:00:00+09:00"),
            ev("s", "SPAN_STARTED", "2026-08-16T20:00:01+09:00", span_id="x", stage="LOOP_ITERATION", workstream_id="m", cycle_seq=1),
            ev("f", "SPAN_FINISHED", "2026-08-16T20:00:02+09:00", span_id="x", stage="LOOP_ITERATION", workstream_id="n", cycle_seq=1),
            ev("z", "RUN_STOPPED", "2026-08-16T20:00:03+09:00"),
        ]
        result = measure(rows, "R")
        self.assertEqual(result["completed_loop_iterations"], 0)
        self.assertEqual(result["metric_status"], "INSUFFICIENT")

    def test_missing_event_uid_downgrades(self):
        rows = good_run()
        rows[0] = {"record_id": "noid", "payload": {"run_id": "R", "event": "RUN_STARTED", "observed_at": "2026-08-16T20:00:00+09:00", "measurement_profile": "TRACE-UL-ROTATION-v0"}}
        self.assertEqual(measure(rows, "R")["metric_status"], "PARTIAL")

    def test_observed_window_cannot_claim_complete_run(self):
        result = measure(good_run()[1:-1], "R")
        self.assertEqual(result["coverage_scope"], "OBSERVED_WINDOW")
        self.assertEqual(result["metric_status"], "PARTIAL")

    def test_duplicate_event_uid_is_deduplicated_and_surfaced(self):
        rows = good_run()
        rows.insert(4, rows[2].copy())
        result = measure(rows, "R")
        self.assertEqual(result["finding_opened"], 1)
        self.assertEqual(result["metric_status"], "PARTIAL")

    def test_multiple_run_boundaries_downgrade(self):
        rows = good_run()
        rows.insert(1, ev("e1b", "RUN_STARTED", "2026-08-16T20:00:00.100000+09:00"))
        result = measure(rows, "R")
        self.assertEqual(result["metric_status"], "PARTIAL")
        self.assertIn("multiple_run_started", result["quality"]["issues"])

    def test_missing_measurement_profile_downgrades(self):
        rows = good_run()
        rows[0] = {"record_id": "e1", "payload": {"event_uid": "e1", "run_id": "R", "event": "RUN_STARTED", "observed_at": "2026-08-16T20:00:00+09:00"}}
        result = measure(rows, "R")
        self.assertEqual(result["metric_status"], "PARTIAL")
        self.assertIn("missing_measurement_profile", result["quality"]["issues"])


if __name__ == "__main__":
    unittest.main()
