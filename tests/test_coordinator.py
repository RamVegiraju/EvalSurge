"""Shared lifecycle invariants independent of HTTP or the Python facade."""

import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from benchmark_agents import coordinator
from benchmark_agents.connections import Connection
from benchmark_agents.coordinator import CoordinatorError, RunCoordinator
from benchmark_agents.models import Evaluation, Plan, PreflightResult, RunRequest
from tests.test_template import configuration


async def test_coordinator_exclusive_lock_and_reuse(tmp_path: Path) -> None:
    owner = RunCoordinator(tmp_path)
    contender = RunCoordinator(tmp_path)
    await owner.open()
    try:
        with pytest.raises(OSError):
            await contender.open()
        with pytest.raises(RuntimeError, match="already open"):
            await owner.open()
    finally:
        await owner.close()
    await contender.open()
    await contender.close()
    with pytest.raises(RuntimeError, match="not open"):
        contender.list_runs()


async def test_input_snapshot_wait_timeout_and_safe_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: list[Any] = []
    entered = asyncio.Event()
    release = asyncio.Event()

    async def probe(
        request: RunRequest, *args: Any, connection: Connection, **kwargs: Any
    ) -> PreflightResult:
        entered.set()
        await release.wait()
        observed.extend([request, connection])
        return PreflightResult(
            status="failed",
            error={
                "code": "target_http_error",
                "message": "Inference failed. Load test did not start.",
            },
        )

    monkeypatch.setattr(coordinator, "run_preflight", probe)
    owner = RunCoordinator(tmp_path)
    await owner.open()
    try:
        config = configuration()
        binding = Connection(url=str(config.target.url))
        accepted = await owner.submit(config, "once", connection=binding)
        identifier = UUID(accepted.id)
        await entered.wait()
        config.evaluation.samples[0].inputs["query"] = "mutated"
        binding.auth = "bearer"
        with pytest.raises(TimeoutError):
            await owner.wait(identifier, timeout=0.01)
        assert owner.get_run(identifier).status == "preflighting"
        release.set()
        report = await owner.wait(identifier, timeout=2)
        assert observed[0].evaluation.samples[0].inputs["query"] == "Can I refund?"
        assert observed[1].auth == "none"
        assert report.run.load_status == "skipped"
        assert "judge-readiness" in report.profiling.notes[0]
        assert "quality results" in report.profiling.notes[0]
        assert owner.list_runs().items[0].url == f"/v1/runs/{identifier}"
        report.run.plan.notes.append("mutated")
        assert "mutated" not in owner.get_run(identifier).plan.notes
        assert owner.tasks == owner.runs == owner.cancellations == {}
    finally:
        release.set()
        await owner.close()


async def test_mixed_history_keeps_versioned_links_after_snapshot_index_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Persisted v2 metadata discriminates paths without changing v1 history links."""

    async def probe(*args: Any, **kwargs: Any) -> PreflightResult:
        return PreflightResult(
            status="failed", error={"code": "target_http_error", "message": "Failed"}
        )

    monkeypatch.setattr(coordinator, "run_preflight", probe)
    owner = RunCoordinator(tmp_path)
    await owner.open()
    try:
        legacy = await owner.submit(configuration())
        await owner.tasks[legacy.id]
        modern = await owner.submit(configuration(), defer_planning=True, evaluation_mode="off")
        await owner.tasks[modern.id]
    finally:
        await owner.close()
    # Summaries are rebuilt from authoritative snapshots, including older snapshots
    # whose existing evaluation_mode was not previously copied into compact indexes.
    recovered = RunCoordinator(tmp_path)
    await recovered.open()
    try:
        links = {entry.id: entry.url for entry in recovered.list_runs().items}
        assert links == {
            legacy.id: f"/v1/runs/{legacy.id}",
            modern.id: f"/v2/runs/{modern.id}",
        }
        assert recovered.get_run(UUID(legacy.id)).status == "failed"
    finally:
        await recovered.close()


async def test_domain_bounds_and_binding_before_admission(tmp_path: Path) -> None:
    owner = RunCoordinator(tmp_path)
    await owner.open()
    try:
        for offset, limit in [(-1, 1), (0, 0), (0, 101)]:
            with pytest.raises(CoordinatorError) as failure:
                owner.list_runs(offset, limit)
            assert failure.value.status_code == 422
        with pytest.raises(CoordinatorError) as failure:
            await owner.submit(
                configuration(), connection=Connection(url="https://different.example/chat")
            )
        assert failure.value.status_code == 422
        assert owner.index == {}
        with pytest.raises(CoordinatorError) as failure:
            owner.get_run(uuid4())
        assert failure.value.status_code == 404
    finally:
        await owner.close()


async def test_cancelled_close_waits_for_pending_planner_before_unlock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    original_create_plan = coordinator.create_plan

    async def paused_plan(evaluation: Evaluation) -> Plan:
        entered.set()
        await release.wait()
        return await original_create_plan(evaluation)

    monkeypatch.setattr(coordinator, "create_plan", paused_plan)
    owner, contender = RunCoordinator(tmp_path), RunCoordinator(tmp_path)
    await owner.open()
    submitting = asyncio.create_task(owner.submit(configuration()))
    await entered.wait()
    closing = asyncio.create_task(owner.close())
    try:
        for _ in range(100):
            if owner._closing:
                break
            await asyncio.sleep(0.001)
        assert owner._closing
        closing.cancel()
        await asyncio.sleep(0.01)
        with pytest.raises(OSError):
            await contender.open()
        assert not closing.done()
    finally:
        release.set()
        with pytest.raises(RuntimeError, match="not open"):
            await submitting
        with pytest.raises(asyncio.CancelledError):
            await closing
        await owner.close()
    await contender.open()
    assert contender.list_runs().total == 0
    await contender.close()


async def test_load_start_failure_retains_terminal_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def passed(*args: Any, **kwargs: Any) -> PreflightResult:
        return PreflightResult(status="passed")

    async def failed_load(*args: Any, **kwargs: Any) -> None:
        raise OSError("private-infrastructure-detail")

    monkeypatch.setattr(coordinator, "run_preflight", passed)
    monkeypatch.setattr(coordinator, "run_load", failed_load)
    owner = RunCoordinator(tmp_path)
    await owner.open()
    try:
        accepted = await owner.submit(configuration())
        report = await owner.wait(UUID(accepted.id))
        assert report.run.status == report.run.load_status == "failed"
        assert report.run.profiling_status == "failed"
        assert report.total == 0
        assert "private-infrastructure-detail" not in report.model_dump_json()
        assert owner.tasks == {}
    finally:
        await owner.close()


async def test_local_input_byte_limit_applies_before_any_planning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden_plan(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Oversized input must not invoke planning")

    monkeypatch.setattr(coordinator, "create_plan", forbidden_plan)
    owner = RunCoordinator(tmp_path)
    await owner.open()
    try:
        request = configuration()
        request.evaluation.samples[0].inputs["large"] = "x" * 8_000_000
        for operation in [
            owner.submit(request),
            owner.evaluation_plan(request.evaluation),
        ]:
            with pytest.raises(CoordinatorError) as failure:
                await operation
            assert failure.value.status_code == 413
        assert owner.index == owner.tasks == {}
        assert not (tmp_path / "plans").exists()
    finally:
        await owner.close()


@pytest.mark.parametrize("entrypoint", ["submit", "plan"])
async def test_plan_write_failure_stops_further_planning_and_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entrypoint: str
) -> None:
    owner = RunCoordinator(tmp_path)
    await owner.open()
    original_plan = coordinator.create_plan
    calls = 0

    async def counted_plan(evaluation: Evaluation) -> Plan:
        nonlocal calls
        calls += 1
        return await original_plan(evaluation)

    def broken_write(*args: Any, **kwargs: Any) -> None:
        raise OSError("private-storage-detail")

    monkeypatch.setattr(coordinator, "create_plan", counted_plan)
    monkeypatch.setattr(coordinator, "atomic_json", broken_write)
    try:
        request = configuration()
        operation = (
            owner.submit(request)
            if entrypoint == "submit"
            else owner.evaluation_plan(request.evaluation)
        )
        with pytest.raises(
            CoordinatorError, match="no agent preflight or load was started"
        ) as failure:
            await operation
        assert failure.value.status_code == 500
        assert "private" not in str(failure.value)
        for operation in [owner.submit(request), owner.evaluation_plan(request.evaluation)]:
            with pytest.raises(CoordinatorError, match="restore storage"):
                await operation
        assert calls == 1
        assert owner.tasks == owner.runs == owner.index == {}
    finally:
        await owner.close()
