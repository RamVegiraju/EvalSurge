"""Offline regressions for coordinator ownership, persistence, and safe errors."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn
from uuid import UUID, uuid4

import httpx
import pytest

from benchmark_agents import api, coordinator
from benchmark_agents.connections import Connection
from benchmark_agents.coordinator import CoordinatorError, RunCoordinator
from benchmark_agents.models import Evaluation, Plan, PreflightResult, RunRequest
from benchmark_agents.planner import fingerprint
from benchmark_agents.storage import append_event

PRIVATE_SENTINEL = "synthetic-private-operator-value"


def configuration() -> RunRequest:
    """Return a small localhost workload with all model-based planning disabled."""
    return RunRequest(
        target={"url": "http://127.0.0.1:9999/chat"},
        evaluation={
            "description": "Synthetic failure-path workload",
            "scorers": [],
            "registered_scorers": [],
            "samples": [{"inputs": {"query": "Synthetic question"}}],
        },
        load={
            "concurrency": 1,
            "duration_seconds": 0.1,
            "max_requests": 1,
            "timeout_seconds": 0.1,
        },
    )


async def offline_plan(evaluation: Evaluation) -> Plan:
    """Freeze local inputs without constructing provider or tracking-store clients.

    Args:
        evaluation: Validated synthetic policy and cases.

    Returns:
        An explicit empty-scorer plan used only for lifecycle tests.
    """
    return Plan(
        source="explicit",
        rubric_hash="synthetic-rubric-hash",
        dataset_hash=fingerprint([sample.model_dump() for sample in evaluation.samples]),
        evaluation_hash=fingerprint(evaluation.model_dump()),
        max_scored_requests=evaluation.max_scored_requests,
        sampling_seed=evaluation.sampling_seed,
        description=evaluation.description,
        recommendations=[],
    )


async def failed_probe(*args: Any, **kwargs: Any) -> PreflightResult:
    """Return a content-free failed probe without dispatching any agent request."""
    return PreflightResult(
        status="failed",
        error={
            "code": "target_http_error",
            "message": "Inference failed. Load test did not start.",
        },
    )


async def unexpected_load(*args: Any, **kwargs: Any) -> NoReturn:
    """Reject accidental load dispatch outside explicitly controlled test boundaries."""
    raise AssertionError("This failure regression must not dispatch target traffic")


def unexpected_postload(*args: Any, **kwargs: Any) -> NoReturn:
    """Reject accidental profiling or judging, including remote tracking access."""
    raise AssertionError("This failure regression must not collect traces or judge")


@pytest.fixture(autouse=True)
def offline_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate operator configuration and replace all potential outbound boundaries."""
    monkeypatch.delenv("BENCHMARK_API_KEY", raising=False)
    monkeypatch.setenv("BENCHMARK_CONNECTIONS", "{}")
    monkeypatch.setenv("BENCHMARK_ALLOWED_TARGETS", "[]")
    monkeypatch.setenv("MLFLOW_MODEL_CATALOG_URI", "")
    monkeypatch.setattr(coordinator, "create_plan", offline_plan)
    monkeypatch.setattr(coordinator, "run_preflight", failed_probe)
    monkeypatch.setattr(coordinator, "run_load", unexpected_load)
    monkeypatch.setattr(coordinator, "collect_profiles", unexpected_postload)
    monkeypatch.setattr(coordinator, "evaluate", unexpected_postload)


def fail_writes(
    monkeypatch: pytest.MonkeyPatch,
    predicate: Callable[[Path, Any], bool],
) -> list[Path]:
    """Inject sustained faults into selected coordinator snapshot writes.

    Args:
        monkeypatch: Test-owned patch lifetime.
        predicate: Selects writes that must fail before reaching real storage.

    Returns:
        Paths of attempted failing writes, populated during test execution.

    Matching writes keep failing until fixture teardown. Other writes retain the
    real atomic storage implementation; no assertion requires storage to recover.
    """
    original_write = coordinator.atomic_json
    failures: list[Path] = []

    def injected_write(path: Path, value: Any) -> None:
        """Write normally unless the selected storage operation is unavailable.

        Args:
            path: Destination selected by the coordinator.
            value: Snapshot the coordinator attempted to commit.

        Raises:
            OSError: A matching fault is active.
        """
        if predicate(path, value):
            failures.append(path)
            raise OSError(PRIVATE_SENTINEL)
        original_write(path, value)

    monkeypatch.setattr(coordinator, "atomic_json", injected_write)
    return failures


async def settle_tasks(*tasks: asyncio.Task[Any]) -> list[Any]:
    """Drain test-owned tasks and retrieve failures without hiding state assertions.

    Args:
        tasks: Already-created coordinator or shutdown tasks.

    Returns:
        Task results or exceptions in input order.

    Raises:
        TimeoutError: Cleanup has not completed within three seconds.
    """
    return await asyncio.wait_for(
        asyncio.gather(*tasks, return_exceptions=True),
        timeout=3,
    )


@pytest.mark.parametrize("destination", ["snapshot", "summary"])
async def test_final_persistence_fault_retains_terminal_state_and_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, destination: str
) -> None:
    """Final write failures must not evict truth or leave an active task behind."""
    owner = RunCoordinator(tmp_path)
    await owner.open()
    try:
        accepted = await owner.submit(configuration(), "terminal-once")
        identifier = UUID(accepted.id)
        task = owner.tasks[accepted.id]
        snapshot = owner.root / f"{accepted.id}.json"
        selected = (
            snapshot if destination == "snapshot" else owner.root / "summaries" / snapshot.name
        )
        failures = fail_writes(
            monkeypatch,
            lambda path, value: path == selected and value.get("status") == "failed",
        )
        await settle_tasks(task)

        assert failures
        run = owner.get_run(identifier)
        assert run.status == "failed"
        assert run.preflight.status == "failed"
        assert run.load_status == run.evaluation_status == "skipped"
        history = owner.list_runs()
        assert history.total == 1
        assert history.items[0].id == accepted.id
        assert history.items[0].status == run.status
        assert history.items[0].load_status == run.load_status
        assert history.items[0].evaluation_status == run.evaluation_status
        assert not owner.tasks
        assert not owner.cancellations

        replay = await owner.submit(configuration(), "terminal-once")
        assert replay.id == accepted.id and replay.status == run.status
        report = owner.get_report(identifier)
        assert report.run.status == run.status
        assert report.total == 0
        assert PRIVATE_SENTINEL not in report.model_dump_json()
        with pytest.raises(CoordinatorError) as unavailable:
            await owner.submit(configuration())
        assert unavailable.value.status_code == 500
        assert not owner.tasks
    finally:
        await owner.close()


async def test_restart_uses_primary_snapshot_after_terminal_summary_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After storage restoration, stale compact history must not override terminal truth."""
    owner = RunCoordinator(tmp_path)
    await owner.open()
    try:
        accepted = await owner.submit(configuration(), "restart-once")
        snapshot = owner.root / f"{accepted.id}.json"
        summary = owner.root / "summaries" / snapshot.name
        with monkeypatch.context() as fault_scope:
            failures = fail_writes(
                fault_scope,
                lambda path, value: path == summary and value.get("status") == "failed",
            )
            await settle_tasks(owner.tasks[accepted.id])
            assert failures
            assert owner.get_run(UUID(accepted.id)).status == "failed"
            assert owner.list_runs().items[0].status == "failed"
            assert json.loads(snapshot.read_text())["status"] == "failed"
            assert json.loads(summary.read_text())["status"] != "failed"
            assert not owner.tasks
    finally:
        await owner.close()

    restarted = RunCoordinator(tmp_path)
    await restarted.open()
    try:
        run = restarted.get_run(UUID(accepted.id))
        history = restarted.list_runs(status="failed")
        assert history.total == 1
        assert history.items[0].id == accepted.id
        assert history.items[0].status == run.status == "failed"
        assert history.items[0].load_status == run.load_status == "skipped"
        assert history.items[0].evaluation_status == run.evaluation_status == "skipped"
        replay = await restarted.submit(configuration(), "restart-once")
        assert replay.id == accepted.id and replay.status == run.status
        assert not restarted.tasks
        assert json.loads(summary.read_text())["status"] == run.status
    finally:
        await restarted.close()


@pytest.mark.parametrize("operation", ["plan", "submit"])
async def test_repeated_close_cancellation_keeps_lock_until_planner_drains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    """Two cancellation deliveries must not release storage under a pending writer."""
    entered, release = asyncio.Event(), asyncio.Event()

    async def paused_plan(evaluation: Evaluation) -> Plan:
        """Pause a local planner until the test permits its final storage write."""
        entered.set()
        await release.wait()
        return await offline_plan(evaluation)

    monkeypatch.setattr(coordinator, "create_plan", paused_plan)
    owner, contender = RunCoordinator(tmp_path), RunCoordinator(tmp_path)
    await owner.open()
    config = configuration()
    pending = asyncio.create_task(
        owner.evaluation_plan(config.evaluation) if operation == "plan" else owner.submit(config)
    )
    closing: asyncio.Task[None] | None = None
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        closing = asyncio.create_task(owner.close())
        async with asyncio.timeout(2):
            while not owner._closing:
                await asyncio.sleep(0)

        for _ in range(2):
            closing.cancel()
            await asyncio.sleep(0.01)

        assert not pending.done()
        with pytest.raises(OSError):
            await contender.open()
        release.set()
        results = await settle_tasks(pending, closing)
        assert isinstance(results[1], asyncio.CancelledError)
        if operation == "submit":
            assert isinstance(results[0], RuntimeError | CoordinatorError)
        else:
            assert isinstance(results[0], Plan)
            assert (owner.root / "plans" / f"{results[0].id}.json").exists()
        assert not owner.tasks
        assert not owner.cancellations
        await contender.open()
        assert contender.list_runs().total == 0
    finally:
        release.set()
        await settle_tasks(pending, *([closing] if closing is not None else []))
        await owner.close()
        await contender.close()


@pytest.mark.parametrize("destination", ["snapshot", "summary"])
async def test_partial_admission_never_replays_an_ownerless_queued_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, destination: str
) -> None:
    """Retain only a safe terminal receipt when a primary admission snapshot exists."""
    owner = RunCoordinator(tmp_path)
    await owner.open()
    try:
        failures = fail_writes(
            monkeypatch,
            lambda path, value: (
                path.parent == owner.root and "config" in value
                if destination == "snapshot"
                else path.parent == owner.root / "summaries"
            ),
        )
        with pytest.raises(CoordinatorError) as failure:
            await owner.submit(configuration(), "admission-once")
        assert failure.value.status_code == 500
        assert "no agent preflight or load was started" in str(failure.value)
        assert PRIVATE_SENTINEL not in str(failure.value)
        assert failures
        assert not owner.tasks
        assert not owner.cancellations

        history = owner.list_runs()
        if destination == "snapshot":
            assert history.total == 0
            assert not owner.runs
            with pytest.raises(CoordinatorError) as unknown:
                owner.get_run(UUID(failures[0].stem))
            assert unknown.value.status_code == 404
            with pytest.raises(CoordinatorError) as unavailable:
                await owner.submit(configuration(), "admission-once")
            assert unavailable.value.status_code == 500
            assert owner.list_runs().total == 0
        else:
            assert history.total == 1
            prior = history.items[0]
            assert prior.status in {"failed", "interrupted"}
            assert (owner.root / f"{prior.id}.json").exists()
            replay = await owner.submit(configuration(), "admission-once")
            assert replay.id == prior.id
            assert replay.status == prior.status
            run = owner.get_run(UUID(replay.id))
            assert run.status == prior.status
            assert run.load_status in {"skipped", "interrupted", "failed"}
            assert run.evaluation_status in {"skipped", "interrupted"}
            assert PRIVATE_SENTINEL not in run.model_dump_json()
            assert not owner.tasks
            assert not owner.cancellations
    finally:
        await owner.close()


async def test_terminal_profile_write_failure_returns_synthetic_gap_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unavailable profile file must not turn a terminal failure into eternal 409."""

    async def passed_probe(*args: Any, **kwargs: Any) -> PreflightResult:
        """Permit the controlled load boundary without making a probe request."""
        return PreflightResult(status="passed")

    request_id = str(uuid4())

    async def failed_load(
        request: RunRequest,
        run_id: str,
        cancel: asyncio.Event,
        artifact_dir: Path,
        *,
        connection: Connection | None = None,
    ) -> NoReturn:
        """Persist one synthetic capture, then fail before returning load results.

        Args:
            request: Validated local workload, not dispatched by this helper.
            run_id: Coordinator-owned identifier for the real local journal.
            cancel: Unused cancellation signal; no target work is performed.
            artifact_dir: Test-owned storage root.
            connection: Unused exact binding, never authenticated here.

        Raises:
            OSError: The simulated load storage operation failed.
        """
        directory = artifact_dir / run_id
        directory.mkdir(parents=True)
        append_event(
            directory / "requests.jsonl",
            {
                "kind": "completed",
                "row": {
                    "request_id": request_id,
                    "case_id": 0,
                    "success": True,
                    "latency_ms": 12.5,
                    "inputs": request.evaluation.samples[0].inputs,
                    "outputs": "Synthetic captured answer",
                },
            },
        )
        raise OSError(PRIVATE_SENTINEL)

    monkeypatch.setattr(coordinator, "run_preflight", passed_probe)
    monkeypatch.setattr(coordinator, "run_load", failed_load)
    failures = fail_writes(monkeypatch, lambda path, value: path.name == "profiling.json")
    owner = RunCoordinator(tmp_path)
    await owner.open()
    try:
        accepted = await owner.submit(configuration())
        await settle_tasks(owner.tasks[accepted.id])
        assert failures
        assert not (owner.root / accepted.id / "profiling.json").exists()

        report = await owner.wait(UUID(accepted.id), timeout=2)
        assert report.run.status == report.run.load_status == "failed"
        assert report.run.evaluation_status == "skipped"
        assert report.run.profiling_status == "failed"
        assert report.total == report.profiling.total_requests == 1
        assert report.profiling.traced_requests == report.profiling.coverage == 0
        assert sum(report.profiling.gaps.values()) == 1
        assert report.profiling.notes
        assert report.requests[0].request_id == request_id
        assert report.requests[0].latency_ms == 12.5
        assert report.requests[0].status != "available"
        assert not report.requests[0].spans
        assert PRIVATE_SENTINEL not in report.model_dump_json()
        assert not owner.tasks
    finally:
        await owner.close()


async def test_invalid_injected_connection_error_is_content_free(tmp_path: Path) -> None:
    """A malformed operator URL must not echo its value through a domain exception."""
    owner = RunCoordinator(tmp_path)
    await owner.open()
    try:
        with pytest.raises(CoordinatorError) as failure:
            await owner.submit(
                configuration(),
                connection=Connection(url=f"invalid-url/{PRIVATE_SENTINEL}"),
            )
        assert failure.value.status_code == 422
        assert PRIVATE_SENTINEL not in str(failure.value)
        assert owner.list_runs().total == 0
        assert not owner.tasks
    finally:
        await owner.close()


@pytest.mark.parametrize("invalid_field", ["url", "auth"])
async def test_invalid_operator_configuration_rest_error_does_not_echo_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid_field: str
) -> None:
    """REST configuration failures retain a safe envelope and correlation headers."""
    config = configuration()
    config.target.connection_id = "synthetic"
    binding = {"url": str(config.target.url), "auth": "none"}
    binding[invalid_field] = (
        f"invalid-url/{PRIVATE_SENTINEL}" if invalid_field == "url" else PRIVATE_SENTINEL
    )
    monkeypatch.setenv("BENCHMARK_CONNECTIONS", json.dumps({"synthetic": binding}))
    app = api.create_app(tmp_path)
    transport = httpx.ASGITransport(
        app=app, client=("127.0.0.1", 12345), raise_app_exceptions=False
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client,
    ):
        response = await client.post("/v1/runs", json=config.model_dump(mode="json"))
        assert response.status_code == 422
        assert PRIVATE_SENTINEL not in response.text
        error = response.json()["error"]
        assert error["code"] and error["message"]
        assert error["request_id"] == response.headers["X-Request-ID"]
        assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("entrypoint", ["plan", "submit"])
async def test_plan_storage_failure_preserves_rest_error_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entrypoint: str
) -> None:
    """Plan-write faults keep the internal-error code and never schedule agent traffic."""
    app = api.create_app(tmp_path)
    failures = fail_writes(monkeypatch, lambda path, value: path.parent == tmp_path / "plans")
    config = configuration()
    path = "/v1/evaluation-plans" if entrypoint == "plan" else "/v1/runs"
    body = config.evaluation if entrypoint == "plan" else config
    transport = httpx.ASGITransport(
        app=app, client=("127.0.0.1", 12345), raise_app_exceptions=False
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client,
    ):
        response = await client.post(path, json=body.model_dump(mode="json"))
        assert response.status_code == 500
        assert PRIVATE_SENTINEL not in response.text
        error = response.json()["error"]
        assert error["code"] == "internal_error"
        assert error["request_id"] == response.headers["X-Request-ID"]
        assert response.headers["Cache-Control"] == "no-store"
        assert "no agent preflight or load was started" in error["message"]
        repeated = await client.post(path, json=body.model_dump(mode="json"))
        assert repeated.status_code == 500
        assert repeated.json()["error"]["code"] == "internal_error"
        assert len(failures) == 1
        owner = app.state.coordinator
        assert owner.runs == owner.tasks == owner.index == {}
