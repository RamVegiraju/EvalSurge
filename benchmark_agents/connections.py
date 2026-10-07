"""Server-owned destination and credential bindings for a single-tenant service."""

import json
from collections.abc import Callable
from urllib.parse import urlsplit

from pydantic import Field

from .configuration import environment, getenv
from .models import Model, Target
from .providers import workspace_client


class Connection(Model):
    """Loaded from server configuration, never from an API request."""

    url: str
    auth: str = Field(default="none", pattern="^(none|bearer|databricks|databricks-app)$")
    token_env: str | None = None
    profile: str | None = Field(default=None, min_length=1, max_length=512)
    app_name: str | None = Field(default=None, pattern=r"^[a-z0-9-]{1,30}$")


def validate_connection(target: Target, connection: Connection) -> Connection:
    """Copy an operator binding after exact URL and credential transport validation.

    Args:
        target: Authorized endpoint; credentials/query/fragment are forbidden.
        connection: Local operator configuration, never caller-supplied REST data.

    Returns:
        A detached binding with no resolved secret values.

    Raises:
        ValueError: Destination differs or remote credential transport is not HTTPS.
    """
    url = str(target.url)
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise ValueError("Target URL must not contain credentials, query parameters, or fragments")
    try:
        bound_url = str(Target(url=connection.url).url)
    except ValueError:
        raise ValueError("Invalid operator connection configuration") from None
    if url != bound_url:
        raise ValueError("Target URL does not match the authorized connection")
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("Remote credential connections require HTTPS")
    if connection.auth == "databricks-app" and (
        not connection.profile
        or not connection.app_name
        or parsed.scheme != "https"
        or parsed.path not in {"/api/invocations", "/responses"}
    ):
        raise ValueError("Invalid operator Databricks App binding")
    return connection.model_copy(deep=True)


def resolve_connection(target: Target) -> Connection:
    """Resolve an endpoint against the operator's destination policy.

    Args:
        target: Endpoint URL and optional server-owned connection identifier.

    Returns:
        A credential binding from BENCHMARK_CONNECTIONS, or an unauthenticated
        binding for a loopback or explicitly allowlisted URL. No secrets are read.

    Raises:
        ValueError: The URL contains forbidden components, is not authorized,
            differs from its connection, or uses remote credentialed HTTP.
    """
    url = str(target.url)
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise ValueError("Target URL must not contain credentials, query parameters, or fragments")
    if target.connection_id:
        try:
            connections = json.loads(getenv("BENCHMARK_CONNECTIONS", "{}"))
            if not isinstance(connections, dict):
                raise ValueError
            if target.connection_id not in connections:
                raise ValueError("Unknown server connection_id")
            record = connections[target.connection_id]
            if isinstance(record, dict) and any(
                key in record for key in ("kind", "protocols", "model", "request_usage")
            ):
                from .settings import ConnectionSettings

                preset = ConnectionSettings.model_validate(record)
                if preset.protocols and target.adapter not in preset.protocols:
                    raise ValueError("Target protocol is not authorized for the connection")
                connection = preset.connection()
            else:
                connection = Connection.model_validate(record)
        except ValueError:
            raise ValueError("Invalid operator connection configuration") from None
        return validate_connection(target, connection)
    allowed = json.loads(getenv("BENCHMARK_ALLOWED_TARGETS", "[]"))
    if parsed.hostname not in {"127.0.0.1", "::1", "localhost"} and url not in allowed:
        raise ValueError("Target requires a server connection or BENCHMARK_ALLOWED_TARGETS entry")
    return Connection(url=url)


def authentication(connection: Connection) -> Callable[[], dict[str, str]]:
    """Create a header source that resolves credentials when a request starts.

    Args:
        connection: Operator-owned destination and authentication settings.

    Returns:
        A callable producing fresh headers. Bearer tokens are read on each call;
        Databricks authentication delegates refresh to the SDK.

    Raises:
        ValueError: Databricks credentials would target a different workspace,
            SDK settings are absent, or a bearer credential is unavailable.
            Bearer credential errors occur when the returned callable is called.
            App discovery/OAuth failures are fixed safe TargetResolutionErrors.
    """
    if connection.auth == "databricks-app":
        # Lazy import prevents the operator registry from becoming a models/settings cycle.
        from .target_resolver import app_authentication

        return app_authentication(connection)
    if connection.auth == "databricks":
        workspace = workspace_client()
        if urlsplit(connection.url).scheme != "https" or (
            urlsplit(connection.url).netloc != urlsplit(workspace.config.host).netloc
        ):
            raise ValueError("Databricks credentials require the configured HTTPS workspace")
        return workspace.config.authenticate
    if connection.auth == "bearer":

        def bearer() -> dict[str, str]:
            """Read the configured token at dispatch time, without caching it."""
            token = environment().get(connection.token_env or "")
            if not token:
                raise ValueError("Connection credential is unavailable")
            return {"Authorization": "Bearer " + token}

        return bearer
    return dict
