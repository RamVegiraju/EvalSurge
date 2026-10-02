"""Server-owned destination and credential bindings for a single-tenant service."""

import json
import os
from collections.abc import Callable
from urllib.parse import urlsplit

from pydantic import Field

from .models import Model, Target
from .providers import workspace_client


class Connection(Model):
    """Loaded from server configuration, never from an API request."""

    url: str
    auth: str = Field(default="none", pattern="^(none|bearer|databricks)$")
    token_env: str | None = None


def resolve_connection(target: Target) -> Connection:
    """Bind credentials to one exact URL; reject redirects and unapproved destinations."""
    url = str(target.url)
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise ValueError("Target URL must not contain credentials, query parameters, or fragments")
    if target.connection_id:
        connections = json.loads(os.getenv("BENCHMARK_CONNECTIONS", "{}"))
        if target.connection_id not in connections:
            raise ValueError("Unknown server connection_id")
        connection = Connection.model_validate(connections[target.connection_id])
        if url != str(Target(url=connection.url).url):
            raise ValueError("Target URL does not match the authorized connection")
        if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("Remote credential connections require HTTPS")
        return connection
    allowed = json.loads(os.getenv("BENCHMARK_ALLOWED_TARGETS", "[]"))
    if parsed.hostname not in {"127.0.0.1", "::1", "localhost"} and url not in allowed:
        raise ValueError("Target requires a server connection or BENCHMARK_ALLOWED_TARGETS entry")
    return Connection(url=url)


def authentication(connection: Connection) -> Callable[[], dict[str, str]]:
    """Create a refreshable header source; all failures stay in the request lifecycle."""
    if connection.auth == "databricks":
        workspace = workspace_client()
        if urlsplit(connection.url).scheme != "https" or (
            urlsplit(connection.url).netloc != urlsplit(workspace.config.host).netloc
        ):
            raise ValueError("Databricks credentials require the configured HTTPS workspace")
        return workspace.config.authenticate
    if connection.auth == "bearer":

        def bearer() -> dict[str, str]:
            token = os.environ.get(connection.token_env or "")
            if not token:
                raise ValueError("Connection credential is unavailable")
            return {"Authorization": "Bearer " + token}

        return bearer
    return dict
