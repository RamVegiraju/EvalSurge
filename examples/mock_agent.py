"""Deterministic local streaming agent for HTTP smoke tests; no LLM credentials."""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()


@app.post("/chat")
async def chat() -> StreamingResponse:
    """Return a deterministic SSE answer with metadata and provider-style usage."""

    async def events() -> AsyncIterator[str]:
        """Yield delayed answer deltas followed by usage and a terminal marker."""
        yield 'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
        for text in ["Opened items ", "are not refundable."]:
            await asyncio.sleep(0.025)
            yield "data: " + json.dumps({"choices": [{"delta": {"content": text}}]}) + "\n\n"
        yield 'data: {"usage":{"completion_tokens":7}}\n\n'
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
