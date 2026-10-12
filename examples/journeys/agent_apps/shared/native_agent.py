"""Agent-only native App entrypoint; the load generator runs somewhere else.

Stage this module with the reviewed framework-neutral real handler. Native App
authentication/Runtime Store configuration is owned by the App deployment, not by
benchmark requests. Importing this module performs no authentication or inference.
"""

from __future__ import annotations

import math
import os
import re
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit

Framework = Literal["langgraph", "openai-agents", "crewai"]
_MODEL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_RUNTIME_STORE_FIELDS = (
    "DATABRICKS_AGENTBRICKS_RUNTIME_STORE_LAKEBASE_BRANCH",
    "DATABRICKS_AGENTBRICKS_RUNTIME_STORE_DATABASE",
    "DATABRICKS_AGENTBRICKS_RUNTIME_STORE_USERNAME",
)


@dataclass(frozen=True)
class AppSelection:
    """Operator-owned App model/host selections; deliberately excludes credentials."""

    workspace_host: str
    model: str
    max_output_tokens: int = 512
    timeout_seconds: float = 30

    def __post_init__(self) -> None:
        """Validate exact destinations and per-call bounds without auth or network."""
        if (
            not isinstance(self.workspace_host, str)
            or any(
                character.isspace() or ord(character) < 32 or ord(character) == 127
                for character in self.workspace_host
            )
            or "\\" in self.workspace_host
        ):
            raise ValueError("Select an exact HTTPS workspace origin without a port or path")
        try:
            parsed = urlsplit(self.workspace_host)
            valid_host = (
                parsed.scheme == "https"
                and parsed.hostname is not None
                and self.workspace_host == f"https://{parsed.hostname}"
                and parsed.username is None
                and parsed.password is None
                and parsed.netloc == parsed.hostname
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            valid_host = False
        if not valid_host:
            raise ValueError("Select an exact HTTPS workspace origin without a port or path")
        if not isinstance(self.model, str) or _MODEL_NAME.fullmatch(self.model) is None:
            raise ValueError("Bind one explicit model resource with MODEL_SERVICE_NAME")
        if type(self.max_output_tokens) is not int or not 1 <= self.max_output_tokens <= 512:
            raise ValueError("The example output-token cap is 1..512")
        if (
            type(self.timeout_seconds) not in {int, float}
            or not math.isfinite(self.timeout_seconds)
            or not 0.1 <= self.timeout_seconds <= 30
        ):
            raise ValueError("The example timeout is 0.1..30 seconds")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> AppSelection:
        """Validate explicit deployment selections before resolving authentication.

        Args:
            environment: App-injected environment. The caller retains ownership of
                credentials; this object never stores them.

        Returns:
            An exact HTTPS workspace origin and model resource selection.

        Raises:
            ValueError: Required selections/credentials are absent, selectors
                conflict, or the injected workspace differs from the approved one.

        Side Effects:
            None. Does not resolve SDK credentials, call a model or log values.
            App-owned OAuth is the only permitted configuration in this template;
            request-user OAuth and notebook credentials are not accepted here.
        """
        host = environment.get("EVALSURGE_SAMPLE_WORKSPACE_HOST", "")
        selection = cls(workspace_host=host, model=environment.get("MODEL_SERVICE_NAME", ""))
        if environment.get("DATABRICKS_HOST", "").rstrip("/") != host:
            raise ValueError("The App-injected workspace must match the approved origin")
        if any(environment.get(name) for name in ("DATABRICKS_TOKEN", "DATABRICKS_CONFIG_PROFILE")):
            raise ValueError("This App template accepts App-owned OAuth, not a token or profile")
        if environment.get("DATABRICKS_AUTH_TYPE") not in {None, "", "oauth-m2m"}:
            raise ValueError("This App template requires oauth-m2m authentication")
        if not all(
            environment.get(name, "").strip()
            for name in ("DATABRICKS_CLIENT_ID", "DATABRICKS_CLIENT_SECRET")
        ):
            raise ValueError("App-injected OAuth client credentials are required")
        return selection

    @property
    def base_url(self) -> str:
        """Return the fixed nonstreaming MLflow Responses gateway prefix."""
        return f"{self.workspace_host}/ai-gateway/mlflow/v1"


def validate_native_input(value: Any, *, attempt: int) -> str:
    """Reject unsupported native input before any paid inference.

    Args:
        value: Native Runtime input, supporting exactly one user message.
        attempt: Native Runtime attempt number; only the initial attempt is allowed.

    Returns:
        The original nonblank query, bounded to 512 characters.

    Raises:
        ValueError: Unsupported message/attempt, or the documented intentional
            pre-provider failure sentinel. No success-shaped fallback exists.

    Side Effects:
        None. Sessions are correlation only: no history or conversational memory is
        read. The special sentinel validates fail-fast, not successful inference.
    """
    if type(attempt) is not int or attempt != 1:
        raise ValueError("Automatic recovery/reinvocation is disabled in this sample")
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise ValueError("Supply exactly one native user message")
    message = value[0]
    if set(message) != {"role", "content"} or message["role"] != "user":
        raise ValueError("This sample accepts user/content only; agent-specific extras are invalid")
    query = message["content"]
    if not isinstance(query, str) or not query.strip() or len(query) > 512:
        raise ValueError("The sample query must be nonblank and at most 512 characters")
    if query == "__evalsurge_fail_preflight__":
        raise ValueError("Intentional pre-provider failure; no model was called")
    return query


def validate_model_destination(method: str, url: str, selection: AppSelection) -> None:
    """Bind credentials to the single permitted model request destination.

    Args:
        method: Actual outgoing native client request method.
        url: Actual outgoing request URL, including any query string.
        selection: Exact operator-approved workspace/model configuration.

    Raises:
        ValueError: The request is not the single nonstreaming Responses POST route.

    Side Effects:
        None. Call before requesting or applying OAuth headers; redirects and
        ambient proxy configuration must remain disabled on the owned transport.
    """
    if method != "POST" or url != f"{selection.base_url}/responses":
        raise ValueError("The model request is outside the approved Responses destination")


def validate_runtime_store_environment(environment: Mapping[str, str]) -> None:
    """Require the inspected managed durable-store configuration, never a local fallback.

    Args:
        environment: Actual process environment read by native Runtime construction.

    Raises:
        ValueError: Local/legacy storage is selected, or managed resource selections
            are absent/placeholders. This checks configuration only, not permissions,
            store reachability, provisioning or an initialized schema.

    Side Effects:
        None. No branch, username, credential, payload or environment value is
        emitted. The field names come from the inspected native 0.4.0 store source.
    """
    if environment.get("DATABRICKS_AGENTBRICKS_RUNTIME_STORE_LOCAL", "").lower() == "true":
        raise ValueError("Deployed native samples require a managed durable Runtime Store")
    if environment.get("DATABRICKS_AGENTBRICKS_RUNTIME_STORE_LAKEBASE_ENDPOINT"):
        raise ValueError("The native sample requires the reviewed managed store route")
    values = [environment.get(name, "") for name in _RUNTIME_STORE_FIELDS]
    if any(not value.strip() or value.startswith("REPLACE_") for value in values):
        raise ValueError("Select the managed Runtime Store branch, database and username")


def create_native_app(framework: Framework, *, environment: Mapping[str, str] | None = None) -> Any:
    """Compose an actual framework/model client around native Runtime lifecycle.

    Args:
        framework: Explicit selected framework. CrewAI's supported deployment
            route is unresolved; never substitute a false CLI framework label.
        environment: App-injected model/auth environment, read at lifespan startup.
            Native Runtime Store selection always uses the actual process environment.

    Returns:
        Native DurableAgentServer exposing /api/invocations.

    Raises:
        ImportError: The staged handler, selected framework or native dependencies
            are absent. No installation, mock, alternative server or fallback.
        ValueError: Configuration/input is invalid; provider failures propagate.

    Side Effects:
        Construction initializes native runtime configuration. Startup owns OAuth,
        transport/model clients and Runtime Store; it performs no model inference.
        Each valid initial invocation permits one bounded LangGraph/OpenAI model
        call, or at most two CrewAI calls. Native
        Runtime persistence may retain inputs/outputs; it is not conversational
        memory or trace export. Shutdown stops runtime work before closing clients.
        The native App ingress, permissions and Runtime Store are deployment gates.
    """
    if framework not in {"langgraph", "openai-agents", "crewai"}:
        raise ValueError("Choose one of the prepared native App framework templates")
    validate_runtime_store_environment(os.environ)
    from databricks_agentkit import DurableAgentServer

    app = DurableAgentServer()
    native_lifespan = app.router.lifespan_context
    resources: dict[str, Any] = {}

    @app.invoke
    async def invoke(value: Any, context: Any) -> dict[str, Any]:
        """Emit and return only the real handler's completed answer and provider usage."""
        query = validate_native_input(value, attempt=context.attempt)
        answer = await resources["handler"]({"query": query}, context)
        await context.emit(
            {"type": "message", "message": {"role": "assistant", "content": answer.outputs}}
        )
        output: dict[str, Any] = {"answer": answer.outputs}
        if answer.output_tokens is not None:
            output["usage"] = {"output_tokens": answer.output_tokens}
        return output

    @asynccontextmanager
    async def lifespan(_: Any) -> AsyncIterator[None]:
        from databricks.sdk.core import Config
        from openai import AsyncOpenAI, DefaultAsyncHttpxClient
        from real_framework_handler import (
            ModelSelection,
            build_handler,
            owned_thread,
            response_completion_guard,
        )

        current_environment = os.environ if environment is None else environment
        selection = AppSelection.from_environment(current_environment)
        if framework == "crewai" and os.getenv("CREWAI_DISABLE_TELEMETRY") != "true":
            raise ValueError("Set CREWAI_DISABLE_TELEMETRY=true before native CrewAI startup")

        def configure() -> Any:
            """Initialize SDK OAuth off the event loop without a profile-file fallback."""
            return Config(
                host=selection.workspace_host,
                client_id=current_environment["DATABRICKS_CLIENT_ID"],
                client_secret=current_environment["DATABRICKS_CLIENT_SECRET"],
                auth_type="oauth-m2m",
                config_file="/dev/null",
                http_timeout_seconds=20,
                retry_timeout_seconds=1,
            )

        config = await owned_thread(configure)

        async def authenticate_request(request: Any) -> None:
            """Refresh App OAuth only after exact destination validation, off the hub."""
            validate_model_destination(request.method, str(request.url), selection)
            headers = await owned_thread(config.authenticate)
            authorization = next(
                (value for key, value in headers.items() if key.lower() == "authorization"), None
            )
            if not authorization:
                raise RuntimeError("App OAuth did not produce authorization headers")
            request.headers["Authorization"] = authorization

        # This is a provenance label, not a local Databricks profile selection.
        model = ModelSelection(
            profile="app-service-principal",
            model=selection.model,
            api="mlflow-responses",
            expected_host=selection.workspace_host,
            max_output_tokens=selection.max_output_tokens,
            timeout_seconds=selection.timeout_seconds,
        )
        # Use OpenAI's own transport class: its source-reviewed versions can use
        # httpx2 rather than httpx. Do not mix different native transport classes.
        async with (
            DefaultAsyncHttpxClient(
                trust_env=False,
                follow_redirects=False,
                timeout=selection.timeout_seconds,
                event_hooks={
                    "request": [authenticate_request],
                    "response": [response_completion_guard],
                },
            ) as http,
            AsyncOpenAI(
                base_url=selection.base_url,
                api_key="sdk-managed",
                http_client=http,
                max_retries=0,
                timeout=selection.timeout_seconds,
            ) as client,
        ):
            resources["handler"] = build_handler(framework, client, model, http_client=http)
            try:
                async with native_lifespan(app):
                    yield
            finally:
                resources.clear()

    app.router.lifespan_context = lifespan
    return app


def run_server(app: Any) -> None:
    """Serve behind the Databricks App ingress on its injected port.

    Args:
        app: Constructed native agent App, never an EvalSurge runner service.

    Raises:
        ValueError: The App port is absent or invalid.

    Side Effects:
        Starts the server and its owned lifespan. Do not run this entrypoint on an
        exposed laptop interface; the deployed Databricks App ingress owns auth.
    """
    import uvicorn

    try:
        port = int(os.environ["DATABRICKS_APP_PORT"])
    except (KeyError, ValueError):
        raise ValueError("Run with the Databricks App-injected port") from None
    if not 1024 <= port <= 65535:
        raise ValueError("The App port must be 1024..65535")
    uvicorn.run(app, host="0.0.0.0", port=port)
