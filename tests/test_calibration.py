"""Pure bounds and real NON-agent clock/socket calibration; no model/provider calls."""

import asyncio
import json
import stat
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from evalsurge.calibration import (
    _distribution,
    _expected_mode_lifecycle,
    _validate_bounds,
    calibrate,
    calibrate_async,
)


def test_empty_timing_observations_do_not_establish_normal_calibration():
    """Pure timing metadata: lifecycle completion alone cannot prove a timing pair."""
    assert not _expected_mode_lifecycle(
        "native", [], {"load_status": "completed", "measurement_complete": True}, {}
    )


def test_arbitrary_worker_interruption_is_not_an_observed_storage_fault():
    """A failed inert child without exact writer evidence is not an injected-fault pass."""
    assert not _expected_mode_lifecycle(
        "fail_start_before_write",
        [],
        {"load_status": "interrupted", "measurement_complete": False},
        {},
    )


def test_timing_server_owns_non_daemon_handlers():
    """Native server close must join handlers rather than abandon daemon threads."""
    from evalsurge.calibration import _TimingServer

    with _TimingServer() as server:
        assert server.daemon_threads is False
        assert server.block_on_close is True


async def test_repeated_cancellation_waits_for_native_cleanup_receipt(tmp_path, monkeypatch):
    """Delay only native close; no model/provider or worker result is substituted."""
    from evalsurge.calibration import _TimingServer

    entered = threading.Event()
    release = threading.Event()
    original_close = _TimingServer.server_close

    def delayed_close(server):
        entered.set()
        assert release.wait(timeout=5)
        original_close(server)

    monkeypatch.setattr(_TimingServer, "server_close", delayed_close)
    task = asyncio.create_task(calibrate_async(tmp_path / "repeat-cancel", max_requests=1))
    try:
        await asyncio.sleep(0.2)
        task.cancel()
        async with asyncio.timeout(5):
            while not entered.is_set():
                await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    report = json.loads((tmp_path / "repeat-cancel" / "calibration.json").read_text())
    assert report["completed"] is False
    assert report["failure_type"] == "CancelledError"
    assert report["cleanup"]["timing_server_stopped"]
    assert report["cleanup"]["timing_handlers_stopped"]


async def test_completed_calibration_requires_observed_worker_cleanup(tmp_path, monkeypatch):
    """Actual timing workload; only the no-inference PID observation is unavailable."""
    monkeypatch.setattr(
        "evalsurge.calibration._worker_exit_observation",
        lambda root: {"recorded_worker_count": 4, "worker_pid_exit_observed": None},
    )
    report = await calibrate_async(tmp_path / "unverified", max_requests=1, duration_seconds=1)
    assert all(mode["expected_lifecycle_observed"] for mode in report["modes"])
    assert report["completed"] is False
    assert report["cleanup"]["worker_pid_exit_observed"] is None


def test_timing_endpoint_rejects_uncorrelated_requests():
    """Actual NON-agent loopback traffic cannot create an anonymous timing record."""
    from evalsurge.calibration import _TimingServer

    with _TimingServer() as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/NON-agent-timing-only",
                data=b'{"timing_only":true}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(HTTPError) as error:
                urlopen(request, timeout=2)
            assert error.value.code == 400
            assert not server.records
        finally:
            server.shutdown()
            thread.join(timeout=2)


def test_timing_worker_runtime_environment_excludes_operator_secrets(monkeypatch):
    """Pure environment selection; credentials are not passed into diagnostic children."""
    from benchmark_agents.locust_runner import (
        CALIBRATION_ENVIRONMENT_KEYS,
        _calibration_environment,
    )

    for key in (
        "DATABRICKS_TOKEN",
        "DATABRICKS_CONFIG_PROFILE",
        "OPENAI_API_KEY",
        "MLFLOW_TRACKING_TOKEN",
        "HTTP_PROXY",
        "BENCHMARK_CONNECTIONS",
    ):
        monkeypatch.setenv(key, "NON-secret-control-must-not-propagate")
    selected = _calibration_environment()
    assert set(selected).issubset(CALIBRATION_ENVIRONMENT_KEYS)
    assert "NON-secret-control-must-not-propagate" not in selected.values()


@pytest.mark.parametrize(
    "values",
    [
        (True, 1, 1),
        (6, 1, 1),
        (1, 201, 1),
        (1, True, 1),
        (1, 1, float("inf")),
        (1, 1, float("nan")),
        (1, 1, 11),
        (1, 1, True),
    ],
)
def test_calibration_bounds_before_resources(values):
    """Diagnostic cannot select arbitrary or nonfinite traffic quantities."""
    with pytest.raises(ValueError):
        _validate_bounds(*values)


def test_calibration_distribution_retains_unavailable_and_signed_differences():
    assert _distribution([]) == {
        "count": 0,
        "mean_ms": None,
        "max_ms": None,
        "p50_ms": None,
        "p95_ms": None,
        "p99_ms": None,
    }
    assert _distribution([-0.1, 0.2])["p95_ms"] == 0.2


async def test_sync_calibration_rejects_running_loop_before_resources(tmp_path):
    with pytest.raises(RuntimeError, match="calibrate_async"):
        calibrate(tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()


async def test_packaged_production_path_calibration_and_cleanup(tmp_path):
    """Actual Locust, journal/fsync, native timing endpoint and storage fault probes."""
    report = await calibrate_async(tmp_path / "fresh", max_requests=10, duration_seconds=2)
    assert report["completed"] and report["accuracy_certified"] is False
    assert report["agent_calls"] == report["model_calls"] == report["cloud_calls"] == 0
    assert report["timing_requests"] == 21
    assert report["operator_credentials_passed_to_worker"] is False
    assert report["cleanup"]["timing_server_stopped"]
    assert report["cleanup"]["timing_handlers_stopped"]
    assert report["cleanup"]["worker_exit_receipts_present"]
    assert report["cleanup"]["recorded_worker_count"] == 4
    assert report["cleanup"]["worker_pid_exit_observed"]
    modes = {mode["mode"]: mode for mode in report["modes"]}
    for mode in ("native", "native_fsync_delay"):
        assert modes[mode]["timing_endpoint_received"] == 10
        assert modes[mode]["paired_client_minus_service_ms"]["count"] == 10
        assert modes[mode]["summary"]["generator_health"]["status"] == "unknown"
        assert modes[mode]["summary"]["generator_health"]["journal"]["completed_events"] == 10
    assert modes["fail_start_before_write"]["timing_endpoint_received"] == 0
    assert modes["fail_completion_before_write"]["timing_endpoint_received"] == 1
    assert stat.S_IMODE((tmp_path / "fresh").stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "fresh" / "calibration.json").stat().st_mode) == 0o600
    assert json.loads((tmp_path / "fresh" / "calibration.json").read_text()) == report
    with pytest.raises(FileExistsError):
        await calibrate_async(tmp_path / "fresh", max_requests=1)


async def test_calibration_cancellation_retains_receipt_and_closes_native_server(tmp_path):
    """Cancel actual child startup, not model execution, and retain native cleanup evidence."""
    task = asyncio.create_task(calibrate_async(tmp_path / "cancelled", max_requests=200))
    await asyncio.sleep(0.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    report = json.loads((tmp_path / "cancelled" / "calibration.json").read_text())
    assert report["failure_type"] == "CancelledError" and report["completed"] is False
    assert (
        report["cleanup"]["timing_server_stopped"] and report["cleanup"]["timing_handlers_stopped"]
    )
    assert report["cleanup"]["recorded_worker_count"] == 1
    assert report["cleanup"]["worker_pid_exit_observed"]
    assert report["cleanup"]["worker_exit_receipts_present"] is False
