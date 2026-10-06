"""JSON contracts and actual localhost traffic through the sole Locust engine."""

import asyncio
import gzip
import json
import time
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from requests import Response
from urllib3.response import HTTPResponse

from benchmark_agents.adapters import InvalidResponse, get_adapter
from benchmark_agents.locust_runner import run_load
from benchmark_agents.models import RunRequest, Sample, Target
from benchmark_agents.runner import payload
from tests.test_template import configuration


def measurement() -> dict[str, Any]:
    """Create empty timing/evidence fields for a single parser invocation."""
    return {
        "outputs": "",
        "ttft_ms": None,
        "first_event_ms": None,
        "output_tokens": None,
        "trace_id": None,
    }


def response(
    body: bytes,
    content_type: str = "application/json",
    headers: dict[str, str] | None = None,
) -> Response:
    """Create a real Requests/urllib3 streaming response without HTTP traffic.

    Args:
        body: Transport bytes, optionally gzip encoded by the caller.
        content_type: Declared media type.
        headers: Additional response headers, including content encoding.

    Returns:
        Caller-owned response whose iter_content performs native decompression.
    """
    result = Response()
    result.status_code = 200
    result.headers.update({"Content-Type": content_type, **(headers or {})})
    result.raw = HTTPResponse(body=BytesIO(body), headers=result.headers, preload_content=False)
    return result


def decode(body: Any, headers: dict[str, str] | None = None) -> dict[str, Any]:
    """Decode a serialized JSON body using the shipped adapter and real response."""
    row = measurement()
    with response(json.dumps(body, ensure_ascii=False).encode(), headers=headers) as received:
        get_adapter("http-json").decode(received, row, time.perf_counter())
    return row


def json_request(url: str, **load: Any) -> RunRequest:
    """Build a bounded JSON workload with inputs independent of query/messages."""
    request = configuration(**{"concurrency": 1, "duration_seconds": 5, "max_requests": 1, **load})
    request.target.url = url
    request.target.adapter = "http-json"
    request.evaluation.samples = [
        Sample(
            inputs={"task": {"question": "Can I refund?"}, "session_id": "local"},
            expectations={"expected_response": "Answer—yes"},
        )
    ]
    return request


def test_json_payload_preserves_raw_provider_independent_inputs() -> None:
    request = json_request("http://127.0.0.1:9001/json")
    sample = request.evaluation.samples[0]
    submitted = payload(request, sample)
    assert submitted == sample.inputs
    assert submitted is not sample.inputs
    assert set(submitted) == {"task", "session_id"}
    request.target.request_usage = False
    assert payload(request, sample) == submitted


def test_json_payload_rejects_empty_inputs() -> None:
    request = json_request("http://127.0.0.1:9001/json")
    with pytest.raises(ValueError, match="nonempty"):
        payload(request, Sample(inputs={}))


@pytest.mark.parametrize("name", ["openai-chat", "mlflow-agent-server"])
def test_existing_sse_envelopes_are_preserved(name: str) -> None:
    request = configuration()
    request.target = Target(url=request.target.url, adapter=name)
    encoded = payload(request, request.evaluation.samples[0])
    assert encoded["stream"] is True
    if name == "openai-chat":
        assert encoded == {
            "model": "agent",
            "messages": [{"role": "user", "content": "Can I refund?"}],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
    else:
        assert encoded == {
            "input": [{"role": "user", "content": "Can I refund?"}],
            "stream": True,
        }


@pytest.mark.parametrize("tokens", [0, 3, None])
def test_json_decode_preserves_unicode_and_honest_usage(tokens: int | None) -> None:
    body: dict[str, Any] = {"outputs": "Answer—yes"}
    if tokens is not None:
        body["usage"] = {"output_tokens": tokens}
    row = decode(body)
    assert row["outputs"] == "Answer—yes"
    assert row["output_tokens"] == tokens
    assert row["ttft_ms"] is row["first_event_ms"] is None
    assert row["trace_id"] is None


@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        "private answer",
        True,
        1,
        {},
        {"outputs": ""},
        {"outputs": " \n\t"},
        {"outputs": None},
        {"outputs": ["private answer"]},
        {"outputs": 1},
        {"outputs": True},
        {"outputs": "answer", "error": "private provider error"},
    ],
)
def test_json_decode_rejects_missing_empty_or_wrong_type_answers(body: Any) -> None:
    with pytest.raises(InvalidResponse) as failure:
        decode(body)
    assert "private" not in str(failure.value)


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {},
        [],
        3,
        {"output_tokens": None},
        {"output_tokens": -1},
        {"output_tokens": True},
        {"output_tokens": False},
        {"output_tokens": 3.0},
        {"output_tokens": "3"},
    ],
)
def test_json_decode_rejects_invalid_usage(usage: Any) -> None:
    with pytest.raises(InvalidResponse):
        decode({"outputs": "answer", "usage": usage})


@pytest.mark.parametrize("trace_id", [None, "", " \t", "x" * 129, 1, True, []])
def test_json_decode_rejects_invalid_trace_ids(trace_id: Any) -> None:
    with pytest.raises(InvalidResponse):
        decode({"outputs": "answer", "trace_id": trace_id})


@pytest.mark.parametrize("trace_id", ["tr-local-json", "x" * 128])
def test_json_trace_id_may_come_from_body_or_header(trace_id: str) -> None:
    assert decode({"outputs": "answer", "trace_id": trace_id})["trace_id"] == trace_id
    headers = {"X-MLflow-Trace-ID": trace_id}
    assert decode({"outputs": "answer"}, headers)["trace_id"] == trace_id
    assert decode({"outputs": "answer", "trace_id": trace_id}, headers)["trace_id"] == trace_id


def test_json_rejects_conflicting_trace_ids_without_partial_evidence() -> None:
    row = measurement()
    with (
        response(
            b'{"outputs":"private answer","usage":{"output_tokens":3},"trace_id":"tr-body"}',
            headers={"X-MLflow-Trace-ID": "tr-header"},
        ) as received,
        pytest.raises(InvalidResponse, match="trace"),
    ):
        get_adapter("http-json").decode(received, row, time.perf_counter())
    assert row == measurement()


@pytest.mark.parametrize("trace_id", ["", " \t", "x" * 129])
def test_json_rejects_invalid_header_trace_ids(trace_id: str) -> None:
    with pytest.raises(InvalidResponse):
        decode({"outputs": "answer"}, {"X-MLflow-Trace-ID": trace_id})


@pytest.mark.parametrize(
    "content_type",
    ["text/plain", "text/event-stream", "application/problem+json", "application/jsonp", ""],
)
def test_json_requires_exact_reviewed_media_type(content_type: str) -> None:
    with (
        response(b'{"outputs":"answer"}', content_type) as received,
        pytest.raises(InvalidResponse),
    ):
        get_adapter("http-json").decode(received, measurement(), time.perf_counter())


def test_json_accepts_media_type_parameters_case_insensitively() -> None:
    with response(b'{"outputs":"answer"}', "Application/JSON; charset=utf-8") as received:
        row = measurement()
        get_adapter("http-json").decode(received, row, time.perf_counter())
    assert row["outputs"] == "answer"


@pytest.mark.parametrize(
    "body",
    [
        b"private-invalid-json",
        b'{"outputs":"private answer"',
        b'{"outputs":"\xff"}',
        b'{"outputs":"\\ud800"}',
        b'{"outputs":"answer","trace_id":"\\ud800"}',
        b'{"outputs":"answer","score":NaN}',
        b'{"outputs":"answer","score":Infinity}',
        b'{"outputs":"answer","score":-Infinity}',
        b'{"outputs":"first","outputs":"second"}',
        b'{"outputs":"answer","usage":{"output_tokens":3,"output_tokens":4}}',
        b"[" * 2000 + b"]" * 2000,
    ],
)
def test_json_malformed_errors_do_not_leak_body_content(body: bytes) -> None:
    with response(body) as received, pytest.raises(InvalidResponse) as failure:
        get_adapter("http-json").decode(received, measurement(), time.perf_counter())
    assert "private" not in str(failure.value)


@pytest.mark.parametrize("compressed", [False, True])
def test_json_response_limit_applies_to_decoded_bytes(compressed: bool) -> None:
    body = json.dumps({"outputs": "é" * 1_000_000}, ensure_ascii=False).encode()
    headers = {"Content-Encoding": "gzip"} if compressed else {}
    transport = gzip.compress(body) if compressed else body
    with (
        response(transport, headers=headers) as received,
        pytest.raises(InvalidResponse, match="limit"),
    ):
        get_adapter("http-json").decode(received, measurement(), time.perf_counter())


def test_json_response_limit_is_inclusive() -> None:
    envelope = b'{"outputs":""}'
    body = b'{"outputs":"' + b"x" * (2_000_000 - len(envelope)) + b'"}'
    with response(body) as received:
        row = measurement()
        get_adapter("http-json").decode(received, row, time.perf_counter())
    assert len(row["outputs"]) == 2_000_000 - len(envelope)


@pytest.mark.parametrize("mode,tokens", [("json", 3), ("json-no-usage", None)])
async def test_locust_json_success_and_absent_usage(
    endpoint: tuple[str, dict[str, Any]], mode: str, tokens: int | None
) -> None:
    base_url, server = endpoint
    request = json_request(base_url + "/" + mode, max_requests=2, concurrency=2)
    rows, metrics = await run_load(request, str(uuid4()), asyncio.Event())
    assert len(rows) == server["received"] == 2
    assert all(body == request.evaluation.samples[0].inputs for body in server["bodies"])
    assert metrics["engine"] == "locust"
    assert metrics["error_rate"] == 0
    assert metrics["incomplete_measurements"] == 0
    assert all(row["outputs"] == "Answer—yes" for row in rows)
    assert all(row["output_tokens"] == tokens for row in rows)
    assert all(row["trace_id"] == "tr-local-json" for row in rows)
    assert all(row["latency_ms"] > 0 for row in rows)
    assert all(row["ttft_ms"] is row["first_event_ms"] is None for row in rows)
    assert metrics["timing_successful_only"]["latency_ms"]["count"] == 2
    assert metrics["token_usage_coverage"] == (1 if tokens is not None else 0)
    if tokens is None:
        assert metrics["reported_output_tokens_per_second"] is None
    for field in ("ttft_ms", "first_event_ms"):
        assert metrics["timing_successful_only"][field] == {
            "count": 0,
            "p50": None,
            "p95": None,
            "p99": None,
        }


@pytest.mark.parametrize(
    "mode",
    [
        "json-empty",
        "json-type",
        "json-malformed",
        "json-list",
        "json-bad-usage",
        "json-large",
        "normal",
    ],
)
async def test_locust_json_invalid_responses_are_durable_safe_failures(
    endpoint: tuple[str, dict[str, Any]], mode: str, tmp_path: Path
) -> None:
    base_url, server = endpoint
    run_id = str(uuid4())
    request = json_request(base_url + "/" + mode)
    rows, metrics = await run_load(request, run_id, asyncio.Event())
    assert len(rows) == server["received"] == 1
    assert metrics["error_rate"] == 1
    assert metrics["incomplete_measurements"] == 0
    assert metrics["measurement_complete"] is True
    row = rows[0]
    assert not row["success"]
    assert row["error"] == "InvalidResponse"
    assert row["error_phase"] == "response"
    assert row["ttft_ms"] is row["first_event_ms"] is None
    assert "private" not in row.get("error_detail", "")
    assert metrics["errors"] == {"InvalidResponse": 1}
    assert (tmp_path / run_id / "requests.jsonl").is_file()


@pytest.mark.parametrize("mode,status", [("denied", 401), ("redirect", 307)])
async def test_locust_json_http_errors_do_not_retry_or_redirect(
    endpoint: tuple[str, dict[str, Any]], mode: str, status: int
) -> None:
    base_url, server = endpoint
    request = json_request(base_url + "/" + mode)
    rows, metrics = await run_load(request, str(uuid4()), asyncio.Event())
    assert len(rows) == server["received"] == 1
    assert metrics["error_rate"] == 1
    assert metrics["incomplete_measurements"] == 0
    assert rows[0]["http_status"] == status
    assert not rows[0]["success"]
    assert rows[0]["ttft_ms"] is rows[0]["first_event_ms"] is None


async def test_locust_json_timeout_records_one_failed_attempt(
    endpoint: tuple[str, dict[str, Any]],
) -> None:
    base_url, server = endpoint
    request = json_request(base_url + "/json-slow", timeout_seconds=0.15)
    rows, metrics = await run_load(request, str(uuid4()), asyncio.Event())
    assert len(rows) == server["received"] == 1
    assert metrics["error_rate"] == 1
    assert metrics["incomplete_measurements"] == 0
    assert not rows[0]["success"]
    assert rows[0]["deadline_exceeded"]
    assert rows[0]["ttft_ms"] is rows[0]["first_event_ms"] is None
