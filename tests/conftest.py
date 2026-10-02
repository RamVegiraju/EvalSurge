"""Shared production-path socket fixture."""

import asyncio
import json
import socket

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse


@pytest.fixture
async def endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCHMARK_ARTIFACT_DIR", str(tmp_path))
    app = FastAPI()
    measurements = {"active": 0, "peak": 0, "received": 0}

    @app.post("/{mode}")
    async def chat(mode: str):
        async def stream():
            measurements["active"] += 1
            measurements["received"] += 1
            measurements["peak"] = max(measurements["peak"], measurements["active"])
            try:
                yield 'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
                await asyncio.sleep(0.15 if mode != "slow" else 1)
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
