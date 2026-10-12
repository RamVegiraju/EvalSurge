"""Intentional pre-dispatch ownership checks: zero agent/model/provider calls."""

import json
import os
import subprocess
import sys
import threading

import pytest

from benchmark_agents.models import RunRequest
from evalsurge.calibration import _TimingServer


@pytest.mark.parametrize(
    "phase,stop", [("start", "cancel"), ("start", "expire"), ("auth", "cancel"), ("auth", "expire")]
)
def test_stopped_after_native_journal_or_auth_wait_never_dispatches(tmp_path, phase, stop):
    """Actual production invocation method, native storage delay and a never-used HTTP client."""
    request = RunRequest(
        target={"url": "http://127.0.0.1:9999/never-dispatched", "adapter": "http-json"},
        evaluation={
            "description": "Pre-dispatch ownership",
            "scorers": [],
            "samples": [{"inputs": {"timing_only": True}}],
        },
        load={
            "concurrency": 1,
            "duration_seconds": 0.1 if stop == "expire" else 1,
            "max_requests": 1,
            "timeout_seconds": 1,
        },
    )
    (tmp_path / "config.json").write_text(request.model_dump_json())
    (tmp_path / "connection.json").write_text(
        json.dumps({"url": str(request.target.url), "auth": "none"})
    )
    script = r"""
import json, sys, time
import gevent
from gevent.monkey import get_original
from locust.env import Environment
import benchmark_agents.locustfile as core
phase, stop = sys.argv[1:]
native_ident = get_original("_thread", "get_ident")
native_sleep = get_original("time", "sleep")
hub_ident = native_ident()
native_threads = []
original_write = core.CooperativeJournal._write_native
def held_start(self, event):
    if phase == "start" and event["kind"] == "started":
        native_threads.append(native_ident())
        if stop == "cancel":
            core.cancel_file.touch()
        native_sleep(0.15)
    return original_write(self, event)
core.CooperativeJournal._write_native = held_start
original_authentication = core.authentication
def delayed_authentication(connection):
    original_headers = original_authentication(connection)
    def headers():
        if phase == "auth":
            if stop == "cancel":
                core.cancel_file.touch()
            gevent.sleep(0.15)
        return original_headers()
    return headers
core.authentication = delayed_authentication
environment = Environment(host=str(core.config.target.url))
core.AgentUser.host = str(core.config.target.url)
user = core.AgentUser(environment)
user.on_start()
core.start(environment)
user.invoke()
core.finish(environment)
assert core.active == core.http_active == 0
assert len(core.rows) == 1 and core.rows[0]["dispatched"] is False
assert core.rows[0]["latency_ms"] is None and core.rows[0]["ttft_ms"] is None
assert core.rows[0]["error"] == ("DispatchCancelled" if stop == "cancel" else "DispatchWindowClosed")
assert core.journal_writer.snapshot()["started_events"] == core.journal_writer.snapshot()["completed_events"] == 1
if phase == "start":
    assert native_threads and native_threads[0] != hub_ident
user.client.close()
print(json.dumps({"phase": phase, "stop": stop, "agent_calls": 0, "model_calls": 0,
                  "row": core.rows[0], "summary": json.loads(core.destination.read_text())["summary"]}))
"""
    environment = {
        **os.environ,
        "BENCHMARK_LOCUST_CONFIG": str(tmp_path / "config.json"),
        "BENCHMARK_LOCUST_RESULT": str(tmp_path / "result.json"),
        "BENCHMARK_LOCUST_CANCEL": str(tmp_path / "cancel"),
        "BENCHMARK_RUN_ID": "pre-dispatch-ownership",
    }
    result = subprocess.run(
        [sys.executable, "-c", script, phase, stop],
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["agent_calls"] == receipt["model_calls"] == 0
    assert receipt["summary"]["measurement_complete"]
    assert receipt["summary"]["dispatched_requests"] == 0


def test_native_start_wait_does_not_consume_auth_response_deadline(tmp_path):
    """Actual timing-only HTTP call remains valid after a slow durable START ack."""
    server = _TimingServer()
    serving = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    serving.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/NON-agent-timing-only"
    request = RunRequest(
        target={"url": endpoint, "adapter": "http-json"},
        evaluation={
            "description": "NON-agent deadline calibration",
            "scorers": [],
            "samples": [{"inputs": {"timing_only": True}}],
        },
        load={"concurrency": 1, "duration_seconds": 1, "max_requests": 1, "timeout_seconds": 0.1},
    )
    (tmp_path / "config.json").write_text(request.model_dump_json())
    (tmp_path / "connection.json").write_text(json.dumps({"url": endpoint, "auth": "none"}))
    script = r"""
import json, time
from gevent.monkey import get_original
from locust.env import Environment
import benchmark_agents.locustfile as core
original_write = core.CooperativeJournal._write_native
native_sleep = get_original("time", "sleep")
def slow_start(self, event):
    if event["kind"] == "started":
        native_sleep(0.15)
    return original_write(self, event)
core.CooperativeJournal._write_native = slow_start
environment = Environment(host=str(core.config.target.url))
core.AgentUser.host = str(core.config.target.url)
user = core.AgentUser(environment)
user.on_start()
core.start(environment)
user.invoke()
core.finish(environment)
user.client.close()
row = core.rows[0]
assert row["dispatched"] is True
assert row["lifecycle_ms"] > 150
assert row["latency_ms"] < 100
assert row["success"] is True, json.dumps(row)
print(json.dumps(row))
"""
    environment = {
        **os.environ,
        "BENCHMARK_LOCUST_CONFIG": str(tmp_path / "config.json"),
        "BENCHMARK_LOCUST_RESULT": str(tmp_path / "result.json"),
        "BENCHMARK_LOCUST_CANCEL": str(tmp_path / "cancel"),
        "BENCHMARK_RUN_ID": "NON-agent-deadline-calibration",
    }
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert len(server.records) == 1
    finally:
        server.shutdown()
        server.server_close()
        serving.join(timeout=2)


@pytest.mark.parametrize("single_flight", [False, True])
def test_authentication_initialization_single_flight_preserves_refresh(tmp_path, single_flight):
    """Actual users share discovery ownership; each refreshes before real NON-agent HTTP.

    The discovery seam has a deliberate cooperative delay and no cloud/model call.
    The unlocked control reproduces duplicate setup without changing transport.
    """
    server = _TimingServer()
    serving = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    serving.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/NON-agent-timing-only"
    request = RunRequest(
        target={"url": endpoint, "adapter": "http-json"},
        evaluation={
            "description": "NON-agent authentication ownership",
            "scorers": [],
            "samples": [{"inputs": {"timing_only": True}}],
        },
        load={"concurrency": 5, "duration_seconds": 2, "max_requests": 5, "timeout_seconds": 1},
    )
    (tmp_path / "config.json").write_text(request.model_dump_json())
    (tmp_path / "connection.json").write_text(json.dumps({"url": endpoint, "auth": "none"}))
    script = r"""
import json, sys
import gevent
from locust.env import Environment
import benchmark_agents.locustfile as core
guarded = sys.argv[1] == "true"
counts = {"initialization": 0, "refresh": 0}
def delayed_initialization(connection):
    counts["initialization"] += 1
    gevent.sleep(0.1)
    def fresh_headers():
        counts["refresh"] += 1
        return {}
    return fresh_headers
core.authentication = delayed_initialization
if not guarded:
    class NoLock:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    core.auth_initialization = NoLock()
environment = Environment(host=str(core.config.target.url))
core.AgentUser.host = str(core.config.target.url)
users = [core.AgentUser(environment) for _ in range(5)]
for user in users:
    user.on_start()
core.start(environment)
gevent.joinall([gevent.spawn(user.invoke) for user in users], timeout=3, raise_error=True)
core.finish(environment)
for user in users:
    user.client.close()
assert counts == {"initialization": 1 if guarded else 5, "refresh": 5}, counts
assert len(core.rows) == 5 and all(row["success"] for row in core.rows)
assert core.active == core.http_active == 0
print(json.dumps({"guarded": guarded, "counts": counts, "endpoint_calls": len(core.rows),
                  "agent_calls": 0, "model_calls": 0, "cloud_calls": 0}))
"""
    environment = {
        **os.environ,
        "BENCHMARK_LOCUST_CONFIG": str(tmp_path / "config.json"),
        "BENCHMARK_LOCUST_RESULT": str(tmp_path / "result.json"),
        "BENCHMARK_LOCUST_CANCEL": str(tmp_path / "cancel"),
        "BENCHMARK_RUN_ID": "NON-agent-authentication-ownership",
    }
    try:
        result = subprocess.run(
            [sys.executable, "-c", script, str(single_flight).lower()],
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert len(server.records) == 5
    finally:
        server.shutdown()
        server.server_close()
        serving.join(timeout=2)
