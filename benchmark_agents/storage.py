"""Atomic snapshots and append-only request journals on a local persistent disk."""

import json
import os
import time
from pathlib import Path
from typing import Any


class JournalWriteError(OSError):
    """Content-free failure of the worker-owned request journal."""


class TimingAggregate:
    """Constant-space count, mean and maximum for nonnegative millisecond timings."""

    def __init__(self) -> None:
        self.count = 0
        self.total_ms = 0.0
        self.maximum_ms = 0.0

    def observe(self, duration_ms: float) -> None:
        """Record one timing without retaining individual observations.

        Args:
            duration_ms: Nonnegative elapsed milliseconds, not server-only latency.
        """
        self.count += 1
        self.total_ms += duration_ms
        self.maximum_ms = max(self.maximum_ms, duration_ms)

    def snapshot(self) -> dict[str, int | float | None]:
        """Return the aggregate, with unavailable mean/max for no observations."""
        return {
            "count": self.count,
            "mean_ms": self.total_ms / self.count if self.count else None,
            "max_ms": self.maximum_ms if self.count else None,
        }


class CooperativeJournal:
    """One bounded FIFO and native writer, owned by a single gevent hub thread.

    Disk serialization/write/flush/fsync run in one actual native thread. Callers
    cooperate while admitting events and waiting for their durable acknowledgment;
    they must leave an event's mutable row unchanged until append returns. This
    removes hub-blocking disk work, not CPU/GIL overhead or per-user persistence
    waits. General storage imports remain independent of gevent.
    """

    def __init__(self, path: Path, concurrency: int) -> None:
        """Create owned dispatcher/pool state; open the file lazily in its worker.

        Args:
            path: Journal in an existing protected, operator-owned run directory.
            concurrency: Sequential users, bounded by the validated load request.

        The caller must close this object from the owning hub. The dispatcher is
        the sole pool submitter; its native worker never invokes gevent APIs.
        """
        import gevent
        from gevent.queue import Queue
        from gevent.threadpool import ThreadPool

        self.path = path
        self.queue_capacity = max(1, min(concurrency, 16))
        self._queue: Any = Queue(self.queue_capacity)
        self._pool: Any = ThreadPool(1)
        self._stream: Any = None
        self._closing = False
        self._sentinel_enqueued = False
        self._drained = False
        self._failure: JournalWriteError | None = None
        self._in_progress = 0
        self._appending = 0
        self._peak_pending = 0
        self._backpressure_events = 0
        self._writer_failures = 0
        self._started_events = 0
        self._completed_events = 0
        self._enqueue_wait = TimingAggregate()
        self._durable_wait = TimingAggregate()
        self._write_and_fsync = TimingAggregate()
        self._dispatcher: Any = gevent.spawn(self._dispatch)

    @property
    def failed(self) -> bool:
        """Whether persistence failed; new target dispatch must stop when true."""
        return self._failure is not None

    def _record_failure(self) -> JournalWriteError:
        if self._failure is None:
            self._failure = JournalWriteError("Request journal persistence failed")
            self._writer_failures += 1
        return self._failure

    def _write_native(self, event: dict[str, Any]) -> float:
        """Serialize, append and fsync one event in the sole native writer.

        Args:
            event: Borrowed event left immutable until acknowledgment.

        Returns:
            Native serialization/write/flush/fsync elapsed milliseconds.

        Raises:
            OSError: Protected file opening, writing or fsync failed.
            TypeError: The event cannot be JSON serialized.

        Existing symlink destinations are rejected. Only this native worker owns
        the descriptor; the caller must not close it from the hub thread.
        """
        began = time.perf_counter()
        if self._stream is None:
            flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self.path, flags, 0o600)
            self._stream = os.fdopen(descriptor, "a", encoding="utf-8")
        self._stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._stream.flush()
        os.fsync(self._stream.fileno())
        return (time.perf_counter() - began) * 1000

    def _close_native(self) -> None:
        """Close the native-owned descriptor after all earlier writes returned."""
        if self._stream is not None:
            self._stream.close()
            self._stream = None

    def _dispatch(self) -> None:
        """Dispatch FIFO events and propagate fixed failures to queued acknowledgments."""
        try:
            while True:
                item = self._queue.get()
                if item is None:
                    break
                event, acknowledgment = item
                self._in_progress = 1
                self._peak_pending = max(self._peak_pending, self._queue.qsize() + 1)
                try:
                    if self._failure is not None:
                        acknowledgment.set_exception(self._failure)
                        continue
                    duration = self._pool.spawn(self._write_native, event).get()
                    self._write_and_fsync.observe(duration)
                    if event["kind"] == "started":
                        self._started_events += 1
                    else:
                        self._completed_events += 1
                    acknowledgment.set(None)
                except Exception:  # noqa: BLE001 - native failures use a content-free envelope
                    acknowledgment.set_exception(self._record_failure())
                finally:
                    self._in_progress = 0
        finally:
            try:
                self._pool.spawn(self._close_native).get()
                self._pool.kill()
                self._drained = True
            except Exception:  # noqa: BLE001 - no raw storage exceptions leave the worker
                self._record_failure()

    def append(self, event: dict[str, Any]) -> None:
        """Cooperatively wait for FIFO admission and durable per-event fsync.

        Args:
            event: Started/completed event borrowing a row unchanged through return.

        Raises:
            JournalWriteError: Journal failed or its owner already began shutdown.
            ValueError: The event is not a supported journal lifecycle kind.

        A shallow row snapshot isolates lifecycle fields even if the caller is
        interrupted before acknowledgment. Nested sample inputs/references are
        immutable worker-owned values, not copied for every event.
        A failed start is never dispatched. Durability and admission timings overlap
        and must not be added to request latency or interpreted as server time.
        """
        from gevent.event import AsyncResult

        if event.get("kind") not in {"started", "completed"}:
            raise ValueError("Unsupported request journal event")
        if not isinstance(event.get("row"), dict):
            raise ValueError("Request journal event needs a row")
        if self._failure is not None:
            raise self._failure
        if self._closing:
            raise JournalWriteError("Request journal is closing")
        began = time.perf_counter()
        acknowledgment: Any = AsyncResult()
        if self._queue.full():
            self._backpressure_events += 1
        snapshot = {"kind": event["kind"], "row": dict(event["row"])}
        self._appending += 1
        try:
            self._queue.put((snapshot, acknowledgment))
            self._peak_pending = max(self._peak_pending, self._queue.qsize() + self._in_progress)
            self._enqueue_wait.observe((time.perf_counter() - began) * 1000)
            acknowledgment.get()
        finally:
            self._durable_wait.observe((time.perf_counter() - began) * 1000)
            self._appending -= 1

    def close(self, timeout: float = 5.0) -> bool:
        """Drain/close cooperatively within an explicit owner shutdown budget.

        Args:
            timeout: Maximum shutdown wait in seconds, including FIFO admission.

        Returns:
            Whether the dispatcher drained and closed its native descriptor.

        A hung native syscall cannot safely be cancelled. On timeout this returns
        false and marks failure; the parent worker watchdog retains final ownership.
        Repeated calls may observe later drain but never clear failure evidence.
        """
        import gevent

        began = time.perf_counter()
        with gevent.Timeout(max(timeout, 0), False):
            self._closing = True
            # Admissions already waiting on a full queue must settle before the
            # sentinel, or they could enqueue behind shutdown and never receive an ack.
            while self._appending:
                gevent.sleep(0.001)
            if not self._sentinel_enqueued:
                self._queue.put(None)
                self._sentinel_enqueued = True
            self._dispatcher.join(timeout=max(0, timeout - (time.perf_counter() - began)))
        if not self._drained:
            self._record_failure()
        return self._drained

    def snapshot(self) -> dict[str, Any]:
        """Return constant-size content-free evidence; acknowledged counts only."""
        return {
            "queue_capacity": self.queue_capacity,
            "peak_pending": self._peak_pending,
            "backpressure_events": self._backpressure_events,
            "writer_failures": self._writer_failures,
            "started_events": self._started_events,
            "completed_events": self._completed_events,
            "drained": self._drained,
            "enqueue_wait_ms": self._enqueue_wait.snapshot(),
            "durable_wait_ms": self._durable_wait.snapshot(),
            "write_and_fsync_ms": self._write_and_fsync.snapshot(),
        }


def atomic_json(path: Path, value: Any) -> None:
    """Write a JSON snapshot through a flushed, fsync'd temporary file.

    Args:
        path: Destination on local storage; missing parent directories are created.
        value: JSON-serializable snapshot, written with Unicode preserved.

    Raises:
        OSError: The snapshot cannot be written, synced, or replaced.
        TypeError: The value cannot be serialized.

    The caller must serialize writes to the same path. Atomic replacement protects
    the previous snapshot, but this function does not fsync the parent directory.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def append_event(path: Path, event: dict[str, Any]) -> None:
    """Append one newline-delimited request event and fsync the journal.

    Args:
        path: Journal in an existing run directory, owned by one local worker.
        event: A started or completed event containing the request's row snapshot.

    Raises:
        OSError: Appending or syncing fails.
        TypeError: The event cannot be serialized.

    Flushing each event retains partial progress at the cost of generator overhead.
    """
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def recover_rows(root: Path, interrupted: bool = True) -> tuple[list[dict[str, Any]], int]:
    """Reconstruct attempts from the latest event for each request identifier.

    Args:
        root: Run directory containing requests.jsonl.
        interrupted: Mark unfinished attempts WorkerInterrupted when true, or
            expose them as in_flight while a worker can still complete them.

    Returns:
        Rows in first-event order and the number of starts without completions.
        A missing journal returns an empty list and zero; malformed JSON lines
        and invalid UTF-8 lines are skipped. The journal is never modified.

    Raises:
        OSError: The journal cannot be read.
    """
    path = root / "requests.jsonl"
    if not path.exists():
        return [], 0
    records: dict[str, dict[str, Any]] = {}
    finished = set()
    with path.open("rb") as stream:
        for line in stream:
            try:
                event = json.loads(line.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if not isinstance(event, dict) or event.get("kind") not in {"started", "completed"}:
                continue
            row = event.get("row")
            if not isinstance(row, dict) or not isinstance(row.get("request_id"), str):
                continue
            records[row["request_id"]] = row
            if event["kind"] == "completed":
                finished.add(row["request_id"])
    incomplete = 0
    for request_id, row in records.items():
        if request_id not in finished:
            incomplete += 1
            row.update(
                success=False,
                error="WorkerInterrupted" if interrupted else None,
                latency_ms=None,
                end_offset_ms=None,
                record_status="interrupted" if interrupted else "in_flight",
                dispatched=None,
            )
    return list(records.values()), incomplete
