"""Operator-owned target resolution; Databricks discovery never invokes an agent."""

import os
import re
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from .configuration import (
    SDK_PROFILE_OVERRIDE_ENV,
    environment,
    profile_config_file_conflict,
    profile_override_present,
)
from .connections import Connection, app_workspace, validate_connection
from .models import Target
from .providers import workspace_client

if TYPE_CHECKING:
    from .settings import ConnectionSettings


class TargetResolutionError(ValueError):
    """A fixed safe resolution failure that omits SDK messages and private config."""


def _reject_profile_overrides() -> None:
    """Fail before SDK calls when ambient identity/routing can override a profile.

    Raises:
        TargetResolutionError: An SDK destination/identity/authentication override
            is set.

    SDK Config merges environment before the selected file profile. Its public
    attribute metadata identifies credential inputs; named attributes additionally
    cover routing fields lacking auth metadata. Only presence is inspected. Profile
    and matching config-file selectors remain allowed; the process environment is
    never temporarily changed, avoiding cross-thread credential races.
    """
    configured = environment()
    if profile_config_file_conflict(os.environ, configured):
        raise TargetResolutionError(
            "Registered App profile conflicts with the authentication configuration selector; "
            "use an isolated operator environment"
        )
    from databricks.sdk.core import Config

    attributes = Config.attributes()
    names = {
        name
        for attribute in attributes
        if attribute.auth
        or attribute.name
        in {
            "host",
            "auth_type",
            "account_id",
            "workspace_id",
            "group_id",
            "cloud",
            "discovery_url",
            "token_audience",
            "azure_environment",
        }
        for name in [attribute.env, *attribute.env_aliases]
        if name
    }
    # The API's task-local snapshot becomes the worker's actual environment.
    # Reject both sources now, so admission cannot succeed only to fail preflight.
    if profile_override_present(os.environ, extra_names=names) or profile_override_present(
        configured, extra_names=names
    ):
        raise TargetResolutionError(
            "Registered App profile conflicts with ambient SDK destination or credentials; "
            "use an isolated operator environment"
        )


def _app_origin(url: Any) -> str:
    """Validate an SDK-returned HTTPS origin without inferring a hostname.

    Args:
        url: App.url from the configured workspace's Apps API.

    Returns:
        The exact origin, without its optional trailing slash.

    Raises:
        TargetResolutionError: The App has no valid deployment origin.

    No URLs are followed. Discovery provenance, rather than a guessed cloud suffix,
    binds the deployment to the explicitly selected SDK workspace.
    """
    if not isinstance(url, str):
        raise TargetResolutionError("Registered App has no valid deployment URL")
    try:
        # Apply identical strict parsing to configured and SDK-discovered origins.
        # URL parsers can strip controls or disagree about backslash host boundaries.
        return app_workspace(url)
    except ValueError:
        raise TargetResolutionError("Registered App has no valid deployment URL") from None


def _workspace_app(profile: str, app_name: str) -> tuple[Any, str]:
    """Look up one deployment through an explicitly selected OAuth SDK client.

    Args:
        profile: Operator-selected profile; never falls back to another profile.
        app_name: Operator-selected App resource name.

    Returns:
        SDK workspace and its exact deployed App origin.

    Raises:
        TargetResolutionError: SDK discovery/authentication or deployment validation
            fails. Original SDK exceptions and credential values are suppressed.

    Discovery uses nominal SDK HTTP/retry budgets. OAuth credential sources can
    exceed those budgets; there is no hard overall authentication deadline here.
    These calls never send inference, create resources, or perform paid validation.
    """
    _reject_profile_overrides()
    try:
        workspace = workspace_client(profile=profile)
        # oauth_token uses the SDK's OAuthCredentialsProvider, rejecting PAT/basic.
        token = workspace.config.oauth_token()
        if not token.access_token or token.token_type not in {None, "Bearer", "bearer"}:
            raise ValueError
        origin = _app_origin(workspace.apps.get(name=app_name).url)
    except Exception:  # noqa: BLE001 - provider errors may contain hosts or credentials
        raise TargetResolutionError(
            "Registered App discovery or OAuth authentication failed"
        ) from None
    return workspace, origin


def _native_environment(workspace: str, client_id: str, workspace_id: str | None = None) -> str:
    """Validate actual and detached native M2M selectors before any SDK construction.

    Args:
        workspace: Exact operator-selected workspace origin.
        client_id: Expected runner service-principal client UUID, not its numeric
            principal ID or the target App's OAuth application/audience ID.
        workspace_id: Optional operator-pinned positive numeric identifier. Any
            configured or injected ID requires exact actual/snapshot agreement.

    Returns:
        The private injected secret for immediate SDK use only. Never persist it.

    Raises:
        TargetResolutionError: Any identity, token, file/profile or alternate
            authentication selector conflicts, or the two environments disagree.

    Side Effects:
        Inspects SDK field metadata and environments only, without credential
        resolution or file/network calls. This is operator/configuration agreement,
        not cryptographic attestation that a process runs on Databricks Apps.
    """
    from databricks.sdk.core import Config

    permitted = {
        "DATABRICKS_HOST",
        "DATABRICKS_WORKSPACE_ID",
        "DATABRICKS_CLIENT_ID",
        "DATABRICKS_CLIENT_SECRET",
        "DATABRICKS_AUTH_TYPE",
    }
    forbidden = set(SDK_PROFILE_OVERRIDE_ENV)
    forbidden.update(
        {
            "DATABRICKS_CONFIG_PROFILE",
            "DATABRICKS_CONFIG_FILE",
            "DATABRICKS_CLI_PATH",
            "DATABRICKS_DEBUG_HEADERS",
        }
    )
    for attribute in Config.attributes():
        if attribute.auth or attribute.name in {
            "host",
            "auth_type",
            "account_id",
            "workspace_id",
            "group_id",
            "cloud",
            "discovery_url",
            "token_audience",
            "azure_environment",
            "profile",
            "config_file",
            "databricks_cli_path",
            "debug_headers",
        }:
            forbidden.update(name for name in (attribute.env, *attribute.env_aliases) if name)
    forbidden.difference_update(permitted)
    actual, scoped = os.environ, environment()
    workspace_id_present = workspace_id is not None or any(
        "DATABRICKS_WORKSPACE_ID" in values for values in (actual, scoped)
    )
    if workspace_id_present and (
        not isinstance(workspace_id, str)
        or re.fullmatch(r"[1-9][0-9]{0,19}", workspace_id) is None
        or any(values.get("DATABRICKS_WORKSPACE_ID") != workspace_id for values in (actual, scoped))
    ):
        raise TargetResolutionError("Native App identity or authentication selectors conflict")
    for values in (actual, scoped):
        if (
            any(values.get(name) for name in forbidden)
            or values.get("DATABRICKS_HOST", "").rstrip("/") != workspace
            or values.get("DATABRICKS_CLIENT_ID") != client_id
            or not values.get("DATABRICKS_CLIENT_SECRET")
            or values.get("DATABRICKS_AUTH_TYPE") not in {None, "", "oauth-m2m"}
        ):
            raise TargetResolutionError("Native App identity or authentication selectors conflict")
    if actual.get("DATABRICKS_CLIENT_SECRET") != scoped.get("DATABRICKS_CLIENT_SECRET"):
        raise TargetResolutionError("Native App identity or authentication selectors conflict")
    return scoped["DATABRICKS_CLIENT_SECRET"]


def _native_workspace_app(
    binding: "Connection | ConnectionSettings", app_name: str
) -> tuple[Any, str]:
    """Resolve a declared target using the explicitly bound runner App's own OAuth.

    Args:
        binding: Private operator settings with exact workspace, runner App and
            service-principal client UUID; never a public benchmark request.
        app_name: Exact registered target App name, not an incoming URL.

    Returns:
        Independent refreshable SDK client and the workspace-discovered App origin.

    Raises:
        TargetResolutionError: Native selector, SDK identity, runner/resource
            mapping, target discovery or refreshable OAuth verification fails.

    Side Effects:
        Makes SDK OAuth/discovery metadata calls only. Config explicitly selects
        the native OAuth M2M strategy; it cannot fall back to a file/profile/token.
        No secret is copied to configuration, disk, receipts or another process.
        Each Locust process reconstructs and verifies its own client. SDK OIDC
        discovery has independent transport budgets, not a hard phase deadline.
    """
    if not all((binding.workspace, binding.runner_app, binding.client_id)) or binding.profile:
        raise TargetResolutionError("Native App requires an explicit operator identity")
    secret = _native_environment(binding.workspace, binding.client_id, binding.workspace_id)
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.core import Config
        from databricks.sdk.credentials_provider import oauth_service_principal
        from databricks.sdk.service.apps import AppResourceAppAppPermission

        workspace = WorkspaceClient(
            config=Config(
                host=binding.workspace,
                workspace_id=binding.workspace_id,
                client_id=binding.client_id,
                client_secret=secret,
                auth_type="oauth-m2m",
                credentials_strategy=oauth_service_principal,
                http_timeout_seconds=5,
                retry_timeout_seconds=1,
                skip_verify=False,
                debug_headers=False,
            )
        )
        if (
            workspace.config.host.rstrip("/") != binding.workspace
            or workspace.config.auth_type != "oauth-m2m"
            or workspace.config.client_id != binding.client_id
            or (
                binding.workspace_id is not None
                and workspace.config.workspace_id != binding.workspace_id
            )
            or workspace.config.profile
            or workspace.config.config_file
        ):
            raise ValueError
        token = workspace.config.oauth_token()
        if not token.access_token or token.token_type not in {None, "Bearer", "bearer"}:
            raise ValueError
        runner = workspace.apps.get(name=binding.runner_app)
        if (
            runner.name != binding.runner_app
            or runner.service_principal_client_id != binding.client_id
            or not any(
                resource.app is not None
                and resource.app.name == app_name
                and resource.app.permission == AppResourceAppAppPermission.CAN_USE
                for resource in (runner.resources or [])
            )
        ):
            raise ValueError
        target = workspace.apps.get(name=app_name)
        if target.name != app_name:
            raise ValueError
        origin = _app_origin(target.url)
    except Exception:  # noqa: BLE001 - native credentials/SDK errors must stay private
        raise TargetResolutionError(
            "Native App identity, resource discovery or OAuth failed"
        ) from None
    return workspace, origin


def app_authentication(connection: Connection) -> Callable[[], dict[str, str]]:
    """Return fresh OAuth headers bound to one previously resolved App origin.

    Args:
        connection: Frozen exact endpoint, explicit operator profile and App name.

    Returns:
        A callable reading the SDK's refreshable OAuth token on each dispatch.

    Raises:
        TargetResolutionError: Missing operator configuration, changed App origin,
            unavailable OAuth, or SDK authentication failure.

    The worker revalidates discovery once before dispatch. Headers contain only
    Authorization, never workspace-specific SDK headers. Redirects remain disabled
    by the sole Locust engine; no access token is copied to persisted configuration.
    """
    if not connection.app_name:
        raise TargetResolutionError("Registered App requires an explicit operator profile")
    if connection.app_auth == "app-runtime":
        workspace, origin = _native_workspace_app(connection, connection.app_name)
    elif connection.profile:
        workspace, origin = _workspace_app(connection.profile, connection.app_name)
    else:
        raise TargetResolutionError("Registered App requires an explicit operator profile")
    endpoint = urlsplit(connection.url)
    if connection.url not in {origin + "/api/invocations", origin + "/responses"} or (
        endpoint.scheme != "https"
    ):
        raise TargetResolutionError("Registered App destination changed")

    def headers() -> dict[str, str]:
        """Resolve the current OAuth token; never retain it in application state."""
        try:
            token = workspace.config.oauth_token()
            if not token.access_token or token.token_type not in {None, "Bearer", "bearer"}:
                raise ValueError
            return {"Authorization": "Bearer " + token.access_token}
        except Exception:  # noqa: BLE001 - only a fixed credential diagnostic is exported
            raise TargetResolutionError("Registered App OAuth authentication failed") from None

    return headers


def resolve_registered_target(
    name: str,
    connections: Mapping[str, "ConnectionSettings"],
    protocol: str | None = None,
) -> tuple[Target, Connection]:
    """Resolve an opaque registered target without accepting caller destinations.

    Args:
        name: Public opaque connection identifier.
        connections: Immutable operator registry; no credential values are required.
        protocol: Optional selected protocol, restricted to the configured allowlist.

    Returns:
        Detached target and credential reference for coordinator/worker ownership.

    Raises:
        TargetResolutionError: Unknown target, unsupported protocol, or App discovery
            failure. Diagnostics do not expose profile, host, App name, or SDK text.
        ValueError: Invalid operator HTTP connection configuration.

    SDK lookup blocks; async callers must offload this function to a thread. App
    sessions are isolated per attempt unless an operator explicitly fixes one.
    Fixed sessions can serialize invocation ordering and change answers when the
    target implements history; a session identifier alone does not create memory.
    """
    preset = connections.get(name)
    if preset is None:
        raise TargetResolutionError("Unknown registered target")
    selected = protocol or (preset.protocols[0] if preset.protocols else "openai-chat")
    enabled = preset.protocols or ("openai-chat", "mlflow-agent-server", "http-json")
    if selected not in enabled:
        raise TargetResolutionError("Protocol is not enabled for the registered target")
    if preset.kind == "databricks-app":
        if selected not in {"databricks-agent-runtime", "mlflow-agent-server"}:
            raise TargetResolutionError("Protocol is not supported for a registered App")
        if not preset.app_name:
            raise TargetResolutionError("Registered App requires an explicit operator profile")
        if preset.app_auth == "app-runtime":
            _, origin = _native_workspace_app(preset, preset.app_name)
        elif preset.profile:
            _, origin = _workspace_app(preset.profile, preset.app_name)
        else:
            raise TargetResolutionError("Registered App requires an explicit operator profile")
        path = "/api/invocations" if selected == "databricks-agent-runtime" else "/responses"
        connection = Connection(
            url=origin + path,
            auth="databricks-app",
            profile=preset.profile,
            app_name=preset.app_name,
            app_auth=preset.app_auth,
            workspace=preset.workspace,
            workspace_id=preset.workspace_id,
            runner_app=preset.runner_app,
            client_id=preset.client_id,
        )
    else:
        connection = preset.connection()
    target = Target(
        url=connection.url,
        adapter=selected,
        model=preset.model,
        framework=preset.framework,
        request_usage=preset.request_usage,
        connection_id=name,
        session_id=preset.session_id,
        session_per_request=selected == "databricks-agent-runtime" and preset.session_id is None,
    )
    return target, validate_connection(target, connection)
