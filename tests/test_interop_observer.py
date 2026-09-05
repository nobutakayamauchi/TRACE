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


def observe(value, *, resolver=None, human_verifier=None):
    return observe_interop_envelope(
        value,
        observer_runtime_identity=OBSERVER_ID,
        observer_commit=OBSERVER_COMMIT,
        payload_ref_resolver=resolver,
        human_identity_verifier=human_verifier,
        captured_at="2026-09-05T06:01:00+00:00",
    )


class InteropObserverTests(unittest.TestCase):
    def test_result_without_verified_content_addressed_payload_is_unknown_gap(self):
        candidate = observe(envelope())
        self.assertEqual(candidate["payload"]["event"], "RESULT_OBSERVED")
        self.assertEqual(candidate["uncertainty"], "UNKNOWN")
        self.assertTrue(candidate["payload"]["interop"]["reconstruction_gap"])

    def test_arbitrary_file_or_raw_reference_does_not_hide_reconstruction_gap(self):
        for ref in (
            {"kind": "source_file", "ref": "/tmp/nonexistent"},
            {"kind": "connector_raw_reference", "ref": "github:fixture:pulls"},
        ):
            candidate = observe(envelope(evidence_refs=[ref]), resolver=lambda _: {"fake": True})
            self.assertEqual(candidate["uncertainty"], "UNKNOWN")

    def test_content_addressed_payload_requires_actual_resolve_and_hash_match(self):
        source = envelope()
        payload_digest = sha(source["payload"])
        ref = {
            "kind": "content_addressed_artifact",
            "ref": f"sha256:{payload_digest}",
            "digest": payload_digest,
        }
        source["evidence_refs"] = [ref]

        no_resolver = observe(source)
        self.assertEqual(no_resolver["uncertainty"], "UNKNOWN")

        wrong_bytes = observe(source, resolver=lambda _: {"different": "payload"})
        self.assertEqual(wrong_bytes["uncertainty"], "UNKNOWN")

        verified = observe(source, resolver=lambda _: source["payload"])
        self.assertEqual(verified["uncertainty"], "SUPPORTED")
        self.assertFalse(verified["payload"]["interop"]["reconstruction_gap"])
        self.assertEqual(
            verified["payload"]["interop"]["durable_payload_ref"]["digest"],
            payload_digest,
        )

    def test_gate_verdict_maps_only_to_observed_gate_event(self):
        self.assertEqual(
            observe(envelope(artifact_type="GATE_RESULT", verdict="PASS", payload={"check": "tests"}))["payload"]["event"],
            "GATE_PASSED",
        )
        self.assertEqual(
            observe(envelope(artifact_type="GATE_RESULT", verdict="FAIL", payload={"check": "tests"}))["payload"]["event"],
            "GATE_FAILED",
        )

    def test_claimed_human_identity_without_trusted_verifier_is_not_human_decision(self):
        approval = envelope(
            artifact_type="APPROVAL",
            payload={"decision": "APPROVE", "approved_by": "human-1"},
            evidence_refs=[{"kind": "human_identity_evidence", "ref": "human-session:1"}],
        )
        candidate = observe(approval)
        self.assertEqual(candidate["payload"]["event"], "APPROVAL_ARTIFACT_OBSERVED")
        self.assertIsNone(candidate["actor"])

    def test_trusted_human_verifier_can_emit_human_decision(self):
        approval = envelope(
            artifact_type="APPROVAL",
            payload={"decision": "APPROVE", "approved_by": "human-1"},
            evidence_refs=[{"kind": "human_identity_evidence", "ref": "human-session:1"}],
        )
        candidate = observe(
            approval,
            human_verifier=lambda ref, actor: ref["ref"] == "human-session:1" and actor == "human-1",
        )
        self.assertEqual(candidate["payload"]["event"], "HUMAN_DECISION")
        self.assertEqual(candidate["actor"], "human-1")

    def test_preappend_trace_is_proposed_and_provenance_bound(self):
        source = envelope()
        candidate = observe(source)
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
            observer_runtime_identity=OBSERVER_ID,
            observer_commit=OBSERVER_COMMIT,
        )
        self.assertEqual(trace["state"], "PROPOSED")
        self.assertEqual(trace["evidence_refs"], [])
        self.assertFalse(trace["payload"]["archive_append_completed"])

        with self.assertRaises(ValueError):
            trace_envelope_from_record(
                record,
                source_artifact_id="other-artifact",
                source_repository=source["producer"]["repository"],
                observer_runtime_identity=OBSERVER_ID,
                observer_commit=OBSERVER_COMMIT,
            )

    def test_mutated_sealed_record_is_rejected_before_trace_derivation(self):
        source = envelope()
        candidate = observe(source)
        record = seal_source_record_candidate(
            candidate,
            record_id="r1",
            source_order=1,
            previous_record_hash=None,
        )
        record["payload"]["interop"]["artifact_id"] = "tampered"
        with self.assertRaises(PermissionError):
            trace_envelope_from_record(
                record,
                source_artifact_id="tampered",
                source_repository=source["producer"]["repository"],
                observer_runtime_identity=OBSERVER_ID,
                observer_commit=OBSERVER_COMMIT,
            )

    def test_sealing_snapshots_candidate_payload(self):
        candidate = observe(envelope())
        record = seal_source_record_candidate(candidate, record_id="r1", source_order=1, previous_record_hash=None)
        candidate["payload"]["interop"]["artifact_id"] = "changed-later"
        self.assertEqual(record["payload"]["interop"]["artifact_id"], "artifact-1")

    def test_missing_observer_identity_or_authority_vector_fails_closed(self):
        with self.assertRaises(ValueError):
            observe_interop_envelope(
                envelope(),
                observer_runtime_identity={},
                observer_commit=OBSERVER_COMMIT,
            )
        bad = envelope()
        del bad["authority"]
        with self.assertRaises(ValueError):
            observe(bad)


if __name__ == "__main__":
    unittest.main()
