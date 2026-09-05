from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

CONTRACT_VERSION = "rts-interop/v1"
TRACE_REPOSITORY = "nobutakayamauchi/TRACE"

_ARTIFACT_EVENTS = {
    "UNIT": "WORK_UNIT_OBSERVED",
    "RESULT": "RESULT_OBSERVED",
    "EVIDENCE": "EVIDENCE_OBSERVED",
    "RETRY_REQUEST": "RETRY_REQUEST_OBSERVED",
    "TRACE": "TRACE_ARTIFACT_OBSERVED",
    "LEARNING_CANDIDATE": "LEARNING_CANDIDATE_OBSERVED",
    "FREEZE_RECORD": "FREEZE_RECORD_OBSERVED",
}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _human_actor_evidence(envelope: dict[str, Any]) -> str | None:
    payload = envelope.get("payload") or {}
    approved_by = payload.get("approved_by")
    if not isinstance(approved_by, str) or not approved_by:
        return None
    for ref in envelope.get("evidence_refs") or []:
        if not isinstance(ref, dict):
            continue
        identity = ref.get("identity") or {}
        if (
            ref.get("kind") == "human_identity_evidence"
            and isinstance(identity, dict)
            and identity.get("actor") == approved_by
            and identity.get("verified") is True
        ):
            return approved_by
    return None


def _event_for(envelope: dict[str, Any]) -> str:
    artifact_type = envelope["artifact_type"]
    if artifact_type == "GATE_RESULT":
        verdict = envelope.get("verdict")
        if verdict == "PASS":
            return "GATE_PASSED"
        if verdict == "FAIL":
            return "GATE_FAILED"
        return "GATE_RESULT_OBSERVED"
    if artifact_type == "APPROVAL":
        return "HUMAN_DECISION" if _human_actor_evidence(envelope) else "APPROVAL_ARTIFACT_OBSERVED"
    if artifact_type == "PROMOTION_DECISION":
        return "PROMOTION_DECISION_OBSERVED"
    return _ARTIFACT_EVENTS[artifact_type]


def _validate_envelope(envelope: dict[str, Any]) -> None:
    if envelope.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("unsupported interop contract version")
    allowed = {
        "UNIT", "RESULT", "EVIDENCE", "GATE_RESULT", "RETRY_REQUEST",
        "APPROVAL", "TRACE", "LEARNING_CANDIDATE", "PROMOTION_DECISION", "FREEZE_RECORD",
    }
    artifact_type = envelope.get("artifact_type")
    if artifact_type not in allowed:
        raise ValueError("unsupported interop artifact type")
    if not envelope.get("artifact_id") or not envelope.get("created_at"):
        raise ValueError("artifact_id and created_at are required")
    producer = envelope.get("producer") or {}
    if not producer.get("repository"):
        raise ValueError("producer.repository is required")
    authority = envelope.get("authority")
    if not isinstance(authority, dict):
        raise ValueError("explicit authority vector is required")
    for key in ("execution", "external_action", "promotion"):
        if not isinstance(authority.get(key), bool):
            raise ValueError(f"authority.{key} must be boolean")
    if artifact_type == "GATE_RESULT" and not envelope.get("verdict"):
        raise ValueError("GATE_RESULT verdict is required")
    if artifact_type == "PROMOTION_DECISION" and not envelope.get("disposition"):
        raise ValueError("PROMOTION_DECISION disposition is required")
    if artifact_type in {"APPROVAL", "PROMOTION_DECISION"}:
        target = (envelope.get("subject") or {}).get("target_identity")
        if not isinstance(target, dict) or not target.get("sha256"):
            raise ValueError(f"{artifact_type} requires immutable target_identity")


def _durable_payload_reference(envelope: dict[str, Any]) -> dict[str, Any] | None:
    for ref in envelope.get("evidence_refs") or []:
        if isinstance(ref, dict) and ref.get("kind") in {
            "content_addressed_artifact",
            "connector_raw_reference",
            "source_file",
            "github_blob",
        } and ref.get("ref"):
            return ref
    return None


def observe_interop_envelope(
    envelope: dict[str, Any],
    *,
    observer_runtime_identity: dict[str, Any],
    observer_commit: str,
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Convert one artifact into a passive TRACE source-record candidate.

    This is observation preparation, not archival append. Missing durable source
    content is preserved as a reconstruction gap rather than mislabeled SUPPORTED.
    """
    _validate_envelope(envelope)
    if not isinstance(observer_runtime_identity, dict) or not observer_runtime_identity:
        raise ValueError("observer runtime identity is required")
    if not observer_commit:
        raise ValueError("observer commit identity is required")

    artifact_type = str(envelope["artifact_type"])
    producer = dict(envelope.get("producer") or {})
    subject = dict(envelope.get("subject") or {})
    payload = dict(envelope.get("payload") or {})
    durable_ref = _durable_payload_reference(envelope)
    human_actor = _human_actor_evidence(envelope) if artifact_type == "APPROVAL" else None
    reconstructable = durable_ref is not None

    observation_payload = {
        "event": _event_for(envelope),
        "observer_identity": {
            "repository": TRACE_REPOSITORY,
            "commit": observer_commit,
            "runtime_identity": observer_runtime_identity,
        },
        "interop": {
            "contract_version": CONTRACT_VERSION,
            "artifact_type": artifact_type,
            "artifact_id": envelope["artifact_id"],
            "artifact_state": envelope.get("state"),
            "producer": producer,
            "subject": subject,
            "verdict": envelope.get("verdict"),
            "disposition": envelope.get("disposition"),
            "authority": dict(envelope["authority"]),
            "authorization_refs": list(envelope.get("authorization_refs") or []),
            "evidence_refs": list(envelope.get("evidence_refs") or []),
            "intended_consumers": list(envelope.get("intended_consumers") or []),
            "payload_sha256": _sha256(payload),
            "envelope_sha256": _sha256(envelope),
            "durable_payload_ref": durable_ref,
            "reconstruction_gap": not reconstructable,
        },
    }
    if artifact_type == "APPROVAL":
        observation_payload["decision"] = payload.get("decision")
        observation_payload["approved_by_asserted"] = payload.get("approved_by")
        observation_payload["human_actor_established"] = human_actor is not None
    elif artifact_type == "RESULT":
        observation_payload["result_status"] = payload.get("status")
    elif artifact_type == "RETRY_REQUEST":
        observation_payload["retry_reason"] = payload.get("reason")

    return {
        "source_type": "rts_interop_artifact",
        "actor": human_actor,
        "source_timestamp": envelope["created_at"],
        "captured_at": captured_at or _now_iso(),
        "payload": observation_payload,
        "provenance": f"{CONTRACT_VERSION}:{producer['repository']}:{envelope['artifact_id']}",
        "uncertainty": "SUPPORTED" if reconstructable else "UNKNOWN",
    }


def seal_source_record_candidate(
    candidate: dict[str, Any],
    *,
    record_id: str,
    source_order: int,
    previous_record_hash: str | None,
) -> dict[str, Any]:
    """Assign deterministic TRACE chain fields without claiming archive persistence."""
    if not record_id:
        raise ValueError("record_id is required")
    if source_order < 1:
        raise ValueError("source_order must be >= 1")
    record = {
        "record_id": record_id,
        "source_type": candidate["source_type"],
        "actor": candidate.get("actor"),
        "source_order": source_order,
        "source_timestamp": candidate.get("source_timestamp"),
        "captured_at": candidate["captured_at"],
        "payload": candidate["payload"],
        "payload_sha256": _sha256(candidate["payload"]),
        "previous_record_hash": previous_record_hash,
        "provenance": candidate["provenance"],
        "uncertainty": candidate["uncertainty"],
    }
    record["record_hash"] = _sha256(record)
    return record


def trace_envelope_from_record_candidate(
    record: dict[str, Any],
    *,
    source_artifact_id: str,
    source_repository: str,
    observer_runtime_identity: dict[str, Any],
    observer_commit: str,
) -> dict[str, Any]:
    """Publish only a PROPOSED TRACE candidate until the archive owner appends/reseals it."""
    if not observer_runtime_identity or not observer_commit:
        raise ValueError("observer deployment identity is required")
    source_digest = record["payload"]["interop"]["envelope_sha256"]
    return {
        "contract_version": CONTRACT_VERSION,
        "artifact_type": "TRACE",
        "artifact_id": f"trace-candidate:{record['record_id']}:{record['record_hash'][:16]}",
        "created_at": record["captured_at"],
        "producer": {
            "repository": TRACE_REPOSITORY,
            "component": "tools.interop_observer",
            "commit": observer_commit,
            "runtime_identity": observer_runtime_identity,
        },
        "subject": {
            "unit_id": None,
            "target_artifact_id": source_artifact_id,
            "target_identity": {
                "repository": source_repository,
                "artifact_id": source_artifact_id,
                "sha256": source_digest,
                "commit": None,
            },
            "parent_artifact_ids": [source_artifact_id],
        },
        "intended_consumers": [],
        "state": "PROPOSED",
        "evidence_refs": [],
        "authority": {"execution": False, "external_action": False, "promotion": False},
        "authorization_refs": [],
        "payload": {
            "source_type": record["source_type"],
            "source_order_candidate": record["source_order"],
            "source_timestamp": record["source_timestamp"],
            "uncertainty": record["uncertainty"],
            "event": record["payload"]["event"],
            "record_hash_candidate": record["record_hash"],
            "archive_append_required": True,
            "archive_append_completed": False,
            "final_trace_evidence_ref": None,
        },
    }


# Compatibility name retained for callers during the draft migration.
trace_envelope_from_record = trace_envelope_from_record_candidate
