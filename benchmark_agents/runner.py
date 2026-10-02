"""Shared protocol payloads and descriptive benchmark metrics."""

import math
from collections import Counter
from typing import Any

from .models import RunRequest, Sample


def payload(request: RunRequest, sample: Sample) -> dict[str, Any]:
    """Build one of the two supported hosted endpoint contracts."""
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
    return {
        "model": request.target.model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }


def percentile(values: list[float], quantile: float) -> float | None:
    """Nearest-rank percentile with explicit empty result."""
    return sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)] if values else None


def summarize(
    rows: list[dict[str, Any]], elapsed: float, dispatch_seconds: float
) -> dict[str, Any]:
    """Report rates over total wall time including drain."""
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
