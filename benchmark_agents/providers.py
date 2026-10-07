"""Server-owned provider settings; SDK authentication avoids copied access tokens."""

from collections.abc import Generator
from typing import Any

import httpx
from openai import AsyncOpenAI, OpenAI

from .configuration import getenv

DEFAULT_FM_ENDPOINT = "databricks-gpt-5-4-mini"


def workspace_client(profile: str | None = None, host: str | None = None) -> Any:
    """Resolve an operator-selected Databricks workspace through SDK authentication.

    Args:
        profile: Explicit CLI profile, falling back to DATABRICKS_CONFIG_PROFILE.
        host: Explicit workspace URL, falling back to DATABRICKS_HOST.

    Returns:
        A WorkspaceClient with nominal SDK HTTP and retry budgets. Credentials remain
        owned by the SDK instead of being copied into benchmark configuration. The
        task-local config-file selector is explicit; OAuth refresh has no hard overall
        wall-time guarantee from these HTTP settings.

    Raises:
        ValueError: Neither a profile nor a host was explicitly configured.
    """
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config

    if profile is None and host is None:
        profile = getenv("DATABRICKS_CONFIG_PROFILE")
        host = getenv("DATABRICKS_HOST")
    if not profile and not host:
        raise ValueError(
            "Set DATABRICKS_CONFIG_PROFILE or DATABRICKS_HOST with SDK authentication."
        )
    return WorkspaceClient(
        config=Config(
            profile=profile,
            host=host,
            config_file=getenv("DATABRICKS_CONFIG_FILE") or "~/.databrickscfg",
            http_timeout_seconds=20,
            retry_timeout_seconds=20,
        )
    )


class DatabricksAuth(httpx.Auth):
    """Delegate refreshable auth headers to the Databricks SDK on every call."""

    def __init__(self, workspace: Any) -> None:
        """Retain the SDK client whose authentication provider refreshes headers.

        Args:
            workspace: Configured WorkspaceClient for the authorized destination.
        """
        self.workspace = workspace

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Apply SDK authentication immediately before yielding an HTTP request.

        Args:
            request: Pending request sent by the planner or judge client.

        Yields:
            The request with current SDK authentication headers attached.
        """
        request.headers.update(self.workspace.config.authenticate())
        yield request


def judge_client(
    profile: str | None = None, host: str | None = None, timeout: int = 60, max_retries: int = 2
) -> Any:
    """Build a synchronous, SDK-authenticated client for direct Databricks judging.

    Args:
        profile: Frozen profile identifier, or the operator's configured default.
        host: Frozen workspace URL, or the operator's configured default.
        timeout: OpenAI client request timeout in seconds.
        max_retries: Maximum additional provider attempts after the initial call.

    Returns:
        An OpenAI-compatible client owned by the caller, which must close it.

    The SDK-auth marker is not a credential; DatabricksAuth supplies actual headers.
    """
    workspace = workspace_client(profile=profile, host=host)
    return OpenAI(
        base_url=workspace.config.host.rstrip("/") + "/serving-endpoints",
        api_key="sdk-auth",
        http_client=httpx.Client(auth=DatabricksAuth(workspace)),
        timeout=timeout,
        max_retries=max_retries,
    )


def judge_endpoint() -> str | None:
    """Resolve the server judge endpoint without performing inference.

    Returns:
        BENCHMARK_JUDGE_MODEL, stripping a legacy databricks:/ prefix; otherwise
        the default endpoint when a workspace is configured, or None.

    Raises:
        ValueError: A configured provider URI targets something other than Databricks.
    """
    configured = getenv("BENCHMARK_JUDGE_MODEL")
    if configured:
        if configured.startswith("databricks:/"):
            return configured.removeprefix("databricks:/")
        if ":/" in configured:
            raise ValueError(
                "Judging uses Databricks directly; configure a Databricks endpoint name."
            )
        return configured
    if getenv("DATABRICKS_CONFIG_PROFILE") or getenv("DATABRICKS_HOST"):
        return DEFAULT_FM_ENDPOINT
    return None


def planner_client() -> Any:
    """Build an asynchronous client for the operator-selected planner provider.

    Returns:
        A caller-owned Databricks or OpenAI client. The Databricks path uses SDK
        authentication, a 60-second timeout, and at most two additional retries.
        The OpenAI path uses that client's configured defaults.

    Raises:
        ValueError: BENCHMARK_LLM_PROVIDER is unsupported or workspace settings
            required by the Databricks path are absent.
    """
    provider = getenv("BENCHMARK_LLM_PROVIDER", "databricks")
    if provider == "databricks":
        workspace = workspace_client()
        return AsyncOpenAI(
            base_url=workspace.config.host.rstrip("/") + "/serving-endpoints",
            api_key="sdk-auth",
            http_client=httpx.AsyncClient(auth=DatabricksAuth(workspace)),
            timeout=60,
            max_retries=2,
        )
    if provider == "openai":
        return AsyncOpenAI(api_key=getenv("OPENAI_API_KEY"))
    raise ValueError("BENCHMARK_LLM_PROVIDER must be databricks or openai.")
