"""CLI/SDK integration with TOML operators, the real API, and real local Locust."""

import asyncio
import configparser
import json
import os
import threading
from importlib import import_module
from pathlib import Path
from typing import Any
from uuid import UUID
from zipfile import ZipFile

import httpx
import pytest
from fastapi.testclient import TestClient
from hatchling.build import build_wheel

from benchmark_agents import coordinator
from benchmark_agents.api import create_app
from benchmark_agents.models import Evaluation, Plan, RunReport, RunResponse
from evalsurge.cli import main
from evalsurge.remote import RemoteClient, RemoteRunFailed, RemoteUnauthorizedError

SECRET = "synthetic-operator-service-key"


def clear_operator_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate operator fixtures from developer settings; pytest restores every value."""
    for name in list(os.environ):
        if name.startswith(("BENCHMARK_", "DATABRICKS_", "MLFLOW_", "EVALSURGE_")):
            monkeypatch.delenv(name)


def operator_file(
    root: Path,
    *,
    url: str,
    api_key: str = SECRET,
    alias: str = "support",
    protocols: tuple[str, ...] = ("http-json",),
) -> Path:
    """Write explicit operator-owned dummy service auth and registered JSON target."""
    root.mkdir()
    path = root / "operator.toml"
    path.write_text(
        f"api_key = {json.dumps(api_key)}\n"
        f"artifact_dir = {json.dumps(str(root / 'evidence'))}\n"
        f"[connections.{alias}]\n"
        f"url = {json.dumps(url)}\n"
        f"protocols = {json.dumps(protocols)}\n",
        encoding="utf-8",
    )
    return path


def request_body() -> dict[str, Any]:
    """Omit evaluation entirely so default-off is exercised across all layers."""
    return {
        "target": {"connection_id": "support"},
        "cases": [{"input": {"query": "Synthetic example"}}],
        "load": {"concurrency": 1, "duration_seconds": 5, "max_requests": 1, "timeout_seconds": 3},
    }


def client_factory(http: TestClient) -> Any:
    """Use the real RemoteClient with a borrowed real ASGI HTTP client."""

    def factory(*args: Any, **kwargs: Any) -> RemoteClient:
        return RemoteClient(*args, **kwargs, http_client=http)

    return factory


def test_sdk_cancel_accepts_actual_api_acknowledgment_and_waits_for_terminal_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancellation acceptance is not itself the terminal cancelled lifecycle."""
    clear_operator_environment(monkeypatch)
    path = operator_file(tmp_path / "operator", url="http://127.0.0.1:9/no-traffic")
    entered, release = threading.Event(), threading.Event()
    original = coordinator.create_plan

    async def paused(evaluation: Evaluation) -> Plan:
        entered.set()
        await asyncio.to_thread(release.wait)
        return await original(evaluation)

    async def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("A cancelled planning run must not invoke the target")

    monkeypatch.setattr(coordinator, "create_plan", paused)
    monkeypatch.setattr(coordinator, "run_preflight", forbidden)
    app = create_app(config_path=path)
    with (
        TestClient(app, client=("127.0.0.1", 50000)) as http,
        RemoteClient("http://127.0.0.1", api_key=SECRET, http_client=http) as sdk,
    ):
        try:
            handle = sdk.start(request_body())
            assert entered.wait(timeout=2)
            acknowledgment = handle.cancel()
            assert acknowledgment["id"] == str(handle.id)
            assert acknowledgment["status"] == "cancellation_requested"
            assert handle.status()["status"] == "planning"
        finally:
            release.set()
        with pytest.raises(RemoteRunFailed) as failure:
            handle.wait(timeout=5)
        assert failure.value.report["run"]["status"] == "cancelled"
        assert failure.value.report["run"]["phases"]["inference"] == "not_run"
        assert SECRET not in str(failure.value)


def test_cli_doctor_reads_toml_capabilities_without_initializing_providers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    clear_operator_environment(monkeypatch)
    path = operator_file(tmp_path / "operator", url="http://127.0.0.1:9/private-target")
    monkeypatch.setenv("EVALSURGE_API_KEY", SECRET)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Doctor must not resolve provider credentials or execute inference/judging")

    monkeypatch.setattr("benchmark_agents.providers.workspace_client", forbidden)
    monkeypatch.setattr("benchmark_agents.planner.planner_client", forbidden)
    monkeypatch.setattr("benchmark_agents.judges.judge_client", forbidden)
    monkeypatch.setattr(coordinator, "run_preflight", forbidden)
    app = create_app(config_path=path)
    with TestClient(app, client=("127.0.0.1", 50000)) as http:
        assert main(["doctor"], client_factory=client_factory(http)) == 0
        assert not http.is_closed
        assert app.state.coordinator.index == {}
        denied = http.get("/v2/capabilities")
        assert denied.status_code == 401
        permitted = http.get("/v2/capabilities", headers={"X-API-Key": SECRET})
        assert permitted.json()["targets"] == [{"name": "support", "protocols": ["http-json"]}]
        assert permitted.headers["Cache-Control"] == "no-store"
        assert "private-target" not in permitted.text
        assert SECRET not in permitted.text
    output = capsys.readouterr()
    assert "Registered targets: 1" in output.out
    assert "Planner: needs configuration" in output.out
    assert "unverified" in output.out
    assert SECRET not in output.out + output.err
    assert os.getenv("BENCHMARK_API_KEY") is None


@pytest.mark.parametrize("protocols", [("http-json",), ("http-json", "mlflow-agent-server")])
async def test_cli_run_toml_default_off_preserves_v1_and_single_json_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: Any,
    capsys: pytest.CaptureFixture[str],
    protocols: tuple[str, ...],
) -> None:
    base, measurements = endpoint
    clear_operator_environment(monkeypatch)
    path = operator_file(tmp_path / "operator", url=base + "/json", protocols=protocols)
    monkeypatch.setenv("EVALSURGE_API_KEY", SECRET)
    config = tmp_path / "run.json"
    config.write_text(json.dumps(request_body()), encoding="utf-8")

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Omitted evaluation must not initialize a planner or judge")

    monkeypatch.setattr("benchmark_agents.planner.planner_client", forbidden)
    monkeypatch.setattr("benchmark_agents.judges.judge_client", forbidden)

    def execute() -> dict[str, Any]:
        app = create_app(config_path=path)
        with TestClient(app, client=("127.0.0.1", 50000)) as http:
            assert (
                main(
                    ["run", str(config), "--wait", "--timeout", "20"],
                    client_factory=client_factory(http),
                )
                == 0
            )
            assert not http.is_closed
            identifier = UUID(next(iter(app.state.coordinator.index)))
            headers = {"X-API-Key": SECRET}
            legacy = http.get(f"/v1/runs/{identifier}", headers=headers)
            RunResponse.model_validate(legacy.json())
            assert legacy.json()["config"]["evaluation"]["scorers"] == []
            legacy_report = http.get(f"/v1/runs/{identifier}/report", headers=headers)
            RunReport.model_validate(legacy_report.json())
            with RemoteClient("http://127.0.0.1", api_key=SECRET, http_client=http) as sdk:
                result = sdk.result(identifier)
                assert result["summary"]["quality"] == "off"
                assert result["summary"]["performance"] == "complete"
                report = sdk.report(identifier)
            assert (
                legacy.headers["Cache-Control"]
                == legacy_report.headers["Cache-Control"]
                == "no-store"
            )
            assert base not in json.dumps(report)
            assert report["run"]["metrics"]["timing_successful_only"]["ttft_ms"]["count"] == 0
            assert legacy_report.json()["total"] == report["total"] == 1
            return report

    report = await asyncio.to_thread(execute)
    assert report["run"]["status"] == "completed"
    assert measurements["received"] == 2  # exactly one excluded probe and one measured attempt
    assert measurements["bodies"] == [{"query": "Synthetic example"}] * 2
    output = capsys.readouterr()
    assert "accepted" in output.out and "completed" in output.out
    assert SECRET not in output.out + output.err
    assert "Synthetic example" not in output.out
    assert os.getenv("BENCHMARK_CONNECTIONS") is None


def test_two_toml_api_owners_preserve_distinct_authentication_and_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_operator_environment(monkeypatch)
    first = operator_file(tmp_path / "first", url="http://127.0.0.1:9/first", alias="first")
    other_key = "synthetic-other-key"
    second = operator_file(
        tmp_path / "second", url="http://127.0.0.1:9/second", api_key=other_key, alias="second"
    )
    app_one, app_two = create_app(config_path=first), create_app(config_path=second)
    with (
        TestClient(app_one, client=("127.0.0.1", 50000)) as http_one,
        TestClient(app_two, client=("127.0.0.1", 50001)) as http_two,
        RemoteClient("http://127.0.0.1", api_key=SECRET, http_client=http_one) as one,
        RemoteClient("http://127.0.0.1", api_key=other_key, http_client=http_two) as two,
    ):
        assert [target["name"] for target in one.capabilities()["targets"]] == ["first"]
        assert [target["name"] for target in two.capabilities()["targets"]] == ["second"]
        with (
            RemoteClient("http://127.0.0.1", api_key=other_key, http_client=http_one) as wrong,
            pytest.raises(RemoteUnauthorizedError) as error,
        ):
            wrong.capabilities()
        assert other_key not in str(error.value)
        assert one.capabilities()["targets"][0]["name"] == "first"
    assert os.getenv("BENCHMARK_API_KEY") is None
    assert os.getenv("BENCHMARK_CONNECTIONS") is None


@pytest.mark.parametrize("change", ["ambient_missing_file", "source_changed_after_startup"])
def test_api_owner_uses_captured_explicit_toml_after_configuration_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    clear_operator_environment(monkeypatch)
    path = operator_file(tmp_path / "operator", url="http://127.0.0.1:9/no-traffic")
    if change == "ambient_missing_file":
        monkeypatch.setenv("BENCHMARK_CONFIG", str(tmp_path / "missing.toml"))
    app = create_app(config_path=path)
    if change == "source_changed_after_startup":
        path.write_text("invalid = [", encoding="utf-8")
    with (
        TestClient(app, client=("127.0.0.1", 50000)) as http,
        RemoteClient("http://127.0.0.1", api_key=SECRET, http_client=http) as sdk,
    ):
        assert sdk.capabilities()["targets"] == [{"name": "support", "protocols": ["http-json"]}]
        assert app.state.coordinator.index == {}
    if change == "ambient_missing_file":
        assert os.getenv("BENCHMARK_CONFIG") == str(tmp_path / "missing.toml")


async def test_pending_report_has_domain_retry_code_without_reclassifying_conflicts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_operator_environment(monkeypatch)
    path = operator_file(tmp_path / "operator", url="http://127.0.0.1:9/no-traffic")
    entered, release = asyncio.Event(), asyncio.Event()
    original = coordinator.create_plan

    async def paused(evaluation: Evaluation) -> Plan:
        entered.set()
        await release.wait()
        return await original(
            evaluation.model_copy(update={"scorers": [], "registered_scorers": []})
        )

    monkeypatch.setattr(coordinator, "create_plan", paused)
    app = create_app(config_path=path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50000)),
            base_url="http://127.0.0.1",
            headers={"X-API-Key": SECRET},
        ) as http,
    ):
        receipt = await http.post(
            "/v2/runs",
            json={**request_body(), "evaluation": {"mode": "automatic"}},
            headers={"Idempotency-Key": "pending"},
        )
        assert receipt.status_code == 202
        identifier = receipt.json()["id"]
        await asyncio.wait_for(entered.wait(), 2)
        try:
            pending = await http.get(f"/v2/runs/{identifier}/report")
            assert pending.status_code == 409
            assert pending.headers["Retry-After"] == "1"
            assert pending.json()["error"]["code"] == "report_not_ready"
            assert pending.json()["error"]["phase"] == "report"
            assert pending.json()["error"]["retryable"] is True
            conflict = await http.post(
                "/v2/runs",
                json={**request_body(), "name": "changed"},
                headers={"Idempotency-Key": "pending"},
            )
            assert conflict.status_code == 409
            assert conflict.json()["error"]["code"] == "resource_conflict"
            assert conflict.json()["error"]["retryable"] is False
        finally:
            await http.post(f"/v2/runs/{identifier}/cancel")
            release.set()
            task = app.state.coordinator.tasks.get(identifier)
            if task:
                await asyncio.wait_for(task, 2)


def test_actual_wheel_contains_remote_modules_and_resolvable_cli_entrypoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Check the actual distribution metadata, rather than only pyproject declarations."""
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    wheel = tmp_path / build_wheel(str(tmp_path))
    with ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "evalsurge/remote.py" in names
        assert "evalsurge/cli.py" in names
        entrypoints = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
        parser = configparser.ConfigParser()
        parser.read_string(archive.read(entrypoints).decode("utf-8"))
        module, callable_name = parser["console_scripts"]["evalsurge"].split(":", 1)
        assert getattr(import_module(module), callable_name) is main
