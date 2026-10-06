"""Regression coverage for frozen plans, representative samples, and API boundaries."""

import asyncio
import json
import os
import signal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from benchmark_agents import api, coordinator
from benchmark_agents.connections import resolve_connection
from benchmark_agents.locust_runner import run_load
from benchmark_agents.models import Evaluation, Target
from benchmark_agents.planner import create_plan
from benchmark_agents.sampling import select_rows
from benchmark_agents.storage import append_event, recover_rows
from tests.test_template import configuration


async def test_sampling_covers_cases_and_late_run():
    config = Evaluation(description="test", scorers=[], max_scored_requests=8)
    plan = await create_plan(config)
    rows = [
        {"request_id": f"{i:03}", "case_id": i % 2, "start_offset_ms": i * 100} for i in range(80)
    ]
    selected, coverage = select_rows(rows, rows, plan)
    repeated, _ = select_rows(list(reversed(rows)), rows, plan)
    assert selected == repeated
    assert coverage["selected_strata"] == coverage["eligible_strata"] == 8
    assert any(r["start_offset_ms"] > 6000 for r in selected)
    assert {r["case_id"] for r in selected} == {0, 1}


def test_journal_recovers_completed_and_partial_lines(tmp_path):
    append_event(tmp_path / "requests.jsonl", {"kind": "started", "row": {"request_id": "a"}})
    append_event(
        tmp_path / "requests.jsonl",
        {"kind": "completed", "row": {"request_id": "b", "success": True}},
    )
    with (tmp_path / "requests.jsonl").open("a") as stream:
        stream.write('{"kind":')
    rows, incomplete = recover_rows(tmp_path)
    assert incomplete == 1
    assert rows[0]["error"] == "WorkerInterrupted"
    assert rows[1]["success"]
    live, _ = recover_rows(tmp_path, interrupted=False)
    assert live[0]["error"] is None and live[0]["record_status"] == "in_flight"


def test_credentials_cannot_be_sent_to_arbitrary_destinations(monkeypatch):
    monkeypatch.setenv(
        "BENCHMARK_CONNECTIONS",
        json.dumps(
            {
                "trusted": {
                    "url": "https://good.example/chat",
                    "auth": "bearer",
                    "token_env": "PRIVATE_KEY",
                }
            }
        ),
    )
    with pytest.raises(ValueError, match="does not match"):
        resolve_connection(Target(url="https://bad.example/chat", connection_id="trusted"))
    with pytest.raises(ValueError, match="requires a server"):
        resolve_connection(Target(url="https://bad.example/chat"))
    with pytest.raises(ValidationError):
        Target(url="https://bad.example/chat", auth_env="PRIVATE_KEY")
    with pytest.raises(ValueError, match="credentials"):
        resolve_connection(Target(url="http://user:password@localhost/chat"))


async def test_locust_authentication_failure_does_not_leak_slots(endpoint, monkeypatch):
    url, server = endpoint
    monkeypatch.delenv("MISSING_TEST_TOKEN", raising=False)
    monkeypatch.setenv(
        "BENCHMARK_CONNECTIONS",
        json.dumps(
            {
                "broken": {
                    "url": url + "/normal",
                    "auth": "bearer",
                    "token_env": "MISSING_TEST_TOKEN",
                }
            }
        ),
    )
    request = configuration(max_requests=5)
    request.target.url = url + "/normal"
    request.target.connection_id = "broken"
    rows, summary = await asyncio.wait_for(run_load(request, str(uuid4()), asyncio.Event()), 15)
    assert len(rows) == 5
    assert summary["incomplete_measurements"] == 0
    assert summary["observed_peak_in_flight"] == server["received"] == 0
    assert all(r["error_phase"] == "authentication" for r in rows)


async def test_locust_killed_worker_preserves_partial_results(endpoint, tmp_path):
    url, server = endpoint
    request = configuration(duration_seconds=30, max_requests=100, concurrency=1)
    request.target.url = url + "/normal"
    run_id = str(uuid4())
    running = asyncio.create_task(run_load(request, run_id, asyncio.Event()))
    for _ in range(1000):
        if server["received"] >= 2:
            break
        await asyncio.sleep(0.01)
    assert server["received"] >= 2
    pid = json.loads((tmp_path / run_id / "worker.json").read_text())["pid"]
    os.kill(pid, signal.SIGKILL)
    rows, summary = await running
    assert any(r["success"] for r in rows)
    assert any(r["error"] == "WorkerInterrupted" for r in rows)
    assert summary["load_status"] == "interrupted"
    assert not summary["measurement_complete"]


def test_plan_reuse_idempotency_and_evaluation_failure(tmp_path, monkeypatch, successful_preflight):
    async def fake_load(*args, **kwargs):
        return [], {"load_status": "completed"}

    monkeypatch.setattr(coordinator, "run_load", fake_load)
    monkeypatch.setattr(coordinator, "evaluate", lambda *args: {"status": "failed"})
    monkeypatch.setenv("BENCHMARK_API_KEY", "test-key")
    monkeypatch.setenv("BENCHMARK_JUDGE_MODEL", "frozen-model")
    app = api.create_app(tmp_path)
    body = configuration().model_dump(mode="json")
    body["evaluation"]["scorers"] = ["relevance"]
    with TestClient(app, client=("127.0.0.1", 50000), headers={"X-API-Key": "test-key"}) as client:
        plan = client.post("/v1/evaluation-plans", json=body["evaluation"]).json()
        monkeypatch.setenv("BENCHMARK_JUDGE_MODEL", "changed-model")
        body["plan_id"] = plan["id"]
        result = client.post("/v1/runs", json=body, headers={"Idempotency-Key": "once"})
        assert result.status_code == 202
        url = result.headers["Location"]
        for _ in range(100):
            run = client.get(url).json()
            if run["status"] == "completed_with_gaps":
                break
        assert run["plan"]["judge_model"] == "frozen-model"
        assert run["load_status"] == "completed" and run["evaluation_status"] == "failed"
        repeat = client.post("/v1/runs", json=body, headers={"Idempotency-Key": "once"})
        assert repeat.json()["id"] == run["id"]
        body["load"]["concurrency"] = 2
        assert (
            client.post("/v1/runs", json=body, headers={"Idempotency-Key": "once"}).status_code
            == 409
        )
        body["evaluation"]["description"] = "different"
        assert client.post("/v1/runs", json=body).status_code == 409
        assert client.get(url + "/requests?limit=101").status_code == 422
        denied = client.get(url, headers={"X-API-Key": "wrong"})
        assert denied.status_code == 401 and denied.json()["error"]["request_id"]
        history = client.get("/v1/runs?status=completed_with_gaps&limit=1").json()
        assert history["total"] == 1 and history["items"][0]["id"] == run["id"]
        assert "config" not in history["items"][0]
    with TestClient(
        api.create_app(tmp_path), client=("127.0.0.1", 50000), headers={"X-API-Key": "test-key"}
    ) as restarted:
        assert restarted.get(url).json()["evaluation_status"] == "failed"


def test_nonloopback_service_requires_authentication(tmp_path, monkeypatch):
    monkeypatch.delenv("BENCHMARK_API_KEY", raising=False)
    with TestClient(api.create_app(tmp_path), client=("192.0.2.1", 50000)) as client:
        response = client.get("/v1/runs")
        assert response.status_code == 403


def test_restart_reads_request_journal(tmp_path):
    request = configuration()
    run_id = str(uuid4())
    root = tmp_path / run_id
    root.mkdir()
    # Exercise recovery independently of any provider call or active worker.
    from benchmark_agents.storage import atomic_json

    atomic_json(
        tmp_path / f"{run_id}.json",
        {
            "id": run_id,
            "status": "running",
            "load_status": "running",
            "evaluation_status": "pending",
            "config": request.model_dump(mode="json"),
        },
    )
    append_event(root / "requests.jsonl", {"kind": "started", "row": {"request_id": "unfinished"}})
    with TestClient(api.create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        result = client.get(f"/v1/runs/{run_id}/requests").json()
        assert result["items"][0]["error"] == "WorkerInterrupted"
        assert (root / "cancel").exists()
