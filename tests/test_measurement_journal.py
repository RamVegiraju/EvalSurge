"""Native storage/thread/clock checks only: no agent, provider, or cloud inference."""

import json
import os
import stat
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

import gevent
from gevent.monkey import get_original

from benchmark_agents.runner import HubLagProbe, generator_health
from benchmark_agents.storage import CooperativeJournal, JournalWriteError, recover_rows
from benchmark_agents.v2_models import GeneratorHealth


def event(kind: str = "started", request_id: str = "one") -> dict[str, Any]:
    """Return an inert journal record, never dispatched to any endpoint."""
    return {
        "kind": kind,
        "row": {
            "request_id": request_id,
            "success": kind == "completed",
            "outputs": "",
            "latency_ms": None,
        },
    }


def wait_until(predicate: Any, timeout: float = 2) -> None:
    """Poll native test synchronization without blocking the owning hub."""
    deadline = time.perf_counter() + timeout
    while not predicate():
        if time.perf_counter() >= deadline:
            raise AssertionError("Native storage condition did not arrive")
        gevent.sleep(0.001)


def test_native_fsync_does_not_block_hub_and_ack_is_durable(tmp_path, monkeypatch):
    """Hold actual native fsync while peer greenlets tick; ack waits for real fsync."""
    native_lock = get_original("_thread", "allocate_lock")
    native_ident = get_original("_thread", "get_ident")
    release = native_lock()
    release.acquire()
    entered = native_lock()
    entered.acquire()
    original_fsync = os.fsync
    fsync_threads: list[int] = []
    descriptors: list[int] = []
    hub_identity = native_ident()

    def held_fsync(descriptor):
        fsync_threads.append(native_ident())
        descriptors.append(descriptor)
        if len(fsync_threads) == 1:
            entered.release()
            assert release.acquire(timeout=2)
            release.release()
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", held_fsync)
    journal = CooperativeJournal(tmp_path / "requests.jsonl", concurrency=5)
    ticks: list[float] = []

    def tick():
        for _ in range(10):
            ticks.append(time.perf_counter())
            gevent.sleep(0.002)

    append = gevent.spawn(journal.append, event())
    ticker = gevent.spawn(tick)
    try:
        wait_until(lambda: not entered.locked())
        ticker.join(timeout=0.5)
        assert len(ticks) == 10
        assert not append.ready()
        assert fsync_threads[0] != hub_identity
        assert journal.snapshot()["started_events"] == 0
        release.release()
        append.get(timeout=2)
        journal.append(event("completed"))
        assert journal.close(timeout=2)
        assert descriptors[0] == descriptors[1]
        assert len(set(fsync_threads)) == 1
        assert stat.S_IMODE((tmp_path / "requests.jsonl").stat().st_mode) == 0o600
        rows, incomplete = recover_rows(tmp_path)
        assert incomplete == 0 and len(rows) == 1 and rows[0]["success"]
    finally:
        if release.locked():
            release.release()
        append.join(timeout=2)
        ticker.kill(block=True)
        journal.close(timeout=2)


def test_fifo_capacity_and_backpressure(tmp_path, monkeypatch):
    """Controlled native disk delay retains bounded FIFO and acknowledgment counts."""
    original_fsync = os.fsync
    native_sleep = get_original("time", "sleep")

    def delayed_fsync(descriptor):
        native_sleep(0.003)
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", delayed_fsync)
    journal = CooperativeJournal(tmp_path / "requests.jsonl", concurrency=3)
    jobs = [gevent.spawn(journal.append, event(request_id=str(index))) for index in range(8)]
    try:
        gevent.joinall(jobs, timeout=3, raise_error=True)
        assert all(job.ready() for job in jobs)
        assert journal.close(timeout=2)
        recovered = [json.loads(line) for line in journal.path.read_text().splitlines()]
        assert [entry["row"]["request_id"] for entry in recovered] == [str(i) for i in range(8)]
        snapshot = journal.snapshot()
        assert snapshot["peak_pending"] <= snapshot["queue_capacity"] + 1 == 4
        assert snapshot["backpressure_events"] > 0
        assert snapshot["started_events"] == 8
        assert snapshot["write_and_fsync_ms"]["count"] == 8
    finally:
        gevent.joinall(jobs, timeout=2)
        journal.close(timeout=2)


def test_writer_failure_is_sticky_content_free_and_fails_waiters(tmp_path, monkeypatch):
    """A controlled filesystem fault cannot disclose raw error text or certify drain."""

    def fail_fsync(descriptor):
        raise OSError("private-secret-location")

    monkeypatch.setattr(os, "fsync", fail_fsync)
    journal = CooperativeJournal(tmp_path / "requests.jsonl", concurrency=2)

    def append_and_capture(index):
        try:
            journal.append(event(request_id=str(index)))
        except JournalWriteError as error:
            return str(error)
        raise AssertionError("A failed journal cannot acknowledge a start")

    jobs = [gevent.spawn(append_and_capture, index) for index in range(4)]
    try:
        assert [job.get(timeout=2) for job in jobs] == ["Request journal persistence failed"] * 4
        assert journal.failed
        assert journal.close(timeout=2)
        snapshot = journal.snapshot()
        assert snapshot["writer_failures"] == 1
        assert snapshot["started_events"] == snapshot["completed_events"] == 0
        assert "private-secret-location" not in json.dumps(snapshot)
    finally:
        gevent.joinall(jobs, timeout=2)
        journal.close(timeout=2)


def test_interrupted_caller_cannot_mutate_borrowed_start(tmp_path, monkeypatch):
    """Kill an actual caller during native persistence; row lifecycle snapshot stays fixed."""
    native_lock = get_original("_thread", "allocate_lock")
    release = native_lock()
    release.acquire()
    entered: list[bool] = []
    original_write = CooperativeJournal._write_native

    def held_write(self, snapshot):
        entered.append(True)
        assert release.acquire(timeout=2)
        release.release()
        return original_write(self, snapshot)

    monkeypatch.setattr(CooperativeJournal, "_write_native", held_write)
    journal = CooperativeJournal(tmp_path / "requests.jsonl", concurrency=1)
    original = event()

    def interrupted_owner():
        try:
            journal.append(original)
        finally:
            original["row"].update(success=True, outputs="caller-completion")

    caller = gevent.spawn(interrupted_owner)
    try:
        wait_until(lambda: bool(entered))
        caller.kill(block=True)
        release.release()
        assert journal.close(timeout=2)
        persisted = json.loads(journal.path.read_text())
        assert persisted["kind"] == "started"
        assert persisted["row"]["success"] is False
        assert persisted["row"]["outputs"] == ""
    finally:
        if release.locked():
            release.release()
        caller.kill(block=True)
        journal.close(timeout=2)


def test_bounded_close_retries_sentinel_admission_after_full_queue(tmp_path, monkeypatch):
    """A timed-out shutdown retains failure and can later release its owned native pool."""
    native_lock = get_original("_thread", "allocate_lock")
    release = native_lock()
    release.acquire()
    entered: list[bool] = []
    original_write = CooperativeJournal._write_native

    def held_write(self, snapshot):
        entered.append(True)
        assert release.acquire(timeout=2)
        release.release()
        return original_write(self, snapshot)

    monkeypatch.setattr(CooperativeJournal, "_write_native", held_write)
    journal = CooperativeJournal(tmp_path / "requests.jsonl", concurrency=1)

    def capture(index):
        with suppress(JournalWriteError):
            journal.append(event(request_id=str(index)))

    # One native write, one FIFO entry, and one admission blocked outside the FIFO.
    jobs = [gevent.spawn(capture, index) for index in range(3)]
    try:
        wait_until(lambda: bool(entered) and journal._queue.full())
        began = time.perf_counter()
        assert journal.close(timeout=0.02) is False
        assert time.perf_counter() - began < 0.3
        assert journal.failed and not journal._sentinel_enqueued
        release.release()
        assert journal.close(timeout=2)
        gevent.joinall(jobs, timeout=2, raise_error=True)
        assert all(job.ready() for job in jobs)
        assert journal.snapshot()["writer_failures"] == 1
        assert journal._dispatcher.dead and journal._pool.size == 0
    finally:
        if release.locked():
            release.release()
        gevent.joinall(jobs, timeout=2)
        journal.close(timeout=2)


def test_symlink_journal_is_not_followed(tmp_path):
    """Reject an untrusted destination without changing its real target."""
    target = tmp_path / "protected.jsonl"
    target.write_text("untouched")
    path = tmp_path / "requests.jsonl"
    path.symlink_to(target)
    journal = CooperativeJournal(path, concurrency=1)
    try:
        try:
            journal.append(event())
        except JournalWriteError:
            pass
        else:
            raise AssertionError("A journal symlink must be rejected")
        assert target.read_text() == "untouched"
        assert journal.close(timeout=2)
    finally:
        journal.close(timeout=2)


def test_health_types_observational_probe_and_constant_space(tmp_path: Path):
    """Pure clock/numeric observations remain unknown; no calibrated capacity verdict."""
    probe = HubLagProbe(interval_ms=1)
    journal = CooperativeJournal(tmp_path / "requests.jsonl", concurrency=100)
    try:
        gevent.sleep(0.02)
        assert journal.close(timeout=2)
        probe.stop()
        health = GeneratorHealth.model_validate(
            generator_health(probe.snapshot(), journal.snapshot())
        )
        assert health.status == "unknown"
        assert health.hub_lag.count > 0
        assert health.hub_lag.mean_ms >= 0
        assert health.journal.queue_capacity == 16
        assert health.journal.drained
        assert len(probe._timing.__dict__) == 3
    finally:
        probe.stop()
        journal.close(timeout=2)
