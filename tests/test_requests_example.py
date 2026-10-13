"""Exercise the requests CLI over real Uvicorn sockets and the existing Locust engine."""

import asyncio
import json
import os
import signal
import socket
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import requests
import uvicorn
from fastapi import Request

from benchmark_agents.api import create_app


@pytest.fixture
async def requests_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Own an authenticated localhost API, its traffic log, storage, and shutdown."""
    monkeypatch.setenv("BENCHMARK_API_KEY", "requests-example-test-key")
    monkeypatch.setenv("BENCHMARK_CONNECTIONS", "{}")
    monkeypatch.setenv("BENCHMARK_ALLOWED_TARGETS", "[]")
    app = create_app(tmp_path / "requests-api")
    observed: dict[str, Any] = {"traffic": [], "poll_delay": 0.0, "submit_delay": 0.0}

    @app.middleware("http")
    async def capture(request: Request, call_next: Any) -> Any:
        observed["traffic"].append(
            {
                "method": request.method,
                "path": request.url.path,
                "query": request.url.query,
                "key": request.headers.get("X-API-Key"),
                "idempotency": request.headers.get("Idempotency-Key"),
            }
        )
        if request.method == "GET" and request.url.path.startswith("/v1/runs/"):
            await asyncio.sleep(observed["poll_delay"])
        if request.method == "POST" and request.url.path == "/v1/runs":
            await asyncio.sleep(observed["submit_delay"])
        return await call_next(request)

    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{connection.getsockname()[1]}"
        server = uvicorn.Server(
            uvicorn.Config(app, log_level="warning", proxy_headers=False, access_log=False)
        )
        serving = asyncio.create_task(server.serve(sockets=[connection]))
        try:
            for _ in range(200):
                if server.started:
                    break
                if serving.done():
                    serving.result()
                await asyncio.sleep(0.01)
            assert server.started, "Local API did not start"
            yield url, observed
        finally:
            server.should_exit = True
            await asyncio.wait_for(serving, timeout=30)


async def run_cli(arguments: list[str], *, api_key: str | None = None) -> tuple[int, str, str]:
    """Run the real requests example as a bounded child process and always reap it.

    Args:
        arguments: CLI flags targeting only test-owned localhost servers.
        api_key: Optional test-only key override, isolated from the API process.

    Returns:
        Exit code, stdout, and stderr after at most 35 seconds.

    Raises:
        TimeoutError: The child does not finish within the test deadline.
    """
    environment = os.environ.copy()
    if api_key is not None:
        environment["BENCHMARK_API_KEY"] = api_key
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "scripts.validation.python_requests_benchmark",
        *arguments,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=35)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    assert process.returncode is not None
    return process.returncode, stdout.decode(), stderr.decode()


def get_json(url: str, method: str = "GET") -> dict[str, Any]:
    """Read test-owned API JSON with actual requests, no ambient proxies or retries."""
    with requests.Session() as session:
        session.trust_env = False
        response = session.request(
            method,
            url,
            headers={"X-API-Key": "requests-example-test-key"},
            timeout=(1, 3),
            allow_redirects=False,
        )
        response.raise_for_status()
        return response.json()


@pytest.mark.parametrize("mode,exit_code", [("normal", 0), ("denied", 1)])
async def test_requests_cli_real_api_locust_and_safe_preflight(
    requests_api: tuple[str, dict[str, Any]],
    endpoint: tuple[str, dict[str, Any]],
    mode: str,
    exit_code: int,
) -> None:
    """A single submission includes an excluded probe and never retries failed inference."""
    api_url, observed = requests_api
    target_url, target = endpoint
    code, stdout, stderr = await run_cli(
        [
            "--api-url",
            api_url,
            "--target-url",
            f"{target_url}/{mode}",
            "--duration",
            "0.5",
            "--concurrency",
            "1",
            "--max-requests",
            "2",
            "--wait-timeout",
            "30",
        ]
    )
    assert code == exit_code, stderr
    submissions = [item for item in observed["traffic"] if item["method"] == "POST"]
    assert len(submissions) == 1 and submissions[0]["path"] == "/v1/runs"
    assert submissions[0]["idempotency"]
    assert f"Idempotency-Key: {submissions[0]['idempotency']}" in stderr
    assert all(item["key"] == "requests-example-test-key" for item in observed["traffic"])
    assert all(not item["query"] for item in observed["traffic"])
    assert "requests-example-test-key" not in stdout + stderr
    assert "private provider failure" not in stdout + stderr
    report_url = stdout.split("Report URL: ", 1)[1].splitlines()[0]
    run_id = report_url.split("?run=", 1)[1]
    report = await asyncio.to_thread(get_json, f"{api_url}/v1/runs/{run_id}/report")
    run = report["run"]
    assert report_url == f"{api_url}/reports/?run={run_id}"
    assert run["config"]["evaluation"]["scorers"] == []
    assert run["config"]["evaluation"]["registered_scorers"] == []
    assert len(run["config"]["evaluation"]["samples"]) == 1
    assert run["config"]["load"]["duration_seconds"] == 0.5
    assert run["config"]["load"]["max_requests"] == 2
    if exit_code == 0:
        assert run["status"] == "completed"
        assert run["preflight"]["status"] == "passed"
        assert run["metrics"]["successful_requests"] == report["total"] == 2
        assert target["received"] == 3
        assert run["evaluation_status"] == "no_ready_scorers"
        assert "Status: completed" in stdout
    else:
        assert run["status"] == run["preflight"]["status"] == "failed"
        assert run["load_status"] == run["evaluation_status"] == "skipped"
        assert report["total"] == 0 and run["metrics"] == {}
        assert target["received"] == 1
        assert run["preflight"]["error"]["code"] == "authentication_failed"
        assert "authentication_failed" in stderr
        assert run["preflight"]["error"]["message"] in stderr
        assert run["preflight"]["request_id"] in stderr


async def test_requests_cli_full_request_file_is_not_overridden(
    requests_api: tuple[str, dict[str, Any]],
    endpoint: tuple[str, dict[str, Any]],
    tmp_path: Path,
) -> None:
    """The complete JSON contract retains explicit target, references, policy, and bounds."""
    api_url, _ = requests_api
    target_url, target = endpoint
    body = {
        "target": {"url": f"{target_url}/json", "adapter": "http-json", "request_usage": False},
        "evaluation": {
            "description": "Explicit performance-only request-file fixture",
            "scorers": [],
            "registered_scorers": [],
            "samples": [
                {
                    "inputs": {"query": "Use this exact input", "custom": [1, 2]},
                    "expectations": {"expected_response": "Answer—yes"},
                }
            ],
            "max_scored_requests": 2,
            "sampling_seed": 7,
        },
        "load": {
            "duration_seconds": 0.5,
            "concurrency": 1,
            "max_requests": 2,
            "timeout_seconds": 2,
        },
    }
    request_file = tmp_path / "request.json"
    request_file.write_text(json.dumps(body), encoding="utf-8")
    code, stdout, stderr = await run_cli(
        ["--api-url", api_url, "--request-file", str(request_file), "--wait-timeout", "30"]
    )
    assert code == 0, stderr
    run_id = stdout.split("?run=", 1)[1].splitlines()[0]
    run = await asyncio.to_thread(get_json, f"{api_url}/v1/runs/{run_id}")
    assert run["config"]["evaluation"] == {
        **body["evaluation"],
        "agent_manifest": None,
    }
    assert run["config"]["load"] == body["load"]
    assert run["config"]["target"]["adapter"] == "http-json"
    assert target["bodies"] == [body["evaluation"]["samples"][0]["inputs"]] * 3


@pytest.mark.parametrize("failure,status", [("auth", 401), ("validation", 422)])
async def test_requests_cli_exposes_only_safe_api_error_envelope(
    requests_api: tuple[str, dict[str, Any]],
    endpoint: tuple[str, dict[str, Any]],
    tmp_path: Path,
    failure: str,
    status: int,
) -> None:
    """Real authorization/validation errors expose safe correlation, never input values."""
    api_url, observed = requests_api
    target_url, target = endpoint
    arguments = ["--api-url", api_url, "--target-url", f"{target_url}/normal"]
    if failure == "validation":
        request_file = tmp_path / "invalid.json"
        request_file.write_text('{"private-input":"DO-NOT-ECHO"}', encoding="utf-8")
        arguments = ["--api-url", api_url, "--request-file", str(request_file)]
    code, stdout, stderr = await run_cli(
        arguments, api_key="wrong-test-key" if failure == "auth" else None
    )
    assert code == 1
    assert f"API HTTP {status}" in stderr
    assert '"request_id":' in stderr
    assert '"code":' in stderr
    assert "DO-NOT-ECHO" not in stdout + stderr
    assert target["received"] == 0
    assert len(observed["traffic"]) == 1


@pytest.mark.parametrize("network_timeout", [False, True])
async def test_requests_cli_wait_and_network_timeouts_do_not_retry_or_cancel(
    requests_api: tuple[str, dict[str, Any]],
    endpoint: tuple[str, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    network_timeout: bool,
) -> None:
    """Waiting and HTTP inactivity have distinct errors; neither changes server ownership."""
    from scripts.validation import python_requests_benchmark as example

    api_url, observed = requests_api
    target_url, _ = endpoint
    if network_timeout:
        observed["poll_delay"] = 3.0
        monkeypatch.setattr(example, "READ_TIMEOUT_SECONDS", 2.0)
    code = await asyncio.to_thread(
        example.main,
        [
            "--api-url",
            api_url,
            "--target-url",
            f"{target_url}/normal",
            "--duration",
            "0.5",
            "--max-requests",
            "2",
            "--wait-timeout",
            "10" if network_timeout else "0.2",
        ],
    )
    output = capsys.readouterr()
    assert code == 1
    assert ("API network timeout" if network_timeout else "Overall wait timeout") in output.err
    assert "no cancellation was sent" in output.err
    assert "Report URL:" in output.out
    posts = [item for item in observed["traffic"] if item["method"] == "POST"]
    assert [item["path"] for item in posts] == ["/v1/runs"]
    observed["poll_delay"] = 0.0
    run_id = output.out.split("?run=", 1)[1].splitlines()[0]
    run = await asyncio.to_thread(get_json, f"{api_url}/v1/runs/{run_id}")
    assert run["status"] not in {"cancelled", "interrupted"}


@pytest.mark.parametrize("terminal_status", ["cancelled", "interrupted"])
async def test_requests_cli_returns_nonzero_for_real_terminal_load_outcomes(
    requests_api: tuple[str, dict[str, Any]],
    endpoint: tuple[str, dict[str, Any]],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    terminal_status: str,
) -> None:
    """Operator cancellation and a killed owned Locust worker are not successful exits."""
    from scripts.validation import python_requests_benchmark as example

    api_url, observed = requests_api
    target_url, target = endpoint
    running = asyncio.create_task(
        asyncio.to_thread(
            example.main,
            [
                "--api-url",
                api_url,
                "--target-url",
                f"{target_url}/normal",
                "--duration",
                "2",
                "--concurrency",
                "1",
                "--max-requests",
                "10",
                "--wait-timeout",
                "30",
            ],
        )
    )
    try:
        for _ in range(1000):
            if target["received"] >= 2:
                break
            if running.done():
                pytest.fail(f"CLI stopped before measured load: {running.result()}")
            await asyncio.sleep(0.01)
        assert target["received"] >= 2, "Preflight and one measured attempt must really run"
        polls = [item for item in observed["traffic"] if item["method"] == "GET"]
        run_id = polls[-1]["path"].rsplit("/", 1)[1]
        if terminal_status == "cancelled":
            await asyncio.to_thread(get_json, f"{api_url}/v1/runs/{run_id}/cancel", "POST")
        else:
            worker = json.loads((tmp_path / "requests-api" / run_id / "worker.json").read_text())
            os.kill(worker["pid"], signal.SIGKILL)
        assert await asyncio.wait_for(asyncio.shield(running), timeout=30) == 1
        output = capsys.readouterr()
        assert f"Status: {terminal_status}" in output.out
        assert f"Run ended {terminal_status}." in output.err
        run = await asyncio.to_thread(get_json, f"{api_url}/v1/runs/{run_id}")
        assert run["status"] == run["load_status"] == terminal_status
        assert run["preflight"]["status"] == "passed"
        assert run["evaluation_status"] == "skipped"
        if terminal_status == "interrupted":
            assert "Load error:" in output.err
            for field in ("code", "message", "guidance"):
                assert run["load_error"][field] in output.err
    finally:
        if not running.done():
            await asyncio.wait_for(asyncio.shield(running), timeout=35)


async def test_requests_cli_connection_failure_is_safe(
    endpoint: tuple[str, dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    """A real unlistened local API port does not leak transport exception details."""
    from scripts.validation import python_requests_benchmark as example

    target_url, target = endpoint
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        api_url = f"http://127.0.0.1:{reservation.getsockname()[1]}"
        code = await asyncio.to_thread(
            example.main,
            [
                "--api-url",
                api_url,
                "--target-url",
                f"{target_url}/normal",
                "--wait-timeout",
                "0.5",
            ],
        )
    output = capsys.readouterr()
    assert code == 1
    assert "API transport failed" in output.err or "Overall wait timeout" in output.err
    assert api_url not in output.err and "HTTPConnectionPool" not in output.err
    assert "no cancellation was sent" in output.err
    assert target["received"] == 0


def test_requests_example_defaults_and_invalid_inputs() -> None:
    """Five-minute performance defaults are bounded; invalid waits fail before submission."""
    from scripts.validation.python_requests_benchmark import parse_options

    options = parse_options(["--target-url", "http://127.0.0.1:9001/chat"])
    assert options.duration == 300
    assert options.concurrency == 5
    assert options.max_requests == 5000
    assert options.http_read_timeout == 30
    for invalid in ("0", "-1", "nan", "inf"):
        with pytest.raises(SystemExit):
            parse_options(["--target-url", "http://127.0.0.1:9001/chat", "--wait-timeout", invalid])
        with pytest.raises(SystemExit):
            parse_options(
                [
                    "--target-url",
                    "http://127.0.0.1:9001/chat",
                    "--http-read-timeout",
                    invalid,
                ]
            )
    for invalid in (
        "http://user:secret@localhost:8000",
        "http://localhost:8000?key=secret",
        "http://localhost:8000#secret",
        "http://localhost:8000/?",
        "http://remote.example:8000",
    ):
        with pytest.raises(SystemExit):
            parse_options(["--target-url", "http://127.0.0.1:9001/chat", "--api-url", invalid])


@pytest.mark.parametrize("error_phase", ["preflight", "evaluation_preflight", "load_error"])
def test_terminal_diagnostics_preserve_phase_outcomes_and_safe_guidance(
    capsys: pytest.CaptureFixture[str], error_phase: str
) -> None:
    """Rendering a failed phase never changes a passed probe or exports extra error data."""
    from scripts.validation.python_requests_benchmark import terminal_result

    error = {
        "code": "fixture_error",
        "message": "Safe phase-specific failure.",
        "guidance": "Correct this phase before explicitly submitting another run.",
        "private": "DO-NOT-ECHO",
    }
    run: dict[str, Any] = {
        "status": "failed",
        "preflight": {"status": "passed", "request_id": "probe-id", "http_status": 200},
        "evaluation_preflight": {"status": "passed"},
        "load_error": None,
    }
    if error_phase == "load_error":
        run["load_error"] = error
    else:
        run[error_phase].update(status="failed", error=error)
    original = json.dumps(run, sort_keys=True)
    assert terminal_result(run) == 1
    output = capsys.readouterr()
    lines = output.err.splitlines()
    probe = json.loads(
        next(line.split(": ", 1)[1] for line in lines if line.startswith("Inference preflight:"))
    )
    assert probe["status"] == ("failed" if error_phase == "preflight" else "passed")
    label = {
        "preflight": "Inference preflight",
        "evaluation_preflight": "Evaluation preflight",
        "load_error": "Load error",
    }[error_phase]
    diagnostic = json.loads(
        next(line.split(": ", 1)[1] for line in lines if line.startswith(f"{label}:"))
    )
    assert (diagnostic if error_phase == "load_error" else diagnostic["error"]) == {
        field: error[field] for field in ("code", "message", "guidance")
    }
    assert "DO-NOT-ECHO" not in output.out + output.err
    assert json.dumps(run, sort_keys=True) == original


def test_completed_with_gaps_keeps_valid_report_and_warns_without_failed_probe(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Completion with gaps is a readable lifecycle result, not a quality pass or exit failure."""
    from scripts.validation.python_requests_benchmark import terminal_result

    run = {
        "status": "completed_with_gaps",
        "preflight": {"status": "passed"},
        "evaluation_preflight": {"status": "passed"},
    }
    assert terminal_result(run) == 0
    output = capsys.readouterr()
    assert "Status: completed_with_gaps" in output.out
    assert "Valid report available with gaps" in output.err
    assert "not a quality pass" in output.err
    assert "failed" not in output.err


async def test_requests_cli_real_evaluation_configuration_error_is_separate_from_inference(
    requests_api: tuple[str, dict[str, Any]],
    endpoint: tuple[str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsupported evaluation evidence fails through the real API without target/judge calls."""
    from scripts.validation.python_requests_benchmark import build_request, parse_options

    for name in ("BENCHMARK_JUDGE_MODEL", "DATABRICKS_CONFIG_PROFILE", "DATABRICKS_HOST"):
        monkeypatch.delenv(name, raising=False)
    api_url, observed = requests_api
    target_url, target = endpoint
    body = build_request(parse_options(["--target-url", f"{target_url}/normal"]))
    body["evaluation"]["scorers"] = ["groundedness"]
    request_file = tmp_path / "missing-evidence.json"
    request_file.write_text(json.dumps(body), encoding="utf-8")
    code, stdout, stderr = await run_cli(
        ["--api-url", api_url, "--request-file", str(request_file), "--wait-timeout", "30"]
    )
    assert code == 1
    run_id = stdout.split("?run=", 1)[1].splitlines()[0]
    run = await asyncio.to_thread(get_json, f"{api_url}/v1/runs/{run_id}")
    assert run["preflight"]["status"] == "not_run"
    assert run["evaluation_preflight"]["status"] == "failed"
    assert "Evaluation preflight:" in stderr
    for field in ("code", "message", "guidance"):
        assert run["evaluation_preflight"]["error"][field] in stderr
    assert target["received"] == 0
    assert len([item for item in observed["traffic"] if item["method"] == "POST"]) == 1


@pytest.mark.parametrize("read_timeout,exit_code", [(0.05, 1), (0.5, 0)])
async def test_requests_cli_http_read_budget_is_configurable_without_replay(
    requests_api: tuple[str, dict[str, Any]],
    endpoint: tuple[str, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    read_timeout: float,
    exit_code: int,
) -> None:
    """A delayed creation response honors the configured HTTP budget without replaying admission."""
    from scripts.validation import python_requests_benchmark as example

    api_url, observed = requests_api
    target_url, _ = endpoint
    observed["submit_delay"] = 0.15
    monkeypatch.setattr(example, "READ_TIMEOUT_SECONDS", 0.05)
    code = await asyncio.to_thread(
        example.main,
        [
            "--api-url",
            api_url,
            "--target-url",
            f"{target_url}/normal",
            "--duration",
            "0.5",
            "--concurrency",
            "1",
            "--max-requests",
            "2",
            "--wait-timeout",
            "30",
            "--http-read-timeout",
            str(read_timeout),
        ],
    )
    output = capsys.readouterr()
    assert code == exit_code, output.err
    assert [item["path"] for item in observed["traffic"] if item["method"] == "POST"] == [
        "/v1/runs"
    ]
    if exit_code:
        assert "API network timeout" in output.err
        assert "submission may have been accepted" in output.err
        assert "no cancellation was sent" in output.err
        assert "Report URL:" not in output.out
    else:
        assert "Report URL:" in output.out
        assert "Status: completed" in output.out
