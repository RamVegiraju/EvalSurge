"""Static consent/budget checks; no agent, transport, fixture completion or LLM call."""

import asyncio
import builtins
import json
import os
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

from benchmark_agents.configuration import configured_environment
from scripts.validation.unified_sdk_journeys import (
    _close_framework_server,
    _validate_http_profile_environment,
    budget_record,
    execute,
    main,
    parse_options,
)


def arguments(journey: str = "http") -> list[str]:
    """Return placeholder operator selections, used only by the pure parser."""
    return [
        "--journey",
        journey,
        "--framework",
        "langgraph",
        "--profile",
        "selected-profile",
        *(
            ["--target-model", "selected-endpoint"]
            if journey == "http"
            else ["--app-name", "existing-agent-app"]
        ),
    ]


def test_budget_accounts_for_probes_and_optional_second_run() -> None:
    normal = budget_record(parse_options(arguments()))
    assert normal["max_total_target_attempts"] == 7
    assert normal["max_measured_invocations"] == 5
    assert normal["max_negative_route_probes_without_model_dispatch"] == 1
    cancellation = budget_record(parse_options(arguments("app") + ["--exercise-cancel"]))
    assert cancellation["max_total_target_attempts"] == 12
    assert cancellation["max_model_bearing_probe_invocations"] == 2
    assert cancellation["evaluation_mode"] == "off"
    assert cancellation["monetary_quota_enforced"] is False


@pytest.mark.parametrize(
    "extra",
    [
        ["--concurrency", "6"],
        ["--max-requests", "21"],
        ["--duration", "nan"],
        ["--timeout", "inf"],
        ["--duration", "181"],
        ["--live"],
        ["--live", "--accept-paid-traffic"],
    ],
)
def test_rejects_unbounded_or_unconsented_execution(extra: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_options(arguments() + extra)


def test_dry_run_does_not_create_artifacts_or_export_private_selections(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "absent"
    assert main(arguments() + ["--artifact-dir", str(destination)]) == 0
    output = capsys.readouterr().out
    body = json.loads(output)
    assert body["live"] is False
    assert not destination.exists()
    assert "selected-profile" not in output
    assert "selected-endpoint" not in output


def test_cli_profile_conflict_is_actionable_before_any_artifact_or_inference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An intentional pre-provider failure never starts an agent or substitutes one."""
    monkeypatch.setenv("DATABRICKS_TOKEN", "private-credential-do-not-print")
    destination = tmp_path / "absent"
    result = main(
        arguments() + ["--live", "--accept-paid-traffic", "--artifact-dir", str(destination)]
    )
    assert result == 2
    output = capsys.readouterr().out
    assert "profile conflicts with ambient SDK configuration" in output
    assert "private-credential-do-not-print" not in output
    assert not destination.exists()


@pytest.mark.parametrize("name", ["DATABRICKS_HOST", "DATABRICKS_TOKEN"])
@pytest.mark.asyncio
async def test_http_profile_rejects_ambient_overrides_before_startup(
    name: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reject intentional pre-provider failures without opening an agent/client."""
    private_value = "private-host-or-credential-value"
    monkeypatch.setenv(name, private_value)
    original_import = builtins.__import__

    def reject_startup_import(module: str, *args: object, **kwargs: object) -> object:
        if module in {"uvicorn", "examples.framework_agent", "evalsurge"}:
            raise AssertionError("HTTP startup must not precede profile isolation")
        return original_import(module, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_startup_import)
    destination = tmp_path / "not-created"
    options = parse_options(
        arguments() + ["--live", "--accept-paid-traffic", "--artifact-dir", str(destination)]
    )
    with configured_environment({}), pytest.raises(ValueError) as failure:
        await execute(options)
    assert str(failure.value) == (
        "Live HTTP validation profile conflicts with ambient SDK configuration; "
        "use an isolated operator environment"
    )
    assert private_value not in str(failure.value)
    assert os.environ[name] == private_value
    assert not destination.exists()


def test_http_profile_checks_installed_sdk_authentication_metadata() -> None:
    """Read real SDK metadata only, never resolve credentials or invoke a model."""
    from databricks.sdk.core import Config

    names = {
        name
        for attribute in Config.attributes()
        if attribute.auth
        for name in [attribute.env, *attribute.env_aliases]
        if name
    }
    assert names
    for name in names:
        with (
            configured_environment({name: "private-sdk-credential"}),
            pytest.raises(ValueError) as failure,
        ):
            _validate_http_profile_environment()
        assert "private-sdk-credential" not in str(failure.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("shutdown_fails", [False, True])
async def test_server_cleanup_closes_listener_and_preserves_failure(shutdown_fails: bool) -> None:
    """Exercise owned task/socket cleanup only, not agent or provider behavior."""
    server = SimpleNamespace(should_exit=False)
    listener = socket.socket()
    record = {"passed": True}

    async def serving_task() -> None:
        if shutdown_fails:
            raise RuntimeError("private shutdown detail")

    task = asyncio.create_task(serving_task())
    if shutdown_fails:
        with pytest.raises(RuntimeError):
            await _close_framework_server(server, task, listener, record)
        assert record["passed"] is False
        assert record["framework_server_closed"] is False
        assert record["cleanup_error"] == "framework_server_shutdown_failed"
        assert "private shutdown detail" not in json.dumps(record)
    else:
        await _close_framework_server(server, task, listener, record)
        assert record["framework_server_closed"] is True
    assert server.should_exit is True
    assert listener.fileno() == -1


@pytest.mark.asyncio
async def test_app_cleanup_has_no_local_server() -> None:
    record = {"passed": True}
    await _close_framework_server(None, None, None, record)
    assert record == {"passed": True, "framework_server_closed": True}
