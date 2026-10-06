"""Public Python entry points exercise the same coordinator and Locust as REST."""

import asyncio
import os
import threading
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from benchmark_agents.coordinator import CoordinatorError
from benchmark_agents.models import ProfilingSummary, RunRequest, RunResponse, Target
from benchmark_agents.planner import validate_plan
from benchmark_agents.storage import atomic_json
from evalsurge import Agent, Connection, EvalSurge, Evaluation, Load, RunFailed, Sample


async def test_local_async_json_report_and_idempotency(endpoint, tmp_path: Path) -> None:
    base, server = endpoint
    agent = Agent.http(base + "/json", protocol="http-json")
    cases = [Sample(inputs={"query": "Can I refund?", "context": {"tenant": "demo"}})]
    async with EvalSurge.local_async(artifact_dir=tmp_path) as client:
        run = await client.start(
            agent=agent,
            cases=cases,
            load=Load(concurrency=2, duration_seconds=5, max_requests=3),
            idempotency_key="json-once",
        )
        report = await run.wait(timeout=30)
        assert report.run.status == "completed"
        assert report.run.preflight.status == "passed"
        assert report.run.metrics["requests"] == 3
        assert report.run.metrics["timing_successful_only"]["ttft_ms"]["count"] == 0
        assert report.run.metrics["timing_successful_only"]["ttft_ms"]["p50"] is None
        assert report.run.metrics["token_usage_coverage"] == 1
        assert report.total == 3
        assert report.profiling.traced_requests == 0
        assert report.run.config.evaluation.scorers == []
        assert report.run.config.evaluation.registered_scorers == []
        assert server["received"] == 4
        assert server["bodies"] == [cases[0].inputs] * 4
        replay = await client.start(
            agent=agent,
            cases=cases,
            load=Load(concurrency=2, duration_seconds=5, max_requests=3),
            idempotency_key="json-once",
        )
        assert replay.id == run.id
        assert server["received"] == 4


@pytest.mark.parametrize(
    "mode",
    ["json-empty", "json-type", "json-malformed", "json-list", "json-bad-usage", "json-large"],
)
async def test_json_failed_preflight_raises_with_safe_report(endpoint, tmp_path, mode) -> None:
    base, server = endpoint
    async with EvalSurge.local_async(artifact_dir=tmp_path) as client:
        run = await client.start(
            agent=Agent.http(base + "/" + mode, protocol="http-json"),
            cases=[Sample(inputs={"query": "probe"})],
            load=Load(max_requests=3, duration_seconds=5),
        )
        with pytest.raises(RunFailed, match="Load test did not start") as failure:
            await run.wait(timeout=30)
        assert failure.value.report.run.load_status == "skipped"
        assert failure.value.report.run.preflight.error.code == "invalid_response"
        assert "private" not in str(failure.value)
        assert server["received"] == 1
        assert (await run.report()).total == 0


async def test_sync_client_does_not_nest_event_loop(endpoint, tmp_path, monkeypatch) -> None:
    base, server = endpoint
    monkeypatch.setenv("BENCHMARK_CONNECTIONS", "unused-invalid-json")
    before = {name: value for name, value in os.environ.items() if name.startswith("BENCHMARK_")}

    def benchmark() -> None:
        with EvalSurge.local(artifact_dir=tmp_path) as client:
            run = client.start(
                agent=Agent.http(base + "/normal"),
                cases=[Sample(inputs={"query": "probe"})],
                load=Load(max_requests=1, duration_seconds=5),
            )
            with pytest.raises(TimeoutError):
                run.wait(timeout=0.001)
            report = run.wait(timeout=30)
            assert report.run.preflight.status == "passed"
            assert report.run.metrics["successful_requests"] == 1
            assert run.report() == report
            assert report.run.config.evaluation.scorers == []
            assert report.run.config.evaluation.registered_scorers == []

    await asyncio.to_thread(benchmark)
    assert server["received"] == 2
    assert {
        name: value for name, value in os.environ.items() if name.startswith("BENCHMARK_")
    } == before


def test_agent_connection_and_target_are_detached_and_exact(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "private-secret")
    connection = Connection(url="https://agent.example/api", auth="bearer", token_env="AGENT_TOKEN")
    agent = Agent.http(
        connection.url,
        model="provider-independent-model",
        request_usage=False,
        connection=connection,
    )
    connection.url = "https://other.example/api"
    connection.token_env = "OTHER_TOKEN"
    agent.connection.url = "https://mutated.example/api"
    agent.target.model = "mutated"
    assert agent.target.model == "provider-independent-model"
    assert agent.target.request_usage is False
    assert agent.connection.url == "https://agent.example/api"
    assert agent.connection.token_env == "AGENT_TOKEN"
    assert "private-secret" not in agent.connection.model_dump_json() + repr(agent)
    with pytest.raises(ValueError, match="does not match"):
        Agent.http("https://agent.example/api", connection=connection)
    with pytest.raises(ValueError, match="String should match pattern"):
        Agent.http(
            "https://agent.example/api",
            connection=agent.connection.model_copy(update={"auth": "unsupported"}),
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@agent.example/api",
        "https://agent.example/api?token=private",
        "https://agent.example/api#private",
        "http://agent.example/api",
        "file:///private/agent",
    ],
)
def test_agent_rejects_unsafe_url_bindings(url: str) -> None:
    with pytest.raises(ValueError):
        Agent.http(url)


@pytest.mark.parametrize("protocol", ["openai-chat", "mlflow-agent-server", "http-json"])
def test_agent_keeps_protocol_separate_from_connection(protocol: str) -> None:
    agent = Agent.http("http://127.0.0.1:9001/invoke", protocol=protocol)
    assert agent.target.adapter == protocol
    assert agent.connection.auth == "none"
    assert agent.connection.url == str(agent.target.url)


async def test_start_rejects_conflicting_evaluation_without_admission(tmp_path: Path) -> None:
    cases = [Sample(inputs={"query": "probe"}, expectations={"expected_response": "yes"})]
    async with EvalSurge.local_async(artifact_dir=tmp_path) as client:
        for conflicting in [
            [Sample(inputs={"query": "different"})],
            [Sample(inputs={"query": "probe"}, expectations={"expected_response": "no"})],
        ]:
            with pytest.raises(ValueError, match="evaluation.samples must match cases"):
                await client.start(
                    agent=Agent.http("http://127.0.0.1:9001/chat"),
                    cases=cases,
                    load=Load(max_requests=1),
                    evaluation=Evaluation(description="opt-in", samples=conflicting),
                )
        assert list(tmp_path.glob("*.json")) == []
        assert not (tmp_path / "plans").exists()


@pytest.mark.parametrize(
    "bad_cases", [[], "not-cases", [{}], [Sample(inputs={"query": "x"})] * 1001]
)
async def test_start_validates_cases_before_admission(tmp_path, bad_cases) -> None:
    async with EvalSurge.local_async(artifact_dir=tmp_path) as client:
        with pytest.raises((TypeError, ValueError)):
            await client.start(
                agent=Agent.http("http://127.0.0.1:9001/chat"),
                cases=bad_cases,
                load=Load(max_requests=1),
            )
        assert list(tmp_path.glob("*.json")) == []


async def test_start_copies_mutable_inputs_and_accepts_matching_samples(endpoint, tmp_path) -> None:
    base, server = endpoint
    original = Sample(
        inputs={"query": "original", "context": {"tenant": "original"}},
        expectations={"expected_facts": ["original"]},
    )
    cases = [original]
    evaluation = Evaluation(
        description="explicit performance-only",
        samples=cases,
        scorers=[],
        registered_scorers=[],
    )
    load = Load(max_requests=1, duration_seconds=5)
    async with EvalSurge.local_async(artifact_dir=tmp_path) as client:
        run = await client.start(
            agent=Agent.http(base + "/json", protocol="http-json"),
            cases=cases,
            evaluation=evaluation,
            load=load,
        )
        original.inputs["context"]["tenant"] = "changed"
        original.expectations["expected_facts"].append("changed")
        original.inputs["query"] = "changed"
        cases.append(Sample(inputs={"query": "changed"}))
        evaluation.description = "changed"
        load.max_requests = 3
        report = await run.wait(timeout=30)
        assert report.run.config.load.max_requests == 1
        assert report.run.config.evaluation.description == "explicit performance-only"
        saved = report.run.config.evaluation.samples
        assert len(saved) == 1
        assert saved[0].inputs == {"query": "original", "context": {"tenant": "original"}}
        assert saved[0].expectations == {"expected_facts": ["original"]}
        assert server["received"] == 2
        assert server["bodies"] == [saved[0].inputs] * 2
        report.run.config.evaluation.samples[0].inputs["query"] = "altered report"
        assert (await run.report()).run.config.evaluation.samples[0].inputs["query"] == "original"
        assert (await run.report(offset=1, limit=1)).requests == []
        with pytest.raises(CoordinatorError, match="Page requires"):
            await run.report(limit=101)


async def test_wait_timeout_and_waiter_cancellation_leave_run_active(endpoint, tmp_path) -> None:
    base, server = endpoint
    async with EvalSurge.local_async(artifact_dir=tmp_path) as client:
        run = await client.start(
            agent=Agent.http(base + "/normal"),
            cases=[Sample(inputs={"query": "probe"})],
            load=Load(max_requests=1, duration_seconds=5),
        )
        with pytest.raises(TimeoutError):
            await run.wait(timeout=0.001)
        waiter = asyncio.create_task(run.wait())
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert (await run.wait(timeout=30)).run.status == "completed"
        assert server["received"] == 2


async def test_cancel_preflight_returns_safe_failure_and_no_load(endpoint, tmp_path) -> None:
    base, server = endpoint
    async with EvalSurge.local_async(artifact_dir=tmp_path) as client:
        run = await client.start(
            agent=Agent.http(base + "/slow"),
            cases=[Sample(inputs={"query": "probe"})],
            load=Load(max_requests=3, duration_seconds=5),
        )
        for _ in range(400):
            if server["active"]:
                break
            await asyncio.sleep(0.01)
        assert server["active"] == 1
        assert (await run.cancel()).status == "cancellation_requested"
        with pytest.raises(RunFailed, match="cancelled") as failure:
            await run.wait(timeout=30)
        assert failure.value.report.run.load_status == "skipped"
        assert failure.value.report.total == 0
        assert server["received"] == 1
        assert (await run.report()).run.status == "cancelled"


async def test_context_ownership_lock_and_failed_sync_startup_cleanup(tmp_path) -> None:
    before = {thread.ident for thread in threading.enumerate() if thread.name == "evalsurge-local"}
    async with EvalSurge.local_async(artifact_dir=tmp_path):
        with pytest.raises(OSError):
            async with EvalSurge.local_async(artifact_dir=tmp_path):
                pytest.fail("Storage ownership must be exclusive")
        with pytest.raises(OSError), EvalSurge.local(artifact_dir=tmp_path):
            pytest.fail("Sync and async clients must use the same storage lock")
    after = {thread.ident for thread in threading.enumerate() if thread.name == "evalsurge-local"}
    assert after == before
    with EvalSurge.local(artifact_dir=tmp_path):
        pass


async def test_async_client_rejects_other_loop_and_closed_misuse(tmp_path) -> None:
    client = EvalSurge.local_async(artifact_dir=tmp_path)
    run_id = uuid4()
    with pytest.raises(RuntimeError, match="not open"):
        await client.report(run_id)
    async with client:

        def wrong_loop() -> None:
            with pytest.raises(RuntimeError, match="different event loop"):
                asyncio.run(client.report(run_id))

        await asyncio.to_thread(wrong_loop)
        with pytest.raises(RuntimeError, match="more than once"):
            await client.__aenter__()
    await client.close()
    with pytest.raises(RuntimeError, match="not open"):
        await client.wait(run_id)
    with pytest.raises(RuntimeError, match="more than once"):
        await client.__aenter__()


def test_sync_client_rejects_closed_misuse_and_cannot_reopen(tmp_path) -> None:
    client = EvalSurge.local(artifact_dir=tmp_path)
    with pytest.raises(RuntimeError, match="not open"):
        client.report(uuid4())
    with client, pytest.raises(RuntimeError, match="more than once"):
        client.__enter__()
    client.close()
    with pytest.raises(RuntimeError, match="not open"):
        client.wait(uuid4())
    with pytest.raises(RuntimeError, match="more than once"):
        client.__enter__()


def test_sync_shutdown_defers_interrupt_until_its_operation_drains(tmp_path, monkeypatch) -> None:
    dispatched = asyncio.run_coroutine_threadsafe
    state = {"interrupted": False, "drained": False}

    def interrupt_waiter(coroutine, loop):
        future = dispatched(coroutine, loop)
        result = future.result

        def interrupted_result(timeout=None):
            if not state["interrupted"]:
                state["interrupted"] = True
                raise KeyboardInterrupt
            return result(timeout)

        monkeypatch.setattr(future, "result", interrupted_result)
        return future

    async def drain() -> None:
        await asyncio.sleep(0.05)
        state["drained"] = True

    with EvalSurge.local(artifact_dir=tmp_path) as client:
        monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", interrupt_waiter)
        with pytest.raises(KeyboardInterrupt):
            client._call(drain, defer_interrupts=True)
        assert state == {"interrupted": True, "drained": True}


async def test_cancelled_async_close_drains_and_releases_storage(endpoint, tmp_path) -> None:
    base, server = endpoint
    client = EvalSurge.local_async(artifact_dir=tmp_path)
    await client.__aenter__()
    try:
        run = await client.start(
            agent=Agent.http(base + "/slow"),
            cases=[Sample(inputs={"query": "probe"})],
            load=Load(max_requests=3, duration_seconds=5),
        )
        for _ in range(400):
            if server["active"]:
                break
            await asyncio.sleep(0.01)
        assert server["active"] == 1
        closing = asyncio.create_task(client.close())
        await asyncio.sleep(0)
        closing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await closing
        assert server["active"] == 0
        assert server["received"] == 1
        with pytest.raises(RuntimeError, match="not open"):
            await run.report()
        async with EvalSurge.local_async(artifact_dir=tmp_path) as reopened:
            assert (await reopened.report(run.id)).run.status == "cancelled"
        assert server["received"] == 1
    finally:
        await client.close()


def terminal_run(directory: Path, status: str) -> UUID:
    """Persist a real coordinator report fixture without target or provider calls."""
    evaluation = Evaluation(
        description="performance-only",
        samples=[Sample(inputs={"query": "private caller text"})],
        scorers=[],
        registered_scorers=[],
    )
    run_id = uuid4()
    request = RunRequest(
        target=Target(url="http://127.0.0.1:9001/chat"),
        evaluation=evaluation,
        load=Load(max_requests=1),
    )
    plan = validate_plan(evaluation, [], "explicit")
    response = RunResponse(
        id=str(run_id),
        status=status,
        load_status="completed" if status == "completed_with_gaps" else status,
        evaluation_status="completed_with_gaps" if status == "completed_with_gaps" else "skipped",
        config=request,
        plan=plan,
        trace_coverage="No internal traces",
    )
    atomic_json(directory / f"{run_id}.json", response.model_dump(mode="json"))
    atomic_json(
        directory / str(run_id) / "profiling.json",
        ProfilingSummary(total_requests=0, traced_requests=0, coverage=0).model_dump(),
    )
    return run_id


@pytest.mark.parametrize("status", ["failed", "interrupted", "cancelled", "completed_with_gaps"])
async def test_wait_recovered_terminal_report_preserves_status_and_safe_errors(
    tmp_path: Path, status: str
) -> None:
    run_id = terminal_run(tmp_path, status)
    async with EvalSurge.local_async(artifact_dir=tmp_path) as client:
        if status == "completed_with_gaps":
            report = await client.wait(run_id)
            assert report.run.status == status
        else:
            with pytest.raises(RunFailed, match=status) as failure:
                await client.wait(run_id)
            assert failure.value.report.run.status == status
            assert "private caller text" not in str(failure.value)
            failure.value.report.run.config.evaluation.description = "mutated exception"
        assert (await client.report(run_id)).run.config.evaluation.description == "performance-only"
        with pytest.raises(ValueError, match="positive finite seconds"):
            await client.wait(run_id, timeout=float("nan"))
        with pytest.raises(CoordinatorError, match="not in a cancellable"):
            await client.cancel(run_id)


@pytest.mark.parametrize("status", ["failed", "interrupted", "cancelled", "completed_with_gaps"])
async def test_sync_terminal_wait_runs_from_an_existing_event_loop(tmp_path, status) -> None:
    run_id = terminal_run(tmp_path, status)
    with EvalSurge.local(artifact_dir=tmp_path) as client:
        if status == "completed_with_gaps":
            assert client.wait(run_id).run.status == status
        else:
            with pytest.raises(RunFailed, match=status) as failure:
                client.wait(run_id)
            assert failure.value.report.run.status == status
            assert "private caller text" not in str(failure.value)
        assert client.report(run_id).run.status == status


@pytest.mark.parametrize("phase", ["evaluation_preflight", "load_error"])
async def test_python_wait_surfaces_safe_readiness_and_worker_guidance(
    tmp_path: Path, phase: str
) -> None:
    """Terminal typed reports and raised errors retain corrective phase-specific guidance."""
    run_id = terminal_run(tmp_path, "failed")
    path = tmp_path / f"{run_id}.json"
    snapshot = RunResponse.model_validate_json(path.read_text()).model_dump(mode="json")
    error = {
        "code": "judge_authentication_failed"
        if phase == "evaluation_preflight"
        else "worker_start_failed",
        "message": "The readiness or worker check failed.",
        "guidance": "Review the operator-owned configuration.",
    }
    snapshot["preflight"] = {"status": "passed"}
    snapshot[phase] = (
        {"status": "failed", "error": error} if phase == "evaluation_preflight" else error
    )
    atomic_json(path, snapshot)
    async with EvalSurge.local_async(artifact_dir=tmp_path) as client:
        with pytest.raises(RunFailed, match=error["guidance"]) as failure:
            await client.wait(run_id)
        assert error["message"] in str(failure.value)
        assert "private caller text" not in str(failure.value)
        assert failure.value.report.run.preflight.status == "passed"
        observed = failure.value.report.run.model_dump(mode="json")
        assert observed[phase] == (await client.report(run_id)).run.model_dump(mode="json")[phase]
