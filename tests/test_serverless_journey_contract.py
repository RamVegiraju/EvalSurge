"""Static notebook topology/consent contracts; no agent/provider completions."""

import ast
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.validation.serverless_sdk_journeys import budget_record, execute, parse_options

ROOT = Path(__file__).resolve().parents[1]


def arguments() -> list[str]:
    """Return noncredential selections; parsing never resolves a workspace."""
    return [
        "--workspace",
        "https://approved-workspace.example",
        "--target-model",
        "approved-model",
        "--framework",
        "langgraph",
        "--model-api",
        "mlflow-responses",
    ]


def test_budget_accounts_for_both_sdk_modes_and_excluded_probes() -> None:
    options = parse_options(arguments())
    record = budget_record(options)
    assert record["normal_run_count"] == 2
    assert record["max_measured_invocations"] == 10
    assert record["max_model_bearing_probe_invocations"] == 2
    assert record["max_negative_route_probes_without_model_dispatch"] == 2
    assert record["max_total_target_attempts"] == 14
    assert record["deployed_app_tested"] is False
    assert record["inference_stubbed"] is False
    assert record["evaluation_mode"] == "off"
    assert record["max_model_calls"] == 12
    assert record["metadata_retry_window_seconds"] == 1
    assert "approved-model" not in json.dumps(record)
    assert "approved-workspace" not in json.dumps(record)


def test_cancellation_is_a_second_independently_bounded_run_per_mode() -> None:
    options = parse_options(arguments() + ["--exercise-cancel"])
    record = budget_record(options)
    assert record["normal_run_count"] == 4
    assert record["max_total_target_attempts"] == 26
    assert record["max_measured_invocations"] == 20
    assert record["max_model_bearing_probe_invocations"] == 4


def test_crewai_native_executor_budget_is_explicit() -> None:
    """Parse declared limits only; CrewAI is not imported or substituted."""
    options = parse_options(arguments() + ["--framework", "crewai"])
    record = budget_record(options)
    assert record["max_model_calls_per_agent_invocation"] == 2
    assert record["max_model_calls"] == 24
    assert record["model_api"] == "mlflow-responses"


def test_every_notebook_scenario_uses_terminal_payload_parity() -> None:
    """Inspect actual scenario wiring, not an agent or a provider completion.

    Normal success, intentional pre-provider failure and observed cancellation
    must each compare status, result and report payloads, not merely identifiers.
    Shared metadata comparison behavior has independent pure-schema coverage in
    ``test_hosted_journey_harness``; no network or inference is exercised here.
    """
    source = (ROOT / "scripts/validation/serverless_sdk_journeys.py").read_text()
    tree = ast.parse(source)
    for name in ("_exercise_direct", "_exercise_api"):
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name
        )
        comparisons = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "retrieval_evidence"
        ]
        assert len(comparisons) == 3
        function_source = ast.get_source_segment(source, function)
        assert function_source is not None
        assert function_source.count('parity["retrieval_agrees"]') == 3
        for comparison in comparisons:
            remote = next(
                keyword.value for keyword in comparison.keywords if keyword.arg == "remote"
            )
            assert isinstance(remote, ast.Constant)
            assert remote.value is (name == "_exercise_api")


def test_prerequisite_sdk_budgets_use_native_config_boundary() -> None:
    """Read native SDK signatures and source only, without initializing credentials.

    WorkspaceClient does not accept Config's timeout/retry keyword arguments.
    Passing them directly creates TypeError before runtime auth is tested.
    """
    from databricks.sdk import WorkspaceClient

    signature = inspect.signature(WorkspaceClient)
    source = (ROOT / "scripts/validation/serverless_prerequisites.py").read_text()
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "WorkspaceClient"
    ]
    assert len(calls) == 1
    assert {keyword.arg for keyword in calls[0].keywords} <= set(signature.parameters)
    config = next(keyword.value for keyword in calls[0].keywords if keyword.arg == "config")
    assert isinstance(config, ast.Call)
    assert isinstance(config.func, ast.Name) and config.func.id == "Config"
    assert {keyword.arg for keyword in config.keywords} >= {
        "host",
        "auth_type",
        "scopes",
        "http_timeout_seconds",
        "retry_timeout_seconds",
    }
    assert "w=WorkspaceClient(config=Config(" in source
    retry = next(
        keyword.value for keyword in config.keywords if keyword.arg == "retry_timeout_seconds"
    )
    assert isinstance(retry, ast.Constant) and retry.value == 1


def test_native_metadata_retry_zero_is_not_no_retries() -> None:
    """Construct actual native HTTP sessions; no auth/request/provider executes."""
    from databricks.sdk._base_client import _BaseClient

    zero = _BaseClient(retry_timeout_seconds=0)
    bounded = _BaseClient(retry_timeout_seconds=1)
    try:
        assert zero._retry_timeout_seconds == 300
        assert bounded._retry_timeout_seconds == 1
    finally:
        zero._session.close()
        bounded._session.close()


@pytest.mark.parametrize(
    "extra",
    [
        ["--concurrency", "6"],
        ["--max-requests", "21"],
        ["--duration", "nan"],
        ["--timeout", "inf"],
        ["--timeout", "31"],
        ["--model-api", "auto"],
        ["--max-output-tokens", "513"],
        ["--duration", "181"],
        ["--live"],
        ["--live", "--accept-paid-traffic"],
        ["--workspace", "http://remote.example"],
        ["--workspace", "https://private@example"],
        ["--workspace", "https://example/path"],
        ["--workspace", "https://example/?token=private"],
        ["--target-model", " "],
    ],
)
def test_rejects_unsafe_or_unbounded_execution(extra: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_options(arguments() + extra)


@pytest.mark.asyncio
async def test_no_consent_fails_before_any_auth_or_artifact(tmp_path: Path) -> None:
    destination = tmp_path / "absent"
    options = parse_options(arguments() + ["--artifact-dir", str(destination)])
    with pytest.raises(ValueError, match="explicit consent"):
        await execute(options)
    assert not destination.exists()


@pytest.mark.asyncio
async def test_old_evidence_rejected_before_any_auth(tmp_path: Path) -> None:
    destination = tmp_path / "existing"
    destination.mkdir()
    evidence = destination / "prior.json"
    evidence.write_text('{"prior":true}', encoding="utf-8")
    options = parse_options(
        arguments() + ["--live", "--accept-paid-traffic", "--artifact-dir", str(destination)]
    )
    with pytest.raises(ValueError, match="never overwritten"):
        await execute(options)
    assert evidence.read_text(encoding="utf-8") == '{"prior":true}'


def test_driver_auth_source_never_exports_or_substitutes_credentials() -> None:
    """Read actual SDK/harness source contracts; no credential provider is invoked."""
    import databricks.sdk.credentials_provider as provider

    provider_source = Path(provider.__file__).read_text(encoding="utf-8")
    assert '@oauth_credentials_strategy("runtime-oauth", ["scopes"]' in provider_source
    source = (ROOT / "scripts/validation/serverless_sdk_journeys.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    driver = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "driver_workspace"
    )
    auth_source = ast.get_source_segment(source, driver)
    assert auth_source is not None
    assert 'auth_type="runtime-oauth"' in auth_source
    assert 'scopes=["all-apis"]' in auth_source
    assert 'workspace.config.host.rstrip("/") != expected_origin' in auth_source
    assert "oauth_token()" in auth_source
    assert ".access_token" not in source
    assert "DATABRICKS_TOKEN" not in source
    assert "DATABRICKS_CONFIG_PROFILE" not in source
    assert "MockTransport" not in source
    assert "fixture_provider" not in source
    assert "helper = _create_driver_helper(options, workspace)" in source
    assert 'DispatchObserver(helper, "/invoke")' in source
    assert "examples.framework_agent" not in source
    assert "response_completion_guard" in source
    assert '"response": [response_completion_guard, record_completion]' in source
    assert '"request": [record_dispatch]' in source
    assert 'record["model_transport_evidence"] = dict(helper.state.inference_evidence)' in source
    assert "DatabricksAuth(workspace)" in source
    assert "max_retries=0" in source
    assert "await asyncio.to_thread(_exercise_api" in source


def test_live_framework_accepts_driver_client_without_changing_default_profile_path() -> None:
    """Inspect wiring only; do not initialize the demo fixture or real provider."""
    source = (ROOT / "examples/framework_agent.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    factory = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "create_app"
    )
    assert [argument.arg for argument in factory.args.kwonlyargs] == ["workspace"]
    assert "workspace is not None and not live" in source
    assert "workspace if workspace is not None else workspace_client()" in source
    assert "DatabricksAuth(selected_workspace)" in source


def test_owned_tracking_store_does_not_leak_native_mlflow_experiment_ids(tmp_path: Path) -> None:
    """Exercise two real local MLflow stores, without any agent or inference calls.

    A child process contains MLflow's process-global tracking state. This is native
    storage integration, not a mocked framework or provider completion.
    """
    script = """
import os
import sys
from pathlib import Path

import mlflow
from scripts.validation.serverless_sdk_journeys import _owned_demo_environment

os.environ.pop("MLFLOW_EXPERIMENT_ID", None)
directory = Path(sys.argv[1])
for index in range(2):
    uri = f"sqlite:///{directory}/native-{index}.db"
    with _owned_demo_environment({"MLFLOW_TRACKING_URI": uri}):
        assert not os.environ.get("MLFLOW_EXPERIMENT_ID")
        mlflow.set_tracking_uri(uri)
        experiment = mlflow.set_experiment("native-harness-regression")
        assert mlflow.MlflowClient().get_experiment(experiment.experiment_id)
        assert os.environ["MLFLOW_EXPERIMENT_ID"] == experiment.experiment_id
    assert "MLFLOW_EXPERIMENT_ID" not in os.environ

os.environ["MLFLOW_EXPERIMENT_ID"] = "caller-owned-experiment"
try:
    with _owned_demo_environment({"MLFLOW_TRACKING_URI": uri}):
        assert not os.environ.get("MLFLOW_EXPERIMENT_ID")
        raise RuntimeError("intentional configuration-scope failure")
except RuntimeError:
    pass
assert os.environ["MLFLOW_EXPERIMENT_ID"] == "caller-owned-experiment"
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_native_uvicorn_startup_failure_does_not_exit_notebook_host() -> None:
    """Run a real failed ASGI lifespan, with no inference route or provider fixture.

    Isolate the process because the unfixed Uvicorn task exits its host interpreter.
    Successful containment must return normal control to the notebook coroutine.
    """
    for name in ("unified_sdk_journeys.py", "serverless_sdk_journeys.py"):
        source = (ROOT / "scripts" / "validation" / name).read_text()
        assert "asyncio.create_task(_serve_without_host_exit(server, listener))" in source
    script = """
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from scripts.validation.serverless_sdk_journeys import _serve

@asynccontextmanager
async def fail_startup(app):
    raise RuntimeError("intentional infrastructure startup failure")
    yield

async def check():
    try:
        await _serve(FastAPI(lifespan=fail_startup))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Startup failure was not reported")
    await asyncio.sleep(0)
    print("host-process-survived")

asyncio.run(check())
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "host-process-survived" in completed.stdout
