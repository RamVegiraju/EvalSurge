"""Pure bridge schema/correlation/routing checks, with no agent/model inference.

Routing handlers deliberately raise before any provider could be invoked. Answer
serialization checks inspect schema objects directly, never synthetic successful
agent execution. These checks do not establish a real-model integration result.
"""

import ast
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError
from starlette.datastructures import Headers
from starlette.requests import Request

from benchmark_agents.limits import MAX_REQUEST_BYTES
from benchmark_agents.locust_runner import preflight_result
from evalsurge.serving import (
    AgentAnswer,
    AnswerUsage,
    InvocationContext,
    _answer_response,
    _context,
    _inputs,
    create_app,
)


def benchmark_headers(case_id: str = "0") -> dict[str, str]:
    """Create opaque correlation labels without a target or provider client."""
    return {
        "X-Benchmark-Run-ID": str(uuid4()),
        "X-Benchmark-Request-ID": str(uuid4()),
        "X-Benchmark-Case-ID": case_id,
    }


def test_answer_schema_preserves_exact_completed_text_and_actual_optional_evidence() -> None:
    """Inspect schema serialization, not a completed synthetic agent invocation."""
    answer = AgentAnswer(
        outputs="  Schema-only text — not an inference result.  ",
        trace_id="tr-schema-only",
        usage={"output_tokens": 0},
    )
    response = _answer_response(answer)
    assert response.status_code == 200
    assert json.loads(response.body) == answer.model_dump()
    assert response.headers["X-MLflow-Trace-ID"] == answer.trace_id
    assert response.headers["Cache-Control"] == "no-store"
    assert json.loads(_answer_response(AgentAnswer(outputs="schema-only")).body) == {
        "outputs": "schema-only"
    }


@pytest.mark.parametrize(
    "fields",
    [
        {"outputs": ""},
        {"outputs": " \n\t"},
        {"outputs": 7},
        {"outputs": "\ud800"},
        {"outputs": "x", "trace_id": " "},
        {"outputs": "x", "trace_id": "x" * 129},
        {"outputs": "x", "usage": {"output_tokens": True}},
        {"outputs": "x", "usage": {"output_tokens": -1}},
        {"outputs": "x", "usage": {"output_tokens": 1.0}},
        {"outputs": "x", "usage": {"output_tokens": float("inf")}},
        {"outputs": "x", "usage": {"output_tokens": float("nan")}},
        {"outputs": "x", "error": "Never success-shaped errors"},
    ],
)
def test_answer_rejects_invalid_completion_or_evidence(fields: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        AgentAnswer.model_validate(fields)


def test_answer_serialization_revalidates_unsafe_models_and_bounds_entire_response() -> None:
    with pytest.raises(ValidationError):
        _answer_response(AgentAnswer.model_construct(outputs=""))
    with pytest.raises(ValidationError):
        _answer_response(
            AgentAnswer.model_construct(
                outputs="schema", usage=AnswerUsage.model_construct(output_tokens=True)
            )
        )
    with pytest.raises(ValueError):
        _answer_response(AgentAnswer(outputs="x" * 2_000_000))
    with pytest.raises(ValueError):
        AgentAnswer(outputs="😀" * 500_001)
    with pytest.raises(ValueError):
        _answer_response(AgentAnswer(outputs="schema", trace_id="trace\r\nprivate-header: x"))


def test_context_isolation_is_explicit_run_scoped_and_does_not_create_traces() -> None:
    raw = benchmark_headers("7")
    first = _context(Headers(raw), "request")
    another = {**raw, "X-Benchmark-Request-ID": str(uuid4())}
    assert _context(Headers(another), "request").session_id != first.session_id
    assert (
        _context(Headers(raw), "case").session_id == _context(Headers(another), "case").session_id
    )
    assert _context(Headers(raw), "case").session_id == f"{first.run_id}:case:7"
    assert _context(Headers(raw), "shared").session_id == f"{first.run_id}:shared"
    assert (
        _context(Headers(raw), "shared").session_id
        == _context(Headers(another), "shared").session_id
    )
    other_run = {**raw, "X-Benchmark-Run-ID": str(uuid4())}
    for isolation in ("case", "shared"):
        assert (
            _context(Headers(raw), isolation).session_id
            != _context(Headers(other_run), isolation).session_id
        )
    standalone = _context(Headers(), "request")
    assert standalone.run_id is None and standalone.case_id is None
    assert standalone.session_id == standalone.request_id
    assert standalone != _context(Headers(), "request")


@pytest.mark.parametrize(
    "header_change,isolation",
    [
        ({"X-Benchmark-Run-ID": None}, "request"),
        ({"X-Benchmark-Request-ID": None}, "request"),
        ({"X-Benchmark-Run-ID": "private-invalid-value"}, "request"),
        ({"X-Benchmark-Case-ID": None}, "case"),
        ({"X-Benchmark-Case-ID": "-1"}, "case"),
        ({"X-Benchmark-Case-ID": "1000"}, "case"),
        ({"X-Benchmark-Case-ID": "01"}, "case"),
        ({"X-Benchmark-Case-ID": "1.0"}, "request"),
    ],
)
def test_context_rejects_incomplete_or_malformed_headers(
    header_change: dict[str, str | None], isolation: Any
) -> None:
    raw = {**benchmark_headers(), **header_change}
    headers = Headers({key: value for key, value in raw.items() if value is not None})
    with pytest.raises(ValueError) as failure:
        _context(headers, isolation)
    assert "private" not in str(failure.value)


def test_context_rejects_duplicate_ids_and_missing_case_shared_context() -> None:
    raw = benchmark_headers()
    pairs = [(key.lower().encode(), value.encode()) for key, value in raw.items()]
    pairs.append((b"x-benchmark-run-id", b"private-duplicate"))
    with pytest.raises(ValueError):
        _context(Headers(raw=pairs), "request")
    for isolation in ("case", "shared"):
        with pytest.raises(ValueError):
            _context(Headers(), isolation)


async def pre_provider_failure(inputs: dict[str, Any], context: InvocationContext) -> AgentAnswer:
    """Intentionally fail before constructing a provider, never return a canned answer."""
    raise RuntimeError("private-provider-credential must not leave the process")


@pytest.mark.parametrize("isolation", ["request", "case", "shared"])
async def test_route_preserves_inputs_context_and_content_free_handler_failure(
    isolation: Any,
) -> None:
    seen: list[tuple[dict[str, Any], InvocationContext]] = []

    async def inspect_then_fail(inputs: dict[str, Any], context: InvocationContext) -> AgentAnswer:
        """Inspect routing, then deliberately fail before any provider construction."""
        seen.append((inputs, context))
        return await pre_provider_failure(inputs, context)

    original = {"task": {"query": "private-input"}, "custom_inputs": [1, None, False]}
    headers = benchmark_headers("6")
    app = create_app(inspect_then_fail, isolation=isolation, path="/agent")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/agent", json=original, headers=headers)
    assert seen[0][0] == original
    assert seen[0][1] == _context(Headers(headers), isolation)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "agent_execution_failed"
    assert "private" not in response.text
    assert "outputs" not in response.json()


@pytest.mark.parametrize(
    "body",
    [
        b"{}",
        b"[]",
        b"null",
        b'{"x": NaN}',
        b'{"x": Infinity}',
        b'{"x": 1e999}',
        b'{"x": 1, "x": 2}',
        b'{"x": "\\ud800"}',
        b'{"x": "\xff"}',
        b"invalid",
    ],
)
async def test_route_rejects_invalid_input_before_handler(body: bytes) -> None:
    called = False

    async def forbidden(inputs: dict[str, Any], context: InvocationContext) -> AgentAnswer:
        nonlocal called
        called = True
        pytest.fail("Invalid input must never reach customer execution")

    app = create_app(forbidden, isolation="request")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/invoke", content=body, headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    assert called is False


async def test_route_rejects_invalid_correlation_before_handler() -> None:
    app = create_app(pre_provider_failure, isolation="case")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/invoke", json={"query": "private"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_correlation"
    assert "private" not in response.text


async def test_route_rejects_missing_answer_without_manufacturing_success() -> None:
    async def no_completed_answer(
        inputs: dict[str, Any], context: InvocationContext
    ) -> AgentAnswer:
        """Intentional completion failure without constructing a model/provider."""
        return None

    app = create_app(no_completed_answer, isolation="request")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/invoke", json={"query": "private"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_agent_answer"
    assert "outputs" not in response.json()
    assert "private" not in response.text


async def test_body_limit_covers_chunked_reads_and_declared_lengths() -> None:
    async def chunks():
        yield b'{"x":"'
        yield b"x" * MAX_REQUEST_BYTES
        yield b'"}'

    app = create_app(pre_provider_failure, isolation="request")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        chunked = await client.post(
            "/invoke", content=chunks(), headers={"Content-Type": "application/json"}
        )
        declared = await client.post(
            "/invoke",
            content=b"{}",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(MAX_REQUEST_BYTES + 1),
            },
        )
        wrong_media = await client.post(
            "/invoke", content=b"{}", headers={"Content-Type": "text/plain"}
        )
        encoded = await client.post(
            "/invoke",
            content=b"{}",
            headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
        )
    assert chunked.status_code == declared.status_code == 413
    assert wrong_media.status_code == encoded.status_code == 422


async def test_input_reader_does_not_strip_or_inject_customer_fields() -> None:
    body = {"query": " x ", "nested": {"model": "operator-owned", "state": [1, 1.25, True, None]}}
    consumed = False

    async def receive():
        nonlocal consumed
        assert not consumed
        consumed = True
        return {"type": "http.request", "body": json.dumps(body).encode(), "more_body": False}

    request = Request(
        {"type": "http", "headers": [(b"content-type", b"application/json")]}, receive
    )
    assert await _inputs(request) == body


def test_helper_requires_explicit_supported_isolation_and_literal_path() -> None:
    with pytest.raises(TypeError):
        create_app(pre_provider_failure)
    for isolation in (None, "automatic"):
        with pytest.raises(ValueError):
            create_app(pre_provider_failure, isolation=isolation)
    for path in ("invoke", "/invoke/{path}", "/invoke?token=private", "/invoke#fragment"):
        with pytest.raises(ValueError):
            create_app(pre_provider_failure, isolation="request", path=path)


def test_runner_adds_only_case_correlation_header_to_existing_dispatch() -> None:
    """Read source structurally; do not import/start the Locust worker."""
    tree = ast.parse((Path(__file__).parents[1] / "benchmark_agents" / "locustfile.py").read_text())
    headers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        and any(
            isinstance(key, ast.Constant) and key.value == "X-Benchmark-Run-ID" for key in node.keys
        )
    ]
    assert len(headers) == 1
    keys = [key.value for key in headers[0].keys]
    assert keys == ["X-Benchmark-Run-ID", "X-Benchmark-Request-ID", "X-Benchmark-Case-ID"]
    assert ast.unparse(headers[0].values[2]) == "str(row['case_id'])"


@pytest.mark.parametrize("status", [401, 403])
def test_preflight_http_auth_rejection_is_actionable_without_target_content(status: int) -> None:
    result = preflight_result(
        [
            {
                "http_status": status,
                "error_phase": "request",
                "error": "HTTPError",
                "error_detail": "private",
            }
        ],
        {"load_status": "completed", "worker_exit_code": 0},
    )
    assert result.error.code == "authentication_failed"
    assert "permissions" in result.error.message
    assert "private" not in result.model_dump_json()


@pytest.mark.parametrize("status", [400, 422])
def test_preflight_http_input_rejection_keeps_existing_code_and_safe_guidance(status: int) -> None:
    result = preflight_result(
        [{"http_status": status, "error_phase": "request", "error": "HTTPError"}],
        {"load_status": "completed", "worker_exit_code": 0},
    )
    assert result.error.code == "target_http_error"
    assert "first case input" in result.error.message


def test_preflight_encoder_failure_explains_no_target_dispatch() -> None:
    result = preflight_result(
        [{"error_phase": "request", "error": "InvalidInput", "error_detail": "private"}],
        {"load_status": "completed", "worker_exit_code": 0},
    )
    assert result.error.code == "invalid_stream"
    assert "encode the first case input" in result.error.message
    assert "No target invocation was dispatched" in result.error.message
    assert "private" not in result.model_dump_json()
