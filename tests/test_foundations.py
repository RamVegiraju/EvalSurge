"""Regression tests for interrupted storage and public error behavior."""

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from benchmark_agents import api, coordinator
from benchmark_agents.planner import PlannerResponseError, fingerprint
from benchmark_agents.storage import append_event, atomic_json, recover_rows
from tests.test_template import configuration


def test_should_accept_readme_sample_as_performance_only_request() -> None:
    """Check the direct v2 golden path without invoking a planner or model."""
    from tests.test_readme import _readme_request

    config = _readme_request()
    assert config.evaluation.mode == "off"
    assert config.cases and config.load.max_requests == 10
    assert config.target.connection_id == "agent"


def test_recovery_survives_torn_multibyte_and_bad_shapes(tmp_path):
    journal = tmp_path / "requests.jsonl"
    append_event(journal, {"kind": "completed", "row": {"request_id": "valid", "outputs": "yes"}})
    with journal.open("ab") as stream:
        stream.write(b'[]\n{"kind":"completed","row":null}\n{"outputs":"\xe2\x80')
    rows, incomplete = recover_rows(tmp_path)
    assert rows == [{"request_id": "valid", "outputs": "yes"}]
    assert incomplete == 0


def test_common_errors_and_headers(tmp_path, monkeypatch):
    async def invalid_plan(*args):
        raise PlannerResponseError("private-upstream-output")

    monkeypatch.setattr(coordinator, "create_plan", invalid_plan)
    app = api.create_app(tmp_path)

    @app.get("/crash")
    async def crash():
        raise RuntimeError("private-error")

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        responses = [
            client.get("/unknown"),
            client.put("/v1/runs"),
            client.get("/crash"),
            client.post("/v1/evaluation-plans", json={"description": "valid"}),
        ]
    assert [response.status_code for response in responses] == [404, 405, 500, 502]
    for response in responses:
        assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "private" not in response.text


@pytest.mark.parametrize("legacy_usage_default", [False, True])
def test_restart_idempotency_matches_recovered_get(tmp_path, legacy_usage_default):
    body = configuration().model_dump(mode="json")
    persisted_body = json.loads(json.dumps(body))
    if legacy_usage_default:
        persisted_body["target"].pop("request_usage")
    run_id = str(uuid4())
    atomic_json(
        tmp_path / f"{run_id}.json",
        {
            "id": run_id,
            "status": "running",
            "load_status": "running",
            "evaluation_status": "pending",
            "config": body,
            "idempotency_key_hash": fingerprint("once"),
            "request_hash": fingerprint(persisted_body),
        },
    )
    with TestClient(api.create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        response = client.post("/v1/runs", json=body, headers={"Idempotency-Key": "once"})
        without_usage = json.loads(json.dumps(body))
        without_usage["target"]["request_usage"] = False
        conflict = client.post("/v1/runs", json=without_usage, headers={"Idempotency-Key": "once"})
    assert response.status_code == 202
    assert response.json()["status"] == "interrupted"
    assert response.headers["Retry-After"] == "1"
    assert conflict.status_code == 409
    assert json.loads((tmp_path / f"{run_id}.json").read_text())["status"] == "running"
