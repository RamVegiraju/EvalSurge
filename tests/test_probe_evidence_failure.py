"""No-inference regressions: required evidence failures before judge execution.

Records are storage/presentation inputs, not simulated provider completions. The
collector deliberately fails and the evaluator is a fail-if-called sentinel.
No target, judge, framework handler or model endpoint executes in these tests.
"""

import asyncio
from uuid import uuid4

import pytest

import benchmark_agents.coordinator as coordinator_module
import benchmark_agents.evaluation_preflight as preflight_module
from benchmark_agents.coordinator import RunCoordinator
from benchmark_agents.models import Plan, Recommendation, RegisteredScorer, TraceSource


def trace_plan() -> Plan:
    """Construct only frozen schema metadata for a trace-required criterion."""
    return Plan(
        source="explicit",
        rubric_hash="frozen-rubric",
        dataset_hash="frozen-dataset",
        evaluation_hash="frozen-policy",
        max_scored_requests=1,
        sampling_seed=42,
        description="Trace readiness",
        trace_source=TraceSource(tracking_uri="sqlite:///unused.db", experiment_ids=["1"]),
        registered_scorers=[
            RegisteredScorer(
                alias="trace-check",
                name="trace-check",
                experiment_id="1",
                version=1,
                required_fields=["trace"],
                definition_hash="frozen-definition",
            )
        ],
        recommendations=[
            Recommendation(
                scorer="registered:trace-check",
                reason="Explicit operator selection",
                status="ready",
                required_fields=["trace"],
                eligible_samples=1,
                total_samples=1,
            )
        ],
    )


async def test_required_probe_collection_failure_is_safe_readiness_failure(tmp_path, monkeypatch):
    """A broken trace store must stop before the native evaluator is called."""
    plan = trace_plan()
    row = {"request_id": str(uuid4())}
    run_id = str(uuid4())

    def failed_collection(*args):
        assert args[0] == [row]
        assert args[1] == run_id
        assert args[2].max_traces == 1
        raise RuntimeError("private-store-token-and-trace-content")

    def forbidden_judging(*args, **kwargs):
        pytest.fail("An evidence failure must not call a judge")

    monkeypatch.setattr(coordinator_module, "collect_profiles", failed_collection)
    monkeypatch.setattr(preflight_module, "evaluate", forbidden_judging)
    owner = RunCoordinator(tmp_path)
    owner.cancellations[run_id] = asyncio.Event()
    outcome = await owner._probe_readiness(run_id, plan, row)
    assert outcome.status == "failed"
    assert outcome.checked_scorers == []
    assert outcome.error.code == "evaluation_trace_collection_failed"
    assert outcome.error.scorer == "registered:trace-check"
    assert "private-store" not in outcome.model_dump_json()
    assert plan.trace_source.max_traces == 100


async def test_missing_correlated_probe_trace_never_calls_judge(tmp_path, monkeypatch):
    """Missing returned IDs fail readiness without any model or store call."""
    plan = trace_plan().model_copy(update={"trace_source": None})
    row = {"request_id": str(uuid4()), "success": True}

    def forbidden_judging(*args, **kwargs):
        pytest.fail("Missing trace evidence must not call a judge")

    monkeypatch.setattr(preflight_module, "evaluate", forbidden_judging)
    run_id = str(uuid4())
    owner = RunCoordinator(tmp_path)
    owner.cancellations[run_id] = asyncio.Event()
    outcome = await owner._probe_readiness(run_id, plan, row)
    assert outcome.status == "failed"
    assert outcome.error.code == "evaluation_missing_trace"
    assert outcome.checked_scorers == []


async def test_answer_only_readiness_does_not_read_optional_probe_traces(tmp_path, monkeypatch):
    """Abort before judging; prove optional trace scope is not a prerequisite."""
    plan = trace_plan().model_copy(
        update={
            "registered_scorers": [],
            "recommendations": [
                Recommendation(
                    scorer="relevance",
                    reason="Answer-only criterion",
                    status="ready",
                    required_fields=["inputs", "outputs"],
                    eligible_samples=1,
                    total_samples=1,
                )
            ],
        }
    )
    row = {"request_id": str(uuid4())}

    class BeforeJudgeExecution(Exception):
        """Intentional stop without an assessment or provider response."""

    def forbidden_collection(*args):
        pytest.fail("Answer-only readiness must not access optional trace stores")

    def stop_before_judging(capture, frozen, traces, *, cancellation):
        assert capture is row and frozen is plan and traces == {}
        assert not cancellation.is_set()
        raise BeforeJudgeExecution

    monkeypatch.setattr(coordinator_module, "collect_profiles", forbidden_collection)
    monkeypatch.setattr(coordinator_module, "run_evaluation_preflight", stop_before_judging)
    run_id = str(uuid4())
    owner = RunCoordinator(tmp_path)
    owner.cancellations[run_id] = asyncio.Event()
    with pytest.raises(BeforeJudgeExecution):
        await owner._probe_readiness(run_id, plan, row)
