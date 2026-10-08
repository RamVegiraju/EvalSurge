"""Dependency-light factories; local execution explicitly needs the server extra."""

from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

from .remote import RemoteClient

if TYPE_CHECKING:
    from .client import AsyncClient, Client

_SERVER_IMPORTS = (
    "fastapi",
    "uvicorn",
    "openai",
    "mlflow",
    "databricks.sdk",
    "locust",
    "dotenv",
    "requests",
    "gevent",
)


class MissingServerDependenciesError(ImportError):
    """The remote-only installation cannot execute a local benchmark/server."""


def _local_module() -> ModuleType:
    """Load local execution only after its explicit dependencies are available.

    Returns:
        Local client module; importing it does not acquire artifacts or send traffic.

    Raises:
        MissingServerDependenciesError: A server dependency is absent. The fixed
            message identifies the installation option, not local configuration.
        ImportError: An installed dependency has an unrelated import failure.

    This checks availability, not version compatibility or provider readiness.
    """
    try:
        available = all(find_spec(name) is not None for name in _SERVER_IMPORTS)
    except ModuleNotFoundError:
        available = False
    if not available:
        raise MissingServerDependenciesError(
            "Local benchmarking requires server dependencies; install 'evalsurge[server]' "
            "(or 'evalsurge[agents]' for framework examples)."
        )
    return import_module("evalsurge.client")


class EvalSurge:
    """Remote HTTP access or explicit local ownership of the one Locust engine."""

    @staticmethod
    def remote(base_url: str, *, api_key: str | None = None, **kwargs: Any) -> RemoteClient:
        """Create a remote HTTP client without loading server/framework dependencies.

        Args:
            base_url: Authorized HTTPS origin, or HTTP loopback for local tests.
            api_key: Optional in-memory service key; never included in URLs.
            **kwargs: RemoteClient timeout, transport, and polling options.

        Returns:
            Unopened client. Enter its context to own and close HTTP resources.
            The API host, not this caller, remains the load generator.
        """
        return RemoteClient(base_url, api_key=api_key, **kwargs)

    @staticmethod
    def local(*, artifact_dir: str | Path = "artifacts") -> "Client":
        """Create a sync local context, deferring server imports until this call.

        Args:
            artifact_dir: Protected persistent POSIX storage, not shared by owners.

        Returns:
            Unopened context; enter it before starting work. This machine is the
            load generator, and entering acquires exclusive storage ownership.

        Raises:
            MissingServerDependenciesError: Install the server extra before use.
        """
        return _local_module().Client(artifact_dir)

    @staticmethod
    def local_async(*, artifact_dir: str | Path = "artifacts") -> "AsyncClient":
        """Create a native-async context owned by its eventual opening event loop.

        Args:
            artifact_dir: Protected persistent POSIX storage, not shared by owners.

        Returns:
            Unopened context; traffic location and ownership match local().

        Raises:
            MissingServerDependenciesError: Install the server extra before use.
        """
        return _local_module().AsyncClient(artifact_dir)
