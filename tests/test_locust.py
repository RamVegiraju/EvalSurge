"""Real localhost integration tests for the production Locust subprocess."""

import asyncio
from uuid import uuid4

import pytest

from benchmark_agents.locust_runner import run_load
from tests.test_template import configuration


async def test_locust_actual_concurrency_ttft_and_unicode(endpoint):
    base_url, server = endpoint
    request = configuration(duration_seconds=5, max_requests=7)
    request.target.url = base_url + "/normal"
    rows, metrics = await run_load(request, str(uuid4()), asyncio.Event())
    assert metrics["engine"] == "locust"
    assert metrics["observed_peak_in_flight"] == server["peak"] == 3
    assert server["received"] == len(rows) == 7
    assert metrics["error_rate"] == 0
    assert all(r["ttft_ms"] > r["first_event_ms"] + 100 for r in rows)
    assert all(r["outputs"] == "Answer—yes" and r["output_tokens"] == 3 for r in rows)


@pytest.mark.parametrize("mode,timeout", [("truncated", 1), ("slow", 0.2)])
async def test_locust_failures_are_recorded(endpoint, mode, timeout):
    base_url, _ = endpoint
    request = configuration(duration_seconds=5, max_requests=1, timeout_seconds=timeout)
    request.target.url = base_url + "/" + mode
    rows, metrics = await run_load(request, str(uuid4()), asyncio.Event())
    assert len(rows) == 1
    assert metrics["error_rate"] == 1
    assert rows[0]["error"]
    assert metrics["incomplete_measurements"] == 0


async def test_locust_cancellation_drains_in_flight(endpoint):
    base_url, server = endpoint
    request = configuration(duration_seconds=10, max_requests=100)
    request.target.url = base_url + "/normal"
    cancel = asyncio.Event()
    running = asyncio.create_task(run_load(request, str(uuid4()), cancel))
    for _ in range(1000):
        if server["active"] == 3:
            break
        await asyncio.sleep(0.01)
    cancel.set()
    rows, metrics = await running
    assert 0 < len(rows) < 100
    assert metrics["incomplete_measurements"] == 0
    assert all(r["success"] for r in rows)
