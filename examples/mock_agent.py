"""Deterministic local streaming agent for HTTP smoke tests; no LLM credentials."""

import asyncio
import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()


@app.post("/chat")
async def chat():
    async def events():
        yield 'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
        for text in ["Opened items ", "are not refundable."]:
            await asyncio.sleep(0.025)
            yield "data: " + json.dumps({"choices": [{"delta": {"content": text}}]}) + "\n\n"
        yield 'data: {"usage":{"completion_tokens":7}}\n\n'
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
