"""Native HTTP/JSON/Locust checks for the documented synchronous invocation API."""

import asyncio
import json
import socket
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import uvicorn
from fastapi import FastAPI, Request

from benchmark_agents.adapters import InvalidResponse, get_adapter
from benchmark_agents.locust_runner import run_load
from benchmark_agents.models import Sample, Target
from benchmark_agents.runner import payload
from tests.test_json_adapter import measurement, response
from tests.test_template import configuration


def runtime_decode(output: Any, *, status: str = "completed") -> dict[str, Any]:
    """Pass a documented envelope through a real Requests/urllib3 response stream."""
    identifier = str(uuid4())
    row = {**measurement(), "request_id": identifier}
    document = {"id": identifier, "status": status, "output": output}
    with response(json.dumps(document).encode()) as received:
        get_adapter("databricks-agent-runtime").decode(received, row, time.perf_counter())
    return row


def test_runtime_payload_uses_wire_id_and_isolated_sessions():
    request = configuration()
    request.target = Target(
        url="http://127.0.0.1:9001/api/invocations",
        adapter="databricks-agent-runtime",
        session_per_request=True,
    )
    request_id = str(uuid4())
    first = payload(request, Sample(inputs={"query": "Hello"}), request_id)
    second = payload(request, Sample(inputs={"query": "Hello"}))
    assert first["id"] == request_id
    assert UUID(second["id"])
    assert UUID(first["session_id"])
    assert first["session_id"] != second["session_id"]
    assert first["input"] == [{"role": "user", "content": "Hello"}]
    assert first["stream"] is first["background"] is False
    assert set(first) == {"id", "input", "session_id", "stream", "background"}
    request.target.session_id = "fixed-conversation"
    assert payload(request, Sample(inputs={"query": "Hello"}))["session_id"] == "fixed-conversation"


@pytest.mark.parametrize(
    "output",
    [
        "Answer—yes",
        {"answer": "Answer—yes"},
        {"status": "completed", "output": [{"role": "assistant", "content": "Answer—yes"}]},
        {
            "status": "completed",
            "output": [
                {"role": "user", "content": "ignored"},
                {"type": "function_call", "role": "assistant", "content": "ignored"},
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "Answer—yes"}],
                },
            ],
        },
    ],
)
def test_synchronous_output_is_text_without_fabricated_ttft(output):
    row = runtime_decode(output)
    assert row["outputs"] == "Answer—yes"
    assert row["ttft_ms"] is row["first_event_ms"] is row["output_tokens"] is None


@pytest.mark.parametrize("status", ["running", "queued", "failed", "interrupted", "cancelled"])
def test_incomplete_invocations_are_not_successful_answers(status):
    with pytest.raises(InvalidResponse, match="synchronously"):
        runtime_decode("private text", status=status)


@pytest.mark.parametrize(
    "output",
    [
        None,
        [],
        "",
        {"output": [{"role": "tool", "content": "private tool result"}]},
        {"status": "interrupted", "output": [{"role": "assistant", "content": "partial"}]},
        {"status": "interrupted", "answer": "private partial output"},
        {"output": [{"role": "assistant", "content": [{"type": "output_text", "text": 1}]}]},
    ],
)
def test_unsupported_or_interrupted_handler_outputs_are_safe(output):
    with pytest.raises(InvalidResponse) as failure:
        runtime_decode(output)
    assert "private" not in str(failure.value)


@pytest.mark.parametrize("status", ["in_progress", "incomplete", "failed", None])
def test_explicit_unfinished_assistant_messages_do_not_publish_partial_answers(status):
    """A completed invocation cannot turn explicitly unfinished text into success."""
    identifier = str(uuid4())
    row = {**measurement(), "request_id": identifier}
    document = {
        "id": identifier,
        "status": "completed",
        "output": {
            "status": "completed",
            "output": [
                {"role": "assistant", "content": "private completed prefix"},
                {"role": "assistant", "status": status, "content": "private partial text"},
            ],
        },
    }
    with (
        response(json.dumps(document).encode()) as received,
        pytest.raises(InvalidResponse) as failure,
    ):
        get_adapter("databricks-agent-runtime").decode(received, row, time.perf_counter())
    assert "private" not in str(failure.value)
    assert row["outputs"] == ""
    assert row["ttft_ms"] is row["first_event_ms"] is None


def test_background_and_mismatched_ids_are_rejected_without_publishing_text():
    identifier = str(uuid4())
    document = {"id": identifier, "status": "completed", "output": "private text"}
    for status, changes in [
        (202, {}),
        (200, {"status_url": "https://private.test"}),
        (200, {"id": str(uuid4())}),
    ]:
        row = {**measurement(), "request_id": identifier}
        with response(json.dumps({**document, **changes}).encode()) as received:
            received.status_code = status
            with pytest.raises(InvalidResponse):
                get_adapter("databricks-agent-runtime").decode(received, row, time.perf_counter())
        assert row["outputs"] == ""


def test_legacy_mlflow_trace_event_after_completion_is_retained():
    events = (
        'data: {"type":"response.output_text.delta","delta":"Answer—yes"}\n\n'
        'data: {"type":"response.completed"}\n\n'
        'data: {"trace_id":"tr-native-mlflow"}\n\n'
        "data: [DONE]\n\n"
    )
    row = measurement()
    with response(events.encode(), "text/event-stream") as received:
        get_adapter("mlflow-agent-server").decode(received, row, time.perf_counter())
    assert row["outputs"] == "Answer—yes"
    assert row["trace_id"] == "tr-native-mlflow"


def test_legacy_mlflow_trace_conflicts_are_safe_failures():
    events = 'data: {"trace_id":"tr-other"}\n\ndata: [DONE]\n\n'
    with (
        response(
            events.encode(), "text/event-stream", {"X-MLflow-Trace-ID": "tr-header"}
        ) as received,
        pytest.raises(ValueError, match="identifiers disagree"),
    ):
        get_adapter("mlflow-agent-server").decode(received, measurement(), time.perf_counter())


@pytest.fixture
async def runtime_endpoint() -> AsyncIterator[tuple[str, list[dict[str, Any]]]]:
    """Serve a controlled native HTTP boundary matching the official invocation API."""
    app = FastAPI()
    received = []

    @app.post("/api/invocations")
    async def invoke(request: Request):
        body = await request.json()
        received.append({"body": body, "headers": dict(request.headers)})
        assert body["stream"] is body["background"] is False
        assert UUID(body["id"])
        assert UUID(body["session_id"])
        return {"id": body["id"], "status": "completed", "output": {"answer": "Answer—yes"}}

    connection = socket.socket()
    connection.bind(("127.0.0.1", 0))
    port = connection.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="off"))
    serving = asyncio.create_task(server.serve(sockets=[connection]))
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}/api/invocations", received
    finally:
        server.should_exit = True
        await serving
        connection.close()


async def test_runtime_dispatch_uses_the_sole_locust_engine(runtime_endpoint, tmp_path):
    url, received = runtime_endpoint
    request = configuration(concurrency=2, max_requests=4, duration_seconds=5)
    request.target = Target(url=url, adapter="databricks-agent-runtime", session_per_request=True)
    rows, summary = await run_load(request, str(uuid4()), asyncio.Event(), artifact_dir=tmp_path)
    assert summary["engine"] == "locust"
    assert summary["successful_requests"] == len(received) == len(rows) == 4
    assert len({item["body"]["session_id"] for item in received}) == 4
    assert {row["request_id"] for row in rows} == {item["body"]["id"] for item in received}
    assert all(item["headers"]["x-benchmark-request-id"] == item["body"]["id"] for item in received)
    assert all(item["headers"]["x-routing-key"] == item["body"]["session_id"] for item in received)
    assert all(item["headers"]["x-mlflow-return-trace-id"] == "true" for item in received)
    assert all(row["outputs"] == "Answer—yes" for row in rows)
    assert summary["timing_successful_only"]["ttft_ms"]["count"] == 0
