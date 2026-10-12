"""Portable, bounded NON-agent localhost timing calibration; no model/provider calls.

This diagnostic uses the production Locust user and parent recovery, but owns only
an inert timing endpoint. It does not certify accuracy, benchmark agent capacity,
subtract calibration from metrics, or expose customer-target/profile selectors.
Server/load dependencies are imported only when explicitly running calibration.
"""

import asyncio
import json
import math
import os
import statistics
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4


def _validate_bounds(concurrency: int, max_requests: int, duration_seconds: float) -> None:
    """Reject nonfinite or oversized diagnostic bounds before starting resources."""
    if type(concurrency) is not int or not 1 <= concurrency <= 5:
        raise ValueError("Calibration concurrency must be an integer from 1 through 5")
    if type(max_requests) is not int or not 1 <= max_requests <= 200:
        raise ValueError("Calibration max_requests must be an integer from 1 through 200")
    if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, (int, float)):
        raise ValueError("Calibration duration_seconds must be a finite number")
    if not math.isfinite(duration_seconds) or not 0.1 <= duration_seconds <= 10:
        raise ValueError("Calibration duration_seconds must be from 0.1 through 10")


def _distribution(values: list[float]) -> dict[str, int | float | None]:
    """Return bounded descriptive millisecond observations, not accuracy thresholds."""
    ordered = sorted(values)
    return {
        "count": len(values),
        "mean_ms": statistics.mean(values) if values else None,
        "max_ms": max(values) if values else None,
        **{
            f"p{int(q * 100)}_ms": ordered[max(0, math.ceil(len(ordered) * q) - 1)]
            if ordered
            else None
            for q in (0.5, 0.95, 0.99)
        },
    }


def _worker_exit_observation(root: Path) -> dict[str, int | bool | None]:
    """Check only private, generated worker PIDs without sending a process signal.

    Args:
        root: Fresh calibration artifact root owned by this invocation.

    Returns:
        Number of recorded workers and whether all recorded Unix PIDs are absent.
        No receipts or unsupported platforms return unavailable, never success.

    PID reuse is possible; this instantaneous observation complements, rather than
    replaces, run_load's owned subprocess wait/termination lifecycle.
    """
    workers = [path / "worker.json" for path in root.iterdir() if path.is_dir()]
    pids = [json.loads(path.read_text())["pid"] for path in workers if path.exists()]
    if not pids or os.name != "posix":
        return {"recorded_worker_count": len(pids), "worker_pid_exit_observed": None}
    exited = True
    for pid in pids:
        if type(pid) is not int or pid <= 0:
            raise ValueError("Invalid private calibration worker receipt")
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        except PermissionError:
            pass
        exited = False
    return {"recorded_worker_count": len(pids), "worker_pid_exit_observed": exited}


class _TimingServer(ThreadingHTTPServer):
    """Native timing server with bounded records and owned non-daemon handlers."""

    daemon_threads = False
    block_on_close = True

    def __init__(self, record_limit: int = 402) -> None:
        if type(record_limit) is not int or not 1 <= record_limit <= 402:
            raise ValueError("Timing record limit must be an integer from 1 through 402")
        self.record_limit = record_limit
        self.records: dict[str, float] = {}
        self.received_ids: set[str] = set()
        self.record_lock = threading.Lock()
        self.active_handlers = 0
        super().__init__(("127.0.0.1", 0), _TimingHandler)

    def admit_request(self, request_id: str) -> bool:
        """Reserve one canonical correlation ID within the fixed timing budget.

        Args:
            request_id: UUID label supplied by the production worker.

        Returns:
            Whether the ID is canonical, unique and within this endpoint's limit.

        Side Effects:
            Keeps a bounded set under a native lock. Correlation is not caller
            authentication; this localhost diagnostic is not a hosted service.
        """
        try:
            canonical = str(UUID(request_id))
        except (ValueError, AttributeError):
            return False
        if canonical != request_id:
            return False
        with self.record_lock:
            if request_id in self.received_ids or len(self.received_ids) >= self.record_limit:
                return False
            self.received_ids.add(request_id)
        return True


class _TimingHandler(BaseHTTPRequestHandler):
    """Explicitly NOT an agent: return a timing marker after native 25 ms sleep."""

    protocol_version = "HTTP/1.1"

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(2)
        with self.server.record_lock:
            self.server.active_handlers += 1

    def finish(self) -> None:
        try:
            super().finish()
        finally:
            with self.server.record_lock:
                self.server.active_handlers -= 1

    def do_POST(self) -> None:
        """Record independent service duration for the exact request correlation ID."""
        began = time.perf_counter()
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if self.path != "/NON-agent-timing-only" or not 0 < size <= 1024:
            self.send_error(400)
            return
        try:
            body = json.loads(self.rfile.read(size))
        except (ValueError, UnicodeDecodeError, TimeoutError):
            self.send_error(400)
            return
        request_id = self.headers.get("X-Benchmark-Request-ID", "")
        if (
            not isinstance(body, dict)
            or set(body) != {"timing_only"}
            or body["timing_only"] is not True
            or not self.server.admit_request(request_id)
        ):
            self.send_error(400)
            return
        time.sleep(0.025)
        reply = b'{"outputs":"NON-agent-timing-marker"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)
        self.wfile.flush()
        elapsed_ms = (time.perf_counter() - began) * 1000
        with self.server.record_lock:
            self.server.records[request_id] = elapsed_ms

    def log_message(self, *args: Any) -> None:
        """Suppress inert endpoint request logs; no input/output content is exported."""


async def _close_timing_server(
    server: _TimingServer, thread: threading.Thread
) -> asyncio.CancelledError | None:
    """Await owned native close despite repeated cancellation of the caller.

    Args:
        server: This invocation's inert, socket-timeout-bounded localhost server.
        thread: Its owned serve_forever thread, already started.

    Returns:
        A cancellation observed during cleanup, to propagate after the receipt.

    Raises:
        OSError: Native server shutdown/close fails.

    Side Effects:
        One native task shuts down the server, joins non-daemon handlers and joins
        the serving thread. It is never detached on caller cancellation. There is
        no model, target or authentication work and no hard syscall deadline.
    """

    def close() -> None:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    cleanup_task = asyncio.create_task(asyncio.to_thread(close))
    cancellation = None
    while not cleanup_task.done():
        try:
            await asyncio.shield(cleanup_task)
        except asyncio.CancelledError as error:
            cancellation = error
    cleanup_task.result()
    return cancellation


def _expected_mode_lifecycle(
    mode: str,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    received: dict[str, float],
) -> bool:
    """Require successful timing pairs or the exact injected storage-fault evidence.

    Args:
        mode: Fixed diagnostic mode, never a customer selector.
        rows: Durable recovered records from the inert timing endpoint only.
        summary: Production worker/recovery observations.
        received: Independent endpoint correlation IDs and service milliseconds.

    Returns:
        Whether the expected observation occurred. Normal duration-limited modes
        need at least one successful pair, not the full maximum request budget.
        An arbitrary interrupted child is not a demonstrated injected fault.
    """
    if mode in {"native", "native_fsync_delay"}:
        return bool(
            rows
            and summary.get("load_status") == "completed"
            and summary.get("measurement_complete") is True
            and summary.get("successful_requests") == len(rows)
            and len(received) == len(rows)
            and all(
                row.get("success") is True
                and row.get("request_id") in received
                and type(row.get("latency_ms")) in {int, float}
                and math.isfinite(row["latency_ms"])
                and row["latency_ms"] >= 0
                for row in rows
            )
        )
    completion_fault = mode == "fail_completion_before_write"
    if mode not in {"fail_start_before_write", "fail_completion_before_write"}:
        return False
    journal = (summary.get("generator_health") or {}).get("journal") or {}
    return bool(
        summary.get("load_status") == "interrupted"
        and summary.get("measurement_complete") is False
        and summary.get("journal_integrity_failed") is True
        and summary.get("attempted_requests") == 1
        and journal.get("writer_failures") == 1
        and journal.get("started_events") == int(completion_fault)
        and journal.get("completed_events") == 0
        and len(received) == int(completion_fault)
        and len(rows) == int(completion_fault)
        and all(
            row.get("request_id") in received
            and row.get("success") is False
            and row.get("error") == "WorkerInterrupted"
            for row in rows
        )
    )


def calibrate(
    output_dir: str | Path | None = None,
    *,
    concurrency: int = 5,
    max_requests: int = 200,
    duration_seconds: float = 10,
) -> dict[str, Any]:
    """Run bounded timing-only calibration synchronously on the caller's machine.

    Args:
        output_dir: New private directory; an existing destination is rejected.
            None creates a fresh protected temporary directory and retains it.
        concurrency: At most five users for each normal timing mode.
        max_requests: At most 200 attempts per normal mode; faults use one each.
        duration_seconds: Dispatch-window upper bound from 0.1 through ten seconds.

    Returns:
        Content-free observations, cleanup evidence and retained artifact path.
        Results never certify accurate/unsaturated load or sustainable capacity.

    Raises:
        ValueError: Diagnostic bounds are invalid.
        RuntimeError: Called inside an event loop, or server dependencies missing.
        FileExistsError: The requested destination already exists.
        OSError: Native endpoint, subprocess or protected persistence fails.

    Side effects are owned localhost timing traffic, native disk fault/delay controls
    in dedicated workers, and protected artifacts. No agent/model/profile/auth calls
    or caller-global environment/subprocess mutations are performed.
    """
    _validate_bounds(concurrency, max_requests, duration_seconds)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("Use await calibrate_async(...) inside an active event loop")
    return asyncio.run(
        calibrate_async(
            output_dir,
            concurrency=concurrency,
            max_requests=max_requests,
            duration_seconds=duration_seconds,
        )
    )


async def calibrate_async(
    output_dir: str | Path | None = None,
    *,
    concurrency: int = 5,
    max_requests: int = 200,
    duration_seconds: float = 10,
) -> dict[str, Any]:
    """Run the same bounded calibration with native asyncio lifecycle ownership.

    Arguments and result match calibrate. The owner reaps each production worker
    via run_load and then shuts down/joins its native timing server/handlers. Caller
    cancellation propagates worker cleanup; there are no target retries or fallback
    providers. A fresh artifact root remains available if execution fails.
    """
    _validate_bounds(concurrency, max_requests, duration_seconds)
    try:
        from benchmark_agents.connections import Connection
        from benchmark_agents.locust_runner import run_load
        from benchmark_agents.models import RunRequest
        from benchmark_agents.storage import atomic_json
    except ImportError as error:
        raise RuntimeError("Calibration requires the evalsurge[server] extra") from error
    root = (
        Path(tempfile.mkdtemp(prefix="evalsurge-calibration-"))
        if output_dir is None
        else Path(output_dir).absolute()
    )
    if output_dir is not None:
        root.mkdir(mode=0o700, exist_ok=False)
    root.chmod(0o700)
    server = _TimingServer(record_limit=2 * max_requests + 2)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
    try:
        thread.start()
    except BaseException:
        server.server_close()
        raise
    endpoint = f"http://127.0.0.1:{server.server_port}/NON-agent-timing-only"
    outcomes = []
    failure: BaseException | None = None
    try:
        for mode in (
            "native",
            "native_fsync_delay",
            "fail_start_before_write",
            "fail_completion_before_write",
        ):
            is_fault = mode.startswith("fail_")
            request = RunRequest.model_validate(
                {
                    "target": {"url": endpoint, "adapter": "http-json"},
                    "evaluation": {
                        "description": "NON-agent timing calibration; no inference",
                        "scorers": [],
                        "samples": [{"inputs": {"timing_only": True}}],
                    },
                    "load": {
                        "concurrency": 1 if is_fault else concurrency,
                        "duration_seconds": duration_seconds,
                        "max_requests": 1 if is_fault else max_requests,
                        "timeout_seconds": 1,
                    },
                }
            )
            run_id = f"{mode}-{uuid4()}"
            with server.record_lock:
                before_ids = set(server.records)
            rows, summary = await run_load(
                request,
                run_id,
                asyncio.Event(),
                artifact_dir=root,
                connection=Connection(url=endpoint, auth="none"),
                _calibration_mode=mode,
            )
            with server.record_lock:
                received = {
                    key: value for key, value in server.records.items() if key not in before_ids
                }
            paired = [
                row
                for row in rows
                if row["request_id"] in received and row.get("latency_ms") is not None
            ]
            outcomes.append(
                {
                    "mode": mode,
                    "run_id": run_id,
                    "same_production_user_and_recovery": True,
                    "timing_endpoint_received": len(received),
                    "recovered_rows": len(rows),
                    "successful_client_latency_ms": _distribution(
                        [
                            row["latency_ms"]
                            for row in rows
                            if row.get("success") and row.get("latency_ms") is not None
                        ]
                    ),
                    "timing_endpoint_service_ms": _distribution(list(received.values())),
                    "paired_client_minus_service_ms": _distribution(
                        [row["latency_ms"] - received[row["request_id"]] for row in paired]
                    ),
                    "expected_lifecycle_observed": _expected_mode_lifecycle(
                        mode, rows, summary, received
                    ),
                    "summary": summary,
                }
            )
    except (asyncio.CancelledError, Exception) as error:  # noqa: BLE001 - retain receipt, then re-raise
        failure = error
    finally:
        cleanup_cancellation = await _close_timing_server(server, thread)
        if failure is None and cleanup_cancellation is not None:
            failure = cleanup_cancellation
    cleanup = {
        "timing_server_stopped": not thread.is_alive(),
        "timing_handlers_stopped": server.active_handlers == 0,
        "worker_exit_receipts_present": len(outcomes) == 4
        and all(type(mode["summary"].get("worker_exit_code")) is int for mode in outcomes),
        **_worker_exit_observation(root),
        "worker_ownership": (
            "run_load owns worker cleanup; PID/receipt fields record observed exit evidence"
        ),
    }
    cleanup_verified = (
        cleanup["timing_server_stopped"] is True
        and cleanup["timing_handlers_stopped"] is True
        and cleanup["worker_exit_receipts_present"] is True
        and cleanup["recorded_worker_count"] == 4
        and cleanup["worker_pid_exit_observed"] is True
    )
    receipt = {
        "kind": "NON-agent-production-locust-timing-calibration",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifact_dir": str(root),
        "report_path": str(root / "calibration.json"),
        "agent_calls": 0,
        "model_calls": 0,
        "cloud_calls": 0,
        "timing_requests": len(server.received_ids),
        "operator_credentials_passed_to_worker": False,
        "accuracy_certified": False,
        "payload_scope": {
            "request_json_bytes": len(json.dumps({"timing_only": True}).encode()),
            "response_json_bytes": len(b'{"outputs":"NON-agent-timing-marker"}'),
            "service_delay_ms": 25,
            "large_payloads_validated": False,
        },
        "bounds_per_normal_mode": {
            "concurrency": concurrency,
            "max_requests": max_requests,
            "duration_seconds": duration_seconds,
            "timeout_seconds": 1,
        },
        "controlled_storage_only": "Native five-ms fsync delay and native start/completion fault probes; no inference substitution",
        "cleanup": cleanup,
        "limitations": [
            "Local observations are not universal accuracy, agent capacity, cloud disk or serverless validation.",
            "Client-minus-service includes transport, parsing, scheduling and clock sampling; never subtract it from benchmark metrics.",
            "Durable disk waits can reduce throughput despite nonblocking fsync; JSON serialization and CPU/GIL can still affect peer scheduling.",
            "Latency remains Requests-inclusive client timing and quality is not evaluated.",
            "This tiny fixed request/response does not validate large captures, JSON/GIL costs or large response parser overhead.",
        ],
        "modes": outcomes,
        "failure_type": type(failure).__name__ if failure is not None else None,
        "completed": failure is None
        and cleanup_verified
        and len(outcomes) == 4
        and all(mode["expected_lifecycle_observed"] for mode in outcomes),
    }
    atomic_json(root / "calibration.json", receipt)
    (root / "calibration.json").chmod(0o600)
    if failure is not None:
        raise failure
    return receipt
