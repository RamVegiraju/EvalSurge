"""Isolated Locust subprocess with durable partial-result recovery."""

import asyncio
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

from .connections import resolve_connection
from .models import RunRequest
from .runner import summarize
from .storage import atomic_json, recover_rows


async def run_load(
    request: RunRequest, run_id: str, cancel: asyncio.Event, artifact_dir: Path | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Launch Locust; retain completed and interrupted measurements on any worker exit."""
    root = (
        artifact_dir or Path(os.getenv("BENCHMARK_ARTIFACT_DIR", "artifacts"))
    ).resolve() / run_id
    root.mkdir(parents=True, exist_ok=False)
    config_path, result_path, cancel_path = [
        root / name for name in ("config.json", "result.json", "cancel")
    ]
    atomic_json(config_path, request.model_dump(mode="json"))
    atomic_json(root / "connection.json", resolve_connection(request.target).model_dump())
    environment = {
        **os.environ,
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
        atomic_json(root / "worker.json", {"pid": process.pid, "phase": "load"})
        deadline = started + request.load.duration_seconds + request.load.timeout_seconds + 45
        expired = False
        try:
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
    summary.update(incomplete_measurements=incomplete, worker_exit_code=process.returncode)
    summary["load_status"] = (
        "interrupted"
        if expired or incomplete or not result_path.exists()
        else "cancelled"
        if cancel.is_set()
        else "completed"
    )
    summary["measurement_complete"] = result_path.exists() and not incomplete and not expired
    atomic_json(root / "recovered.json", {"rows": rows, "summary": summary})
    return rows, summary
