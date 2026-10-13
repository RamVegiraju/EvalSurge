"""Native MLflow export-visibility regressions; no agents, models or provider stubs.

Exercise the actual incremental span write followed by complete trace metadata
write used by MLflow's V3 exporter. Only the retry clock is controlled; native
storage, reads and traces are real. This is not live-inference validation.
"""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import mlflow
import pytest
from mlflow.entities.trace_location import MlflowExperimentLocation, TraceLocation
from mlflow.tracing.client import TracingClient
from mlflow.tracking import MlflowClient

from benchmark_agents import profiling
from benchmark_agents.configuration import configured_environment
from benchmark_agents.models import Evaluation, TraceSource
from benchmark_agents.planner import create_plan


class CountingClient(MlflowClient):
    """Count real native reads without replacing or modifying their responses."""

    def __init__(self, uri: str) -> None:
        super().__init__(tracking_uri=uri)
        self.reads = 0

    def get_trace(self, trace_id: str, display: bool = False, flush: bool = False) -> Any:
        self.reads += 1
        return super().get_trace(trace_id, display=display, flush=flush)


@pytest.fixture
def incremental_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Persist real spans before metadata, exactly as the native V3 exporter can.

    Two local SQLite stores isolate the original complete trace from the collector
    store. Native TracingClient methods are exporter internals, inspected against
    the installed MLflow version; they do not substitute provider or trace content.
    Restore process tracking configuration after draining local telemetry.
    """
    previous = mlflow.get_tracking_uri()
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    origin_uri = f"sqlite:///{tmp_path}/origin.db"
    target_uri = f"sqlite:///{tmp_path}/incremental.db"
    mlflow.set_tracking_uri(origin_uri)
    origin_experiment = MlflowClient(tracking_uri=origin_uri).create_experiment("origin")
    try:
        with mlflow.start_span(
            "actual_telemetry", trace_destination=MlflowExperimentLocation(origin_experiment)
        ) as span:
            mlflow.update_current_trace(
                metadata={"evalsurge.run_id": "run", "evalsurge.request_id": "request"}
            )
            span.set_outputs(2 + 3)
        mlflow.flush_trace_async_logging()
        trace = MlflowClient(tracking_uri=origin_uri).get_trace(span.trace_id, display=False)
        client = CountingClient(target_uri)
        experiment = client.create_experiment("incremental")
        exporter = TracingClient(tracking_uri=target_uri)
        exporter.log_spans(experiment, trace.data.spans)
        info = replace(trace.info, trace_location=TraceLocation.from_experiment_id(experiment))
        row = {
            "request_id": "request",
            "case_id": 0,
            "success": True,
            "trace_id": trace.info.trace_id,
            "latency_ms": 1000,
        }
        yield (
            exporter,
            info,
            row,
            client,
            TraceSource(tracking_uri=target_uri, experiment_ids=[experiment]),
        )
    finally:
        mlflow.flush_trace_async_logging()
        mlflow.set_tracking_uri(previous)


@pytest.mark.parametrize("absent", ["both", "run", "request"])
def test_incremental_metadata_visibility_retries_same_native_trace(
    absent: str, incremental_trace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing correlation can land later; readiness must not accept it prematurely."""
    exporter, info, row, client, source = incremental_trace
    if absent != "both":
        metadata = dict(info.trace_metadata)
        metadata.pop(f"evalsurge.{absent}_id")
        exporter.start_trace(replace(info, trace_metadata=metadata))
    partial = client.get_trace(info.trace_id, display=False)
    assert partial.info.trace_location.mlflow_experiment.experiment_id in source.experiment_ids
    for key in ("run", "request") if absent == "both" else (absent,):
        assert partial.info.trace_metadata.get(f"evalsurge.{key}_id") is None
    assert partial.data.spans  # Non-None native Trace is insufficient readiness.
    client.reads = 0
    sleeps = []

    def metadata_lands(seconds: float) -> None:
        sleeps.append(seconds)
        exporter.start_trace(info)

    monkeypatch.setattr(
        profiling, "time", SimpleNamespace(monotonic=lambda: 0, sleep=metadata_lands)
    )
    summary, traces = profiling.collect_profiles([row], "run", source, tmp_path / "report", client)
    assert summary.traced_requests == 1
    assert summary.gaps == {}
    assert traces["request"].info.trace_metadata["evalsurge.run_id"] == "run"
    assert client.reads == 2
    assert sleeps == [0.5]


def test_absent_metadata_exhausts_bounded_native_reads(
    incremental_trace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A permanently uncorrelated native trace stays a gap, never authorization."""
    _, _, row, client, source = incremental_trace
    sleeps = []
    monkeypatch.setattr(
        profiling, "time", SimpleNamespace(monotonic=lambda: 0, sleep=sleeps.append)
    )
    summary, traces = profiling.collect_profiles([row], "run", source, tmp_path / "report", client)
    assert traces == {}
    assert summary.gaps == {"missing": 1}
    assert client.reads == 4
    assert sleeps == [0.5, 2.0, 4.0]


@pytest.mark.parametrize("field", ["run", "request", "experiment", "trace"])
def test_conflicting_scope_is_rejected_without_visibility_retry(
    field: str, incremental_trace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Existing foreign scope values cannot become retryable provisional metadata."""
    exporter, info, row, client, source = incremental_trace
    metadata = dict(info.trace_metadata)
    # Leave one required field missing: the other conflicting field must still win.
    metadata.pop("evalsurge.request_id")
    if field == "run":
        metadata["evalsurge.run_id"] = "foreign-run"
    elif field == "request":
        metadata.pop("evalsurge.run_id")
        metadata["evalsurge.request_id"] = "foreign-request"
    exporter.start_trace(replace(info, trace_metadata=metadata))
    if field == "experiment":
        source = source.model_copy(update={"experiment_ids": ["foreign-experiment"]})
    elif field == "trace":
        # Counted native fetch of a different real identifier; no fabricated Trace.
        original_read = client.get_trace

        def different_native_id(trace_id: str, display: bool = False):
            return original_read(info.trace_id, display=display)

        monkeypatch.setattr(client, "get_trace", different_native_id)
        row = {**row, "trace_id": "foreign-id"}
    sleeps = []
    monkeypatch.setattr(
        profiling, "time", SimpleNamespace(monotonic=lambda: 0, sleep=sleeps.append)
    )
    summary, traces = profiling.collect_profiles([row], "run", source, tmp_path / "report", client)
    assert traces == {}
    assert summary.gaps == {"scope_mismatch": 1}
    assert client.reads == 1
    assert sleeps == []


def test_pending_metadata_obeys_shared_collection_deadline(
    incremental_trace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stalled admitted native read must not start another read after the deadline."""
    _, _, row, client, source = incremental_trace
    clock = iter([0, 0, 61])
    sleeps = []
    monkeypatch.setattr(
        profiling, "time", SimpleNamespace(monotonic=lambda: next(clock), sleep=sleeps.append)
    )
    summary, traces = profiling.collect_profiles([row], "run", source, tmp_path / "report", client)
    assert traces == {}
    assert summary.gaps == {"missing": 1}
    assert client.reads == 1
    assert sleeps == []


def test_backoff_does_not_start_native_read_at_deadline(
    incremental_trace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The last wait is clamped and cannot admit a second fetch at the deadline."""
    _, _, row, client, source = incremental_trace
    clock = iter([0, 0, 59.9, 59.9, 60])
    sleeps = []
    monkeypatch.setattr(
        profiling, "time", SimpleNamespace(monotonic=lambda: next(clock), sleep=sleeps.append)
    )
    summary, traces = profiling.collect_profiles([row], "run", source, tmp_path / "report", client)
    assert traces == {}
    assert summary.gaps == {"missing": 1}
    assert client.reads == 1
    assert sleeps == pytest.approx([0.1])


@pytest.mark.parametrize(
    "values",
    [
        {"BENCHMARK_TRACE_ENABLED": "true"},
        {"BENCHMARK_TRACE_ENABLED": "true", "MLFLOW_TRACKING_URI": "sqlite:///not-read.db"},
        {"BENCHMARK_TRACE_ENABLED": "true", "BENCHMARK_TRACE_EXPERIMENT_IDS": '["1"]'},
    ],
)
@pytest.mark.asyncio
async def test_load_only_planning_rejects_incomplete_enabled_trace_scope(values) -> None:
    """Existing production planning guard rejects configuration before inference."""
    with configured_environment(values), pytest.raises(ValueError, match="Tracing requires"):
        await create_plan(Evaluation(description="Load only", scorers=[]))
