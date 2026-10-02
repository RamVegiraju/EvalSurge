"""Exercise native MLflow evaluation with a controlled judge response."""

from benchmark_agents.evaluator import evaluate
from benchmark_agents.models import Evaluation
from benchmark_agents.planner import create_plan


async def test_native_mlflow_captured_outputs(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    import mlflow

    from benchmark_agents import judges

    monkeypatch.setenv("BENCHMARK_JUDGE_MODEL", "controlled-test")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.delenv("MLFLOW_EXPERIMENT_ID", raising=False)
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path}/mlflow.db")

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def create(self, **kwargs):
            assert kwargs["model"] == "controlled-test"
            assert "refund" in kwargs["messages"][1]["content"]
            assert "Opened items are not refundable." in kwargs["messages"][1]["content"]
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps({"result": "yes", "rationale": "Controlled fixture"})
                        )
                    )
                ]
            )

    monkeypatch.setattr(judges, "judge_client", Client)
    config = Evaluation(description="Refund assistant", scorers=["relevance"])
    plan = await create_plan(config)
    plan.judge_host = "https://fixture.example"
    rows = [
        {
            "success": True,
            "case_id": 0,
            "request_id": "captured-1",
            "inputs": {"query": "Can I refund?"},
            "outputs": "Opened items are not refundable.",
            "expectations": {},
        }
    ]
    result = evaluate(rows, plan, config)
    assert result["status"] == "completed"
    assert result["results"][0]["scored"] == 1
    assert result["results"][0]["metrics"]["relevance_to_query/mean"] == 1
    assert mlflow.get_run(result["results"][0]["mlflow_run_id"])
