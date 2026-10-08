"""Dependency-light factories; local execution explicitly needs the server extra."""

from collections.abc import Mapping
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

from .remote import RemoteClient, TypedRemoteClient

if TYPE_CHECKING:
    from benchmark_agents.settings import Settings

    from .client import Agent
    from .local import AsyncClient, Client

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
    """Direct Python execution by default; remote execution is an optional adapter."""

    def __new__(
        cls,
        *,
        artifact_dir: str | Path | None = None,
        targets: Mapping[str, "Agent"] | None = None,
        settings: "Settings | None" = None,
    ) -> "Client":
        """Create the direct context without opening artifacts, auth, or network.

        Arguments match local(). Enter the returned context to acquire ownership.
        """
        return cls.local(artifact_dir=artifact_dir, targets=targets, settings=settings)

    @staticmethod
    def remote(
        base_url: str, *, api_key: str | None = None, typed: bool = False, **kwargs: Any
    ) -> RemoteClient | TypedRemoteClient:
        """Create a remote HTTP client without loading server/framework dependencies.

        Args:
            base_url: Authorized HTTPS origin, or HTTP loopback for local tests.
            api_key: Optional in-memory service key; never included in URLs.
            typed: Opt into the unified typed status/result/report contract.
                False preserves existing dictionary return values and wait defaults.
            **kwargs: RemoteClient timeout, transport, and polling options.

        Returns:
            Unopened client. Enter its context to own and close HTTP resources.
            The API host, not this caller, remains the load generator.
        """
        if type(typed) is not bool:
            raise TypeError("typed must be a boolean")
        return (TypedRemoteClient if typed else RemoteClient)(base_url, api_key=api_key, **kwargs)

    @staticmethod
    def local(
        *,
        artifact_dir: str | Path | None = None,
        targets: Mapping[str, "Agent"] | None = None,
        settings: "Settings | None" = None,
    ) -> "Client":
        """Create a sync local context, deferring server imports until this call.

        Args:
            artifact_dir: Protected persistent POSIX storage, not shared by owners.
                Explicit values override settings; omission uses Settings.artifact_dir
                from supplied or loaded operator settings. Without configuration,
                the legacy "artifacts" default remains.
            targets: Detached operator aliases to HTTP/App bindings; no discovery here.
            settings: Optional immutable operator configuration, outside requests.

        Returns:
            Unopened context; enter it before starting work. This machine is the
            load generator, and entering acquires exclusive storage ownership.

        Raises:
            MissingServerDependenciesError: Install the server extra before use.
        """
        _local_module()
        return import_module("evalsurge.local").Client(
            artifact_dir, targets=targets, settings=settings
        )

    @staticmethod
    def local_async(
        *,
        artifact_dir: str | Path | None = None,
        targets: Mapping[str, "Agent"] | None = None,
        settings: "Settings | None" = None,
    ) -> "AsyncClient":
        """Create a native-async context owned by its eventual opening event loop.

        Args:
            artifact_dir: Protected persistent POSIX storage, not shared by owners.
                Precedence matches local(): explicit value, supplied or loaded
                operator settings, then the legacy "artifacts" default.
            targets: Detached operator aliases to HTTP/App bindings; no discovery here.
            settings: Optional immutable operator configuration, outside requests.

        Returns:
            Unopened context; traffic location and ownership match local().

        Raises:
            MissingServerDependenciesError: Install the server extra before use.
        """
        _local_module()
        return import_module("evalsurge.local").AsyncClient(
            artifact_dir, targets=targets, settings=settings
        )
