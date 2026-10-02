"""Shared SSE event semantics for HTTP adapters."""

import json
from typing import Any


def consume(row: dict[str, Any], data: str, elapsed_ms: float) -> bool:
    """Record first answer text; return whether a terminal event was received."""
    if row["first_event_ms"] is None:
        row["first_event_ms"] = elapsed_ms
    if data == "[DONE]":
        return True
    event = json.loads(data)
    kind = event.get("type", "")
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
