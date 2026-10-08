"""Receipt-counter instrumentation only; no agent, model or fixture completion.

The tiny ASGI callbacks exercise routing/cancellation/cleanup, not agent behavior.
No provider transport or inference response is mocked or substituted here.
"""

import asyncio
import json
from typing import Any

import pytest

from scripts.validation.dispatch_observer import DispatchObserver, observation

RUN = "a0102e33-b165-4124-9e66-b0f5e1414a1f"


def scope(run_id: str = RUN, path: str = "/agent/chat") -> dict[str, Any]:
    return {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [(b"x-benchmark-run-id", run_id.encode()), (b"authorization", b"private")],
    }


async def forbidden_receive() -> Any:
    raise AssertionError("The observer must never consume an inference body")


async def unused_send(event: Any) -> None:
    """Counter-only test callback; it emits no model response."""


@pytest.mark.asyncio
async def test_preflight_is_excluded_and_measured_handling_observed_through_return() -> None:
    started, finish = asyncio.Event(), asyncio.Event()
    calls = 0

    async def lifecycle_endpoint(scope: Any, receive: Any, send: Any) -> None:
        nonlocal calls
        calls += 1
        if calls > 1:
            started.set()
            await finish.wait()

    observer = DispatchObserver(lifecycle_endpoint, "/agent/chat")
    await observer(scope(), forbidden_receive, unused_send)
    assert observer.snapshot(RUN) == {"received": 1, "measured_received": 0, "measured_inflight": 0}
    measured = asyncio.create_task(observer(scope(), forbidden_receive, unused_send))
    await started.wait()
    counts = await asyncio.to_thread(observer.snapshot, RUN)
    assert counts == {"received": 2, "measured_received": 1, "measured_inflight": 1}
    assert "private" not in json.dumps(observer._runs)
    finish.set()
    await measured
    assert observer.snapshot(RUN)["measured_inflight"] == 0


@pytest.mark.asyncio
async def test_serving_failure_always_releases_measured_counter() -> None:
    calls = 0

    async def failed_lifecycle(scope: Any, receive: Any, send: Any) -> None:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise RuntimeError("failure detail not retained")

    observer = DispatchObserver(failed_lifecycle, "/agent/chat")
    await observer(scope(), forbidden_receive, unused_send)
    with pytest.raises(RuntimeError):
        await observer(scope(), forbidden_receive, unused_send)
    assert observer.snapshot(RUN)["measured_inflight"] == 0
    assert "failure detail" not in json.dumps(observer._runs)


@pytest.mark.asyncio
async def test_observer_ignores_unrelated_routes_invalid_ids_and_bounds_counters() -> None:
    seen = 0

    async def lifecycle_endpoint(scope: Any, receive: Any, send: Any) -> None:
        nonlocal seen
        seen += 1

    observer = DispatchObserver(lifecycle_endpoint, "/agent/chat", max_runs=1)
    await observer(scope("invalid-private-value"), forbidden_receive, unused_send)
    await observer(scope(path="/not-an-agent"), forbidden_receive, unused_send)
    assert observer.snapshot(RUN)["received"] == 0
    await observer(scope(), forbidden_receive, unused_send)
    other = "f520671b-5509-4a82-8f0c-aab1c8317d5f"
    await observer(scope(other), forbidden_receive, unused_send)
    assert observer.snapshot(other)["received"] == 0
    assert len(observer._runs) == 1
    assert seen == 4


def test_external_app_without_receipt_observation_cannot_claim_dispatch() -> None:
    assert observation(None, RUN) == {"received": 0, "measured_received": 0, "measured_inflight": 0}
