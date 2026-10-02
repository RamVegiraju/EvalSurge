"""Atomic snapshots and append-only request journals on a local persistent disk."""

import json
import os
from pathlib import Path
from typing import Any


def atomic_json(path: Path, value: Any) -> None:
    """Flush a snapshot before atomically replacing its prior version."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def append_event(path: Path, event: dict[str, Any]) -> None:
    """Durably append a complete event; one local worker owns each journal."""
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def recover_rows(root: Path, interrupted: bool = True) -> tuple[list[dict[str, Any]], int]:
    """Recover completed records, marking starts without completions as interrupted."""
    path = root / "requests.jsonl"
    if not path.exists():
        return [], 0
    records: dict[str, dict[str, Any]] = {}
    finished = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue  # A killed writer can leave an incomplete final line.
        if event.get("kind") not in {"started", "completed"}:
            continue
        row = event["row"]
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
