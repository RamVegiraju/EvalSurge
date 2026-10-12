"""Journal recovery and inert subprocess receipts; no agent or model calls."""

import asyncio
import json
import os
import sys
from contextlib import suppress
from typing import Any
from uuid import uuid4

import pytest

from benchmark_agents import locust_runner
from benchmark_agents.models import RunRequest
from benchmark_agents.runner import generator_health


@pytest.mark.skipif(os.name != "posix", reason="Native TERM grace uses POSIX signals")
async def test_repeated_cancellation_during_term_grace_reaps_owned_child(tmp_path, monkeypatch):
    """Native inert child delays TERM; no agent/inference/HTTP response is substituted."""
    original_spawn = asyncio.create_subprocess_exec
    spawned = asyncio.Event()
    children = []
    ready = tmp_path / "ready"
    terminating = tmp_path / "terminating"

    async def inert_spawn(*args, **kwargs):
        script = (
            "import signal,time,sys; from pathlib import Path; "
            f"signal.signal(signal.SIGTERM, lambda *args: (Path({str(terminating)!r}).touch(), "
            "time.sleep(0.4), sys.exit(0))); "
            f"Path({str(ready)!r}).touch(); time.sleep(30)"
        )
        child = await original_spawn(sys.executable, "-c", script, **kwargs)
        children.append(child)
        async with asyncio.timeout(3):
            while not ready.exists():
                await asyncio.sleep(0.01)
        spawned.set()
        return child

    monkeypatch.setattr(locust_runner.asyncio, "create_subprocess_exec", inert_spawn)
    request = RunRequest(
        target={"url": "http://127.0.0.1:9999/never-dispatched"},
        evaluation={
            "description": "Inert subprocess cleanup, no inference",
            "scorers": [],
            "samples": [{"inputs": {"query": "unused"}}],
        },
        load={"concurrency": 1, "duration_seconds": 0.1, "max_requests": 1},
    )
    task = asyncio.create_task(
        locust_runner.run_load(request, str(uuid4()), asyncio.Event(), artifact_dir=tmp_path)
    )
    try:
        await asyncio.wait_for(spawned.wait(), timeout=3)
        task.cancel()
        async with asyncio.timeout(3):
            while not terminating.exists():
                await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert children[0].returncode == 0
    finally:
        for child in children:
            if child.returncode is None:
                child.kill()
            await child.wait()
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def health(*, starts: int, completions: int, failures: int = 0, drained: bool = True):
    """Construct only numeric owned-writer evidence for recovery fault cases."""
    timing = {"count": 0, "mean_ms": None, "max_ms": None}
    return generator_health(
        {"interval_ms": 10, **timing},
        {
            "queue_capacity": 1,
            "peak_pending": 1,
            "backpressure_events": 0,
            "writer_failures": failures,
            "started_events": starts,
            "completed_events": completions,
            "drained": drained,
            "enqueue_wait_ms": timing,
            "durable_wait_ms": timing,
            "write_and_fsync_ms": timing,
        },
    )


@pytest.mark.parametrize(
    "issued,starts,completions,failures,drained,durable_completed,expected",
    [
        (1, 0, 0, 1, True, 0, True),
        (1, 1, 0, 1, True, 0, True),
        (1, 1, 1, 0, False, 1, True),
        (1, 1, 1, 0, True, 0, True),
        (2, 1, 1, 0, True, 1, True),
        (1, 1, 1, 0, True, 1, False),
        (0, 0, 0, 0, True, 0, False),
    ],
)
def test_journal_integrity_counts(
    issued, starts, completions, failures, drained, durable_completed, expected
):
    """Numeric checks do not reinterpret absent rows as successful measurements."""
    summary = {
        "attempted_requests": issued,
        "generator_health": health(
            starts=starts, completions=completions, failures=failures, drained=drained
        ),
    }
    rows = [{"error": None} for _ in range(durable_completed)]
    assert locust_runner.journal_integrity_failed(summary, rows) is expected


@pytest.mark.parametrize("fault", ["start", "completion", "drain", "mismatch", "worker_false"])
async def test_result_exists_cannot_hide_journal_incompleteness(tmp_path, monkeypatch, fault):
    """Actual inert child receipts reproduce parent recovery without dispatch/inference."""
    original_spawn = asyncio.create_subprocess_exec
    children: list[asyncio.subprocess.Process] = []
    row = {
        "request_id": "journal-attempt",
        "success": True,
        "error": None,
        "latency_ms": 25,
        "ttft_ms": None,
        "first_event_ms": None,
        "output_tokens": None,
        "dispatched": True,
    }
    summary = {
        "attempted_requests": 1,
        "successful_requests": 1,
        "elapsed_seconds_including_drain": 0.1,
        "dispatch_seconds": 0.05,
        "measurement_complete": fault != "worker_false",
        "generator_health": health(
            starts=0 if fault == "start" else 1,
            completions=0 if fault in {"start", "completion"} else 1,
            failures=1 if fault in {"start", "completion"} else 0,
            drained=fault != "drain",
        ),
    }
    entries = []
    if fault != "start":
        entries.append({"kind": "started", "row": {**row, "success": False}})
    if fault not in {"start", "completion", "mismatch"}:
        entries.append({"kind": "completed", "row": row})
    encoded_journal = "".join(json.dumps(entry) + "\n" for entry in entries)
    encoded_receipt = json.dumps({"summary": summary})

    async def inert_spawn(*args: Any, **kwargs: Any):
        script = (
            "import os; from pathlib import Path; "
            "p=Path(os.environ['BENCHMARK_LOCUST_RESULT']); "
            f"p.write_text({encoded_receipt!r}); "
            f"p.with_name('requests.jsonl').write_text({encoded_journal!r})"
        )
        child = await original_spawn(sys.executable, "-c", script, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(locust_runner.asyncio, "create_subprocess_exec", inert_spawn)
    request = RunRequest(
        target={"url": "http://127.0.0.1:9999/never-dispatched"},
        evaluation={
            "description": "Inert recovery",
            "scorers": [],
            "samples": [{"inputs": {"query": "unused"}}],
        },
        load={"concurrency": 1, "duration_seconds": 0.1, "max_requests": 1},
    )
    try:
        rows, recovered = await asyncio.wait_for(
            locust_runner.run_load(request, str(uuid4()), asyncio.Event(), artifact_dir=tmp_path),
            timeout=5,
        )
        assert recovered["measurement_complete"] is False
        assert recovered["load_status"] == "interrupted"
        assert recovered["worker_exit_code"] == 0
        assert recovered["journal_integrity_failed"] is (fault != "worker_false")
        assert recovered["generator_health"]["status"] == (
            "unknown" if fault == "worker_false" else "degraded"
        )
        assert recovered["incomplete_measurements"] == (
            1 if fault in {"start", "completion", "mismatch"} else 0
        )
        if fault == "start":
            assert rows == [] and recovered["successful_requests"] == 0
            preflight = locust_runner.preflight_result(rows, recovered)
            assert "journal" in preflight.error.message
        if fault in {"completion", "mismatch"}:
            assert rows[0]["error"] == "WorkerInterrupted"
            assert recovered["successful_requests"] == 0
        assert children[0].returncode == 0
    finally:
        for child in children:
            if child.returncode is None:
                child.terminate()
            await asyncio.wait_for(child.wait(), timeout=2)


def test_historical_missing_generator_health_is_not_a_verdict():
    """Historical receipts keep compatibility; public projection handles missing evidence."""
    assert not locust_runner.journal_integrity_failed({}, [])
    assert locust_runner.journal_integrity_failed({"attempted_requests": 1}, [])


@pytest.mark.parametrize(
    "field",
    ["attempted_requests", "started_events", "completed_events", "writer_failures", "status"],
)
def test_malformed_new_receipt_counts_fail_closed(field):
    """Boolean counts and unknown status cannot masquerade as a valid native receipt."""
    summary = {"attempted_requests": 1, "generator_health": health(starts=1, completions=1)}
    if field == "attempted_requests":
        summary[field] = True
    elif field == "status":
        summary["generator_health"][field] = "verified"
    else:
        summary["generator_health"]["journal"][field] = field != "writer_failures"
    assert locust_runner.journal_integrity_failed(summary, [{"error": None}])
