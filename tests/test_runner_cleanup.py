"""Local subprocess cleanup regressions without running Locust or agent inference."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal
from uuid import uuid4

import pytest

from benchmark_agents import locust_runner
from benchmark_agents.models import RunRequest


async def reap_children(children: list[asyncio.subprocess.Process]) -> None:
    """Release only subprocesses created by this test, including on regression failure.

    Args:
        children: Controlled Python sleepers owned by the current test.

    Raises:
        TimeoutError: A killed child cannot be reaped within two seconds.

    Termination gets two seconds before a forced kill. This cleanup runs after the
    production-cleanup assertion and cannot turn a leaked child into a passing test.
    """
    for child in children:
        if child.returncode is None:
            child.terminate()
        try:
            await asyncio.wait_for(child.wait(), timeout=2)
        except TimeoutError:
            child.kill()
            await asyncio.wait_for(child.wait(), timeout=2)


@pytest.mark.parametrize("phase", ["load", "preflight"])
async def test_worker_metadata_failure_reaps_spawned_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: Literal["load", "preflight"]
) -> None:
    """Failure immediately after spawn must terminate and await the owned child."""
    children: list[asyncio.subprocess.Process] = []
    failed_paths: list[Path] = []
    original_spawn = asyncio.create_subprocess_exec
    original_write = locust_runner.atomic_json

    async def controlled_spawn(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        """Replace the Locust command with an inert, real, test-owned Python child.

        Args:
            *args: Ignored production command; no agent or Locust code is executed.
            **kwargs: Production environment and stdout/stderr configuration.

        Returns:
            A sleeping subprocess that requires the runner to terminate and reap it.
        """
        child = await original_spawn(sys.executable, "-c", "import time; time.sleep(60)", **kwargs)
        children.append(child)
        return child

    def fail_worker_metadata(path: Path, value: Any) -> None:
        """Keep worker ownership metadata unavailable after a successful spawn.

        Args:
            path: Runner-selected snapshot destination.
            value: Configuration or worker metadata to persist.

        Raises:
            OSError: Every worker.json write fails before touching real storage.
        """
        if path.name == "worker.json":
            failed_paths.append(path)
            raise OSError("synthetic-worker-metadata-failure")
        original_write(path, value)

    monkeypatch.setattr(locust_runner.asyncio, "create_subprocess_exec", controlled_spawn)
    monkeypatch.setattr(locust_runner, "atomic_json", fail_worker_metadata)
    monkeypatch.setenv("BENCHMARK_CONNECTIONS", "{}")
    monkeypatch.setenv("BENCHMARK_ALLOWED_TARGETS", "[]")
    request = RunRequest(
        target={"url": "http://127.0.0.1:9999/chat"},
        evaluation={
            "description": "Synthetic subprocess cleanup",
            "scorers": [],
            "samples": [{"inputs": {"query": "Never dispatched"}}],
        },
        load={
            "concurrency": 1,
            "duration_seconds": 0.1,
            "max_requests": 1,
            "timeout_seconds": 0.1,
        },
    )
    try:
        with pytest.raises(OSError, match="synthetic-worker-metadata-failure"):
            await asyncio.wait_for(
                locust_runner.run_load(
                    request,
                    str(uuid4()),
                    asyncio.Event(),
                    artifact_dir=tmp_path,
                    phase=phase,
                ),
                timeout=12,
            )
        assert len(failed_paths) == len(children) == 1
        assert children[0].returncode is not None
        assert await asyncio.wait_for(children[0].wait(), timeout=2) == children[0].returncode
    finally:
        await reap_children(children)


@pytest.mark.parametrize("exit_code", [0, 1, 2])
async def test_worker_exit_contract_cannot_certify_abnormal_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int
) -> None:
    """A written result cannot hide an abnormal worker exit; Locust errors may exit one."""
    original_spawn = asyncio.create_subprocess_exec
    children: list[asyncio.subprocess.Process] = []

    async def controlled_spawn(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        child = await original_spawn(
            sys.executable,
            "-c",
            "import json, os, sys; "
            "from pathlib import Path; "
            "Path(os.environ['BENCHMARK_LOCUST_RESULT']).write_text("
            "json.dumps({'summary': {'total_requests': 0}})); "
            f"sys.exit({exit_code})",
            **kwargs,
        )
        children.append(child)
        return child

    monkeypatch.setattr(locust_runner.asyncio, "create_subprocess_exec", controlled_spawn)
    request = RunRequest(
        target={"url": "http://127.0.0.1:9999/chat"},
        evaluation={
            "description": "No target traffic",
            "scorers": [],
            "samples": [{"inputs": {"query": "Unused"}}],
        },
        load={"duration_seconds": 300, "max_requests": 1},
    )
    try:
        rows, summary = await asyncio.wait_for(
            locust_runner.run_load(request, str(uuid4()), asyncio.Event(), tmp_path), timeout=5
        )
        assert rows == []
        assert summary["worker_exit_code"] == exit_code
        assert summary["worker_timed_out"] is False
        assert summary["measurement_complete"] is (exit_code in {0, 1})
        assert summary["load_status"] == ("completed" if exit_code in {0, 1} else "interrupted")
    finally:
        await reap_children(children)


async def test_worker_watchdog_records_timeout_and_reaps_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expose a distinct timeout without waiting for the real startup grace."""
    original_spawn = asyncio.create_subprocess_exec
    children: list[asyncio.subprocess.Process] = []

    async def controlled_spawn(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        child = await original_spawn(sys.executable, "-c", "import time; time.sleep(60)", **kwargs)
        children.append(child)
        return child

    clock = iter([0.0, 100.0, 100.0])
    monkeypatch.setattr(locust_runner, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    monkeypatch.setattr(locust_runner.asyncio, "create_subprocess_exec", controlled_spawn)
    request = RunRequest(
        target={"url": "http://127.0.0.1:9999/chat"},
        evaluation={
            "description": "No target traffic",
            "scorers": [],
            "samples": [{"inputs": {"query": "Unused"}}],
        },
        load={"duration_seconds": 0.1, "timeout_seconds": 0.1, "max_requests": 1},
    )
    try:
        rows, summary = await asyncio.wait_for(
            locust_runner.run_load(request, str(uuid4()), asyncio.Event(), tmp_path), timeout=5
        )
        assert rows == []
        assert summary["worker_timed_out"] is True
        assert summary["load_status"] == "interrupted"
        assert summary["measurement_complete"] is False
        assert children[0].returncode is not None
    finally:
        await reap_children(children)
