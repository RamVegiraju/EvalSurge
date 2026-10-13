"""Native SQLite/process regressions only: deterministic storage predicates, no LLM.

No agent or provider is replaced. These tests validate persistence and ownership,
not agent answers, model inference, judge calibration or sustainable capacity.
The explicit storage-only child rejects all network connections.
"""

import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time

import mlflow
import pandas as pd
import pytest
from mlflow.entities import Feedback
from mlflow.genai.scorers import RegexMatch
from mlflow.tracking import MlflowClient

from benchmark_agents.configuration import configured_environment
from benchmark_agents.evaluation_attempts import record_judge_attempt, record_judge_outcome
from benchmark_agents.evaluation_preflight import run_evaluation_preflight
from benchmark_agents.evaluation_process import (
    NATIVE_ENVIRONMENT,
    _stop_worker,
    verify_durable_assessments,
)
from benchmark_agents.evaluator import _verified_metrics, evaluate
from benchmark_agents.judges import rubric_hash
from benchmark_agents.models import Plan, Recommendation, RegisteredScorer
from benchmark_agents.scorer_registry import definition_hash
from benchmark_agents.v2_models import EvaluationOutcome

storage_nonempty = RegexMatch(name="storage_nonempty", pattern=r".+")
storage_trace_spans = RegexMatch(name="storage_trace_spans", pattern=r".+")


@pytest.fixture
def native_store(tmp_path, monkeypatch):
    """Own an actual local SQLite registry and restore caller tracking state."""
    previous = mlflow.get_tracking_uri()
    uri = f"sqlite:///{tmp_path / 'native.db'}"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.setenv("MLFLOW_DISABLE_TELEMETRY", "true")
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    monkeypatch.setenv("BENCHMARK_EVALUATION_STORAGE_ONLY", "true")
    mlflow.set_tracking_uri(uri)
    client = MlflowClient(tracking_uri=uri)
    experiment_id = client.create_experiment(
        "storage-only", artifact_location=str(tmp_path / "artifacts")
    )
    monkeypatch.setenv("MLFLOW_EXPERIMENT_ID", experiment_id)
    yield client, experiment_id, uri
    mlflow.set_tracking_uri(previous)


def frozen_plan(native_store, selected_scorer, *, count=50, trace=False):
    """Freeze an actual native registry definition; no inference registration."""
    _client, experiment_id, uri = native_store
    registered = selected_scorer.register(experiment_id=experiment_id)
    reference = RegisteredScorer(
        alias="storage",
        name=registered.name,
        version=1,
        experiment_id=experiment_id,
        required_fields=["trace"] if trace else ["outputs"],
        definition_hash=definition_hash(registered),
    )
    return Plan(
        source="explicit",
        rubric_hash=rubric_hash(),
        dataset_hash="storage-data",
        evaluation_hash="storage-policy",
        max_scored_requests=count,
        sampling_seed=7,
        description="Storage completeness only; not answer quality",
        tracking_uri=uri,
        registered_scorers=[reference],
        recommendations=[
            Recommendation(
                scorer="registered:storage",
                reason="Storage verification",
                status="ready",
                required_fields=reference.required_fields,
                eligible_samples=count,
                total_samples=count,
            )
        ],
    )


def captures(count=50):
    """Construct storage records, not an agent implementation or model completion."""
    return [
        {
            "request_id": f"storage-{index}",
            "case_id": index % 5,
            "success": True,
            "inputs": {"storage_index": index},
            "outputs": {"stored_index": index},
            "expectations": {},
            "start_offset_ms": index * 10,
        }
        for index in range(count)
    ]


def test_fifty_native_scores_keep_exact_durable_metadata_and_parent_state(native_store, tmp_path):
    plan = frozen_plan(native_store, storage_nonempty)
    previous = dict(os.environ)
    previous_tracking = mlflow.get_tracking_uri()
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    receipt_path = private / "workers.jsonl"
    scoped = dict(os.environ)
    scoped["MLFLOW_GENAI_EVAL_MAX_WORKERS"] = "7"
    scoped["BENCHMARK_EVALUATION_WORKER_RECEIPT_JOURNAL"] = str(receipt_path)
    with configured_environment(scoped):
        result = evaluate(captures(), plan)
    assert result["status"] == "completed"
    assert result["results"][0]["attempted"] == result["results"][0]["scored"] == 50
    assert result["results"][0]["metrics"] == {}
    assert {item["request_id"] for item in result["results"][0]["assessments"]} == {
        row["request_id"] for row in captures()
    }
    assert all(item["status"] == "scored" for item in result["results"][0]["assessments"])
    EvaluationOutcome.model_validate(result)
    assert dict(os.environ) == previous
    assert mlflow.get_tracking_uri() == previous_tracking
    receipt = json.loads(receipt_path.read_text())
    assert receipt["native_settings"] == NATIVE_ENVIRONMENT
    assert receipt["pid"] != os.getpid()
    assert receipt["reaped"] is True
    assert receipt["exit_code"] == 0
    assert not any(
        receipt["warning_counts"][key]
        for key in (
            "pool_exhaustion",
            "tag_write",
            "assessment_write",
            "sqlite_lock",
        )
    )
    assert receipt_path.stat().st_mode & 0o077 == 0
    client, experiment_id, _uri = native_store
    native_traces = client.search_traces(locations=[experiment_id], max_results=100)
    request_traces = [
        trace for trace in native_traces if trace.info.tags.get("evalsurge.request_id")
    ]
    assert len(request_traces) == 50
    run_id = result["results"][0]["mlflow_run_id"]
    for trace in request_traces:
        feedback = [item for item in trace.info.assessments if item.name == "storage_nonempty"]
        assert len(feedback) == 1
        assert feedback[0].metadata["mlflow.assessment.sourceRunId"] == run_id
        assert feedback[0].trace_id == trace.info.trace_id


def test_registered_outputs_scorer_preserves_actual_native_trace_transfer(native_store):
    """Verify native transfer/eligibility, not a trace-consuming judge's semantics."""
    plan = frozen_plan(native_store, storage_trace_spans, count=2, trace=True)
    client, experiment_id, _uri = native_store
    rows, traces = captures(2), {}
    with mlflow.start_run(experiment_id=experiment_id):
        for row in rows:
            with mlflow.start_span("storage-source-record") as span:
                span.set_inputs(row["inputs"])
                span.set_outputs(row["outputs"])
                mlflow.update_current_trace(tags={"evalsurge.request_id": row["request_id"]})
            mlflow.flush_trace_async_logging()
            trace = client.get_trace(span.trace_id)
            assert trace.data.spans
            traces[row["request_id"]] = trace
    result = evaluate(rows, plan, traces)
    assert result["status"] == "completed"
    assert result["results"][0]["scored"] == 2
    assert all(item["status"] == "scored" for item in result["results"][0]["assessments"])
    EvaluationOutcome.model_validate(result)
    run_id = result["results"][0]["mlflow_run_id"]
    persisted = client.search_traces(locations=[experiment_id], max_results=20)
    evaluation_traces = [
        trace
        for trace in persisted
        if any(
            (item.metadata or {}).get("mlflow.assessment.sourceRunId") == run_id
            for item in trace.info.assessments
        )
    ]
    assert len(evaluation_traces) == 2
    for trace in evaluation_traces:
        request_id = trace.info.tags["evalsurge.request_id"]
        assert [
            (span.name, span.span_type, span.inputs, span.outputs) for span in trace.data.spans
        ] == [
            (span.name, span.span_type, span.inputs, span.outputs)
            for span in traces[request_id].data.spans
        ]


@pytest.mark.parametrize("_iteration", range(6))
def test_owner_timeout_reaps_child_without_provider_calls(native_store, monkeypatch, _iteration):
    from benchmark_agents import evaluation_process

    diagnostics = []
    native_failure, native_cleanup = (
        evaluation_process._phase_failure,
        evaluation_process._stop_worker,
    )

    def diagnostic_failure(code):
        diagnostics.append(code)
        return native_failure(code)

    def diagnostic_cleanup(process):
        try:
            return native_cleanup(process)
        except Exception as error:
            diagnostics.append(type(error).__name__)
            raise

    monkeypatch.setattr(evaluation_process, "_phase_failure", diagnostic_failure)
    monkeypatch.setattr(evaluation_process, "_stop_worker", diagnostic_cleanup)
    previous_trace = sys.gettrace()

    def safe_exception_categories(frame, event, argument):
        if event == "exception" and frame.f_code.co_filename == evaluation_process.__file__:
            diagnostics.append(f"{argument[0].__name__}:{frame.f_lineno}")
        return safe_exception_categories

    plan = frozen_plan(native_store, storage_nonempty, count=1)
    monkeypatch.setenv("BENCHMARK_EVALUATION_TIMEOUT_SECONDS", "0.3")
    started = time.monotonic()
    try:
        sys.settrace(safe_exception_categories)
        result = evaluate(captures(1), plan)
    finally:
        sys.settrace(previous_trace)
    assert result["status"] == "failed"
    assert result["error"]["code"] == "evaluation_worker_timeout", diagnostics
    assert time.monotonic() - started < 5
    EvaluationOutcome.model_validate(result)


def test_owner_cancellation_is_observed_during_native_startup(native_store):
    plan = frozen_plan(native_store, storage_nonempty, count=1)
    cancellation = threading.Event()
    timer = threading.Timer(0.3, cancellation.set)
    timer.start()
    try:
        result = evaluate(captures(1), plan, cancellation=cancellation)
    finally:
        timer.cancel()
        timer.join()
    assert result["error"]["code"] == "evaluation_worker_cancelled"
    EvaluationOutcome.model_validate(result)


@pytest.mark.parametrize(
    "failure,code,status",
    [
        ("timeout", "evaluation_worker_timeout", "failed"),
        ("cancelled", "evaluation_worker_cancelled", "cancelled"),
        ("startup", "evaluation_worker_failed", "failed"),
    ],
)
def test_readiness_preserves_worker_failure_without_provider_calls(
    native_store, monkeypatch, failure, code, status
):
    """Retain actual process/OS failures instead of inventing absent assessments.

    Timeout owns a real storage-only native child. Cancellation stops before
    worker startup. The startup case controls only OS process creation with a
    PermissionError; no agent, judge response or provider transport is stubbed.
    """
    from benchmark_agents import evaluation_process

    plan = frozen_plan(native_store, storage_nonempty, count=1)
    cancellation = threading.Event()
    if failure == "timeout":
        monkeypatch.setenv("BENCHMARK_EVALUATION_TIMEOUT_SECONDS", "0.3")
    elif failure == "cancelled":
        cancellation.set()
    else:

        def denied_startup(*args, **kwargs):
            """Fail before native worker creation without replacing any inference."""
            raise PermissionError("private OS process-startup detail")

        monkeypatch.setattr(evaluation_process.subprocess, "Popen", denied_startup)
    started = time.monotonic()
    outcome = run_evaluation_preflight(captures(1)[0], plan, cancellation=cancellation)
    assert outcome.status == status
    assert outcome.checked_scorers == ["registered:storage"]
    assert outcome.error.code == code
    assert outcome.error.scorer == "registered:storage"
    assert outcome.error.message and outcome.error.guidance
    assert "private OS process-startup detail" not in outcome.model_dump_json()
    assert time.monotonic() - started < 5


def test_attempt_cap_counts_actual_reservations_not_outcomes(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    path = private / "attempts.jsonl"
    assert record_judge_attempt(path, 2) == 1
    record_judge_outcome(path, 1, http_status=200)
    assert record_judge_attempt(path, 2) == 2
    with pytest.raises(RuntimeError, match="budget exhausted"):
        record_judge_attempt(path, 2)
    assert path.stat().st_mode & 0o077 == 0
    assert [event["kind"] for event in map(json.loads, path.read_text().splitlines())] == [
        "attempt",
        "outcome",
        "attempt",
    ]


def test_unsafe_journal_fails_before_dispatch_reservation(tmp_path):
    """Create an explicitly unsafe file even when the invoking shell uses umask 077."""
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    path = private / "attempts.jsonl"
    path.touch(mode=0o644)
    path.chmod(0o644)
    assert path.stat().st_mode & 0o077
    with pytest.raises(RuntimeError, match="private regular file"):
        record_judge_attempt(path, 2)
    assert path.read_text() == ""


def test_result_rows_without_durable_trace_are_not_counted():
    frame = pd.DataFrame(
        [
            {
                "tags": {"evalsurge.request_id": "storage-0"},
                "storage_nonempty/value": True,
            }
        ]
    )
    verified = verify_durable_assessments(frame, captures(1), "storage_nonempty", "run", None)
    assert verified.empty


@pytest.mark.parametrize(
    "failure", ["missing_run", "wrong_run", "duplicate", "invalid", "wrong_tag"]
)
def test_exact_native_feedback_membership_rejects_invalid_evidence(
    native_store, failure, monkeypatch
):
    client, experiment_id, _uri = native_store
    with (
        mlflow.start_run(experiment_id=experiment_id),
        mlflow.start_span("native-storage-source") as span,
    ):
        span.set_inputs({"storage": 1})
        span.set_outputs({"stored": 1})
        mlflow.update_current_trace(tags={"evalsurge.request_id": "storage-0"})
    mlflow.flush_trace_async_logging()
    source_run = "foreign" if failure == "wrong_run" else "evaluation-run"
    metadata = {} if failure == "missing_run" else {"mlflow.assessment.sourceRunId": source_run}
    mlflow.log_assessment(
        trace_id=span.trace_id,
        assessment=Feedback(
            name="storage_nonempty",
            value=True,
            metadata=metadata,
            valid=failure != "invalid",
        ),
    )
    if failure == "duplicate":
        mlflow.log_feedback(
            trace_id=span.trace_id,
            name="storage_nonempty",
            value=False,
            metadata=metadata,
        )
    elif failure == "wrong_tag":
        client.set_trace_tag(span.trace_id, "evalsurge.request_id", "foreign-request")
    trace = client.get_trace(span.trace_id)
    if failure == "invalid":
        # Native SQLite creation currently forces valid=True. Exercise this
        # verifier branch with a mutated actual native entity, not a provider.
        trace.info.assessments[0].valid = False
        monkeypatch.setattr(client, "get_trace", lambda _identifier: trace)
    frame = pd.DataFrame(
        [
            {
                "tags": {"evalsurge.request_id": "storage-0"},
                "trace": trace.to_json(),
                "storage_nonempty/value": True,
            }
        ]
    )
    verified = verify_durable_assessments(
        frame,
        captures(1),
        "storage_nonempty",
        "evaluation-run",
        client,
    )
    assert verified.empty


def test_durable_values_determine_means_not_transient_native_results(native_store):
    client, experiment_id, _uri = native_store
    with (
        mlflow.start_run(experiment_id=experiment_id),
        mlflow.start_span("native-storage-source") as span,
    ):
        span.set_inputs({"storage": 1})
        span.set_outputs({"stored": 1})
        mlflow.update_current_trace(tags={"evalsurge.request_id": "storage-0"})
    mlflow.flush_trace_async_logging()
    mlflow.log_feedback(
        trace_id=span.trace_id,
        name="storage_nonempty",
        value=False,
        metadata={"mlflow.assessment.sourceRunId": "evaluation-run"},
    )
    trace = client.get_trace(span.trace_id)
    frame = pd.DataFrame(
        [
            {
                "tags": {"evalsurge.request_id": "storage-0"},
                "trace": trace.to_json(),
                "storage_nonempty/value": True,
            }
        ]
    )
    verified = verify_durable_assessments(
        frame,
        captures(1),
        "storage_nonempty",
        "evaluation-run",
        client,
    )
    values = verified["storage_nonempty/value"].tolist()
    assert values == [False]
    assert _verified_metrics("storage_nonempty", values, 1) == {"storage_nonempty/mean": 0.0}
    assert _verified_metrics("storage_nonempty", values, 2) == {}
    duplicates = verify_durable_assessments(
        pd.concat([frame, frame]),
        captures(1),
        "storage_nonempty",
        "evaluation-run",
        client,
    )
    assert len(duplicates) == 2


def test_cancellation_during_actual_native_writes_reaps_worker(native_store, tmp_path):
    plan = frozen_plan(native_store, storage_nonempty, count=500)
    cancellation, finished = threading.Event(), threading.Event()
    observed = {"assessments": 0}
    database = native_store[2].removeprefix("sqlite:///")
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    path = private / "workers.jsonl"
    scoped = dict(os.environ)
    scoped["BENCHMARK_EVALUATION_WORKER_RECEIPT_JOURNAL"] = str(path)

    def observe_native_persistence():
        """Wait for real durable feedback, then ask the owner to stop its worker."""
        stop = time.monotonic() + 20
        while not finished.is_set() and time.monotonic() < stop:
            with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
                count = connection.execute("SELECT COUNT(*) FROM assessments").fetchone()[0]
            if count:
                observed["assessments"] = count
                cancellation.set()
                return
            finished.wait(0.03)
        cancellation.set()

    observer = threading.Thread(target=observe_native_persistence)
    observer.start()
    try:
        with configured_environment(scoped):
            result = evaluate(captures(500), plan, cancellation=cancellation)
    finally:
        finished.set()
        observer.join(timeout=2)
    assert observed["assessments"] > 0
    assert result["error"]["code"] == "evaluation_worker_cancelled"
    receipt = json.loads(path.read_text())
    assert receipt["reaped"] is True
    assert receipt["process_group_cleanup"] in {"not_present", "terminated", "kill_sent"}


def test_complete_large_finite_scores_keep_a_finite_mean():
    maximum = sys.float_info.max
    assert _verified_metrics("large", [maximum, maximum], 2) == {"large/mean": maximum}
    assert _verified_metrics("large", [maximum, -maximum], 2) == {"large/mean": 0.0}
    assert _verified_metrics("large", [float("inf")], 1) == {}
    assert _verified_metrics("large", [float("nan")], 1) == {}


def test_owned_group_cleanup_kills_descendant_after_leader_exit(tmp_path):
    """Exercise genuine process ownership only; neither process can call a model."""
    marker = tmp_path / "heartbeat"
    child_source = (
        "import signal,sys,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); marker=Path(sys.argv[1]); "
        "\nwhile True:\n marker.write_text(str(time.monotonic_ns())); time.sleep(.03)\n"
    )
    leader_source = (
        "import subprocess,sys,time; from pathlib import Path; "
        "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]]); "
        "marker=Path(sys.argv[2]); "
        "\nwhile not marker.exists(): time.sleep(.01)\n"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", leader_source, child_source, str(marker)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        process.wait(timeout=5)
        assert marker.exists()
        cleanup = _stop_worker(process)
        assert cleanup in {"terminated", "kill_sent"}
        value = marker.read_text()
        time.sleep(0.15)
        assert marker.read_text() == value
    finally:
        _stop_worker(process)


def test_no_ready_scorers_never_start_worker_or_serialize_traces(native_store, monkeypatch):
    from benchmark_agents import evaluation_process

    def forbidden(*_args, **_kwargs):
        pytest.fail("Performance-only evaluation must not enter the native worker")

    monkeypatch.setattr(evaluation_process, "evaluate_in_process", forbidden)
    plan = frozen_plan(native_store, storage_nonempty).model_copy(update={"recommendations": []})
    assert evaluate(captures(), plan, {"unserializable": object()}) == {
        "status": "no_ready_scorers",
        "results": [],
        "needs_data": [],
    }


def test_denied_signal_zero_does_not_mask_owned_timeout(native_store, monkeypatch):
    """Control only the OS-probe error; real signals stop a real no-inference child."""
    from benchmark_agents import evaluation_process

    genuine_kill = os.killpg

    def denied_probe(group_id, requested_signal):
        if requested_signal == 0:
            raise PermissionError("Controlled OS probe denial")
        return genuine_kill(group_id, requested_signal)

    monkeypatch.setattr(evaluation_process.os, "killpg", denied_probe)
    monkeypatch.setenv("BENCHMARK_EVALUATION_TIMEOUT_SECONDS", "0.3")
    plan = frozen_plan(native_store, storage_nonempty, count=1)
    result = evaluate(captures(1), plan)
    assert result["error"]["code"] == "evaluation_worker_timeout"


def test_group_state_inventory_reports_a_genuine_owned_live_process():
    """Inspect only PID/group/state of a real idle Python child, without inference."""
    from benchmark_agents.evaluation_process import _has_running_group_member

    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert _has_running_group_member(process.pid) is True
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)


@pytest.mark.parametrize("deadline", ["0.3", "30"])
def test_cleanup_failure_preserves_original_phase_failure_and_private_receipt(
    native_store,
    tmp_path,
    monkeypatch,
    deadline,
):
    """Exercise a controlled cleanup error after genuinely stopping a native child."""
    from benchmark_agents import evaluation_process

    genuine_cleanup = evaluation_process._stop_worker

    def stopped_but_unverified(process):
        genuine_cleanup(process)
        raise RuntimeError("Controlled ownership-verification error")

    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    path = private / "workers.jsonl"
    monkeypatch.setattr(evaluation_process, "_stop_worker", stopped_but_unverified)
    monkeypatch.setenv("BENCHMARK_EVALUATION_WORKER_RECEIPT_JOURNAL", str(path))
    monkeypatch.setenv("BENCHMARK_EVALUATION_TIMEOUT_SECONDS", deadline)
    result = evaluate(captures(1), frozen_plan(native_store, storage_nonempty, count=1))
    assert result["status"] == "failed"
    assert result["error"]["code"] == (
        "evaluation_worker_timeout" if deadline == "0.3" else "evaluation_worker_failed"
    )
    receipt = json.loads(path.read_text())
    assert receipt["cleanup_error"] == "worker_cleanup_failed"
    assert receipt["process_group_cleanup"] == "unverified"
    assert receipt["reaped"] is True
    if deadline == "30":
        assert result["results"][0]["scored"] == 1
    EvaluationOutcome.model_validate(result)
