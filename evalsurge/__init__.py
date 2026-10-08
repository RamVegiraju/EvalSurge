"""Unified request vocabulary; direct execution lazily requires evalsurge[server]."""

from typing import TYPE_CHECKING, Any

from benchmark_agents.models import Evaluation, Load, RunReport, Sample
from benchmark_agents.v2_models import (
    Acknowledgment,
    AssessmentOutcome,
    Case,
    DecisionSummary,
    EvaluationOutcome,
    EvaluationPolicy,
    Links,
    Performance,
    PhaseStates,
    Report,
    RequestCoverage,
    Result,
    RunCreate,
    RunStatus,
    SamplingCoverage,
    SamplingStratum,
    ScorerOutcome,
    TargetReference,
    Timing,
    ValidationIssue,
)
from benchmark_agents.validation import RequestValidationError

from .facade import EvalSurge, MissingServerDependenciesError, _local_module
from .remote import (
    RemoteClient,
    RemoteConflictError,
    RemoteError,
    RemoteProtocolError,
    RemoteRateLimitError,
    RemoteRun,
    RemoteRunFailed,
    RemoteTimeout,
    RemoteTransportError,
    RemoteUnauthorizedError,
    TypedRemoteClient,
    TypedRemoteRun,
)

if TYPE_CHECKING:
    from benchmark_agents.connections import Connection as Connection

    from .client import Agent as Agent
    from .client import RunFailed as RunFailed


def __getattr__(name: str) -> Any:
    """Preserve local public names without importing the server for remote access.

    Args:
        name: Requested module attribute; only three documented local names defer.

    Returns:
        The existing local class, cached after successful dependency validation.

    Raises:
        AttributeError: The name is not a documented lazy export.
        MissingServerDependenciesError: A local export needs the server extra.
    """
    if name not in {"Agent", "Connection", "RunFailed"}:
        raise AttributeError(f"module 'evalsurge' has no attribute {name!r}")
    value = getattr(_local_module(), name)
    globals()[name] = value
    return value


__all__ = [
    "Agent",
    "Connection",
    "EvalSurge",
    "Evaluation",
    "Load",
    "RunFailed",
    "RunReport",
    "Sample",
    "RemoteClient",
    "RemoteRun",
    "RemoteError",
    "RemoteUnauthorizedError",
    "RemoteRateLimitError",
    "RemoteConflictError",
    "RemoteProtocolError",
    "RemoteTransportError",
    "RemoteTimeout",
    "RemoteRunFailed",
    "MissingServerDependenciesError",
    "RunCreate",
    "Case",
    "TargetReference",
    "EvaluationPolicy",
    "RunStatus",
    "Result",
    "Report",
    "Acknowledgment",
    "Links",
    "PhaseStates",
    "DecisionSummary",
    "Performance",
    "Timing",
    "ValidationIssue",
    "RequestValidationError",
    "TypedRemoteClient",
    "TypedRemoteRun",
    "EvaluationOutcome",
    "ScorerOutcome",
    "AssessmentOutcome",
    "RequestCoverage",
    "SamplingCoverage",
    "SamplingStratum",
]
