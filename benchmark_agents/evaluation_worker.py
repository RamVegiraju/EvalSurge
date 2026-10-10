"""Private native evaluation entry point; process environment is set before import."""

import json
import logging
import os
import sys
import time
from pathlib import Path


def main() -> int:
    """Evaluate a bounded protected transfer and emit only a safe protected outcome.

    Returns:
        Zero after a valid bounded outcome is durably written; one on startup,
        transfer or persistence failures. No raw exception is printed.

    The parent owns deadlines, cancellation and process cleanup. Native startup
    flags are established before importing MLflow, OpenAI or SDK modules. The
    worker receives detached operator environment/authentication through startup,
    which is never persisted in the transfer or result files. It receives no
    target invocation instructions and never invokes a target; this environment
    inheritance is not an allowlist or a sandbox for trusted scorer code.
    """
    from .evaluation_process import MAX_PRIVATE_BYTES, NATIVE_ENVIRONMENT, write_private_json

    os.environ.update(NATIVE_ENVIRONMENT)
    counts = {
        "pool_exhaustion": 0,
        "tag_write": 0,
        "assessment_write": 0,
        "trace_export": 0,
        "trace_refresh": 0,
        "sqlite_lock": 0,
        "other": 0,
    }

    class SafeWarnings(logging.Handler):
        """Count fixed persistence categories without retaining native messages."""

        def emit(self, record: logging.LogRecord) -> None:
            text = record.getMessage().lower()
            if "queuepool" in text or "connection pool" in text:
                counts["pool_exhaustion"] += 1
            elif "database is locked" in text:
                counts["sqlite_lock"] += 1
            elif "tag" in text and ("failed" in text or "error" in text):
                counts["tag_write"] += 1
            elif "assessment" in text and ("failed" in text or "error" in text):
                counts["assessment_write"] += 1
            elif "refresh trace" in text and ("failed" in text or "error" in text):
                counts["trace_refresh"] += 1
            elif "span" in text or "trace" in text:
                counts["trace_export"] += 1
            else:
                counts["other"] += 1

    handler = SafeWarnings(level=logging.WARNING)
    logging.getLogger().handlers = [handler]
    logging.getLogger().setLevel(logging.WARNING)
    started = time.monotonic()
    try:
        source, destination = map(Path, sys.argv[1:])
        if source.stat().st_size > MAX_PRIVATE_BYTES or source.stat().st_mode & 0o077:
            return 1
        if source.parent.stat().st_mode & 0o077 or source.parent != destination.parent:
            return 1
        payload = json.loads(source.read_text())
        if os.environ.get("BENCHMARK_EVALUATION_STORAGE_ONLY") == "true":

            def prohibit_network(event, _args):
                """Forbid network in explicit pure-storage regression runs."""
                if event == "socket.connect":
                    raise RuntimeError("Storage-only worker forbids network")

            sys.addaudithook(prohibit_network)
        from mlflow.entities import Trace

        from .evaluation_attempts import install_judge_attempt_guard
        from .evaluator import _evaluate_native
        from .models import Plan

        # Native imports install non-propagating handlers; replace those exact
        # handlers only inside this worker, keeping all exported diagnostics safe.
        for logger_name in ("mlflow", "sqlalchemy", "alembic", "huey"):
            logger = logging.getLogger(logger_name)
            logger.handlers = [handler]
            logger.propagate = False
            logger.setLevel(logging.WARNING)
        install_judge_attempt_guard()
        traces = {key: Trace.from_json(value) for key, value in payload["traces"].items()}
        result = _evaluate_native(
            payload["rows"],
            Plan.model_validate(payload["plan"]),
            traces,
            fail_fast=payload["fail_fast"],
            phase=payload["phase"],
        )
        result["worker"] = {
            "pid": os.getpid(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "warning_counts": counts,
            "native_settings": NATIVE_ENVIRONMENT,
        }
        write_private_json(destination, result)
        return 0
    except Exception:  # noqa: BLE001
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
