"""Resolve trusted MLflow scorers from an operator allowlist, never uploaded Python."""

import json
import os
from typing import Any
from urllib.parse import urlsplit

from .models import RegisteredScorer, TraceSource


def tracking_uri() -> str | None:
    """Resolve an explicit store and forbid credentials embedded in persisted URIs."""
    uri = os.getenv("MLFLOW_TRACKING_URI")
    if uri == "databricks":
        profile = os.getenv("DATABRICKS_CONFIG_PROFILE")
        if not profile:
            raise ValueError("MLflow Databricks tracking requires an explicit profile")
        uri = f"databricks://{profile}"
    if uri and (urlsplit(uri).username or urlsplit(uri).password):
        raise ValueError("Configure MLflow credentials outside the tracking URI")
    return uri


def trace_source() -> TraceSource | None:
    """Freeze opt-in trace scope and hard collection limits from server configuration."""
    if os.getenv("BENCHMARK_TRACE_ENABLED", "false").lower() != "true":
        return None
    uri = tracking_uri()
    experiments = json.loads(os.getenv("BENCHMARK_TRACE_EXPERIMENT_IDS", "[]"))
    if not experiments and os.getenv("MLFLOW_EXPERIMENT_ID"):
        experiments = [os.environ["MLFLOW_EXPERIMENT_ID"]]
    if not uri or not experiments:
        raise ValueError("Tracing requires MLFLOW_TRACKING_URI and authorized experiment IDs")
    return TraceSource(
        tracking_uri=uri,
        experiment_ids=experiments,
        max_traces=int(os.getenv("BENCHMARK_MAX_TRACES", "100")),
    )


def catalog() -> dict[str, dict[str, Any]]:
    """Read bounded operator-owned scorer references without executing scorer code."""
    raw = json.loads(os.getenv("BENCHMARK_SCORERS", "{}"))
    if not isinstance(raw, dict) or len(raw) > 20:
        raise ValueError("BENCHMARK_SCORERS must be an object with at most 20 aliases")
    result = {}
    for alias, value in raw.items():
        reference = RegisteredScorer.model_validate(
            {**value, "alias": alias, "definition_hash": "not-resolved"}
        )
        result[alias] = reference.model_dump(exclude={"definition_hash"})
    return result


def load_scorer(reference: RegisteredScorer, uri: str) -> Any:
    """Fetch one exact trusted version from the frozen operator-selected MLflow store."""
    import mlflow
    from mlflow.genai.scorers import get_scorer

    mlflow.set_tracking_uri(uri)
    return get_scorer(
        name=reference.name, experiment_id=reference.experiment_id, version=reference.version
    )


def definition_hash(scorer: Any) -> str:
    """Hash the public serialized definition, normalizing set-valued required columns."""
    from .planner import fingerprint

    def canonical(value: Any, field: str = "") -> Any:
        """Preserve semantic list order, but sort MLflow's unordered column names."""
        if isinstance(value, dict):
            return {name: canonical(item, name) for name, item in value.items()}
        if isinstance(value, list):
            return (
                sorted(value)
                if field == "required_columns"
                else [canonical(item) for item in value]
            )
        return value

    return fingerprint(canonical(scorer.model_dump()))


def freeze(aliases: list[str]) -> list[RegisteredScorer]:
    """Bind selected aliases to exact versions and serialized-definition hashes.

    The allowlist is trusted administrative configuration: MLflow can deserialize
    executable scorer definitions. Callers may select aliases but cannot supply
    source, tracking URIs, registry names, experiment IDs, or arbitrary versions.
    """
    available, uri = catalog(), tracking_uri()
    if aliases and not uri:
        raise ValueError("Registered scorers require an explicit MLFLOW_TRACKING_URI")
    frozen = []
    for alias in dict.fromkeys(aliases):
        if alias not in available:
            raise ValueError("Unknown operator-allowlisted scorer alias")
        reference = RegisteredScorer(**available[alias], definition_hash="not-resolved")
        scorer = load_scorer(reference, uri)
        reference.definition_hash = definition_hash(scorer)
        frozen.append(reference)
    return frozen
