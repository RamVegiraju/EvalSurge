"""Standalone real CrewAI HTTP endpoint for an independently reviewed environment.

Run this source with real CrewAI, OpenAI, SDK, HTTPX, FastAPI and Uvicorn installed
in an isolated customer environment; do not install EvalSurge into that agent
environment when dependency ranges conflict. EvalSurge runs in its own load
generator environment. This is local agent hosting, not native App deployment.
Default CLI mode is no-network planning. Real startup/inference requires explicit
profile/model/route/origin and paid-traffic consent, plus separate traffic bounds.
"""

import argparse
import json
import math
import os
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

if __package__:
    from .real_framework_handler import (
        ModelSelection,
        build_handler,
        owned_thread,
        response_completion_guard,
        validate_inputs,
        validate_model_request,
    )
else:
    # Explicit same-directory script entrypoint, not arbitrary path/plugin loading.
    from real_framework_handler import (
        ModelSelection,
        build_handler,
        owned_thread,
        response_completion_guard,
        validate_inputs,
        validate_model_request,
    )

REQUEST_BYTES = 16_384


@dataclass(frozen=True)
class RequestContext:
    """Untrusted correlation labels; no authentication, trace or session memory."""

    run_id: str | None
    request_id: str
    case_id: int | None
    session_id: str


def correlation_context(headers: Any) -> RequestContext:
    """Validate optional benchmark labels before inference, preserving request isolation.

    Args:
        headers: Native request headers, supporting getlist for duplicates.

    Returns:
        Context with a fresh UUID for standalone calls and no persistent store.

    Raises:
        ValueError: Duplicate/incomplete/noncanonical labels, without values.
    """
    names = ("X-Benchmark-Run-ID", "X-Benchmark-Request-ID", "X-Benchmark-Case-ID")
    values = [headers.getlist(name) for name in names]
    if any(len(value) > 1 for value in values):
        raise ValueError("Invalid correlation labels")
    run_id, request_id, raw_case = [value[0] if value else None for value in values]
    if not any(values):
        request_id = str(uuid4())
        return RequestContext(None, request_id, None, request_id)
    if run_id is None or request_id is None:
        raise ValueError("Invalid correlation labels")
    for identifier in (run_id, request_id):
        if len(identifier) != 36 or str(UUID(identifier)) != identifier:
            raise ValueError("Invalid correlation labels")
    case_id = None
    if raw_case is not None:
        if (
            not raw_case.isascii()
            or not raw_case.isdecimal()
            or len(raw_case) > 3
            or str(int(raw_case)) != raw_case
        ):
            raise ValueError("Invalid correlation labels")
        case_id = int(raw_case)
    return RequestContext(run_id, request_id, case_id, request_id)


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Invalid JSON")
    return number


def _constant(value: str) -> Any:
    raise ValueError("Invalid JSON")


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("Invalid JSON")
        document[key] = value
    return document


def decode_inputs(body: bytes) -> dict[str, Any]:
    """Decode bounded strict JSON and validate the exact sample query before inference.

    Args:
        body: At most 16,384 raw bytes, independently bounded during request reading.

    Returns:
        Original object containing only one nonblank UTF-8 query of <=512 characters.

    Raises:
        ValueError: Invalid UTF-8/JSON, duplicate fields, nonfinite or unsupported input.
    """
    if len(body) > REQUEST_BYTES:
        raise ValueError("Sample request exceeds the byte limit")
    try:
        document = json.loads(
            body.decode("utf-8"),
            parse_float=_finite_float,
            parse_constant=_constant,
            object_pairs_hook=_object,
        )
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise ValueError("Invalid sample JSON") from None
    if not isinstance(document, dict):
        raise ValueError("The sample input must be an object")
    validate_inputs(document)
    return document


def create_app(selection: ModelSelection) -> Any:
    """Create loopback-only hosting for the canonical actual CrewAI handler.

    Args:
        selection: Exact operator-owned model, route, profile, origin and bounds.

    Returns:
        FastAPI app exposing generic http-json POST /invoke, without startup inference.

    Raises:
        ImportError: Required native packages are absent; no fallback/installation.
        RuntimeError: Explicit profile resolves to a different workspace.

    Side Effects:
        Lifespan resolves SDK authentication on an owned thread, then owns two
        native async clients. Each request refreshes SDK headers on an owned thread
        and performs <=2 real model calls, <=512 tokens/call, 30 seconds/call and
        a 35-second handler deadline. Endpoint latency includes target hosting work;
        it is not subtracted from measurements. No memory, tools or traces are added.
        This endpoint supplies no inbound auth: the CLI binds only loopback.
    """
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient
    from starlette.requests import ClientDisconnect

    resources: dict[str, Any] = {}
    evidence = {"outbound_attempts": 0, "completed_responses": 0}

    async def authenticate_request(request: Any) -> None:
        """Apply refreshable SDK auth only to the exact selected destination."""
        validate_model_request(request, selection)
        headers = await owned_thread(resources["workspace"].config.authenticate)
        authorization = next(
            (value for key, value in headers.items() if key.lower() == "authorization"), None
        )
        if not authorization:
            raise RuntimeError("SDK authentication did not produce authorization headers")
        request.headers["Authorization"] = authorization

    def workspace_client() -> Any:
        workspace = WorkspaceClient(
            config=Config(
                profile=selection.profile, http_timeout_seconds=20, retry_timeout_seconds=1
            )
        )
        if workspace.config.host.rstrip("/") != selection.expected_host:
            raise RuntimeError("The selected profile does not resolve to the approved workspace")
        return workspace

    async def dispatch(request: Any) -> None:
        evidence["outbound_attempts"] += 1

    async def completion(response: Any) -> None:
        if 200 <= response.status_code < 300:
            evidence["completed_responses"] += 1

    @asynccontextmanager
    async def lifespan(app: Any) -> AsyncIterator[None]:
        if os.getenv("CREWAI_DISABLE_TELEMETRY") != "true":
            raise ValueError("Set CREWAI_DISABLE_TELEMETRY=true before real CrewAI startup")
        resources["workspace"] = await owned_thread(workspace_client)
        try:
            async with (
                DefaultAsyncHttpxClient(
                    trust_env=False,
                    follow_redirects=False,
                    timeout=selection.timeout_seconds,
                    event_hooks={
                        "request": [authenticate_request, dispatch],
                        "response": [response_completion_guard, completion],
                    },
                ) as http,
                AsyncOpenAI(
                    base_url=selection.base_url,
                    api_key="sdk-auth",
                    http_client=http,
                    max_retries=0,
                    timeout=selection.timeout_seconds,
                ) as client,
            ):
                resources["handler"] = build_handler("crewai", client, selection, http_client=http)
                yield
        finally:
            resources.clear()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.inference_evidence = evidence

    def failure(status: int, code: str, message: str) -> Any:
        return JSONResponse(
            {"error": {"code": code, "message": message}},
            status_code=status,
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/invoke")
    async def invoke(request: Request) -> Any:
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return failure(415, "invalid_input", "Use application/json")
        body = bytearray()
        try:
            async for chunk in request.stream():
                if len(body) + len(chunk) > REQUEST_BYTES:
                    return failure(413, "invalid_input", "Sample request exceeds the byte limit")
                body.extend(chunk)
            inputs = decode_inputs(bytes(body))
            context = correlation_context(request.headers)
        except ClientDisconnect:
            return failure(400, "invalid_input", "Incomplete request")
        except (ValueError, UnicodeDecodeError, RecursionError):
            return failure(400, "invalid_input", "Use exactly one nonblank query field")
        try:
            answer = await resources["handler"](inputs, context)
        except TimeoutError:
            return failure(504, "inference_timeout", "Real inference exceeded its deadline")
        except Exception:  # noqa: BLE001 - fixed content-free boundary, not a fallback answer
            return failure(502, "inference_failed", "Real inference did not complete")
        document: dict[str, Any] = {"outputs": answer.outputs}
        if answer.output_tokens is not None:
            document["usage"] = {"output_tokens": answer.output_tokens}
        return JSONResponse(document, headers={"Cache-Control": "no-store"})

    return app


def main(arguments: Sequence[str] | None = None) -> None:
    """Plan without imports/network; require explicit real-traffic consent for startup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--workspace-host", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api", required=True, choices=("mlflow-responses", "openai-responses"))
    parser.add_argument("--port", type=int, default=9003)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--accept-paid-traffic", action="store_true")
    options = parser.parse_args(arguments)
    selection = ModelSelection(options.profile, options.model, options.api, options.workspace_host)
    if not 1024 <= options.port <= 65535:
        parser.error("--port must be 1024..65535")
    if not options.live:
        print("Dry run: real CrewAI standalone /invoke; no framework import or inference")
        return
    if not options.accept_paid_traffic:
        parser.error(
            "--live requires --accept-paid-traffic and separately bounded benchmark traffic"
        )
    if os.getenv("CREWAI_DISABLE_TELEMETRY") != "true":
        parser.error("Set CREWAI_DISABLE_TELEMETRY=true before real CrewAI startup")
    import uvicorn

    uvicorn.run(create_app(selection), host="127.0.0.1", port=options.port)


if __name__ == "__main__":
    main()
