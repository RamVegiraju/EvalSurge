"""Shared protocol payloads and descriptive benchmark metrics."""

import math
from collections import Counter
from typing import Any

from .adapters import get_adapter
from .models import RunRequest, Sample


def payload(request: RunRequest, sample: Sample) -> dict[str, Any]:
    """Convert one workload case into a fixed hosted-agent wire contract.

    Args:
        request: Target adapter and model settings for this run.
        sample: Nonempty raw inputs for http-json; query or messages for SSE.

    Returns:
        The raw inputs object for http-json, or a streaming OpenAI Chat Completions
        or MLflow agent-server envelope. Extra SSE input keys remain evaluation
        metadata. No reasoning, tool, or sampling settings are injected. Streamed
        usage is requested only when target.request_usage is enabled for openai-chat.

    Raises:
        ValueError: JSON inputs are empty, or SSE inputs lack a query or valid messages.
            This validates the supported envelope, not all provider fields.
    """
    return get_adapter(request.target.adapter).encode(request.target, sample)


def percentile(values: list[float], quantile: float) -> float | None:
    """Compute a nearest-rank percentile without mutating the supplied values.

    Args:
        values: Observations to sort; an empty collection is allowed.
        quantile: Requested fraction in (0, 1], as used by the metric summaries.

    Returns:
        The nearest-rank observation, or None when no observations are available.
    """
    return sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)] if values else None


def summarize(
    rows: list[dict[str, Any]], elapsed: float, dispatch_seconds: float
) -> dict[str, Any]:
    """Aggregate client measurements without applying quality thresholds.

    Args:
        rows: Completed or recovered attempts with success, error, timing, and
            output_tokens fields.
        elapsed: Positive measured wall time in seconds, including request drain.
        dispatch_seconds: Offset of the last HTTP dispatch from the measured start.

    Returns:
        Attempt and success counts, error breakdown, rates, token-usage coverage,
        and successful-only latency percentiles. WorkerInterrupted attempts do not
        count toward completed TPS; other failed attempts do.
    """
    successful = [r for r in rows if r["success"]]
    timing = {}
    for field in ("latency_ms", "ttft_ms", "first_event_ms"):
        values = [r[field] for r in successful if r[field] is not None]
        timing[field] = {
            "count": len(values),
            **{f"p{int(q * 100)}": percentile(values, q) for q in (0.5, 0.95, 0.99)},
        }
    tokens = [r["output_tokens"] for r in successful if r["output_tokens"] is not None]
    return {
        "requests": len(rows),
        "successful_requests": len(successful),
        "error_rate": 1 - len(successful) / len(rows) if rows else None,
        "completed_tps": sum(r.get("error") != "WorkerInterrupted" for r in rows) / elapsed,
        "successful_tps": len(successful) / elapsed,
        "elapsed_seconds_including_drain": elapsed,
        "dispatch_seconds": dispatch_seconds,
        "token_usage_coverage": len(tokens) / len(successful) if successful else 0,
        "reported_output_tokens_per_second": sum(tokens) / elapsed if tokens else None,
        "errors": dict(Counter(r["error"] for r in rows if not r["success"])),
        "timing_successful_only": timing,
    }
