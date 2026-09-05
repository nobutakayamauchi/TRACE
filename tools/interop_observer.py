from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable

CONTRACT_VERSION = "rts-interop/v1"
TRACE_REPOSITORY = "nobutakayamauchi/TRACE"
_ARTIFACT_EVENTS = {"UNIT": "WORK_UNIT_OBSERVED", "RESULT": "RESULT_OBSERVED", "EVIDENCE": "EVIDENCE_OBSERVED",
                    "RETRY_REQUEST": "RETRY_REQUEST_OBSERVED", "TRACE": "TRACE_ARTIFACT_OBSERVED",
                    "LEARNING_CANDIDATE": "LEARNING_CANDIDATE_OBSERVED", "FREEZE_RECORD": "FREEZE_RECORD_OBSERVED"}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _snapshot(value: Any) -> Any:
    return json.loads(_canonical_json(value).decode("utf-8"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _asserted_approval_actor(envelope: dict[str, Any]) -> str | None:
    payload = envelope.get("payload") or {}
    actor = payload.get("approved_by_asserted") or payload.get("approved_by")
    return actor if isinstance(actor, str) and actor else None


def _human_actor_evidence(envelope: dict[str, Any], *, verifier: Callable[[dict[str, Any], str, str], bool] | None) -> str | None:
    if verifier is None:
        return None
    actor = _asserted_approval_actor(envelope)
    if not actor:
        return None
    envelope_digest = _sha256(envelope)
    for ref in envelope.get("evidence_refs") or []:
        if not isinstance(ref, dict) or ref.get("kind") != "human_identity_evidence":
            continue
        try:
            if verifier(_snapshot(ref), actor, envelope_digest) is True:
                return actor
        except Exception:
            continue
    return None


def _event_for(envelope: dict[str, Any], *, human_actor: str | None) -> str:
    t = envelope["artifact_type"]
    if t == "GATE_RESULT":
        return "GATE_PASSED" if envelope.get("verdict") == "PASS" else "GATE_FAILED" if envelope.get("verdict") == "FAIL" else "GATE_RESULT_OBSERVED"
    if t == "APPROVAL":
        return "HUMAN_DECISION" if human_actor else "APPROVAL_ARTIFACT_OBSERVED"
    if t == "PROMOTION_DECISION":
        return "PROMOTION_DECISION_OBSERVED"
    return _ARTIFACT_EVENTS[t]


def _validate_envelope(envelope: dict[str, Any]) -> None:
    if envelope.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("unsupported interop contract version")
    allowed = set(_ARTIFACT_EVENTS) | {"GATE_RESULT", "APPROVAL", "PROMOTION_DECISION"}
    if envelope.get("artifact_type") not in allowed:
        raise ValueError("unsupported interop artifact type")
    if not envelope.get("artifact_id") or not envelope.get("created_at"):
        raise ValueError("artifact_id and created_at are required")
    if not (envelope.get("producer") or {}).get("repository"):
        raise ValueError("producer.repository is required")
    authority = envelope.get("authority")
    if not isinstance(authority, dict) or any(not isinstance(authority.get(k), bool) for k in ("execution", "external_action", "promotion")):
        raise ValueError("explicit boolean authority vector is required")
    if envelope["artifact_type"] == "GATE_RESULT" and not envelope.get("verdict"):
        raise ValueError("GATE_RESULT verdict is required")
    if envelope["artifact_type"] == "PROMOTION_DECISION" and not envelope.get("disposition"):
        raise ValueError("PROMOTION_DECISION disposition is required")
    if envelope["artifact_type"] in {"APPROVAL", "PROMOTION_DECISION"} and not ((envelope.get("subject") or {}).get("target_identity") or {}).get("sha256"):
        raise ValueError("decision artifact requires immutable target_identity")


def _verified_payload_reference(envelope: dict[str, Any], *, payload_sha256: str,
                                resolver: Callable[[dict[str, Any]], Any | None] | None) -> dict[str, Any] | None:
    if resolver is None:
        return None
    immutable_ref = f"sha256:{payload_sha256}"
    for ref in envelope.get("evidence_refs") or []:
        if not isinstance(ref, dict):
            continue
        if ref.get("kind") != "content_addressed_artifact" or ref.get("ref") != immutable_ref or ref.get("digest") != payload_sha256:
            continue
        try:
            resolved = resolver(_snapshot(ref))
        except Exception:
            continue
        if resolved is not None and _sha256(resolved) == payload_sha256:
            return _snapshot(ref)
    return None


def observe_interop_envelope(envelope: dict[str, Any], *, observer_runtime_identity: dict[str, Any], observer_commit: str,
                             payload_ref_resolver: Callable[[dict[str, Any]], Any | None] | None = None,
                             human_identity_verifier: Callable[[dict[str, Any], str, str], bool] | None = None,
                             captured_at: str | None = None) -> dict[str, Any]:
    _validate_envelope(envelope)
    if not isinstance(observer_runtime_identity, dict) or not observer_runtime_identity or not observer_commit:
        raise ValueError("observer deployment identity is required")
    artifact_type = str(envelope["artifact_type"])
    producer = _snapshot(envelope.get("producer") or {})
    subject = _snapshot(envelope.get("subject") or {})
    payload = _snapshot(envelope.get("payload") or {})
    payload_sha = _sha256(payload)
    durable_ref = _verified_payload_reference(envelope, payload_sha256=payload_sha, resolver=payload_ref_resolver)
    human_actor = _human_actor_evidence(envelope, verifier=human_identity_verifier) if artifact_type == "APPROVAL" else None
    reconstructable = durable_ref is not None
    observation_payload = {
        "event": _event_for(envelope, human_actor=human_actor),
        "observer_identity": {"repository": TRACE_REPOSITORY, "commit": observer_commit, "runtime_identity": _snapshot(observer_runtime_identity)},
        "interop": {"contract_version": CONTRACT_VERSION, "artifact_type": artifact_type, "artifact_id": envelope["artifact_id"],
                    "artifact_state": envelope.get("state"), "producer": producer, "subject": subject,
                    "verdict": envelope.get("verdict"), "disposition": envelope.get("disposition"),
                    "authority": _snapshot(envelope["authority"]), "authorization_refs": _snapshot(envelope.get("authorization_refs") or []),
                    "evidence_refs": _snapshot(envelope.get("evidence_refs") or []), "intended_consumers": _snapshot(envelope.get("intended_consumers") or []),
                    "payload_sha256": payload_sha, "envelope_sha256": _sha256(envelope), "durable_payload_ref": durable_ref,
                    "reconstruction_gap": not reconstructable},
    }
    if artifact_type == "APPROVAL":
        observation_payload.update({"decision": payload.get("decision"), "approved_by_asserted": _asserted_approval_actor(envelope),
                                    "human_actor_established": human_actor is not None})
    elif artifact_type == "RESULT":
        observation_payload["result_status"] = payload.get("status")
    elif artifact_type == "RETRY_REQUEST":
        observation_payload["retry_reason"] = payload.get("reason")
    return {"source_type": "rts_interop_artifact", "actor": human_actor, "source_timestamp": envelope["created_at"],
            "captured_at": captured_at or _now_iso(), "payload": observation_payload,
            "provenance": f"{CONTRACT_VERSION}:{producer['repository']}:{envelope['artifact_id']}",
            "uncertainty": "SUPPORTED" if reconstructable else "UNKNOWN"}


def seal_source_record_candidate(candidate: dict[str, Any], *, record_id: str, source_order: int,
                                 previous_record_hash: str | None) -> dict[str, Any]:
    if not record_id or source_order < 1:
        raise ValueError("valid record_id and source_order >= 1 are required")
    payload = _snapshot(candidate["payload"])
    record = {"record_id": record_id, "source_type": candidate["source_type"], "actor": candidate.get("actor"),
              "source_order": source_order, "source_timestamp": candidate.get("source_timestamp"), "captured_at": candidate["captured_at"],
              "payload": payload, "payload_sha256": _sha256(payload), "previous_record_hash": previous_record_hash,
              "provenance": candidate["provenance"], "uncertainty": candidate["uncertainty"]}
    record["record_hash"] = _sha256(record)
    return record


def _verify_sealed_candidate_record(record: dict[str, Any]) -> None:
    stored = str(record.get("record_hash") or "")
    material = {k: v for k, v in record.items() if k != "record_hash"}
    if not stored or _sha256(material) != stored or _sha256(record.get("payload")) != record.get("payload_sha256"):
        raise PermissionError("sealed TRACE candidate record integrity mismatch")


def trace_envelope_from_record_candidate(record: dict[str, Any], *, source_artifact_id: str, source_repository: str,
                                         observer_runtime_identity: dict[str, Any], observer_commit: str) -> dict[str, Any]:
    if not isinstance(observer_runtime_identity, dict) or not observer_runtime_identity or not observer_commit:
        raise ValueError("observer deployment identity is required")
    _verify_sealed_candidate_record(record)
    record_observer = record["payload"].get("observer_identity") or {}
    if record_observer.get("repository") != TRACE_REPOSITORY or record_observer.get("commit") != observer_commit or record_observer.get("runtime_identity") != _snapshot(observer_runtime_identity):
        raise PermissionError("TRACE derivation identity does not match sealed observer identity")
    interop = record["payload"]["interop"]
    if source_artifact_id != interop["artifact_id"] or source_repository != interop["producer"]["repository"]:
        raise ValueError("TRACE source arguments do not match hashed observed artifact")
    digest = interop["envelope_sha256"]
    return {"contract_version": CONTRACT_VERSION, "artifact_type": "TRACE",
            "artifact_id": f"trace-candidate:{record['record_id']}:{record['record_hash'][:16]}", "created_at": record["captured_at"],
            "producer": {"repository": TRACE_REPOSITORY, "component": "tools.interop_observer", "commit": observer_commit,
                         "runtime_identity": _snapshot(observer_runtime_identity)},
            "subject": {"unit_id": None, "target_artifact_id": interop["artifact_id"],
                        "target_identity": {"repository": interop["producer"]["repository"], "artifact_id": interop["artifact_id"],
                                            "sha256": digest, "commit": None}, "parent_artifact_ids": [interop["artifact_id"]]},
            "intended_consumers": [], "state": "PROPOSED", "evidence_refs": [],
            "authority": {"execution": False, "external_action": False, "promotion": False}, "authorization_refs": [],
            "payload": {"source_type": record["source_type"], "source_order_candidate": record["source_order"],
                        "source_timestamp": record["source_timestamp"], "uncertainty": record["uncertainty"],
                        "event": record["payload"]["event"], "record_hash_candidate": record["record_hash"],
                        "archive_append_required": True, "archive_append_completed": False, "final_trace_evidence_ref": None}}


trace_envelope_from_record = trace_envelope_from_record_candidate
