"""Test-only SDK/OAuth and exact-App HTTP boundaries, including Locust workers.

This does not implement DurableAgentServer, App deployment, or Lakebase. It keeps
the real SDK discovery/authentication APIs while containing all HTTP traffic in
one authorized loopback fixture. Never use this transport in application code.
"""

import json
import os
from pathlib import Path
from typing import Any

import requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks.sdk.credentials_provider import OAuthCredentialsProvider, oauth_credentials_strategy
from databricks.sdk.oauth import HostMetadata, Token

from benchmark_agents import target_resolver


def install_boundary(
    *,
    profile_file: str,
    app_name: str,
    origin: str,
    endpoint: str,
    audit_file: str,
    framework: str,
    invocation_status: str,
) -> None:
    """Install narrowly controlled provider boundaries in one test process.

    Args:
        profile_file: Test-owned SDK profile file, never a developer profile.
        app_name: Exact synthetic App resource returned by the native AppsAPI.
        origin: Exact synthetic HTTPS App origin authorized by discovery.
        endpoint: Loopback HTTP fixture receiving only the invocation path.
        audit_file: Test-owned append-only counter log; no credentials are written.
        framework: Exact real framework selected by the loopback envelope fixture.
        invocation_status: Synthetic outer lifecycle for completion/failure tests.

    Raises:
        AssertionError: A different profile, SDK operation, or HTTP destination is
            attempted. No unexpected request is forwarded to a real destination.

    Side effects remain process-local. OAuth tokens are synthetic and refreshed
    on every call; the real SDK converts transport data to its native App type.
    The original Requests adapter performs actual HTTP, without retries added.
    """
    import databricks.sdk.config

    databricks.sdk.config.get_host_metadata = lambda *args, **kwargs: HostMetadata(oidc_endpoint="")
    count = 0

    def audit(kind: str, **values: Any) -> None:
        """Append content-free process/counter evidence to the test-owned journal."""
        with Path(audit_file).open("a", encoding="utf-8") as output:
            output.write(json.dumps({"kind": kind, "pid": os.getpid(), **values}) + "\n")

    def token() -> Token:
        """Issue a fresh synthetic token, retaining only its counter in evidence."""
        nonlocal count
        count += 1
        audit("oauth", counter=count)
        return Token(access_token=f"fixture-{os.getpid()}-{count}", token_type="Bearer")

    @oauth_credentials_strategy("controlled-app-e2e", [])
    def credentials(config: Config) -> OAuthCredentialsProvider:
        """Provide the actual SDK's OAuth source without network credentials."""
        return OAuthCredentialsProvider(lambda: {}, token)

    workspace = WorkspaceClient(
        config=Config(
            profile="controlled-app",
            config_file=profile_file,
            credentials_strategy=credentials,
        )
    )
    assert workspace.config.host == "https://controlled-workspace.invalid"

    def discovery(method: str, path: str, **kwargs: Any) -> dict[str, str]:
        """Control only native AppsAPI HTTP, preserving SDK request/response types."""
        assert method == "GET" and path == f"/api/2.0/apps/{app_name}"
        audit("discovery")
        return {"name": app_name, "url": origin}

    workspace.api_client.do = discovery

    def selected_workspace(*, profile: str) -> WorkspaceClient:
        """Reject any implicit or developer-selected profile before SDK discovery."""
        assert profile == "controlled-app"
        return workspace

    target_resolver.workspace_client = selected_workspace
    original_send = requests.adapters.HTTPAdapter.send

    def send(
        adapter: requests.adapters.HTTPAdapter,
        request: requests.PreparedRequest,
        *args: Any,
        **kwargs: Any,
    ) -> requests.Response:
        """Bind the one exact synthetic App URL to real loopback HTTP transport."""
        assert request.method == "POST"
        assert request.url == origin + "/api/invocations"
        assert kwargs.get("proxies") in ({}, None)
        mapped = request.copy()
        mapped.url = endpoint
        mapped.headers["X-Test-Framework"] = framework
        mapped.headers["X-Test-Invocation-Status"] = invocation_status
        audit("dispatch")
        return original_send(adapter, mapped, *args, **kwargs)

    requests.adapters.HTTPAdapter.send = send
