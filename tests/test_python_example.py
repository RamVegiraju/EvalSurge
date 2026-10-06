"""Exercise the documented Python example through actual CLI and Locust processes."""

import asyncio
import json
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("mode,exit_code", [("normal", 0), ("denied", 1)])
async def test_python_benchmark_cli_saves_success_or_preflight_failure(
    endpoint: tuple[str, dict], tmp_path: Path, mode: str, exit_code: int
) -> None:
    """The CLI honors bounded load settings and retains a readable terminal report."""
    base_url, server = endpoint
    artifact_dir = tmp_path / "python-example"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "scripts.validation.python_benchmark",
        "--url",
        f"{base_url}/{mode}",
        "--duration",
        "0.25",
        "--concurrency",
        "2",
        "--max-requests",
        "100",
        "--request-timeout",
        "2",
        "--artifact-dir",
        str(artifact_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    assert process.returncode == exit_code, stderr.decode()
    summary = json.loads(stdout)
    report_path = Path(summary["report_file"])
    assert report_path.parent == artifact_dir
    report = json.loads(report_path.read_text())
    config = report["run"]["config"]
    assert config["load"]["duration_seconds"] == 0.25
    assert config["load"]["concurrency"] == 2
    assert config["load"]["max_requests"] == 100
    assert config["load"]["timeout_seconds"] == 2
    assert config["evaluation"]["scorers"] == []
    assert config["evaluation"]["registered_scorers"] == []
    assert summary["run_id"] == report["run"]["id"]
    assert summary["status"] == report["run"]["status"]
    assert "private provider failure" not in stdout.decode() + stderr.decode()
    if exit_code == 0:
        assert report["run"]["preflight"]["status"] == "passed"
        assert summary["metrics"]["successful_requests"] == summary["metrics"]["requests"] > 0
        assert summary["metrics"]["dispatch_seconds"] <= 0.25
        assert server["received"] == summary["metrics"]["requests"] + 1
    else:
        assert report["run"]["preflight"]["status"] == "failed"
        assert report["run"]["load_status"] == "skipped"
        assert report["total"] == 0
        assert server["received"] == 1


def test_default_python_example_allows_a_three_minute_dispatch_window() -> None:
    """The default request budget must not remain the facade's short 100-request cap."""
    from scripts.validation.python_benchmark import parse_options

    options = parse_options([])
    assert options.duration == 180
    assert options.concurrency == 2
    assert options.max_requests == 10_000
