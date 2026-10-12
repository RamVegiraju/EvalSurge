"""Pure numeric/schema/CLI projections; no agent, provider or substituted inference."""

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from benchmark_agents.run_views import result_view
from evalsurge import GeneratorHealth
from evalsurge.cli import _summary
from tests.test_hosted_evidence_contract import stored_run


def observations(*, degraded: bool = False) -> dict[str, Any]:
    """Return fixed aggregate DTOs for presentation only, not measurements."""
    timing = {"count": 8, "mean_ms": 1.25, "max_ms": 2.5}
    return {
        "status": "degraded" if degraded else "unknown",
        "observation_window": "dispatch_and_drain",
        "hub_lag": {"interval_ms": 10.0, **timing},
        "journal": {
            "queue_capacity": 5,
            "peak_pending": 6,
            "backpressure_events": 2,
            "writer_failures": 1 if degraded else 0,
            "started_events": 4,
            "completed_events": 4,
            "drained": not degraded,
            "enqueue_wait_ms": dict(timing),
            "durable_wait_ms": dict(timing),
            "write_and_fsync_ms": dict(timing),
        },
        "limitations": ["Telemetry is not verified accuracy."],
    }


def test_historical_metrics_do_not_invent_generator_health() -> None:
    """Absent telemetry is unknown without invalidating historical completion."""
    run = stored_run()
    before = deepcopy(run)
    result = result_view(run)
    assert result.metrics.generator_health is None
    assert "generator_health_unavailable" in result.summary.evidence_gaps
    assert result.summary.performance == "complete"
    assert result.metrics.measurement_complete
    assert not result.summary.sustainable_capacity_established
    assert run == before


def test_available_observations_do_not_certify_accuracy() -> None:
    """Observed aggregates never produce a healthy or verified status."""
    run = stored_run()
    run["metrics"]["generator_health"] = observations()
    result = result_view(run)
    assert isinstance(result.metrics.generator_health, GeneratorHealth)
    assert result.metrics.generator_health.status == "unknown"
    assert "generator_health_unavailable" not in result.summary.evidence_gaps
    assert result.summary.performance == "complete"
    assert not result.summary.sustainable_capacity_established
    assert result.metrics.timing_successful_only["latency_ms"].p95 == 80


def test_degraded_generator_cannot_be_presented_as_complete() -> None:
    """Fail-safe projection retains observations but never mutates stored evidence."""
    run = stored_run()
    run["metrics"]["generator_health"] = observations(degraded=True)
    before = deepcopy(run)
    result = result_view(run)
    assert not result.metrics.measurement_complete
    assert result.summary.performance == "incomplete"
    assert {"incomplete_measurements", "generator_degraded"} <= set(result.summary.evidence_gaps)
    assert result.metrics.successful_requests == 3
    assert run == before


@pytest.mark.parametrize("field,value", [("writer_failures", 1), ("drained", False)])
def test_observed_failure_overrides_inconsistent_unknown_state(field: str, value: Any) -> None:
    """An inconsistent stored health label cannot hide actual failure/drain evidence."""
    run = stored_run()
    health = observations()
    health["journal"][field] = value
    run["metrics"]["generator_health"] = health
    before = deepcopy(run)
    result = result_view(run)
    assert result.metrics.generator_health.status == "degraded"
    assert not result.metrics.measurement_complete
    assert result.summary.performance == "incomplete"
    assert "generator_degraded" in result.summary.evidence_gaps
    assert run == before


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan")])
def test_generator_durations_reject_impossible_observations(value: float) -> None:
    """Nonfinite/negative evidence cannot enter the public result model."""
    health = observations()
    health["hub_lag"]["mean_ms"] = value
    with pytest.raises(ValidationError):
        GeneratorHealth.model_validate(health)


def test_generator_model_rejects_accuracy_certification_and_private_fields() -> None:
    """No arbitrary telemetry schema or claimed healthy status crosses the DTO."""
    health = observations()
    health["status"] = "verified"
    with pytest.raises(ValidationError):
        GeneratorHealth.model_validate(health)
    health = observations()
    health["journal"]["path"] = "private-operator-path"
    with pytest.raises(ValidationError):
        GeneratorHealth.model_validate(health)


def test_cli_shows_observations_without_raw_guidance(capsys) -> None:
    """CLI prints only fixed labels/state and numeric values from raw reports."""
    run = stored_run()
    health = observations()
    health["limitations"] = ["private-provider-message"]
    health["journal"]["path"] = "private-operator-path"
    run["metrics"]["generator_health"] = health
    _summary({"run": run})
    output = capsys.readouterr().out
    assert "Generator health: unknown" in output
    assert "Hub wake-up lag: mean 1.25 ms" in output
    assert "Native write + fsync" in output
    assert "Journal drained: yes" in output
    assert "waits overlap" in output
    assert "private" not in output


def test_cli_does_not_assume_historical_runner_is_healthy(capsys) -> None:
    """Legacy successful metric DTOs retain an explicit telemetry gap."""
    _summary({"run": stored_run()})
    assert "Generator health: unavailable" in capsys.readouterr().out


def test_cli_reports_successful_timing_coverage_and_generator_backpressure(capsys) -> None:
    """Presentation never hides failed attempts or equates backlog with capacity."""
    run = stored_run()
    run["metrics"]["generator_health"] = observations()
    _summary({"run": run})
    output = capsys.readouterr().out
    assert "successful observations /" in output
    assert "Failed and timed-out attempts are excluded" in output
    assert "Journal backpressure observed" in output
    assert "may be generator-limited" in output
    assert "even without queue backpressure" in output


@pytest.mark.parametrize("backpressure", [0, None, "private-value", True, float("nan")])
def test_cli_backpressure_warning_requires_observed_positive_count(capsys, backpressure) -> None:
    """Absent or malformed counters never invent observed backpressure or export data."""
    run = stored_run()
    health = observations()
    health["journal"]["backpressure_events"] = backpressure
    run["metrics"]["generator_health"] = health
    _summary({"run": run})
    output = capsys.readouterr().out
    assert "Journal backpressure observed" not in output
    assert "private-value" not in output
