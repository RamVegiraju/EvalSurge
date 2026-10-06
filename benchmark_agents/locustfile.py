"""Locust process entry point. Never import into the asyncio API process."""

import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import gevent
import requests
from locust import HttpUser, constant, events, task

from benchmark_agents.adapters import get_adapter
from benchmark_agents.connections import Connection, authentication
from benchmark_agents.models import RunRequest
from benchmark_agents.runner import payload, summarize
from benchmark_agents.storage import append_event, atomic_json

config = RunRequest.model_validate_json(Path(os.environ["BENCHMARK_LOCUST_CONFIG"]).read_text())
destination = Path(os.environ["BENCHMARK_LOCUST_RESULT"])
cancel_file = Path(os.environ["BENCHMARK_LOCUST_CANCEL"])
run_id = os.environ["BENCHMARK_RUN_ID"]
rows: list[dict[str, Any]] = []
started: float | None = None
last_dispatch = 0.0
issued = 0
active = 0
peak = 0
auth_headers = None
http_active = 0
journal = destination.parent / "requests.jsonl"
connection = Connection.model_validate_json((destination.parent / "connection.json").read_text())
adapter = get_adapter(config.target.adapter)


@events.test_start.add_listener
def start(environment: Any, **kwargs: Any) -> None:
    """Start the measured window at Locust's test_start event.

    Args:
        environment: Locust event context; not needed to initialize the clock.
        **kwargs: Additional event metadata accepted for Locust compatibility.

    Authentication is deferred to each attempt and is included in the run window.
    """
    global started
    started = time.perf_counter()


@events.quitting.add_listener
def finish(environment: Any, **kwargs: Any) -> None:
    """Persist the aggregate summary when Locust emits its quitting event.

    Args:
        environment: Locust event context; measurements use this module's state.
        **kwargs: Additional event metadata accepted for Locust compatibility.

    Raw attempts already reside in the append-only journal. This snapshot records
    measured wall time, attempted dispatches, and observed peak HTTP concurrency.
    """
    elapsed = time.perf_counter() - started if started is not None else 0.001
    summary = summarize(rows, max(elapsed, 0.001), last_dispatch)
    summary.update(
        engine="locust",
        configured_concurrency=config.load.concurrency,
        observed_peak_in_flight=peak,
        attempted_requests=issued,
        dispatched_requests=sum(r["dispatched"] for r in rows),
        incomplete_measurements=issued - len(rows),
    )
    atomic_json(destination, {"summary": summary})


class AgentUser(HttpUser):
    """One sequential HTTP transaction per user, with no think time."""

    wait_time = constant(0)

    def on_start(self) -> None:
        """Disable ambient proxy and netrc discovery for this user's HTTP session."""
        self.client.trust_env = False

    @task
    def invoke(self) -> None:
        """Execute one sequential, journaled HTTP attempt for this Locust user.

        Cases are assigned round-robin across users. Count, duration, and cancellation
        limits stop new attempts while existing work drains. Authentication and
        response reading/parsing share one deadline. SSE TTFT starts after auth at
        HTTP dispatch and ignores non-answer events; JSON TTFT stays unavailable.

        Each attempt releases its active counters and records completion in cleanup,
        including failed authentication, invalid responses, and target errors. Target
        requests are never retried, because agent actions may have side effects.
        """
        global issued, active, peak, last_dispatch, auth_headers, http_active
        if started is None:
            return
        exhausted = issued >= config.load.max_requests
        expired = time.perf_counter() - started >= config.load.duration_seconds
        if exhausted or expired or cancel_file.exists():
            if active == 0:
                gevent.spawn(self.environment.runner.quit)
            gevent.sleep(0.01)
            return
        index = issued % len(config.evaluation.samples)
        issued += 1
        active += 1
        sample = config.evaluation.samples[index]
        row = {
            "request_id": str(uuid4()),
            "case_id": index,
            "inputs": sample.inputs,
            "expectations": sample.expectations,
            "outputs": "",
            "success": False,
            "first_event_ms": None,
            "ttft_ms": None,
            "output_tokens": None,
            "trace_id": None,
            "error": None,
            "http_status": None,
        }
        lifecycle_start = time.perf_counter()
        row["start_offset_ms"] = (lifecycle_start - started) * 1000
        row["stage_id"] = "single"
        row["dispatched"] = False
        sent = None
        response = None
        phase = "journal"
        try:
            append_event(journal, {"kind": "started", "row": row})
            phase = "authentication"
            with gevent.Timeout(
                config.load.timeout_seconds, TimeoutError("Request deadline exceeded")
            ):
                headers = {
                    "X-Benchmark-Run-ID": run_id,
                    "X-Benchmark-Request-ID": row["request_id"],
                }
                if auth_headers is None:
                    auth_headers = authentication(connection)
                headers.update(auth_headers())
                phase = "request"
                row["auth_ms"] = (time.perf_counter() - lifecycle_start) * 1000
                sent = time.perf_counter()
                last_dispatch = sent - started
                row["dispatched"] = True
                http_active += 1
                peak = max(peak, http_active)
                with self.client.post(
                    str(config.target.url),
                    json=payload(config, sample),
                    headers=headers,
                    stream=True,
                    catch_response=True,
                    allow_redirects=False,
                    timeout=config.load.timeout_seconds,
                    name="agent_transaction",
                ) as response:
                    try:
                        row["http_status"] = response.status_code or None
                        response.raise_for_status()
                        if not 200 <= response.status_code < 300:
                            raise ValueError("Target returned a non-success HTTP status")
                        phase = "response" if config.target.adapter == "http-json" else "stream"
                        adapter.decode(response, row, sent)
                        if time.perf_counter() - lifecycle_start >= config.load.timeout_seconds:
                            raise TimeoutError("Request deadline exceeded")
                        row["success"] = True
                    except (
                        requests.RequestException,
                        TimeoutError,
                        ValueError,
                        TypeError,
                        AttributeError,
                        IndexError,
                    ) as error:
                        row["error"] = type(error).__name__
                        row["error_phase"] = phase
                        row["error_detail"] = str(error)[:300]
                        response.failure(row["error"])
                    finally:
                        # Locust otherwise reports time to response headers for stream=True.
                        response.request_meta["response_time"] = (time.perf_counter() - sent) * 1000
                        response.request_meta["response_length"] = len(row["outputs"].encode())
        except Exception as error:  # noqa: BLE001 - record infrastructure failures and release the slot
            row["success"] = False
            row["error"] = type(error).__name__
            row["error_phase"] = phase
        finally:
            if response is not None and response.raw is not None:
                response.close()
            row["latency_ms"] = (time.perf_counter() - sent) * 1000 if sent else None
            row["lifecycle_ms"] = (time.perf_counter() - lifecycle_start) * 1000
            row["deadline_exceeded"] = (
                not row["success"] and row["lifecycle_ms"] >= config.load.timeout_seconds * 1000
            )
            if sent is not None:
                http_active -= 1
            row["end_offset_ms"] = (time.perf_counter() - started) * 1000
            active -= 1
            rows.append(row)
            append_event(journal, {"kind": "completed", "row": row})
        # Preserve TTFT as metadata, not a second transaction in Locust's total RPS.
