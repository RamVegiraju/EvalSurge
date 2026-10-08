"""Bounded synchronous v2 client; the API host remains the load generator.

Requests use one configured service origin and never follow server links or
redirects. Submission/cancellation and uncertain transport failures are not
retried. Reports contain protected workload evidence; exception messages and
object representations omit their contents and service credentials.
"""

import ipaddress
import json
import math
import re
import time
from collections.abc import Callable, Mapping
from contextlib import closing, suppress
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import ValidationError

from benchmark_agents.v2_models import Acknowledgment, Report, Result, RunCreate, RunStatus
from benchmark_agents.validation import encode_request

MAX_REQUEST_BYTES = 8_000_000
_ACTIVE = {"queued", "planning", "preflighting", "running", "profiling", "evaluating"}
_SUCCESS = {"completed", "completed_with_gaps"}
_FAILURE = {"failed", "cancelled", "interrupted"}
_STATUSES = _ACTIVE | _SUCCESS | _FAILURE


class RemoteError(RuntimeError):
    """Fixed safe message with bounded diagnostic attributes, never raw bodies."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
        retry_after_seconds: float | None = None,
        phase: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        self.retry_after_seconds = retry_after_seconds
        self.phase = phase
        self.retryable = retryable
        super().__init__(message)


class RemoteUnauthorizedError(RemoteError):
    """The service rejected authentication or authorization."""


class RemoteRateLimitError(RemoteError):
    """The service refused admission/read traffic with HTTP 429."""


class RemoteConflictError(RemoteError):
    """The request conflicts with server lifecycle/idempotency state."""


class RemoteProtocolError(RemoteError):
    """The service returned an invalid, oversized, or redirected response."""


class RemoteTransportError(RemoteError):
    """Transport failed; a submitted mutation may already have been admitted."""


class RemoteTimeout(RemoteError):
    """A transport/poll deadline elapsed; server-side work was not cancelled."""


class RemoteRunFailed(RemoteError):
    """Failed lifecycle with protected report retained only on the attribute."""

    def __init__(self, report: dict[str, Any] | Report) -> None:
        self.report = report
        super().__init__("Benchmark run failed, was cancelled, or was interrupted; inspect report.")


def _positive(value: Any, label: str) -> float:
    """Require a positive finite numeric timing/size bound without coercing strings."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a positive finite number")
    try:
        valid = math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{label} must be a positive finite number")
    return float(value)


def _url(value: str) -> str:
    """Validate one operator-selected HTTPS service or loopback HTTP prefix.

    Args:
        value: Service URL with an optional path prefix.

    Returns:
        Normalized URL without a trailing slash; no network/credential resolution.

    Raises:
        ValueError: Unsafe scheme, authority, control characters, or path aliases.
    """
    if not isinstance(value, str) or any(ord(char) < 33 or ord(char) == 127 for char in value):
        raise ValueError("Service URL must be an absolute HTTPS or loopback HTTP URL")
    try:
        parts = urlsplit(value)
        host = parts.hostname
        parts.port
        loopback = host == "localhost"
        if host is not None and not loopback:
            with suppress(ValueError):
                loopback = ipaddress.ip_address(host).is_loopback
        if (
            not host
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
            or "?" in value
            or "#" in value
            or "\\" in value
            or parts.scheme not in {"https", "http"}
            or (parts.scheme == "http" and not loopback)
        ):
            raise ValueError
        # Reject encoded path separators/control characters and traversal aliases.
        if re.search(r"%(?:0[0-9a-f]|1[0-9a-f]|7f|2f|5c|2e)", parts.path, re.I):
            raise ValueError
        if any(segment in {".", ".."} for segment in parts.path.split("/")):
            raise ValueError
        return str(httpx.URL(value)).rstrip("/")
    except (ValueError, httpx.InvalidURL):
        raise ValueError("Service URL must be an absolute HTTPS or loopback HTTP URL") from None


def _run_id(value: UUID | str) -> UUID:
    """Validate IDs before constructing paths, with no arbitrary server path input."""
    try:
        if not isinstance(value, (UUID, str)):
            raise ValueError
        return UUID(str(value))
    except ValueError:
        raise ValueError("Run ID must be a UUID") from None


def _hint(value: Any) -> float | None:
    """Accept finite nonnegative poll hints; invalid hints use the client default."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value) if math.isfinite(value) and value >= 0 else None
    except OverflowError:
        return None


def _token(value: Any) -> str | None:
    """Retain bounded structured identifiers without including them in messages."""
    return value if isinstance(value, str) and re.fullmatch(r"[\w.-]{1,128}", value) else None


@dataclass(frozen=True, slots=True)
class RemoteRun:
    """A service-owned run handle; representations carry no credentials or data."""

    id: UUID
    _client: "RemoteClient" = field(repr=False)
    _poll_after_seconds: float = field(default=0, repr=False)

    @property
    def report_url(self) -> str:
        """Return a locally constructed report shell URL with no credentials."""
        return self._client.report_url(self.id)

    def status(self) -> dict[str, Any]:
        """Read lightweight lifecycle status without changing server work."""
        return self._client.status(self.id)

    def wait(self, timeout: float | None = 3600) -> dict[str, Any]:
        """Wait in seconds and return a report; timeout never cancels the run."""
        return self._client.wait(self.id, timeout=timeout, _initial_delay=self._poll_after_seconds)

    def result(self) -> dict[str, Any]:
        """Read the separate typed result, retaining independent phase outcomes."""
        return self._client.result(self.id)

    def report(self, *, offset: int = 0, limit: int = 25) -> dict[str, Any]:
        """Read protected report content using bounded pagination."""
        return self._client.report(self.id, offset=offset, limit=limit)

    def cancel(self) -> dict[str, Any]:
        """Request dispatch cancellation once; active requests still drain."""
        return self._client.cancel(self.id)


class RemoteClient:
    """Synchronous HTTP context; closing it does not cancel server-owned work.

    Owns its HTTP client unless supplied by the caller. The default client ignores
    proxy/netrc environment discovery. Caller-supplied clients retain their own
    transport configuration and ownership. All methods are synchronous.
    """

    def __init__(
        self,
        url: str,
        *,
        api_key: str | None = None,
        request_timeout: float = 30,
        poll_interval: float = 1,
        max_response_bytes: int = 8_000_000,
        http_client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        """Configure safe transport without performing network requests.

        Args:
            url: Exact service origin and optional path prefix; HTTPS unless loopback.
            api_key: Optional inbound service key, sent in X-API-Key only.
            request_timeout: Positive per-I/O HTTP timeout, in seconds.
            poll_interval: Positive default poll delay, in seconds.
            max_response_bytes: Maximum decoded bytes for any response body.
            http_client: Borrowed client; never closed here or used with redirects.
            transport: Optional controlled transport for an owned client.
            sleep: Poll sleeper accepting seconds; injectable for offline tests.
            clock: Monotonic seconds used for total waiting budget.
            wall_clock: Unix seconds used to parse HTTP-date Retry-After values.

        Raises:
            ValueError: Invalid URL, bounds, header value, or conflicting ownership.

        Per-I/O transport timeouts cannot provide process-level interruption of a
        stalled caller-supplied transport. Poll deadlines are checked between I/O.
        """
        self._url = _url(url)
        self._request_timeout = _positive(request_timeout, "request_timeout")
        self._poll_interval = _positive(poll_interval, "poll_interval")
        if (
            isinstance(max_response_bytes, bool)
            or not isinstance(max_response_bytes, int)
            or not 1 <= max_response_bytes <= 64_000_000
        ):
            raise ValueError("max_response_bytes must be an integer from 1 to 64000000")
        if api_key is not None and (
            not isinstance(api_key, str)
            or not api_key
            or any(ord(char) < 32 or ord(char) > 126 for char in api_key)
        ):
            raise ValueError("api_key must be a nonempty ASCII HTTP header value")
        if http_client is not None and transport is not None:
            raise ValueError("Supply either http_client or transport, not both")
        self._headers = {"X-API-Key": api_key} if api_key is not None else {}
        self._max_response_bytes = max_response_bytes
        self._sleep = sleep
        self._clock = clock
        self._wall_clock = wall_clock
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(transport=transport, trust_env=False)
        self._closed = False

    def __repr__(self) -> str:
        return f"RemoteClient(closed={self._closed})"

    def __enter__(self) -> "RemoteClient":
        if self._closed:
            raise RuntimeError("Remote client is closed")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close owned transport once, without cancelling server-side runs."""
        if not self._closed:
            self._closed = True
            if self._owns_client:
                self._client.close()

    def _retry_after(self, value: str | None) -> float | None:
        """Interpret Retry-After seconds or HTTP date, omitting malformed values."""
        if value is None or len(value) > 128:
            return None
        if re.fullmatch(r"\d+", value):
            try:
                return _hint(float(value))
            except ValueError:
                return None
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                return None
            return _hint(max(0.0, date.timestamp() - self._wall_clock()))
        except (TypeError, ValueError, OverflowError):
            return None

    def _request(
        self,
        method: str,
        path: str,
        *,
        content: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, int] | None = None,
        timeout: float | None = None,
    ) -> tuple[dict[str, Any], float | None]:
        """Send one bounded request without redirect, mutation retry, or raw errors.

        Args:
            method: Fixed operation's HTTP method.
            path: Internally constructed resource path, never a response link.
            content: Optional prevalidated bounded JSON bytes.
            headers: Optional fixed-name idempotency header.
            params: Optional prevalidated pagination integers.
            timeout: Remaining wait budget in seconds, limiting per-I/O timeout.

        Returns:
            Parsed JSON object and optional Retry-After seconds.

        Raises:
            RemoteError: Safe HTTP/transport/protocol failure.
            RuntimeError: Client has been closed.
        """
        if self._closed:
            raise RuntimeError("Remote client is closed")
        request_headers = {"Accept": "application/json", **self._headers, **(headers or {})}
        if content is not None:
            request_headers["Content-Type"] = "application/json"
        try:
            request = self._client.build_request(
                method,
                self._url + path,
                content=content,
                headers=request_headers,
                params=params,
                timeout=min(self._request_timeout, timeout)
                if timeout is not None
                else self._request_timeout,
            )
            response = self._client.send(request, stream=True, follow_redirects=False, auth=None)
            with closing(response):
                retry_after = self._retry_after(response.headers.get("Retry-After"))
                if 300 <= response.status_code < 400:
                    raise RemoteProtocolError("Service redirects are unsupported.")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    if len(raw) + len(chunk) > self._max_response_bytes:
                        raise RemoteProtocolError(
                            "Service response exceeds the configured byte limit."
                        )
                    raw.extend(chunk)
                try:
                    body = json.loads(raw)
                except (ValueError, UnicodeDecodeError, RecursionError):
                    body = None
                if response.status_code >= 400:
                    error = body.get("error") if isinstance(body, dict) else None
                    error = error if isinstance(error, dict) else {}
                    kind = {
                        401: RemoteUnauthorizedError,
                        403: RemoteUnauthorizedError,
                        409: RemoteConflictError,
                        429: RemoteRateLimitError,
                    }.get(response.status_code, RemoteError)
                    raise kind(
                        f"EvalSurge service returned HTTP {response.status_code}.",
                        status_code=response.status_code,
                        code=_token(error.get("code")),
                        request_id=_token(error.get("request_id")),
                        retry_after_seconds=retry_after,
                        phase=_token(error.get("phase")),
                        retryable=error.get("retryable")
                        if isinstance(error.get("retryable"), bool)
                        else None,
                    )
                if not 200 <= response.status_code < 300 or not isinstance(body, dict):
                    raise RemoteProtocolError("Service response is not a valid JSON object.")
                return body, retry_after
        except httpx.TimeoutException:
            raise RemoteTimeout(
                "Remote request timed out; server-side work was not cancelled."
            ) from None
        except httpx.RequestError:
            raise RemoteTransportError(
                "Remote transport failed; a submitted run may have been admitted. No request was retried."
            ) from None

    @staticmethod
    def _state(
        body: dict[str, Any], run_id: UUID | None = None, *, cancellation_ack: bool = False
    ) -> UUID:
        """Validate lifecycle identity/status; never trust server-provided URLs."""
        try:
            identifier = _run_id(body.get("id"))
        except ValueError:
            raise RemoteProtocolError("Service response has an invalid run identity.") from None
        status = body.get("status")
        if (
            not isinstance(status, str)
            or (
                status not in _STATUSES
                and not (cancellation_ack and status == "cancellation_requested")
            )
            or (run_id is not None and identifier != run_id)
        ):
            raise RemoteProtocolError("Service response has an invalid run lifecycle.")
        return identifier

    def start(
        self, config: Mapping[str, Any] | RunCreate, *, idempotency_key: str | None = None
    ) -> RemoteRun:
        """Submit once and return a run handle; no inference occurs on this client.

        Args:
            config: Typed or JSON-compatible v2 request validated before traffic.
            idempotency_key: Optional explicit key used for safe caller-directed recovery.

        Returns:
            Handle bound to this service and acceptance poll guidance.

        Raises:
            ValueError: Configuration/header is invalid or exceeds eight million bytes.
            RemoteError: Service/transport failure. Uncertain POSTs are never replayed.
        """
        _, content = encode_request(config)
        headers = {}
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not re.fullmatch(
                r"[!-~]{1,128}", idempotency_key
            ):
                raise ValueError("Idempotency key must contain 1 to 128 printable ASCII characters")
            headers["Idempotency-Key"] = idempotency_key
        body, retry = self._request("POST", "/v2/runs", content=content, headers=headers)
        identifier = self._state(body)
        delay = max(retry or 0, _hint(body.get("poll_after_seconds")) or 0)
        return RemoteRun(identifier, self, delay)

    def status(self, run_id: UUID | str) -> dict[str, Any]:
        """Read and validate one lifecycle snapshot; no automatic retries."""
        identifier = _run_id(run_id)
        body, _ = self._request("GET", f"/v2/runs/{identifier}")
        self._state(body, identifier)
        return body

    def result(self, run_id: UUID | str) -> dict[str, Any]:
        """Read the separate protected result without executing or retrying a run."""
        identifier = _run_id(run_id)
        body, _ = self._request("GET", f"/v2/runs/{identifier}/result")
        self._state(body, identifier)
        return body

    def report_url(self, run_id: UUID | str) -> str:
        """Construct the report shell URL locally; only the validated UUID is added."""
        return f"{self._url}/reports/?run={_run_id(run_id)}"

    def report(self, run_id: UUID | str, *, offset: int = 0, limit: int = 25) -> dict[str, Any]:
        """Read a protected report page with 1–100 rows and bounded offset."""
        identifier = _run_id(run_id)
        params = self._pagination(offset, limit)
        body, _ = self._request("GET", f"/v2/runs/{identifier}/report", params=params)
        self._report_state(body, identifier)
        return body

    @staticmethod
    def _pagination(offset: int, limit: int) -> dict[str, int]:
        if type(offset) is not int or not 0 <= offset <= 10_000:
            raise ValueError("offset must be an integer from 0 to 10000")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer from 1 to 100")
        return {"offset": offset, "limit": limit}

    @staticmethod
    def _report_state(body: dict[str, Any], run_id: UUID | None = None) -> str:
        run = body.get("run")
        if (
            not isinstance(run, dict)
            or not isinstance(run.get("status"), str)
            or run["status"] not in _STATUSES
        ):
            raise RemoteProtocolError("Service report has an invalid run lifecycle.")
        if run_id is not None and "id" in run:
            RemoteClient._state(run, run_id)
        return run["status"]

    def cancel(self, run_id: UUID | str) -> dict[str, Any]:
        """Send one cancellation request; transport failure never triggers a replay."""
        identifier = _run_id(run_id)
        body, _ = self._request("POST", f"/v2/runs/{identifier}/cancel")
        self._state(body, identifier, cancellation_ack=True)
        return body

    def capabilities(self) -> dict[str, Any]:
        """Read capabilities only; does not start a target/planner/judge call."""
        body, _ = self._request("GET", "/v2/capabilities")
        return body

    def wait(
        self,
        run_id: UUID | str,
        timeout: float | None = 3600,
        *,
        _initial_delay: float = 0,
    ) -> dict[str, Any]:
        """Poll lifecycle/report readiness with a total budget measured in seconds.

        Args:
            run_id: Existing service run UUID.
            timeout: Positive total wait seconds; None explicitly waits indefinitely.
            _initial_delay: Acceptance guidance supplied by RemoteRun.

        Returns:
            Report on completed/completed_with_gaps; completion is not a quality pass.

        Raises:
            RemoteRunFailed: Failed lifecycle; report retained as protected evidence.
            RemoteTimeout: Deadline expired; server-side run is never cancelled.
            RemoteError: Nonretryable response or uncertain transport failure.

        Only read-side HTTP 429 and report_not_ready HTTP 409 are retried. Sleeps
        honor both Retry-After and JSON poll hints, capped by remaining wait budget.
        """
        identifier = _run_id(run_id)
        deadline = self._clock() + _positive(timeout, "timeout") if timeout is not None else None

        def remaining() -> float | None:
            budget = deadline - self._clock() if deadline is not None else None
            if budget is not None and budget <= 0:
                raise RemoteTimeout("Remote wait timed out; server-side run was not cancelled.")
            return budget

        def pause(seconds: float) -> None:
            budget = remaining()
            self._sleep(min(seconds, budget) if budget is not None else seconds)
            remaining()

        if _initial_delay:
            pause(_initial_delay)
        terminal = False
        while True:
            try:
                if terminal:
                    body, _ = self._request(
                        "GET",
                        f"/v2/runs/{identifier}/report",
                        params=self._pagination(0, 25),
                        timeout=remaining(),
                    )
                    remaining()
                    status = self._report_state(body, identifier)
                    if status in _FAILURE:
                        raise RemoteRunFailed(body)
                    if status not in _SUCCESS:
                        raise RemoteProtocolError("Terminal report has an inconsistent lifecycle.")
                    return body
                body, retry = self._request("GET", f"/v2/runs/{identifier}", timeout=remaining())
                remaining()
                self._state(body, identifier)
                terminal = body["status"] in _SUCCESS | _FAILURE
                if not terminal:
                    hints = [
                        value
                        for value in (retry, _hint(body.get("poll_after_seconds")))
                        if value is not None
                    ]
                    pause(max(0.1, max(hints)) if hints else self._poll_interval)
            except RemoteRateLimitError as exc:
                pause(
                    max(0.1, exc.retry_after_seconds)
                    if exc.retry_after_seconds is not None
                    else self._poll_interval
                )
            except RemoteConflictError as exc:
                if not terminal or exc.code != "report_not_ready":
                    raise
                pause(
                    max(0.1, exc.retry_after_seconds)
                    if exc.retry_after_seconds is not None
                    else self._poll_interval
                )


def _typed_response(model: type[Any], body: dict[str, Any]) -> Any:
    """Validate a protected response without putting native validation values in errors."""
    try:
        return model.model_validate(body)
    except ValidationError:
        raise RemoteProtocolError(
            "Service response does not match the documented typed contract."
        ) from None


@dataclass(frozen=True, slots=True)
class TypedRemoteRun:
    """A typed service-owned handle; closing its client does not cancel its work."""

    id: UUID
    _client: "TypedRemoteClient" = field(repr=False)
    _poll_after_seconds: float = field(default=0, repr=False)

    @property
    def report_url(self) -> str:
        """Return the credential-free browser shell address."""
        return self._client.report_url(self.id)

    def status(self) -> RunStatus:
        """Read independent lifecycle phases without protected request contents."""
        return self._client.status(self.id)

    def wait(self, timeout: float | None = None) -> Report:
        """Wait in seconds; completion does not imply a passing quality verdict."""
        return self._client.wait(self.id, timeout=timeout, _initial_delay=self._poll_after_seconds)

    def result(self) -> Result:
        """Read available performance and protected quality evidence."""
        return self._client.result(self.id)

    def report(self, *, offset: int = 0, limit: int = 25) -> Report:
        """Read a bounded profile page alongside protected assessments."""
        return self._client.report(self.id, offset=offset, limit=limit)

    def cancel(self) -> Acknowledgment:
        """Request dispatch cancellation once; active requests drain."""
        return self._client.cancel(self.id)


class TypedRemoteClient(RemoteClient):
    """Additive typed v2 adapter; legacy RemoteClient dictionary methods stay intact."""

    def start(
        self, config: Mapping[str, Any] | RunCreate, *, idempotency_key: str | None = None
    ) -> TypedRemoteRun:
        """Validate and submit once using the existing bounded HTTP transport."""
        run = super().start(config, idempotency_key=idempotency_key)
        return TypedRemoteRun(run.id, self, run._poll_after_seconds)

    def status(self, run_id: UUID | str) -> RunStatus:
        """Read a validated lightweight status; never follow response links."""
        return _typed_response(RunStatus, super().status(run_id))

    def result(self, run_id: UUID | str) -> Result:
        """Read typed independent outcomes; no new model calls occur here."""
        return _typed_response(Result, super().result(run_id))

    def report(self, run_id: UUID | str, *, offset: int = 0, limit: int = 25) -> Report:
        """Read typed protected report data with bounded pagination."""
        return _typed_response(Report, super().report(run_id, offset=offset, limit=limit))

    def cancel(self, run_id: UUID | str) -> Acknowledgment:
        """Validate cancellation acknowledgment without replaying mutations."""
        return _typed_response(Acknowledgment, super().cancel(run_id))

    def wait(
        self, run_id: UUID | str, timeout: float | None = None, *, _initial_delay: float = 0
    ) -> Report:
        """Return a typed report; failed lifecycles retain typed evidence on the error.

        Timeout leaves service work active. False judge verdicts are returned normally.
        """
        try:
            body = super().wait(run_id, timeout, _initial_delay=_initial_delay)
        except RemoteRunFailed as error:
            raise RemoteRunFailed(_typed_response(Report, error.report)) from None
        return _typed_response(Report, body)
