"""Bounded App quality flow through real HTTP, Locust, OpenAI SDK and native MLflow."""

import asyncio
import json
import os
import socket
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import httpx
import mlflow
import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mlflow.tracking import MlflowClient, fluent
from mlflow.tracking._tracking_service import utils as tracking_utils
from openai import OpenAI

from benchmark_agents import judges, planner, target_resolver
from benchmark_agents.configuration import SDK_PROFILE_OVERRIDE_ENV
from benchmark_agents.connections import Connection
from benchmark_agents.models import Target
from scripts.validation import databricks_app_quality as quality


@pytest.fixture(autouse=True)
def restore_mlflow_state() -> Iterator[None]:
    """Restore native MLflow selectors and their exact process environment on teardown.

    Yields:
        Native evaluation without replacing the tracking/evaluation implementation.

    MLflow's tracking setter also changes ``os.environ``, outside the harness's
    task-local configuration. Snapshot the raw selector rather than the resolved
    URI: ``None`` must remain environment-driven after this test. The active
    experiment has no public reset API, so preserve its native raw state as well.
    This autouse fixture tears down after the test's monkeypatch/provider fixtures;
    environment values and absence are restored even after a test failure.
    """
    tracking_uri = tracking_utils._tracking_uri
    experiment_id = fluent._active_experiment_id
    environment = {
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
        mlflow.set_tracking_uri(tracking_uri)
        fluent._active_experiment_id = experiment_id
        for name, value in environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def arguments(*extra: str) -> list[str]:
    return ["--profile", "chosen-private-profile", "--app-name", "sample-agent", *extra]


def test_default_dry_run_has_exact_budget_and_no_external_or_storage_calls(monkeypatch, capsys):
    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Dry-run cannot execute discovery, auth, model calls or storage")

    monkeypatch.setattr(quality, "execute", forbidden)
    monkeypatch.setattr(target_resolver, "resolve_registered_target", forbidden)
    assert quality.main(arguments()) == 0
    output = capsys.readouterr().out
    record = json.loads(output)
    assert record["live"] is False
    assert record["max_total_invocations"] == 3
    assert record["max_judge_readiness_assessments"] == 2
    assert record["max_judge_quality_assessments"] == 4
    assert record["max_judge_provider_attempts"] == 14
    assert record["judge_model"] == quality.JUDGE_MODEL
    assert record["evaluation_mode"] == "explicit" and record["automatic_planner_calls"] == 0
    assert "chosen-private-profile" not in output and quality.POLICY_PROMPT not in output


@pytest.mark.parametrize(
    "extra",
    [
        ["--live"],
        ["--live", "--accept-paid-traffic"],
        ["--max-requests", "3"],
        ["--duration", "11"],
        ["--duration", "nan"],
        ["--concurrency", "6"],
        ["--timeout", "inf"],
    ],
)
def test_quality_workload_and_consent_are_bounded(extra):
    with pytest.raises(SystemExit):
        quality.parse_options(arguments(*extra))


def test_execute_does_not_bypass_consent_or_overwrite_evidence(tmp_path: Path, monkeypatch):
    with pytest.raises(ValueError, match="explicit consent"):
        quality.execute(quality.parse_options(arguments()))
    evidence = tmp_path / "protected.txt"
    evidence.write_text("old protected evidence")
    options = quality.parse_options(
        arguments("--live", "--accept-paid-traffic", "--artifact-dir", str(tmp_path))
    )

    def forbidden(*args: Any, **kwargs: Any):
        pytest.fail("Existing evidence is rejected before SDK discovery")

    monkeypatch.setattr(target_resolver, "resolve_registered_target", forbidden)
    with pytest.raises(ValueError, match="empty dedicated"):
        quality.execute(options)
    assert evidence.read_text() == "old protected evidence"


@pytest.fixture
async def native_target() -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Controlled target HTTP boundary uses the installed native server/template schema."""
    app = FastAPI()
    state = {"bodies": [], "fail": False}

    @app.post("/api/invocations")
    async def invoke(request: Request):
        body = await request.json()
        state["bodies"].append(body)
        assert UUID(body["id"]) and UUID(body["session_id"])
        assert body["stream"] is body["background"] is False
        if state["fail"]:
            return JSONResponse({"detail": "intentional private failure"}, status_code=500)
        return {
            "id": body["id"],
            "status": "completed",
            "output": {
                "status": "completed",
                "output": [
                    {"role": "assistant", "content": "No, opened items cannot be refunded."}
                ],
            },
        }

    connection = socket.socket()
    connection.bind(("127.0.0.1", 0))
    port = connection.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="off"))
    serving = asyncio.create_task(server.serve(sockets=[connection]))
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}/api/invocations", state
    finally:
        server.should_exit = True
        await serving
        connection.close()


def install_boundaries(monkeypatch: pytest.MonkeyPatch, url: str, *, mode: str = "yes"):
    """Control provider transports/configuration, not Locust/scorers/native MLflow."""
    from tests.evaluation_unit_boundary import install_inline_native

    install_inline_native(monkeypatch)
    for name in SDK_PROFILE_OVERRIDE_ENV:
        monkeypatch.delenv(name, raising=False)
    calls = []
    workspace_selections = []

    def resolve(alias, presets):
        # Execute the real fail-closed SDK override guard before the controlled URL.
        target_resolver._reject_profile_overrides()
        assert presets[alias].profile == "chosen-private-profile"
        return Target(
            url=url, adapter="databricks-agent-runtime", session_per_request=True
        ), Connection(url=url)

    def workspace(*, profile, host):
        workspace_selections.append((profile, host))
        assert profile == "chosen-private-profile" and host is None
        return SimpleNamespace(config=SimpleNamespace(host="https://controlled.example"))

    def forbidden(*args: Any, **kwargs: Any):
        pytest.fail("Explicit evaluation must not construct an automatic planner")

    def provider(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload)
        assert payload["model"] == quality.JUDGE_MODEL
        assert payload["max_completion_tokens"] == 2048
        assert quality.POLICY_PROMPT in payload["messages"][1]["content"]
        if mode == "readiness_error" or (mode == "quality_error" and len(calls) > 2):
            return httpx.Response(
                429, json={"error": {"message": "synthetic-private-provider-value"}}
            )
        return httpx.Response(
            200,
            json={
                "id": "controlled-judge",
                "object": "chat.completion",
                "created": 0,
                "model": quality.JUDGE_MODEL,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "result": "no" if mode == "no" else "yes",
                                    "rationale": "Synthetic protected rationale",
                                }
                            ),
                        },
                    }
                ],
            },
        )

    def judge_client(**options):
        return OpenAI(
            api_key="controlled-placeholder",
            base_url="https://controlled.example/serving-endpoints",
            timeout=options["timeout"],
            max_retries=options["max_retries"],
            http_client=httpx.Client(transport=httpx.MockTransport(provider)),
        )

    monkeypatch.setattr(target_resolver, "resolve_registered_target", resolve)
    monkeypatch.setattr(planner, "workspace_client", workspace)
    monkeypatch.setattr(planner, "planner_client", forbidden)
    monkeypatch.setattr(judges, "judge_client", judge_client)
    return calls, workspace_selections


@pytest.mark.parametrize("mode", ["yes", "no"])
async def test_real_quality_assesses_captures_without_target_reinvocation(
    native_target, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
):
    url, target = native_target
    calls, selections = install_boundaries(monkeypatch, url, mode=mode)
    options = quality.parse_options(
        arguments(
            "--concurrency", "5", "--live", "--accept-paid-traffic", "--artifact-dir", str(tmp_path)
        )
    )
    code, record = await asyncio.to_thread(quality.execute, options)
    assert code == (0 if mode == "yes" else 1), record
    assert record["quality_outcome"] == ("passed" if mode == "yes" else "failed")
    assert record["evaluation_execution_complete"] is True
    assert record["evaluation_readiness"]["status"] == "passed"
    assert record["metrics"]["requests"] == 2
    assert record["metrics"]["configured_concurrency"] == 5
    assert len(target["bodies"]) == record["observed_total_target_attempts"] == 3
    assert len(calls) == 6  # two readiness + four captured post-load assessments
    assert sum(quality.EXPECTED_FACT in call["messages"][1]["content"] for call in calls) == 3
    assert selections == [("chosen-private-profile", None)]
    assert all(
        body["input"] == [{"role": "user", "content": quality.POLICY_PROMPT}]
        for body in target["bodies"]
    )
    assert all(
        item["scored"] == 2 and item["judge_errors"] == 0 for item in record["scorer_results"]
    )
    serialized = json.dumps(record)
    assert (
        "Synthetic protected rationale" not in serialized
        and "chosen-private-profile" not in serialized
    )
    saved = json.loads((tmp_path / "validation.json").read_text())
    assert saved == record
    owner = json.loads((tmp_path / f"{record['run_id']}.json").read_text())
    assert owner["plan"]["source"] == "explicit"
    assert owner["plan"]["judge_model"] == quality.JUDGE_MODEL
    assert owner["plan"]["judge_max_retries"] == 2
    assert owner["config"]["evaluation"]["samples"][0]["expectations"] == {
        "expected_facts": [quality.EXPECTED_FACT]
    }
    store = MlflowClient(tracking_uri=f"sqlite:///{tmp_path / 'quality-mlflow.db'}")
    experiment = store.get_experiment_by_name("evalsurge-app-quality")
    assert experiment.artifact_location == (tmp_path / "mlflow-artifacts").as_uri()
    runs = store.search_runs([experiment.experiment_id])
    assert len(runs) == 4  # each criterion has distinct readiness and quality evidence
    assert {run.data.tags["evalsurge.phase"] for run in runs} == {
        "evaluation-preflight",
        "evaluation",
    }


@pytest.mark.parametrize("mode,count", [("readiness_error", 1), ("quality_error", 5)])
async def test_actual_sdk_retry_budget_and_safe_judge_failure(
    native_target, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, count: int
):
    url, target = native_target
    calls, _ = install_boundaries(monkeypatch, url, mode=mode)
    options = quality.parse_options(
        arguments(
            "--max-requests",
            "1",
            "--live",
            "--accept-paid-traffic",
            "--artifact-dir",
            str(tmp_path),
        )
    )
    code, record = await asyncio.to_thread(quality.execute, options)
    assert code == 1 and record["quality_outcome"] == "unavailable"
    assert len(calls) == count
    assert len(target["bodies"]) == (1 if mode == "readiness_error" else 2)
    assert record["metrics"]["requests"] == (0 if mode == "readiness_error" else 1)
    if mode == "readiness_error":
        assert record["evaluation_readiness"]["error"]["code"] == "judge_rate_limited"
        assert record["load_status"] == "skipped"
    else:
        assert record["load_status"] == "completed"
    assert "synthetic-private-provider-value" not in json.dumps(record)


async def test_failed_inference_has_no_judge_or_measured_calls(
    native_target, tmp_path, monkeypatch
):
    url, target = native_target
    target["fail"] = True
    calls, _ = install_boundaries(monkeypatch, url)
    options = quality.parse_options(
        arguments("--live", "--accept-paid-traffic", "--artifact-dir", str(tmp_path))
    )
    code, record = await asyncio.to_thread(quality.execute, options)
    assert code == 1 and record["load_status"] == "skipped"
    assert record["inference_preflight"]["error"]["code"] == "target_http_error"
    assert len(target["bodies"]) == 1 and not calls
    assert record["observed_measured_attempts"] == 0


def test_ambient_sdk_override_is_rejected_before_local_store_or_paid_calls(tmp_path, monkeypatch):
    calls, _ = install_boundaries(monkeypatch, "http://127.0.0.1:9001/api/invocations")
    monkeypatch.setenv("DATABRICKS_HOST", "https://synthetic-private.example")
    options = quality.parse_options(
        arguments("--live", "--accept-paid-traffic", "--artifact-dir", str(tmp_path))
    )
    with pytest.raises(target_resolver.TargetResolutionError, match="conflicts"):
        quality.execute(options)
    assert not list(tmp_path.iterdir()) and not calls
