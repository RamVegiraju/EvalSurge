"""Behavioral tests for evidence selection, concurrency, SSE, and REST lifecycle."""

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from benchmark_agents import api
from benchmark_agents.models import Evaluation, RunRequest, Selection
from benchmark_agents.planner import create_plan, validate_plan


def configuration(**load):
    return RunRequest.model_validate(
        {
            "target": {"url": "http://localhost:9999/chat"},
            "evaluation": {
                "description": "Answer refund questions",
                "scorers": [],
                "samples": [{"inputs": {"query": "Can I refund?"}}],
            },
            "load": {"concurrency": 3, "duration_seconds": 1, "max_requests": 7, **load},
        }
    )


def test_reference_coverage_and_missing_data():
    evaluation = Evaluation.model_validate(
        {
            "description": "Refund policy assistant",
            "samples": [
                {"inputs": {"query": "a"}},
                {"inputs": {"query": "b"}, "expectations": {"expected_response": "yes"}},
            ],
        }
    )
    plan = validate_plan(
        evaluation,
        [Selection(scorer=s, reason="test") for s in ["relevance", "correctness", "groundedness"]],
        "llm",
    )
    assert [r.status for r in plan.recommendations] == ["ready", "ready", "needs_data"]
    assert plan.recommendations[1].eligible_samples == 1
    empty = validate_plan(
        Evaluation(description="Refund assistant"),
        [Selection(scorer="correctness", reason="test")],
        "llm",
    )
    assert empty.recommendations[0].status == "needs_data"


async def test_llm_planner_and_deterministic_validation(monkeypatch):
    monkeypatch.setenv("BENCHMARK_PLANNER_MODEL", "test-planner")

    class Completions:
        async def create(self, **kwargs):
            assert "Refund" in kwargs["messages"][1]["content"]
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps(
                                {
                                    "selections": [
                                        {"scorer": "correctness", "reason": "Policy accuracy"}
                                    ]
                                }
                            )
                        )
                    )
                ]
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    result = await create_plan(Evaluation(description="Refund assistant"), client)
    assert result.source == "llm"
    assert result.recommendations[0].status == "needs_data"


async def test_explicit_selection_does_not_need_planner(monkeypatch):
    monkeypatch.delenv("BENCHMARK_PLANNER_MODEL", raising=False)
    result = await create_plan(Evaluation(description="Assistant", scorers=["relevance"]))
    assert result.source == "explicit"


def test_api_lifecycle_and_persistence(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "ARTIFACTS", tmp_path)

    async def fake_load(request, run_id, cancel, **kwargs):
        return [], {"requests": 0}

    monkeypatch.setattr(api, "run_load", fake_load)
    with TestClient(api.create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        planned = client.post(
            "/v1/evaluation-plans", json={"description": "refund", "scorers": ["correctness"]}
        )
        assert planned.json()["recommendations"][0]["status"] == "needs_data"
        response = client.post("/v1/runs", json=configuration().model_dump(mode="json"))
        assert response.status_code == 202
        run_id = response.json()["id"]
        for _ in range(100):
            result = client.get(f"/v1/runs/{run_id}").json()
            if result["status"] == "completed":
                break
        assert result["status"] == "completed"
        assert (tmp_path / f"{run_id}.json").exists()
        assert client.get("/v1/runs/not-a-uuid").status_code == 422


def test_description_only_load_rejected(tmp_path):
    with TestClient(api.create_app(tmp_path), client=("127.0.0.1", 50000)) as client:
        body = configuration().model_dump(mode="json")
        body["evaluation"]["samples"] = []
        assert client.post("/v1/runs", json=body).status_code == 422
