"""Independent metric arithmetic checks; numeric rows are not inference evidence."""

from copy import deepcopy
from typing import Any

import pytest

from benchmark_agents.runner import percentile, summarize


def row(
    latency_ms: float | None,
    *,
    success: bool = True,
    error: str | None = None,
    output_tokens: int | None = None,
) -> dict[str, Any]:
    """Build a numeric aggregation input without agent inputs or completions."""
    return {
        "success": success,
        "error": error,
        "latency_ms": latency_ms,
        "ttft_ms": None,
        "first_event_ms": None,
        "output_tokens": output_tokens,
    }


def test_successful_percentiles_do_not_hide_failed_attempts_in_error_rate() -> None:
    """Timeout durations are excluded from successful tails, but not attempt counts."""
    rows = [row(10), row(20), row(1000, success=False, error="TimeoutError")]
    measured = summarize(rows, elapsed=2, dispatch_seconds=1)
    assert measured["requests"] == 3
    assert measured["successful_requests"] == 2
    assert measured["error_rate"] == pytest.approx(1 / 3)
    assert measured["timing_successful_only"]["latency_ms"] == {
        "count": 2,
        "p50": 10,
        "p95": 20,
        "p99": 20,
    }
    assert measured["errors"] == {"TimeoutError": 1}


def test_rates_include_drain_and_exclude_interrupted_completions() -> None:
    """Rates use the whole window, never the last dispatch offset as steady state."""
    rows = [
        row(25),
        row(200, success=False, error="TimeoutError"),
        row(None, success=False, error="WorkerInterrupted"),
    ]
    measured = summarize(rows, elapsed=10, dispatch_seconds=2)
    assert measured["completed_tps"] == 0.2
    assert measured["successful_tps"] == 0.1
    assert measured["elapsed_seconds_including_drain"] == 10
    assert measured["dispatch_seconds"] == 2
    assert measured["error_rate"] == pytest.approx(2 / 3)


def test_missing_token_usage_and_ttft_are_not_fabricated() -> None:
    """Partial usage retains its coverage; unknown token/TTFT values stay unknown."""
    measured = summarize([row(10, output_tokens=8), row(20)], elapsed=4, dispatch_seconds=1)
    assert measured["token_usage_coverage"] == 0.5
    assert measured["reported_output_tokens_per_second"] == 2
    assert measured["timing_successful_only"]["ttft_ms"] == {
        "count": 0,
        "p50": None,
        "p95": None,
        "p99": None,
    }
    unavailable = summarize([row(10)], elapsed=4, dispatch_seconds=1)
    assert unavailable["token_usage_coverage"] == 0
    assert unavailable["reported_output_tokens_per_second"] is None


def test_known_zero_usage_is_distinct_from_unavailable_usage() -> None:
    """A reported zero is an observation, not a missing token-usage value."""
    measured = summarize([row(10, output_tokens=0)], elapsed=1, dispatch_seconds=0.1)
    assert measured["token_usage_coverage"] == 1
    assert measured["reported_output_tokens_per_second"] == 0


def test_empty_aggregate_has_no_latency_or_error_rate_observations() -> None:
    """No requests do not become a zero-latency or zero-error benchmark."""
    measured = summarize([], elapsed=1, dispatch_seconds=0)
    assert measured["requests"] == 0
    assert measured["error_rate"] is None
    assert measured["timing_successful_only"]["latency_ms"]["p95"] is None
    assert measured["reported_output_tokens_per_second"] is None


def test_nearest_rank_and_aggregation_preserve_source_evidence() -> None:
    """Known ranks are independent of input order and do not mutate the inputs."""
    values = list(range(100, 0, -1))
    assert [percentile(values, q) for q in (0.5, 0.95, 0.99)] == [50, 95, 99]
    assert values == list(range(100, 0, -1))
    rows = [row(value) for value in values]
    before = deepcopy(rows)
    measured = summarize(rows, elapsed=10, dispatch_seconds=8)
    assert measured["timing_successful_only"]["latency_ms"]["p99"] == 99
    assert measured["timing_successful_only"]["first_event_ms"]["count"] == 0
    assert rows == before
