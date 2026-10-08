"""Static SDK/lifecycle contracts: no agents, completions, model calls or judges.

Synthetic persisted metadata and API response documents validate schema/read
behavior only. Transport controls below represent EvalSurge resource documents,
not provider inference. Pre-admission failures never dispatch an inference probe.
"""

import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from benchmark_agents.configuration import configured_environment, environment
from benchmark_agents.coordinator import CoordinatorError
from benchmark_agents.planner import fingerprint
from benchmark_agents.run_views import report_view
from benchmark_agents.settings import Settings, SettingsError
from benchmark_agents.validation import encode_request
from evalsurge import (
    Acknowledgment,
    Agent,
    EvalSurge,
    Report,
    RequestValidationError,
    Result,
    RunCreate,
    RunFailed,
    RunStatus,
)
from evalsurge.local import AsyncClient, AsyncDirectRun, Client, DirectRun
from evalsurge.remote import RemoteClient, RemoteProtocolError, RemoteRunFailed, TypedRemoteClient

RUN_ID = UUID("51d78660-11d8-486c-8399-fd9e74da19ce")


def _failure() -> dict:
    """Return static pre-planning failure metadata; there are no agent outputs."""
    return {
        "id": str(RUN_ID),
        "status": "failed",
        "planning_status": "failed",
        "load_status": "skipped",
        "profiling_status": "skipped",
        "evaluation_status": "skipped",
        "evaluation_mode": "off",
        "config": {"evaluation": {"scorers": []}},
        "plan": None,
        "planning_error": {"code": "planning_failed", "message": "Planning failed"},
        "preflight": {"status": "not_run"},
        "evaluation_preflight": {"status": "not_run"},
    }


def test_default_factory_aliases_freeze_targets_without_creating_artifacts(tmp_path: Path) -> None:
    targets = {"agent": Agent.http("http://127.0.0.1:8000/chat")}
    context = EvalSurge(artifact_dir=tmp_path / "unopened", targets=targets, settings=Settings())
    assert isinstance(context, Client)
    targets.clear()
    assert context._async_client._bindings["agent"].url == "http://127.0.0.1:8000/chat"
    assert not (tmp_path / "unopened").exists()
    context.close()
    with pytest.raises(TypeError):
        context._async_client._bindings["new"] = Agent.http("http://127.0.0.1:8000/chat")


def test_app_configuration_is_lazy_explicit_and_not_request_data(tmp_path: Path) -> None:
    agent = Agent.databricks_app("sample-agent", profile="explicit-operator-profile")
    registration = agent.registration
    assert registration.protocols == ("databricks-agent-runtime",)
    assert registration.profile == "explicit-operator-profile"
    assert registration.url is None
    assert "explicit-operator-profile" not in repr(registration)
    with pytest.raises(ValueError, match="resolve during unified"):
        _ = agent.target
    with pytest.raises(ValueError, match="resolve during unified"):
        _ = agent.connection
    with pytest.raises(ValueError):
        Agent.databricks_app("sample-agent", profile="")
    context = EvalSurge(artifact_dir=tmp_path, targets={"agent": agent}, settings=Settings())
    assert context._async_client._bindings["agent"].app_name == "sample-agent"
    context.close()
    assert Agent.databricks_app(
        "sample-agent", profile="explicit", protocol="mlflow-agent-server"
    ).registration.protocols == ("mlflow-agent-server",)


def test_invalid_requests_preserve_safe_field_guidance_before_any_http() -> None:
    with (
        RemoteClient("https://api.example") as client,
        pytest.raises(RequestValidationError) as failure,
    ):
        client.start(
            {
                "target": {"connection_id": "agent"},
                "cases": [{"input": {"query": "private"}}],
                "load": {"concurrency": 0},
            }
        )
    assert "load.concurrency" in str(failure.value)
    assert "private" not in str(failure.value) + repr(failure.value.errors())


@pytest.mark.asyncio
async def test_async_context_alias_rejection_and_cleanup_make_no_inference(tmp_path: Path) -> None:
    async with EvalSurge.local_async(artifact_dir=tmp_path, settings=Settings()) as client:
        assert isinstance(client, AsyncClient)
        with pytest.raises(CoordinatorError, match="Unknown registered target"):
            await client.start(
                RunCreate(target={"connection_id": "missing"}, cases=[{"input": {"query": "hi"}}])
            )
        assert not client._owned_coordinator().tasks
        assert not client._owned_coordinator().index
    async with EvalSurge.local_async(artifact_dir=tmp_path, settings=Settings()):
        pass


@pytest.mark.asyncio
async def test_planless_metadata_has_typed_read_wait_cancel_parity(tmp_path: Path) -> None:
    async with EvalSurge.local_async(artifact_dir=tmp_path, settings=Settings()) as client:
        coordinator = client._owned_coordinator()
        coordinator.runs[str(RUN_ID)] = _failure()
        handle = AsyncDirectRun(RUN_ID, client)
        assert isinstance(await handle.status(), RunStatus)
        result = await handle.result()
        assert isinstance(result, Result)
        assert result.summary.quality == "off"
        assert result.summary.performance == "not_run"
        report = await handle.report()
        assert isinstance(report, Report) and report.total == 0
        assert "planning_failed" in report.run.summary.evidence_gaps
        with pytest.raises(RunFailed) as failure:
            await handle.wait()
        assert isinstance(failure.value.report, Report)
        with pytest.raises(CoordinatorError, match="not in a cancellable"):
            await handle.cancel()
        detached = coordinator.read_run(RUN_ID)
        detached["status"] = "cancelled"
        assert coordinator.read_run(RUN_ID)["status"] == "failed"
        with pytest.raises(CoordinatorError):
            report_view(coordinator, RUN_ID, limit=0)
        coordinator.runs[str(RUN_ID)]["status"] = "running"
        coordinator.cancellations[str(RUN_ID)] = asyncio.Event()
        ack = await handle.cancel()
        assert isinstance(ack, Acknowledgment) and ack.status == "cancellation_requested"
        assert coordinator.cancellations[str(RUN_ID)].is_set()


@pytest.mark.asyncio
async def test_sync_context_works_inside_existing_loop_and_leaves_no_loop_owner(
    tmp_path: Path,
) -> None:
    caller_loop = asyncio.get_running_loop()
    with EvalSurge(artifact_dir=tmp_path, settings=Settings()) as client:
        assert asyncio.get_running_loop() is caller_loop

        async def metadata_only() -> None:
            client._async_client._owned_coordinator().runs[str(RUN_ID)] = _failure()

        client._call(metadata_only)
        run = DirectRun(RUN_ID, client)
        assert isinstance(run.status(), RunStatus)
        assert isinstance(run.result(), Result)
        assert isinstance(run.report(), Report)
        with pytest.raises(RunFailed):
            run.wait()
        with pytest.raises(CoordinatorError, match="not in a cancellable"):
            run.cancel()
        thread = client._thread
    assert thread is not None and not thread.is_alive()
    with EvalSurge(artifact_dir=tmp_path, settings=Settings()):
        pass


def test_typed_remote_resource_documents_and_legacy_default(tmp_path: Path) -> None:
    with EvalSurge(artifact_dir=tmp_path, settings=Settings()) as local:

        async def metadata_only() -> Report:
            coordinator = local._async_client._owned_coordinator()
            coordinator.runs[str(RUN_ID)] = _failure()
            return report_view(coordinator, RUN_ID)

        report = local._call(metadata_only)
    requests = []

    def resource(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST" and request.url.path == "/v2/runs":
            return httpx.Response(202, json={"id": str(RUN_ID), "status": "queued"})
        if request.url.path.endswith("/cancel"):
            return httpx.Response(
                202,
                json={
                    "id": str(RUN_ID),
                    "status": "cancellation_requested",
                    "links": report.run.links.model_dump(),
                },
            )
        if request.url.path.endswith("/report"):
            return httpx.Response(200, json=report.model_dump(mode="json"))
        if request.url.path.endswith("/result"):
            return httpx.Response(200, json=report.run.model_dump(mode="json"))
        status = {
            **report.run.model_dump(
                mode="json", include={"id", "status", "name", "phases", "links"}
            ),
            "poll_after_seconds": 0,
        }
        return httpx.Response(200, json=status)

    config = RunCreate(target={"connection_id": "agent"}, cases=[{"input": {"query": "hi"}}])
    with EvalSurge.remote(
        "https://api.example", typed=True, transport=httpx.MockTransport(resource)
    ) as client:
        assert isinstance(client, TypedRemoteClient)
        run = client.start(config)
        assert isinstance(run.status(), RunStatus)
        assert isinstance(run.result(), Result)
        assert isinstance(run.report(), Report)
        assert isinstance(run.cancel(), Acknowledgment)
        with pytest.raises(RemoteRunFailed) as failure:
            run.wait(timeout=5)
        assert isinstance(failure.value.report, Report)
    with EvalSurge.remote("https://api.example", transport=httpx.MockTransport(resource)) as legacy:
        assert type(legacy) is RemoteClient
        assert isinstance(legacy.report(RUN_ID), dict)
    assert (
        sum(request.method == "POST" and request.url.path == "/v2/runs" for request in requests)
        == 1
    )


def test_typed_remote_rejects_invalid_schema_without_body_leakage() -> None:
    def resource(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"id": str(RUN_ID), "status": "failed", "private": "secret-workload"}
        )

    with (
        EvalSurge.remote(
            "https://api.example", typed=True, transport=httpx.MockTransport(resource)
        ) as client,
        pytest.raises(RemoteProtocolError) as failure,
    ):
        client.result(RUN_ID)
    assert "secret-workload" not in str(failure.value)


def test_public_models_do_not_import_fastapi_or_execution_stack() -> None:
    code = "import sys, evalsurge; assert evalsurge.RunCreate; assert evalsurge.Report; assert 'fastapi' not in sys.modules; assert 'benchmark_agents.coordinator' not in sys.modules; assert 'locust' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)


@pytest.mark.asyncio
async def test_idempotent_app_replay_uses_metadata_without_discovery(tmp_path: Path) -> None:
    config = RunCreate(target={"connection_id": "agent"}, cases=[{"input": {"query": "hi"}}])
    agent = Agent.databricks_app("not-deployed", profile="explicit-unused-profile")
    async with EvalSurge.local_async(
        artifact_dir=tmp_path, targets={"agent": agent}, settings=Settings()
    ) as client:
        coordinator = client._owned_coordinator()
        coordinator.runs[str(RUN_ID)] = _failure()
        coordinator.index[str(RUN_ID)] = {
            "id": str(RUN_ID),
            "idempotency_key_hash": fingerprint("existing"),
            "request_hash": fingerprint(
                {"api_version": "v2", "request": config.model_dump(mode="json")}
            ),
        }
        replay = await client.start(config, idempotency_key="existing")
        assert replay.id == RUN_ID
        assert not coordinator.tasks
        changed = config.model_copy(update={"name": "different"})
        with pytest.raises(CoordinatorError, match="different body"):
            await client.start(changed, idempotency_key="existing")


@pytest.mark.asyncio
async def test_wait_deadline_leaves_metadata_task_active_without_inference(tmp_path: Path) -> None:
    async with EvalSurge.local_async(artifact_dir=tmp_path, settings=Settings()) as client:
        coordinator = client._owned_coordinator()
        coordinator.runs[str(RUN_ID)] = {**_failure(), "status": "running"}
        finish = asyncio.Event()
        task = asyncio.create_task(finish.wait())
        coordinator.tasks[str(RUN_ID)] = task
        try:
            with pytest.raises(TimeoutError):
                await client.wait(RUN_ID, timeout=0.001)
            assert not task.done() and not task.cancelled()
        finally:
            finish.set()
            await task
            coordinator.tasks.pop(str(RUN_ID))


def test_schema_errors_and_non_json_values_are_distinct_in_both_modes() -> None:
    from evalsurge.local import _detached_request

    constructed = RunCreate.model_construct(
        target={"connection_id": "agent"}, cases=[], load={"concurrency": 0}
    )
    with pytest.raises(RequestValidationError):
        _detached_request(constructed)
    non_json = RunCreate(target={"connection_id": "agent"}, cases=[{"input": {"query": object()}}])
    with pytest.raises(ValueError, match="finite JSON-compatible"):
        _detached_request(non_json)
    with (
        RemoteClient("https://api.example") as remote,
        pytest.raises(ValueError, match="finite JSON-compatible"),
    ):
        remote.start(non_json)


def test_mapping_python_only_values_reject_both_modes_but_typed_json_is_supported() -> None:
    from evalsurge.local import _detached_request

    config = {
        "target": {"connection_id": "agent"},
        "cases": [{"input": {"query": "hi"}, "reference": {"captured_at": datetime(2026, 10, 8)}}],
    }
    with pytest.raises(ValueError, match="finite JSON-compatible"):
        _detached_request(config)
    with (
        RemoteClient("https://api.example") as remote,
        pytest.raises(ValueError, match="finite JSON-compatible"),
    ):
        remote.start(config)
    typed = RunCreate.model_validate(config)
    detached, content = encode_request(typed)
    assert detached.cases[0].reference["captured_at"] == "2026-10-08T00:00:00"
    assert json.loads(content)["cases"][0]["reference"]["captured_at"] == "2026-10-08T00:00:00"
    assert _detached_request(typed) == detached
    observed = []

    def resource(request: httpx.Request) -> httpx.Response:
        observed.append(request.content)
        return httpx.Response(202, json={"id": str(RUN_ID), "status": "queued"})

    with RemoteClient("https://api.example", transport=httpx.MockTransport(resource)) as remote:
        remote.start(typed)
    assert observed == [content]


def test_utf8_byte_boundaries_are_identical_without_ascii_escape_or_defaults() -> None:
    from evalsurge.local import _detached_request

    config = {"target": {"connection_id": "agent"}, "cases": [{"input": {"query": ""}}]}
    overhead = len(json.dumps(config, ensure_ascii=False).encode("utf-8"))
    available = 8_000_000 - overhead
    text = "é" * (available // 2) + "a" * (available % 2)
    config["cases"][0]["input"]["query"] = text
    detached, content = encode_request(config)
    assert len(content) == 8_000_000
    assert b"\\u00e9" not in content
    assert _detached_request(config) == detached
    seen = []

    def resource(request: httpx.Request) -> httpx.Response:
        seen.append(len(request.content))
        assert request.content == content
        return httpx.Response(202, json={"id": str(RUN_ID), "status": "queued"})

    with RemoteClient("https://api.example", transport=httpx.MockTransport(resource)) as remote:
        remote.start(config)
        config["cases"][0]["input"]["query"] += "a"
        with pytest.raises(ValueError, match="eight-million-byte"):
            remote.start(config)
    with pytest.raises(ValueError, match="eight-million-byte"):
        _detached_request(config)
    assert seen == [8_000_000]


def test_shared_encoding_detaches_nested_mapping_values_and_preserves_unset_fields() -> None:
    from evalsurge.local import _detached_request

    config = {
        "target": {"connection_id": "agent"},
        "cases": [{"input": {"query": "hi"}, "reference": {"facts": ["first"]}}],
    }
    detached = _detached_request(config)
    config["cases"][0]["reference"]["facts"].append("second")
    assert detached.cases[0].reference["facts"] == ["first"]
    typed = RunCreate(target={"connection_id": "agent"}, cases=[{"input": {"query": "hi"}}])
    _, content = encode_request(typed)
    assert json.loads(content) == typed.model_dump(mode="json", exclude_unset=True)
    assert "evaluation" not in json.loads(content)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("field", ["input", "reference"])
@pytest.mark.parametrize("mutated", [False, True])
def test_typed_nonfinite_values_are_rejected_before_json_normalization(
    number: float, field: str, mutated: bool
) -> None:
    from evalsurge.local import _detached_request

    typed = RunCreate(
        target={"connection_id": "agent"},
        cases=[{"input": {"query": "hi"}, "reference": {"facts": ["first"]}}],
    )
    if mutated:
        getattr(typed.cases[0], field)["nested"] = [{"score": number}]
    else:
        document = typed.model_dump(mode="python")
        document["cases"][0][field]["nested"] = [{"score": number}]
        typed = RunCreate.model_validate(document)
    with pytest.raises(ValueError, match="finite JSON-compatible"):
        encode_request(typed)
    with pytest.raises(ValueError, match="finite JSON-compatible"):
        _detached_request(typed)
    with (
        RemoteClient("https://api.example") as remote,
        pytest.raises(ValueError, match="finite JSON-compatible"),
    ):
        remote.start(typed)


@pytest.mark.asyncio
@pytest.mark.parametrize("factory", [EvalSurge, EvalSurge.local, EvalSurge.local_async])
@pytest.mark.parametrize("explicit", [False, True])
async def test_settings_artifact_precedence_matches_snapshot_and_preserves_aliases(
    tmp_path: Path, factory, explicit: bool
) -> None:
    selected = tmp_path / "settings-owned"
    override = tmp_path / "explicit-owner"
    targets = {"agent": Agent.http("http://127.0.0.1:8000/chat")}
    kwargs = {"settings": Settings(artifact_dir=selected), "targets": targets}
    if explicit:
        kwargs["artifact_dir"] = override
    context = factory(**kwargs)
    async_client = context if isinstance(context, AsyncClient) else context._async_client
    expected = override if explicit else selected
    assert async_client._artifact_dir == expected
    assert async_client._operator["BENCHMARK_ARTIFACT_DIR"] == str(expected)
    targets.clear()
    assert async_client._bindings["agent"].url == "http://127.0.0.1:8000/chat"
    assert not expected.exists()
    if isinstance(context, AsyncClient):
        await context.close()
    else:
        context.close()


def test_legacy_omitted_artifact_default_still_matches_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BENCHMARK_ARTIFACT_DIR", raising=False)
    monkeypatch.delenv("BENCHMARK_CONFIG", raising=False)
    context = EvalSurge.local()
    assert context._async_client._artifact_dir == Path("artifacts")
    assert context._async_client._operator["BENCHMARK_ARTIFACT_DIR"] == "artifacts"
    context.close()


@pytest.mark.parametrize("factory", [EvalSurge, EvalSurge.local, EvalSurge.local_async])
@pytest.mark.parametrize("source", ["environment", "file"])
@pytest.mark.parametrize("explicit", [False, True])
def test_loaded_operator_storage_is_frozen_once_and_explicit_path_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, factory, source: str, explicit: bool
) -> None:
    from benchmark_agents.settings import load_settings
    from evalsurge import local

    monkeypatch.delenv("BENCHMARK_ARTIFACT_DIR", raising=False)
    monkeypatch.delenv("BENCHMARK_CONFIG", raising=False)
    selected = tmp_path / "configured-owner"
    override = tmp_path / "explicit-owner"
    operator_file = tmp_path / "operator.toml"
    if source == "environment":
        monkeypatch.setenv("BENCHMARK_ARTIFACT_DIR", str(selected))
    else:
        operator_file.write_text(f'artifact_dir = "{selected}"\n', encoding="utf-8")
        monkeypatch.setenv("BENCHMARK_CONFIG", str(operator_file))
    loads = []

    def counted_settings(*args, **kwargs):
        loads.append(None)
        return load_settings(*args, **kwargs)

    monkeypatch.setattr(local, "load_settings", counted_settings)
    context = factory(**({"artifact_dir": override} if explicit else {}))
    async_client = context if isinstance(context, AsyncClient) else context._async_client
    expected = override if explicit else selected
    assert loads == [None]
    assert async_client._artifact_dir == expected
    assert async_client._operator["BENCHMARK_ARTIFACT_DIR"] == str(expected)
    assert "BENCHMARK_CONFIG" not in async_client._operator
    monkeypatch.setenv("BENCHMARK_ARTIFACT_DIR", str(tmp_path / "changed-environment"))
    if source == "file":
        operator_file.write_text('artifact_dir = "changed-file"\n', encoding="utf-8")
    assert load_settings(environ=async_client._operator).artifact_dir == expected
    assert not expected.exists()
    if not isinstance(context, AsyncClient):
        context.close()


def test_cli_artifact_option_does_not_override_operator_default() -> None:
    from evalsurge.cli import _parser

    args = _parser().parse_args(["run", "request.json", "--local"])
    assert args.artifact_dir is None
    args = _parser().parse_args(
        ["run", "request.json", "--local", "--artifact-dir", "selected-owner"]
    )
    assert args.artifact_dir == Path("selected-owner")


@pytest.mark.parametrize("factory", [EvalSurge, EvalSurge.local, EvalSurge.local_async])
def test_direct_factory_inherits_scoped_operator_configuration(tmp_path: Path, factory) -> None:
    """Freeze the effective private scope, never bypass it for process settings."""
    values = {
        "BENCHMARK_ARTIFACT_DIR": str(tmp_path / "scoped-owner"),
        "BENCHMARK_JUDGE_MODEL": "scoped-judge",
        "BENCHMARK_CONNECTIONS": json.dumps({"scoped": {"url": "http://127.0.0.1:8000/chat"}}),
    }
    with configured_environment(values):
        context = factory()
        async_client = context if isinstance(context, AsyncClient) else context._async_client
        assert async_client._artifact_dir == tmp_path / "scoped-owner"
        assert async_client._operator["BENCHMARK_JUDGE_MODEL"] == "scoped-judge"
        assert json.loads(async_client._operator["BENCHMARK_CONNECTIONS"]) == json.loads(
            values["BENCHMARK_CONNECTIONS"]
        )
        values["BENCHMARK_JUDGE_MODEL"] = "later-change"
        assert async_client._operator["BENCHMARK_JUDGE_MODEL"] == "scoped-judge"
        assert not async_client._artifact_dir.exists()
        if not isinstance(context, AsyncClient):
            context.close()


@pytest.mark.asyncio
async def test_unused_legacy_registry_still_fails_closed_for_unified_admission(
    tmp_path: Path,
) -> None:
    """Invalid v2 bindings never become an unknown alias or an admitted target."""
    values = {"BENCHMARK_CONNECTIONS": "unused-invalid-json"}
    with configured_environment(values):
        async with EvalSurge.local_async(artifact_dir=tmp_path) as client:
            with pytest.raises(SettingsError, match="Invalid operator configuration"):
                await client.start(
                    RunCreate(target={"connection_id": "agent"}, cases=[{"input": {"query": "hi"}}])
                )
            assert not client._owned_coordinator().index
            assert not client._owned_coordinator().tasks


@pytest.mark.asyncio
async def test_implicit_registry_is_frozen_and_selected_only_for_unified_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reach the resolution boundary without discovery, auth or inference calls."""
    from benchmark_agents.target_resolver import TargetResolutionError
    from evalsurge import local

    observed = []

    def stop_resolution(alias, bindings):
        observed.append((alias, bindings[alias].url))
        raise TargetResolutionError("Intentional pre-discovery stop")

    monkeypatch.setattr(local, "resolve_registered_target", stop_resolution)
    values = {"BENCHMARK_CONNECTIONS": json.dumps({"agent": {"url": "http://127.0.0.1:8000/chat"}})}
    with configured_environment(values):
        async with EvalSurge.local_async(artifact_dir=tmp_path) as client:
            values["BENCHMARK_CONNECTIONS"] = "later-invalid-value"
            with pytest.raises(CoordinatorError, match="Registered target resolution failed"):
                await client.start(
                    RunCreate(target={"connection_id": "agent"}, cases=[{"input": {"query": "hi"}}])
                )
            assert not client._owned_coordinator().index
            assert not client._owned_coordinator().tasks
    assert observed == [("agent", "http://127.0.0.1:8000/chat")]


@pytest.mark.asyncio
@pytest.mark.parametrize("sync", [False, True])
async def test_legacy_submission_preserves_current_scope_without_registry_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sync: bool
) -> None:
    """Stop at admission; no target, provider, preflight or model completion is used."""
    from benchmark_agents.coordinator import RunCoordinator
    from benchmark_agents.models import Load, Sample

    observed = []

    async def inspect_submission(self, *args, **kwargs):
        observed.append(dict(environment()))
        raise CoordinatorError(422, "Intentional pre-admission stop")

    monkeypatch.setattr(RunCoordinator, "submit", inspect_submission)
    values = {
        "BENCHMARK_CONNECTIONS": "unused-invalid-json",
        "MLFLOW_EXPERIMENT_ID": "1",
    }
    arguments = {
        "agent": Agent.http("http://127.0.0.1:8000/chat"),
        "cases": [Sample(inputs={"query": "hi"})],
        "load": Load(max_requests=1),
    }
    with configured_environment(values):
        if sync:
            with EvalSurge.local(artifact_dir=tmp_path) as client:
                values["MLFLOW_EXPERIMENT_ID"] = "2"
                with pytest.raises(CoordinatorError, match="Intentional pre-admission"):
                    client.start(**arguments)
        else:
            async with EvalSurge.local_async(artifact_dir=tmp_path) as client:
                values["MLFLOW_EXPERIMENT_ID"] = "2"
                with pytest.raises(CoordinatorError, match="Intentional pre-admission"):
                    await client.start(**arguments)
        assert environment() is values
    assert len(observed) == 1
    assert observed[0]["MLFLOW_EXPERIMENT_ID"] == "2"
    assert observed[0]["BENCHMARK_CONNECTIONS"] == "unused-invalid-json"
    assert observed[0]["BENCHMARK_ARTIFACT_DIR"] == str(tmp_path)
