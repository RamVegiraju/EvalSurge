"""Run every user-facing example through real Python, Locust, framework, and MLflow APIs."""

import ast
import asyncio
import json
import os
import re
import socket
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import mlflow
import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from benchmark_agents.api import create_app
from benchmark_agents.models import RunReport
from benchmark_agents.v2_models import Report, RunCreate
from evalsurge import EvalSurge, RunFailed
from evalsurge.cli import main as cli_main
from evalsurge.remote import RemoteClient, RemoteRunFailed
from examples.mock_agent import app as mock_agent
from tests.test_evaluation_preflight import install_judge

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_EXAMPLES = {
    "langgraph_benchmark.py": ("langgraph", "langgraph/chat"),
    "openai_agents_benchmark.py": ("openai-agents", "openai-agents/chat"),
}
LOCAL_REQUEST_EXAMPLES = {
    "local-langgraph.json": ("local-langgraph", "langgraph/chat"),
    "local-openai-agents.json": ("local-openai-agents", "openai-agents/chat"),
}


@pytest.fixture
async def sample_agent() -> AsyncIterator[tuple[str, dict[str, int]]]:
    """Serve the actual credential-free sample agent and count invocations."""
    app = FastAPI()
    observed = {"received": 0}
    app.mount("/", mock_agent)

    @app.middleware("http")
    async def count_invocations(request: Request, call_next: Any) -> Any:
        observed["received"] += 1
        return await call_next(request)

    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{connection.getsockname()[1]}/chat"
        server = uvicorn.Server(
            uvicorn.Config(app, log_level="warning", proxy_headers=False, access_log=False)
        )
        serving = asyncio.create_task(server.serve(sockets=[connection]))
        try:
            for _ in range(100):
                if server.started:
                    break
                if serving.done():
                    await serving
                    raise RuntimeError("Sample agent did not start")
                await asyncio.sleep(0.01)
            else:
                raise TimeoutError("Sample agent did not start within one second")
            yield url, observed
        finally:
            server.should_exit = True
            await serving


@pytest.fixture
async def framework_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[str, dict[str, Any], str]]:
    """Serve the real LangGraph and OpenAI Agents demos with controlled model responses."""
    pytest.importorskip("agents")
    pytest.importorskip("langgraph")
    from examples import framework_agent as framework_demo

    previous_tracking_uri = mlflow.get_tracking_uri()
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    monkeypatch.setenv("MLFLOW_MODEL_CATALOG_URI", "")
    monkeypatch.delenv("MLFLOW_EXPERIMENT_ID", raising=False)
    observed: dict[str, Any] = {"received": 0, "provider_messages": [], "request_ids": []}
    original_provider = framework_demo.fixture_provider

    def capture_provider(request: httpx.Request) -> httpx.Response:
        """Observe real framework conversations or deny the controlled provider boundary."""
        observed["provider_messages"].append(json.loads(request.content)["messages"])
        if observed.get("provider_failure"):
            return httpx.Response(401, json={"error": {"message": "private provider failure"}})
        return original_provider(request)

    monkeypatch.setattr(framework_demo, "fixture_provider", capture_provider)
    app = framework_demo.create_app()

    @app.middleware("http")
    async def count_invocations(request: Request, call_next: Any) -> Any:
        if request.url.path.endswith("/chat"):
            observed["received"] += 1
            observed["request_ids"].append(request.headers.get("X-Benchmark-Request-ID"))
        return await call_next(request)

    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        base_url = f"http://127.0.0.1:{connection.getsockname()[1]}"
        server = uvicorn.Server(
            uvicorn.Config(app, log_level="warning", proxy_headers=False, access_log=False)
        )
        serving = asyncio.create_task(server.serve(sockets=[connection]))
        try:
            for _ in range(500):
                if server.started:
                    break
                if serving.done():
                    await serving
                    raise RuntimeError("Framework agent did not start")
                await asyncio.sleep(0.01)
            else:
                raise TimeoutError("Framework agent did not start within five seconds")
            async with httpx.AsyncClient(trust_env=False) as client:
                disclosure = (await client.get(f"{base_url}/manifest/langgraph")).json()
            yield base_url, observed, disclosure["trace_experiment_id"]
        finally:
            server.should_exit = True
            await serving
            mlflow.langchain.autolog(disable=True)
            mlflow.openai.autolog(disable=True)
            mlflow.set_tracking_uri(previous_tracking_uri)


def _example_source(filename: str, target_url: str, artifact_dir: Path) -> tuple[Path, str]:
    """Load a published script while changing only test-owned runtime settings."""
    path = ROOT / "examples" / filename
    source = path.read_text()
    default_url = (
        "http://127.0.0.1:9001/chat"
        if filename == "python_benchmark.py"
        else f"http://127.0.0.1:9001/{FRAMEWORK_EXAMPLES[filename][1]}"
    )
    assert f'Agent.http("{default_url}")' in source
    assert "argparse" not in source
    source = source.replace(default_url, target_url)
    source, count = re.subn(r'artifact_dir="[^"]+"', f"artifact_dir={str(artifact_dir)!r}", source)
    assert count == 1
    source, count = re.subn(r"duration_seconds=\d+", "duration_seconds=1", source)
    assert count == 1
    source, count = re.subn(r"max_requests=[\d_]+", "max_requests=2", source)
    assert count == 1
    return path, source


def _execute(path: Path, source: str) -> None:
    """Execute one synchronous tutorial entry point in its own namespace."""
    exec(compile(source, str(path), "exec"), {"__name__": "__main__"})


def _printed_report(output: str) -> RunReport:
    """Parse the final JSON report after any native MLflow progress output."""
    match = re.search(r'(?m)^\{\n  "run":', output)
    assert match is not None, output
    return RunReport.model_validate_json(output[match.start() :])


@pytest.mark.parametrize("mode", ["normal", "denied"])
async def test_mock_python_example_runs_or_surfaces_preflight_failure(
    mode: str,
    endpoint: tuple[str, dict[str, int]],
    sample_agent: tuple[str, dict[str, int]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercise the credential-free Python quickstart and its inference guard."""
    base_url, server = endpoint
    target_url = f"{base_url}/{mode}"
    if mode == "normal":
        target_url, server = sample_agent
    path, source = _example_source("python_benchmark.py", target_url, tmp_path / "benchmark")
    monkeypatch.setattr(sys, "argv", [str(path)])

    if mode == "denied":
        with pytest.raises(RunFailed) as failure:
            await asyncio.to_thread(_execute, path, source)
        report = failure.value.report
        assert report.run.preflight.status == "failed"
        assert report.run.load_status == report.run.evaluation_status == "skipped"
        assert report.run.metrics == {}
        assert server["received"] == 1
        assert "private provider failure" not in str(failure.value)
    else:
        await asyncio.to_thread(_execute, path, source)
        report = _printed_report(capsys.readouterr().out)
        assert report.run.status == "completed"
        assert report.run.metrics["successful_requests"] == report.run.metrics["requests"] == 2
        assert report.run.evaluation_status == "no_ready_scorers"
        assert report.run.config.evaluation.scorers == []
        assert server["received"] == 3
    with EvalSurge.local(artifact_dir=tmp_path / "benchmark") as client:
        assert client.report(report.run.id) == report


@pytest.mark.parametrize("filename", FRAMEWORK_EXAMPLES)
async def test_framework_python_example_produces_load_evaluation_and_profiles(
    filename: str,
    framework_agent: tuple[str, dict[str, Any], str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Run each published framework sample against its actual SDK implementation."""
    base_url, observed, experiment_id = framework_agent
    framework, path_suffix = FRAMEWORK_EXAMPLES[filename]
    artifact_dir = tmp_path / f"{framework}-benchmark"
    path, source = _example_source(filename, f"{base_url}/{path_suffix}", artifact_dir)
    monkeypatch.setattr(sys, "argv", [str(path)])
    monkeypatch.setenv("BENCHMARK_TRACE_ENABLED", "true")
    monkeypatch.setenv("BENCHMARK_TRACE_EXPERIMENT_IDS", json.dumps([experiment_id]))
    previous_tracking_uri = mlflow.get_tracking_uri()
    judge_calls = install_judge(tmp_path, monkeypatch)

    try:
        await asyncio.to_thread(_execute, path, source)
        report = _printed_report(capsys.readouterr().out)
        assert report.run.status == "completed"
        assert report.run.preflight.status == report.run.evaluation_preflight.status == "passed"
        assert report.run.metrics["successful_requests"] == report.run.metrics["requests"] == 2
        assert report.run.evaluation["status"] == "completed"
        results = report.run.evaluation["results"]
        assert {result["scorer"] for result in results} == {"relevance", "correctness"}
        assert all(result["scored"] == 2 and result["judge_errors"] == 0 for result in results)
        assert all(result["pass_rate"] == 0 for result in results)
        assert len(judge_calls) == 6
        assert observed["received"] == 3
        assert report.profiling.coverage == 1
        for request_profile in report.requests:
            categories = {span.category for span in request_profile.spans}
            assert {"tool", "model", "memory"} <= categories
        with EvalSurge.local(artifact_dir=artifact_dir) as client:
            assert client.report(report.run.id) == report
    finally:
        mlflow.set_tracking_uri(previous_tracking_uri)


def _bounded_local_request(filename: str) -> dict[str, Any]:
    """Copy a published request without ever executing its three-minute traffic budget.

    Args:
        filename: Covered local framework request fixture under examples/requests.

    Returns:
        Validated default-off workload reduced to two measured attempts, two
        concurrent users, five seconds of dispatch, and ten-second HTTP deadlines.
        Published files are not modified and no credentials are resolved.
    """
    body = json.loads((ROOT / "examples" / "requests" / filename).read_text())
    assert "evaluation" not in body
    body["load"].update(concurrency=2, duration_seconds=5, max_requests=2, timeout_seconds=10)
    RunCreate.model_validate(body)
    return body


def _framework_api_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    alias: str,
    target_url: str,
) -> Path:
    """Create one test-owned registered target without ambient operator configuration.

    Args:
        tmp_path: Test-owned directory for the private config and evidence.
        monkeypatch: Restores ambient settings after the test.
        alias: Published connection identifier selected by the API caller.
        target_url: Actual ephemeral framework server URL selected by the operator.

    Returns:
        TOML path binding the alias to OpenAI Chat SSE. Tracing settings remain
        disabled here; actual agent MLflow instrumentation continues to execute.
    """
    for name in list(os.environ):
        if name.startswith(("BENCHMARK_", "DATABRICKS_", "EVALSURGE_")):
            monkeypatch.delenv(name)
    path = tmp_path / "framework-operator.toml"
    path.write_text(
        f"artifact_dir = {json.dumps(str(tmp_path / 'v2-evidence'))}\n"
        f"[connections.{alias}]\n"
        f"url = {json.dumps(target_url)}\n"
        'protocols = ["openai-chat"]\n',
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("filename", LOCAL_REQUEST_EXAMPLES)
@pytest.mark.parametrize("entrypoint", ["sdk", "cli"])
async def test_local_framework_request_runs_real_v2_pipeline_with_isolated_memory(
    filename: str,
    entrypoint: str,
    framework_agent: tuple[str, dict[str, Any], str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Execute published requests through REST, the SDK/CLI, and real framework streams."""
    base_url, observed, _ = framework_agent
    alias, suffix = LOCAL_REQUEST_EXAMPLES[filename]
    body = _bounded_local_request(filename)
    assert body["target"] == {"connection_id": alias}
    config = _framework_api_configuration(
        tmp_path, monkeypatch, alias=alias, target_url=f"{base_url}/{suffix}"
    )

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Omitted evaluation must not initialize a planner or judge")

    monkeypatch.setattr("benchmark_agents.planner.planner_client", forbidden)
    monkeypatch.setattr("benchmark_agents.judges.judge_client", forbidden)

    def execute() -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Keep synchronous API/client ownership off the real target's event loop."""
        app = create_app(config_path=config)
        with (
            TestClient(app, client=("127.0.0.1", 50000)) as http,
            EvalSurge.remote("http://127.0.0.1", http_client=http, poll_interval=0.01) as sdk,
        ):
            if entrypoint == "sdk":
                handle = sdk.start(body)
                report = handle.wait(timeout=30)
                identifier = str(handle.id)
            else:
                request_file = tmp_path / "bounded-request.json"
                request_file.write_text(json.dumps(body), encoding="utf-8")

                def client_factory(*args: Any, **kwargs: Any) -> RemoteClient:
                    """Borrow the actual API transport without replacing CLI behavior."""
                    return RemoteClient(*args, **kwargs, http_client=http)

                assert (
                    cli_main(
                        ["run", str(request_file), "--wait", "--timeout", "30"],
                        client_factory=client_factory,
                    )
                    == 0
                )
                identifier = next(iter(app.state.coordinator.index))
                report = sdk.report(identifier)
            Report.model_validate(report)
            result = sdk.result(identifier)
            assert result["summary"]["performance"] == "complete"
            assert result["summary"]["quality"] == "off"
            assert result["summary"]["sustainable_capacity_established"] is False
            assert result["phases"] == {
                "planning": "completed",
                "inference": "passed",
                "profiling_readiness": "skipped",
                "evaluation_readiness": "skipped",
                "load": "completed",
                "profiling": "completed",
                "evaluation": "no_ready_scorers",
            }
            rows = http.get(f"/v1/runs/{identifier}/requests").json()["items"]
            return report, rows

    report, rows = await asyncio.to_thread(execute)
    assert report["run"]["status"] == "completed"
    assert report["total"] == report["run"]["metrics"]["successful_requests"] == 2
    assert report["run"]["metrics"]["requests"] == 2
    assert all(request["status"] == "disabled" for request in report["requests"])
    assert observed["received"] == 3  # one excluded probe, then two measured attempts
    assert len(set(observed["request_ids"])) == 3
    assert len(rows) == 2
    for row in rows:
        assert row["outputs"] == "Opened items cannot be refunded."
        assert row["success"] is True
        assert 0 <= row["first_event_ms"] < row["ttft_ms"] <= row["latency_ms"]
        assert row["trace_id"]
    # Inspect actual model inputs: neither real framework sees another request's
    # transcript, even when the same workload case is reused by concurrent users.
    for messages in observed["provider_messages"]:
        user_messages = [message for message in messages if message["role"] == "user"]
        assert len(user_messages) == 1
        assert user_messages[0]["content"] == body["cases"][0]["input"]["query"]
    assert len(observed["provider_messages"]) == (3 if alias == "local-langgraph" else 6)
    if entrypoint == "cli":
        output = capsys.readouterr()
        assert "accepted" in output.out and "completed" in output.out
        assert body["cases"][0]["input"]["query"] not in output.out


@pytest.mark.parametrize("filename", LOCAL_REQUEST_EXAMPLES)
async def test_local_framework_request_fails_fast_at_real_provider_boundary(
    filename: str,
    framework_agent: tuple[str, dict[str, Any], str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real SDK provider denial causes one excluded probe and zero measured attempts."""
    base_url, observed, _ = framework_agent
    alias, suffix = LOCAL_REQUEST_EXAMPLES[filename]
    body = _bounded_local_request(filename)
    observed["provider_failure"] = True
    config = _framework_api_configuration(
        tmp_path, monkeypatch, alias=alias, target_url=f"{base_url}/{suffix}"
    )

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Performance-only failure must not initialize a planner or judge")

    monkeypatch.setattr("benchmark_agents.planner.planner_client", forbidden)
    monkeypatch.setattr("benchmark_agents.judges.judge_client", forbidden)

    def execute() -> dict[str, Any]:
        """Retain the API failure report without blocking framework request servicing."""
        with (
            TestClient(create_app(config_path=config), client=("127.0.0.1", 50000)) as http,
            EvalSurge.remote("http://127.0.0.1", http_client=http, poll_interval=0.01) as sdk,
        ):
            with pytest.raises(RemoteRunFailed) as failure:
                sdk.start(body).wait(timeout=30)
            assert "private provider failure" not in str(failure.value)
            return failure.value.report

    report = await asyncio.to_thread(execute)
    assert report["run"]["status"] == "failed"
    assert report["run"]["preflight"]["status"] == "failed"
    assert report["run"]["phases"]["load"] == "skipped"
    assert report["run"]["phases"]["evaluation"] == "skipped"
    assert report["run"]["metrics"] is None
    assert report["total"] == 0
    assert observed["received"] == len(observed["provider_messages"]) == 1


@pytest.mark.parametrize("filename", FRAMEWORK_EXAMPLES)
async def test_framework_example_surfaces_inference_preflight_failure(
    filename: str,
    endpoint: tuple[str, dict[str, int]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure either framework tutorial stops before load and judging on bad inference."""
    base_url, observed = endpoint
    path, source = _example_source(filename, f"{base_url}/denied", tmp_path / "benchmark")
    monkeypatch.setattr(sys, "argv", [str(path)])
    previous_tracking_uri = mlflow.get_tracking_uri()
    judge_calls = install_judge(tmp_path, monkeypatch)

    try:
        with pytest.raises(RunFailed) as failure:
            await asyncio.to_thread(_execute, path, source)
        report = failure.value.report
        assert report.run.preflight.status == "failed"
        assert report.run.load_status == report.run.evaluation_status == "skipped"
        assert report.run.metrics == {}
        assert observed["received"] == 1
        assert judge_calls == []
        assert "private provider failure" not in str(failure.value)
    finally:
        mlflow.set_tracking_uri(previous_tracking_uri)


@pytest.mark.parametrize("filename", FRAMEWORK_EXAMPLES)
@pytest.mark.parametrize("failure", ["401", "invalid"])
async def test_framework_example_stops_load_when_judge_readiness_fails(
    filename: str,
    failure: str,
    sample_agent: tuple[str, dict[str, int]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Surface native judge readiness errors before measured agent requests."""
    target_url, observed = sample_agent
    path, source = _example_source(filename, target_url, tmp_path / "benchmark")
    monkeypatch.setattr(sys, "argv", [str(path)])
    previous_tracking_uri = mlflow.get_tracking_uri()
    judge_calls = install_judge(tmp_path, monkeypatch, failure=failure)

    try:
        with pytest.raises(RunFailed) as error:
            await asyncio.to_thread(_execute, path, source)
        report = error.value.report
        assert report.run.preflight.status == "passed"
        assert report.run.evaluation_preflight.status == "failed"
        assert report.run.load_status == "skipped"
        assert report.run.evaluation_status == "failed"
        assert report.run.metrics == {}
        assert observed["received"] == 1
        assert len(judge_calls) == 1
        assert "private-provider-text" not in str(error.value)
    finally:
        mlflow.set_tracking_uri(previous_tracking_uri)


def test_example_index_links_resolve() -> None:
    """Keep the example and validation indexes navigable after moving helper scripts."""
    for directory in ("examples", "scripts/validation"):
        index = ROOT / directory / "README.md"
        for destination in re.findall(r"\]\(([^)]+)\)", index.read_text()):
            if destination.startswith(("https://", "http://")):
                continue
            assert (index.parent / destination.split("#", 1)[0]).is_file(), destination


def test_minimal_examples_are_safe_to_import() -> None:
    """Importing a tutorial must not start a benchmark or resolve provider credentials."""
    for filename in ("python_benchmark.py", *FRAMEWORK_EXAMPLES):
        path = ROOT / "examples" / filename
        namespace = {"__name__": "example_import"}
        exec(compile(path.read_text(), str(path), "exec"), namespace)
        assert callable(namespace["main"])
        assert "run" not in namespace
        assert "report" not in namespace


@pytest.mark.parametrize("filename", ["python_benchmark.py", *FRAMEWORK_EXAMPLES])
def test_tutorial_rejects_cli_flags_before_starting_a_run(
    filename: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stale or misspelled CLI flags must not silently load the default target."""
    path = ROOT / "examples" / filename
    monkeypatch.setattr(sys, "argv", [str(path), "--url", "https://wrong.example/chat"])

    def unexpected_run(*args: Any, **kwargs: Any) -> None:
        """Fail if argument rejection reaches any storage or execution boundary."""
        pytest.fail("Unexpected benchmark admission")

    monkeypatch.setattr(EvalSurge, "local", unexpected_run)
    with pytest.raises(SystemExit, match="CLI flags"):
        exec(compile(path.read_text(), str(path), "exec"), {"__name__": "__main__"})


def test_every_user_example_has_an_explicit_integration_contract() -> None:
    """Require new examples to extend the tested inventory rather than silently bypass CI."""
    covered = {
        "python_benchmark.py",
        "langgraph_benchmark.py",
        "openai_agents_benchmark.py",
        "mock_agent.py",
        "framework_agent.py",
        "real_framework_agent.py",
        "real_framework_handler.py",
        "crewai_agent.py",
    }
    examples = {path.name for path in (ROOT / "examples").glob("*.py")}
    assert examples == covered, "Add end-to-end coverage and update the example index."
    index = (ROOT / "examples/README.md").read_text()
    assert all(f"]({filename})" in index for filename in covered)


def test_journey_sources_have_named_non_inference_contract_coverage() -> None:
    """Inventory nested samples without claiming successful live integration.

    This test reads filenames/documentation only. The named modules validate
    source/configuration/lifecycle boundaries, not model inference, deployment,
    independent-worker credentials or successful cloud benchmarks.
    """
    covered = {
        "classic_notebook.py": "test_unified_journey_examples.py",
        "direct_app.py": "test_unified_journey_examples.py",
        "direct_http.py": "test_unified_journey_examples.py",
        "local_runner_databricks_app_target.py": "test_unified_journey_examples.py",
        "local_runner_http_target.py": "test_unified_journey_examples.py",
        "local_runner_traced_http_target.py": "test_load_only_tracing.py",
        "multitool_heatmap/agent.py": "test_simple_examples.py",
        "multitool_heatmap/handler.py": "test_simple_examples.py",
        "multitool_heatmap/runner.py": "test_simple_examples.py",
        "framework_runner_matrix.py": "test_framework_runner_matrix.py",
        "serverless_runner_databricks_app_target.py": "test_serverless_notebook_examples.py",
        "serverless_runner_http_target.py": "test_serverless_notebook_examples.py",
        "app_runner/app.py": "test_app_direct_runner_example.py",
        "app_runner/runner.py": "test_app_direct_runner_example.py",
        "agent_apps/shared/native_agent.py": "test_native_agent_app_examples.py",
        "agent_apps/stage_shared_sources.py": "test_native_agent_app_examples.py",
        "agent_apps/langgraph/app.py": "test_native_agent_app_examples.py",
        "agent_apps/openai_agents/app.py": "test_native_agent_app_examples.py",
        "agent_apps/crewai/app.py": "test_native_agent_app_examples.py",
    }
    source_root = ROOT / "examples" / "journeys"
    sources = {str(path.relative_to(source_root)) for path in source_root.rglob("*.py")}
    assert sources == set(covered), "Declare coverage and live gaps for new journey sources."
    assert all((ROOT / "tests" / filename).is_file() for filename in covered.values())
    plan = (ROOT / "docs" / "RUNNER_TARGET_VALIDATION.md").read_text()
    assert "fifteen" in plan and "15" in plan
    assert "Listed samples are not automatically successful live runs" in plan


def test_multitool_heatmap_request_bounds_and_non_inference_inputs() -> None:
    """Construct the public request and reject inputs without agent/model execution."""
    from examples.journeys.multitool_heatmap.handler import validate_inputs
    from examples.journeys.multitool_heatmap.runner import request

    run = request()
    assert run.evaluation.mode == "off"
    assert run.load.concurrency == 5
    assert run.load.duration_seconds == 10
    assert run.load.max_requests == 4
    assert run.load.timeout_seconds == 40
    assert [case.input["scenario"] for case in run.cases] == ["delayed", "normal"]
    assert all(case.input["order_id"] == "DEMO-42" for case in run.cases)
    for case in run.cases:
        validate_inputs(case.input)
    assert all(not case.reference for case in run.cases)
    assert "profile" not in run.model_dump_json()
    assert "tracking_uri" not in run.model_dump_json()


@pytest.mark.parametrize(
    "update",
    [
        {"scenario": "unknown"},
        {"scenario": []},
        {"order_id": "another-order"},
        {"query": " "},
        {"query": "x" * 513},
        {"query": None},
        {"extra": "not-declared"},
    ],
)
def test_multitool_heatmap_rejects_inputs_before_inference(update: dict[str, Any]) -> None:
    """Actual input validation only; intentional pre-provider failure, no stub/client."""
    from examples.journeys.multitool_heatmap.handler import validate_inputs

    inputs = {"query": "Can I return this?", "order_id": "DEMO-42", "scenario": "normal"}
    with pytest.raises(ValueError, match="Unsupported demonstration input"):
        validate_inputs({**inputs, **update})


def test_multitool_heatmap_declared_data_and_serial_source_contract() -> None:
    """Inspect synthetic documents/AST without constructing or executing the graph.

    This is a no-inference source/data contract, not an end-to-end agent test.
    The real-model trace/report record in VALIDATION.md is separate evidence.
    """
    directory = ROOT / "examples/journeys/multitool_heatmap"
    orders = json.loads((directory / "orders.json").read_text())
    policies = json.loads((directory / "policies.json").read_text())
    assert orders["DEMO-42"]["category"] in policies
    assert orders["DEMO-42"]["days_since_purchase"] <= policies["electronics"]["return_window_days"]
    assert not orders["DEMO-42"]["opened"]

    tree = ast.parse((directory / "handler.py").read_text())
    tool_names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "trace":
            options = {item.arg: ast.literal_eval(item.value) for item in node.keywords}
            if options.get("span_type") == "TOOL":
                tool_names.add(options["name"])
    assert tool_names == {"lookup_order", "lookup_return_policy", "quote_return_shipping"}
    edges = {
        tuple(arg.value if isinstance(arg, ast.Constant) else arg.id for arg in node.args)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_edge"
    }
    assert edges == {
        ("START", "order"),
        ("order", "policy"),
        ("policy", "shipping"),
        ("shipping", "decision"),
        ("decision", "answer"),
        ("answer", "END"),
    }
    runner_tree = ast.parse((directory / "runner.py").read_text())
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module in {"handler", ".handler"}
        for node in ast.walk(runner_tree)
    )
    agent_source = (directory / "agent.py").read_text()
    assert "flush_trace_async_logging" not in agent_source
    assert "max_retries=0" in agent_source
    assert 'host="127.0.0.1"' in agent_source
    assert "attempts >= 5" in agent_source


def test_multitool_heatmap_documented_viewer_contract_and_links() -> None:
    """Check source/docs wiring for the existing viewer without starting any server."""
    directory = ROOT / "examples/journeys/multitool_heatmap"
    readme = (directory / "README.md").read_text()
    for relative in re.findall(r"\]\((\.\./[^)]+)\)", readme):
        assert (directory / relative).resolve().is_file(), relative
    assert "benchmark_agents.api:app" in readme
    assert "BENCHMARK_ARTIFACT_DIR=/absolute/private/demo/benchmark" in readme
    assert "--host 127.0.0.1 --port 9003 --no-proxy-headers" in readme
    assert "BENCHMARK_CONFIG" in readme and "BENCHMARK_API_KEY" in readme
    api_tree = ast.parse((ROOT / "benchmark_agents/api.py").read_text())
    assert any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "app" for target in node.targets)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "create_app"
        for node in api_tree.body
    )
    runner_tree = ast.parse((directory / "runner.py").read_text())
    main = next(
        node
        for node in runner_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    execution = next(index for index, node in enumerate(main.body) if isinstance(node, ast.With))
    post_execution_strings = [
        node.value
        for statement in main.body[execution + 1 :]
        for node in ast.walk(statement)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert any("Run ID:" in value for value in post_execution_strings)
    assert any("http://127.0.0.1:9003/reports/?run=" in value for value in post_execution_strings)
    # Source-only ownership/exit contract; this does not simulate agent lifecycle.
    assert any(
        isinstance(node, ast.ExceptHandler)
        and isinstance(node.type, ast.Name)
        and node.type.id == "RunFailed"
        for node in ast.walk(main.body[execution])
    )
    assert any(
        isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
        and node.exc.func.id == "SystemExit"
        and len(node.exc.args) == 1
        and isinstance(node.exc.args[0], ast.Constant)
        and node.exc.args[0].value == 1
        for statement in main.body[execution + 1 :]
        for node in ast.walk(statement)
    )


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_multitool_heatmap_export_configuration_without_lifespan(mode: str) -> None:
    """Construct configuration only; no client/auth/exporter/agent/inference runs."""
    from examples.journeys.multitool_heatmap.agent import create_tool_app
    from examples.real_framework_handler import ModelSelection

    selection = ModelSelection(
        "explicit-profile", "explicit-model", "mlflow-responses", "https://workspace.example"
    )
    before = os.environ.get("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING")
    app = create_tool_app(
        selection, "sqlite:////absolute/private/traces.sqlite", "1", trace_export=mode
    )
    assert app.state.trace_export == mode
    assert os.environ.get("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING") == before


def test_multitool_heatmap_invalid_export_rejected_before_lifespan() -> None:
    """Reject an invalid policy before native clients or export initialization."""
    from examples.journeys.multitool_heatmap.agent import create_tool_app
    from examples.real_framework_handler import ModelSelection

    selection = ModelSelection(
        "explicit-profile", "explicit-model", "mlflow-responses", "https://workspace.example"
    )
    with pytest.raises(ValueError, match="Select trace export as sync or async"):
        create_tool_app(
            selection, "sqlite:////absolute/private/traces.sqlite", "1", trace_export="other"
        )
