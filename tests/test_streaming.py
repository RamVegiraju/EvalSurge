"""Regression tests for Databricks SSE completion and text semantics."""

import pytest

from benchmark_agents.streaming import consume


def state():
    return {"first_event_ms": None, "ttft_ms": None, "outputs": "", "output_tokens": None}


def test_databricks_stop_without_done_and_trailing_usage():
    row = state()
    consume(row, '{"choices":[{"delta":{"role":"assistant"}}]}', 1)
    consume(row, '{"choices":[{"delta":{"content":"No—opened items cannot be refunded."}}]}', 10)
    assert not consume(row, '{"choices":[{"delta":{},"finish_reason":"stop"}]}', 20)
    consume(row, '{"choices":[],"usage":{"completion_tokens":9}}', 21)
    assert row["completion_reason"] == "stop"
    assert row["output_tokens"] == 9
    assert row["ttft_ms"] == 10
    assert "—" in row["outputs"]


@pytest.mark.parametrize("reason", ["length", "content_filter"])
def test_truncation_is_not_success(reason):
    with pytest.raises(ValueError):
        consume(state(), '{"choices":[{"delta":{},"finish_reason":"' + reason + '"}]}', 1)


def test_metadata_and_reasoning_are_not_ttft():
    row = state()
    consume(row, '{"choices":[{"delta":{"reasoning_content":"thinking"}}]}', 5)
    assert row["ttft_ms"] is None
