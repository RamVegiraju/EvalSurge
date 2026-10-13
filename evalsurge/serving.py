"""Optional customer-process HTTP bridge; never imported by the load worker.

This helper requires ``evalsurge[server]`` and deliberately has no authentication,
instrumentation, retry, persistence or model-provider policy. Use it on loopback
for the tutorial; production endpoint authentication and handler deadlines belong
to the customer. Correlation/session keys are untrusted labels, not identities.
"""

import json
import math
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.datastructures import Headers
from starlette.requests import ClientDisconnect

from benchmark_agents.adapters import JSON_RESPONSE_LIMIT
from benchmark_agents.limits import MAX_REQUEST_BYTES
from benchmark_agents.trace_ids import MAX_TRACE_ID_CHARS, valid_wire_trace_id

Isolation = Literal["request", "case", "shared"]


@dataclass
class _ResponseTrace:
    """Invocation-owned native ID carrier; never process-global last-trace state."""

    trace_id: str | None = None


_response_trace: ContextVar[_ResponseTrace | None] = ContextVar(
    "evalsurge_response_trace", default=None
)


@dataclass(frozen=True)
class InvocationContext:
    """Untrusted correlation labels and the explicitly selected framework state key.

    ``run_id`` is absent for standalone request-isolated calls. ``session_id`` is
    an optional key the customer handler can pass to its own state store; this
    helper does not create memory, a session store, or an MLflow trace.
    """

    run_id: str | None
    request_id: str
    case_id: int | None
    session_id: str


class AnswerUsage(BaseModel):
    """Optional actual output-token count, not an estimate inferred from text."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    output_tokens: int = Field(ge=0)


class AgentAnswer(BaseModel):
    """A completed customer answer with optional actual token and trace evidence."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    outputs: str = Field(min_length=1, max_length=JSON_RESPONSE_LIMIT)
    trace_id: str | None = Field(default=None, min_length=1, max_length=MAX_TRACE_ID_CHARS)
    usage: AnswerUsage | None = None

    @field_validator("outputs", "trace_id")
    @classmethod
    def valid_text(cls, value: str | None) -> str | None:
        """Reject invalid evidence without modifying customer text.

        Args:
            value: Optional customer text already type/length checked by Pydantic.

        Returns:
            The original nonblank UTF-8 value, or absent optional evidence.

        Raises:
            ValueError: Blank, invalid Unicode, or excessive encoded-byte length.
        """
        if value is not None:
            if not value.strip():
                raise ValueError("Answer and trace text must be nonblank")
            try:
                encoded = value.encode("utf-8")
            except UnicodeEncodeError:
                raise ValueError("Answer and trace text must be valid UTF-8") from None
            if len(encoded) > JSON_RESPONSE_LIMIT:
                raise ValueError("Answer text exceeds the response byte limit")
        return value

    @field_validator("trace_id")
    @classmethod
    def valid_trace_id(cls, value: str | None) -> str | None:
        """Preserve legacy limits while accepting bounded native UC trace identifiers."""
        if value is not None and not valid_wire_trace_id(value):
            raise ValueError("Trace ID must meet the legacy or native UC identifier contract")
        return value


AgentHandler = Callable[[dict[str, Any], InvocationContext], Awaitable[AgentAnswer]]


def _failure(status: int, code: str, message: str, *, trace_id: str | None = None) -> JSONResponse:
    """Return only fixed helper diagnostics, never customer input/exception text."""
    headers = {"Cache-Control": "no-store"}
    if valid_wire_trace_id(trace_id) and all(32 <= ord(c) <= 126 for c in trace_id):
        headers["X-MLflow-Trace-ID"] = trace_id
    return JSONResponse(
        {"error": {"code": code, "message": message}},
        status_code=status,
        headers=headers,
    )


def _context(headers: Headers, isolation: Isolation) -> InvocationContext:
    """Resolve bounded benchmark headers without authenticating their sender.

    Args:
        headers: Caller-owned HTTP headers; repeated benchmark headers are invalid.
        isolation: Explicit state-key semantics selected by the customer operator.

    Returns:
        Immutable context. Request mode alone permits standalone calls and generates
        a fresh opaque request key when no benchmark headers were supplied.

    Raises:
        ValueError: Benchmark headers are malformed/incomplete, or case/shared mode
            lacks the necessary benchmark context. Messages omit header values.

    Run-scoped case/shared keys can retain probe side effects. They do not isolate
    shared globals, stores, tools or authenticated tenants.
    """
    names = ("X-Benchmark-Run-ID", "X-Benchmark-Request-ID", "X-Benchmark-Case-ID")
    values = [headers.getlist(name) for name in names]
    if any(len(value) > 1 for value in values):
        raise ValueError("Duplicate benchmark correlation headers")
    run_id, request_id, raw_case = [value[0] if value else None for value in values]
    if not any(values):
        if isolation != "request":
            raise ValueError("This isolation mode requires benchmark correlation headers")
        request_id = str(uuid4())
        return InvocationContext(None, request_id, None, request_id)
    if run_id is None or request_id is None:
        raise ValueError("Benchmark correlation requires both run and request IDs")
    for identifier in (run_id, request_id):
        if len(identifier) != 36:
            raise ValueError("Benchmark correlation IDs must be canonical UUIDs")
        try:
            if str(UUID(identifier)) != identifier:
                raise ValueError
        except ValueError:
            raise ValueError("Benchmark correlation IDs must be canonical UUIDs") from None
    case_id = None
    if raw_case is not None:
        if (
            not raw_case.isascii()
            or not raw_case.isdecimal()
            or len(raw_case) > 3
            or str(int(raw_case)) != raw_case
        ):
            raise ValueError("Benchmark case ID must be an integer from zero to 999")
        case_id = int(raw_case)
    if isolation == "case" and case_id is None:
        raise ValueError("Case isolation requires a benchmark case ID")
    session_id = (
        f"{run_id}:case:{case_id}"
        if isolation == "case"
        else f"{run_id}:shared"
        if isolation == "shared"
        else request_id
    )
    return InvocationContext(run_id, request_id, case_id, session_id)


def _finite_float(value: str) -> float:
    """Reject valid JSON exponent syntax that overflows to an infinite float."""
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON numbers must be finite")
    return number


def _constant(value: str) -> Any:
    """Reject NaN/Infinity literals without retaining the submitted literal."""
    raise ValueError("JSON numbers must be finite")


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate keys instead of silently discarding customer input."""
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("JSON object keys must be unique")
    return result


async def _inputs(request: Request) -> dict[str, Any]:
    """Read a bounded, nonempty finite UTF-8 JSON object, including chunked bodies.

    Args:
        request: Customer-process HTTP request; this function owns reading its body.

    Returns:
        The parsed input object without adding/removing keys or changing structure.

    Raises:
        OverflowError: Declared or observed body size exceeds MAX_REQUEST_BYTES.
        ValueError: Wrong media type, malformed/nonfinite JSON, duplicate fields,
            invalid Unicode, or an empty/non-object body. Values are not echoed.
        RuntimeError: The client disconnects or the request stream is unavailable.
    """
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise ValueError("Expected application/json")
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise ValueError("Encoded request bodies are not supported")
    declared = request.headers.get("content-length")
    if declared is not None:
        if len(declared) > 12 or not declared.isascii() or not declared.isdecimal():
            raise ValueError("Invalid request length")
        if int(declared) > MAX_REQUEST_BYTES:
            raise OverflowError("Request body exceeds the byte limit")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_REQUEST_BYTES:
            raise OverflowError("Request body exceeds the byte limit")
        body.extend(chunk)
    try:
        document = json.loads(
            body.decode("utf-8"),
            parse_float=_finite_float,
            parse_constant=_constant,
            object_pairs_hook=_object,
        )
        # The JSON parser accepts lone escaped surrogates; never pass them onward.
        json.dumps(document, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, RecursionError):
        raise ValueError("Invalid finite UTF-8 JSON object") from None
    if not isinstance(document, dict) or not document:
        raise ValueError("Inputs must be a nonempty JSON object")
    return document


def _answer_response(answer: AgentAnswer) -> JSONResponse:
    """Serialize bounded answer evidence consistently with the http-json adapter.

    Args:
        answer: Completed customer result; revalidated even if constructed unsafely.

    Returns:
        A non-streaming 200 JSON response with matching optional body/header trace ID.

    Raises:
        ValueError: Wrong result type, invalid evidence, or the entire encoded JSON
            response exceeds JSON_RESPONSE_LIMIT. Errors omit answer content.

    Token counts are supplied by the customer, not estimated. Serialization is
    inside HTTP response latency; no TTFT, trace export or model call is invented.
    """
    if not isinstance(answer, AgentAnswer):
        raise ValueError("The handler must return AgentAnswer")
    valid = AgentAnswer.model_validate(answer.model_dump(mode="python", warnings=False))
    headers = {"Cache-Control": "no-store"}
    if valid.trace_id is not None:
        # Trace IDs are echoed into an HTTP header, so prohibit header delimiters.
        if any(ord(character) < 32 or ord(character) > 126 for character in valid.trace_id):
            raise ValueError("Trace ID must contain printable ASCII header characters")
        headers["X-MLflow-Trace-ID"] = valid.trace_id
    response = JSONResponse(valid.model_dump(exclude_none=True), headers=headers)
    if len(response.body) > JSON_RESPONSE_LIMIT:
        raise ValueError("Completed response exceeds the byte limit")
    return response


def create_app(handler: AgentHandler, *, isolation: Isolation, path: str = "/invoke") -> FastAPI:
    """Bind customer-owned async execution to the existing completed-answer contract.

    Args:
        handler: Async function in the customer process, receiving unchanged input
            and explicit correlation/state keys. It must return AgentAnswer.
        isolation: Required request/case/shared choice; selects keys only, not stores.
        path: Literal POST route, with no route parameters, query, or fragment.

    Returns:
        Customer-owned FastAPI app. It has no built-in authentication; add your own
        auth middleware or authenticated gateway before exposing it beyond loopback.

    Raises:
        ValueError: Invalid handler, isolation option, or endpoint path.

    Handler failures become fixed safe 502 responses. Request failures precede
    handler execution. There are no retries, imports of customer source, automatic
    instrumentation, provider clients, memory stores, or extra invocation calls.
    Customer code owns model/tool costs, cancellation cleanup, deadlines and state.
    """
    if not callable(handler) or isolation not in {"request", "case", "shared"}:
        raise ValueError("Supply an async handler and explicit request/case/shared isolation")
    if not isinstance(path, str) or not path.startswith("/") or any(c in path for c in "{}?#"):
        raise ValueError("Supply a literal absolute endpoint path")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.post(path)
    async def invoke(request: Request) -> JSONResponse:
        """Validate one input/context, then await exactly one customer invocation."""
        try:
            context = _context(request.headers, isolation)
        except ValueError:
            return _failure(400, "invalid_correlation", "Check the benchmark correlation headers.")
        try:
            inputs = await _inputs(request)
        except OverflowError:
            return _failure(413, "input_too_large", "Input exceeds the eight-megabyte limit.")
        except (ValueError, RuntimeError, ClientDisconnect):
            return _failure(422, "invalid_input", "Provide a nonempty finite UTF-8 JSON object.")
        capture = _ResponseTrace()
        token = _response_trace.set(capture)
        try:
            try:
                answer = await handler(inputs, context)
            except Exception:  # noqa: BLE001 - do not expose customer exception/credential content
                return _failure(
                    502,
                    "agent_execution_failed",
                    "The agent handler did not complete successfully.",
                    trace_id=capture.trace_id,
                )
            try:
                return _answer_response(answer)
            except (ValueError, TypeError, RecursionError, UnicodeError):
                return _failure(
                    502,
                    "invalid_agent_answer",
                    "The agent must return a valid completed AgentAnswer.",
                    trace_id=capture.trace_id,
                )
        finally:
            _response_trace.reset(token)

    return app
