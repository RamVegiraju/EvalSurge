"""Secret-free capability documents and read-only configuration diagnostics.

Configured readiness describes static prerequisites, never verified authentication,
target health, provider compatibility, storage ownership, or runtime quality.
These functions do not load SDK clients, scorer definitions, tracking stores, or
network destinations and never create an artifact directory.
"""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field

from .adapters import JSON_RESPONSE_LIMIT
from .configuration import profile_config_file_conflict, profile_override_present
from .limits import MAX_REQUEST_BYTES
from .settings import OperatorModel, ProtocolName, Settings, SettingsError, load_settings

Readiness = Literal["configured", "needs_configuration", "disabled"]


class TargetCapability(OperatorModel):
    """Explicit public target alias and its declared invocation protocols."""

    name: str
    protocols: tuple[ProtocolName, ...] = ()


class CapabilityLimits(OperatorModel):
    """Current local workload and transport bounds, independent of target capacity."""

    max_concurrent_users: int = 100
    max_requests: int = 10_000
    max_duration_seconds: float = 3600
    max_timeout_seconds: float = 120
    max_cases: int = 1000
    max_request_bytes: int = MAX_REQUEST_BYTES
    max_json_response_bytes: int = JSON_RESPONSE_LIMIT
    max_active_runs: int = 1


class EvaluationCapability(OperatorModel):
    """Static planning/judging readiness and reviewed executable scorer identifiers."""

    default_mode: Literal["off"] = "off"
    planner: Readiness
    catalog_judges: Readiness
    executable_catalog_scorers: tuple[str, ...] = ("relevance", "correctness", "safety")
    registered_scorers: tuple[str, ...] = ()
    answer_evaluation_requires_traces: Literal[False] = False
    trace_required_judges_require_correlated_probe: Literal[True] = True
    captured_answers_only: Literal[True] = True


class TraceCapability(OperatorModel):
    """Static tracing readiness and public collection budgets without private scope."""

    readiness: Readiness
    max_traces: int
    max_spans: int
    optional_for_load_and_answer_evaluation: Literal[True] = True


class Capabilities(OperatorModel):
    """Public metadata with no destinations, credential references, or SDK state."""

    api_version: Literal["v2"] = "v2"
    targets: tuple[TargetCapability, ...] = ()
    protocols: tuple[ProtocolName, ...]
    limits: CapabilityLimits = Field(default_factory=CapabilityLimits)
    evaluation: EvaluationCapability
    tracing: TraceCapability
    runtime_verified: Literal[False] = False


class DiagnosticCheck(OperatorModel):
    """Fixed safe operator guidance; raw exceptions and private names are excluded."""

    code: str
    status: Literal["ok", "warning", "error"]
    message: str


class DoctorReport(OperatorModel):
    """Read-only findings about static prerequisites, never a live health result."""

    ok: bool
    configuration_only: Literal[True] = True
    checks: tuple[DiagnosticCheck, ...]
    capabilities: Capabilities | None


def build_capabilities(
    settings: Settings, *, environ: Mapping[str, str] | None = None
) -> Capabilities:
    """Produce only reviewed public metadata from a validated operator snapshot.

    Args:
        settings: Validated immutable configuration; private fields remain private.
        environ: Environment for credential-presence checks only, or process values.

    Returns:
        Static readiness and bounds. No SDK credential resolution, provider calls,
        trace retrieval, target traffic, scorer loading, or filesystem mutation.
    """
    environment = os.environ if environ is None else environ
    workspace_configured = bool(settings.provider.profile or settings.provider.host)
    planner_configured = (
        workspace_configured and bool(settings.provider.planner_endpoint)
        if settings.provider.name == "databricks"
        else bool(settings.provider.planner_model and environment.get("OPENAI_API_KEY"))
    )
    catalog_configured = workspace_configured and bool(settings.provider.judge_endpoint)
    tracing: Readiness = "disabled"
    if settings.tracing.enabled:
        tracing = (
            "configured"
            if settings.effective_tracking_uri and settings.trace_experiment_ids
            else "needs_configuration"
        )
    protocols: tuple[ProtocolName, ...] = ("openai-chat", "mlflow-agent-server", "http-json")
    if any("databricks-agent-runtime" in item.protocols for item in settings.connections.values()):
        protocols += ("databricks-agent-runtime",)
    return Capabilities(
        targets=tuple(
            TargetCapability(name=alias, protocols=binding.protocols)
            for alias, binding in sorted(settings.connections.items())
        ),
        protocols=protocols,
        evaluation=EvaluationCapability(
            planner="configured" if planner_configured else "needs_configuration",
            catalog_judges="configured" if catalog_configured else "needs_configuration",
            registered_scorers=tuple(sorted(settings.scorers)),
        ),
        tracing=TraceCapability(
            readiness=tracing,
            max_traces=settings.tracing.max_traces,
            max_spans=settings.tracing.max_spans,
        ),
    )


def startup_diagnostics(
    settings: Settings, *, environ: Mapping[str, str] | None = None
) -> DoctorReport:
    """Inspect static dependencies without initializing storage or external clients.

    Args:
        settings: Validated operator-owned configuration.
        environ: Isolated environment for bearer/OpenAI credential presence; None
            reads process values without modifying them.

    Returns:
        Findings with safe fixed guidance. Optional absent evaluation/tracing are
        warnings; explicitly enabled features with missing dependencies are errors.
        A successful result does not verify credentials, disk ownership, or health.
    """
    environment = os.environ if environ is None else environ
    capabilities = build_capabilities(settings, environ=environment)
    checks: list[DiagnosticCheck] = []

    def add(code: str, status: Literal["ok", "warning", "error"], message: str) -> None:
        """Add only fixed reviewed messages, with no raw operator or provider text."""
        checks.append(DiagnosticCheck(code=code, status=status, message=message))

    if settings.api_key:
        add("api_auth_configured", "ok", "Inbound service authentication is configured.")
    else:
        add(
            "api_auth_unconfigured",
            "warning",
            "Configure inbound authentication before remote use.",
        )
    for binding in settings.connections.values():
        if binding.kind == "databricks-app":
            if (
                settings.provider.host
                or profile_override_present(environment)
                or profile_config_file_conflict(os.environ, environment)
            ):
                add(
                    "target_app_identity_conflict",
                    "error",
                    "An App identity conflicts with SDK destination, credential, or selector overrides. "
                    "Use an isolated operator environment.",
                )
            else:
                add(
                    "target_app_unverified",
                    "warning",
                    "App resolution and SDK authentication are unverified.",
                )
        elif binding.auth == "bearer":
            if not environment.get(binding.token_env or ""):
                add(
                    "target_credential_missing",
                    "error",
                    "A registered target credential is unavailable.",
                )
        elif binding.auth == "databricks":
            if settings.provider.host:
                if urlsplit(binding.url).netloc != urlsplit(settings.provider.host).netloc:
                    add(
                        "target_workspace_mismatch",
                        "error",
                        "A registered target differs from the configured HTTPS workspace.",
                    )
                else:
                    add(
                        "target_workspace_unverified",
                        "warning",
                        "SDK authentication is unverified.",
                    )
            elif settings.provider.profile:
                add(
                    "target_workspace_unverified",
                    "warning",
                    "Workspace binding and SDK authentication are unverified.",
                )
            else:
                add(
                    "target_workspace_missing",
                    "error",
                    "Configure an explicit workspace for the target.",
                )
    if settings.tracking_uri == "databricks" and not settings.provider.profile:
        add(
            "tracking_profile_missing",
            "error",
            "Databricks tracking needs an explicit operator identity.",
        )
    if settings.scorers and not settings.effective_tracking_uri:
        add(
            "scorer_tracking_missing",
            "error",
            "Registered scorers need a configured tracking destination.",
        )
    if settings.tracing.enabled and capabilities.tracing.readiness != "configured":
        add(
            "trace_configuration_missing",
            "error",
            "Enabled tracing needs a tracking destination and authorized experiments.",
        )
    elif not settings.tracing.enabled:
        add(
            "tracing_disabled",
            "warning",
            "Tracing is disabled; internal latency evidence will be unavailable.",
        )
    if capabilities.evaluation.planner == "needs_configuration":
        add(
            "planner_configuration_missing",
            "warning",
            "Automatic evaluation planning needs provider configuration.",
        )
    if capabilities.evaluation.catalog_judges == "needs_configuration":
        add(
            "judge_configuration_missing",
            "warning",
            "Catalog evaluation needs a configured Databricks judge.",
        )
    add(
        "runtime_unverified",
        "warning",
        "Configuration inspection does not verify live providers, targets, or storage ownership.",
    )
    return DoctorReport(
        ok=not any(check.status == "error" for check in checks),
        checks=tuple(checks),
        capabilities=capabilities,
    )


def doctor(
    config_path: str | Path | None = None, *, environ: Mapping[str, str] | None = None
) -> DoctorReport:
    """Load bounded operator configuration and return safe read-only diagnostics.

    Args:
        config_path: Explicit TOML/YAML file, overriding the environment file path.
        environ: Isolated environment snapshot; None copies process values.

    Returns:
        A typed report. Invalid configuration has one safe error and no partial
        capability registry. No target, provider, credential, or storage checks run.
    """
    environment = dict(os.environ if environ is None else environ)
    try:
        settings = load_settings(config_path, environ=environment)
    except SettingsError as error:
        return DoctorReport(
            ok=False,
            checks=(DiagnosticCheck(code=error.code, status="error", message=str(error)),),
            capabilities=None,
        )
    return startup_diagnostics(settings, environ=environment)
