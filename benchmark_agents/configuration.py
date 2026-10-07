"""Task-local operator configuration without process environment mutation."""

import os
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar

_environment: ContextVar[Mapping[str, str] | None] = ContextVar(
    "operator_environment", default=None
)

# Destination, identity, and authentication-routing overrides from the supported
# Databricks SDK's Config metadata. Several routing attributes have no auth label;
# review those explicitly rather than treating unlabeled inputs as profile-safe.
# Keep doctor independent of SDK imports, credential resolution, and profile reads.
SDK_PROFILE_OVERRIDE_ENV = frozenset(
    {
        "DATABRICKS_HOST",
        "DATABRICKS_ACCOUNT_ID",
        "DATABRICKS_WORKSPACE_ID",
        "DATABRICKS_GROUP_ID",
        "DATABRICKS_CLOUD",
        "DATABRICKS_DISCOVERY_URL",
        "DATABRICKS_TOKEN_AUDIENCE",
        "DATABRICKS_TOKEN",
        "DATABRICKS_OIDC_TOKEN_ENV",
        "DATABRICKS_OIDC_TOKEN_FILEPATH",
        "DATABRICKS_OIDC_TOKEN_FILE",
        "DATABRICKS_USERNAME",
        "DATABRICKS_PASSWORD",
        "DATABRICKS_CLIENT_ID",
        "DATABRICKS_CLIENT_SECRET",
        "DATABRICKS_GOOGLE_SERVICE_ACCOUNT",
        "GOOGLE_CREDENTIALS",
        "DATABRICKS_AZURE_RESOURCE_ID",
        "ARM_USE_MSI",
        "ARM_CLIENT_SECRET",
        "ARM_CLIENT_ID",
        "ARM_TENANT_ID",
        "ARM_ENVIRONMENT",
        "DATABRICKS_AUTH_TYPE",
        "DATABRICKS_METADATA_SERVICE_URL",
    }
)


def profile_override_present(values: Mapping[str, str], *, extra_names: Iterable[str] = ()) -> bool:
    """Inspect only presence of SDK inputs that can override a selected identity.

    Args:
        values: Explicit operator environment snapshot; never modified or exported.
        extra_names: Runtime SDK metadata names for forward compatibility; the
            configuration-only doctor uses the reviewed static set.

    Returns:
        Whether any nonempty destination/identity/authentication-routing override
        is configured.
        Profile and configuration-file selectors remain allowed. No SDK import,
        credential resolution, profile-file read, or network call occurs.
    """
    return any(values.get(name) for name in SDK_PROFILE_OVERRIDE_ENV.union(extra_names))


def profile_config_file_conflict(
    actual_env: Mapping[str, str], scoped_env: Mapping[str, str]
) -> bool:
    """Detect different SDK and token-subprocess profile-file selectors without I/O.

    Args:
        actual_env: Process environment inherited by SDK authentication subprocesses.
        scoped_env: Operator snapshot selected for the benchmark and its worker.

    Returns:
        Whether lexically normalized configuration-file paths differ. Missing
        selectors use the SDK default. Expansion and absolute-path normalization
        do not read files or follow symlinks; callers should use the same selector
        for alternate names of a file. Private paths are never returned.
    """
    actual = actual_env.get("DATABRICKS_CONFIG_FILE") or "~/.databrickscfg"
    scoped = scoped_env.get("DATABRICKS_CONFIG_FILE") or "~/.databrickscfg"
    return os.path.abspath(os.path.expanduser(actual)) != os.path.abspath(
        os.path.expanduser(scoped)
    )


def environment() -> Mapping[str, str]:
    """Return private task settings, or the legacy ambient environment.

    The mapping can contain secrets. Callers must never serialize or persist it.
    Async tasks and thread-offloaded work inherit the current context.
    """
    configured = _environment.get()
    return os.environ if configured is None else configured


def getenv(name: str, default: str | None = None) -> str | None:
    """Read one operator setting without changing process-global state."""
    return environment().get(name, default)


@contextmanager
def configured_environment(values: Mapping[str, str] | None) -> Iterator[None]:
    """Scope private configuration to owned work and restore the prior context.

    Args:
        values: Detached operator snapshot, or None for legacy environment reads.

    Yields:
        Nothing; tasks started in this scope inherit its configuration.
    """
    token = _environment.set(values)
    try:
        yield
    finally:
        _environment.reset(token)
