"""Shared production-path socket fixture."""

import asyncio
import json
import socket
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from benchmark_agents import api
from benchmark_agents.models import PreflightResult


@pytest.fixture
def successful_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep phase-unit tests at their existing controlled load boundary."""

    async def passed(*args: Any, **kwargs: Any) -> PreflightResult:
        return PreflightResult(status="passed")

    monkeypatch.setattr(api, "run_preflight", passed)


@pytest.fixture
async def endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Serve deterministic local SSE and safe failure modes with dispatch counters."""
    monkeypatch.setenv("BENCHMARK_ARTIFACT_DIR", str(tmp_path))
    app = FastAPI()
    measurements = {"active": 0, "peak": 0, "received": 0, "bodies": [], "request_ids": []}

    @app.post("/{mode}", response_model=None)
    async def chat(mode: str, request: Request) -> JSONResponse | StreamingResponse:
        measurements["received"] += 1
        measurements["bodies"].append(await request.json())
        measurements["request_ids"].append(request.headers.get("X-Benchmark-Request-ID"))
        if mode in {"denied", "redirect"}:
            return JSONResponse(
                {"error": "private provider failure"},
                status_code=401 if mode == "denied" else 307,
                headers={"Location": "/normal"},
            )
        if mode == "wrong_content_type":
            return JSONResponse({"answer": "private answer"})

        async def stream() -> AsyncIterator[str]:
            measurements["active"] += 1
            measurements["peak"] = max(measurements["peak"], measurements["active"])
            try:
                if mode == "provider_error":
                    yield 'data: {"error":{"message":"private provider failure"}}\n\n'
                    return
                if mode == "malformed":
                    yield "data: private-invalid-json\n\n"
                    return
                if mode == "filtered":
                    yield 'data: {"choices":[{"delta":{},"finish_reason":"content_filter"}]}\n\n'
                    return
                if mode == "empty":
                    yield "data: [DONE]\n\n"
                    return
                yield 'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
                await asyncio.sleep(0.15 if mode != "slow" else 1)
                if mode == "responses":
                    yield 'data: {"type":"response.output_text.delta","delta":"Answer—yes"}\n\n'
                    yield 'data: {"type":"response.completed","response":{"usage":{"output_tokens":3}}}\n\n'
                    return
                yield (
                    "data: "
                    + json.dumps(
                        {"choices": [{"delta": {"content": "Answer—yes"}}]}, ensure_ascii=False
                    )
                    + "\n\n"
                )
                if mode != "truncated":
                    yield 'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
                    yield 'data: {"usage":{"completion_tokens":3}}\n\n'
            finally:
                measurements["active"] -= 1

        return StreamingResponse(stream(), media_type="text/event-stream")

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
        yield f"http://127.0.0.1:{port}", measurements
    finally:
        server.should_exit = True
        await serving
        connection.close()
