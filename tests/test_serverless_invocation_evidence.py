"""Pure receipt metadata mapping, not agent behavior or actual inference coverage."""

from uuid import uuid4

import pytest

from benchmark_agents.locust_runner import preflight_result
from benchmark_agents.models import EvaluationPreflight, PreflightResult
from benchmark_agents.v2_models import DecisionSummary, Links, Performance, PhaseStates, Result
from evalsurge.serverless import _invocation_evidence


def _result(probe: PreflightResult, metrics: Performance | None = None) -> Result:
    """Build typed metadata only, with no captured/model responses or provider transport."""
    identifier = uuid4()
    return Result(
        id=identifier,
        status="failed",
        phases=PhaseStates(
            planning="completed",
            inference=probe.status,
            evaluation_readiness="skipped",
            load="skipped",
            profiling="skipped",
            evaluation="skipped",
        ),
        links=Links.for_run(str(identifier)),
        summary=DecisionSummary(performance="not_run", quality="off"),
        preflight=probe,
        evaluation_preflight=EvaluationPreflight(status="skipped"),
        metrics=metrics,
    )


def _metrics(*, success: int = 0, peak: int | None = None) -> Performance:
    """Represent counters only; no target, auth, answer, or inference is provided."""
    return Performance(
        requests=1,
        successful_requests=success,
        error_rate=1 - success,
        successful_tps=0,
        completed_tps=0,
        elapsed_seconds_including_drain=1,
        dispatch_seconds=0,
        token_usage_coverage=0,
        reported_output_tokens_per_second=None,
        timing_successful_only={},
        observed_peak_in_flight=peak,
    )


@pytest.mark.parametrize("stage", ["not_run", "worker_failure", "authentication", "input"])
def test_pre_dispatch_metadata_does_not_establish_app_invocation(stage: str) -> None:
    if stage == "not_run":
        probe = PreflightResult(status="not_run")
    else:
        row = (
            {}
            if stage == "worker_failure"
            else {
                "request_id": "recorded-start-is-not-dispatch",
                "error_phase": "authentication" if stage == "authentication" else "request",
                "error": "AuthError" if stage == "authentication" else "InvalidInput",
                "latency_ms": None,
                "http_status": None,
            }
        )
        probe = preflight_result(
            [row] if row else [], {"load_status": "failed", "worker_exit_code": 0}
        )
    assert _invocation_evidence(_result(probe)) == {
        "client_invocation_observed": False,
        "successful_completion_observed": False,
        "deployed_app_tested": False,
    }


@pytest.mark.parametrize("peak", [None, 0])
def test_failed_measured_attempt_count_alone_is_not_dispatch_evidence(peak: int | None) -> None:
    evidence = _invocation_evidence(_result(PreflightResult(status="not_run"), _metrics(peak=peak)))
    assert evidence["client_invocation_observed"] is False
    assert evidence["successful_completion_observed"] is False


@pytest.mark.parametrize("observation", ["latency", "http_status", "measured_peak"])
def test_client_dispatch_evidence_does_not_imply_successful_completion(observation: str) -> None:
    probe = PreflightResult(
        status="failed",
        latency_ms=12 if observation == "latency" else None,
        http_status=403 if observation == "http_status" else None,
    )
    metrics = _metrics(peak=1) if observation == "measured_peak" else None
    evidence = _invocation_evidence(_result(probe, metrics))
    assert evidence["client_invocation_observed"] is True
    assert evidence["deployed_app_tested"] is True
    assert evidence["successful_completion_observed"] is False


@pytest.mark.parametrize("source", ["preflight", "measured"])
def test_completion_metadata_is_independent_from_terminal_run_state(source: str) -> None:
    probe = PreflightResult(status="passed" if source == "preflight" else "not_run")
    metrics = _metrics(success=1) if source == "measured" else None
    result = _result(probe, metrics)
    assert result.status == "failed"
    evidence = _invocation_evidence(result)
    assert evidence["client_invocation_observed"] is True
    assert evidence["successful_completion_observed"] is True
