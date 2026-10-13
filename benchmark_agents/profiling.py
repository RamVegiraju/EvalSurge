"""Post-load MLflow correlation and overlap-aware, content-free profiling."""

import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Literal

from .models import ProfilingSummary, RequestProfile, SpanProfile, TraceSource
from .runner import percentile
from .storage import atomic_json
from .trace_ids import uc_namespace

CATEGORIES = ("model", "tool", "retrieval", "memory", "orchestration", "parallel")
TRACE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
PROFILE_NOTES = [
    "Wall occupancy is not a critical path or a causal bottleneck measurement.",
    "Concurrent leaf spans occupy the parallel bucket; inclusive span times must not be summed.",
    "Client-minus-agent time remains unattributed; clock origins are not aligned.",
    "One closed-loop load level measures throughput, not sustainable capacity.",
    "Boundary-only traces establish request mapping, not internal model/tool bottlenecks.",
]


def category(span: Any) -> str:
    """Map an explicit category or MLflow span type to a stable report bucket."""
    explicit = span.attributes.get("evalsurge.category")
    if explicit in CATEGORIES[:-1]:
        return explicit
    kind = str(span.span_type).upper()
    if kind in {"LLM", "CHAT_MODEL", "EMBEDDING"}:
        return "model"
    if kind == "TOOL":
        return "tool"
    if kind in {"RETRIEVER", "RERANKER"}:
        return "retrieval"
    return "orchestration"


def union_duration(intervals: list[tuple[float, float]]) -> float:
    """Measure the union of half-open intervals without double-counting overlap."""
    total, end = 0.0, float("-inf")
    for start, stop in sorted(intervals):
        total += max(0.0, stop - max(start, end))
        end = max(end, stop)
    return total


def normalize_trace(trace: Any, row: dict[str, Any], max_spans: int = 250) -> RequestProfile:
    """Validate a closed span tree and compute exclusive wall occupancy.

    Args:
        trace: Actual MLflow Trace, already checked against the configured scope.
        row: Captured client attempt, including request and case identifiers.
        max_spans: Hard bound on normalization and returned waterfall complexity.

    Returns:
        A profile without prompts, tool arguments, retrieved text, or span attributes.

    Raises:
        ValueError: The trace is incomplete, cyclic, oversized, or has invalid timing.
    """
    spans = trace.data.spans
    if not spans or len(spans) > max_spans:
        raise ValueError("Trace span count outside profiling bounds")
    indexed = {span.span_id: span for span in spans}
    roots = [span for span in spans if span.parent_id is None]
    if len(indexed) != len(spans) or len(roots) != 1:
        raise ValueError("Trace must have unique spans and one root")
    origin, stop = roots[0].start_time_ns, roots[0].end_time_ns
    if not isinstance(origin, int) or not isinstance(stop, int) or stop < origin:
        raise ValueError("Trace has no complete root interval")
    children: dict[str, list[Any]] = defaultdict(list)
    depths: dict[str, int] = {}
    for span in spans:
        if (
            not isinstance(span.start_time_ns, int)
            or not isinstance(span.end_time_ns, int)
            or not origin <= span.start_time_ns <= span.end_time_ns <= stop
        ):
            raise ValueError("Span is incomplete or outside the root interval")
        visited = {span.span_id}
        ancestor = span
        while ancestor.parent_id is not None:
            if ancestor.parent_id in visited or ancestor.parent_id not in indexed:
                raise ValueError("Trace has invalid ancestry")
            parent = indexed[ancestor.parent_id]
            if not (
                parent.start_time_ns <= ancestor.start_time_ns
                and ancestor.end_time_ns <= parent.end_time_ns
            ):
                raise ValueError("Child extends beyond its parent")
            visited.add(parent.span_id)
            ancestor = parent
        depths[span.span_id] = len(visited) - 1
        if span.parent_id:
            children[span.parent_id].append(span)
    normalized = []
    for span in sorted(spans, key=lambda item: (item.start_time_ns, depths[item.span_id])):
        duration = (span.end_time_ns - span.start_time_ns) / 1e6
        child_time = union_duration(
            [
                ((child.start_time_ns - origin) / 1e6, (child.end_time_ns - origin) / 1e6)
                for child in children[span.span_id]
            ]
        )
        normalized.append(
            SpanProfile(
                span_id=span.span_id,
                parent_id=span.parent_id,
                name=str(span.name)[:200],
                category=category(span),
                start_ms=(span.start_time_ns - origin) / 1e6,
                duration_ms=duration,
                self_ms=max(0.0, duration - child_time),
                depth=depths[span.span_id],
                status=str(span.status.status_code),
            )
        )
    boundaries = sorted(
        {
            point
            for span in normalized
            for point in (span.start_ms, span.start_ms + span.duration_ms)
        }
    )
    occupancy = dict.fromkeys(CATEGORIES, 0.0)
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        active = [
            span for span in normalized if span.start_ms <= start < span.start_ms + span.duration_ms
        ]
        active_parents = {span.parent_id for span in active}
        leaves = [span for span in active if span.span_id not in active_parents]
        bucket = leaves[0].category if len(leaves) == 1 else "parallel"
        occupancy[bucket] += end - start
    duration = (stop - origin) / 1e6
    latency = row.get("latency_ms")
    return RequestProfile(
        request_id=row["request_id"],
        case_id=row.get("case_id", 0),
        success=row["success"],
        latency_ms=latency,
        trace_id=trace.info.trace_id,
        status="available",
        agent_duration_ms=duration,
        client_minus_agent_ms=max(0.0, latency - duration) if latency is not None else None,
        occupancy_ms=occupancy,
        spans=normalized,
    )


def summarize_profiles(profiles: list[RequestProfile]) -> ProfilingSummary:
    """Aggregate coverage and inclusive per-name percentiles across observed traces."""
    timings: dict[tuple[str, str], list[float]] = defaultdict(list)
    for profile in profiles:
        for span in profile.spans:
            if span.category != "orchestration":
                timings[(span.name, span.category)].append(span.duration_ms)
    hotspots = [
        {
            "name": name,
            "category": kind,
            "observations": len(values),
            "p50_ms": percentile(values, 0.5),
            "p95_ms": percentile(values, 0.95),
        }
        for (name, kind), values in timings.items()
    ]
    traced = sum(profile.status == "available" for profile in profiles)
    return ProfilingSummary(
        total_requests=len(profiles),
        traced_requests=traced,
        coverage=traced / len(profiles) if profiles else 0,
        gaps=dict(Counter(profile.status for profile in profiles if profile.status != "available")),
        hotspots=sorted(hotspots, key=lambda item: item["p95_ms"], reverse=True)[:10],
        notes=PROFILE_NOTES,
    )


def _scope_status(
    trace: Any, trace_id: str, run_id: str, request_id: str, source: TraceSource
) -> Literal["available", "missing", "scope_mismatch"]:
    """Separate absent export metadata from conflicting authorization evidence.

    Args:
        trace: Actual fetched native MLflow trace; no content is normalized yet.
        trace_id: Exact target-returned identifier used for this fetch.
        run_id: Admitted benchmark identifier, never inferred from the trace.
        request_id: Exact captured attempt identifier.
        source: Frozen operator-owned experiment allowlist.

    Returns:
        ``available`` only for exact scope/correlation; ``missing`` for absent
        run/request keys in an already matching experiment/trace; otherwise
        ``scope_mismatch``. Even one conflicting present key fails immediately.

    Raises:
        AttributeError, TypeError: Malformed native metadata. The caller records
            an invalid profile rather than accepting or retrying that trace.

    Limitations:
        Missing metadata is not authorization. It only permits bounded rereads
        of the same identifier outside measured load; no search or scope change.
    """
    location = trace.info.trace_location.mlflow_experiment
    if (
        location is None
        or location.experiment_id not in source.experiment_ids
        or trace.info.trace_id != trace_id
    ):
        return "scope_mismatch"
    metadata = trace.info.trace_metadata
    if not isinstance(metadata, dict):
        raise TypeError("Invalid native trace metadata")
    expected = {"evalsurge.run_id": run_id, "evalsurge.request_id": request_id}
    if any(key in metadata and metadata[key] != value for key, value in expected.items()):
        return "scope_mismatch"
    if any(key not in metadata for key in expected):
        return "missing"
    return "available"


def collect_profiles(
    rows: list[dict[str, Any]],
    run_id: str,
    source: TraceSource | None,
    directory: Path,
    client: Any = None,
) -> tuple[ProfilingSummary, dict[str, Any]]:
    """Fetch correlated traces after load and persist content-free report artifacts.

    Missing exports/correlation keys receive at most four fetch attempts with bounded backoff.
    Incrementally visible spans alone are not evidence readiness. Conflicting
    trace/experiment/run/request values fail closed without retries. The collector stops
    starting fetches after 60 seconds or max_traces attempts. Only the configured
    experiment scope and exact run/request metadata are accepted. The operator
    must configure MLflow transport timeouts separately for remote trace stores.
    Actual Trace objects are returned in-memory only for trace-aware evaluation.
    """
    if source and client is None:
        import mlflow
        from mlflow.tracking import MlflowClient

        mlflow.flush_trace_async_logging()
        client = MlflowClient(tracking_uri=source.tracking_uri)
    profiles, traces = [], {}
    fetched, deadline = 0, time.monotonic() + 60
    for row in rows:
        profile = RequestProfile(
            request_id=row["request_id"],
            case_id=row.get("case_id", 0),
            success=row["success"],
            latency_ms=row.get("latency_ms"),
            trace_id=row.get("trace_id"),
            status="disabled" if source is None else "missing",
        )
        trace_id = row.get("trace_id")
        if source and trace_id:
            if fetched >= source.max_traces or time.monotonic() >= deadline:
                profile.status = "budget"
            elif uc_namespace(trace_id) is not None:
                # Native UC locations can be shared by experiments. Never mistake
                # location equality or caller metadata for authorized membership.
                profile.status = "unsupported_scope"
            elif not isinstance(trace_id, str) or not TRACE_ID.fullmatch(trace_id):
                profile.status = "invalid"
            else:
                fetched += 1
                for attempt in range(4):
                    if attempt and time.monotonic() >= deadline:
                        break
                    try:
                        trace = client.get_trace(trace_id, display=False)
                    except Exception:  # noqa: BLE001
                        trace = None
                    if trace is not None:
                        try:
                            profile.status = _scope_status(
                                trace, trace_id, run_id, row["request_id"], source
                            )
                        except (TypeError, AttributeError):
                            profile.status = "invalid"
                            break
                        if profile.status == "scope_mismatch":
                            break
                        if profile.status == "available":
                            try:
                                profile = normalize_trace(trace, row, source.max_spans)
                            except (ValueError, TypeError, AttributeError):
                                profile.status = "invalid"
                            else:
                                traces[row["request_id"]] = trace
                            break
                    if time.monotonic() >= deadline:
                        break
                    if attempt < 3:
                        time.sleep(
                            min((0.5, 2.0, 4.0)[attempt], max(0.0, deadline - time.monotonic()))
                        )
        profiles.append(profile)
        atomic_json(directory / "profiles" / f"{row['request_id']}.json", profile.model_dump())
    summary = summarize_profiles(profiles)
    atomic_json(directory / "profiling.json", summary.model_dump())
    atomic_json(directory / "profile-order.json", [profile.request_id for profile in profiles])
    return summary, traces
