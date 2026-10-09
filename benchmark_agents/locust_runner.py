"""Isolated Locust subprocess with durable partial-result recovery."""

import asyncio
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Literal

from .configuration import environment as operator_environment
from .connections import Connection, resolve_connection, validate_connection
from .models import Load, PreflightError, PreflightResult, RunRequest
from .runner import summarize
from .storage import atomic_json, recover_rows


def preflight_result(rows: list[dict[str, Any]], summary: dict[str, Any]) -> PreflightResult:
    """Reduce one worker attempt to content-free, provider-independent diagnostics.

    Args:
        rows: Recovered probe journal; exactly one complete success is required.
        summary: Worker lifecycle summary, including cancellation/completeness.

    Returns:
        Probe status and safe error guidance. Raw exception text, outputs, target
        URLs, and credential values are never copied into this public result.
    """
    row = rows[0] if rows else {}
    result = PreflightResult(
        request_id=row.get("request_id"),
        latency_ms=row.get("latency_ms"),
        http_status=row.get("http_status"),
    )
    if summary.get("load_status") == "cancelled":
        result.status = "cancelled"
        return result
    if summary.get("load_status") == "interrupted":
        result.status = "interrupted"
    elif (
        len(rows) == 1
        and row.get("success")
        and summary.get("measurement_complete")
        and summary.get("worker_exit_code") == 0
    ):
        result.status = "passed"
        return result
    else:
        result.status = "failed"
    error_type = row.get("error")
    if result.status == "interrupted" or not row or summary.get("worker_exit_code") not in {0, 1}:
        code, guidance = "worker_failed", "The inference-check worker did not finish."
    elif row.get("error_phase") == "authentication":
        code, guidance = "authentication_failed", "Check the server-owned target credentials."
    elif row.get("http_status") in {401, 403}:
        code, guidance = (
            "authentication_failed",
            "The target rejected authentication or authorization. Check the operator-owned "
            "credentials and the selected identity's endpoint permissions.",
        )
    elif row.get("http_status") in {400, 422}:
        code, guidance = (
            "target_http_error",
            "The target rejected the first case input. Check its schema and the selected "
            "invocation protocol; unsupported fields must be explicitly mapped by your endpoint.",
        )
    elif row.get("http_status") is not None and not 200 <= row["http_status"] < 300:
        code, guidance = "target_http_error", "Check target access and endpoint configuration."
    elif row.get("deadline_exceeded") or error_type in {
        "TimeoutError",
        "Timeout",
        "ReadTimeout",
        "ConnectTimeout",
    }:
        code, guidance = "target_timeout", "The agent exceeded the request deadline."
    elif error_type in {"ConnectionError", "SSLError"}:
        code, guidance = "target_connection_error", "The agent connection failed."
    elif row.get("error_phase") == "response":
        code, guidance = (
            "invalid_response",
            "The agent did not return a valid, completed nonempty JSON answer. Check the selected "
            "endpoint contract, completion status, and returned trace/token evidence.",
        )
    elif error_type == "InvalidInput":
        code, guidance = (
            "invalid_stream",
            "The selected invocation protocol could not encode the first case input. "
            "Check its query/messages contract; use http-json or an explicit endpoint mapping "
            "for custom input fields. No target invocation was dispatched.",
        )
    elif row.get("error_phase") in {"request", "stream"}:
        code, guidance = (
            "invalid_stream",
            "The agent did not return a complete, nonempty answer stream. Check agent/model configuration.",
        )
    else:
        code, guidance = "worker_failed", "The inference-check worker failed."
    result.error = PreflightError(
        code=code, message=f"Inference preflight failed. Load test did not start. {guidance}"
    )
    return result


async def run_preflight(
    request: RunRequest,
    run_id: str,
    cancel: asyncio.Event,
    artifact_dir: Path,
    *,
    connection: Connection | None = None,
) -> PreflightResult:
    """Check the first case once using the production Locust engine before load.

    Args:
        request: Original target, workload, and per-request timeout.
        run_id: Run correlation identifier; retained for the separate probe.
        cancel: API-owned cancellation event; no retries or fallback are performed.
        artifact_dir: Operator-owned root; probe journals live under preflights/.
        connection: Optional prevalidated operator binding shared with measured load.

    Returns:
        A safe result. Only passed permits measured load; cancellation/interruption
        also stop the run. An already-cancelled check sends no request.

    Raises:
        OSError: Worker creation or artifact persistence fails.
        ValueError: The operator-owned connection is invalid.

    This is an extra invocation that can incur provider cost and execute agent tools.
    Its captures are protected artifacts, never benchmark rows or quality samples.
    Selected judges may reuse the capture for excluded readiness assessments.
    Worker startup has the same bounded grace as load; duration limits dispatch.
    """
    if cancel.is_set():
        return PreflightResult(status="cancelled")
    probe = request.model_copy(
        update={
            "evaluation": request.evaluation.model_copy(
                update={"samples": request.evaluation.samples[:1]}
            ),
            "load": Load(
                concurrency=1,
                duration_seconds=5,
                max_requests=1,
                timeout_seconds=request.load.timeout_seconds,
            ),
        }
    )
    rows, summary = await run_load(
        probe,
        run_id,
        cancel,
        artifact_dir=artifact_dir / "preflights",
        phase="preflight",
        connection=connection,
    )
    result = preflight_result(rows, summary)
    atomic_json(artifact_dir / "preflights" / run_id / "preflight.json", result.model_dump())
    return result


async def run_load(
    request: RunRequest,
    run_id: str,
    cancel: asyncio.Event,
    artifact_dir: Path | None = None,
    *,
    phase: Literal["load", "preflight"] = "load",
    connection: Connection | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the production Locust subprocess and recover its request measurements.

    Args:
        request: Validated endpoint, workload, and closed-loop load limits.
        run_id: Unique identifier used for a new artifact subdirectory.
        cancel: API-owned event; setting it requests dispatch stop and active drain.
        artifact_dir: Storage root, defaulting to BENCHMARK_ARTIFACT_DIR or artifacts.
        phase: Worker ownership label; preflight uses a separate artifact root.
        connection: Optional trusted exact binding; never a resolved secret.

    Returns:
        Recovered request rows and a summary with independent load status,
        worker exit code, and measurement completeness.

    Raises:
        FileExistsError: This run's artifact directory already exists.
        ValueError: The target's server-owned connection is invalid.
        OSError: Artifact writes or subprocess creation fail.

    Configuration and connection metadata are persisted before launch. A bounded
    outer deadline terminates and, if needed, kills an unresponsive worker. Missing
    worker results use diagnostic parent-observed timing, not comparable load timing.
    """
    root = (
        artifact_dir or Path(os.getenv("BENCHMARK_ARTIFACT_DIR", "artifacts"))
    ).resolve() / run_id
    root.mkdir(parents=True, exist_ok=False)
    config_path, result_path, cancel_path = [
        root / name for name in ("config.json", "result.json", "cancel")
    ]
    atomic_json(config_path, request.model_dump(mode="json"))
    binding = (
        validate_connection(request.target, connection)
        if connection is not None
        else resolve_connection(request.target)
    )
    atomic_json(root / "connection.json", binding.model_dump())
    if cancel.is_set():
        cancel_path.touch(exist_ok=True)
    environment = {
        **operator_environment(),
        "BENCHMARK_LOCUST_CONFIG": str(config_path),
        "BENCHMARK_LOCUST_RESULT": str(result_path),
        "BENCHMARK_LOCUST_CANCEL": str(cancel_path),
        "BENCHMARK_RUN_ID": run_id,
    }
    started = time.monotonic()
    with (root / "locust.log").open("wb") as log:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "locust",
            "-f",
            str(Path(__file__).with_name("locustfile.py")),
            "--headless",
            "--users",
            str(request.load.concurrency),
            "--spawn-rate",
            str(request.load.concurrency),
            "--host",
            str(request.target.url),
            "--stop-timeout",
            str(math.ceil(request.load.timeout_seconds + 5)),
            "--only-summary",
            "--skip-log-setup",
            env=environment,
            stdout=log,
            stderr=asyncio.subprocess.STDOUT,
        )
        deadline = started + request.load.duration_seconds + request.load.timeout_seconds + 45
        expired = False
        try:
            atomic_json(root / "worker.json", {"pid": process.pid, "phase": phase})
            while process.returncode is None:
                if cancel.is_set():
                    cancel_path.touch(exist_ok=True)
                if time.monotonic() > deadline:
                    expired = True
                    break
                await asyncio.sleep(0.05)
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except TimeoutError:
                    process.kill()
                    await process.wait()
    rows, incomplete = recover_rows(root)
    if result_path.exists():
        summary = json.loads(result_path.read_text())["summary"]
    else:
        summary = summarize(rows, max(time.monotonic() - started, 0.001), 0)
        summary.update(
            engine="locust",
            configured_concurrency=request.load.concurrency,
            observed_peak_in_flight=None,
            dispatched_requests=len(rows),
        )
    summary.update(
        incomplete_measurements=incomplete,
        worker_exit_code=process.returncode,
        worker_timed_out=expired,
    )
    summary["load_status"] = (
        "interrupted"
        if expired or incomplete or not result_path.exists() or process.returncode not in {0, 1}
        else "cancelled"
        if cancel.is_set()
        else "completed"
    )
    summary["measurement_complete"] = (
        result_path.exists() and not incomplete and not expired and process.returncode in {0, 1}
    )
    atomic_json(root / "recovered.json", {"rows": rows, "summary": summary})
    return rows, summary
