"""Native MLflow telemetry contracts: no agent, model, judge or provider transport.

Trivial arithmetic handlers exercise real span/context/storage APIs only. Passing
these tests is not live-agent or Databricks App validation.
"""

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import mlflow
import pytest
from mlflow.tracking import MlflowClient
from requests import Response

from benchmark_agents.adapters import failed_response_trace_id
from benchmark_agents.coordinator import RunCoordinator
from benchmark_agents.models import Plan, ProfilingReadinessError, TraceSource
from benchmark_agents.profiling import collect_profiles
from benchmark_agents.run_views import status_view
from benchmark_agents.streaming import consume
from evalsurge.serving import AgentAnswer, InvocationContext, create_app
from evalsurge.tracing import traced_handler


@pytest.fixture
def trace_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, str]]:
    """Own an actual local MLflow store; never configure cloud credentials or providers."""
    previous = mlflow.get_tracking_uri()
    uri = f"sqlite:///{tmp_path}/telemetry.db"
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    mlflow.set_tracking_uri(uri)
    experiment = MlflowClient(tracking_uri=uri).create_experiment("telemetry-contract")
    try:
        yield uri, experiment
    finally:
        mlflow.flush_trace_async_logging()
        mlflow.set_tracking_uri(previous)


def context() -> InvocationContext:
    """Build fresh valid correlation labels without any target invocation."""
    request_id = str(uuid4())
    return InvocationContext(str(uuid4()), request_id, 0, request_id)


def plan(source: TraceSource | None) -> Plan:
    """Construct a load-only frozen policy with no scorer/model configuration."""
    return Plan(
        source="explicit",
        rubric_hash="telemetry-contract",
        dataset_hash="telemetry-contract",
        evaluation_hash="telemetry-contract",
        max_scored_requests=1,
        sampling_seed=42,
        description="Telemetry contract without inference",
        trace_source=source,
        recommendations=[],
    )


async def arithmetic(inputs: dict[str, Any], invocation: InvocationContext) -> AgentAnswer:
    """Execute real non-LLM work; it is deliberately not an agent substitute."""
    with mlflow.start_span("arithmetic", span_type="TOOL") as operation:
        operation.set_inputs(inputs)
        await asyncio.sleep(0)
        output = str(inputs["left"] + inputs["right"])
        operation.set_outputs(output)
    return AgentAnswer(outputs=output)


@pytest.mark.asyncio
async def test_native_correlated_trace_without_evaluation(
    trace_store: tuple[str, str], tmp_path: Path
) -> None:
    """Real trace collection works with zero judges and removes protected raw content."""
    uri, experiment = trace_store
    invocation = context()
    answer = await traced_handler(arithmetic, experiment_id=experiment)(
        {"left": 2, "right": 4}, invocation
    )
    mlflow.flush_trace_async_logging()
    native = MlflowClient(tracking_uri=uri).get_trace(answer.trace_id, display=False)
    assert answer.outputs == "6"
    assert native.info.trace_metadata["evalsurge.run_id"] == invocation.run_id
    assert native.info.trace_metadata["evalsurge.request_id"] == invocation.request_id
    assert {span.name for span in native.data.spans} == {"hosted_agent", "arithmetic"}
    source = TraceSource(tracking_uri=uri, experiment_ids=[experiment])
    row = {
        "request_id": invocation.request_id,
        "case_id": 0,
        "success": True,
        "trace_id": answer.trace_id,
        "latency_ms": 1000,
    }
    coordinator = RunCoordinator(tmp_path / "benchmark")
    error, traces = await coordinator._profiling_readiness(invocation.run_id, plan(source), row)
    assert error is None
    assert traces[invocation.request_id].info.trace_id == answer.trace_id
    path = (
        coordinator.root
        / "preflights"
        / invocation.run_id
        / "readiness-profiles"
        / "profiles"
        / f"{invocation.request_id}.json"
    )
    content = path.read_text()
    assert "arithmetic" in content
    assert '"left"' not in content and '"outputs"' not in content


@pytest.mark.asyncio
async def test_native_concurrent_contexts_do_not_cross_correlate(
    trace_store: tuple[str, str],
) -> None:
    """Actual asynchronous telemetry preserves independent request/root IDs."""
    uri, experiment = trace_store
    invoke = traced_handler(arithmetic, experiment_id=experiment)
    first, second = context(), context()
    answers = await asyncio.gather(
        invoke({"left": 1, "right": 2}, first), invoke({"left": 3, "right": 4}, second)
    )
    mlflow.flush_trace_async_logging()
    assert answers[0].trace_id != answers[1].trace_id
    client = MlflowClient(tracking_uri=uri)
    for invocation, answer in zip((first, second), answers, strict=True):
        trace = client.get_trace(answer.trace_id, display=False)
        assert trace.info.trace_metadata["evalsurge.request_id"] == invocation.request_id


@pytest.mark.asyncio
async def test_native_error_trace_is_retained(trace_store: tuple[str, str]) -> None:
    """An actual handler exception stays an error, not a fabricated successful answer."""
    uri, experiment = trace_store
    captured = []

    async def broken(inputs: dict[str, Any], invocation: InvocationContext) -> AgentAnswer:
        captured.append(mlflow.get_current_active_span().trace_id)
        raise ValueError("protected failure detail")

    with pytest.raises(ValueError, match="protected failure detail"):
        await traced_handler(broken, experiment_id=experiment)({}, context())
    mlflow.flush_trace_async_logging()
    trace = MlflowClient(tracking_uri=uri).get_trace(captured[0], display=False)
    assert trace.data.spans[0].status.status_code.value == "ERROR"


@pytest.mark.asyncio
async def test_missing_or_mismatched_probe_fails_without_evaluation(
    trace_store: tuple[str, str], tmp_path: Path
) -> None:
    """Intentional evidence failure; no model or evaluator is used for this check."""
    uri, experiment = trace_store
    invocation = context()
    answer = await traced_handler(arithmetic, experiment_id=experiment)(
        {"left": 2, "right": 3}, invocation
    )
    source = TraceSource(tracking_uri=uri, experiment_ids=[experiment])
    coordinator = RunCoordinator(tmp_path / "benchmark")
    for trace_id, request_id in ((None, invocation.request_id), (answer.trace_id, str(uuid4()))):
        error, traces = await coordinator._profiling_readiness(
            invocation.run_id,
            plan(source),
            {"request_id": request_id, "success": True, "trace_id": trace_id},
        )
        assert error.code == "trace_readiness_failed"
        assert "Inference completed" in error.message
        assert "load did not start" in error.message
        assert traces == {}


@pytest.mark.asyncio
async def test_unconfigured_tracing_has_no_telemetry_work(tmp_path: Path) -> None:
    """Client-only compatibility makes no trace/model/evaluation call."""
    coordinator = RunCoordinator(tmp_path)
    assert await coordinator._profiling_readiness("run", plan(None), {}) == (None, {})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_boundary_only_trace_is_not_labeled_model_work(
    trace_store: tuple[str, str], tmp_path: Path
) -> None:
    """Native root-only timing remains orchestration, never manufactured model spans."""
    uri, experiment = trace_store

    async def boundary(inputs: dict[str, Any], invocation: InvocationContext) -> AgentAnswer:
        return AgentAnswer(outputs=str(inputs["value"] + 1))

    invocation = context()
    answer = await traced_handler(boundary, experiment_id=experiment)({"value": 1}, invocation)
    summary, traces = collect_profiles(
        [{"request_id": invocation.request_id, "success": True, "trace_id": answer.trace_id}],
        invocation.run_id,
        TraceSource(tracking_uri=uri, experiment_ids=[experiment]),
        tmp_path / "profiles",
    )
    assert summary.traced_requests == 1
    assert len(traces[invocation.request_id].data.spans) == 1
    assert summary.hotspots == []
    assert any("Boundary-only" in note for note in summary.notes)


@pytest.mark.asyncio
async def test_wrong_experiment_is_not_accepted(
    trace_store: tuple[str, str], tmp_path: Path
) -> None:
    """An actual native trace in another experiment is rejected without broad search."""
    uri, experiment = trace_store
    invocation = context()
    answer = await traced_handler(arithmetic, experiment_id=experiment)(
        {"left": 1, "right": 2}, invocation
    )
    coordinator = RunCoordinator(tmp_path / "benchmark")
    error, traces = await coordinator._profiling_readiness(
        invocation.run_id,
        plan(TraceSource(tracking_uri=uri, experiment_ids=["unauthorized-experiment"])),
        {"request_id": invocation.request_id, "success": True, "trace_id": answer.trace_id},
    )
    assert error.code == "trace_readiness_failed"
    assert traces == {}


def test_wrapper_configuration_is_explicit_and_bounded() -> None:
    """Pure validation: no experiment lookup, resource creation or provider call."""
    for experiment_id in ("", "1' OR true", "x" * 129):
        with pytest.raises(ValueError, match="exact existing experiment"):
            traced_handler(arithmetic, experiment_id=experiment_id)


def test_example_is_load_only_and_bounded() -> None:
    """Request construction is inert; it is not proof of live agent/App success."""
    from examples.journeys.local_runner_traced_http_target import request

    config = request()
    assert config.evaluation.mode == "off"
    assert config.load.concurrency == 5
    assert config.load.max_requests == 5


@pytest.mark.asyncio
async def test_http_helper_returns_actual_correlated_trace_header(
    trace_store: tuple[str, str],
) -> None:
    """Exercise real HTTP/MLflow telemetry wiring; arithmetic is not agent inference."""
    uri, experiment = trace_store
    invocation = context()
    app = create_app(traced_handler(arithmetic, experiment_id=experiment), isolation="request")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://telemetry"
    ) as client:
        response = await client.post(
            "/invoke",
            json={"left": 2, "right": 6},
            headers={
                "X-Benchmark-Run-ID": invocation.run_id,
                "X-Benchmark-Request-ID": invocation.request_id,
            },
        )
    assert response.status_code == 200
    trace_id = response.headers["X-MLflow-Trace-ID"]
    assert response.json()["trace_id"] == trace_id
    native = MlflowClient(tracking_uri=uri).get_trace(trace_id, display=False)
    assert native.info.trace_metadata["evalsurge.request_id"] == invocation.request_id


@pytest.mark.asyncio
async def test_disabled_native_tracing_stops_before_handler(
    trace_store: tuple[str, str],
) -> None:
    """Intentional pre-handler failure: never report a native no-op span as real evidence."""
    _uri, experiment = trace_store

    async def forbidden(inputs: dict[str, Any], invocation: InvocationContext) -> AgentAnswer:
        pytest.fail("Disabled tracing must not silently execute the handler")

    with (
        mlflow.tracing.context(enabled=False),
        pytest.raises(RuntimeError, match="Tracing must be enabled"),
    ):
        await traced_handler(forbidden, experiment_id=experiment)({}, context())


def test_trace_failure_preserves_inference_and_independent_phases(tmp_path: Path) -> None:
    """Pure transition/presentation check; no target or provider success is fabricated."""
    coordinator = RunCoordinator(tmp_path)
    run_id, request_id = str(uuid4()), str(uuid4())
    coordinator.runs[run_id] = {
        "id": run_id,
        "status": "preflighting",
        "load_status": "queued",
        "evaluation_status": "pending",
        "preflight": {"status": "passed", "request_id": request_id, "latency_ms": 42.0},
        "profiling_preflight": {"status": "running"},
        "evaluation_preflight": {"status": "skipped"},
    }
    coordinator._fail_profiling_readiness(
        run_id, request_id, ProfilingReadinessError(message="Fixed telemetry readiness guidance.")
    )
    run = coordinator.runs[run_id]
    phases = status_view(run).phases
    assert run["preflight"]["latency_ms"] == 42.0
    assert phases.inference == "passed"
    assert phases.profiling_readiness == "failed"
    assert phases.load == "skipped"
    assert phases.profiling == "failed"
    assert phases.evaluation == "skipped"
    assert run["profiling_preflight"]["error"]["code"] == "trace_readiness_failed"


@pytest.mark.asyncio
async def test_http_error_retains_native_trace_without_returning_exception_content(
    trace_store: tuple[str, str], tmp_path: Path
) -> None:
    """Real failing telemetry retains exact HTTP correlation; no LLM is substituted."""
    uri, experiment = trace_store
    invocation = context()

    async def broken(inputs: dict[str, Any], invocation: InvocationContext) -> AgentAnswer:
        raise ValueError("protected failure detail")

    app = create_app(traced_handler(broken, experiment_id=experiment), isolation="request")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://telemetry"
    ) as client:
        failed, invalid = await asyncio.gather(
            client.post(
                "/invoke",
                json={"value": 1},
                headers={
                    "X-Benchmark-Run-ID": invocation.run_id,
                    "X-Benchmark-Request-ID": invocation.request_id,
                },
            ),
            client.post("/invoke", json={}),
        )
    assert failed.status_code == 502
    assert "protected failure detail" not in failed.text
    assert "X-MLflow-Trace-ID" not in invalid.headers
    received = Response()
    received.status_code = failed.status_code
    received.headers.update(failed.headers)
    trace_id = failed_response_trace_id(received)
    summary, traces = collect_profiles(
        [{"request_id": invocation.request_id, "success": False, "trace_id": trace_id}],
        invocation.run_id,
        TraceSource(tracking_uri=uri, experiment_ids=[experiment]),
        tmp_path / "profiles",
    )
    assert summary.traced_requests == 1
    assert traces[invocation.request_id].data.spans[0].status.status_code.value == "ERROR"
    assert (
        traces[invocation.request_id].info.trace_metadata["evalsurge.request_id"]
        == invocation.request_id
    )


@pytest.mark.parametrize(
    "trace_id", ["", "x" * 129, "trace:/wrong/'unsafe", "trace:/" + "x" * 1024]
)
def test_invalid_error_trace_header_is_not_retained(trace_id: str) -> None:
    """Metadata validation alone makes no invocation and never repairs HTTP failure."""
    received = Response()
    received.status_code = 502
    received.headers["X-MLflow-Trace-ID"] = trace_id
    assert failed_response_trace_id(received) is None
    assert received.status_code == 502


def test_native_uc_identifier_retained_but_scope_fails_without_content_lookup(
    tmp_path: Path,
) -> None:
    """Pure authorization regression: shared UC location is not experiment membership."""
    trace_id = f"trace:/{'c' * 60}.{'s' * 60}.prefix/{'a' * 32}"
    assert len(trace_id) > 128
    assert AgentAnswer(outputs="actual output field", trace_id=trace_id).trace_id == trace_id
    received = Response()
    received.headers["X-MLflow-Trace-ID"] = trace_id
    assert failed_response_trace_id(received) == trace_id
    row = {"first_event_ms": None, "ttft_ms": None, "outputs": "", "output_tokens": None}
    import json

    consume(row, json.dumps({"type": "evalsurge.trace", "trace_id": trace_id}), 1.0)
    assert row["trace_id"] == trace_id

    class ForbiddenLookup:
        def get_trace(self, *args: Any, **kwargs: Any) -> None:
            pytest.fail("Unsupported UC scope must be rejected before reading protected content")

    summary, traces = collect_profiles(
        [{"request_id": "metadata-only", "success": False, "trace_id": trace_id}],
        "run",
        TraceSource(tracking_uri="databricks", experiment_ids=["explicit"]),
        tmp_path / "profiles",
        client=ForbiddenLookup(),
    )
    assert summary.gaps == {"unsupported_scope": 1}
    assert summary.traced_requests == 0
    assert traces == {}


@pytest.mark.asyncio
async def test_helper_will_not_override_databricks_governed_destination(
    trace_store: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pure pre-handler config failure; no workspace credential or model is accessed."""
    _uri, experiment = trace_store
    monkeypatch.setattr(mlflow, "get_tracking_uri", lambda: "databricks://explicit-profile")

    async def forbidden(inputs: dict[str, Any], invocation: InvocationContext) -> AgentAnswer:
        pytest.fail("Governed destination must not be silently overridden before handler work")

    with pytest.raises(RuntimeError, match="will not select legacy storage"):
        await traced_handler(forbidden, experiment_id=experiment)({}, context())
