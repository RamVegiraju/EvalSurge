"""Pure typed-metadata comparisons; no inference, auth, storage or network calls."""

import json
import subprocess
import sys
from uuid import UUID, uuid4

import pytest

from benchmark_agents.models import (
    EvaluationPreflight,
    PreflightError,
    PreflightResult,
    ProfilingSummary,
)
from benchmark_agents.v2_models import (
    DecisionSummary,
    Links,
    PhaseStates,
    Report,
    Result,
    RunStatus,
)
from evalsurge._retrieval import retrieval_evidence


def _failed_metadata() -> tuple[RunStatus, Result, Report]:
    """Build schema-only failure metadata, never agent/model response fixtures."""
    identifier = UUID("9382b38b-9d1e-4b9d-86fe-3e0d778bb327")
    phases = PhaseStates(
        planning="completed",
        inference="failed",
        evaluation_readiness="skipped",
        load="skipped",
        profiling="skipped",
        evaluation="skipped",
    )
    result = Result(
        id=identifier,
        status="failed",
        phases=phases,
        links=Links.for_run(str(identifier)),
        summary=DecisionSummary(performance="not_run", quality="off"),
        preflight=PreflightResult(
            status="failed",
            error=PreflightError(code="worker_failed", message="protected-diagnostic-marker"),
        ),
        evaluation_preflight=EvaluationPreflight(status="skipped"),
    )
    status = RunStatus(id=identifier, status=result.status, phases=phases, links=result.links)
    report = Report(
        run=result,
        profiling=ProfilingSummary(total_requests=0, traced_requests=0, coverage=0),
        requests=[],
        offset=0,
        limit=25,
        total=0,
    )
    return status, result, report


def test_failed_receipts_can_agree_without_claiming_successful_inference() -> None:
    status, result, report = _failed_metadata()
    evidence = retrieval_evidence(
        result.id, status, result, report, report.model_copy(deep=True), remote=False
    )
    assert evidence["retrieval_agrees"] is True
    assert evidence["remote_work_may_remain_active"] is False
    assert evidence["preflight_code"] == "worker_failed"
    assert "protected-diagnostic-marker" not in json.dumps(evidence)
    assert "passed" not in evidence
    assert result.metrics is None


@pytest.mark.parametrize("mismatch", ["identity", "state", "phase", "result", "page"])
def test_remote_disagreement_never_clears_active_work_warning(mismatch: str) -> None:
    status, result, report = _failed_metadata()
    retrieved = report.model_copy(deep=True)
    if mismatch == "identity":
        status.id = uuid4()
    elif mismatch == "state":
        status.status = "running"
    elif mismatch == "phase":
        status.phases = status.phases.model_copy(update={"load": "running"})
    elif mismatch == "result":
        retrieved.run.summary.quality = "unavailable"
    else:
        retrieved.limit = 10
    evidence = retrieval_evidence(result.id, status, result, report, retrieved, remote=True)
    assert evidence["retrieval_agrees"] is False
    assert evidence["remote_work_may_remain_active"] is True


def test_unknown_preflight_error_is_not_exported() -> None:
    """Fail closed on deliberately malformed metadata, not a provider response."""
    status, result, report = _failed_metadata()
    report.run.preflight.error = report.run.preflight.error.model_copy(
        update={"code": "operator-private-error-marker"}
    )
    evidence = retrieval_evidence(result.id, status, result, report, report, remote=False)
    assert evidence["preflight_code"] is None
    assert "private-error" not in json.dumps(evidence)
    assert "protected-diagnostic" not in json.dumps(evidence)


def test_package_retrieval_import_does_not_pull_validation_or_agent_frameworks() -> None:
    """Inspect a fresh native interpreter's imports only; no inference is performed."""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from evalsurge._retrieval import retrieval_evidence; "
            "assert not any(name.startswith('scripts.') for name in sys.modules); "
            "assert not {'agents', 'langgraph', 'crewai', 'locust'} & sys.modules.keys(); "
            "print('pure-retrieval-import')",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "pure-retrieval-import"


def test_historical_validation_comparison_preserves_packaged_receipt_values() -> None:
    """Compare metadata-only script compatibility; neither function performs calls."""
    from scripts.validation.hosted_journeys import retrieval_evidence as historical_evidence

    assert historical_evidence is retrieval_evidence
    status, result, report = _failed_metadata()
    retrieved = report.model_copy(deep=True)
    for remote in (False, True):
        assert retrieval_evidence(
            result.id, status, result, report, retrieved, remote=remote
        ) == historical_evidence(result.id, status, result, report, retrieved, remote=remote)
