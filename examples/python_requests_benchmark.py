"""Submit one benchmark with requests; the server owns Locust, storage, and judging.

Start the local mock and API in separate terminals, then run this checkout example:

    uv run --no-sync uvicorn examples.mock_agent:app --host 127.0.0.1 --port 9001
    uv run --no-sync uvicorn benchmark_agents.api:app --host 127.0.0.1 \
        --port 8000 --no-proxy-headers
    uv run --no-sync python -m examples.python_requests_benchmark \
        --target-url http://127.0.0.1:9001/chat

The generated request is performance-only: one prompt, no planning or scorers, a
300-second dispatch window, five users, and at most 5,000 measured attempts. The
server performs one extra excluded inference preflight; its failure skips load.
Duration/cap are competing stopping conditions, not an overall completion deadline.

For evaluation or another wire adapter, pass --request-file containing the complete
POST /v1/runs JSON contract. It is sent unchanged; target/load flags do not override
it. Select models, references, scorers, and connections explicitly in that contract
and server configuration. Remote target/planner/judge calls can incur spend or
execute tools. This example never chooses a workspace or creates judge clients.

Set BENCHMARK_API_KEY in the environment when required; it is sent only in X-API-Key.
API URLs cannot contain credentials, queries, or fragments; remote APIs require
HTTPS. Environment proxies/netrc, redirects, and retries are disabled. A request
file and server artifacts can contain protected prompts/references: do not commit
them. The report URL contains only the run ID; authenticate in the report UI.

--wait-timeout covers submission and polling in seconds, separately from HTTP
connect/read inactivity timeouts and the server's target deadline. Set
--http-read-timeout (default 30 seconds) for both submission and polls. Planning can
run before the creation response and exceed that default; increase it explicitly
(for example, --http-read-timeout 300) and allow sufficient --wait-timeout for the
server's planning budget plus the remaining phases. Expiry or Ctrl-C stops waiting,
never cancels or resubmits. Reconcile an uncertain submission using
the printed Idempotency-Key and server history before manually retrying: re-running
this CLI generates a new key. Requests timeouts are not hard wall-clock interrupts
for a peer that keeps sending bytes; the monotonic deadline bounds polling and
caps each transport timeout. Inference preflight, evaluation readiness, and load
errors are independent diagnostics. completed_with_gaps returns zero with a valid
report and an explicit gaps warning, not a quality/capacity verdict.
"""

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import requests

CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 30.0
POLL_INTERVAL_SECONDS = 0.5
MAX_REQUEST_BYTES = 8_000_000
TERMINAL_STATUSES = {"completed", "completed_with_gaps", "failed", "cancelled", "interrupted"}
ACTIVE_STATUSES = {"queued", "preflighting", "running", "profiling", "evaluating"}


class ExampleError(Exception):
    """Safe CLI failure without response bodies, input values, or transport exception text."""


def parse_options(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse explicit inputs and finite bounds without starting traffic.

    Args:
        arguments: CLI arguments, or None to read the process arguments.

    Returns:
        Validated command-line options; request-file contents remain server validated.

    Raises:
        SystemExit: Syntax, load bounds, wait timeout, or API URL is invalid.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--target-url", help="Authorized OpenAI Chat SSE endpoint; judging is off.")
    source.add_argument("--request-file", type=Path, help="Full run JSON, sent without overrides.")
    parser.add_argument(
        "--duration", type=float, default=300, help="Dispatch seconds; default 300."
    )
    parser.add_argument("--concurrency", type=int, default=5, help="Locust users; default 5.")
    parser.add_argument(
        "--max-requests", type=int, default=5000, help="Measured cap; default 5000."
    )
    parser.add_argument(
        "--wait-timeout", type=float, default=600, help="Overall wait seconds; default 600."
    )
    parser.add_argument(
        "--http-read-timeout",
        type=float,
        default=READ_TIMEOUT_SECONDS,
        help="API read inactivity seconds, including creation/planning; default 30.",
    )
    options = parser.parse_args(arguments)
    if not math.isfinite(options.duration) or not 0.1 <= options.duration <= 3600:
        parser.error("--duration must be finite and between 0.1 and 3600 seconds")
    if not 1 <= options.concurrency <= 100 or not 1 <= options.max_requests <= 10_000:
        parser.error("--concurrency must be 1..100 and --max-requests must be 1..10000")
    for name in ("wait_timeout", "http_read_timeout"):
        value = getattr(options, name)
        if not math.isfinite(value) or value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be finite and positive")
    try:
        parsed = urlsplit(options.api_url)
        port = parsed.port
        valid_url = (
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and parsed.username is None
            and parsed.password is None
            and "?" not in options.api_url
            and "#" not in options.api_url
            and (port is None or port > 0)
            and not any(character.isspace() for character in options.api_url)
            and (parsed.scheme == "https" or parsed.hostname in {"localhost", "127.0.0.1", "::1"})
        )
    except ValueError:
        valid_url = False
    if not valid_url:
        parser.error(
            "Use an HTTP(S) API URL without credentials/query/fragment; remote APIs need HTTPS"
        )
    options.api_url = options.api_url.rstrip("/")
    return options


def build_request(options: argparse.Namespace) -> dict[str, Any]:
    """Read the full contract or construct a bounded, explicitly performance-only workload.

    Args:
        options: Parsed options; a request file takes precedence over load defaults.

    Returns:
        One JSON object to submit, without local evaluation/model/profile selection.

    Raises:
        ExampleError: The file is unreadable, over eight MB, or not a JSON object.

    Only the selected file is read; the API validates its full schema before admission.
    """
    if options.request_file is not None:
        try:
            with options.request_file.open("rb") as request_file:
                contents = request_file.read(MAX_REQUEST_BYTES + 1)
            if len(contents) > MAX_REQUEST_BYTES:
                raise ExampleError("Request file exceeds the eight MB API input limit")
            body = json.loads(contents.decode("utf-8"))
        except (OSError, ValueError, UnicodeError):
            raise ExampleError("Request file must be a readable UTF-8 JSON object") from None
        if not isinstance(body, dict):
            raise ExampleError("Request file must contain the full run JSON object")
        return body
    return {
        "target": {"url": options.target_url},
        "evaluation": {
            "description": "Performance-only benchmark; no quality judging requested.",
            "scorers": [],
            "registered_scorers": [],
            "samples": [{"inputs": {"query": "Reply with a short greeting."}}],
        },
        "load": {
            "duration_seconds": options.duration,
            "concurrency": options.concurrency,
            "max_requests": options.max_requests,
        },
    }


def remaining_seconds(deadline: float) -> float:
    """Return remaining monotonic seconds without changing the server run.

    Args:
        deadline: Absolute monotonic deadline in seconds.

    Returns:
        Positive remaining wait in seconds.

    Raises:
        ExampleError: The overall deadline has elapsed; no cancellation is sent.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ExampleError(
            "Overall wait timeout expired; no cancellation was sent. The run may still be active."
        )
    return remaining


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    deadline: float,
    *,
    read_timeout: float | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Perform one HTTP operation, exposing only the API's safe error-envelope fields.

    Args:
        session: Caller-owned session with retries, ambient auth/proxies disabled.
        method: Explicit POST submission or GET poll.
        url: URL under the operator-selected API base, never a server redirect.
        deadline: Overall wait deadline in monotonic seconds.
        read_timeout: Positive finite API read inactivity limit in seconds,
            defaulting to READ_TIMEOUT_SECONDS; separate from server target timeouts.
        **kwargs: Submission JSON and idempotency header when applicable.

    Returns:
        Decoded JSON object; responses are closed before returning.

    Raises:
        ExampleError: Wait expiry, HTTP/transport failure, or invalid JSON contract.

    Connect/read inactivity timeouts are capped by the remaining wait. There is
    exactly one request: errors never trigger a retry, resubmission, or cancellation.
    """
    remaining = remaining_seconds(deadline)
    read_timeout = READ_TIMEOUT_SECONDS if read_timeout is None else read_timeout
    try:
        with session.request(
            method,
            url,
            timeout=(min(CONNECT_TIMEOUT_SECONDS, remaining), min(read_timeout, remaining)),
            allow_redirects=False,
            **kwargs,
        ) as response:
            try:
                body = response.json()
            except ValueError:
                body = None
            if not 200 <= response.status_code < 300:
                detail = body.get("error") if isinstance(body, dict) else None
                if isinstance(detail, dict) and all(
                    isinstance(detail.get(field), str)
                    for field in ("code", "message", "request_id")
                ):
                    safe = {field: detail[field] for field in ("code", "message", "request_id")}
                    raise ExampleError(
                        f"API HTTP {response.status_code}: {json.dumps({'error': safe})}"
                    )
                raise ExampleError(f"API HTTP {response.status_code}: no safe error envelope")
            if not isinstance(body, dict):
                raise ExampleError("API returned an invalid JSON object")
    except requests.Timeout:
        remaining_seconds(deadline)
        raise ExampleError(
            "API network timeout (connect/read); submission may have been accepted; no cancellation was sent."
        ) from None
    except requests.RequestException:
        raise ExampleError(
            "API transport failed; submission may have been accepted; no cancellation was sent."
        ) from None
    remaining_seconds(deadline)
    return body


def terminal_result(run: dict[str, Any]) -> int:
    """Print independent safe phase diagnostics and the terminal lifecycle result.

    Args:
        run: API snapshot whose terminal status was validated by the polling loop.

    Returns:
        Zero for completed or completed_with_gaps, otherwise one. Gaps produce an
        explicit warning, not a quality pass or a relabelled inference failure.

    Writes stdout/stderr, but never mutates the snapshot, replays, or cancels work.
    Only public error code/message/guidance fields are copied, not raw captures.
    """
    status = run["status"]
    print(f"Status: {status}", flush=True)
    if status == "completed":
        return 0
    if status == "completed_with_gaps":
        print(
            "Valid report available with gaps; inspect phase outcomes and coverage. "
            "Lifecycle completion is not a quality pass.",
            file=sys.stderr,
        )
    else:
        print(f"Run ended {status}.", file=sys.stderr)
    for name, label in (
        ("preflight", "Inference preflight"),
        ("evaluation_preflight", "Evaluation preflight"),
    ):
        phase = run.get(name)
        if isinstance(phase, dict):
            safe = {
                field: phase[field]
                for field in ("status", "request_id", "http_status")
                if field in phase
            }
            error = phase.get("error")
            if isinstance(error, dict):
                safe["error"] = {
                    field: error[field]
                    for field in ("code", "message", "guidance")
                    if isinstance(error.get(field), str)
                }
            print(f"{label}: {json.dumps(safe)}", file=sys.stderr)
    error = run.get("load_error")
    if isinstance(error, dict):
        safe = {
            field: error[field]
            for field in ("code", "message", "guidance")
            if isinstance(error.get(field), str)
        }
        print(f"Load error: {json.dumps(safe)}", file=sys.stderr)
    return int(status != "completed_with_gaps")


def main(arguments: Sequence[str] | None = None) -> int:
    """Submit once, poll the lifecycle, and print an authenticated report-shell URL.

    Args:
        arguments: Optional CLI arguments, otherwise the process arguments.

    Returns:
        Zero for lifecycle completion (including gaps), one for API/run/wait errors,
        or 130 when interrupted locally. Completion is not a quality pass.

    Raises:
        SystemExit: Command-line syntax or bounds are invalid before submission.

    Owns/closes one Session. The server owns execution even after local wait expiry.
    Independent phase diagnostics are safe public fields, never raw probe captures.
    """
    options = parse_options(arguments)
    try:
        body = build_request(options)
        key = str(uuid4())
        print(f"Idempotency-Key: {key}", file=sys.stderr, flush=True)
        deadline = time.monotonic() + options.wait_timeout
        with requests.Session() as session:
            session.trust_env = False
            if api_key := os.getenv("BENCHMARK_API_KEY"):
                session.headers["X-API-Key"] = api_key
            accepted = request_json(
                session,
                "POST",
                f"{options.api_url}/v1/runs",
                deadline,
                read_timeout=options.http_read_timeout,
                json=body,
                headers={"Idempotency-Key": key},
            )
            try:
                run_id = str(UUID(accepted["id"]))
            except (KeyError, TypeError, ValueError, AttributeError):
                raise ExampleError(
                    "API submission returned an invalid run ID; reconcile before retrying"
                ) from None
            print(f"Report URL: {options.api_url}/reports/?run={run_id}", flush=True)
            while True:
                run = request_json(
                    session,
                    "GET",
                    f"{options.api_url}/v1/runs/{run_id}",
                    deadline,
                    read_timeout=options.http_read_timeout,
                )
                status = run.get("status")
                if not isinstance(status, str) or status not in ACTIVE_STATUSES | TERMINAL_STATUSES:
                    raise ExampleError("API returned an unknown lifecycle status")
                if status in TERMINAL_STATUSES:
                    return terminal_result(run)
                time.sleep(min(POLL_INTERVAL_SECONDS, remaining_seconds(deadline)))
    except ExampleError as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(
            "Stopped waiting; no cancellation was sent. Reconcile before resubmitting.",
            file=sys.stderr,
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
