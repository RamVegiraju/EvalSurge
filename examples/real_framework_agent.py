"""Real-model HTTP helper examples; the canonical handlers have no EvalSurge imports.

This optional bridge requires EvalSurge's serving dependencies. The standalone
CrewAI endpoint lives in crewai_agent.py so its independently reviewed framework
environment does not inherit EvalSurge's OpenAI/Pydantic requirements. No fixture
path exists; profile/model/API route and traffic bounds remain explicit choices.
"""

import argparse
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from evalsurge.serving import AgentAnswer, AnswerUsage, InvocationContext, create_app

if __package__:
    from .real_framework_handler import (  # noqa: F401 - compatibility exports
        INSTRUCTIONS,
        POLICY,
        CompletedAnswer,
        Framework,
        ModelAPI,
        ModelSelection,
        ProviderInvocationFailed,
        _GraphState,
        completed_response,
        owned_thread,
        response_completion_guard,
        validate_completion_metadata,
        validate_inputs,
        validate_model_request,
    )
    from .real_framework_handler import build_handler as build_framework_handler
else:
    # Explicit same-directory script entrypoint, not arbitrary path/plugin loading.
    from real_framework_handler import (  # noqa: F401 - compatibility exports
        INSTRUCTIONS,
        POLICY,
        CompletedAnswer,
        Framework,
        ModelAPI,
        ModelSelection,
        ProviderInvocationFailed,
        _GraphState,
        completed_response,
        owned_thread,
        response_completion_guard,
        validate_completion_metadata,
        validate_inputs,
        validate_model_request,
    )
    from real_framework_handler import build_handler as build_framework_handler


def build_handler(
    framework: Framework, client: Any, selection: ModelSelection, *, http_client: Any
) -> Any:
    """Preserve the original EvalSurge serving-handler contract over the pure handler.

    Args:
        framework: Explicit actual framework selection; missing packages fail.
        client: Operator-owned native AsyncOpenAI authenticated model client.
        selection: Frozen exact profile/model/route and per-call bounds.
        http_client: Same owned HTTPX transport with the raw completion guard.

    Returns:
        Async handler accepting inputs/context and returning validated AgentAnswer.

    Raises:
        ImportError: Selected actual framework is not installed.
        ValueError: Invalid selections, provenance, input or completed evidence.

    Side Effects:
        Construction imports the selected framework but makes no provider call.
        Invocation preserves the canonical handler's bounded actual model calls.
        Conversion does not add a retry, trace, memory store or alternate runner.
    """
    invoke = build_framework_handler(framework, client, selection, http_client=http_client)

    async def handler(inputs: dict[str, Any], context: InvocationContext) -> AgentAnswer:
        answer = await invoke(inputs, context)
        return AgentAnswer(
            outputs=answer.outputs,
            usage=(
                AnswerUsage(output_tokens=answer.output_tokens)
                if answer.output_tokens is not None
                else None
            ),
        )

    return handler


def create_real_app(framework: Framework, selection: ModelSelection) -> Any:
    """Own actual clients/frameworks in a loopback app lifespan, with no startup inference.

    Args:
        framework: Chosen real optional framework.
        selection: Exact caller-selected profile/workspace/model/route and bounds.

    Returns:
        FastAPI app serving the generic completed-answer contract at /invoke.

    Raises:
        RuntimeError: Resolved SDK host differs from the explicitly selected origin.
        ImportError: Selected framework or native client is missing.

    Side Effects:
        Startup and per-request SDK authentication use an owned off-loop thread;
        cancellation waits for its completion, not a hard auth deadline. Requests
        incur bounded actual inference. Native OpenAI transport/version ownership
        is preserved; transports do not follow redirects or ambient proxy config.
        Shutdown closes every owned client. No token is copied into requests/artifacts.
        Authentication is absent at the helper endpoint: bind loopback only unless the
        customer supplies their own authenticated gateway. No deployment occurs.
    """
    resources: dict[str, Any] = {}

    async def handler(inputs: dict[str, Any], context: InvocationContext) -> AgentAnswer:
        return await resources["handler"](inputs, context)

    app = create_app(handler, isolation="request")
    # Content-free live validation counters: a dispatch hook is an attempted
    # transport request, not proof of provider receipt or sustainable capacity.
    app.state.inference_evidence = {"outbound_attempts": 0, "completed_responses": 0}

    async def record_dispatch(request: Any) -> None:
        """Count actual client dispatches without retaining URLs, headers or content."""
        app.state.inference_evidence["outbound_attempts"] += 1

    async def record_completion(response: Any) -> None:
        """Count only successful responses already accepted by the raw status guard."""
        if 200 <= response.status_code < 300:
            app.state.inference_evidence["completed_responses"] += 1

    @asynccontextmanager
    async def lifespan(app: Any) -> AsyncIterator[None]:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.core import Config
        from openai import AsyncOpenAI, DefaultAsyncHttpxClient

        def configure() -> Any:
            workspace = WorkspaceClient(
                config=Config(
                    profile=selection.profile, http_timeout_seconds=20, retry_timeout_seconds=1
                )
            )
            if workspace.config.host.rstrip("/") != selection.expected_host:
                raise RuntimeError(
                    "The selected profile does not resolve to the approved workspace"
                )
            return workspace

        workspace = await owned_thread(configure)

        async def authenticate_request(request: Any) -> None:
            """Refresh headers off-loop only after exact destination validation."""
            validate_model_request(request, selection)
            headers = await owned_thread(workspace.config.authenticate)
            authorization = next(
                (value for key, value in headers.items() if key.lower() == "authorization"), None
            )
            if not authorization:
                raise RuntimeError("SDK authentication did not produce authorization headers")
            request.headers["Authorization"] = authorization

        async with (
            DefaultAsyncHttpxClient(
                trust_env=False,
                follow_redirects=False,
                timeout=selection.timeout_seconds,
                event_hooks={
                    "request": [authenticate_request, record_dispatch],
                    "response": [response_completion_guard, record_completion],
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
            resources["handler"] = build_handler(framework, client, selection, http_client=http)
            try:
                yield
            finally:
                resources.clear()

    app.router.lifespan_context = lifespan
    return app


def main(arguments: Sequence[str] | None = None) -> None:
    """Validate a no-network plan by default; require consent before starting real clients."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--framework", required=True, choices=("langgraph", "openai-agents", "crewai")
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--workspace-host", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api", required=True, choices=("mlflow-responses", "openai-responses"))
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--accept-paid-traffic", action="store_true")
    options = parser.parse_args(arguments)
    selection = ModelSelection(options.profile, options.model, options.api, options.workspace_host)
    if not 1024 <= options.port <= 65535:
        parser.error("--port must be 1024..65535")
    if not options.live:
        print(
            f"Dry run: {options.framework}, {options.api}, no inference; request-isolated /invoke"
        )
        return
    if not options.accept_paid_traffic:
        parser.error(
            "--live requires --accept-paid-traffic and separately bounded benchmark traffic"
        )
    import uvicorn

    uvicorn.run(create_real_app(options.framework, selection), host="127.0.0.1", port=options.port)


if __name__ == "__main__":
    main()
