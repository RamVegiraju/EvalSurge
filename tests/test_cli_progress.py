"""Lifecycle/CLI telemetry contracts only; no agents, model calls or completions.

HTTP fixtures represent EvalSurge status/report documents, not provider responses.
Native direct tests use retained planless metadata and a waiting lifecycle task;
they never submit workloads or substitute inference results.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

from benchmark_agents.coordinator import CoordinatorError
from benchmark_agents.run_views import status_view
from benchmark_agents.settings import Settings
from evalsurge import EvalSurge, RunFailed, RunStatus
from evalsurge.cli import _LiveProgress, main
from evalsurge.local import AsyncDirectRun, DirectRun, _wait_observed
from evalsurge.remote import (
    RemoteClient,
    RemoteRateLimitError,
    RemoteRunFailed,
    RemoteTimeout,
    TypedRemoteClient,
)
from tests.test_cli import factory
from tests.test_remote_sdk import CONFIG, RUN_ID, SECRET, Clock
from tests.test_unified_sdk_contract import _failure


def _status(state: str, *, load: str = "running") -> dict[str, Any]:
    """Construct metadata-only service status, including untrusted ignored fields."""
    return {
        "id": str(RUN_ID),
        "status": state,
        "name": SECRET,
        "phases": {"load": load, "evaluation": "off", "profiling": SECRET},
        "private": SECRET,
    }


def test_progress_emits_changes_and_bounded_heartbeat_without_private_fields(capsys) -> None:
    clock = Clock()
    progress = _LiveProgress(clock=clock.time)
    progress(_status("running"))
    clock.now = 9
    progress(_status("running"))
    clock.now = 10
    progress(_status("running"))
    progress(_status("profiling", load="completed"))
    progress({"status": SECRET, "phases": {SECRET: SECRET}})
    captured = capsys.readouterr()
    assert captured.out == ""
    lines = captured.err.splitlines()
    assert len(lines) == 4
    assert lines[0] == "[0s] running | load=running"
    assert lines[1] == "[10s] running | load=running"
    assert "profiling | load=completed" in lines[2]
    assert lines[3] == "[10s] unknown"
    assert SECRET not in captured.err


def test_progress_handles_typed_phase_observations(capsys) -> None:
    status = status_view(_failure())
    _LiveProgress()(status)
    text = capsys.readouterr().err
    assert "failed" in text
    assert "planning=failed" in text
    assert "evaluation=skipped" in text
    assert "planning_failed" not in text


@pytest.mark.parametrize("structured", [False, True])
def test_cli_progress_keeps_json_stdout_separate_and_adds_no_status_polls(
    tmp_path: Path, capsys, structured: bool
) -> None:
    config = tmp_path / "run.json"
    config.write_text(json.dumps(CONFIG))
    states = iter(["preflighting", "running", "profiling", "completed"])
    paths: list[str] = []
    report = {"run": {"id": str(RUN_ID), "status": "completed", "private": SECRET}}

    def handle(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.method == "POST":
            return httpx.Response(202, json={"id": str(RUN_ID), "status": "queued"})
        if request.url.path.endswith("/report"):
            return httpx.Response(200, json=report)
        return httpx.Response(200, json=_status(next(states)))

    argv = ["run", str(config), "--wait", "--progress"]
    if structured:
        argv.append("--json")
    assert main(argv, client_factory=factory(handle)) == 0
    captured = capsys.readouterr()
    assert SECRET not in captured.err
    assert all(
        state in captured.err for state in ("preflighting", "running", "profiling", "completed")
    )
    assert paths.count(f"/v2/runs/{RUN_ID}") == 4
    assert paths.count(f"/v2/runs/{RUN_ID}/report") == 1
    assert paths.count("/v2/runs") == 1
    if structured:
        assert json.loads(captured.out) == report
    else:
        assert SECRET not in captured.out
        assert "Run" in captured.out


@pytest.mark.parametrize(
    "extra,shown", [([], True), (["--no-progress"], False), (["--json"], False)]
)
def test_cli_progress_interactive_default_and_explicit_suppression(
    tmp_path: Path, monkeypatch, capsys, extra: list[str], shown: bool
) -> None:
    config = tmp_path / "run.json"
    config.write_text(json.dumps(CONFIG))
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"id": str(RUN_ID), "status": "queued"})
        if request.url.path.endswith("/report"):
            return httpx.Response(200, json={"run": {"status": "completed"}})
        return httpx.Response(200, json=_status("completed"))

    assert main(["run", str(config), "--wait", *extra], client_factory=factory(handle)) == 0
    assert bool(capsys.readouterr().err) is shown


def test_progress_without_wait_is_rejected_before_client_or_admission(
    tmp_path: Path, capsys
) -> None:
    config = tmp_path / "run.json"
    config.write_text(json.dumps(CONFIG))

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid progress options must not create a client")

    assert main(["run", str(config), "--progress"], client_factory=forbidden) == 2
    assert "requires --wait or --local" in capsys.readouterr().err


def test_remote_observer_preserves_hints_and_cannot_mutate_waiter_state() -> None:
    clock = Clock()
    paths = []
    states = iter(["running", "completed"])
    seen = []

    def handle(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/report"):
            return httpx.Response(200, json={"run": {"status": "completed"}})
        return httpx.Response(
            200,
            json={"id": str(RUN_ID), "status": next(states), "poll_after_seconds": 3},
            headers={"Retry-After": "2"},
        )

    def observe(body):
        seen.append(body["status"])
        body["status"] = "failed"

    with RemoteClient(
        "https://api.example",
        transport=httpx.MockTransport(handle),
        clock=clock.time,
        sleep=clock.sleep,
    ) as client:
        assert client.wait(RUN_ID, timeout=10, on_status=observe)["run"]["status"] == "completed"
    assert seen == ["running", "completed"]
    assert clock.sleeps == [3]
    assert len(paths) == 3


def test_observer_exception_is_not_retried_or_interpreted_as_server_rate_limiting() -> None:
    paths = []
    error = RemoteRateLimitError("observer-only error")

    def handle(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"id": str(RUN_ID), "status": "running"})

    def observe(body):
        raise error

    with (
        RemoteClient("https://api.example", transport=httpx.MockTransport(handle)) as client,
        pytest.raises(RemoteRateLimitError) as caught,
    ):
        client.wait(RUN_ID, on_status=observe)
    assert caught.value is error
    assert paths == [f"/v2/runs/{RUN_ID}"]


def test_remote_observer_time_consumes_wait_budget_without_cancellation() -> None:
    clock = Clock()
    paths = []

    def handle(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"id": str(RUN_ID), "status": "running"})

    def observe(body):
        clock.now = 3

    with (
        RemoteClient(
            "https://api.example",
            transport=httpx.MockTransport(handle),
            clock=clock.time,
            sleep=clock.sleep,
        ) as client,
        pytest.raises(RemoteTimeout),
    ):
        client.wait(RUN_ID, timeout=2, on_status=observe)
    assert paths == [f"/v2/runs/{RUN_ID}"]


def test_typed_remote_observer_receives_public_model_before_waiter_failure() -> None:
    status = status_view(_failure()).model_dump(mode="json")
    error = ValueError("observer-only error")
    seen = []

    def observe(body):
        seen.append(body)
        raise error

    with (
        TypedRemoteClient(
            "https://api.example",
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=status)),
        ) as client,
        pytest.raises(ValueError) as caught,
    ):
        client.wait(RUN_ID, on_status=observe)
    assert caught.value is error
    assert len(seen) == 1 and isinstance(seen[0], RunStatus)


@pytest.mark.asyncio
async def test_native_direct_observer_reads_terminal_metadata_without_inference(
    tmp_path: Path,
) -> None:
    seen = []
    async with EvalSurge.local_async(artifact_dir=tmp_path, settings=Settings()) as client:
        client._owned_coordinator().runs[str(RUN_ID)] = _failure()
        run = AsyncDirectRun(RUN_ID, client)
        with pytest.raises(RunFailed):
            await run.wait(on_status=seen.append)
    assert seen and all(
        isinstance(status, RunStatus) and status.status == "failed" for status in seen
    )


@pytest.mark.asyncio
async def test_status_projection_never_copies_cases_or_request_payloads(tmp_path: Path) -> None:
    class CannotCopy:
        def __deepcopy__(self, memo):
            pytest.fail("Status polling must not copy protected request payloads")

    async with EvalSurge.local_async(artifact_dir=tmp_path, settings=Settings()) as client:
        coordinator = client._owned_coordinator()
        row = _failure()
        row["config"] = {"cases": [CannotCopy()]}
        row["requests"] = [CannotCopy()]
        coordinator.runs[str(RUN_ID)] = row
        status = await client.status(RUN_ID)
        assert isinstance(status, RunStatus)
        assert "cases" not in status.model_dump()
        status.phases.planning = "running"
        assert coordinator.runs[str(RUN_ID)]["planning_status"] == "failed"


@pytest.mark.asyncio
async def test_direct_observer_coordinator_error_is_not_swallowed_as_report_readiness(
    tmp_path: Path,
) -> None:
    error = CoordinatorError(409, "observer-only conflict")

    def observe(status):
        raise error

    async with EvalSurge.local_async(artifact_dir=tmp_path, settings=Settings()) as client:
        client._owned_coordinator().runs[str(RUN_ID)] = _failure()
        with pytest.raises(CoordinatorError) as caught:
            await AsyncDirectRun(RUN_ID, client).wait(on_status=observe)
    assert caught.value is error


def test_typed_remote_observer_run_error_is_not_reinterpreted_as_a_report() -> None:
    error = RemoteRunFailed({"observer": "not a service report"})

    def observe(status):
        raise error

    status = status_view(_failure()).model_dump(mode="json")
    with (
        TypedRemoteClient(
            "https://api.example",
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=status)),
        ) as client,
        pytest.raises(RemoteRunFailed) as caught,
    ):
        client.wait(RUN_ID, on_status=observe)
    assert caught.value is error


def test_sync_direct_observer_uses_existing_loop_with_no_inference(tmp_path: Path) -> None:
    seen = []
    with EvalSurge(artifact_dir=tmp_path, settings=Settings()) as client:

        async def metadata_only():
            client._async_client._owned_coordinator().runs[str(RUN_ID)] = _failure()

        client._call(metadata_only)
        with pytest.raises(RunFailed):
            DirectRun(RUN_ID, client).wait(on_status=seen.append)
    assert seen and all(isinstance(status, RunStatus) for status in seen)


@pytest.mark.asyncio
@pytest.mark.parametrize("abort", ["timeout", "observer_error", "cancel_waiter"])
async def test_direct_progress_wait_abort_never_cancels_owned_lifecycle_task(
    tmp_path: Path, abort: str
) -> None:
    release = asyncio.Event()
    async with EvalSurge.local_async(artifact_dir=tmp_path, settings=Settings()) as client:
        coordinator = client._owned_coordinator()
        row = _failure()
        row.update(status="running", load_status="running")
        coordinator.runs[str(RUN_ID)] = row

        async def metadata_task():
            await release.wait()

        owned = asyncio.create_task(metadata_task())
        coordinator.tasks[str(RUN_ID)] = owned

        def observe(status):
            if abort == "observer_error":
                raise ValueError("observer-only error")

        run = AsyncDirectRun(RUN_ID, client)
        try:
            if abort == "cancel_waiter":
                waiter = asyncio.create_task(run.wait(on_status=observe))
                await asyncio.sleep(0)
                waiter.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await waiter
            else:
                with pytest.raises(TimeoutError if abort == "timeout" else ValueError):
                    await run.wait(timeout=0.01 if abort == "timeout" else None, on_status=observe)
            assert not owned.done() and not owned.cancelled()
        finally:
            release.set()
            await owned


@pytest.mark.asyncio
async def test_slow_direct_observer_cannot_start_another_callback_after_deadline(
    tmp_path: Path, monkeypatch
) -> None:
    """A controlled clock avoids real sleep/scheduler assumptions; no inference occurs."""
    release = asyncio.Event()
    observed = []
    waits = []
    clock = Clock()

    async def recorded_wait(tasks, *, timeout):
        waits.append(timeout)
        clock.now += timeout
        await asyncio.sleep(0)
        return set(), tasks

    monkeypatch.setattr("evalsurge.local.asyncio.wait", recorded_wait)
    async with EvalSurge.local_async(artifact_dir=tmp_path, settings=Settings()) as client:
        coordinator = client._owned_coordinator()
        row = _failure()
        row.update(status="running", load_status="running")
        coordinator.runs[str(RUN_ID)] = row
        owned = asyncio.create_task(release.wait())
        coordinator.tasks[str(RUN_ID)] = owned

        def slow_observer(status):
            observed.append(status)
            clock.now += 0.15

        try:
            with pytest.raises(TimeoutError):
                await _wait_observed(coordinator, RUN_ID, 0.2, slow_observer, clock=clock.time)
            assert len(observed) == 1
            assert waits and 0 < waits[0] < 0.1
            assert not owned.done() and not owned.cancelled()
        finally:
            release.set()
            await owned
