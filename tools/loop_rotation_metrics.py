from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SPAN_START = "SPAN_STARTED"
SPAN_FINISH = "SPAN_FINISHED"
LOOP_STAGE = "LOOP_ITERATION"
MEASUREMENT_EVENTS = {
    "RUN_STARTED", "RUN_STOPPED", "OBSERVATION_BOUNDARY", SPAN_START, SPAN_FINISH,
    "LOOP_REOPENED", "FINDING_OPENED", "FINDING_RESOLVED", "HUMAN_DECISION",
    "ARTIFACT_CHECKPOINT",
}


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _payload(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("payload")
    return value if isinstance(value, dict) else record


def _event_time(record: dict[str, Any], payload: dict[str, Any]) -> datetime | None:
    return _time(payload.get("observed_at")) or _time(record.get("source_timestamp")) or _time(record.get("captured_at"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no} must be a JSON object")
        rows.append(value)
    return rows


def _span_duration(start: tuple[dict[str, Any], dict[str, Any]], finish: tuple[dict[str, Any], dict[str, Any]]) -> tuple[float | None, str | None]:
    sr, sp = start
    fr, fp = finish
    sd, fd = sp.get("clock_domain"), fp.get("clock_domain")
    sm, fm = sp.get("monotonic_ns"), fp.get("monotonic_ns")
    if isinstance(sd, str) and sd and sd == fd and isinstance(sm, int) and isinstance(fm, int):
        return ((fm - sm) / 1_000_000_000, "monotonic") if fm >= sm else (None, "negative_monotonic")
    st, ft = _event_time(sr, sp), _event_time(fr, fp)
    if st is None or ft is None:
        return None, None
    return ((ft - st).total_seconds(), "wall") if ft >= st else (None, "negative_wall")


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "total_seconds": 0.0, "avg_seconds": None, "min_seconds": None, "max_seconds": None}
    total = sum(values)
    return {
        "count": len(values), "total_seconds": round(total, 6),
        "avg_seconds": round(total / len(values), 6),
        "min_seconds": round(min(values), 6), "max_seconds": round(max(values), 6),
    }


def measure(records: Iterable[dict[str, Any]], run_id: str) -> dict[str, Any]:
    material: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen_uids: set[str] = set()
    issues: list[str] = []

    for record in records:
        if not isinstance(record, dict):
            continue
        payload = _payload(record)
        if payload.get("run_id") != run_id or not isinstance(payload.get("event"), str):
            continue
        event, uid = payload["event"], payload.get("event_uid")
        if isinstance(uid, str) and uid:
            if uid in seen_uids:
                issues.append(f"duplicate_event_uid:{uid}")
                continue
            seen_uids.add(uid)
        elif event in MEASUREMENT_EVENTS:
            issues.append(f"missing_event_uid:{record.get('record_id', 'UNKNOWN')}")
        material.append((record, payload))

    starts: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    finishes: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    run_starts: list[tuple[dict[str, Any], dict[str, Any]]] = []
    run_stops: list[tuple[dict[str, Any], dict[str, Any]]] = []
    wall_times: list[datetime] = []
    stage_values: dict[str, list[float]] = defaultdict(list)
    findings_opened = findings_resolved = reopens = human_decisions = reopens_without_cause = 0
    root_causes: set[str] = set()

    for record, payload in material:
        event = payload["event"]
        t = _event_time(record, payload)
        if t is not None:
            wall_times.append(t)
        if event == "RUN_STARTED":
            run_starts.append((record, payload))
        elif event == "RUN_STOPPED":
            run_stops.append((record, payload))
        elif event == "FINDING_OPENED":
            findings_opened += 1
            if not isinstance(payload.get("finding_id"), str) or not payload.get("finding_id"):
                issues.append(f"missing_finding_id:{payload.get('event_uid', 'UNKNOWN')}")
            if isinstance(payload.get("root_cause_id"), str) and payload["root_cause_id"]:
                root_causes.add(payload["root_cause_id"])
        elif event == "FINDING_RESOLVED":
            findings_resolved += 1
            if not isinstance(payload.get("finding_id"), str) or not payload.get("finding_id"):
                issues.append(f"missing_finding_id:{payload.get('event_uid', 'UNKNOWN')}")
        elif event == "LOOP_REOPENED":
            reopens += 1
            causes = payload.get("cause_event_ids")
            if not isinstance(causes, list) or not any(isinstance(v, str) and v for v in causes):
                reopens_without_cause += 1
            if not isinstance(payload.get("workstream_id"), str) or not payload.get("workstream_id"):
                issues.append(f"reopen_missing_workstream:{payload.get('event_uid', 'UNKNOWN')}")
            a, b = payload.get("from_cycle_seq"), payload.get("to_cycle_seq")
            if not isinstance(a, int) or not isinstance(b, int) or b <= a:
                issues.append(f"reopen_invalid_cycle_edge:{payload.get('event_uid', 'UNKNOWN')}")
        elif event == "HUMAN_DECISION":
            human_decisions += 1

        if event in {SPAN_START, SPAN_FINISH}:
            sid = payload.get("span_id")
            if not isinstance(sid, str) or not sid:
                issues.append(f"missing_span_id:{payload.get('event_uid', 'UNKNOWN')}")
                continue
            bucket = starts if event == SPAN_START else finishes
            if sid in bucket:
                issues.append(f"duplicate_span_endpoint:{sid}:{event}")
            else:
                bucket[sid] = (record, payload)

    loops: list[dict[str, Any]] = []
    unmatched = duration_unknown = 0
    for sid in sorted(set(starts) | set(finishes)):
        start, finish = starts.get(sid), finishes.get(sid)
        if start is None or finish is None:
            unmatched += 1
            issues.append(f"unmatched_span:{sid}")
            continue
        sr, sp = start
        fr, fp = finish
        if sp.get("stage") != fp.get("stage") or not isinstance(sp.get("stage"), str):
            issues.append(f"span_stage_mismatch:{sid}")
            continue
        if sp.get("run_id") != fp.get("run_id"):
            issues.append(f"span_run_mismatch:{sid}")
            continue
        if sp.get("workstream_id") != fp.get("workstream_id"):
            issues.append(f"span_workstream_id_mismatch:{sid}")
            continue
        if sp.get("cycle_seq") != fp.get("cycle_seq"):
            issues.append(f"span_cycle_seq_mismatch:{sid}")
            continue
        duration, clock = _span_duration(start, finish)
        if duration is None:
            duration_unknown += 1
            issues.append(f"duration_unknown:{sid}")
        else:
            stage_values[sp["stage"]].append(duration)
        if sp["stage"] == LOOP_STAGE:
            loops.append({
                "span_id": sid, "workstream_id": sp.get("workstream_id"), "cycle_seq": sp.get("cycle_seq"),
                "duration_seconds": duration, "clock": clock,
                "start_time": _event_time(sr, sp), "finish_time": _event_time(fr, fp),
            })

    seen_cycles: set[tuple[str, int]] = set()
    valid_loops: list[dict[str, Any]] = []
    duplicate_cycles = 0
    for span in loops:
        w, seq = span["workstream_id"], span["cycle_seq"]
        if not isinstance(w, str) or not w or not isinstance(seq, int) or seq < 1 or span["duration_seconds"] is None:
            issues.append(f"invalid_cycle_identity:{span['span_id']}")
            continue
        key = (w, seq)
        if key in seen_cycles:
            duplicate_cycles += 1
            issues.append(f"duplicate_cycle_identity:{w}:{seq}")
            continue
        seen_cycles.add(key)
        valid_loops.append(span)

    cycle_gaps = 0
    by_workstream: dict[str, list[int]] = defaultdict(list)
    for span in valid_loops:
        by_workstream[span["workstream_id"]].append(span["cycle_seq"])
    for workstream, seqs in by_workstream.items():
        u = sorted(set(seqs))
        if len(u) > 1:
            missing = sorted(set(range(u[0], u[-1] + 1)) - set(u))
            if missing:
                cycle_gaps += 1
                issues.append(f"cycle_gap:{workstream}:{','.join(map(str, missing))}")

    run_started, run_stopped = len(run_starts) == 1, len(run_stops) == 1
    if len(run_starts) > 1:
        issues.append("multiple_run_started")
    if len(run_stops) > 1:
        issues.append("multiple_run_stopped")
    profile = run_starts[0][1].get("measurement_profile") if run_started else None
    if run_started and (not isinstance(profile, str) or not profile):
        issues.append("missing_measurement_profile")

    wall_elapsed = None
    wall_source = None
    if run_started and run_stopped:
        st, ft = _event_time(*run_starts[0]), _event_time(*run_stops[0])
        if st is not None and ft is not None and ft >= st:
            wall_elapsed, wall_source = (ft - st).total_seconds(), "run_boundaries"
        else:
            issues.append("invalid_run_boundary_time")
    elif len(wall_times) >= 2:
        wall_elapsed, wall_source = (max(wall_times) - min(wall_times)).total_seconds(), "observed_window"

    throughput = len(valid_loops) * 3600 / wall_elapsed if wall_elapsed and wall_elapsed > 0 and valid_loops else None

    points: list[tuple[datetime, int]] = []
    parallel_ok = True
    for span in valid_loops:
        st, ft = span["start_time"], span["finish_time"]
        if st is None or ft is None or ft < st:
            parallel_ok = False
            break
        points.extend([(st, +1), (ft, -1)])
    max_parallel = None
    if parallel_ok and points:
        active = max_parallel = 0
        for _, delta in sorted(points, key=lambda item: (item[0], item[1])):
            active += delta
            max_parallel = max(max_parallel, active)

    if not loops:
        status, coverage = "INSUFFICIENT", "INSUFFICIENT"
    else:
        coverage = "COMPLETE_RUN" if run_started and run_stopped else "OBSERVED_WINDOW"
        critical_prefixes = (
            "missing_event_uid:", "missing_finding_id:", "reopen_missing_workstream:",
            "reopen_invalid_cycle_edge:", "span_workstream_id_mismatch:", "span_cycle_seq_mismatch:",
            "duplicate_event_uid:", "cycle_gap:",
        )
        critical = bool(
            unmatched or duration_unknown or duplicate_cycles or reopens_without_cause
            or any(i.startswith(critical_prefixes) for i in issues)
            or any(i in {"missing_measurement_profile", "multiple_run_started", "multiple_run_stopped", "invalid_run_boundary_time"} for i in issues)
        )
        if throughput is None:
            critical = True
            issues.append("wall_throughput_unmeasurable")
        status = "PARTIAL" if critical or coverage != "COMPLETE_RUN" else "MEASURED"

    stage_summary = {stage: _summary(values) for stage, values in sorted(stage_values.items())}
    material_bytes = sum(len(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()) for r, _ in material)
    count = len(valid_loops)

    return {
        "metric_status": status, "coverage_scope": coverage, "run_id": run_id, "measurement_profile": profile,
        "completed_loop_iterations": count, "wall_elapsed_seconds": round(wall_elapsed, 6) if wall_elapsed is not None else None,
        "wall_elapsed_source": wall_source, "loop_iterations_per_wall_hour": round(throughput, 6) if throughput is not None else None,
        "max_parallel_loop_iterations": max_parallel, "stage_durations": stage_summary, "stage_breakdown_scope": "OBSERVED_SPANS_ONLY",
        "finding_opened": findings_opened, "finding_resolved": findings_resolved,
        "finding_yield_per_iteration": round(findings_opened / count, 6) if count else None,
        "distinct_root_causes": len(root_causes) if root_causes else None,
        "root_cause_yield_per_iteration": round(len(root_causes) / count, 6) if count and root_causes else None,
        "loop_reopened": reopens, "causal_link_status": "PARTIAL" if reopens_without_cause else "MEASURED",
        "human_decisions": human_decisions, "external_wait": stage_summary.get("EXTERNAL_WAIT", _summary([])),
        "material_event_count": len(material), "events_per_completed_iteration": round(len(material) / count, 6) if count else None,
        "observed_json_bytes": material_bytes,
        "quality": {
            "run_started_observed": run_started, "run_stopped_observed": run_stopped, "unmatched_spans": unmatched,
            "duration_unknown": duration_unknown, "duplicate_cycle_identity": duplicate_cycles, "cycle_gap_count": cycle_gaps,
            "reopen_without_cause": reopens_without_cause, "issues": sorted(set(issues)),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure Ultimate Loop rotation from TRACE material-event spans")
    parser.add_argument("--trace-events", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(measure(_load_jsonl(args.trace_events), args.run_id), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
