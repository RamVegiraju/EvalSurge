"""Fail-fast inference regressions through the real API and Locust worker."""

import asyncio
import json
import os
import signal
import socket
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from benchmark_agents import api, coordinator
from benchmark_agents.locust_runner import preflight_result, run_load, run_preflight
from benchmark_agents.storage import append_event, atomic_json
from tests.test_template import configuration


async def submit_and_wait(
    client: httpx.AsyncClient, body: dict[str, Any], key: str = "once"
) -> tuple[str, dict[str, Any]]:
    """Submit and poll a bounded local run, without any paid providers.

    Args:
        client: Local API transport whose lifespan is owned by the test.
        body: Synthetic run configuration with explicit scorers.
        key: Submission replay key, reused only with the same body.

    Returns:
        Polling URL and terminal run snapshot.

    Raises:
        AssertionError: Submission fails or the run exceeds the polling bound.
    """
    accepted = await client.post("/v1/runs", json=body, headers={"Idempotency-Key": key})
    assert accepted.status_code == 202, accepted.text
    url = accepted.headers["Location"]
    for _ in range(400):
        response = await client.get(url)
        response.raise_for_status()
        run = response.json()
        if run["status"] in {
            "completed",
            "completed_with_gaps",
            "failed",
            "cancelled",
            "interrupted",
        }:
            return url, run
        await asyncio.sleep(0.05)
    raise AssertionError("Local run did not terminate")


@pytest.mark.parametrize(
    "mode,timeout,code",
    [
        ("denied", 1, "authentication_failed"),
        ("redirect", 1, "target_http_error"),
        ("provider_error", 1, "invalid_stream"),
        ("empty", 1, "invalid_stream"),
        ("filtered", 1, "invalid_stream"),
        ("malformed", 1, "invalid_stream"),
        ("wrong_content_type", 1, "invalid_stream"),
        ("truncated", 1, "invalid_stream"),
        ("slow", 0.2, "target_timeout"),
    ],
)
async def test_failed_inference_stops_before_load_and_returns_safe_report(
    endpoint: tuple[str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    timeout: float,
    code: str,
) -> None:
    base_url, server = endpoint
    monkeypatch.setattr(
        coordinator, "evaluate", lambda *args, **kwargs: pytest.fail("Judging must not run")
    )
    monkeypatch.setattr(
        coordinator, "run_load", lambda *args, **kwargs: pytest.fail("Load must not run")
    )
    body = configuration(timeout_seconds=timeout).model_dump(mode="json")
    body["target"]["url"] = base_url + "/" + mode
    app = api.create_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50000)),
            base_url="http://test",
        ) as client,
    ):
        url, run = await submit_and_wait(client, body)
        assert run["status"] == "failed"
        assert (
            run["load_status"] == run["evaluation_status"] == run["profiling_status"] == "skipped"
        )
        assert run["preflight"]["status"] == "failed"
        assert run["preflight"]["error"]["code"] == code
        assert run["preflight"]["request_id"]
        assert "Load test did not start" in run["preflight"]["error"]["message"]
        assert "private" not in json.dumps(run)
        assert run["metrics"] == {}
        assert server["received"] == 1
        records = (await client.get(url + "/requests")).json()
        assert records["total"] == 0
        report = await client.get(url + "/report")
        assert report.status_code == 200
        assert report.json()["run"]["preflight"] == run["preflight"]
        assert report.json()["profiling"]["total_requests"] == report.json()["total"] == 0
        repeated = await client.post("/v1/runs", json=body, headers={"Idempotency-Key": "once"})
        assert repeated.json()["id"] == run["id"]
        assert repeated.json()["status"] == "failed"
        assert server["received"] == 1


@pytest.mark.parametrize(
    "adapter,mode", [("openai-chat", "normal"), ("mlflow-agent-server", "responses")]
)
async def test_passed_preflight_is_one_extra_first_case_and_excluded_from_measurements(
    endpoint: tuple[str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    adapter: str,
    mode: str,
) -> None:
    base_url, server = endpoint
    evaluated: list[list[dict[str, Any]]] = []

    def evaluate(
        rows: list[dict[str, Any]], *args: Any, cancellation: Any = None
    ) -> dict[str, str]:
        """Capture the post-load phase without performing any judge/model inference."""
        evaluated.append(rows)
        return {"status": "completed"}

    monkeypatch.setattr(coordinator, "evaluate", evaluate)
    body = configuration(duration_seconds=5, max_requests=3).model_dump(mode="json")
    body["target"]["url"] = base_url + "/" + mode
    body["target"]["adapter"] = adapter
    body["target"]["request_usage"] = False
    body["evaluation"]["samples"].append({"inputs": {"query": "Second case"}})
    app = api.create_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50000)),
            base_url="http://test",
        ) as client,
    ):
        url, run = await submit_and_wait(client, body)
        assert run["status"] == "completed"
        assert run["preflight"]["status"] == "passed"
        assert run["preflight"]["http_status"] == 200
        assert run["preflight"]["latency_ms"] > 0
        assert run["metrics"]["requests"] == run["metrics"]["successful_requests"] == 3
        assert run["metrics"]["observed_peak_in_flight"] == 3
        records = (await client.get(url + "/requests")).json()
        assert records["total"] == len(evaluated[0]) == 3
        assert all(row["request_id"] != run["preflight"]["request_id"] for row in evaluated[0])
        assert server["received"] == 4
        messages_key = "messages" if adapter == "openai-chat" else "input"
        assert server["bodies"][0][messages_key][0]["content"] == "Can I refund?"
        assert all("stream_options" not in payload for payload in server["bodies"])
        assert server["request_ids"][0] == run["preflight"]["request_id"]
        report = (await client.get(url + "/report")).json()
        assert report["total"] == report["profiling"]["total_requests"] == 3
        assert all(
            row["request_id"] != run["preflight"]["request_id"] for row in report["requests"]
        )


async def test_preflight_auth_failure_never_dispatches_or_loads(
    endpoint: tuple[str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url, server = endpoint
    monkeypatch.delenv("PREFLIGHT_TEST_TOKEN", raising=False)
    monkeypatch.setenv(
        "BENCHMARK_CONNECTIONS",
        json.dumps(
            {
                "probe": {
                    "url": base_url + "/normal",
                    "auth": "bearer",
                    "token_env": "PREFLIGHT_TEST_TOKEN",
                }
            }
        ),
    )
    body = configuration().model_dump(mode="json")
    body["target"].update(url=base_url + "/normal", connection_id="probe")
    app = api.create_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50000)),
            base_url="http://test",
        ) as client,
    ):
        _, run = await submit_and_wait(client, body)
        assert run["status"] == "failed" and run["load_status"] == "skipped"
        assert run["preflight"]["error"]["code"] == "authentication_failed"
        assert run["preflight"]["http_status"] is None
        assert server["received"] == 0


async def test_cancellation_during_preflight_drains_one_attempt_without_starting_load(
    endpoint: tuple[str, dict[str, Any]],
    tmp_path: Path,
) -> None:
    base_url, server = endpoint
    body = configuration(timeout_seconds=2).model_dump(mode="json")
    body["target"]["url"] = base_url + "/slow"
    app = api.create_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50000)),
            base_url="http://test",
        ) as client,
    ):
        accepted = await client.post("/v1/runs", json=body)
        url = accepted.headers["Location"]
        for _ in range(400):
            if server["active"]:
                break
            await asyncio.sleep(0.01)
        assert server["active"] == 1
        active = (await client.get(url)).json()
        assert active["status"] == "preflighting" and active["load_status"] == "queued"
        assert (await client.post(url + "/cancel")).status_code == 200
        for _ in range(400):
            run = (await client.get(url)).json()
            if run["status"] == "cancelled":
                break
            await asyncio.sleep(0.01)
        assert run["status"] == "cancelled" and run["load_status"] == "skipped"
        assert run["preflight"]["status"] == "cancelled"
        assert server["received"] == 1
        assert (await client.get(url + "/report")).status_code == 200


async def test_already_cancelled_preflight_sends_nothing(
    tmp_path: Path,
) -> None:
    cancel = asyncio.Event()
    cancel.set()
    result = await run_preflight(configuration(), str(uuid4()), cancel, tmp_path)
    assert result.status == "cancelled"
    assert result.request_id is None
    assert not list(tmp_path.iterdir())


async def test_connection_failure_is_safe_and_stops_before_load(tmp_path: Path) -> None:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        request = configuration(duration_seconds=5, max_requests=3, timeout_seconds=1)
        request.target.url = f"http://127.0.0.1:{reservation.getsockname()[1]}/chat"
        result = await run_preflight(request, str(uuid4()), asyncio.Event(), tmp_path)
        rows, summary = await run_load(request, str(uuid4()), asyncio.Event(), tmp_path)
    assert result.status == "failed"
    assert result.error.code in {"target_connection_error", "target_timeout"}
    assert result.request_id and result.http_status is None
    assert "127.0.0.1" not in result.model_dump_json()
    assert len(rows) == request.load.max_requests
    assert summary["incomplete_measurements"] == 0 and summary["load_status"] == "completed"
    assert all(
        row["error"] in {"ConnectionError", "ConnectTimeout", "TimeoutError"} for row in rows
    )


async def test_preflight_worker_start_error_surfaces_safe_failure_and_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken_worker(*args: Any, **kwargs: Any) -> None:
        raise OSError("private worker details")

    monkeypatch.setattr(coordinator, "run_preflight", broken_worker)
    monkeypatch.setattr(
        coordinator, "run_load", lambda *args, **kwargs: pytest.fail("Load must not run")
    )
    app = api.create_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50000)),
            base_url="http://test",
        ) as client,
    ):
        url, run = await submit_and_wait(client, configuration().model_dump(mode="json"))
        assert run["status"] == run["preflight"]["status"] == "failed"
        assert run["load_status"] == run["evaluation_status"] == "skipped"
        assert run["preflight"]["error"]["code"] == "worker_failed"
        assert "private" not in json.dumps(run)
        assert (await client.get(url + "/report")).status_code == 200


async def test_killed_preflight_worker_never_starts_load(
    endpoint: tuple[str, dict[str, Any]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_url, server = endpoint
    monkeypatch.setattr(
        coordinator, "run_load", lambda *args, **kwargs: pytest.fail("Load must not run")
    )
    body = configuration(timeout_seconds=4).model_dump(mode="json")
    body["target"]["url"] = base_url + "/slow"
    app = api.create_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50000)),
            base_url="http://test",
        ) as client,
    ):
        accepted = await client.post("/v1/runs", json=body)
        url = accepted.headers["Location"]
        for _ in range(400):
            if server["active"]:
                break
            await asyncio.sleep(0.01)
        assert server["active"] == 1
        probe_root = tmp_path / "preflights" / accepted.json()["id"]
        pid = json.loads((probe_root / "worker.json").read_text())["pid"]
        os.kill(pid, signal.SIGKILL)
        for _ in range(400):
            run = (await client.get(url)).json()
            if run["status"] == "interrupted":
                break
            await asyncio.sleep(0.01)
        assert run["status"] == run["preflight"]["status"] == "interrupted"
        assert run["load_status"] == run["evaluation_status"] == "skipped"
        assert run["preflight"]["error"]["code"] == "worker_failed"
        assert server["received"] == 1
        assert (await client.get(url + "/report")).status_code == 200


def test_preflight_cannot_pass_without_a_single_complete_attempt_and_clean_exit() -> None:
    row = {"request_id": "probe", "success": True, "http_status": 200}
    summary = {"load_status": "completed", "measurement_complete": True, "worker_exit_code": 0}
    assert preflight_result([row], summary).status == "passed"
    for rows, changes in [
        ([], {}),
        ([row, row], {}),
        ([row], {"measurement_complete": False}),
        ([row], {"worker_exit_code": 2}),
    ]:
        result = preflight_result(rows, {**summary, **changes})
        assert result.status == "failed"
        assert result.error.code == "worker_failed"
    failed = {
        **row,
        "success": False,
        "http_status": None,
        "error": "ConnectionError",
        "error_phase": "request",
        "error_detail": "private provider details",
    }
    connection = preflight_result([failed], summary)
    assert connection.error.code == "target_connection_error"
    deadline = preflight_result([{**failed, "deadline_exceeded": True}], summary)
    assert deadline.error.code == "target_timeout"
    assert "private" not in connection.model_dump_json() + deadline.model_dump_json()


def test_restart_during_preflight_preserves_probe_without_replaying_or_load_rows(
    tmp_path: Path,
) -> None:
    body = configuration().model_dump(mode="json")
    run_id = str(uuid4())
    probe = tmp_path / "preflights" / run_id
    probe.mkdir(parents=True)
    from benchmark_agents.planner import fingerprint, validate_plan

    plan = validate_plan(configuration().evaluation, [], "explicit")
    atomic_json(
        tmp_path / f"{run_id}.json",
        {
            "id": run_id,
            "status": "preflighting",
            "load_status": "queued",
            "evaluation_status": "pending",
            "config": body,
            "plan": plan.model_dump(),
            "trace_coverage": "Not collected",
            "preflight": {"status": "running"},
            "idempotency_key_hash": fingerprint("once"),
            "request_hash": fingerprint(body),
        },
    )
    append_event(probe / "requests.jsonl", {"kind": "started", "row": {"request_id": "probe"}})
    with TestClient(api.create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        url = f"/v1/runs/{run_id}"
        run = client.get(url).json()
        assert run["status"] == run["preflight"]["status"] == "interrupted"
        assert run["load_status"] == run["evaluation_status"] == "skipped"
        assert run["preflight"]["request_id"] == "probe"
        assert client.get(url + "/requests").json()["total"] == 0
        assert client.get(url + "/report").status_code == 200
        replay = client.post("/v1/runs", json=body, headers={"Idempotency-Key": "once"})
        assert replay.json()["id"] == run_id and replay.json()["status"] == "interrupted"
        history = client.get("/v1/runs?status=interrupted").json()
        assert history["items"][0]["load_status"] == "skipped"


def test_restart_signals_abandoned_preflight_and_blocks_new_dispatch(tmp_path: Path) -> None:
    run_id = str(uuid4())
    probe = tmp_path / "preflights" / run_id
    atomic_json(probe / "worker.json", {"pid": os.getpid(), "phase": "preflight"})
    with TestClient(api.create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        assert (probe / "cancel").exists()
        response = client.post("/v1/runs", json=configuration().model_dump(mode="json"))
        assert response.status_code == 409
        assert "draining" in response.json()["error"]["message"]
