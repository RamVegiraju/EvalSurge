"""Exercise native MLflow evaluation with a controlled judge response."""

from benchmark_agents.models import Evaluation
from benchmark_agents.planner import create_plan
from tests.evaluation_unit_boundary import evaluate_inline_native as evaluate


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
            assert kwargs == {
                "profile": "frozen-profile",
                "host": "https://fixture.example",
                "timeout": 7,
                "max_retries": 0,
            }
            self.chat = SimpleNamespace(completions=self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def create(self, **kwargs):
            assert kwargs["model"] == "controlled-test"
            assert kwargs["max_completion_tokens"] == 128
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
    plan.judge_profile = "frozen-profile"
    plan.judge_host = "https://fixture.example"
    plan.judge_timeout_seconds = 7
    plan.judge_max_retries = 0
    plan.judge_max_completion_tokens = 128
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
    result = evaluate(rows, plan)
    assert result["status"] == "completed"
    assert result["results"][0]["scored"] == 1
    assert result["results"][0]["metrics"]["relevance_to_query/mean"] == 1
    assessment = result["results"][0]["assessments"][0]
    assert assessment["request_id"] == "captured-1"
    assert assessment["status"] == "passed"
    assert assessment["rationale"] == "Controlled fixture"
    native_run = mlflow.get_run(result["results"][0]["mlflow_run_id"])
    assert result["results"][0]["mlflow_experiment_id"] == native_run.info.experiment_id


async def test_native_catalog_scoring_with_partial_trace_coverage(tmp_path, monkeypatch):
    """Score traced and untraced answers together without a nullable trace column."""
    import json
    from types import SimpleNamespace

    import mlflow

    from benchmark_agents import judges

    uri = f"sqlite:///{tmp_path}/mlflow.db"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    monkeypatch.delenv("MLFLOW_EXPERIMENT_ID", raising=False)
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment("partial-trace-regression")
    with mlflow.start_span("agent") as root:
        root.set_inputs({"query": "Can I refund?"})
        root.set_outputs("No")
        trace_id = root.trace_id
    trace = mlflow.get_trace(trace_id)
    assert trace is not None
    calls = []

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps({"result": "no", "rationale": "Controlled verdict"})
                        )
                    )
                ]
            )

    monkeypatch.setattr(judges, "judge_client", Client)
    plan = await create_plan(Evaluation(description="Refund assistant", scorers=["relevance"]))
    plan.judge_model = "controlled-test"
    plan.judge_host = "https://fixture.example"
    rows = [
        {
            "success": True,
            "case_id": index,
            "request_id": f"captured-{index}",
            "inputs": {"query": "Can I refund?"},
            "outputs": "No",
            "expectations": {},
            "start_offset_ms": index,
        }
        for index in range(2)
    ]
    result = evaluate(rows, plan, {"captured-0": trace})
    assert result["status"] == "completed"
    assert result["results"][0]["scored"] == 2
    assert result["results"][0]["pass_rate"] == 0
    assessments = result["results"][0]["assessments"]
    assert {item["request_id"] for item in assessments} == {"captured-0", "captured-1"}
    assert all(item["status"] == "failed" for item in assessments)
    assert all(item["rationale"] == "Controlled verdict" for item in assessments)
    assert len(calls) == 2


async def test_native_mixed_verdicts_and_provider_error_are_request_correlated(
    tmp_path, monkeypatch
):
    """Persist reasons and safe native errors for repeated inputs without paid calls."""
    import json
    from types import SimpleNamespace
    from uuid import uuid4

    import httpx
    import mlflow
    from fastapi.testclient import TestClient
    from openai import RateLimitError

    from benchmark_agents import judges
    from benchmark_agents.api import create_app
    from benchmark_agents.storage import atomic_json
    from evalsurge import EvalSurge
    from tests.test_template import configuration

    uri = f"sqlite:///{tmp_path}/mlflow.db"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    monkeypatch.delenv("MLFLOW_EXPERIMENT_ID", raising=False)
    mlflow.set_tracking_uri(uri)

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def create(self, **kwargs):
            prompt = kwargs["messages"][1]["content"]
            if "error-answer" in prompt:
                raise RateLimitError(
                    "secret-provider-body",
                    response=httpx.Response(
                        429, request=httpx.Request("POST", "https://fixture.example")
                    ),
                    body={"secret": "secret-provider-body"},
                )
            failed = "wrong-answer" in prompt
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps(
                                {
                                    "result": "no" if failed else "yes",
                                    "rationale": "Missed policy." if failed else "Accurate.",
                                }
                            )
                        )
                    )
                ]
            )

    monkeypatch.setattr(judges, "judge_client", Client)
    plan = await create_plan(Evaluation(description="Refund assistant", scorers=["relevance"]))
    plan.judge_model = "controlled-test"
    plan.judge_host = "https://fixture.example"
    rows = [
        {
            "success": True,
            "case_id": index,
            "request_id": f"captured-{index}",
            "inputs": {"query": "Repeated input"},
            "outputs": output,
            "expectations": {},
            "start_offset_ms": index,
        }
        for index, output in enumerate(["good-answer", "wrong-answer", "error-answer"])
    ]
    result = evaluate(rows, plan)
    assert result["status"] == "completed_with_errors"
    criterion = result["results"][0]
    assert criterion["scored"] == 2
    assert criterion["judge_errors"] == 1
    assert criterion["pass_rate"] == 0.5
    assert criterion["error"]["http_status"] == 429
    by_request = {item["request_id"]: item for item in criterion["assessments"]}
    assert by_request["captured-0"]["status"] == "passed"
    assert by_request["captured-1"]["status"] == "failed"
    assert by_request["captured-1"]["rationale"] == "Missed policy."
    assert by_request["captured-2"]["status"] == "error"
    assert by_request["captured-2"]["error"]["code"] == "judge_rate_limited"
    assert by_request["captured-2"]["rationale"] is None
    assert "secret-provider-body" not in json.dumps(result)
    native = mlflow.search_traces(
        locations=[criterion["mlflow_experiment_id"]],
        run_id=criterion["mlflow_run_id"],
        return_type="list",
    )
    assert len(native) == 3
    assert {trace.info.tags["evalsurge.request_id"] for trace in native} == set(by_request)
    run_id = str(uuid4())
    directory = tmp_path / "report-service"
    snapshot = directory / f"{run_id}.json"
    atomic_json(
        snapshot,
        {
            "id": run_id,
            "status": "completed_with_gaps",
            "load_status": "completed",
            "evaluation_status": result["status"],
            "profiling_status": "completed",
            "config": configuration().model_dump(mode="json"),
            "plan": plan.model_dump(mode="json"),
            "trace_coverage": "Controlled native assessment fixture",
            "metrics": {},
            "evaluation": result,
            "requests": [],
        },
    )
    original = snapshot.read_bytes()
    async with EvalSurge.local_async(artifact_dir=directory) as client:
        report = await client.report(run_id)
        assert report.run.evaluation["results"][0]["assessments"] == criterion["assessments"]
    monkeypatch.setenv("BENCHMARK_API_KEY", "private-test-key")
    with TestClient(create_app(directory), client=("127.0.0.1", 50000)) as client:
        for suffix in ("", "/report"):
            route = f"/v1/runs/{run_id}{suffix}"
            assert client.get(route).status_code == 401
            response = client.get(route, headers={"X-API-Key": "private-test-key"})
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "no-store"
            run = response.json()["run"] if suffix else response.json()
            assert run["evaluation"]["results"][0]["assessments"] == criterion["assessments"]
    assert snapshot.read_bytes() == original
