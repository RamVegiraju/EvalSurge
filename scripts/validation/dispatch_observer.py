"""Validation-only, content-free receipt counters for an owned real HTTP agent.

The sole engine sends the same run ID for its one excluded preflight and measured
requests. The first receipt is that preflight; only later receipts count as
measured. This assumption is valid only after the normal coordinator reports
``running``. This observer does not instrument Apps, decode prompts/outputs, delay
model calls, alter headers, or change engine measurement/cancellation semantics.
"""

import asyncio
import threading
import time
from typing import Any
from uuid import UUID


class DispatchObserver:
    """Wrap one exact agent route, retaining bounded opaque IDs and counters only."""

    def __init__(self, app: Any, path: str, *, max_runs: int = 16) -> None:
        """Retain an owned ASGI app and exact inference path, with no added traffic.

        Args:
            app: Real framework ASGI app; requests pass through unchanged.
            path: Exact hosted inference route, excluding unrelated/unknown routes.
            max_runs: Maximum UUID counter entries; validation creates at most four.

        Raises:
            ValueError: Counter budget or path is invalid.
        """
        if not 1 <= max_runs <= 100 or not path.startswith("/"):
            raise ValueError("Invalid dispatch observation bounds")
        self.app = app
        self.path = path
        self.max_runs = max_runs
        self._lock = threading.Lock()
        self._runs: dict[str, dict[str, int]] = {}

    def snapshot(self, run_id: str) -> dict[str, int]:
        """Copy thread-safe content-free counters without retaining caller values.

        Args:
            run_id: SDK-owned opaque run UUID, never an inference payload.

        Returns:
            Receipt count, measured receipt count, and currently active measured
            ASGI handlers. The excluded first preflight never counts as measured.
            In-flight covers application handling through its final return; it is
            not proof that the model is still generating tokens at that instant.
        """
        with self._lock:
            counts = self._runs.get(run_id, {"received": 0, "measured_inflight": 0})
            return {
                "received": counts["received"],
                "measured_received": max(0, counts["received"] - 1),
                "measured_inflight": counts["measured_inflight"],
            }

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """Observe only arrival/final application return; never consume body data.

        Lifespan, non-POST, other routes and invalid IDs pass through unchanged.
        A measured in-flight decrement is guaranteed even when serving fails or
        is cancelled. Only the validated UUID is retained, not headers or content.
        """
        run_id = None
        measured = False
        if (
            scope.get("type") == "http"
            and scope.get("method") == "POST"
            and scope.get("path") == self.path
        ):
            for name, value in scope.get("headers", ()):
                if name.lower() == b"x-benchmark-run-id":
                    try:
                        candidate = value.decode("ascii")
                        if len(candidate) == 36 and str(UUID(candidate)) == candidate:
                            run_id = candidate
                    except (UnicodeError, ValueError):
                        pass
                    break
        if run_id is not None:
            with self._lock:
                if run_id not in self._runs and len(self._runs) >= self.max_runs:
                    run_id = None
                else:
                    counts = self._runs.setdefault(run_id, {"received": 0, "measured_inflight": 0})
                    counts["received"] += 1
                    measured = counts["received"] > 1
                    if measured:
                        counts["measured_inflight"] += 1
        try:
            await self.app(scope, receive, send)
        finally:
            if run_id is not None and measured:
                with self._lock:
                    self._runs[run_id]["measured_inflight"] -= 1


def observation(observer: DispatchObserver | None, run_id: str) -> dict[str, int]:
    """Return counters, or zeros when external App receipt cannot be observed."""
    return (
        observer.snapshot(run_id)
        if observer is not None
        else {"received": 0, "measured_received": 0, "measured_inflight": 0}
    )


async def wait_for_active_dispatch(
    run: Any, observer: DispatchObserver | None, timeout: float
) -> tuple[Any, dict[str, int]]:
    """Wait for actual measured receipt before requesting direct cancellation.

    Args:
        run: Native asynchronous SDK run handle for this real benchmark.
        observer: Owned real HTTP app receipt observer; None for external Apps.
        timeout: Overall observation deadline in seconds, not a new traffic bound.

    Returns:
        Current typed status and counters at the cancellation decision. Without an
        observer a running status supports lifecycle cancellation only, not an
        active-dispatch claim. Natural completion/failure returns without a claim.

    Raises:
        TimeoutError: No eligible/terminal observation within the finite deadline.
    """
    deadline = time.monotonic() + timeout
    while True:
        status = await run.status()
        counts = observation(observer, str(run.id))
        if status.status in {
            "completed",
            "completed_with_gaps",
            "failed",
            "cancelled",
            "interrupted",
        }:
            return status, counts
        if status.status == "running" and (observer is None or counts["measured_inflight"] > 0):
            return status, counts
        if time.monotonic() >= deadline:
            raise TimeoutError("Measured dispatch observation window exceeded")
        await asyncio.sleep(0.01)


def wait_for_active_dispatch_sync(
    run: Any, observer: DispatchObserver, timeout: float
) -> tuple[Any, dict[str, int]]:
    """Observe actual HTTP receipts from the remote client's owned worker thread.

    Same semantics as the asynchronous helper. Thread-safe counters allow the
    real framework server to continue on its existing event loop while polling.
    """
    deadline = time.monotonic() + timeout
    while True:
        status = run.status()
        counts = observer.snapshot(str(run.id))
        if status.status in {
            "completed",
            "completed_with_gaps",
            "failed",
            "cancelled",
            "interrupted",
        } or (status.status == "running" and counts["measured_inflight"] > 0):
            return status, counts
        if time.monotonic() >= deadline:
            raise TimeoutError("Measured dispatch observation window exceeded")
        time.sleep(0.01)
