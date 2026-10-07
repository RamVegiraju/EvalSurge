"""Operator-owned target resolution; Databricks discovery never invokes an agent."""

import os
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from .configuration import environment, profile_config_file_conflict, profile_override_present
from .connections import Connection, validate_connection
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
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise TargetResolutionError("Registered App has no valid deployment URL")
    return url.rstrip("/")


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
    if not connection.profile or not connection.app_name:
        raise TargetResolutionError("Registered App requires an explicit operator profile")
    workspace, origin = _workspace_app(connection.profile, connection.app_name)
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
    sessions are isolated per attempt unless an operator explicitly fixes one;
    fixed sessions serialize invocation ordering and retain target conversation state.
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
        if not preset.profile or not preset.app_name:
            raise TargetResolutionError("Registered App requires an explicit operator profile")
        _, origin = _workspace_app(preset.profile, preset.app_name)
        path = "/api/invocations" if selected == "databricks-agent-runtime" else "/responses"
        connection = Connection(
            url=origin + path,
            auth="databricks-app",
            profile=preset.profile,
            app_name=preset.app_name,
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
