"""Exercise actual MLflow registered scorers and conservative non-executing setup scans."""

import json
from pathlib import Path
from typing import Any

import mlflow
import pytest
from mlflow.entities import Feedback
from mlflow.genai import judges
from mlflow.genai.scorers import Correctness, RetrievalGroundedness

from benchmark_agents.evaluator import evaluate
from benchmark_agents.models import Evaluation
from benchmark_agents.planner import create_plan
from scripts.scan_agent import scan


async def test_exact_registered_version_and_expectation_coverage(tmp_path, monkeypatch):
    uri = f"sqlite:///{tmp_path}/mlflow.db"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.delenv("MLFLOW_EXPERIMENT_ID", raising=False)
    mlflow.set_tracking_uri(uri)
    experiment = mlflow.set_experiment("registry-tests")

    Correctness(name="policy_check").register(experiment_id=experiment.experiment_id)
    monkeypatch.setattr(
        judges,
        "is_correct",
        lambda **kwargs: Feedback(
            name=kwargs["name"],
            value=kwargs["response"] == kwargs["expected_response"],
            rationale="Controlled provider boundary",
        ),
    )
    monkeypatch.setenv(
        "BENCHMARK_SCORERS",
        json.dumps(
            {
                "policy": {
                    "name": "policy_check",
                    "version": 1,
                    "experiment_id": experiment.experiment_id,
                    "required_fields": ["outputs", "expectations"],
                }
            }
        ),
    )
    config = Evaluation(
        description="Refund accuracy",
        scorers=[],
        registered_scorers=["policy"],
        samples=[{"inputs": {"query": "refund?"}, "expectations": {"expected_response": "No"}}],
    )
    plan = await create_plan(config)
    rows = [
        {
            "request_id": "yes",
            "case_id": 0,
            "success": True,
            "inputs": {"query": "refund?"},
            "outputs": "No",
            "expectations": {"expected_response": "No"},
        },
        {
            "request_id": "no-data",
            "case_id": 1,
            "success": True,
            "inputs": {"query": "refund?"},
            "outputs": "No",
            "expectations": {},
        },
    ]
    result = evaluate(rows, plan)
    assert result["status"] == "completed"
    assert result["results"][0]["version"] == 1
    assert result["results"][0]["scored"] == 1
    assert result["results"][0]["pass_rate"] == 1
    assert result["results"][0]["eligible"] == 1
    from mlflow.entities import AssessmentError

    monkeypatch.setattr(
        judges,
        "is_correct",
        lambda **kwargs: Feedback(
            name=kwargs["name"],
            error=AssessmentError(
                error_code="judge_rate_limited", error_message="private registered error"
            ),
            rationale="private registered error",
        ),
    )
    errored = evaluate(rows, plan)
    assessment = errored["results"][0]["assessments"][0]
    assert assessment["request_id"] == "yes"
    assert assessment["status"] == "error"
    assert assessment["error"]["code"] == "evaluation_backend_error"
    assert assessment["rationale"] is None
    assert "private registered error" not in json.dumps(errored)
    plan.registered_scorers[0].definition_hash = "changed"
    assert evaluate(rows, plan)["results"][0]["status"] == "configuration_changed"
    with pytest.raises(ValueError, match="allowlisted"):
        await create_plan(config.model_copy(update={"registered_scorers": ["untrusted"]}))


def test_static_scan_never_executes_or_exports_source(tmp_path):
    source = tmp_path / "agent.py"
    source.write_text(
        'raise RuntimeError("never executed")\nSECRET = "private-key"\n'
        '@function_tool\nasync def policy_db():\n    """Private implementation"""\n'
        '    return SECRET\nsession = SQLiteSession("private-session")\n'
    )
    manifest = scan(source, "openai-agents", "Refund agent")
    assert [(capability.name, capability.kind) for capability in manifest.capabilities] == [
        ("policy_db", "tool"),
        ("SQLiteSession", "memory"),
    ]
    assert "private" not in manifest.model_dump_json().lower()
    assert manifest.source == "static-scan"


async def test_registered_trace_scorer_receives_native_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise registry lookup and native trace-aware evaluation without paid judging."""
    uri = f"sqlite:///{tmp_path}/mlflow.db"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    monkeypatch.delenv("MLFLOW_EXPERIMENT_ID", raising=False)
    mlflow.set_tracking_uri(uri)
    experiment = mlflow.set_experiment("trace-registry-tests")
    RetrievalGroundedness(name="grounded_policy").register(experiment_id=experiment.experiment_id)
    with mlflow.start_span(name="refund_agent") as root:
        root.set_inputs({"query": "refund?"})
        with mlflow.start_span(name="policy", span_type="RETRIEVER") as retrieval:
            retrieval.set_inputs({"query": "refund?"})
            retrieval.set_outputs([{"page_content": "Opened items cannot be refunded."}])
        root.set_outputs("No")
        trace_id = root.trace_id
    mlflow.flush_trace_async_logging()
    trace = mlflow.get_trace(trace_id)
    assert trace is not None
    observed = []

    def controlled_judge(**kwargs: Any) -> Feedback:
        """Control only the model-provider boundary of the actual built-in scorer."""
        observed.append(kwargs)
        return Feedback(
            name=kwargs["name"], value=True, rationale="Controlled groundedness provider"
        )

    monkeypatch.setattr(judges, "is_grounded", controlled_judge)
    monkeypatch.setenv("BENCHMARK_TRACE_ENABLED", "true")
    monkeypatch.setenv("BENCHMARK_TRACE_EXPERIMENT_IDS", json.dumps([experiment.experiment_id]))
    monkeypatch.setenv(
        "BENCHMARK_SCORERS",
        json.dumps(
            {
                "grounded": {
                    "name": "grounded_policy",
                    "version": 1,
                    "experiment_id": experiment.experiment_id,
                    "required_fields": ["inputs", "trace"],
                }
            }
        ),
    )
    config = Evaluation(
        description="Answer from the retrieved policy",
        scorers=[],
        registered_scorers=["grounded"],
        samples=[{"inputs": {"query": "refund?"}}],
    )
    plan = await create_plan(config)
    rows = [
        {
            "request_id": request_id,
            "case_id": 0,
            "success": True,
            "inputs": {"query": "refund?"},
            "outputs": "No",
            "expectations": {},
        }
        for request_id in ("has-trace", "missing-trace")
    ]
    result = evaluate(rows, plan, traces={"has-trace": trace})
    assessment = result["results"][0]
    assert result["status"] == "completed"
    assert assessment["eligible"] == assessment["scored"] == 1
    assert assessment["request_ids"] == ["has-trace"]
    assert assessment["judge_errors"] == 0
    assert len(observed) == 1
    assert observed[0]["response"] == "No"
    assert "Opened items cannot be refunded." in str(observed[0]["context"])
