"""Run every user-facing example through real Python, Locust, framework, and MLflow APIs."""

import asyncio
import json
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

from benchmark_agents.models import RunReport
from evalsurge import EvalSurge, RunFailed
from examples.mock_agent import app as mock_agent
from tests.test_evaluation_preflight import install_judge

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_EXAMPLES = {
    "langgraph_benchmark.py": ("langgraph", "langgraph/chat"),
    "openai_agents_benchmark.py": ("openai-agents", "openai-agents/chat"),
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
) -> AsyncIterator[tuple[str, dict[str, int], str]]:
    """Serve the real LangGraph and OpenAI Agents demos with controlled model responses."""
    pytest.importorskip("agents")
    pytest.importorskip("langgraph")
    from examples import framework_agent as framework_demo

    previous_tracking_uri = mlflow.get_tracking_uri()
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    monkeypatch.setenv("MLFLOW_MODEL_CATALOG_URI", "")
    monkeypatch.delenv("MLFLOW_EXPERIMENT_ID", raising=False)
    observed = {"received": 0}
    app = framework_demo.create_app()

    @app.middleware("http")
    async def count_invocations(request: Request, call_next: Any) -> Any:
        if request.url.path.endswith("/chat"):
            observed["received"] += 1
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
    framework_agent: tuple[str, dict[str, int], str],
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
    }
    examples = {path.name for path in (ROOT / "examples").glob("*.py")}
    assert examples == covered, "Add end-to-end coverage and update the example index."
    index = (ROOT / "examples/README.md").read_text()
    assert all(f"]({filename})" in index for filename in covered)
