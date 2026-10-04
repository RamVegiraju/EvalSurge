"""Atomic snapshots and append-only request journals on a local persistent disk."""

import json
import os
from pathlib import Path
from typing import Any


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
