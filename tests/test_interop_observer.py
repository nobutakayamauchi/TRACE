import hashlib
import json
import unittest

from tools.interop_observer import observe_interop_envelope, seal_source_record_candidate, trace_envelope_from_record

OBSERVER_ID = {"service": "trace-local", "workspace": "test"}
OBSERVER_COMMIT = "trace-commit-123"
TARGET_SHA = "a" * 64


def sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def envelope(artifact_type="RESULT", **overrides):
    value = {
        "contract_version": "rts-interop/v1", "artifact_type": artifact_type, "artifact_id": "artifact-1",
        "created_at": "2026-09-05T06:00:00+00:00",
        "producer": {"repository": "nobutakayamauchi/connector-hub", "component": "interop", "commit": "abc123", "runtime_identity": None},
        "subject": {"unit_id": "unit-1", "target_artifact_id": "unit-1",
                    "target_identity": {"repository": "nobutakayamauchi/right-arm", "artifact_id": "unit-1", "sha256": TARGET_SHA, "commit": None},
                    "parent_artifact_ids": ["unit-1"]},
        "intended_consumers": ["nobutakayamauchi/right-arm"], "state": "FINAL", "evidence_refs": [],
        "authority": {"execution": False, "external_action": False, "promotion": False}, "authorization_refs": [],
        "payload": {"status": "READY", "large_result": {"secret": "not copied"}},
    }
    value.update(overrides)
    return value


def observe(value, *, resolver=None, human_verifier=None):
    return observe_interop_envelope(value, observer_runtime_identity=OBSERVER_ID, observer_commit=OBSERVER_COMMIT,
                                    payload_ref_resolver=resolver, human_identity_verifier=human_verifier,
                                    captured_at="2026-09-05T06:01:00+00:00")


class InteropObserverTests(unittest.TestCase):
    def test_payload_requires_immutable_digest_bound_ref_and_resolved_hash(self):
        source = envelope()
        digest = sha(source["payload"])
        source["evidence_refs"] = [{"kind": "content_addressed_artifact", "ref": "mutable:latest", "digest": digest}]
        self.assertEqual(observe(source, resolver=lambda _: source["payload"])["uncertainty"], "UNKNOWN")
        source["evidence_refs"] = [{"kind": "content_addressed_artifact", "ref": f"sha256:{digest}", "digest": digest}]
        self.assertEqual(observe(source)["uncertainty"], "UNKNOWN")
        self.assertEqual(observe(source, resolver=lambda _: {"wrong": True})["uncertainty"], "UNKNOWN")
        self.assertEqual(observe(source, resolver=lambda _: source["payload"])["uncertainty"], "SUPPORTED")

    def test_verified_ref_is_snapshotted_before_resolver_mutates_source(self):
        source = envelope()
        digest = sha(source["payload"])
        source["evidence_refs"] = [{"kind": "content_addressed_artifact", "ref": f"sha256:{digest}", "digest": digest}]
        def resolver(_):
            source["evidence_refs"][0]["ref"] = "mutable:latest"
            return source["payload"]
        candidate = observe(source, resolver=resolver)
        self.assertEqual(candidate["uncertainty"], "SUPPORTED")
        self.assertEqual(candidate["payload"]["interop"]["durable_payload_ref"]["ref"], f"sha256:{digest}")

    def test_decision_target_requires_canonical_sha256(self):
        bad = envelope(artifact_type="APPROVAL", payload={"decision": "APPROVE", "approved_by_asserted": "human-1"})
        bad["subject"]["target_identity"]["sha256"] = "latest"
        with self.assertRaises(ValueError):
            observe(bad)

    def test_approval_human_verification_is_bound_to_exact_envelope_digest(self):
        approval = envelope(artifact_type="APPROVAL", payload={"decision": "APPROVE", "approved_by_asserted": "human-1"},
                            evidence_refs=[{"kind": "human_identity_evidence", "ref": "human-session:1"}])
        expected_digest = sha(approval)
        candidate = observe(approval, human_verifier=lambda ref, actor, digest: ref["ref"] == "human-session:1" and actor == "human-1" and digest == expected_digest)
        self.assertEqual(candidate["payload"]["event"], "HUMAN_DECISION")
        substituted = dict(approval); substituted["artifact_id"] = "substituted"
        candidate2 = observe(substituted, human_verifier=lambda ref, actor, digest: digest == expected_digest)
        self.assertEqual(candidate2["payload"]["event"], "APPROVAL_ARTIFACT_OBSERVED")

    def test_gate_events_are_observations_only(self):
        self.assertEqual(observe(envelope(artifact_type="GATE_RESULT", verdict="PASS", payload={"check": "tests"}))["payload"]["event"], "GATE_PASSED")

    def test_preappend_trace_is_proposed_and_sealed_identity_bound(self):
        source = envelope()
        record = seal_source_record_candidate(observe(source), record_id="r1", source_order=1, previous_record_hash=None)
        trace = trace_envelope_from_record(record, source_artifact_id=source["artifact_id"], source_repository=source["producer"]["repository"], observer_runtime_identity=OBSERVER_ID, observer_commit=OBSERVER_COMMIT)
        self.assertEqual(trace["state"], "PROPOSED")
        self.assertEqual(trace["evidence_refs"], [])
        with self.assertRaises(PermissionError):
            trace_envelope_from_record(record, source_artifact_id=source["artifact_id"], source_repository=source["producer"]["repository"], observer_runtime_identity={"service": "other"}, observer_commit=OBSERVER_COMMIT)

    def test_mutated_sealed_record_is_rejected(self):
        source = envelope()
        record = seal_source_record_candidate(observe(source), record_id="r1", source_order=1, previous_record_hash=None)
        record["payload"]["interop"]["artifact_id"] = "tampered"
        with self.assertRaises(PermissionError):
            trace_envelope_from_record(record, source_artifact_id="tampered", source_repository=source["producer"]["repository"], observer_runtime_identity=OBSERVER_ID, observer_commit=OBSERVER_COMMIT)

    def test_missing_observer_identity_fails_closed(self):
        with self.assertRaises(ValueError):
            observe_interop_envelope(envelope(), observer_runtime_identity={}, observer_commit=OBSERVER_COMMIT)


if __name__ == "__main__":
    unittest.main()
