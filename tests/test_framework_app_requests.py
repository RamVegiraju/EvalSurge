"""Published App requests through real v2, SDK, Locust, and framework runtimes.

Only SDK discovery/OAuth and provider HTTP are controlled. The loopback fixture
wraps actual LangGraph/OpenAI Agents demo responses in the supported synchronous
invocation envelope. It is not DurableAgentServer, a deployed App, or Lakebase;
these tests establish wiring/fail-fast semantics, not live deployment or capacity.
"""

import asyncio
import json
import os
import socket
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import mlflow
import pytest
import requests
import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from mlflow.tracking import fluent
from mlflow.tracking._tracking_service import utils as tracking_utils

from benchmark_agents import target_resolver
from benchmark_agents.api import create_app
from evalsurge.remote import RemoteClient, RemoteRunFailed
from tests.framework_app_boundary import install_boundary

pytest.importorskip("agents")
pytest.importorskip("langgraph")
from examples import framework_agent as demo

ROOT = Path(__file__).resolve().parents[1]
SERVICE_KEY = "synthetic-app-example-service-key"


@pytest.fixture(autouse=True)
def restore_mlflow_state() -> Iterator[None]:
    """Restore exact native tracking selectors after all provider fixtures tear down.

    Yields:
        Unmodified framework and native MLflow execution during the test.

    A raw ``None`` tracking selector must stay environment-driven; restoring the
    resolved URI instead would leak this test's temporary store to future tests.
    MLflow has no public active-experiment reset API, so preserve its raw state.
    The setter mutates process environment outside monkeypatch; restore absence
    as well as values after monkeypatch's own environment teardown.
    """
    previous_uri = tracking_utils._tracking_uri
    previous_experiment = fluent._active_experiment_id
    selectors = {
        name: os.environ.get(name)
        for name in (
            "MLFLOW_TRACKING_URI",
            "MLFLOW_EXPERIMENT_ID",
            "MLFLOW_EXPERIMENT_NAME",
            "MLFLOW_RUN_ID",
        )
    }
    try:
        yield
    finally:
        mlflow.set_tracking_uri(previous_uri)
        fluent._active_experiment_id = previous_experiment
        for name, value in selectors.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@pytest.fixture
async def framework_invocations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[str, list[dict[str, Any]], str]]:
    """Serve native-shaped invocations around actual framework/model/tool runs.

    Args:
        tmp_path: Test-owned MLflow storage, removed by pytest after this test.
        monkeypatch: Owned environment changes restored by pytest.

    Yields:
        Loopback invocation endpoint, observed HTTP requests, and experiment ID.

    The fixture calls the existing real demo handler via ASGI without mocking
    graph/Runner methods. Only the demo's model-provider response is synthetic.
    Every request runs actual framework tools, memory, and native MLflow tracing.
    The incomplete mode preserves output but rejects the outer lifecycle status.
    """
    for name in list(os.environ):
        if name.startswith(("BENCHMARK_", "DATABRICKS_", "MLFLOW_", "EVALSURGE_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    monkeypatch.setenv("MLFLOW_MODEL_CATALOG_URI", "")
    app = demo.create_app()
    received: list[dict[str, Any]] = []

    @app.post("/api/invocations")
    async def invoke(request: Request) -> JSONResponse:
        """Drain a real framework SSE response into a test-only native envelope."""
        body = await request.json()
        observed = {"body": body, "headers": dict(request.headers)}
        received.append(observed)
        assert body["stream"] is body["background"] is False
        assert UUID(body["id"])
        assert UUID(body["session_id"])
        framework = request.headers["x-test-framework"]
        assert framework in {"langgraph", "openai-agents"}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://framework-fixture"
        ) as client:
            response = await client.post(
                f"/{framework}/chat",
                json={"messages": body["input"]},
                headers={
                    "X-Benchmark-Run-ID": request.headers["x-benchmark-run-id"],
                    "X-Benchmark-Request-ID": body["id"],
                },
            )
        assert response.status_code == 200
        output = ""
        trace_id = None
        terminal = False
        for line in response.text.splitlines():
            if not line.startswith("data: "):
                continue
            if line == "data: [DONE]":
                terminal = True
                continue
            event = json.loads(line.removeprefix("data: "))
            assert "error" not in event
            if event.get("type") == "evalsurge.trace":
                trace_id = event["trace_id"]
            for choice in event.get("choices", []):
                output += choice.get("delta", {}).get("content", "")
        assert terminal and output and trace_id
        observed["output"] = output
        observed["trace_id"] = trace_id
        return JSONResponse(
            {
                "id": body["id"],
                "status": request.headers["x-test-invocation-status"],
                "output": {
                    "status": "completed",
                    "output": [{"role": "assistant", "status": "completed", "content": output}],
                },
            },
            headers={"X-MLflow-Trace-ID": trace_id},
        )

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
                    raise RuntimeError("Framework invocation fixture did not start")
                await asyncio.sleep(0.01)
            else:
                raise TimeoutError("Framework invocation fixture exceeded five seconds")
            async with httpx.AsyncClient(trust_env=False) as client:
                manifest = (await client.get(base_url + "/manifest/langgraph")).json()
            yield base_url + "/api/invocations", received, manifest["trace_experiment_id"]
        finally:
            server.should_exit = True
            await serving
            mlflow.langchain.autolog(disable=True)
            mlflow.openai.autolog(disable=True)


def _install_worker_boundary(
    monkeypatch: pytest.MonkeyPatch,
    *,
    arguments: dict[str, str],
) -> list[tuple[str, ...]]:
    """Contain native SDK/OAuth and HTTP in real production Locust subprocesses.

    Args:
        monkeypatch: Test-owned process launch interception, restored by pytest.
        arguments: Exact synthetic SDK profile/App and loopback destination.

    Returns:
        Original commands, which remain the one standard Locust load engine.

    The bootstrap performs gevent patching before importing SDK HTTP libraries,
    installs only the test provider boundaries, and invokes the actual Locust
    module with all production flags preserved. No engine/task/metrics are mocked.
    """
    original_launch = asyncio.create_subprocess_exec
    commands: list[tuple[str, ...]] = []
    bootstrap = (
        "import gevent.monkey; gevent.monkey.patch_all(); "
        "from tests.framework_app_boundary import install_boundary; "
        f"install_boundary(**{arguments!r}); "
        "import runpy; runpy.run_module('locust', run_name='__main__')"
    )

    async def launch(*command: str, **kwargs: Any) -> asyncio.subprocess.Process:
        """Insert provider controls into the original sole-engine child command."""
        assert command[:3] == (sys.executable, "-m", "locust")
        commands.append(command)
        return await original_launch(sys.executable, "-c", bootstrap, *command[3:], **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    return commands


@pytest.mark.parametrize("framework", ["langgraph", "openai-agents"])
@pytest.mark.parametrize("status", ["completed", "running"])
async def test_published_app_request_runs_real_framework_or_stops_at_probe(
    framework: str,
    status: str,
    framework_invocations: tuple[str, list[dict[str, Any]], str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise each actual JSON fixture through remote SDK/v2 and production Locust."""
    endpoint, observed, experiment_id = framework_invocations
    alias = f"databricks-{framework}"
    request = json.loads((ROOT / "examples" / "requests" / f"{alias}.json").read_text())
    assert request["target"] == {"connection_id": alias}
    assert "evaluation" not in request
    request["load"] = {
        "concurrency": 2,
        "duration_seconds": 5,
        "max_requests": 2,
        "timeout_seconds": 10,
    }
    profile_file = tmp_path / "controlled-profile.ini"
    profile_file.write_text("[controlled-app]\nhost = https://controlled-workspace.invalid\n")
    monkeypatch.setenv("DATABRICKS_CONFIG_FILE", str(profile_file))
    app_name = f"controlled-{framework}"
    origin = f"https://{app_name}.databricksapps.com"
    audit_file = tmp_path / "boundary.jsonl"
    arguments = {
        "profile_file": str(profile_file),
        "app_name": app_name,
        "origin": origin,
        "endpoint": endpoint,
        "audit_file": str(audit_file),
        "framework": framework,
        "invocation_status": status,
    }
    # Install the same real SDK boundary in the parent for deferred App resolution;
    # pytest restores process-local patches, workers exit after their own phases.
    with monkeypatch.context() as parent_patch:
        parent_patch.setattr(target_resolver, "workspace_client", target_resolver.workspace_client)
        parent_patch.setattr(
            requests.adapters.HTTPAdapter, "send", requests.adapters.HTTPAdapter.send
        )
        import databricks.sdk.config

        parent_patch.setattr(
            databricks.sdk.config, "get_host_metadata", databricks.sdk.config.get_host_metadata
        )
        install_boundary(**arguments)
        commands = _install_worker_boundary(parent_patch, arguments=arguments)

        def forbidden(*args: Any, **kwargs: Any) -> None:
            pytest.fail("Default-off requests must not initialize a planner or judge")

        parent_patch.setattr("benchmark_agents.planner.planner_client", forbidden)
        parent_patch.setattr("benchmark_agents.judges.judge_client", forbidden)
        evidence = tmp_path / "evidence"
        operator = tmp_path / "operator.toml"
        operator.write_text(
            f"api_key = {json.dumps(SERVICE_KEY)}\n"
            f"artifact_dir = {json.dumps(str(evidence))}\n"
            f"[connections.{alias}]\n"
            'kind = "databricks-app"\n'
            'profile = "controlled-app"\n'
            f"app_name = {json.dumps(app_name)}\n"
            f"framework = {json.dumps(framework)}\n"
            'protocols = ["databricks-agent-runtime"]\n'
            "[tracing]\nenabled = true\n"
            f"experiment_ids = [{json.dumps(experiment_id)}]\n"
        )

        def execute() -> dict[str, Any]:
            """Own the real ASGI service and borrowed remote HTTP client in a thread."""
            app = create_app(config_path=operator)
            with (
                TestClient(app, client=("127.0.0.1", 50000)) as http,
                RemoteClient("http://127.0.0.1", api_key=SERVICE_KEY, http_client=http) as sdk,
            ):
                assert sdk.capabilities()["targets"] == [
                    {"name": alias, "protocols": ["databricks-agent-runtime"]}
                ]
                handle = sdk.start(request)
                assert UUID(str(handle.id))
                if status == "running":
                    with pytest.raises(RemoteRunFailed) as failure:
                        handle.wait(timeout=30)
                    report = failure.value.report
                else:
                    report = handle.wait(timeout=30)
                assert handle.report() == report
                return report

        report = await asyncio.to_thread(execute)

    run = report["run"]
    serialized = json.dumps(report)
    assert SERVICE_KEY not in serialized and "fixture-" not in serialized
    assert "controlled-app" not in serialized and origin not in serialized
    assert run["summary"]["quality"] == "off"
    assert run["summary"]["sustainable_capacity_established"] is False
    expected = 3 if status == "completed" else 1
    assert len(observed) == expected
    assert len({item["body"]["id"] for item in observed}) == expected
    assert len({item["body"]["session_id"] for item in observed}) == expected
    assert len({item["headers"]["authorization"] for item in observed}) == expected
    for item in observed:
        assert item["output"] == "Opened items cannot be refunded."
        assert item["headers"]["x-benchmark-request-id"] == item["body"]["id"]
        assert item["headers"]["x-routing-key"] == item["body"]["session_id"]
        assert item["headers"]["x-mlflow-return-trace-id"] == "true"
        assert item["body"]["input"] == [
            {"role": "user", "content": request["cases"][0]["input"]["query"]}
        ]
    audit = [json.loads(line) for line in audit_file.read_text().splitlines()]
    assert sum(event["kind"] == "dispatch" for event in audit) == expected
    child_pids = {event["pid"] for event in audit if event["kind"] == "dispatch"}
    assert len(child_pids) == len(commands) == (2 if status == "completed" else 1)
    for pid in child_pids:
        events = [event for event in audit if event["pid"] == pid]
        assert sum(event["kind"] == "discovery" for event in events) == 1
        tokens = [event["counter"] for event in events if event["kind"] == "oauth"]
        dispatches = sum(event["kind"] == "dispatch" for event in events)
        assert tokens == list(range(1, dispatches + 2))
    if status == "running":
        assert run["status"] == "failed"
        assert run["preflight"]["status"] == "failed"
        assert run["preflight"]["error"]["code"] == "invalid_response"
        assert run["phases"]["load"] == run["phases"]["evaluation"] == "skipped"
        assert run["metrics"] is None
        assert report["total"] == 0
    else:
        assert run["status"] == "completed"
        assert run["preflight"]["status"] == "passed"
        assert run["metrics"]["requests"] == run["metrics"]["successful_requests"] == 2
        assert run["metrics"]["timing_successful_only"]["ttft_ms"]["count"] == 0
        assert report["total"] == 2
        assert run["preflight"]["request_id"] not in {
            item["request_id"] for item in report["requests"]
        }
        assert report["profiling"]["coverage"] == 1
        for item in report["requests"]:
            assert {"model", "memory", "tool"} <= {span["category"] for span in item["spans"]}
        recovered = json.loads((evidence / str(run["id"]) / "recovered.json").read_text())
        assert recovered["summary"]["engine"] == "locust"
        assert recovered["summary"]["worker_exit_code"] == 0
        assert {row["outputs"] for row in recovered["rows"]} == {"Opened items cannot be refunded."}
