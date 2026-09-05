import unittest

from tools.interop_observer import (
    observe_interop_envelope,
    seal_source_record_candidate,
    trace_envelope_from_record,
)

OBSERVER_ID = {"service": "trace-local", "workspace": "test"}
OBSERVER_COMMIT = "trace-commit-123"
TARGET_SHA = "a" * 64


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
            "runtime_identity": None,
        },
        "subject": {
            "unit_id": "unit-1",
            "target_artifact_id": "unit-1",
            "target_identity": {
                "repository": "nobutakayamauchi/right-arm",
                "artifact_id": "unit-1",
                "sha256": TARGET_SHA,
                "commit": None,
            },
            "parent_artifact_ids": ["unit-1"],
        },
        "intended_consumers": ["nobutakayamauchi/right-arm"],
        "state": "FINAL",
        "evidence_refs": [],
        "authority": {"execution": False, "external_action": False, "promotion": False},
        "authorization_refs": [],
        "payload": {"status": "READY", "large_result": {"secret": "not copied"}},
    }
    value.update(overrides)
    return value


def observe(value):
    return observe_interop_envelope(
        value,
        observer_runtime_identity=OBSERVER_ID,
        observer_commit=OBSERVER_COMMIT,
        captured_at="2026-09-05T06:01:00+00:00",
    )


class InteropObserverTests(unittest.TestCase):
    def test_result_without_durable_payload_reference_is_unknown_gap(self):
        candidate = observe(envelope())
        self.assertEqual(candidate["payload"]["event"], "RESULT_OBSERVED")
        self.assertEqual(candidate["uncertainty"], "UNKNOWN")
        self.assertTrue(candidate["payload"]["interop"]["reconstruction_gap"])
        self.assertNotIn("large_result", candidate["payload"])

    def test_result_with_durable_reference_is_supported_observation(self):
        source = envelope(
            evidence_refs=[
                {
                    "kind": "connector_raw_reference",
                    "ref": "github:fixture:pulls",
                }
            ]
        )
        candidate = observe(source)
        self.assertEqual(candidate["uncertainty"], "SUPPORTED")
        self.assertFalse(candidate["payload"]["interop"]["reconstruction_gap"])
        self.assertEqual(
            candidate["payload"]["interop"]["durable_payload_ref"]["ref"],
            "github:fixture:pulls",
        )

    def test_gate_verdict_maps_only_to_observed_gate_event(self):
        passed = envelope(artifact_type="GATE_RESULT", verdict="PASS", payload={"check": "tests"})
        failed = envelope(artifact_type="GATE_RESULT", verdict="FAIL", payload={"check": "tests"})
        self.assertEqual(observe(passed)["payload"]["event"], "GATE_PASSED")
        self.assertEqual(observe(failed)["payload"]["event"], "GATE_FAILED")

    def test_unverified_approval_is_not_human_decision(self):
        approval = envelope(
            artifact_type="APPROVAL",
            payload={"decision": "APPROVE", "approved_by": "ci-bot"},
        )
        candidate = observe(approval)
        self.assertEqual(candidate["payload"]["event"], "APPROVAL_ARTIFACT_OBSERVED")
        self.assertIsNone(candidate["actor"])
        self.assertFalse(candidate["payload"]["human_actor_established"])

    def test_verified_human_identity_can_emit_human_decision(self):
        approval = envelope(
            artifact_type="APPROVAL",
            payload={"decision": "APPROVE", "approved_by": "human-1"},
            evidence_refs=[
                {
                    "kind": "human_identity_evidence",
                    "ref": "human-session:1",
                    "identity": {"actor": "human-1", "verified": True},
                }
            ],
        )
        candidate = observe(approval)
        self.assertEqual(candidate["payload"]["event"], "HUMAN_DECISION")
        self.assertEqual(candidate["actor"], "human-1")

    def test_promotion_is_observed_not_automatically_frozen(self):
        decision = envelope(
            artifact_type="PROMOTION_DECISION",
            disposition="PROMOTE",
            producer={
                "repository": "nobutakayamauchi/right-arm",
                "runtime_identity": {"surface": "local"},
            },
            authority={"execution": False, "external_action": False, "promotion": True},
            authorization_refs=[
                {
                    "kind": "PROMOTION_AUTHORIZATION",
                    "ref": "chat:promotion",
                    "issuer": "human",
                    "scope": ["promotion:bounded"],
                    "target_sha256": TARGET_SHA,
                    "issuer_identity": {"surface": "local"},
                }
            ],
            payload={},
        )
        candidate = observe(decision)
        self.assertEqual(candidate["payload"]["event"], "PROMOTION_DECISION_OBSERVED")

    def test_source_record_hashing_is_deterministic_and_chained(self):
        candidate = observe(envelope())
        first = seal_source_record_candidate(candidate, record_id="r1", source_order=1, previous_record_hash=None)
        again = seal_source_record_candidate(candidate, record_id="r1", source_order=1, previous_record_hash=None)
        second = seal_source_record_candidate(candidate, record_id="r2", source_order=2, previous_record_hash=first["record_hash"])
        self.assertEqual(first["record_hash"], again["record_hash"])
        self.assertEqual(second["previous_record_hash"], first["record_hash"])

    def test_preappend_trace_is_proposed_and_has_no_final_evidence_reference(self):
        source = envelope()
        candidate = observe(source)
        record = seal_source_record_candidate(candidate, record_id="r1", source_order=1, previous_record_hash=None)
        trace = trace_envelope_from_record(
            record,
            source_artifact_id=source["artifact_id"],
            source_repository=source["producer"]["repository"],
            observer_runtime_identity=OBSERVER_ID,
            observer_commit=OBSERVER_COMMIT,
        )
        self.assertEqual(trace["artifact_type"], "TRACE")
        self.assertEqual(trace["state"], "PROPOSED")
        self.assertEqual(trace["evidence_refs"], [])
        self.assertFalse(trace["payload"]["archive_append_completed"])
        self.assertIsNone(trace["payload"]["final_trace_evidence_ref"])
        self.assertEqual(trace["producer"]["runtime_identity"], OBSERVER_ID)

    def test_missing_observer_identity_fails_closed(self):
        with self.assertRaises(ValueError):
            observe_interop_envelope(
                envelope(),
                observer_runtime_identity={},
                observer_commit=OBSERVER_COMMIT,
            )

    def test_missing_explicit_authority_vector_fails_closed(self):
        bad = envelope()
        del bad["authority"]
        with self.assertRaises(ValueError):
            observe(bad)


if __name__ == "__main__":
    unittest.main()
