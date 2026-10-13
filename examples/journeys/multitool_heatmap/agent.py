"""Loopback-only real multi-tool agent host, separate from the traffic generator.

The explicit local SQLite destination and selected export policy are sample
choices, not changes to EvalSurge/MLflow defaults. Sync matches the demonstrated
smoke; async is an explicit opt-in for fresh validation. The actual model client
has no retry or fixture fallback. Import/construction does not authenticate/infer.
"""

import argparse
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from evalsurge.serving import AgentAnswer, InvocationContext, create_app
from evalsurge.tracing import traced_handler
from examples.real_framework_handler import (
    ModelSelection,
    owned_thread,
    response_completion_guard,
    validate_model_request,
)

from .handler import build_handler


def create_tool_app(
    selection: ModelSelection,
    tracking_uri: str,
    experiment_id: str,
    *,
    trace_export: Literal["sync", "async"] = "sync",
) -> Any:
    """Own native clients/tracing for one capped, request-isolated loopback endpoint.

    Args:
        selection: Exact operator-selected profile, workspace origin and model.
        tracking_uri: Explicit absolute local SQLite URI; no Databricks tracking.
        experiment_id: Existing authorized experiment ID in that SQLite store.
        trace_export: Explicit sample-only export policy, set before exporter
            initialization. Sync matches the previously demonstrated smoke;
            async is available for newly approved collector validation.

    Returns:
        FastAPI app with /invoke and a shutdown-owned native client lifespan.

    Raises:
        ValueError: Export policy is invalid or tracing is not absolute local SQLite.
        RuntimeError: Profile/host/experiment mismatch or five-call cap reached.

    Side Effects:
        Startup initializes operator-owned local tracing and native authentication
        without inference. At most five model transport attempts per app lifetime,
        with 512-token/30-second per-call ceilings. Three tools and traces run in
        the agent, not Locust. Export costs contribute to measured latency.
        No per-request flush, destination fallback, redirect or provider retry.
        Native SDK auth work is owned off-loop but is not a hard timeout boundary.
        Shutdown closes owned clients; the unauthenticated endpoint binds loopback.
    """
    if not isinstance(trace_export, str) or trace_export not in {"sync", "async"}:
        raise ValueError("Select trace export as sync or async")
    if not tracking_uri.startswith("sqlite:////") or "?" in tracking_uri or "#" in tracking_uri:
        raise ValueError("Select an absolute local SQLite tracing URI")
    resources: dict[str, Any] = {}
    attempts = 0

    async def handler(inputs: dict[str, Any], context: InvocationContext) -> AgentAnswer:
        return await resources["handler"](inputs, context)

    app = create_app(handler, isolation="request")
    app.state.trace_export = trace_export

    @asynccontextmanager
    async def lifespan(_app: Any) -> AsyncIterator[None]:
        import mlflow
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.core import Config
        from mlflow.environment_variables import MLFLOW_ENABLE_ASYNC_TRACE_LOGGING
        from openai import AsyncOpenAI, DefaultAsyncHttpxClient

        # Explicit agent-process sample policy, selected before any local exporter
        # is initialized. The runner never sets it; neither mode flushes per call.
        MLFLOW_ENABLE_ASYNC_TRACE_LOGGING.set(trace_export == "async")
        mlflow.set_tracking_uri(tracking_uri)
        experiment = mlflow.MlflowClient(tracking_uri=tracking_uri).get_experiment(experiment_id)
        if experiment is None or experiment.lifecycle_stage != "active":
            raise RuntimeError("Select an existing active local trace experiment")
        mlflow.set_experiment(experiment_id=experiment_id)
        mlflow.openai.autolog(log_traces=True)

        def configure() -> Any:
            workspace = WorkspaceClient(
                config=Config(
                    profile=selection.profile, http_timeout_seconds=20, retry_timeout_seconds=1
                )
            )
            if workspace.config.host.rstrip("/") != selection.expected_host:
                raise RuntimeError("Selected profile does not match the approved workspace")
            return workspace

        workspace = await owned_thread(configure)

        async def authenticate(request: Any) -> None:
            nonlocal attempts
            validate_model_request(request, selection)
            headers = await owned_thread(workspace.config.authenticate)
            authorization = next(
                (v for k, v in headers.items() if k.lower() == "authorization"), None
            )
            if not authorization:
                raise RuntimeError("SDK authentication produced no authorization")
            if attempts >= 5:
                raise RuntimeError("Sample lifetime model-attempt ceiling reached")
            attempts += 1
            request.headers["Authorization"] = authorization

        async with (
            DefaultAsyncHttpxClient(
                trust_env=False,
                follow_redirects=False,
                timeout=selection.timeout_seconds,
                event_hooks={
                    "request": [authenticate],
                    "response": [response_completion_guard],
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
            resources["handler"] = traced_handler(
                build_handler(client, selection, Path(__file__).parent),
                experiment_id=experiment_id,
            )
            try:
                yield
            finally:
                resources.clear()

    app.router.lifespan_context = lifespan
    return app


def main() -> None:
    """Require explicit native selections and paid-call consent before agent startup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--workspace-host", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api", required=True, choices=("mlflow-responses", "openai-responses"))
    parser.add_argument("--tracking-uri", required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--trace-export", choices=("sync", "async"), default="sync")
    parser.add_argument("--port", type=int, default=9002)
    parser.add_argument("--allow-paid-inference", action="store_true")
    args = parser.parse_args()
    if not args.allow_paid_inference:
        parser.error("Review five possible real model calls; pass --allow-paid-inference.")
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be 1024..65535")
    selection = ModelSelection(args.profile, args.model, args.api, args.workspace_host)
    import uvicorn

    uvicorn.run(
        create_tool_app(
            selection, args.tracking_uri, args.experiment_id, trace_export=args.trace_export
        ),
        host="127.0.0.1",
        port=args.port,
        access_log=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
