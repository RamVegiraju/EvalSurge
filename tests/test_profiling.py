"""Validate span timing math, correlation, bounded collection, and report contracts."""

from types import SimpleNamespace

import httpx
import mlflow
import pytest
from fastapi.testclient import TestClient

from benchmark_agents import api, coordinator
from benchmark_agents.models import Evaluation, TraceSource
from benchmark_agents.planner import create_plan
from benchmark_agents.profiling import collect_profiles, normalize_trace
from benchmark_agents.storage import atomic_json
from tests.test_report_ui import render
from tests.test_template import configuration


def span(identifier, parent, start, stop, kind="CHAIN"):
    return SimpleNamespace(
        span_id=identifier,
        parent_id=parent,
        start_time_ns=int(start * 1e6),
        end_time_ns=int(stop * 1e6),
        name=identifier,
        span_type=kind,
        attributes={},
        status=SimpleNamespace(status_code="OK"),
    )


def row(identifier="request"):
    return {
        "request_id": identifier,
        "case_id": 0,
        "success": True,
        "latency_ms": 120.0,
        "trace_id": "trace",
    }


def test_parallel_occupancy_and_child_union():
    trace = SimpleNamespace(
        info=SimpleNamespace(trace_id="trace"),
        data=SimpleNamespace(
            spans=[
                span("root", None, 0, 100),
                span("model", "root", 10, 50, "LLM"),
                span("tool", "root", 20, 60, "TOOL"),
            ]
        ),
    )
    profile = normalize_trace(trace, row())
    assert profile.agent_duration_ms == 100
    assert profile.client_minus_agent_ms == 20
    assert sum(profile.occupancy_ms.values()) == 100
    assert profile.occupancy_ms == {
        "model": 10,
        "tool": 10,
        "retrieval": 0,
        "memory": 0,
        "orchestration": 50,
        "parallel": 30,
    }
    assert profile.spans[0].self_ms == 50
    trace.data.spans[2].parent_id = "model"
    trace.data.spans[2].end_time_ns = int(30 * 1e6)
    profile = normalize_trace(trace, row())
    assert profile.occupancy_ms["parallel"] == 0
    assert profile.spans[1].self_ms == 30
    trace.data.spans[2].parent_id = "tool"
    with pytest.raises(ValueError, match="ancestry"):
        normalize_trace(trace, row())


def test_actual_mlflow_correlation_scope_and_budget(tmp_path, monkeypatch):
    uri = f"sqlite:///{tmp_path}/mlflow.db"
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    mlflow.set_tracking_uri(uri)
    experiment = mlflow.set_experiment("profiling-tests")
    with mlflow.start_span("agent", span_type="AGENT") as root:
        mlflow.update_current_trace(
            metadata={"evalsurge.run_id": "run", "evalsurge.request_id": "request"}
        )
        with mlflow.start_span("policy_db", span_type="TOOL") as tool:
            tool.set_inputs({"secret": "private"})
            tool.set_outputs("private-tool-output")
    mlflow.flush_trace_async_logging()
    source = TraceSource(tracking_uri=uri, experiment_ids=[experiment.experiment_id], max_traces=1)
    valid = {**row(), "trace_id": root.trace_id}
    wrong = {**valid, "request_id": "other"}
    summary, traces = collect_profiles([valid, wrong], "run", source, tmp_path / "run")
    assert summary.traced_requests == 1
    assert summary.gaps == {"budget": 1}
    assert traces["request"].info.trace_id == root.trace_id
    content = (tmp_path / "run" / "profiles" / "request.json").read_text()
    assert "policy_db" in content and "private" not in content and "secret" not in content
    summary, _ = collect_profiles([wrong], "run", source, tmp_path / "mismatch")
    assert summary.gaps == {"scope_mismatch": 1}
    summary, _ = collect_profiles([valid], "run", None, tmp_path / "disabled")
    assert summary.traced_requests == 0 and summary.gaps == {"disabled": 1}


def test_report_pagination_and_shell_auth(tmp_path, monkeypatch, successful_preflight):
    async def fake_load(*args, **kwargs):
        return [row("first"), row("second")], {"load_status": "completed"}

    monkeypatch.setattr(coordinator, "run_load", fake_load)
    monkeypatch.setenv("BENCHMARK_API_KEY", "test-key")
    app = api.create_app(tmp_path)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        assert client.get("/reports/").status_code == 200
        assert "test-key" not in client.get("/reports/").text
        assert client.get("/v1/runs").status_code == 401
        client.headers["X-API-Key"] = "test-key"
        response = client.post("/v1/runs", json=configuration().model_dump(mode="json"))
        run_url = response.headers["Location"]
        for _ in range(200):
            response = client.get(run_url + "/report?offset=1&limit=1")
            if response.status_code == 200:
                break
        data = response.json()
        assert data["requests"][0]["request_id"] == "second"
        assert data["requests"][0]["occupancy_ms"] == {}
        assert data["profiling"]["coverage"] == 0
        ui = render(data)
        assert "No quality criteria" in ui["nodes"]["suggestions"]["text"]
        assert "Internal time is unknown" in ui["nodes"]["waterfall-note"]["text"]
        assert client.get(run_url + "/report?limit=101").status_code == 422


async def test_chunked_body_limit(tmp_path):
    async def body():
        yield b'{"description":"'
        for _ in range(9):
            yield b"x" * 1_000_000
        yield b'","scorers":[]}'

    app = api.create_app(tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50000)),
        base_url="http://localhost",
    ) as client:
        response = await client.post(
            "/v1/evaluation-plans", content=body(), headers={"content-type": "application/json"}
        )
    assert response.status_code == 413
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


async def test_trace_source_frozen_at_planning(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCHMARK_TRACE_ENABLED", "true")
    monkeypatch.setenv("BENCHMARK_TRACE_EXPERIMENT_IDS", '["1"]')
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/tracking.db")
    plan = await create_plan(Evaluation(description="Performance only", scorers=[]))
    monkeypatch.setenv("BENCHMARK_TRACE_EXPERIMENT_IDS", '["2"]')
    atomic_json(tmp_path / "plan.json", plan.model_dump())
    assert plan.trace_source.experiment_ids == ["1"]
