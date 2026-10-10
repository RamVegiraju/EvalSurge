"""Native readiness evidence with controlled providers and durable recovery checks.

Judge-response substitutions stay at the explicit test-only inline native boundary.
No controlled assessment here establishes real inference or worker ownership;
actual native process/storage regressions remain in their separate test module.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn
from uuid import UUID, uuid4

import mlflow
import pytest
from mlflow.entities import Feedback, MlflowExperimentLocation, Trace
from mlflow.genai import judges as native_judges
from mlflow.genai.scorers import RetrievalGroundedness, RetrievalRelevance, Scorer, builtin_scorers
from mlflow.tracking import MlflowClient

from benchmark_agents import coordinator, judges
from benchmark_agents.coordinator import RunCoordinator
from benchmark_agents.evaluation_preflight import run_evaluation_preflight
from benchmark_agents.models import Evaluation, Plan
from benchmark_agents.planner import create_plan, fingerprint
from benchmark_agents.profiling import collect_profiles
from benchmark_agents.runner import summarize
from benchmark_agents.scorer_registry import load_scorer
from benchmark_agents.storage import append_event, atomic_json
from tests.evaluation_unit_boundary import install_inline_native
from tests.test_template import configuration


@dataclass(frozen=True)
class NativeStore:
    """Test-owned SQLite tracking store with artifacts confined to a temporary path."""

    tracking_uri: str
    experiment_id: str


@pytest.fixture
def native_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[NativeStore]:
    """Isolate native MLflow and operator settings without configuring any provider.

    Args:
        tmp_path: Test-owned database and artifact destination.
        monkeypatch: Restores operator environment and controlled boundaries.

    Yields:
        A real local experiment; no global active experiment is selected.

    The previous tracking URI is restored on teardown. Unexpected catalog provider
    construction fails instead of resolving credentials or dispatching paid calls.
    """
    install_inline_native(monkeypatch)
    previous_uri = mlflow.get_tracking_uri()
    uri = f"sqlite:///{tmp_path}/mlflow.db"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.setenv("MLFLOW_MODEL_CATALOG_URI", "")
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    monkeypatch.setenv("BENCHMARK_SCORERS", "{}")
    monkeypatch.setenv("BENCHMARK_TRACE_ENABLED", "false")
    monkeypatch.setenv("BENCHMARK_CONNECTIONS", "{}")
    monkeypatch.setenv("BENCHMARK_ALLOWED_TARGETS", "[]")
    for name in ("DATABRICKS_CONFIG_PROFILE", "DATABRICKS_HOST", "MLFLOW_EXPERIMENT_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(judges, "judge_client", unexpected_execution)
    mlflow.set_tracking_uri(uri)
    try:
        experiment_id = MlflowClient(tracking_uri=uri).create_experiment(
            "evaluation-readiness-contract",
            artifact_location=str(tmp_path / "mlflow-artifacts"),
        )
        monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", experiment_id)
        yield NativeStore(uri, experiment_id)
    finally:
        mlflow.set_tracking_uri(previous_uri)


def unexpected_execution(*args: Any, **kwargs: Any) -> NoReturn:
    """Reject outbound providers or replayed phases at explicitly forbidden boundaries."""
    pytest.fail("This readiness regression must not invoke this boundary")


async def registered_plan(
    store: NativeStore, monkeypatch: pytest.MonkeyPatch, scorer: Scorer
) -> Plan:
    """Register and freeze an actual trace-required MLflow scorer without inference.

    Args:
        store: Local native registry and trace experiment.
        monkeypatch: Lifetime of the explicit operator-owned scorer/trace allowlist.
        scorer: Native built-in scorer, not a replacement evaluation implementation.

    Returns:
        A frozen exact-version plan with an explicitly authorized trace source.
    """
    import json

    scorer.register(experiment_id=store.experiment_id)
    monkeypatch.setenv("BENCHMARK_TRACE_ENABLED", "true")
    monkeypatch.setenv("BENCHMARK_TRACE_EXPERIMENT_IDS", json.dumps([store.experiment_id]))
    monkeypatch.setenv(
        "BENCHMARK_SCORERS",
        json.dumps(
            {
                "policy": {
                    "name": scorer.name,
                    "version": 1,
                    "experiment_id": store.experiment_id,
                    "required_fields": ["inputs", "trace"],
                }
            }
        ),
    )
    plan = await create_plan(
        Evaluation(
            description="Answer using the retrieved refund policy",
            scorers=[],
            registered_scorers=["policy"],
            samples=[{"inputs": {"query": "Can I refund?"}}],
            max_scored_requests=3,
        )
    )
    assert plan.recommendations[0].status == "ready"
    assert "trace" in plan.registered_scorers[0].required_fields
    return plan


def verified_probe(
    store: NativeStore,
    plan: Plan,
    directory: Path,
    documents: list[dict[str, str]],
) -> tuple[dict[str, Any], Trace]:
    """Create and collect a real scoped/correlated trace for one synthetic probe.

    Args:
        store: Local MLflow experiment, never a remote workspace.
        plan: Frozen authorized trace scope.
        directory: Test-owned content-free profiling output directory.
        documents: Synthetic retriever outputs, including the empty-list case.

    Returns:
        Captured answer and actual Trace accepted by the production collector.

    Only native span logging and local trace reads occur; the hosted agent is not
    invoked. The row's client timings are synthetic milliseconds, not a benchmark.
    """
    run_id, request_id = str(uuid4()), str(uuid4())
    inputs = {"query": "Can I refund?"}
    with mlflow.start_span(
        name="refund_agent",
        span_type="AGENT",
        trace_destination=MlflowExperimentLocation(experiment_id=store.experiment_id),
    ) as root:
        mlflow.update_current_trace(
            metadata={"evalsurge.run_id": run_id, "evalsurge.request_id": request_id}
        )
        root.set_inputs(inputs)
        with mlflow.start_span(name="policy", span_type="RETRIEVER") as retrieval:
            retrieval.set_inputs(inputs)
            retrieval.set_outputs(documents)
        root.set_outputs("No")
        trace_id = root.trace_id
    mlflow.flush_trace_async_logging()
    row = {
        "request_id": request_id,
        "case_id": 0,
        "success": True,
        "inputs": inputs,
        "outputs": "No",
        "expectations": {},
        "trace_id": trace_id,
        "latency_ms": 100,
        "start_offset_ms": 0,
    }
    coverage, traces = collect_profiles([row], run_id, plan.trace_source, directory)
    assert coverage.traced_requests == coverage.total_requests == 1
    trace = traces[request_id]
    assert isinstance(trace, Trace)
    assert trace.info.trace_id == trace_id
    assert trace.info.trace_metadata["evalsurge.request_id"] == request_id
    assert len(trace.data.spans) == 2
    return row, trace


@pytest.mark.parametrize("verdict", [True, False])
async def test_registered_trace_readiness_accepts_verified_native_assessment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    native_store: NativeStore,
    verdict: bool,
) -> None:
    """Accept completed native assessment execution, including a negative quality verdict."""
    plan = await registered_plan(
        native_store, monkeypatch, RetrievalGroundedness(name="grounded_policy")
    )
    row, trace = verified_probe(
        native_store,
        plan,
        tmp_path / "profiles",
        [{"page_content": "Opened items cannot be refunded."}],
    )
    observed: list[dict[str, Any]] = []

    def controlled_judge(**kwargs: Any) -> Feedback:
        """Control only the native scorer's model boundary, retaining native evaluation."""
        observed.append(kwargs)
        return Feedback(name=kwargs["name"], value=verdict, rationale="Controlled policy verdict")

    monkeypatch.setattr(native_judges, "is_grounded", controlled_judge)
    frozen = plan.model_dump(mode="json")
    outcome = run_evaluation_preflight(row, plan, {row["request_id"]: trace})
    assert outcome.status == "passed"
    assert outcome.checked_scorers == ["registered:policy"]
    assert outcome.error is None
    assert len(observed) == 1
    assert observed[0]["name"] == "grounded_policy"
    assert observed[0]["response"] == "No"
    assert "Opened items cannot be refunded." in str(observed[0]["context"])
    assert plan.model_dump(mode="json") == frozen
    runs = MlflowClient(tracking_uri=native_store.tracking_uri).search_runs(
        [native_store.experiment_id],
        filter_string="tags.`evalsurge.phase` = 'evaluation-preflight'",
    )
    assert len(runs) == 1
    assert runs[0].info.status == "FINISHED"
    assert runs[0].data.metrics["grounded_policy/mean"] == float(verdict)


async def test_registered_trace_readiness_blocks_missing_trace_before_scorer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, native_store: NativeStore
) -> None:
    """A trace for a different request does not permit scorer execution or create a run."""
    plan = await registered_plan(
        native_store, monkeypatch, RetrievalGroundedness(name="grounded_policy")
    )
    row, trace = verified_probe(
        native_store,
        plan,
        tmp_path / "profiles",
        [{"page_content": "Opened items cannot be refunded."}],
    )
    monkeypatch.setattr(native_judges, "is_grounded", unexpected_execution)
    for traces in (None, {"another-request": trace}):
        outcome = run_evaluation_preflight(row, plan, traces)
        assert outcome.status == "failed"
        assert outcome.checked_scorers == []
        assert outcome.error is not None
        assert outcome.error.code == "evaluation_missing_trace"
        assert outcome.error.scorer == "registered:policy"
        assert outcome.error.guidance
    assert not MlflowClient(tracking_uri=native_store.tracking_uri).search_runs(
        [native_store.experiment_id]
    )


async def test_registered_scorer_empty_feedback_list_blocks_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, native_store: NativeStore
) -> None:
    """An actual built-in's empty feedback list is not a completed readiness assessment."""
    plan = await registered_plan(
        native_store,
        monkeypatch,
        RetrievalRelevance(name="retrieval_policy", model="openai:/controlled-fixture"),
    )
    row, trace = verified_probe(native_store, plan, tmp_path / "profiles", [])
    monkeypatch.setattr(builtin_scorers, "invoke_judge_model", unexpected_execution)
    registered = load_scorer(plan.registered_scorers[0], plan.tracking_uri)
    assert registered(trace=trace) == []
    outcome = run_evaluation_preflight(row, plan, {row["request_id"]: trace})
    assert outcome.status == "failed"
    assert outcome.checked_scorers == ["registered:policy"]
    assert outcome.error is not None
    assert outcome.error.code == "assessment_missing"
    assert outcome.error.scorer == "registered:policy"
    assert outcome.error.guidance


async def test_post_load_evaluator_raise_preserves_metrics_and_safe_durable_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    native_store: NativeStore,
    successful_preflight: None,
) -> None:
    """Preserve measured rows and metrics when post-load evaluation raises privately."""
    private_detail = "synthetic-private-evaluator-credential"
    row = {
        "request_id": str(uuid4()),
        "case_id": 0,
        "success": True,
        "inputs": {"query": "Can I refund?"},
        "outputs": "No",
        "expectations": {},
        "latency_ms": 125,
        "ttft_ms": 25,
        "first_event_ms": 10,
        "output_tokens": 3,
        "error": None,
    }
    metrics = {**summarize([row], elapsed=0.5, dispatch_seconds=0.25), "load_status": "completed"}
    dispatches: list[str] = []
    evaluations: list[list[dict[str, Any]]] = []

    async def captured_load(
        request: Any, run_id: str, *args: Any, artifact_dir: Path, **kwargs: Any
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Persist one controlled completed load row through the actual journal."""
        dispatches.append(run_id)
        (artifact_dir / run_id).mkdir(parents=True, exist_ok=True)
        append_event(artifact_dir / run_id / "requests.jsonl", {"kind": "completed", "row": row})
        return [row], metrics

    def broken_evaluator(
        rows: list[dict[str, Any]],
        plan: Plan,
        traces: dict[str, Any],
        *,
        cancellation: Any = None,
    ) -> NoReturn:
        """Raise at the post-load boundary without judging or invoking the hosted agent."""
        evaluations.append(rows)
        raise RuntimeError(private_detail)

    monkeypatch.setattr(coordinator, "run_load", captured_load)
    monkeypatch.setattr(coordinator, "evaluate", broken_evaluator)
    request = configuration(max_requests=1)
    request.evaluation.scorers = ["relevance"]
    owner = RunCoordinator(tmp_path / "runs")
    await owner.open()
    try:
        accepted = await owner.submit(request, "post-load-once")
        run_id = UUID(accepted.id)
        report = await owner.wait(run_id, timeout=5)
        assert report.run.status == "completed_with_gaps"
        assert report.run.load_status == report.run.profiling_status == "completed"
        assert report.run.evaluation_status == "failed"
        assert report.run.metrics == metrics
        assert report.total == report.profiling.total_requests == 1
        assert report.run.evaluation["error"]["code"] == "evaluation_backend_error"
        assert report.run.evaluation["error"]["guidance"]
        assert private_detail not in report.model_dump_json()
        assert owner.get_requests(run_id).items == [row]
        assert dispatches == [accepted.id]
        assert evaluations == [[row]]
        assert owner.tasks == owner.runs == owner.cancellations == {}
    finally:
        await owner.close()
    restarted = RunCoordinator(tmp_path / "runs")
    await restarted.open()
    try:
        recovered = restarted.get_report(run_id)
        assert recovered.run.metrics == metrics
        assert recovered.run.evaluation == report.run.evaluation
        replay = await restarted.submit(request, "post-load-once")
        assert replay.id == accepted.id
        assert replay.status == "completed_with_gaps"
        assert dispatches == [accepted.id]
        assert evaluations == [[row]]
        assert private_detail not in recovered.model_dump_json()
    finally:
        await restarted.close()


@pytest.mark.parametrize("readiness_status", ["pending", "running"])
async def test_restart_interrupts_readiness_and_idempotency_never_replays(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    native_store: NativeStore,
    readiness_status: str,
) -> None:
    """Recover abandoned judge readiness separately from a passed excluded inference probe."""
    request = configuration(max_requests=1)
    request.evaluation.scorers = ["relevance"]
    plan = await create_plan(request.evaluation)
    run_id = uuid4()
    key = "readiness-once"
    probe_root = tmp_path / "preflights" / str(run_id)
    atomic_json(probe_root / "preflight.json", {"status": "passed", "request_id": "probe"})
    append_event(
        probe_root / "requests.jsonl",
        {
            "kind": "completed",
            "row": {"request_id": "probe", "case_id": 0, "success": True, "outputs": "No"},
        },
    )
    atomic_json(
        tmp_path / f"{run_id}.json",
        {
            "id": str(run_id),
            "status": "preflighting",
            "load_status": "queued",
            "evaluation_status": "pending",
            "config": request.model_dump(mode="json"),
            "plan": plan.model_dump(mode="json"),
            "trace_coverage": "Readiness is pending",
            "preflight": {"status": "passed", "request_id": "probe"},
            "evaluation_preflight": {
                "status": readiness_status,
                "checked_scorers": ["relevance"] if readiness_status == "running" else [],
                "error": None,
            },
            "idempotency_key_hash": fingerprint(key),
            "request_hash": fingerprint(request.model_dump(mode="json")),
        },
    )
    for boundary in (
        "create_plan",
        "run_preflight",
        "run_evaluation_preflight",
        "run_load",
        "collect_profiles",
        "evaluate",
    ):
        monkeypatch.setattr(coordinator, boundary, unexpected_execution)
    owner = RunCoordinator(tmp_path)
    await owner.open()
    try:
        report = owner.get_report(run_id)
        assert report.run.status == "interrupted"
        assert report.run.preflight.status == "passed"
        assert report.run.preflight.request_id == "probe"
        assert report.run.evaluation_preflight.status == "interrupted"
        assert report.run.evaluation_preflight.checked_scorers == (
            ["relevance"] if readiness_status == "running" else []
        )
        assert report.run.load_status == report.run.evaluation_status == "skipped"
        assert report.run.profiling_status == "skipped"
        assert report.run.metrics == {}
        assert report.total == owner.get_requests(run_id).total == 0
        assert (probe_root / "cancel").exists()
        replay = await owner.submit(request, key)
        assert replay.id == str(run_id)
        assert replay.status == "interrupted"
        history = owner.list_runs(status="interrupted")
        assert history.total == 1
        assert history.items[0].load_status == history.items[0].evaluation_status == "skipped"
        assert owner.tasks == owner.runs == owner.cancellations == {}
    finally:
        await owner.close()
