"""v2 admission, recovery, isolation, and real SDK-to-Locust traffic contracts."""

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from benchmark_agents import coordinator
from benchmark_agents.api import create_app
from benchmark_agents.models import Evaluation, Plan, PreflightResult
from benchmark_agents.v2_models import Result, RunCreate
from evalsurge import EvalSurge


def request_body(mode: str = "off") -> dict[str, Any]:
    """Return the bounded registered-target golden path."""
    return {
        "name": "baseline",
        "target": {"connection_id": "support"},
        "cases": [
            {"input": {"query": "Can I refund?"}, "reference": {"expected_response": "Answer—yes"}}
        ],
        "load": {"concurrency": 1, "duration_seconds": 5, "max_requests": 2},
        "evaluation": {"mode": mode},
    }


def register(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    """Configure a server-owned preset; no API caller chooses the destination."""
    monkeypatch.setenv("BENCHMARK_CONNECTIONS", json.dumps({"support": {"url": url}}))
    monkeypatch.delenv("BENCHMARK_CONFIG", raising=False)


async def test_sdk_v2_runs_actual_locust_without_planner_or_judge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: Any,
) -> None:
    """Remote SDK, REST, preflight, journals and report use the same real engine."""
    base, server = endpoint
    register(monkeypatch, base + "/normal")

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Default-off must not construct a planner or judge client")

    monkeypatch.setattr("benchmark_agents.planner.planner_client", forbidden)
    monkeypatch.setattr("benchmark_agents.judges.judge_client", forbidden)

    def run() -> dict[str, Any]:
        with (
            TestClient(create_app(tmp_path), client=("127.0.0.1", 50000)) as http,
            EvalSurge.remote("http://127.0.0.1", http_client=http, poll_interval=0.01) as sdk,
        ):
            handle = sdk.start(request_body(), idempotency_key="golden")
            report = handle.wait(timeout=20)
            repeated = sdk.start(request_body(), idempotency_key="golden")
            assert repeated.id == handle.id
            assert http.get(f"/v1/runs/{handle.id}").status_code == 200
            assert http.get("/v2/capabilities").json()["runtime_verified"] is False
            result = http.get(f"/v2/runs/{handle.id}/result").json()
            Result.model_validate(result)
            assert result["summary"]["quality"] == "off"
            assert result["summary"]["performance"] == "complete"
            assert "internal_trace_coverage" in result["summary"]["evidence_gaps"]
            assert base not in json.dumps(report)
            return report

    report = await asyncio.to_thread(run)
    assert server["received"] == 3  # one excluded preflight + two measured attempts
    assert report["total"] == report["run"]["metrics"]["requests"] == 2
    assert report["run"]["phases"]["inference"] == "passed"
    assert report["run"]["summary"]["sustainable_capacity_established"] is False


async def test_admission_precedes_planning_cancel_prevents_inference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register(monkeypatch, "http://127.0.0.1:9001/chat")
    entered, release = asyncio.Event(), asyncio.Event()
    original = coordinator.create_plan

    async def paused(evaluation: Evaluation) -> Plan:
        entered.set()
        await release.wait()
        # An explicit empty selection completes this controlled planning boundary.
        return await original(
            evaluation.model_copy(update={"scorers": [], "registered_scorers": []})
        )

    async def forbidden(*args: Any, **kwargs: Any) -> PreflightResult:
        pytest.fail("Cancellation during planning must prevent inference")

    monkeypatch.setattr(coordinator, "create_plan", paused)
    monkeypatch.setattr(coordinator, "run_preflight", forbidden)
    app = create_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50000)),
            base_url="http://local",
        ) as client,
    ):
        receipt = await asyncio.wait_for(
            client.post(
                "/v2/runs", json=request_body("automatic"), headers={"Idempotency-Key": "once"}
            ),
            1,
        )
        assert receipt.status_code == 202
        identifier = receipt.json()["id"]
        await entered.wait()
        status = await client.get(f"/v2/runs/{identifier}")
        assert status.json()["status"] == "planning"
        assert (await client.post(f"/v2/runs/{identifier}/cancel")).status_code == 200
        assert (
            await client.post(
                "/v2/runs", json=request_body("automatic"), headers={"Idempotency-Key": "once"}
            )
        ).json()["id"] == identifier
        release.set()
        await app.state.coordinator.tasks[identifier]
        report = await client.get(f"/v2/runs/{identifier}/report")
        assert report.json()["run"]["status"] == "cancelled"
        assert report.json()["run"]["phases"]["load"] == "skipped"
        assert report.json()["run"]["phases"]["inference"] == "not_run"


async def test_cancel_before_deferred_planning_retains_not_run_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancel before the task starts; neither planning nor inference may run."""
    from benchmark_agents.v2 import result_view
    from tests.test_template import configuration

    async def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Cancellation before deferred planning must prevent external work")

    monkeypatch.setattr(coordinator, "create_plan", forbidden)
    monkeypatch.setattr(coordinator, "run_preflight", forbidden)
    owner = coordinator.RunCoordinator(tmp_path)
    await owner.open()
    try:
        receipt = await owner.submit(configuration(), defer_planning=True)
        owner.cancel(UUID(receipt.id))
        await owner.tasks[receipt.id]
        view = result_view(owner._read_run(UUID(receipt.id)))
        assert view.status == "cancelled"
        assert view.phases.planning == "cancelled"
        assert view.phases.inference == "not_run"
        assert view.phases.evaluation_readiness == "not_run"
        assert view.phases.load == "skipped"
    finally:
        await owner.close()


def test_planning_failure_report_and_restart_idempotency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register(monkeypatch, "http://127.0.0.1:9001/chat")

    async def failed(*args: Any, **kwargs: Any) -> Plan:
        raise RuntimeError("synthetic-secret-provider-message")

    monkeypatch.setattr(coordinator, "create_plan", failed)
    body = request_body("automatic")
    with TestClient(create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        receipt = client.post("/v2/runs", json=body, headers={"Idempotency-Key": "failed"})
        identifier = receipt.json()["id"]
    monkeypatch.setenv("BENCHMARK_CONNECTIONS", "{}")
    with TestClient(create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        replay = client.post("/v2/runs", json=body, headers={"Idempotency-Key": "failed"})
        assert replay.status_code == 202 and replay.json()["id"] == identifier
        report = client.get(f"/v2/runs/{identifier}/report")
        assert report.status_code == 200
        assert report.json()["run"]["status"] == "failed"
        assert report.json()["run"]["planning_error"]["code"] == "planning_failed"
        assert "synthetic-secret" not in report.text
        history = client.get("/v1/runs").json()
        entry = next(item for item in history["items"] if item["id"] == identifier)
        assert entry["url"] == f"/v2/runs/{identifier}"
        assert client.get(entry["url"]).status_code == 200
        from tests.test_report_ui import render

        output = render(
            report.json(),
            responses=[
                {
                    "ok": False,
                    "status": 409,
                    "body": client.get(f"/v1/runs/{identifier}/report").json(),
                },
                {"ok": True, "body": report.json()},
            ],
        )
        assert [call["url"] for call in output["calls"]] == [
            f"/v1/runs/{identifier}/report?offset=0&limit=25",
            f"/v2/runs/{identifier}/report?offset=0&limit=25",
        ]
        assert not output["nodes"]["report"]["hidden"]
        assert "Planning failed" in output["nodes"]["context"]["text"]
        assert "No frozen evaluation plan" in output["nodes"]["suggestions"]["text"]
        assert "synthetic-secret" not in json.dumps(output)
        body["name"] = "different"
        assert (
            client.post("/v2/runs", json=body, headers={"Idempotency-Key": "failed"}).status_code
            == 409
        )


def test_v2_authentication_errors_are_safe_and_versioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BENCHMARK_API_KEY", "operator-private-key")
    with TestClient(create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        denied = client.get("/v2/capabilities")
        assert denied.status_code == 401
        assert denied.json()["error"]["code"] == "authentication_required"
        assert denied.json()["error"]["retryable"] is False
        headers = {"X-API-Key": "operator-private-key"}
        body = request_body()
        body["target"] = {"url": "https://operator-private-key.example"}
        invalid = client.post("/v2/runs", json=body, headers=headers)
        assert invalid.status_code == 422
        assert "operator-private-key" not in invalid.text
        assert invalid.json()["error"]["phase"] == "admission"
        legacy = client.post("/v1/runs", json={}, headers=headers)
        assert set(legacy.json()["error"]) == {"code", "message", "request_id"}


def test_off_rejects_ignored_scorers_and_undeclared_target_fields() -> None:
    body = request_body()
    body["evaluation"]["scorers"] = ["relevance"]
    with pytest.raises(ValueError):
        RunCreate.model_validate(body)
    body = request_body()
    body["target"]["profile"] = "user-profile"
    with pytest.raises(ValueError):
        RunCreate.model_validate(body)


def test_v2_validation_reports_safe_fields_and_bounds_without_submitted_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(monkeypatch, "http://127.0.0.1:9/no-traffic")
    body = request_body()
    body["load"]["concurrency"] = 0
    body["load"]["duration_seconds"] = "synthetic-secret-invalid-duration"
    body["target"]["synthetic-secret-unknown-field"] = "private-token"
    with TestClient(create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        response = client.post("/v2/runs", json=body)
        assert response.status_code == 422
        detail = response.json()["error"]
        assert detail["code"] == "invalid_request"
        assert detail["retryable"] is False
        errors = {tuple(item["location"]): item for item in detail["errors"]}
        assert errors[("body", "load", "concurrency")]["message"] == (
            "Must be greater than or equal to 1"
        )
        assert errors[("body", "load", "duration_seconds")]["code"] == "invalid_type"
        assert errors[("body", "target", "<extra>")]["code"] == "unsupported_field"
        assert "synthetic-secret" not in response.text
        assert "private-token" not in response.text
        assert response.headers["Cache-Control"] == "no-store"
        many = request_body()
        many["cases"] = [{"input": []} for _ in range(100)]
        bounded = client.post("/v2/runs", json=many).json()["error"]
        assert len(bounded["errors"]) == 20
        assert all(len(item["location"]) <= 12 for item in bounded["errors"])


def test_v2_validation_preserves_only_fixed_model_validator_guidance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(monkeypatch, "http://127.0.0.1:9/no-traffic")
    body = request_body("explicit")
    with TestClient(create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        detail = client.post("/v2/runs", json=body).json()["error"]
        assert detail["errors"][0]["location"] == ["body", "evaluation"]
        assert detail["errors"][0]["message"] == "Explicit evaluation requires scorer IDs"


def test_v2_validation_never_serializes_custom_exception_or_arbitrary_context(
    tmp_path: Path,
) -> None:
    """Unrecognized validators must not export their error message/context/keys."""
    from fastapi.exceptions import RequestValidationError

    app = create_app(tmp_path)

    @app.get("/v2/synthetic-invalid", include_in_schema=False)
    async def invalid() -> None:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("body", "cases", 0, "input", "synthetic-secret-key"),
                    "msg": "Value error, synthetic-secret-provider-exception",
                    "input": "synthetic-secret-submitted-value",
                    "ctx": {"error": RuntimeError("synthetic-secret-context")},
                }
            ]
        )

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.get("/v2/synthetic-invalid")
        issue = response.json()["error"]["errors"][0]
        assert issue["location"] == ["body", "cases", 0, "input", "<extra>"]
        assert issue["message"] == "Field has an invalid value"
        assert "synthetic-secret" not in response.text


async def test_close_drains_deferred_planning_without_lock_deadlock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = coordinator.create_plan
    entered, release = asyncio.Event(), asyncio.Event()

    async def paused(evaluation: Evaluation) -> Plan:
        entered.set()
        await release.wait()
        return await original(evaluation)

    monkeypatch.setattr(coordinator, "create_plan", paused)
    owner = coordinator.RunCoordinator(tmp_path)
    await owner.open()
    from tests.test_template import configuration

    accepted = await owner.submit(configuration(), defer_planning=True)
    await entered.wait()
    closing = asyncio.create_task(owner.close())
    await asyncio.sleep(0)
    release.set()
    await asyncio.wait_for(closing, 2)
    assert owner.tasks == {}
    assert json.loads((tmp_path / f"{UUID(accepted.id)}.json").read_text())["status"] == "cancelled"


async def test_interrupted_planning_recovery_has_no_pending_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Abandoned planning cannot leave unstarted phases pending after recovery."""
    entered = asyncio.Event()

    async def interrupted(evaluation: Evaluation) -> Plan:
        entered.set()
        await asyncio.Event().wait()
        raise AssertionError("Unreachable planning completion")

    monkeypatch.setattr(coordinator, "create_plan", interrupted)
    owner = coordinator.RunCoordinator(tmp_path)
    await owner.open()
    from tests.test_template import configuration

    accepted = await owner.submit(configuration(), defer_planning=True)
    await entered.wait()
    task = owner.tasks[accepted.id]
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await owner.close()

    with TestClient(create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        status = client.get(f"/v2/runs/{accepted.id}").json()
        assert status["status"] == "interrupted"
        assert status["phases"]["planning"] == "interrupted"
        assert status["phases"]["inference"] == "not_run"
        assert status["phases"]["evaluation_readiness"] == "not_run"
        assert status["phases"]["load"] == "skipped"
        report = client.get(f"/v2/runs/{accepted.id}/report")
        assert report.status_code == 200
        assert report.json()["run"]["phases"] == status["phases"]
