import unittest

from tools.interop_observer import (
    observe_interop_envelope,
    seal_source_record_candidate,
    trace_envelope_from_record,
)


def envelope(artifact_type="RESULT", **overrides):
    value = {
        "contract_version": "rts-interop/v1",
        "artifact_type": artifact_type,
        "artifact_id": "artifact-1",
        "created_at": "2026-09-05T06:00:00+00:00",
        "producer": {
            "repository": "nobutakayamauchi/connector-hub",
            "component": "interop.connector_runtime",
            "commit": "abc123",
        },
        "subject": {
            "unit_id": "unit-1",
            "target_artifact_id": "unit-1",
            "target_identity": None,
            "parent_artifact_ids": ["unit-1"],
        },
        "intended_consumers": ["nobutakayamauchi/right-arm"],
        "state": "FINAL",
        "evidence_refs": [],
        "authority": {
            "execution": False,
            "external_action": False,
            "promotion": False,
        },
        "payload": {"status": "READY", "large_result": {"secret": "not copied"}},
    }
    value.update(overrides)
    return value


class InteropObserverTests(unittest.TestCase):
    def test_result_observation_does_not_claim_completion_or_copy_payload(self):
        source = envelope()

        candidate = observe_interop_envelope(
            source, captured_at="2026-09-05T06:01:00+00:00"
        )

        self.assertEqual(candidate["payload"]["event"], "RESULT_OBSERVED")
        self.assertEqual(candidate["payload"]["result_status"], "READY")
        self.assertNotIn("large_result", candidate["payload"])
        self.assertEqual(candidate["uncertainty"], "SUPPORTED")
        self.assertEqual(
            candidate["payload"]["interop"]["artifact_state"], "FINAL"
        )

    def test_gate_verdict_maps_only_to_observed_gate_event(self):
        passed = envelope(
            artifact_type="GATE_RESULT",
            verdict="PASS",
            payload={"check": "tests"},
        )
        failed = envelope(
            artifact_type="GATE_RESULT",
            verdict="FAIL",
            payload={"check": "tests"},
        )

        self.assertEqual(
            observe_interop_envelope(passed)["payload"]["event"], "GATE_PASSED"
        )
        self.assertEqual(
            observe_interop_envelope(failed)["payload"]["event"], "GATE_FAILED"
        )

    def test_human_decision_requires_explicit_actor_and_target_binding(self):
        approval = envelope(
            artifact_type="APPROVAL",
            subject={
                "unit_id": "unit-1",
                "target_artifact_id": "unit-1",
                "target_identity": None,
                "parent_artifact_ids": ["unit-1"],
            },
            payload={
                "decision": "APPROVE",
                "approved_by": "human",
                "reason": "explicit approval",
            },
        )

        candidate = observe_interop_envelope(approval)

        self.assertEqual(candidate["payload"]["event"], "HUMAN_DECISION")
        self.assertEqual(candidate["actor"], "human")
        self.assertEqual(candidate["payload"]["decision"], "APPROVE")

        unbound = envelope(
            artifact_type="APPROVAL",
            subject={
                "unit_id": "unit-1",
                "target_artifact_id": None,
                "target_identity": None,
                "parent_artifact_ids": [],
            },
            payload={"decision": "APPROVE", "approved_by": "human"},
        )
        with self.assertRaises(ValueError):
            observe_interop_envelope(unbound)

    def test_promotion_is_observed_not_automatically_frozen(self):
        decision = envelope(
            artifact_type="PROMOTION_DECISION",
            disposition="PROMOTE",
            authority={
                "execution": False,
                "external_action": False,
                "promotion": True,
            },
            payload={},
        )

        candidate = observe_interop_envelope(decision)

        self.assertEqual(
            candidate["payload"]["event"], "PROMOTION_DECISION_OBSERVED"
        )
        self.assertNotEqual(candidate["payload"]["event"], "FREEZE_RECORD_OBSERVED")

    def test_source_record_hashing_is_deterministic_and_chained(self):
        candidate = observe_interop_envelope(
            envelope(), captured_at="2026-09-05T06:01:00+00:00"
        )

        first = seal_source_record_candidate(
            candidate,
            record_id="r1",
            source_order=1,
            previous_record_hash=None,
        )
        again = seal_source_record_candidate(
            candidate,
            record_id="r1",
            source_order=1,
            previous_record_hash=None,
        )
        second = seal_source_record_candidate(
            candidate,
            record_id="r2",
            source_order=2,
            previous_record_hash=first["record_hash"],
        )

        self.assertEqual(first["record_hash"], again["record_hash"])
        self.assertEqual(second["previous_record_hash"], first["record_hash"])
        self.assertNotEqual(first["record_hash"], second["record_hash"])

    def test_trace_envelope_explicitly_says_archive_append_is_not_completed(self):
        source = envelope()
        candidate = observe_interop_envelope(
            source, captured_at="2026-09-05T06:01:00+00:00"
        )
        record = seal_source_record_candidate(
            candidate,
            record_id="r1",
            source_order=1,
            previous_record_hash=None,
        )

        trace = trace_envelope_from_record(
            record,
            source_artifact_id=source["artifact_id"],
            source_repository=source["producer"]["repository"],
        )

        self.assertEqual(trace["artifact_type"], "TRACE")
        self.assertFalse(trace["authority"]["execution"])
        self.assertFalse(trace["authority"]["promotion"])
        self.assertTrue(trace["payload"]["archive_append_required"])
        self.assertFalse(trace["payload"]["archive_append_completed"])

    def test_missing_explicit_authority_vector_fails_closed(self):
        bad = envelope()
        del bad["authority"]

        with self.assertRaises(ValueError):
            observe_interop_envelope(bad)


if __name__ == "__main__":
    unittest.main()
