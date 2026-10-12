"""CLI smoke/error coverage with injected transports and browser opener."""

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

from evalsurge.cli import main
from evalsurge.remote import RemoteClient
from tests.test_remote_sdk import CONFIG, RUN_ID, SECRET


@pytest.fixture
def config(tmp_path: Path) -> Path:
    path = tmp_path / "run.json"
    path.write_text(json.dumps(CONFIG))
    return path


def factory(handler: Any) -> Any:
    """Inject HTTP transport without replacing the real remote client implementation."""

    def create(*args: Any, **kwargs: Any) -> RemoteClient:
        return RemoteClient(
            *args, **kwargs, transport=httpx.MockTransport(handler), sleep=lambda seconds: None
        )

    return create


def test_cli_run_wait_open_report_never_exports_keys_or_report_contents(
    config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("EVALSURGE_API_KEY", SECRET)
    requests: list[httpx.Request] = []
    opened: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["X-API-Key"] == SECRET
        if request.method == "POST":
            assert json.loads(request.content) == CONFIG
            return httpx.Response(
                202, json={"id": str(RUN_ID), "status": "queued"}, headers={"Retry-After": "0"}
            )
        if request.url.path.endswith("/report"):
            return httpx.Response(200, json={"run": {"status": "completed", "secret": SECRET}})
        return httpx.Response(200, json={"id": str(RUN_ID), "status": "completed"})

    code = main(
        ["run", str(config), "--url", "https://api.example", "--wait", "--open-report"],
        client_factory=factory(handle),
        opener=lambda url: opened.append(url) or True,
    )
    output = capsys.readouterr()
    assert code == 0
    assert str(RUN_ID) in output.out
    assert "completed" in output.out
    assert SECRET not in output.out + output.err + repr(opened)
    assert opened == [f"https://api.example/reports/?run={RUN_ID}"]
    assert requests[0].method == "POST"


def test_cli_doctor_uses_v2_capabilities_without_running_load(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("EVALSURGE_API_KEY", SECRET)
    paths: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.headers["X-API-Key"] == SECRET
        paths.append(request.url.path)
        return httpx.Response(200, json={"api_version": "v2", "private": SECRET})

    assert main(["--url", "https://api.example", "doctor"], client_factory=factory(handle)) == 0
    captured = capsys.readouterr()
    assert "reachable" in captured.out
    assert SECRET not in captured.out + captured.err
    assert paths == ["/v2/capabilities"]


def test_cli_invalid_json_and_missing_yaml_are_actionable_without_echoing_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "private.json"
    path.write_text(SECRET)
    assert main(["run", str(path)]) == 2
    assert SECRET not in capsys.readouterr().err
    yaml_path = tmp_path / "run.yaml"
    yaml_path.write_text("target:\n  url: https://agent.example/chat\n")
    original = importlib.import_module

    def unavailable(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "yaml":
            raise ModuleNotFoundError("yaml")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", unavailable)
    assert main(["run", str(yaml_path)]) == 2
    assert "PyYAML" in capsys.readouterr().err


def test_cli_optional_yaml_uses_safe_loader(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pytest.importorskip("yaml")
    path = tmp_path / "run.yml"
    path.write_text("!!python/object/apply:os.system ['echo private-api-key']")
    assert main(["run", str(path)]) == 2
    assert SECRET not in capsys.readouterr().err


@pytest.mark.parametrize("status", [401, 429, 500])
def test_cli_service_errors_have_nonzero_exit_and_no_secret(
    config: Path, capsys: pytest.CaptureFixture[str], status: int
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"code": "safe", "message": SECRET}})

    assert main(["run", str(config)], client_factory=factory(handle)) == 1
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err
    assert "HTTP" in captured.err


def test_cli_failed_run_uses_safe_failure_not_raw_report(
    config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"id": str(RUN_ID), "status": "queued"})
        if request.url.path.endswith("/report"):
            return httpx.Response(200, json={"run": {"status": "failed", "private": SECRET}})
        return httpx.Response(200, json={"id": str(RUN_ID), "status": "failed"})

    assert main(["run", str(config), "--wait"], client_factory=factory(handle)) == 1
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err


def test_cli_usage_errors_and_missing_files_do_not_echo_arguments(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["doctor", "--api-key", SECRET]) == 2
    assert SECRET not in capsys.readouterr().err
    assert main(["run", str(tmp_path / SECRET)]) == 2
    assert SECRET not in capsys.readouterr().err


def test_direct_cli_missing_dependencies_names_local_and_compatible_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Simulate an absent optional module; no client, target or model is invoked."""
    monkeypatch.setitem(sys.modules, "benchmark_agents.diagnostics", None)
    assert main(["doctor", "--local"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "evalsurge[local]" in output.err
    assert "evalsurge[server]" in output.err
    assert "Neither starts an API server" in output.err


def test_cli_oversized_configuration_stops_before_remote_client(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "large.json"
    path.write_bytes(b" " * 8_000_001)

    def forbidden(*args: Any, **kwargs: Any) -> RemoteClient:
        pytest.fail("Oversized configuration must not create an HTTP client")

    assert main(["run", str(path)], client_factory=forbidden) == 2
    assert "limit" in capsys.readouterr().err


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf"])
def test_cli_invalid_wait_budget_never_admits_a_run(
    config: Path, timeout: str, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> RemoteClient:
        pytest.fail("Invalid wait budget must not create a client or submit a run")

    assert main(["run", str(config), "--wait", "--timeout", timeout], client_factory=forbidden) == 2
    assert "timeout" in capsys.readouterr().err


def test_cli_invalid_v2_schema_never_constructs_client(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "direct.json"
    path.write_text(json.dumps({"target": {"url": f"https://agent.example/{SECRET}"}}))

    def forbidden(*args: Any, **kwargs: Any) -> RemoteClient:
        pytest.fail("Invalid schema must be rejected locally")

    assert main(["run", str(path)], client_factory=forbidden) == 2
    captured = capsys.readouterr()
    assert SECRET not in captured.err


def test_cli_yaml_alias_expansion_is_rejected_before_client_creation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pytest.importorskip("yaml")
    path = tmp_path / "aliases.yml"
    path.write_text("target: &target {connection_id: support}\ncases: [{input: *target}]\n")

    def forbidden(*args: Any, **kwargs: Any) -> RemoteClient:
        pytest.fail("YAML aliases must not be expanded or submitted")

    assert main(["run", str(path)], client_factory=forbidden) == 2
    assert "aliases" in capsys.readouterr().err


def test_cli_doctor_displays_only_fixed_static_readiness_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/capabilities"
        return httpx.Response(
            200,
            json={
                "api_version": "v2",
                "targets": [{"name": SECRET}],
                "evaluation": {"planner": "configured", "catalog_judges": SECRET},
                "tracing": {"readiness": "disabled"},
            },
        )

    assert main(["doctor"], client_factory=factory(handle)) == 0
    captured = capsys.readouterr()
    assert "Registered targets: 1" in captured.out
    assert "Planner: configured" in captured.out
    assert "Tracing: disabled" in captured.out
    assert "unverified" in captured.out
    assert SECRET not in captured.out + captured.err
