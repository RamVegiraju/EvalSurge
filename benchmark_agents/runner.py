"""Shared protocol payloads and descriptive benchmark metrics."""

import math
from collections import Counter
from typing import Any

from .models import RunRequest, Sample


def payload(request: RunRequest, sample: Sample) -> dict[str, Any]:
    """Convert one workload case into the selected streaming wire contract.

    Args:
        request: Target adapter and model settings for this run.
        sample: A nonempty query or messages array; messages take precedence.

    Returns:
        A streaming OpenAI Chat Completions or MLflow agent-server request body.
        Additional sample input keys remain evaluation metadata, not target fields.
        No reasoning, tool, or sampling settings are injected. Streamed token usage
        is requested only when target.request_usage is enabled for openai-chat.

    Raises:
        ValueError: A query is missing or messages are not nonempty role-bearing
            objects. This validates the supported envelope, not all provider fields.
    """
    messages = sample.inputs.get("messages")
    if messages is None:
        query = sample.inputs.get("query")
        if not isinstance(query, str) or not query:
            raise ValueError("Each sample needs inputs.query or inputs.messages.")
        messages = [{"role": "user", "content": query}]
    if (
        not isinstance(messages, list)
        or not messages
        or any(
            not isinstance(message, dict) or not isinstance(message.get("role"), str)
            for message in messages
        )
    ):
        raise ValueError("inputs.messages must be a nonempty array of objects with a role")
    if request.target.adapter == "mlflow-agent-server":
        return {"input": messages, "stream": True}
    body = {
        "model": request.target.model,
        "messages": messages,
        "stream": True,
    }
    if request.target.request_usage:
        body["stream_options"] = {"include_usage": True}
    return body


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
