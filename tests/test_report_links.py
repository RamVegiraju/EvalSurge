"""Check experiment links against frozen store authority without external requests."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from benchmark_agents.api import create_app
from benchmark_agents.models import Plan, TraceSource
from benchmark_agents.report_links import experiment_links
from benchmark_agents.storage import atomic_json
from tests.test_report_ui import render
from tests.test_template import configuration


@pytest.fixture
def plan():
    return Plan(
        source="explicit",
        rubric_hash="fixture",
        dataset_hash="fixture",
        evaluation_hash="fixture",
        max_scored_requests=5,
        sampling_seed=42,
        description="Report links",
        recommendations=[],
        tracking_uri="https://tracking.example/prefix",
        trace_source=TraceSource(
            tracking_uri="https://tracking.example/prefix", experiment_ids=["11", "12"]
        ),
    )


def test_http_experiment_links_keep_store_prefix_and_merge_scopes(plan, monkeypatch):
    monkeypatch.delenv("BENCHMARK_MLFLOW_UI_URL", raising=False)
    links = experiment_links(
        plan, {"results": [{"mlflow_experiment_id": "12"}, {"mlflow_experiment_id": "15"}]}
    )
    assert [link.model_dump() for link in links] == [
        {
            "experiment_id": "11",
            "url": "https://tracking.example/prefix/#/experiments/11",
            "scopes": ["traces"],
        },
        {
            "experiment_id": "12",
            "url": "https://tracking.example/prefix/#/experiments/12",
            "scopes": ["traces", "evaluation"],
        },
        {
            "experiment_id": "15",
            "url": "https://tracking.example/prefix/#/experiments/15",
            "scopes": ["evaluation"],
        },
    ]


def test_local_store_requires_an_explicit_same_store_ui(plan, monkeypatch):
    uri = "sqlite:///private/mlflow.db"
    plan.tracking_uri = plan.trace_source.tracking_uri = uri
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.delenv("BENCHMARK_MLFLOW_UI_URL", raising=False)
    assert experiment_links(plan, {}) == []
    monkeypatch.setenv("BENCHMARK_MLFLOW_UI_URL", "http://127.0.0.1:5000")
    links = experiment_links(plan, {})
    assert links[0].url == "http://127.0.0.1:5000/#/experiments/11"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "sqlite:///other/mlflow.db")
    assert experiment_links(plan, {}) == []


def test_databricks_ui_is_explicit_and_never_inferred_from_the_judge_host(plan, monkeypatch):
    monkeypatch.delenv("BENCHMARK_MLFLOW_UI_URL", raising=False)
    plan.tracking_uri = plan.trace_source.tracking_uri = "databricks://selected-workspace"
    plan.judge_profile = "another-workspace"
    plan.judge_host = "https://judge.example"
    assert experiment_links(plan, {}) == []
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "databricks://selected-workspace")
    monkeypatch.setenv("BENCHMARK_MLFLOW_UI_URL", "https://workspace.example")
    links = experiment_links(plan, {})
    assert links[0].url == "https://workspace.example/ml/experiments/11"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "databricks://another-workspace")
    assert experiment_links(plan, {}) == []


@pytest.mark.parametrize(
    "base",
    [
        "javascript:alert(1)",
        "file:///private/mlflow.db",
        "//tracking.example",
        "http://remote.example",
        "https://user:secret@tracking.example",
        "https://tracking.example?token=secret",
        "https://tracking.example?",
        "https://tracking.example#fragment",
        "https://tracking.example:invalid",
        "https://tracking.example\\@other.example",
        "https://track\ning.example",
    ],
)
def test_unsafe_ui_destinations_are_omitted(plan, monkeypatch, base):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", plan.tracking_uri)
    monkeypatch.setenv("BENCHMARK_MLFLOW_UI_URL", base)
    assert experiment_links(plan, {}) == []


def test_legacy_missing_ids_and_untrusted_identifiers_do_not_invent_links(plan, monkeypatch):
    monkeypatch.delenv("BENCHMARK_MLFLOW_UI_URL", raising=False)
    plan.trace_source = None
    assert experiment_links(plan, {"results": [{"mlflow_run_id": "existing-run"}]}) == []
    links = experiment_links(
        plan,
        {
            "results": [
                {"mlflow_experiment_id": "../another"},
                {"mlflow_experiment_id": "x?token=secret"},
                {"mlflow_experiment_id": "<script>"},
                {"mlflow_experiment_id": "x" * 129},
                {"mlflow_experiment_id": 1},
                {"mlflow_experiment_id": "15"},
            ]
        },
    )
    assert [link.experiment_id for link in links] == ["15"]


def test_links_are_bounded_and_do_not_assume_shared_trace_and_eval_stores(plan, monkeypatch):
    monkeypatch.delenv("BENCHMARK_MLFLOW_UI_URL", raising=False)
    plan.trace_source.tracking_uri = "https://traces.example"
    links = experiment_links(
        plan, {"results": [{"mlflow_experiment_id": str(identifier)} for identifier in range(30)]}
    )
    assert len(links) == 20
    assert links[0].url == "https://traces.example/#/experiments/11"
    assert links[2].url == "https://tracking.example/prefix/#/experiments/0"


def test_authenticated_rest_report_links_do_not_mutate_historical_evidence(
    plan, tmp_path, monkeypatch
):
    run_id = str(uuid4())
    snapshot = tmp_path / f"{run_id}.json"
    atomic_json(
        snapshot,
        {
            "id": run_id,
            "status": "completed",
            "load_status": "completed",
            "evaluation_status": "completed",
            "profiling_status": "completed",
            "config": configuration().model_dump(mode="json"),
            "plan": plan.model_dump(mode="json"),
            "trace_coverage": "Historical fixture",
            "metrics": {},
            "evaluation": {"results": [{"mlflow_experiment_id": "12"}]},
            "requests": [],
        },
    )
    original = snapshot.read_bytes()
    monkeypatch.setenv("BENCHMARK_API_KEY", "private-test-key")
    monkeypatch.delenv("BENCHMARK_MLFLOW_UI_URL", raising=False)
    with TestClient(create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        route = f"/v1/runs/{run_id}/report"
        assert client.get(route).status_code == 401
        response = client.get(route, headers={"X-API-Key": "private-test-key"})
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        report = response.json()
        assert report["mlflow_experiments"][1]["scopes"] == ["traces", "evaluation"]
        output = render(report)
        assert "Open MLflow experiment 11" in output["nodes"]["mlflow-links"]["text"]
    assert snapshot.read_bytes() == original
