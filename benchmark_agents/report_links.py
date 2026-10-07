"""Build bounded MLflow navigation links without querying stores or credentials."""

import re
from typing import Any
from urllib.parse import urlsplit

from pydantic import HttpUrl, ValidationError

from .configuration import getenv
from .models import MLflowExperimentLink, Plan
from .scorer_registry import tracking_uri


def _safe_base(value: str) -> str | None:
    """Normalize a credential-free UI base without performing network I/O.

    Args:
        value: Operator-selected base, bounded to 2,048 characters.

    Returns:
        Normalized HTTP(S) base without a trailing slash, or None for unsafe
        schemes, credentials, query/fragment, ambiguity, or remote plain HTTP.
        Invalid configuration is omitted rather than breaking a report.
    """
    if len(value) > 2048 or any(
        character.isspace() or ord(character) < 32 or character in "\\?#" for character in value
    ):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.port == 0
            or (
                parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            )
        ):
            return None
        return str(HttpUrl(value)).rstrip("/")
    except (ValueError, ValidationError):
        return None


def _ui_base(uri: str | None) -> str | None:
    """Resolve presentation configuration without querying tracking or credentials.

    Args:
        uri: Exact frozen tracking store, or None when no destination was recorded.

    Returns:
        A safe operator override for the matching current store, otherwise the
        HTTP(S) store base when available. Invalid or unknown bases return None.

    Reads process-owned environment settings; no SDK or MLflow client is created.
    """
    if not uri:
        return None
    configured = getenv("BENCHMARK_MLFLOW_UI_URL")
    if configured:
        try:
            if uri == tracking_uri():
                return _safe_base(configured)
        except ValueError:
            return None
    return _safe_base(uri)


def experiment_links(plan: Plan, evaluation: dict[str, Any]) -> list[MLflowExperimentLink]:
    """Create browser-only links to recorded trace and evaluation experiments.

    Args:
        plan: Frozen destinations and authorized trace experiment IDs.
        evaluation: Captured native results with optional mlflow_experiment_id.

    Returns:
        At most 20 credential-free links, merged by destination and experiment.
        Unconfigured, unsafe, or historical unknown destinations are omitted.

    Reads only operator environment configuration. No store, SDK, provider, or
    credential request is made; judging and measurement outcomes are unchanged.
    An override is used only when MLFLOW_TRACKING_URI matches the frozen store.
    The operator must ensure its UI serves that store. A model-provider host is
    never assumed to be a tracking destination.
    """
    links: dict[str, MLflowExperimentLink] = {}
    destinations = (
        [
            (plan.trace_source.tracking_uri, identifier, "traces")
            for identifier in plan.trace_source.experiment_ids
        ]
        if plan.trace_source
        else []
    )
    destinations.extend(
        (plan.tracking_uri, result.get("mlflow_experiment_id"), "evaluation")
        for result in evaluation.get("results", [])[:20]
    )
    for uri, identifier, scope in destinations:
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identifier):
            continue
        base = _ui_base(uri)
        if not base:
            continue
        route = "/ml/experiments/" if uri and uri.startswith("databricks") else "/#/experiments/"
        url = base + route + identifier
        if url in links:
            if scope not in links[url].scopes:
                links[url].scopes.append(scope)
        elif len(links) < 20:
            links[url] = MLflowExperimentLink(experiment_id=identifier, url=url, scopes=[scope])
    return list(links.values())
