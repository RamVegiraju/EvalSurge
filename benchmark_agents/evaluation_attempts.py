"""Optional operator-owned real judge dispatch accounting; never replace inference."""

import fcntl
import json
import os
import stat
import time
from pathlib import Path
from typing import Any


def record_judge_attempt(path: Path, maximum: int) -> int:
    """Durably reserve a genuine HTTP transport attempt before provider dispatch.

    Args:
        path: Operator-owned journal in a private 0700 directory.
        maximum: Positive cap shared across this validation lease's children.

    Raises:
        RuntimeError: Unsafe journal permissions or an exhausted attempt budget.

    Returns:
        The reserved one-based attempt sequence.

    The locked 0600 append-only record contains sequence/time only. Failed sends
    still consume reservations. Bodies, model inputs, URLs and credentials are
    never recorded; reservations are not provider billing receipts.
    """
    if maximum < 1 or maximum > 100_000:
        raise RuntimeError("Invalid operator judge attempt cap")
    parent = path.parent.stat()
    if parent.st_mode & 0o077 or parent.st_uid != os.getuid():
        raise RuntimeError("Judge attempt directory must be private and owned")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+", encoding="utf-8") as stream:
        metadata = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_mode & 0o077
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or metadata.st_size > 16 * 1024 * 1024
        ):
            raise RuntimeError("Judge attempt journal must be a bounded private regular file")
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        count = sum(json.loads(line).get("kind") == "attempt" for line in stream if line.strip())
        if count >= maximum:
            raise RuntimeError("Operator judge attempt budget exhausted")
        stream.write(
            json.dumps({"kind": "attempt", "attempt": count + 1, "reserved_at_ns": time.time_ns()})
            + "\n"
        )
        stream.flush()
        os.fsync(stream.fileno())
        return count + 1


def record_judge_outcome(path: Path, attempt: int, **outcome: Any) -> None:
    """Append fixed content-free response/failure evidence without refunding spend.

    Args:
        path: The already validated owner-only attempt journal.
        attempt: Reserved sequence of the actual dispatch.
        outcome: Fixed HTTP status or safe failure class, never exception text.

    Raises:
        RuntimeError: Unsafe, missing or oversized journal.
    """
    record_private_event(
        path,
        {
            "kind": "outcome",
            "attempt": attempt,
            "recorded_at_ns": time.time_ns(),
            **outcome,
        },
    )


def record_private_event(path: Path, event: dict[str, Any]) -> None:
    """Append a fixed content-free owned worker/transport receipt with safe modes.

    Args:
        path: Operator-owned private regular journal, not a public request field.
        event: Internally constructed receipt containing no captured content.

    Raises:
        RuntimeError: The journal location, permissions or bounds are unsafe.
    """
    parent = path.parent.stat()
    if parent.st_mode & 0o077 or parent.st_uid != os.getuid():
        raise RuntimeError("Worker receipt directory must be private and owned")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as stream:
        metadata = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_mode & 0o077
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or metadata.st_size > 16 * 1024 * 1024
        ):
            raise RuntimeError("Unsafe judge outcome journal")
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.write(json.dumps(event, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def install_judge_attempt_guard() -> None:
    """Attach a dispatch hook to genuine clients when a private lease is configured.

    Raises:
        RuntimeError: A partial or invalid operator journal/cap configuration exists.

    The native authenticated HTTP client and transport are unchanged. OpenAI's
    actual initial sends/retries each trigger the reservation hook. This optional
    operator-only validation control is not a public request or scorer plugin.
    """
    path = os.environ.get("BENCHMARK_EVALUATION_JUDGE_ATTEMPT_JOURNAL")
    cap = os.environ.get("BENCHMARK_EVALUATION_JUDGE_MAX_ATTEMPTS")
    if not path and not cap:
        return
    if not path or not cap:
        raise RuntimeError("Judge attempt accounting requires both journal and cap")
    maximum = int(cap)
    journal = Path(path)
    if not journal.is_absolute():
        raise RuntimeError("Judge attempt journal must be an absolute operator path")
    import httpx

    from . import judges
    from .configuration import getenv

    genuine_client = judges.judge_client

    def bounded_client(**options: Any) -> Any:
        """Keep genuine SDK authentication/transport and count each real dispatch."""
        client = genuine_client(**options)

        def before_dispatch(_request: Any) -> None:
            """Reserve the actual send without inspecting protected request data."""
            _request.extensions["evalsurge.judge_attempt"] = record_judge_attempt(journal, maximum)
            record_private_event(
                journal,
                {
                    "kind": "dispatch_context",
                    "attempt": _request.extensions["evalsurge.judge_attempt"],
                    "phase": getenv("BENCHMARK_EVALUATION_INTERNAL_PHASE"),
                    "pid": os.getpid(),
                },
            )

        def after_response(response: Any) -> None:
            """Record genuine HTTP status without accessing headers or response data."""
            attempt = response.request.extensions.get("evalsurge.judge_attempt")
            if isinstance(attempt, int):
                record_judge_outcome(journal, attempt, http_status=int(response.status_code))

        client._client.event_hooks["request"].append(before_dispatch)
        client._client.event_hooks["response"].append(after_response)
        genuine_send = client._client.send

        def observed_send(request: Any, *args: Any, **kwargs: Any) -> Any:
            """Observe safe failures while preserving the actual HTTP send method."""
            try:
                return genuine_send(request, *args, **kwargs)
            except Exception as error:  # noqa: BLE001
                attempt = request.extensions.get("evalsurge.judge_attempt")
                if isinstance(attempt, int):
                    category = (
                        "http_timeout"
                        if isinstance(error, httpx.TimeoutException)
                        else "http_connection_failed"
                        if isinstance(error, httpx.TransportError)
                        else "http_send_failed"
                    )
                    record_judge_outcome(journal, attempt, error_category=category)
                raise

        client._client.send = observed_send
        return client

    judges.judge_client = bounded_client
