"""Local Python API for hosted-agent benchmarks using the shared Locust engine."""

from benchmark_agents.connections import Connection
from benchmark_agents.models import Evaluation, Load, RunReport, Sample

from .client import Agent, EvalSurge, RunFailed
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
)

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
]
