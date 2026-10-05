"""Production Locust requests through real compiled graphs and OpenAI Agent runners."""

import asyncio
import json
import os
import socket
from uuid import uuid4

import httpx
import mlflow
import pytest
import uvicorn

from benchmark_agents.locust_runner import run_load, run_preflight
from benchmark_agents.models import TraceSource
from benchmark_agents.profiling import collect_profiles
from benchmark_agents.providers import DEFAULT_FM_ENDPOINT
from tests.test_template import configuration

pytest.importorskip("agents")
pytest.importorskip("langgraph")
from examples import framework_agent, framework_e2e
from examples.framework_agent import create_app


@pytest.fixture
def provider_requests():
    """Retain emitted provider bodies for retry and configuration assertions."""
    return []


@pytest.fixture
def provider_control():
    """Control only the model HTTP response, never the agent framework."""
    return {"reject": False}


@pytest.fixture(
    params=[
        "portable",
        "portable-no-usage",
        "portable-missing-usage",
        "portable-null-id",
        "databricks-mini",
    ]
)
async def framework_endpoint(tmp_path, monkeypatch, request, provider_requests, provider_control):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    monkeypatch.delenv("MLFLOW_EXPERIMENT_ID", raising=False)
    monkeypatch.delenv("EVALSURGE_DEMO_TOKEN_PARAMETER", raising=False)
    monkeypatch.delenv("EVALSURGE_DEMO_REASONING_EFFORT", raising=False)
    monkeypatch.setenv(
        "EVALSURGE_DEMO_REQUEST_USAGE", "false" if request.param == "portable-no-usage" else "true"
    )
    original_provider = framework_agent.fixture_provider
    contract = request.param
    provider_control["omit_usage"] = contract == "portable-missing-usage"
    if contract == "databricks-mini":
        resolve_options = framework_agent.demo_chat_options

        def preset_options(**options):
            return resolve_options("databricks", DEFAULT_FM_ENDPOINT, tools=options["tools"])

        monkeypatch.setattr(framework_agent, "demo_chat_options", preset_options)

    def compatible_provider(request: httpx.Request) -> httpx.Response:
        """Check settings at the actual SDK wire boundary, not framework mocks."""
        body = json.loads(request.content)
        provider_requests.append(body)
        assert "parallel_tool_calls" not in body and "store" not in body
        if contract == "portable-no-usage":
            assert "stream_options" not in body
        if contract == "databricks-mini":
            assert body["reasoning_effort"] == ("none" if body.get("tools") else "low")
            assert body["max_completion_tokens"] == 1024
            assert "max_tokens" not in body
        else:
            assert "reasoning_effort" not in body
            assert body["max_tokens"] == 1024
            assert "max_completion_tokens" not in body
        if provider_control["reject"]:
            return httpx.Response(
                400,
                json={"error": {"message": "Unsupported setting", "type": "invalid_request_error"}},
            )
        response = original_provider(request)
        if contract == "portable-null-id":
            for event in response.stream.events:
                event["id"] = None
        if provider_control["omit_usage"]:
            response.stream.events = [
                event for event in response.stream.events if "usage" not in event
            ]
        return response

    monkeypatch.setattr(framework_agent, "fixture_provider", compatible_provider)
    connection = socket.socket()
    connection.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(create_app(), log_level="warning", proxy_headers=False))
    serving = asyncio.create_task(server.serve(sockets=[connection]))
    try:
        for _ in range(500):
            if server.started:
                break
            if serving.done():
                await serving
                pytest.fail("Framework demo failed to start")
            await asyncio.sleep(0.01)
        assert server.started
        yield f"http://127.0.0.1:{connection.getsockname()[1]}"
    finally:
        server.should_exit = True
        await serving
        connection.close()
        mlflow.langchain.autolog(disable=True)
        mlflow.openai.autolog(disable=True)


@pytest.mark.parametrize("framework", ["langgraph", "openai-agents"])
async def test_real_framework_stream_tools_memory_and_correlation(
    framework_endpoint, tmp_path, framework, provider_requests, provider_control
):
    config = configuration(concurrency=2, max_requests=2, timeout_seconds=10, duration_seconds=3)
    config.target.url = f"{framework_endpoint}/{framework}/chat"
    config.target.framework = framework
    config.target.request_usage = False
    run_id = str(uuid4())
    probe = await run_preflight(config, run_id, asyncio.Event(), tmp_path)
    assert probe.status == "passed", probe
    rows, metrics = await run_load(config, run_id, asyncio.Event(), tmp_path)
    assert len(rows) == metrics["successful_requests"] == 2, rows
    assert all(row["ttft_ms"] > row["first_event_ms"] for row in rows)
    assert all(row["outputs"] == "Opened items cannot be refunded." for row in rows)
    if provider_control["omit_usage"] or all(
        "stream_options" not in body for body in provider_requests
    ):
        assert all(row["output_tokens"] is None for row in rows)
    assert len({row["trace_id"] for row in rows}) == 2
    mlflow.flush_trace_async_logging()
    async with httpx.AsyncClient() as client:
        disclosure = (await client.get(f"{framework_endpoint}/manifest/{framework}")).json()
    source = TraceSource(
        tracking_uri=mlflow.get_tracking_uri(),
        experiment_ids=[disclosure["trace_experiment_id"]],
    )
    summary, traces = await asyncio.to_thread(
        collect_profiles, rows, run_id, source, tmp_path / run_id
    )
    assert summary.coverage == 1, summary
    for trace in traces.values():
        names = [span.name for span in trace.data.spans]
        assert "policy_db" in names and "memory.read" in names and "memory.write" in names
        reads = [span for span in trace.data.spans if span.name == "memory.read"]
        assert not reads[0].outputs
        assert any(span.span_type in {"LLM", "CHAT_MODEL"} for span in trace.data.spans)


@pytest.mark.parametrize("framework", ["langgraph", "openai-agents"])
async def test_should_not_retry_or_switch_models_when_provider_rejects(
    framework_endpoint, tmp_path, framework, provider_requests, provider_control
):
    provider_control["reject"] = True
    config = configuration(concurrency=2, max_requests=2, timeout_seconds=10, duration_seconds=3)
    config.target.url = f"{framework_endpoint}/{framework}/chat"
    probe = await run_preflight(config, str(uuid4()), asyncio.Event(), tmp_path)
    assert probe.status == "failed" and probe.error.code == "invalid_stream"
    assert len(provider_requests) == 1
    provider_requests.clear()
    rows, metrics = await run_load(config, str(uuid4()), asyncio.Event(), tmp_path)
    assert len(rows) == 2 and metrics["successful_requests"] == 0
    assert len(provider_requests) == 2
    assert all(body["model"] == "fixture" for body in provider_requests)
    assert all(not row["success"] and not row["outputs"] for row in rows)


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        ("fixture", DEFAULT_FM_ENDPOINT),
        ("openai-compatible", DEFAULT_FM_ENDPOINT),
        ("databricks", DEFAULT_FM_ENDPOINT + "-unverified"),
        ("databricks", "unknown-model"),
    ],
)
def test_should_omit_reasoning_when_provider_model_pair_is_unverified(provider, model):
    """A similar model name on a different transport must not inherit a preset."""
    assert framework_agent.demo_chat_options(provider, model, tools=True) == {"max_tokens": 1024}
    assert framework_agent.demo_chat_options(
        provider,
        model,
        tools=True,
        token_parameter="max_completion_tokens",
        reasoning_effort="high",
    ) == {"max_completion_tokens": 1024, "reasoning_effort": "high"}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"reasoning_effort": "low"}, "function tools require"),
        ({"reasoning_effort": "invalid"}, "Unsupported demo reasoning"),
        ({"token_parameter": "max_tokens"}, "requires max_completion_tokens"),
        ({"token_parameter": "unbounded"}, "Demo token parameter"),
    ],
)
def test_should_reject_invalid_or_known_incompatible_demo_settings(overrides, message):
    """Fail before inference rather than negotiating by repeated paid requests."""
    with pytest.raises(ValueError, match=message):
        framework_agent.demo_chat_options(
            "databricks", DEFAULT_FM_ENDPOINT, tools=True, **overrides
        )


@pytest.mark.parametrize(("value", "expected"), [(None, True), ("true", True), ("false", False)])
def test_demo_usage_setting_is_explicit(value, expected):
    assert framework_agent.demo_request_usage(value) is expected


@pytest.mark.parametrize("value", ["", "False", "0", "unknown"])
def test_demo_usage_setting_rejects_invalid_configuration(value):
    with pytest.raises(ValueError, match="true or false"):
        framework_agent.demo_request_usage(value)


@pytest.mark.parametrize(
    ("planner", "judge", "expected_planner", "expected_judge"),
    [
        (None, None, "target", "target"),
        ("planner", "judge", "planner", "judge"),
        (None, "judge", "target", "judge"),
    ],
)
def test_live_example_keeps_model_roles_explicit(
    monkeypatch, planner, judge, expected_planner, expected_judge
):
    for name in (
        "DATABRICKS_CONFIG_PROFILE",
        "BENCHMARK_PLANNER_MODEL",
        "BENCHMARK_JUDGE_MODEL",
        "BENCHMARK_LLM_PROVIDER",
    ):
        monkeypatch.setenv(name, "previous-value")
    framework_e2e.configure_live_models("confirmed-profile", "target", planner, judge)
    assert os.environ["DATABRICKS_CONFIG_PROFILE"] == "confirmed-profile"
    assert os.environ["BENCHMARK_PLANNER_MODEL"] == expected_planner
    assert os.environ["BENCHMARK_JUDGE_MODEL"] == expected_judge


def test_live_example_requires_confirmed_profile_before_configuration(monkeypatch):
    monkeypatch.setenv("DATABRICKS_CONFIG_PROFILE", "existing-profile")
    with pytest.raises(ValueError, match="confirmed"):
        framework_e2e.configure_live_models(None, "target", "planner", "judge")
    assert os.environ["DATABRICKS_CONFIG_PROFILE"] == "existing-profile"
