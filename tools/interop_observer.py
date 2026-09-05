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
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        payload = envelope.get("payload") or {}
        if payload.get("decision") in {"APPROVE", "REJECT"} and payload.get("approved_by"):
            return "HUMAN_DECISION"
        return "APPROVAL_ARTIFACT_OBSERVED"

    if artifact_type == "PROMOTION_DECISION":
        return "PROMOTION_DECISION_OBSERVED"

    return _ARTIFACT_EVENTS[artifact_type]


def _validate_envelope(envelope: dict[str, Any]) -> None:
    if envelope.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("unsupported interop contract version")

    artifact_type = envelope.get("artifact_type")
    allowed = {
        "UNIT",
        "RESULT",
        "EVIDENCE",
        "GATE_RESULT",
        "RETRY_REQUEST",
        "APPROVAL",
        "TRACE",
        "LEARNING_CANDIDATE",
        "PROMOTION_DECISION",
        "FREEZE_RECORD",
    }
    if artifact_type not in allowed:
        raise ValueError("unsupported interop artifact type")

    if not envelope.get("artifact_id"):
        raise ValueError("artifact_id is required")
    if not envelope.get("created_at"):
        raise ValueError("created_at is required")

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

    if artifact_type == "APPROVAL":
        subject = envelope.get("subject") or {}
        if not subject.get("target_artifact_id") and not subject.get("target_identity"):
            raise ValueError("APPROVAL requires an exact target binding")


def observe_interop_envelope(
    envelope: dict[str, Any],
    *,
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Convert one interop artifact into a passive TRACE source-record candidate.

    The returned value intentionally has no record_id, source_order,
    previous_record_hash, or record_hash. Those belong to the archive append/seal
    boundary and must be assigned by the run that owns the chain.
    """
    _validate_envelope(envelope)

    artifact_type = str(envelope["artifact_type"])
    producer = dict(envelope.get("producer") or {})
    subject = dict(envelope.get("subject") or {})
    payload = dict(envelope.get("payload") or {})
    envelope_hash = _sha256(envelope)
    payload_hash = _sha256(payload)

    actor = None
    if artifact_type == "APPROVAL":
        actor = payload.get("approved_by")

    observation_payload = {
        "event": _event_for(envelope),
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
            "evidence_refs": list(envelope.get("evidence_refs") or []),
            "intended_consumers": list(envelope.get("intended_consumers") or []),
            "payload_sha256": payload_hash,
            "envelope_sha256": envelope_hash,
        },
    }

    # Preserve only a bounded semantic snapshot in TRACE by default. The raw
    # envelope remains the source artifact at the producer/transport boundary.
    if artifact_type == "APPROVAL":
        observation_payload["decision"] = payload.get("decision")
        observation_payload["approved_by"] = payload.get("approved_by")
        observation_payload["reason"] = payload.get("reason")
    elif artifact_type == "RESULT":
        observation_payload["result_status"] = payload.get("status")
    elif artifact_type == "RETRY_REQUEST":
        observation_payload["retry_reason"] = payload.get("reason")

    return {
        "source_type": "rts_interop_artifact",
        "actor": actor,
        "source_timestamp": envelope["created_at"],
        "captured_at": captured_at or _now_iso(),
        "payload": observation_payload,
        "provenance": f"{CONTRACT_VERSION}:{producer['repository']}:{envelope['artifact_id']}",
        # SUPPORTED means TRACE observed this artifact, not that its claims are true.
        "uncertainty": "SUPPORTED",
    }


def seal_source_record_candidate(
    candidate: dict[str, Any],
    *,
    record_id: str,
    source_order: int,
    previous_record_hash: str | None,
) -> dict[str, Any]:
    """Assign TRACE chain fields deterministically without writing an archive."""
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


def trace_envelope_from_record(
    record: dict[str, Any],
    *,
    source_artifact_id: str,
    source_repository: str,
) -> dict[str, Any]:
    """Represent one sealed source-record candidate as the cross-repo TRACE artifact."""
    return {
        "contract_version": CONTRACT_VERSION,
        "artifact_type": "TRACE",
        "artifact_id": f"trace:{record['record_id']}:{record['record_hash'][:16]}",
        "created_at": record["captured_at"],
        "producer": {
            "repository": TRACE_REPOSITORY,
            "component": "tools.interop_observer",
            "commit": None,
            "runtime_identity": None,
        },
        "subject": {
            "unit_id": None,
            "target_artifact_id": source_artifact_id,
            "target_identity": {
                "source_repository": source_repository,
                "trace_record_hash": record["record_hash"],
            },
            "parent_artifact_ids": [source_artifact_id],
        },
        "intended_consumers": [],
        "state": "FINAL",
        "evidence_refs": [
            {
                "kind": "trace_record_hash",
                "ref": f"sha256:{record['record_hash']}",
            }
        ],
        "authority": {
            "execution": False,
            "external_action": False,
            "promotion": False,
        },
        "payload": {
            "source_type": record["source_type"],
            "source_order": record["source_order"],
            "source_timestamp": record["source_timestamp"],
            "uncertainty": record["uncertainty"],
            "event": record["payload"]["event"],
            "archive_append_required": True,
            "archive_append_completed": False,
        },
    }
