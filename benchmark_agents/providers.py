"""Server-owned provider settings; SDK authentication avoids copied access tokens."""

import os
from collections.abc import Generator
from typing import Any

import httpx
from openai import AsyncOpenAI, OpenAI

DEFAULT_FM_ENDPOINT = "databricks-gpt-5-4-mini"


def workspace_client(profile: str | None = None, host: str | None = None) -> Any:
    """Resolve explicitly configured SDK credentials without exporting tokens."""
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config

    profile = profile or os.getenv("DATABRICKS_CONFIG_PROFILE")
    host = host or os.getenv("DATABRICKS_HOST")
    if not profile and not host:
        raise ValueError(
            "Set DATABRICKS_CONFIG_PROFILE or DATABRICKS_HOST with SDK authentication."
        )
    return WorkspaceClient(
        config=Config(profile=profile, host=host, http_timeout_seconds=20, retry_timeout_seconds=20)
    )


class DatabricksAuth(httpx.Auth):
    """Delegate refreshable auth headers to the Databricks SDK on every call."""

    def __init__(self, workspace: Any) -> None:
        self.workspace = workspace

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers.update(self.workspace.config.authenticate())
        yield request


def judge_client(
    profile: str | None = None, host: str | None = None, timeout: int = 60, max_retries: int = 2
) -> Any:
    """Use direct Databricks FM inference for judging, without LiteLLM."""
    workspace = workspace_client(profile=profile, host=host)
    return OpenAI(
        base_url=workspace.config.host.rstrip("/") + "/serving-endpoints",
        api_key="sdk-auth",
        http_client=httpx.Client(auth=DatabricksAuth(workspace)),
        timeout=timeout,
        max_retries=max_retries,
    )


def judge_endpoint() -> str | None:
    """Use the low-cost default only when Databricks credentials are configured."""
    configured = os.getenv("BENCHMARK_JUDGE_MODEL")
    if configured:
        if configured.startswith("databricks:/"):
            return configured.removeprefix("databricks:/")
        if ":/" in configured:
            raise ValueError(
                "Judging uses Databricks directly; configure a Databricks endpoint name."
            )
        return configured
    if os.getenv("DATABRICKS_CONFIG_PROFILE") or os.getenv("DATABRICKS_HOST"):
        return DEFAULT_FM_ENDPOINT
    return None


def planner_client() -> Any:
    """Build the configured asynchronous inference client."""
    provider = os.getenv("BENCHMARK_LLM_PROVIDER", "databricks")
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
        return AsyncOpenAI()
    raise ValueError("BENCHMARK_LLM_PROVIDER must be databricks or openai.")
