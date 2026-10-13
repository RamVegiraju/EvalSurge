"""Shared SSE event semantics for HTTP adapters."""

import json
from typing import Any

from .trace_ids import valid_wire_trace_id


def consume(row: dict[str, Any], data: str, elapsed_ms: float) -> bool:
    """Apply one single-line SSE data payload to a mutable measurement row.

    Args:
        row: Attempt state with first_event_ms, ttft_ms, outputs, and output_tokens.
        data: Decoded JSON event or the literal [DONE] marker, without data:.
        elapsed_ms: Milliseconds since HTTP dispatch at event receipt.

    Returns:
        True for [DONE] or response.completed. A chat finish_reason of stop is
        recorded but returns false so trailing usage events can still be consumed.
        Metadata, reasoning, and tool deltas do not start the answer-text TTFT clock.

    Raises:
        ValueError: JSON is invalid, an error or truncation is reported, or an
            answer-text delta is not a string.
    """
    if row["first_event_ms"] is None:
        row["first_event_ms"] = elapsed_ms
    if data == "[DONE]":
        return True
    event = json.loads(data)
    kind = event.get("type", "")
    if kind == "evalsurge.trace" or (not kind and "trace_id" in event):
        trace_id = event.get("trace_id")
        if not valid_wire_trace_id(trace_id):
            raise ValueError("Invalid trace identifier")
        if row.get("trace_id") is not None and row["trace_id"] != trace_id:
            raise ValueError("Trace identifiers disagree")
        row["trace_id"] = trace_id
    if event.get("error") or kind in {"error", "response.failed", "response.incomplete"}:
        raise ValueError("Agent emitted an error event")
    text = ""
    choices = event.get("choices", [])
    if choices:
        text = choices[0].get("delta", {}).get("content") or ""
        finish_reason = choices[0].get("finish_reason")
        if finish_reason in {"content_filter", "length"}:
            raise ValueError("Agent output filtered or truncated")
        if finish_reason == "stop":
            row["completion_reason"] = "stop"
    elif kind == "response.output_text.delta":
        text = event.get("delta", "")
    if text:
        if not isinstance(text, str):
            raise ValueError("Expected a text delta")
        if row["ttft_ms"] is None:
            row["ttft_ms"] = elapsed_ms
        row["outputs"] += text
    usage = event.get("usage") or event.get("response", {}).get("usage") or {}
    row["output_tokens"] = usage.get(
        "completion_tokens", usage.get("output_tokens", row["output_tokens"])
    )
    return kind == "response.completed"
