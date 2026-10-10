"""Fail-fast evaluation and worker checks through the real local REST/Locust path."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APIStatusError, APITimeoutError

from benchmark_agents import api, coordinator, judges
from benchmark_agents.models import Evaluation, EvaluationPreflight, Plan
from benchmark_agents.planner import create_plan
from tests.evaluation_unit_boundary import install_inline_native
from tests.test_preflight import submit_and_wait
from tests.test_template import configuration


def install_judge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None = None
) -> list[dict[str, Any]]:
    """Use actual MLflow with a controlled provider boundary and no workspace access."""
    install_inline_native(monkeypatch)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    monkeypatch.setenv("BENCHMARK_JUDGE_MODEL", "controlled-judge")
    monkeypatch.setenv("MLFLOW_MODEL_CATALOG_URI", "")
    for name in ("DATABRICKS_CONFIG_PROFILE", "DATABRICKS_HOST", "MLFLOW_EXPERIMENT_ID"):
        monkeypatch.delenv(name, raising=False)

    async def controlled_plan(evaluation: Evaluation) -> Plan:
        plan = await create_plan(evaluation)
        plan.judge_model = "controlled-judge"
        plan.judge_host = "https://fixture.example"
        plan.judge_profile = "operator-fixture"
        plan.judge_timeout_seconds = 2
        plan.judge_max_retries = 2
        return plan

    monkeypatch.setattr(coordinator, "create_plan", controlled_plan)
    calls: list[dict[str, Any]] = []

    class Client:
        def __init__(self, **options: Any) -> None:
            self.options = options
            self.chat = SimpleNamespace(completions=self)

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def create(self, **kwargs: Any) -> Any:
            calls.append({"options": self.options, "request": kwargs})
            request = httpx.Request("POST", "https://fixture.example")
            if failure == "timeout":
                raise APITimeoutError(request=request)
            if failure in {"401", "403", "429", "500"}:
                response = httpx.Response(int(failure), request=request)
                raise APIStatusError(
                    "private-provider-text",
                    response=response,
                    body={"secret": "private-credential"},
                )
            content = (
                "{}"
                if failure == "invalid"
                else json.dumps(
                    {"result": "no", "rationale": "Controlled negative quality verdict"}
                )
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )

    monkeypatch.setattr(judges, "judge_client", Client)
    return calls


@pytest.mark.parametrize(
    "failure,code",
    [
        ("401", "judge_authentication_failed"),
        ("403", "judge_authentication_failed"),
        ("429", "judge_rate_limited"),
        ("500", "judge_provider_error"),
        ("timeout", "judge_timeout"),
        ("invalid", "invalid_judge_response"),
    ],
)
async def test_broken_judge_stops_before_load(
    endpoint, tmp_path, monkeypatch, failure, code
) -> None:
    base_url, target = endpoint
    calls = install_judge(tmp_path, monkeypatch, failure)
    body = configuration().model_dump(mode="json")
    body["target"]["url"] = base_url + "/normal"
    body["evaluation"].update(
        scorers=["relevance", "correctness"],
        max_scored_requests=1,
        samples=[
            {
                "inputs": {"query": "Can I refund?"},
                "expectations": {"expected_response": "No"},
            }
        ],
    )
    monkeypatch.setattr(
        coordinator, "run_load", lambda *args, **kwargs: pytest.fail("Load must not start")
    )
    app = api.create_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50000)),
            base_url="http://test",
        ) as client,
    ):
        url, run = await submit_and_wait(client, body)
        assert run["status"] == run["evaluation_status"] == "failed"
        assert run["load_status"] == run["profiling_status"] == "skipped"
        assert run["preflight"]["status"] == "passed"
        readiness = run["evaluation_preflight"]
        assert readiness["status"] == "failed"
        assert readiness["checked_scorers"] == ["relevance"]
        assert readiness["error"]["code"] == code
        assert readiness["error"]["guidance"]
        assert readiness["error"]["scorer"] == "relevance"
        assert target["received"] == 1
        assert len(calls) == 1
        assert calls[0]["options"]["max_retries"] == 0
        assert calls[0]["options"]["timeout"] == 2
        assert run["plan"]["judge_max_retries"] == 2
        assert run["metrics"] == {}
        assert all(
            secret not in json.dumps(run)
            for secret in ("private-provider-text", "private-credential")
        )
        assert (await client.get(url + "/requests")).json()["total"] == 0
        report = (await client.get(url + "/report")).json()
        assert report["total"] == report["profiling"]["total_requests"] == 0
        repeated = await client.post("/v1/runs", json=body, headers={"Idempotency-Key": "once"})
        assert repeated.json()["id"] == run["id"]
        assert target["received"] == len(calls) == 1


async def test_negative_quality_verdict_allows_load_and_is_not_benchmark_score(
    endpoint, tmp_path, monkeypatch
) -> None:
    base_url, target = endpoint
    calls = install_judge(tmp_path, monkeypatch)
    body = configuration(max_requests=2, duration_seconds=2).model_dump(mode="json")
    body["target"]["url"] = base_url + "/normal"
    body["evaluation"].update(scorers=["relevance"], max_scored_requests=1)
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
        assert run["evaluation_preflight"] == {
            "status": "passed",
            "checked_scorers": ["relevance"],
            "error": None,
        }
        assert run["metrics"]["requests"] == 2
        assert run["evaluation"]["results"][0]["scored"] == 1
        assert run["evaluation"]["results"][0]["pass_rate"] == 0
        assert target["received"] == 3
        assert len(calls) == 2
        assert calls[0]["options"]["max_retries"] == 0
        assert calls[1]["options"]["max_retries"] == 2
        assert (await client.get(url + "/requests")).json()["total"] == 2


@pytest.mark.parametrize("missing", ["provider", "reference", "needs_data"])
async def test_known_evaluation_setup_failure_sends_no_agent_requests(
    endpoint, tmp_path, monkeypatch, missing
) -> None:
    base_url, target = endpoint
    calls = install_judge(tmp_path, monkeypatch)
    body = configuration().model_dump(mode="json")
    body["target"]["url"] = base_url + "/normal"
    body["evaluation"]["scorers"] = ["relevance"]
    if missing == "provider":

        async def unconfigured(evaluation: Evaluation) -> Plan:
            plan = await create_plan(evaluation)
            plan.judge_host = None
            return plan

        monkeypatch.setattr(coordinator, "create_plan", unconfigured)
    elif missing == "reference":
        body["evaluation"]["scorers"] = ["correctness"]
        body["evaluation"]["samples"].append(
            {
                "inputs": {"query": "Second case"},
                "expectations": {"expected_response": "No"},
            }
        )
    else:
        body["evaluation"]["scorers"] = ["groundedness"]
    app = api.create_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50000)),
            base_url="http://test",
        ) as client,
    ):
        _url, run = await submit_and_wait(client, body)
        assert run["status"] == "failed"
        assert run["preflight"]["status"] == "not_run"
        assert run["evaluation_preflight"]["status"] == "failed"
        assert run["load_status"] == "skipped"
        assert target["received"] == len(calls) == 0


@pytest.mark.parametrize("phase", ["invoke", "load"])
async def test_process_spawn_failure_is_immediate_and_safe(
    endpoint, tmp_path, monkeypatch, phase
) -> None:
    base_url, target = endpoint
    body = configuration().model_dump(mode="json")
    body["target"]["url"] = base_url + "/normal"
    if phase == "load":

        async def passed(request, run_id, *args, **kwargs):
            return coordinator.PreflightResult(status="passed")

        monkeypatch.setattr(coordinator, "run_preflight", passed)

    async def spawn_failure(*args, **kwargs):
        raise PermissionError("private-process-path-and-credential")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn_failure)
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
        assert target["received"] == 0
        assert "private" not in json.dumps(run)
        if phase == "load":
            assert run["load_status"] == "failed"
            assert run["load_error"]["code"] == "worker_start_failed"
        else:
            assert run["load_status"] == "skipped"
            assert run["preflight"]["error"]["code"] == "worker_failed"
        assert (await client.get(url + "/report")).status_code == 200


async def test_cancel_during_judge_readiness_does_not_start_load(
    endpoint, tmp_path, monkeypatch
) -> None:
    import threading

    base_url, target = endpoint
    install_judge(tmp_path, monkeypatch)
    entered, release = threading.Event(), threading.Event()

    def waiting(*args: Any, **kwargs: Any) -> EvaluationPreflight:
        entered.set()
        assert release.wait(5)
        return EvaluationPreflight(status="passed", checked_scorers=["relevance"])

    monkeypatch.setattr(coordinator, "run_evaluation_preflight", waiting)
    monkeypatch.setattr(
        coordinator, "run_load", lambda *args, **kwargs: pytest.fail("Load must not start")
    )
    body = configuration().model_dump(mode="json")
    body["target"]["url"] = base_url + "/normal"
    body["evaluation"]["scorers"] = ["relevance"]
    app = api.create_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50000)),
            base_url="http://test",
        ) as client,
    ):
        accepted = await client.post("/v1/runs", json=body)
        url = accepted.json()["url"]
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            assert (await client.post(url + "/cancel")).status_code == 200
        finally:
            release.set()
        for _ in range(100):
            run = (await client.get(url)).json()
            if run["status"] == "cancelled":
                break
            await asyncio.sleep(0.02)
        assert run["status"] == "cancelled"
        assert run["load_status"] == "skipped"
        assert target["received"] == 1
