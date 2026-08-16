from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class PRKey:
    repository: str
    pr: int


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_no}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"record at {path}:{line_no} must be an object")
        rows.append(row)
    return rows


def _key(payload: dict[str, Any]) -> PRKey | None:
    repository = payload.get("repository")
    pr = payload.get("pr")
    if isinstance(repository, str) and repository and isinstance(pr, int) and pr > 0:
        return PRKey(repository, pr)
    return None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _trace_observed_at(record: dict[str, Any]) -> datetime | None:
    payload = record.get("payload") or {}
    if isinstance(payload, dict):
        explicit = _parse_time(payload.get("observed_at"))
        if explicit is not None:
            return explicit
    return _parse_time(record.get("source_timestamp")) or _parse_time(record.get("captured_at"))


def _trace_state(record: dict[str, Any]) -> str | None:
    payload = record.get("payload") or {}
    if not isinstance(payload, dict):
        return None
    event = payload.get("event")
    if event in {"PR_MERGED", "MERGE_RECORDED"}:
        return "MERGED"
    if event == "PR_STATE_OBSERVED":
        merged = payload.get("merged")
        state = payload.get("state")
        if merged is True:
            return "MERGED"
        if state == "open" and merged is False:
            return "OPEN"
        if state == "closed" and merged is False:
            return "CLOSED_UNMERGED"
    if event == "PR_CREATED":
        return "CREATED"
    return None


def _snapshot_state(snapshot: dict[str, Any]) -> str:
    merged = snapshot.get("merged")
    state = snapshot.get("state")
    if merged is True:
        return "MERGED"
    if state == "open" and merged is False:
        return "OPEN"
    if state == "closed" and merged is False:
        return "CLOSED_UNMERGED"
    return "UNKNOWN"


def _ordering(snapshot_time: datetime | None, trace_time: datetime | None) -> str:
    if snapshot_time is None or trace_time is None:
        return "UNKNOWN"
    if snapshot_time > trace_time:
        return "SNAPSHOT_NEWER"
    if snapshot_time == trace_time:
        return "SAME_TIME"
    return "SNAPSHOT_OLDER"


def _claim_ordering(claim: dict[str, Any], snapshot: dict[str, Any], github_snapshot: dict[str, Any]) -> str:
    claim_time = _parse_time(claim.get("claimed_at"))
    snapshot_time = _parse_time(snapshot.get("observed_at") or github_snapshot.get("observed_at"))
    if claim_time is not None and snapshot_time is not None:
        if snapshot_time > claim_time:
            return "SNAPSHOT_NEWER"
        if snapshot_time == claim_time:
            return "SAME_TIME"
        return "SNAPSHOT_OLDER"
    claim_order = claim.get("capture_order")
    snapshot_order = snapshot.get("capture_order", github_snapshot.get("capture_order"))
    if isinstance(claim_order, int) and isinstance(snapshot_order, int):
        if snapshot_order > claim_order:
            return "SNAPSHOT_NEWER"
        if snapshot_order == claim_order:
            return "SAME_TIME"
        return "SNAPSHOT_OLDER"
    return "UNKNOWN"


def reconcile(
    trace_records: Iterable[dict[str, Any]],
    github_snapshot: dict[str, Any],
    claims: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    latest_trace: dict[PRKey, tuple[datetime | None, int, str, str]] = {}
    for record in trace_records:
        payload = record.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        key = _key(payload)
        state = _trace_state(record)
        if key is None or state is None:
            continue
        order = record.get("source_order")
        if not isinstance(order, int):
            order = -1
        rid = record.get("record_id")
        rid = rid if isinstance(rid, str) else "UNKNOWN"
        observed_at = _trace_observed_at(record)
        previous = latest_trace.get(key)
        if previous is None:
            latest_trace[key] = (observed_at, order, state, rid)
        else:
            previous_time, previous_order, _, _ = previous
            newer = False
            if observed_at is not None and previous_time is not None:
                newer = observed_at > previous_time or (observed_at == previous_time and order > previous_order)
            elif observed_at is not None and previous_time is None:
                newer = True
            elif observed_at is None and previous_time is None:
                newer = order > previous_order
            if newer:
                latest_trace[key] = (observed_at, order, state, rid)

    findings: list[dict[str, Any]] = []
    snapshots = github_snapshot.get("prs", [])
    if not isinstance(snapshots, list):
        raise ValueError("github snapshot must contain a prs list")

    snapshot_by_key: dict[PRKey, dict[str, Any]] = {}
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        key = _key(snapshot)
        if key is None:
            continue
        snapshot_by_key[key] = snapshot
        github_state = _snapshot_state(snapshot)
        trace = latest_trace.get(key)
        if trace is None:
            findings.append({
                "type": "TRACE_COVERAGE_GAP",
                "repository": key.repository,
                "pr": key.pr,
                "github_state": github_state,
                "message": "GitHub PR is in the evaluation snapshot but TRACE has no PR lifecycle record for it.",
            })
            continue
        trace_time, _, trace_state, record_id = trace
        snapshot_time = _parse_time(snapshot.get("observed_at") or github_snapshot.get("observed_at"))
        ordering = _ordering(snapshot_time, trace_time)
        if ordering == "UNKNOWN" and github_state != trace_state:
            findings.append({
                "type": "STATE_FRESHNESS_UNKNOWN",
                "repository": key.repository,
                "pr": key.pr,
                "trace_state": trace_state,
                "github_state": github_state,
                "trace_record_id": record_id,
                "message": "State differs but observation freshness cannot be ordered; preserve UNKNOWN instead of declaring conflict.",
            })
            continue
        snapshot_can_supersede = ordering in {"SNAPSHOT_NEWER", "SAME_TIME"}
        if snapshot_can_supersede and github_state == "MERGED" and trace_state != "MERGED":
            findings.append({
                "type": "MISSING_MERGE_TRANSITION",
                "repository": key.repository,
                "pr": key.pr,
                "trace_state": trace_state,
                "github_state": github_state,
                "trace_record_id": record_id,
                "message": "GitHub now records the PR as merged, but TRACE has not captured a merge transition.",
            })
        elif snapshot_can_supersede and github_state in {"OPEN", "CLOSED_UNMERGED"} and trace_state == "MERGED":
            findings.append({
                "type": "SOURCE_CONFLICT",
                "repository": key.repository,
                "pr": key.pr,
                "trace_state": trace_state,
                "github_state": github_state,
                "trace_record_id": record_id,
                "message": "TRACE merge evidence conflicts with the supplied GitHub point-in-time snapshot.",
            })

    for claim in claims:
        if not isinstance(claim, dict):
            continue
        key = _key(claim)
        if key is None:
            continue
        snapshot = snapshot_by_key.get(key)
        if snapshot is None:
            findings.append({
                "type": "CLAIM_UNCHECKED",
                "repository": key.repository,
                "pr": key.pr,
                "claim": claim.get("claim"),
                "message": "No GitHub snapshot was supplied for this lifecycle claim.",
            })
            continue
        claim_value = claim.get("claim")
        target_branch = claim.get("target_branch")
        github_state = _snapshot_state(snapshot)
        if claim_value == "MERGED_TO_TARGET":
            claim_ordering = _claim_ordering(claim, snapshot, github_snapshot)
            if claim_ordering == "SNAPSHOT_OLDER":
                findings.append({
                    "type": "CLAIM_UNCHECKED",
                    "repository": key.repository,
                    "pr": key.pr,
                    "claim": claim_value,
                    "source_ref": claim.get("source_ref"),
                    "message": "GitHub snapshot predates the lifecycle claim and cannot refute it.",
                })
                continue
            if claim_ordering == "UNKNOWN":
                findings.append({
                    "type": "CLAIM_UNCHECKED",
                    "repository": key.repository,
                    "pr": key.pr,
                    "claim": claim_value,
                    "source_ref": claim.get("source_ref"),
                    "message": "Claim and GitHub snapshot cannot be ordered in time; preserve UNKNOWN.",
                })
                continue
            if github_state == "UNKNOWN":
                findings.append({
                    "type": "CLAIM_UNCHECKED",
                    "repository": key.repository,
                    "pr": key.pr,
                    "claim": claim_value,
                    "source_ref": claim.get("source_ref"),
                    "message": "GitHub snapshot does not establish a merge state; preserve UNKNOWN.",
                })
                continue
            supported = github_state == "MERGED" and (
                target_branch is None or snapshot.get("base") == target_branch
            )
            if not supported:
                findings.append({
                    "type": "CLAIM_CONFLICT",
                    "repository": key.repository,
                    "pr": key.pr,
                    "claim": claim_value,
                    "target_branch": target_branch,
                    "github_state": github_state,
                    "github_base": snapshot.get("base"),
                    "source_ref": claim.get("source_ref"),
                    "message": "Lifecycle claim is not supported by the GitHub point-in-time snapshot.",
                })

    return {
        "status": "PASS" if not findings else "FINDINGS",
        "rule": "IMPLEMENTATION_COMPLETE != PR_MERGED != TARGET_BRANCH_INTEGRATED != DEPLOYED",
        "finding_count": len(findings),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare TRACE PR lifecycle evidence with a point-in-time GitHub snapshot")
    parser.add_argument("--trace-events", type=Path, required=True)
    parser.add_argument("--github-snapshot", type=Path, required=True)
    parser.add_argument("--claims", type=Path)
    args = parser.parse_args()

    trace_records = _load_jsonl(args.trace_events)
    snapshot = _load_json(args.github_snapshot)
    claims: list[dict[str, Any]] = []
    if args.claims:
        loaded = _load_json(args.claims)
        if not isinstance(loaded, list):
            raise ValueError("claims file must contain a JSON list")
        claims = loaded

    print(json.dumps(reconcile(trace_records, snapshot, claims), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
