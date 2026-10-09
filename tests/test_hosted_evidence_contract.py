"""No-inference schema/presentation and intentional pre-provider evidence checks.

Stored DTO examples exercise reporting only; no target, framework or judge
executes and no provider completions are substituted. Missing-trace checks stop
before any evaluator invocation. These passes do not establish live inference.
"""

from copy import deepcopy
from typing import Any, NoReturn

import pytest

from benchmark_agents import evaluation_preflight
from benchmark_agents.diagnostics import build_capabilities
from benchmark_agents.models import Plan, ProfilingSummary
from benchmark_agents.run_views import result_view
from benchmark_agents.settings import load_settings
from benchmark_agents.v2_models import EvidenceCapabilities, Result

RUN_ID = "3cb02594-2e3b-408d-9f3a-0c9cedbd7d78"
PRIVATE = "operator-private-sentinel"


def stored_run() -> dict[str, Any]:
    """Build a detached presentation DTO, not a fake agent or inference result.

    Counts represent report fields under test; no captured answers are supplied.
    Private policy values test that presentation never exposes operator setup.
    """
    return {
        "id": RUN_ID,
        "status": "completed",
        "planning_status": "completed",
        "load_status": "completed",
        "profiling_status": "completed",
        "evaluation_status": "no_ready_scorers",
        "evaluation_mode": "off",
        "config": {"evaluation": {"scorers": []}},
        "plan": {
            "recommendations": [],
            "registered_scorers": [],
            "trace_source": None,
            "judge_profile": PRIVATE,
            "judge_host": f"https://{PRIVATE}.example",
        },
        "preflight": {"status": "passed", "request_id": "excluded-probe"},
        "evaluation_preflight": {"status": "skipped"},
        "evaluation": {},
        "metrics": {
            "requests": 4,
            "successful_requests": 3,
            "error_rate": 0.25,
            "successful_tps": 0.3,
            "completed_tps": 0.4,
            "elapsed_seconds_including_drain": 10,
            "dispatch_seconds": 8,
            "token_usage_coverage": 0,
            "timing_successful_only": {"latency_ms": {"count": 3, "p50": 30, "p95": 80, "p99": 80}},
            "measurement_complete": True,
        },
    }


def selected_criteria(run: dict[str, Any], *, trace: bool = False) -> str:
    """Add frozen criterion DTO metadata without loading or executing a scorer."""
    name = "registered:tool-use" if trace else "relevance"
    run["evaluation_mode"] = "explicit"
    run["config"]["evaluation"]["scorers"] = [name]
    run["plan"]["recommendations"] = [
        {"scorer": name, "required_fields": ["trace"] if trace else ["inputs", "outputs"]}
    ]
    if trace:
        run["plan"]["registered_scorers"] = [{"alias": "tool-use", "required_fields": ["trace"]}]
        run["plan"]["trace_source"] = {
            "tracking_uri": f"https://{PRIVATE}.example",
            "experiment_ids": [PRIVATE],
        }
    return name


def test_load_only_evidence_is_independent_of_disabled_optional_tracing() -> None:
    """Absent optional spans are off, not an enabled instrumentation failure."""
    run = stored_run()
    profiling = ProfilingSummary(
        total_requests=4, traced_requests=0, coverage=0, gaps={"disabled": 4}
    )
    before = deepcopy(run)
    report = result_view(run, profiling)
    evidence = report.evidence
    assert evidence.load_measurements.configured
    assert evidence.load_measurements.state == "observed"
    assert evidence.load_measurements.observed_count == 4
    assert evidence.load_measurements.total_count == 4
    assert evidence.load_measurements.coverage == 1
    assert report.metrics.timing_successful_only["latency_ms"].count == 3
    assert evidence.answer_evaluation.state == "off"
    assert evidence.internal_profiling.state == "off"
    assert evidence.trace_aware_evaluation.state == "off"
    assert "internal_trace_coverage" not in report.summary.evidence_gaps
    assert not report.summary.sustainable_capacity_established
    assert PRIVATE not in report.model_dump_json()
    assert run == before


def test_answer_judging_observation_does_not_require_traces_or_passing_verdicts() -> None:
    """Native false judgments are observed evidence, not an execution failure."""
    run = stored_run()
    name = selected_criteria(run)
    run["evaluation_status"] = "completed"
    run["evaluation"] = {
        "status": "completed",
        "results": [
            {
                "scorer": name,
                "status": "completed",
                "eligible": 3,
                "attempted": 2,
                "scored": 2,
                "pass_rate": 0,
                "assessments": [
                    {"request_id": "r1", "status": "failed", "value": False},
                    {"request_id": "r2", "status": "failed", "value": False},
                ],
            }
        ],
    }
    report = result_view(run)
    assert report.evidence.answer_evaluation.configured
    assert report.evidence.answer_evaluation.state == "observed"
    assert report.evidence.answer_evaluation.observed_count == 2
    assert report.evidence.answer_evaluation.coverage == pytest.approx(2 / 3)
    assert report.evidence.trace_aware_evaluation.state == "off"
    assert report.evidence.internal_profiling.state == "off"
    assert report.summary.quality == "available"
    assert report.evaluation.results[0].pass_rate == 0


def test_partial_judging_keeps_observed_assessments_and_existing_summary_meanings() -> None:
    """Independent evidence survives incomplete quality execution without claiming pass."""
    run = stored_run()
    name = selected_criteria(run)
    run["status"] = "completed_with_gaps"
    run["evaluation_status"] = "completed_with_errors"
    run["evaluation"] = {
        "status": "completed_with_errors",
        "results": [
            {"scorer": name, "status": "partial", "eligible": 3, "scored": 1, "judge_errors": 1}
        ],
    }
    report = result_view(run)
    assert report.evidence.answer_evaluation.state == "observed"
    assert report.evidence.answer_evaluation.coverage == pytest.approx(1 / 3)
    assert report.summary.quality == "unavailable"
    assert "evaluation_unavailable" in report.summary.evidence_gaps


def test_absent_selected_scorer_does_not_overstate_aggregate_assessment_coverage() -> None:
    """A stopped evaluator keeps observations but cannot supply the omitted denominator."""
    run = stored_run()
    name = selected_criteria(run)
    run["plan"]["recommendations"].append(
        {"scorer": "safety", "required_fields": ["inputs", "outputs"]}
    )
    run["config"]["evaluation"]["scorers"].append("safety")
    run["evaluation_status"] = "completed_with_errors"
    run["evaluation"] = {
        "status": "completed_with_errors",
        "results": [{"scorer": name, "status": "partial", "scored": 1, "eligible": 3}],
    }
    report = result_view(run)
    assert report.evidence.answer_evaluation.state == "observed"
    assert report.evidence.answer_evaluation.observed_count == 1
    assert report.evidence.answer_evaluation.total_count is None
    assert report.evidence.answer_evaluation.coverage is None


def test_duplicate_scorer_outcomes_leave_aggregate_denominator_unknown() -> None:
    """Exactly-once selected-scorer representation is required for a known denominator."""
    run = stored_run()
    name = selected_criteria(run)
    run["evaluation_status"] = "completed_with_errors"
    run["evaluation"] = {
        "status": "completed_with_errors",
        "results": [
            {"scorer": name, "status": "partial", "scored": 1, "eligible": 3},
            {"scorer": name, "status": "partial", "scored": 1, "eligible": 3},
        ],
    }
    report = result_view(run)
    assert report.evidence.answer_evaluation.observed_count == 2
    assert report.evidence.answer_evaluation.total_count is None
    assert report.evidence.answer_evaluation.coverage is None


def test_ready_probe_cannot_claim_measured_load_or_trace_aware_judging() -> None:
    """Readiness and feature selection never substitute for post-load evidence."""
    run = stored_run()
    selected_criteria(run, trace=True)
    run.update(
        status="failed",
        load_status="skipped",
        profiling_status="skipped",
        evaluation_status="failed",
        metrics={},
        evaluation_preflight={"status": "passed", "checked_scorers": ["registered:tool-use"]},
    )
    report = result_view(run, ProfilingSummary(total_requests=0, traced_requests=0, coverage=0))
    assert report.evidence.load_measurements.state == "unavailable"
    assert report.evidence.load_measurements.observed_count == 0
    assert report.evidence.answer_evaluation.state == "off"
    assert report.evidence.internal_profiling.configured
    assert report.evidence.internal_profiling.state == "unavailable"
    assert report.evidence.trace_aware_evaluation.configured
    assert report.evidence.trace_aware_evaluation.state == "unavailable"
    assert report.evidence.trace_aware_evaluation.observed_count == 0


def test_trace_aware_assessments_and_internal_spans_have_independent_coverage() -> None:
    """Validated profiles do not assert that a judge ran or produced assessments."""
    run = stored_run()
    name = selected_criteria(run, trace=True)
    run["evaluation_status"] = "completed"
    run["evaluation"] = {
        "status": "completed",
        "results": [{"scorer": name, "status": "completed", "eligible": 2, "scored": 1}],
    }
    report = result_view(run, ProfilingSummary(total_requests=4, traced_requests=2, coverage=0.5))
    assert report.evidence.internal_profiling.state == "observed"
    assert report.evidence.internal_profiling.observed_count == 2
    assert report.evidence.internal_profiling.coverage == 0.5
    assert report.evidence.trace_aware_evaluation.state == "observed"
    assert report.evidence.trace_aware_evaluation.observed_count == 1
    assert report.evidence.trace_aware_evaluation.total_count == 2
    assert report.evidence.trace_aware_evaluation.coverage == 0.5
    assert "internal_trace_coverage" in report.summary.evidence_gaps
    assert PRIVATE not in report.model_dump_json()


def test_all_failed_measured_attempts_remain_load_evidence_but_not_latency_or_judgments() -> None:
    """All-attempt errors are observations; failed judges are not scored assessments."""
    run = stored_run()
    name = selected_criteria(run)
    run["status"] = "completed_with_gaps"
    run["evaluation_status"] = "failed"
    run["metrics"].update(
        successful_requests=0,
        error_rate=1,
        errors={"Timeout": 4},
        timing_successful_only={"latency_ms": {"count": 0, "p50": None}},
    )
    run["evaluation"] = {
        "status": "failed",
        "results": [{"scorer": name, "status": "failed", "scored": 0, "judge_errors": 2}],
    }
    report = result_view(run)
    assert report.evidence.load_measurements.state == "observed"
    assert report.evidence.load_measurements.observed_count == 4
    assert report.evidence.load_measurements.coverage == 1
    assert report.metrics.error_rate == 1
    assert report.metrics.timing_successful_only["latency_ms"].count == 0
    assert report.metrics.timing_successful_only["latency_ms"].p50 is None
    assert report.evidence.answer_evaluation.state == "unavailable"
    assert report.evidence.answer_evaluation.coverage is None


def test_historical_catalog_assessments_remain_observed_without_frozen_plan_metadata() -> None:
    """Recorded catalog provenance identifies answer judging; configuration stays unknown."""
    run = stored_run()
    name = selected_criteria(run)
    run.pop("plan")
    run.pop("evaluation_mode")
    run["evaluation_status"] = "completed"
    run["evaluation"] = {
        "status": "completed",
        "results": [
            {
                "scorer": name,
                "source": "catalog",
                "status": "completed",
                "scored": 1,
                "eligible": 2,
            }
        ],
    }
    report = result_view(run)
    assert report.evidence.answer_evaluation.configured is None
    assert report.evidence.answer_evaluation.state == "observed"
    assert report.evidence.answer_evaluation.observed_count == 1
    assert report.evidence.answer_evaluation.coverage == 0.5
    assert report.evidence.trace_aware_evaluation.configured is None
    assert "requirements are unknown" in report.evidence.trace_aware_evaluation.guidance


def test_historical_registered_assessments_are_preserved_without_inventing_requirements() -> None:
    """Absent requirement metadata leaves classification unknown, not silently answer-only."""
    run = stored_run()
    name = selected_criteria(run, trace=True)
    run.pop("plan")
    run.pop("evaluation_mode")
    run["evaluation_status"] = "completed"
    run["evaluation"] = {
        "status": "completed",
        "results": [
            {"scorer": name, "source": "registered-mlflow", "status": "completed", "scored": 1}
        ],
    }
    report = result_view(run)
    assert report.evaluation.results[0].scored == 1
    assert report.evidence.answer_evaluation.configured is None
    assert report.evidence.trace_aware_evaluation.configured is None
    assert report.evidence.answer_evaluation.observed_count == 0
    assert report.evidence.trace_aware_evaluation.observed_count == 0
    assert "requirements are unknown" in report.evidence.answer_evaluation.guidance
    assert "remain in evaluation.results" in report.evidence.trace_aware_evaluation.guidance


@pytest.mark.parametrize("status", ["queued", "preflighting", "running", "evaluating"])
def test_selected_pending_features_are_not_observed_before_measured_evidence(status: str) -> None:
    """Running phases report pending independently of a successful excluded probe."""
    run = stored_run()
    selected_criteria(run, trace=True)
    run.update(status=status, metrics={}, evaluation={}, evaluation_status="pending")
    report = result_view(run)
    assert report.evidence.load_measurements.state == "pending"
    assert report.evidence.internal_profiling.state == "pending"
    assert report.evidence.trace_aware_evaluation.state == "pending"


def test_historical_config_and_old_response_fields_remain_unknown() -> None:
    """Absent historical fields do not imply disabled tracing or verified authentication."""
    run = stored_run()
    del run["plan"]["trace_source"]
    report = result_view(run)
    assert report.evidence.internal_profiling.configured is None
    assert report.evidence.internal_profiling.state == "unavailable"
    old_payload = report.model_dump(mode="json")
    old_payload.pop("evidence")
    parsed = Result.model_validate(old_payload)
    assert parsed.evidence == EvidenceCapabilities()
    assert parsed.evidence.load_measurements.configured is None
    assert parsed.evidence.load_measurements.state == "pending"


def test_static_capabilities_describe_contracts_without_claiming_runtime_verification() -> None:
    """Pure configuration distinguishes optional profiling from trace-required criteria."""
    capabilities = build_capabilities(load_settings(environ={}), environ={})
    assert capabilities.evaluation.default_mode == "off"
    assert not capabilities.evaluation.answer_evaluation_requires_traces
    assert capabilities.evaluation.trace_required_judges_require_correlated_probe
    assert capabilities.evaluation.captured_answers_only
    assert capabilities.tracing.optional_for_load_and_answer_evaluation
    assert not capabilities.runtime_verified


def test_required_trace_with_another_request_id_stops_before_any_judge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Intentional pre-provider failure: unrelated evidence never authorizes judging."""

    def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
        """Fail if this evidence-only check ever tries to execute an evaluator."""
        pytest.fail("A missing correlated probe trace must stop before judge execution")

    monkeypatch.setattr(evaluation_preflight, "evaluate", forbidden)
    plan = Plan(
        source="explicit",
        rubric_hash="presentation-only",
        dataset_hash="presentation-only",
        evaluation_hash="presentation-only",
        max_scored_requests=1,
        sampling_seed=42,
        description="Missing evidence check without inference",
        registered_scorers=[
            {
                "alias": "tool-use",
                "name": "operator-owned-tool-use",
                "experiment_id": "1",
                "version": 1,
                "required_fields": ["trace"],
                "definition_hash": "not-loaded",
            }
        ],
        recommendations=[
            {
                "scorer": "registered:tool-use",
                "reason": "Explicit selection",
                "status": "ready",
                "required_fields": ["trace"],
                "eligible_samples": 1,
                "total_samples": 1,
            }
        ],
    )
    result = evaluation_preflight.run_evaluation_preflight(
        {"request_id": "expected-probe"}, plan, {"other-request": object()}
    )
    assert result.status == "failed"
    assert result.error.code == "evaluation_missing_trace"
    assert result.checked_scorers == []
