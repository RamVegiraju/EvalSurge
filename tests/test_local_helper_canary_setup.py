"""Safe local-canary setup failures only; no agent or model execution.

Metadata/source setup failures use explicit exception-only mocks. No successful
agent, provider transport, framework result or model completion is substituted.
"""

import argparse
import json
import logging
import os
from collections.abc import Iterator
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Any

import pytest

from benchmark_agents.storage import atomic_json
from scripts.validation import local_helper_canary as canary

PRIVATE_MARKER = "setup-only-private-error-sentinel"


@pytest.fixture(autouse=True)
def restore_canary_process_configuration() -> Iterator[None]:
    """Restore CLI-owned logger/telemetry settings in this borrowed test process."""
    previous_logging = logging.root.manager.disable
    previous_environment = {
        name: os.environ.get(name) for name in ("CREWAI_DISABLE_TELEMETRY", "OTEL_SDK_DISABLED")
    }
    try:
        yield
    finally:
        logging.disable(previous_logging)
        for name, value in previous_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def options(directory: Path, *, framework: str = "crewai") -> argparse.Namespace:
    """Build structural selections; no profile, client or model is resolved."""
    return argparse.Namespace(
        framework=framework,
        model="system.ai.gpt-oss-120b",
        api="mlflow-responses",
        profile="not-resolved-setup-only-profile",
        workspace_host="https://selected-workspace.cloud.databricks.com",
        artifact_dir=directory,
        live=True,
        accept_paid_traffic=True,
    )


def forbid_agent_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if setup rejection reaches real agent/client construction."""

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Setup failure must precede agent or model startup")

    monkeypatch.setattr(canary, "create_real_app", forbidden)


def assert_safe_failed_receipt(directory: Path, returned: dict[str, Any], error: str) -> None:
    """Compare native protected storage and content-free setup failure metadata."""
    receipt_path = directory / "receipt.json"
    assert receipt_path.is_file()
    encoded = receipt_path.read_text()
    stored = json.loads(encoded)
    assert stored == returned
    assert stored["passed"] is False
    assert stored["failure_type"] == error
    assert stored["failure_phase"] == "setup"
    assert stored["model_transport_evidence"] == {
        "outbound_attempts": 0,
        "completed_responses": 0,
    }
    assert stored["agent_started"] is False
    assert "run_id" not in stored
    assert "metrics" not in stored
    assert "preflight" not in stored
    assert PRIVATE_MARKER not in encoded
    assert receipt_path.stat().st_mode & 0o777 == 0o600
    assert directory.stat().st_mode & 0o777 == 0o700
    assert {path.name for path in directory.iterdir()} == {"receipt.json"}


@pytest.mark.parametrize("error_type", [PackageNotFoundError, RuntimeError])
async def test_optional_framework_metadata_failure_is_retained_safely(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    error_type: type[Exception],
) -> None:
    """Only distribution lookup raises; actual model/framework startup is forbidden."""
    native_version = canary.version
    seen: list[str] = []

    def failed_optional_metadata(name: str) -> str:
        seen.append(name)
        if name == "crewai":
            raise error_type(PRIVATE_MARKER)
        return native_version(name)

    monkeypatch.setattr(canary, "version", failed_optional_metadata)
    forbid_agent_startup(monkeypatch)
    directory = tmp_path / "metadata-failure"
    result = await canary.execute(options(directory))
    assert_safe_failed_receipt(directory, result, error_type.__name__)
    assert seen == ["openai", "databricks-sdk", "locust", "mlflow", "crewai"]
    assert "crewai" not in result["versions"]
    assert "sample_sha256" not in result
    output = capsys.readouterr()
    assert PRIVATE_MARKER not in output.out + output.err


async def test_source_read_failure_is_retained_before_agent_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Only reading sample source raises; no framework code/provider is executed."""
    native_read_bytes = Path.read_bytes

    def failed_source_read(path: Path) -> bytes:
        if path == Path("examples/real_framework_agent.py"):
            raise OSError(PRIVATE_MARKER)
        return native_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", failed_source_read)
    forbid_agent_startup(monkeypatch)
    directory = tmp_path / "source-failure"
    result = await canary.execute(options(directory, framework="langgraph"))
    assert_safe_failed_receipt(directory, result, "OSError")
    assert set(result["versions"]) == {
        "openai",
        "databricks-sdk",
        "locust",
        "mlflow",
        "langgraph",
    }
    assert "sample_sha256" not in result
    output = capsys.readouterr()
    assert PRIVATE_MARKER not in output.out + output.err


async def test_app_construction_failure_is_retained_without_listener_or_inference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exception-only app factory; no fabricated app or successful agent result."""

    def failed_app_construction(*args: Any, **kwargs: Any) -> Any:
        raise ImportError(PRIVATE_MARKER)

    monkeypatch.setattr(canary, "create_real_app", failed_app_construction)
    directory = tmp_path / "construction-failure"
    result = await canary.execute(options(directory, framework="langgraph"))
    assert_safe_failed_receipt(directory, result, "ImportError")
    assert len(result["sample_sha256"]) == 64
    output = capsys.readouterr()
    assert PRIVATE_MARKER not in output.out + output.err


def test_cli_missing_optional_framework_returns_safe_json_and_exit_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exercise the actual CLI with a metadata-only pre-provider failure."""
    native_version = canary.version

    def missing_optional_metadata(name: str) -> str:
        if name == "crewai":
            raise PackageNotFoundError(PRIVATE_MARKER)
        return native_version(name)

    monkeypatch.setattr(canary, "version", missing_optional_metadata)
    forbid_agent_startup(monkeypatch)
    directory = tmp_path / "cli-failure"
    with pytest.raises(SystemExit) as stopped:
        canary.main(
            [
                "--framework",
                "crewai",
                "--profile",
                "not-resolved-setup-only-profile",
                "--workspace-host",
                "https://selected-workspace.cloud.databricks.com",
                "--model",
                "system.ai.gpt-oss-120b",
                "--api",
                "mlflow-responses",
                "--artifact-dir",
                str(directory),
                "--live",
                "--accept-paid-traffic",
            ]
        )
    assert stopped.value.code == 1
    output = capsys.readouterr()
    assert PRIVATE_MARKER not in output.out + output.err
    assert "Traceback" not in output.out + output.err
    returned = json.loads(output.out)
    assert_safe_failed_receipt(directory, returned, "PackageNotFoundError")


async def test_existing_failure_receipt_is_never_replaced_or_replayed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Retain a native setup-only fixture receipt, not historical live evidence."""
    directory = tmp_path / "retained"
    directory.mkdir(mode=0o700)
    receipt_path = directory / "receipt.json"
    original = {"passed": False, "failure_type": "PriorSetupFailure"}
    atomic_json(receipt_path, original)
    original_bytes = receipt_path.read_bytes()
    forbid_agent_startup(monkeypatch)
    with pytest.raises(ValueError, match="fresh empty protected storage"):
        await canary.execute(options(directory))
    assert receipt_path.read_bytes() == original_bytes
