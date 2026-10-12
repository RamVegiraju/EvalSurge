"""Immutable operator configuration with bounded loading and private serialization.

Loading inspects a supplied environment snapshot and an optional TOML/YAML file;
it does not authenticate, execute scorer code, create storage, or change globals.
Private configuration can be read explicitly by trusted runtime integrations, but
is excluded from ordinary model serialization and representations.
"""

import json
import os
import re
import tomllib
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .connections import Connection, app_workspace, validate_connection
from .models import RegisteredScorer, Target, TraceSource
from .providers import DEFAULT_FM_ENDPOINT

MAX_CONFIGURATION_BYTES = 1_000_000
ProtocolName = Literal[
    "openai-chat", "mlflow-agent-server", "http-json", "databricks-agent-runtime"
]


class SettingsError(ValueError):
    """A fixed safe configuration diagnostic, never a parser exception payload."""

    def __init__(self, code: str, message: str) -> None:
        """Retain a stable code and operator guidance without private input values."""
        self.code = code
        super().__init__(message)


class OperatorModel(BaseModel):
    """Reject unknown configuration and prevent mutation after validation."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


def _private(default: Any = None, **kwargs: Any) -> Any:
    """Declare private fields without depending on serialization callers to redact."""
    return Field(default=default, exclude=True, repr=False, **kwargs)


def _safe_url(value: str, *, host_only: bool = False) -> str:
    """Validate an HTTP destination without credentials, query strings, or fragments."""
    target = Target(url=value)
    parsed = urlsplit(str(target.url))
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Unsafe operator destination")
    if host_only and (parsed.scheme != "https" or parsed.path not in {"", "/"}):
        raise ValueError("Workspace must be an HTTPS origin")
    return str(target.url).rstrip("/") if host_only else str(target.url)


class ProviderSettings(OperatorModel):
    """Provider selection and hidden operator-owned endpoint/workspace references."""

    name: Literal["databricks", "openai"] = "databricks"
    planner_model: str | None = _private(max_length=512, min_length=1)
    judge_model: str | None = _private(max_length=512, min_length=1)
    profile: str | None = _private(max_length=512, min_length=1)
    host: str | None = _private(max_length=2048, min_length=1)

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str | None) -> str | None:
        """Require an explicitly configured workspace to be a safe HTTPS origin."""
        return _safe_url(value, host_only=True) if value else None

    @field_validator("judge_model")
    @classmethod
    def validate_judge_model(cls, value: str | None) -> str | None:
        """Retain legacy Databricks URIs while rejecting other judge providers."""
        if value and ":/" in value and not value.startswith("databricks:/"):
            raise ValueError("Catalog judges require a Databricks endpoint")
        if value == "databricks:/":
            raise ValueError("Catalog judges require an endpoint")
        return value

    @property
    def planner_endpoint(self) -> str | None:
        """Return the configured endpoint or the legacy Databricks planner default."""
        return self.planner_model or (DEFAULT_FM_ENDPOINT if self.name == "databricks" else None)

    @property
    def judge_endpoint(self) -> str | None:
        """Return the private direct-Databricks endpoint without resolving credentials."""
        if self.judge_model:
            return self.judge_model.removeprefix("databricks:/")
        return DEFAULT_FM_ENDPOINT if self.profile or self.host else None


class ConnectionSettings(OperatorModel):
    """Registered targets; DurableAgentServer is the current App protocol default.

    Legacy MLflow AgentServer deployments must explicitly select
    ``protocols=("mlflow-agent-server",)`` for their ``/responses`` endpoint.
    Protocol order determines the operator default; hosting does not infer which
    server an existing App runs. Only protocol names are ordinary public metadata.
    """

    kind: Literal["http", "databricks-app"] = "http"
    url: str | None = _private(min_length=1, max_length=2048)
    auth: Literal["none", "bearer", "databricks"] = _private("none")
    token_env: str | None = _private(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,255}$")
    app_name: str | None = _private(pattern=r"^[a-z][a-z0-9-]{0,29}$")
    profile: str | None = _private(min_length=1, max_length=512)
    app_auth: Literal["profile", "app-runtime"] = _private("profile")
    workspace: str | None = _private(min_length=1, max_length=2048)
    workspace_id: str | None = _private(pattern=r"^[1-9][0-9]{0,19}$")
    runner_app: str | None = _private(pattern=r"^[a-z][a-z0-9-]{0,29}$")
    client_id: str | None = _private(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    protocols: tuple[ProtocolName, ...] = Field(default=(), max_length=4)
    model: str = _private("agent", min_length=1, max_length=512)
    framework: Literal["langgraph", "openai-agents"] | None = _private()
    request_usage: bool = True
    session_id: str | None = _private(min_length=1, max_length=128)

    @field_validator("workspace")
    @classmethod
    def validate_workspace(cls, value: str | None) -> str | None:
        """Require native App workspace metadata to be a fixed HTTPS origin."""
        return app_workspace(value) if value is not None else None

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        """Validate credential transport and distinguish App lookup from HTTP URLs."""
        if len(set(self.protocols)) != len(self.protocols):
            raise ValueError("Duplicate target protocols")
        if self.kind == "databricks-app":
            native = (self.workspace, self.runner_app, self.client_id)
            if (
                not self.app_name
                or self.url
                or self.token_env
                or (
                    self.app_auth == "profile"
                    and (not self.profile or any(native) or self.workspace_id is not None)
                )
                or (
                    self.app_auth == "app-runtime" and (self.profile is not None or not all(native))
                )
            ):
                raise ValueError("App targets require one explicit operator identity binding")
            if self.auth != "none":
                raise ValueError("App authentication is SDK-owned")
            if not self.protocols:
                object.__setattr__(self, "protocols", ("databricks-agent-runtime",))
            if any(
                p not in {"databricks-agent-runtime", "mlflow-agent-server"} for p in self.protocols
            ):
                raise ValueError("Unsupported App protocol")
        else:
            if (
                not self.url
                or self.app_name
                or self.profile
                or self.app_auth != "profile"
                or any((self.workspace, self.runner_app, self.client_id))
                or self.workspace_id is not None
            ):
                raise ValueError("HTTP targets require a destination")
            normalized = _safe_url(self.url)
            binding = Connection(url=normalized, auth=self.auth, token_env=self.token_env)
            validate_connection(Target(url=normalized), binding)
            if self.token_env and self.auth != "bearer":
                raise ValueError("Only bearer bindings use credential references")
            object.__setattr__(self, "url", normalized)
        return self

    def connection(self) -> Connection:
        """Return a detached HTTP worker binding without reading any credential.

        Returns:
            An exact URL/authentication reference owned by the caller.

        Raises:
            SettingsError: The target requires App resolution before binding.
        """
        if self.kind != "http":
            raise SettingsError(
                "configuration_app_resolution", "App configuration needs resolution."
            )
        return Connection(url=self.url, auth=self.auth, token_env=self.token_env)

    def operator_record(self) -> dict[str, Any]:
        """Return private runtime configuration; never publish or persist this mapping."""
        fields = type(self).model_fields
        return {
            name: list(value) if isinstance(value, tuple) else value
            for name in fields
            if (value := getattr(self, name)) is not None
        }


class ScorerSettings(OperatorModel):
    """Exact trusted scorer references, with registry identities kept private."""

    name: str = _private(..., min_length=1, max_length=128)
    experiment_id: str = _private(..., min_length=1, max_length=128)
    version: int = Field(ge=1)
    required_fields: tuple[Literal["inputs", "outputs", "expectations", "trace"], ...] = (
        "inputs",
        "outputs",
    )
    description: str = _private("", max_length=2000)

    def reference(self, alias: str) -> RegisteredScorer:
        """Return a detached trusted reference without loading native scorer code."""
        return RegisteredScorer(
            alias=alias,
            name=self.name,
            experiment_id=self.experiment_id,
            version=self.version,
            required_fields=list(self.required_fields),
            description=self.description,
            definition_hash="not-resolved",
        )


class TraceSettings(OperatorModel):
    """Opt-in static trace scope and bounded collection limits."""

    enabled: bool = False
    experiment_ids: tuple[str, ...] = _private((), max_length=10)
    max_traces: int = Field(default=100, ge=1, le=200)
    max_spans: int = Field(default=250, ge=1, le=1000)

    @field_validator("experiment_ids")
    @classmethod
    def validate_experiments(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject blank or unbounded tracking identifiers."""
        if any(not item or len(item) > 128 for item in value):
            raise ValueError("Invalid authorized experiment identifier")
        return value


class Settings(OperatorModel):
    """Validated private configuration; missing optional readiness is diagnosed later."""

    artifact_dir: Path = _private(Path("artifacts"))
    provider: ProviderSettings = Field(default_factory=ProviderSettings)
    tracing: TraceSettings = Field(default_factory=TraceSettings)
    connections: Mapping[str, ConnectionSettings] = Field(
        default_factory=dict, exclude=True, repr=False
    )
    scorers: Mapping[str, ScorerSettings] = Field(default_factory=dict, exclude=True, repr=False)
    allowed_targets: tuple[str, ...] = _private((), max_length=1000)
    tracking_uri: str | None = _private(min_length=1, max_length=2048)
    api_key: str | None = _private(min_length=1, max_length=4096)

    @field_validator("connections", "scorers")
    @classmethod
    def freeze_registry(cls, value: Mapping[str, Any], info: Any) -> Mapping[str, Any]:
        """Bound public aliases and freeze registries independently of input mappings."""
        maximum = 20 if info.field_name == "scorers" else 1000
        if len(value) > maximum or any(not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", k) for k in value):
            raise ValueError("Invalid configuration registry")
        return MappingProxyType(dict(value))

    @field_validator("allowed_targets")
    @classmethod
    def validate_allowed_targets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Normalize each exact unauthenticated destination without inferring patterns."""
        return tuple(_safe_url(item) for item in value)

    @field_validator("tracking_uri")
    @classmethod
    def validate_tracking_uri(cls, value: str | None) -> str | None:
        """Prevent credentials from entering private tracking references and artifacts."""
        if value:
            parsed = urlsplit(value)
            if parsed.username or parsed.password or parsed.fragment or parsed.query:
                raise ValueError("Unsafe tracking destination")
        return value

    @property
    def effective_tracking_uri(self) -> str | None:
        """Resolve the legacy Databricks profile URI without SDK or tracking access."""
        if self.tracking_uri == "databricks":
            return f"databricks://{self.provider.profile}" if self.provider.profile else None
        return self.tracking_uri

    @property
    def trace_experiment_ids(self) -> tuple[str, ...]:
        """Return the private authorized trace scope."""
        return self.tracing.experiment_ids

    def trace_source(self) -> TraceSource | None:
        """Return a detached runtime scope or None for disabled/incomplete tracing."""
        if (
            not self.tracing.enabled
            or not self.effective_tracking_uri
            or not self.trace_experiment_ids
        ):
            return None
        return TraceSource(
            tracking_uri=self.effective_tracking_uri,
            experiment_ids=list(self.trace_experiment_ids),
            max_traces=self.tracing.max_traces,
            max_spans=self.tracing.max_spans,
        )

    def to_environment(self, environ: Mapping[str, str] | None = None) -> dict[str, str]:
        """Create a private detached legacy-runtime snapshot without changing globals.

        Args:
            environ: Operator environment to preserve, including bearer credentials;
                None copies the current process environment.

        Returns:
            Private values for task-local configuration and worker inheritance.
            NEVER serialize, log, export, or persist this mapping.

        Side Effects:
            None. Credential references are retained without resolving SDK secrets.
        """
        result = dict(os.environ if environ is None else environ)
        # The resulting mapping is a complete snapshot, not another file-loader
        # instruction. Runtime consumers must remain independent of file changes.
        result.pop("BENCHMARK_CONFIG", None)
        result.update(
            BENCHMARK_ARTIFACT_DIR=str(self.artifact_dir),
            BENCHMARK_CONNECTIONS=json.dumps(
                {alias: binding.operator_record() for alias, binding in self.connections.items()}
            ),
            BENCHMARK_ALLOWED_TARGETS=json.dumps(self.allowed_targets),
            BENCHMARK_LLM_PROVIDER=self.provider.name,
            BENCHMARK_TRACE_ENABLED=str(self.tracing.enabled).lower(),
            BENCHMARK_TRACE_EXPERIMENT_IDS=json.dumps(self.trace_experiment_ids),
            BENCHMARK_MAX_TRACES=str(self.tracing.max_traces),
            BENCHMARK_MAX_SPANS=str(self.tracing.max_spans),
            BENCHMARK_SCORERS=json.dumps(
                {
                    alias: reference.reference(alias).model_dump(
                        exclude={"alias", "definition_hash"}
                    )
                    for alias, reference in self.scorers.items()
                }
            ),
        )
        for key, value in {
            "BENCHMARK_PLANNER_MODEL": self.provider.planner_endpoint,
            "BENCHMARK_JUDGE_MODEL": self.provider.judge_endpoint,
            "DATABRICKS_CONFIG_PROFILE": self.provider.profile,
            "DATABRICKS_HOST": self.provider.host,
            "MLFLOW_TRACKING_URI": self.tracking_uri,
            "BENCHMARK_API_KEY": self.api_key,
        }.items():
            if value is None:
                result.pop(key, None)
            else:
                result[key] = value
        return result


def _bounded_json(value: str) -> Any:
    """Apply byte limits before parsing an operator-owned JSON environment value."""
    if len(value.encode("utf-8")) > MAX_CONFIGURATION_BYTES:
        raise SettingsError("configuration_limit", "Operator configuration exceeds the size limit.")
    return json.loads(value)


def _yaml_document(contents: str) -> Any:
    """Load optional YAML with no executable tags, aliases, anchors, or duplicate keys."""
    try:
        import yaml
    except ImportError:
        raise SettingsError(
            "configuration_yaml_dependency", "YAML configuration requires PyYAML; use TOML instead."
        ) from None

    class UniqueSafeLoader(yaml.SafeLoader):
        """Retain safe constructors while rejecting ambiguous mapping keys."""

        def construct_mapping(self, node: Any, deep: bool = False) -> Any:
            """Build a mapping only after verifying unique scalar keys."""
            keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
            if len(set(keys)) != len(keys):
                raise ValueError("Duplicate configuration keys")
            return super().construct_mapping(node, deep=deep)

    try:
        for token in yaml.scan(contents):
            if isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken)):
                raise ValueError("YAML references are not supported")
        return yaml.load(contents, Loader=UniqueSafeLoader)
    except (yaml.YAMLError, TypeError, ValueError):
        raise SettingsError("configuration_file_invalid", "Invalid YAML configuration.") from None


def _read_document(path: Path) -> dict[str, Any]:
    """Read at most one bounded operator file, returning a non-executed mapping."""
    if path.suffix.lower() not in {".toml", ".yaml", ".yml"}:
        raise SettingsError("configuration_file_type", "Use TOML or YAML operator configuration.")
    with path.open("rb") as stream:
        contents = stream.read(MAX_CONFIGURATION_BYTES + 1)
    if len(contents) > MAX_CONFIGURATION_BYTES:
        raise SettingsError("configuration_limit", "Operator configuration exceeds the size limit.")
    text = contents.decode("utf-8")
    document = tomllib.loads(text) if path.suffix.lower() == ".toml" else _yaml_document(text)
    if not isinstance(document, dict):
        raise ValueError("Configuration must be a mapping")
    return document


def load_settings(
    config_path: str | Path | None = None, *, environ: Mapping[str, str] | None = None
) -> Settings:
    """Load operator defaults, a file, then explicit per-field environment overrides.

    Args:
        config_path: Explicit file path; takes precedence over BENCHMARK_CONFIG.
        environ: Isolated environment snapshot, or the current process environment.

    Returns:
        Immutable settings whose normal serialization omits private values.

    Raises:
        SettingsError: Malformed, unsupported, oversized, or invalid configuration.
            Errors never include file paths, contents, or raw parser messages.

    Side Effects:
        Reads at most one bounded file. Does not mutate the supplied environment,
        authenticate, read profile files, execute scorers, or create directories.
    """
    environment = dict(os.environ if environ is None else environ)
    try:
        selected = config_path if config_path is not None else environment.get("BENCHMARK_CONFIG")
        document = _read_document(Path(selected)) if selected is not None else {}
        document = dict(document)
        for section in ("provider", "tracing"):
            if section in document:
                if not isinstance(document[section], dict):
                    raise ValueError("Configuration section must be a mapping")
                document[section] = dict(document[section])
        fields = {
            "BENCHMARK_ARTIFACT_DIR": (None, "artifact_dir"),
            "BENCHMARK_LLM_PROVIDER": ("provider", "name"),
            "BENCHMARK_PLANNER_MODEL": ("provider", "planner_model"),
            "BENCHMARK_JUDGE_MODEL": ("provider", "judge_model"),
            "DATABRICKS_CONFIG_PROFILE": ("provider", "profile"),
            "DATABRICKS_HOST": ("provider", "host"),
            "MLFLOW_TRACKING_URI": (None, "tracking_uri"),
            "BENCHMARK_API_KEY": (None, "api_key"),
            "BENCHMARK_TRACE_ENABLED": ("tracing", "enabled"),
            "BENCHMARK_MAX_TRACES": ("tracing", "max_traces"),
            "BENCHMARK_MAX_SPANS": ("tracing", "max_spans"),
        }
        for key, (section, field) in fields.items():
            if key in environment:
                value: Any = environment[key]
                if key == "BENCHMARK_TRACE_ENABLED":
                    if value.lower() not in {"true", "false"}:
                        raise ValueError("Trace enablement must be true or false")
                    value = value.lower() == "true"
                destination = document.setdefault(section, {}) if section else document
                destination[field] = value
        for key, field, expected in (
            ("BENCHMARK_CONNECTIONS", "connections", dict),
            ("BENCHMARK_SCORERS", "scorers", dict),
            ("BENCHMARK_ALLOWED_TARGETS", "allowed_targets", list),
        ):
            if key in environment:
                value = _bounded_json(environment[key])
                if not isinstance(value, expected):
                    raise ValueError("Configuration registry has the wrong shape")
                document[field] = value
        tracing = document.setdefault("tracing", {})
        if "BENCHMARK_TRACE_EXPERIMENT_IDS" in environment:
            experiments = _bounded_json(environment["BENCHMARK_TRACE_EXPERIMENT_IDS"])
            if not isinstance(experiments, list):
                raise ValueError("Trace experiments must be a list")
            tracing["experiment_ids"] = experiments
        if not tracing.get("experiment_ids") and environment.get("MLFLOW_EXPERIMENT_ID"):
            tracing["experiment_ids"] = [environment["MLFLOW_EXPERIMENT_ID"]]
        return Settings.model_validate(document)
    except SettingsError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError, ValidationError):
        raise SettingsError(
            "configuration_invalid", "Invalid operator configuration. Check the configured fields."
        ) from None
