import hashlib
import json
import unittest

from tools.interop_observer import (
    observe_interop_envelope,
    seal_source_record_candidate,
    trace_envelope_from_record,
)

OBSERVER_ID = {"service": "trace-local", "workspace": "test"}
OBSERVER_COMMIT = "trace-commit-123"
TARGET_SHA = "a" * 64


def sha(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def envelope(artifact_type="RESULT", **overrides):
    value = {
        "contract_version": "rts-interop/v1",
        "artifact_type": artifact_type,
        "artifact_id": "artifact-1",
        "created_at": "2026-09-05T06:00:00+00:00",
        "producer": {"repository": "nobutakayamauchi/connector-hub", "component": "interop.connector_runtime", "commit": "abc123", "runtime_identity": None},
        "subject": {
            "unit_id": "unit-1", "target_artifact_id": "unit-1",
            "target_identity": {"repository": "nobutakayamauchi/right-arm", "artifact_id": "unit-1", "sha256": TARGET_SHA, "commit": None},
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
    def test_result_without_content_addressed_payload_is_unknown_gap(self):
        candidate = observe(envelope())
        self.assertEqual(candidate["payload"]["event"], "RESULT_OBSERVED")
        self.assertEqual(candidate["uncertainty"], "UNKNOWN")
        self.assertTrue(candidate["payload"]["interop"]["reconstruction_gap"])

    def test_arbitrary_file_or_raw_reference_does_not_hide_reconstruction_gap(self):
        for ref in (
            {"kind": "source_file", "ref": "/tmp/nonexistent"},
            {"kind": "connector_raw_reference", "ref": "github:fixture:pulls"},
        ):
            source = envelope(evidence_refs=[ref])
            candidate = observe(source)
            self.assertEqual(candidate["uncertainty"], "UNKNOWN")
            self.assertTrue(candidate["payload"]["interop"]["reconstruction_gap"])

    def test_exact_content_addressed_payload_reference_is_supported(self):
        source = envelope()
        payload_digest = sha(source["payload"])
        source["evidence_refs"] = [{
            "kind": "content_addressed_artifact",
            "ref": f"sha256:{payload_digest}",
            "digest": payload_digest,
        }]
        candidate = observe(source)
        self.assertEqual(candidate["uncertainty"], "SUPPORTED")
        self.assertFalse(candidate["payload"]["interop"]["reconstruction_gap"])
        self.assertEqual(candidate["payload"]["interop"]["durable_payload_ref"]["digest"], payload_digest)

    def test_wrong_content_digest_remains_unknown(self):
        source = envelope(evidence_refs=[{
            "kind": "content_addressed_artifact",
            "ref": "sha256:wrong",
            "digest": "b" * 64,
        }])
        candidate = observe(source)
        self.assertEqual(candidate["uncertainty"], "UNKNOWN")

    def test_gate_verdict_maps_only_to_observed_gate_event(self):
        self.assertEqual(observe(envelope(artifact_type="GATE_RESULT", verdict="PASS", payload={"check": "tests"}))["payload"]["event"], "GATE_PASSED")
        self.assertEqual(observe(envelope(artifact_type="GATE_RESULT", verdict="FAIL", payload={"check": "tests"}))["payload"]["event"], "GATE_FAILED")

    def test_unverified_approval_is_not_human_decision(self):
        approval = envelope(artifact_type="APPROVAL", payload={"decision": "APPROVE", "approved_by": "ci-bot"})
        candidate = observe(approval)
        self.assertEqual(candidate["payload"]["event"], "APPROVAL_ARTIFACT_OBSERVED")
        self.assertIsNone(candidate["actor"])

    def test_verified_human_identity_can_emit_human_decision(self):
        approval = envelope(
            artifact_type="APPROVAL",
            payload={"decision": "APPROVE", "approved_by": "human-1"},
            evidence_refs=[{"kind": "human_identity_evidence", "ref": "human-session:1", "identity": {"actor": "human-1", "verified": True}}],
        )
        candidate = observe(approval)
        self.assertEqual(candidate["payload"]["event"], "HUMAN_DECISION")
        self.assertEqual(candidate["actor"], "human-1")

    def test_preappend_trace_is_proposed_and_provenance_bound(self):
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
        self.assertEqual(trace["state"], "PROPOSED")
        self.assertEqual(trace["evidence_refs"], [])
        self.assertFalse(trace["payload"]["archive_append_completed"])
        self.assertEqual(trace["producer"]["runtime_identity"], OBSERVER_ID)

        with self.assertRaises(ValueError):
            trace_envelope_from_record(
                record,
                source_artifact_id="other-artifact",
                source_repository=source["producer"]["repository"],
                observer_runtime_identity=OBSERVER_ID,
                observer_commit=OBSERVER_COMMIT,
            )

    def test_missing_observer_identity_or_authority_vector_fails_closed(self):
        with self.assertRaises(ValueError):
            observe_interop_envelope(envelope(), observer_runtime_identity={}, observer_commit=OBSERVER_COMMIT)
        bad = envelope()
        del bad["authority"]
        with self.assertRaises(ValueError):
            observe(bad)


if __name__ == "__main__":
    unittest.main()
