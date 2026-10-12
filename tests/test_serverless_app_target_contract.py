"""No-inference guards for a runner-only notebook -> deployed App sample.

These checks exercise parsing, real schemas, native SDK construction, controlled
metadata/auth boundaries, source boundaries and deliberate pre-provider rejection.
No selected profile is resolved; no outbound HTTP request or inference is performed.
They do not establish successful live notebook-to-App coverage.
"""

import ast
import asyncio
import json
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from scripts.validation.serverless_runner_app_target import (
    budget_record,
    execute,
    parse_options,
    readiness,
    request,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def native_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Callable[..., tuple[Any, list[str]]]]:
    """Construct native clients without selected profiles or outbound metadata calls.

    Args:
        monkeypatch: Test-scoped interception of HTTP, metadata and client selection.
        tmp_path: Test-owned location for an explicitly absent configuration file.

    Returns:
        A client factory and ordered metadata/auth event log for each construction.

    Side Effects:
        Intercepts SDK host metadata and blocks every Requests HTTP operation.
        Native AppsAPI decoding runs against explicit metadata-only responses.
        Test-owned session pools are closed at fixture teardown.
    """
    import requests
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.config import Config
    from databricks.sdk.credentials_provider import (
        OAuthCredentialsProvider,
        OauthCredentialsStrategy,
    )
    from databricks.sdk.oauth import HostMetadata, Token

    from benchmark_agents import providers, target_resolver

    def reject_outbound(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("No outbound metadata or inference request is permitted")

    monkeypatch.setattr(requests.Session, "request", reject_outbound)
    monkeypatch.setattr(
        "databricks.sdk.config.get_host_metadata",
        lambda *args, **kwargs: HostMetadata(oidc_endpoint=""),
    )
    clients: list[Any] = []

    def build(
        *,
        host: str = "https://selected-workspace.cloud.databricks.com",
        oauth: bool = True,
        token_error: bool = False,
        token_type: str = "Bearer",
        token_value: str = "controlled-auth-marker",
        discovery_error: bool = False,
        app_url: str | None = "https://selected-app.databricksapps.com",
    ) -> tuple[Any, list[str]]:
        """Create one native SDK client with controlled metadata/auth boundaries.

        Args:
            host: Explicit synthetic workspace origin, never a selected profile.
            oauth: Whether native OAuthCredentialsProvider or native PAT is constructed.
            token_error: Raise a private marker at token retrieval rather than return it.
            token_type: Synthetic OAuth metadata type, for deliberate invalid-type checks.
            token_value: Synthetic token metadata, never sent to an HTTP transport.
            discovery_error: Raise a private marker instead of returning App metadata.
            app_url: Synthetic AppsAPI deployment metadata for origin-validation checks.

        Returns:
            Native WorkspaceClient and ordered safe stage log, not live auth evidence.

        Side Effects:
            Replaces both module client factories and the native API metadata transport.
        """
        events: list[str] = []

        def token() -> Token:
            events.append("oauth")
            if token_error:
                raise ValueError("private-auth-marker")
            return Token(access_token=token_value, token_type=token_type)

        config_args: dict[str, Any] = {
            "host": host,
            "config_file": str(tmp_path / "absent-test-config"),
        }
        if oauth:
            config_args["credentials_strategy"] = OauthCredentialsStrategy(
                "test-metadata",
                lambda cfg: OAuthCredentialsProvider(lambda: {}, token),
            )
        else:
            config_args["token"] = "controlled-auth-marker"
        workspace = WorkspaceClient(config=Config(**config_args))
        clients.append(workspace)

        def metadata(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
            events.append("app-discovery")
            assert method == "GET"
            assert path == "/api/2.0/apps/operator-selected-app"
            if discovery_error:
                raise ValueError("private-discovery-marker")
            return {"name": "operator-selected-app", "url": app_url}

        monkeypatch.setattr(workspace.api_client, "do", metadata)

        def selected_client(*, profile: str) -> Any:
            events.append("selected-client")
            assert profile == "operator-selected-profile"
            return workspace

        # Patch both bindings so the pre-fix resolver cannot resolve a real profile.
        monkeypatch.setattr(providers, "workspace_client", selected_client)
        monkeypatch.setattr(target_resolver, "workspace_client", selected_client)
        return workspace, events

    yield build
    for client in clients:
        client.api_client._api_client._session.close()


def _arguments() -> list[str]:
    return [
        "--workspace",
        "https://selected-workspace.cloud.databricks.com",
        "--app-name",
        "operator-selected-app",
        "--profile",
        "operator-selected-profile",
        "--target-model",
        "operator-selected-model",
        "--source-revision",
        "reviewed-source-hash",
    ]


def test_dry_run_declares_only_runner_app_topology() -> None:
    options = parse_options(_arguments())
    record = budget_record(options)
    assert not options.live
    assert record["runner"] == "serverless-notebook"
    assert record["target_hosting"] == "deployed-databricks-app"
    assert record["maximum_app_invocations"] == 2
    assert record["declared_deployed_max_output_tokens"] == 512
    assert record["evaluation"] == "off"
    assert not record["deployed_app_tested"]
    assert not record["api_execution_tested"]
    assert not record["paid_traffic_authorized_by_this_record"]


def test_request_is_one_measured_attempt_and_no_judging() -> None:
    config = request()
    assert config.load.concurrency == 1
    assert config.load.max_requests == 1
    assert config.load.duration_seconds == 5
    assert config.load.timeout_seconds == 30
    assert config.target.connection_id == "agent"
    assert config.evaluation.mode == "off"
    assert set(config.cases[0].input) == {"query"}
    assert "profile" not in config.model_dump_json()


@pytest.mark.parametrize(
    "extra",
    [
        ["--workspace", "https://selected-workspace.cloud.databricks.com/path"],
        ["--workspace", "https://user:secret@selected-workspace.cloud.databricks.com"],
        ["--app-name", "bad_app_name"],
        ["--profile", ""],
        ["--source-revision", " "],
        ["--target-model", ""],
        ["--deployed-max-output-tokens", "513"],
        ["--deployed-max-output-tokens", "0"],
        ["--live"],
    ],
)
def test_selectors_and_paid_gate_reject_before_calls(extra: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_options([*_arguments(), *extra])


def test_execute_without_consent_makes_no_authentication_or_inference_calls() -> None:
    options = parse_options(_arguments())
    with pytest.raises(PermissionError, match="before auth or traffic"):
        asyncio.run(execute(options))


@pytest.mark.asyncio
async def test_execute_enters_real_sdk_and_releases_storage_on_pre_provider_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise package imports and native storage, never auth or target inference.

    Readiness is deliberately not exercised: its resource-access gate is skipped
    by a test-only metadata return, not an OAuth/provider response. A real empty
    SDK registry rejects the unknown alias before discovery or Locust. Native
    context acquisition and cleanup must still occur. No agent completion exists.
    """
    import requests

    from benchmark_agents import providers, target_resolver
    from benchmark_agents.coordinator import CoordinatorError
    from benchmark_agents.settings import Settings
    from evalsurge import EvalSurge, serverless

    original_factory = EvalSurge.local_async
    contexts: list[Any] = []

    def no_provider(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Pre-provider rejection must not initialize auth, load or HTTP")

    def empty_native_context(*, artifact_dir: Path, targets: Any) -> Any:
        assert set(targets) == {"agent"}
        context = original_factory(
            artifact_dir=artifact_dir, targets={}, settings=Settings(connections={})
        )
        contexts.append(context)
        return context

    monkeypatch.setattr(requests.Session, "request", no_provider)
    monkeypatch.setattr(providers, "workspace_client", no_provider)
    monkeypatch.setattr(target_resolver, "workspace_client", no_provider)
    monkeypatch.setattr(subprocess, "Popen", no_provider)
    monkeypatch.setattr(EvalSurge, "local_async", staticmethod(empty_native_context))
    monkeypatch.setattr(
        serverless,
        "readiness",
        lambda options: {"blockers": [], "portable_oauth_source_verified": False},
    )
    artifacts = tmp_path / "owned-empty-storage"
    options = parse_options(
        [
            *_arguments(),
            "--live",
            "--accept-paid-traffic",
            "--real-inference-attested",
            "--artifact-dir",
            str(artifacts),
        ]
    )
    with pytest.raises(CoordinatorError, match="Unknown registered target"):
        await execute(options)
    assert len(contexts) == 1
    assert contexts[0]._state == "closed"
    assert (artifacts / ".service.lock").is_file()
    assert not list(artifacts.glob("*.json"))
    # Opening the same real storage proves the native lock was released; no
    # process/agent/provider substitute is involved in either context.
    async with original_factory(
        artifact_dir=artifacts, targets={}, settings=Settings(connections={})
    ) as reopened:
        assert reopened._state == "open"


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_phase", ["planning", "worker_start"])
async def test_terminal_pre_provider_failure_does_not_claim_app_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_phase: str
) -> None:
    """Persist/read real terminal failures, never execute a target or model.

    Readiness is outside this regression and skipped by test-only metadata. The
    real SDK context owns a non-agent localhost binding solely to reach native
    admission. Injected infrastructure failure stops planning or worker launch
    before a process or HTTP request is created. No App or local agent substitute
    is run, and no model/provider response or completion is supplied.
    """
    import requests

    from benchmark_agents import coordinator, providers, target_resolver
    from benchmark_agents.settings import Settings
    from evalsurge import Agent, EvalSurge, RunFailed, serverless

    original_factory = EvalSurge.local_async

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("This intentional infrastructure failure must make no calls")

    async def infrastructure_failure(*args: Any, **kwargs: Any) -> Any:
        raise OSError("intentional-pre-provider-infrastructure-failure")

    def native_context(*, artifact_dir: Path, targets: Any) -> Any:
        assert set(targets) == {"agent"}
        return original_factory(
            artifact_dir=artifact_dir,
            targets={
                "agent": Agent.http(
                    "http://127.0.0.1:9/NON-agent-unreachable", protocol="http-json"
                )
            },
            settings=Settings(connections={}),
        )

    monkeypatch.setattr(requests.Session, "request", forbidden)
    monkeypatch.setattr(providers, "workspace_client", forbidden)
    monkeypatch.setattr(target_resolver, "workspace_client", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(EvalSurge, "local_async", staticmethod(native_context))
    monkeypatch.setattr(
        serverless,
        "readiness",
        lambda options: {"blockers": [], "portable_oauth_source_verified": False},
    )
    if failed_phase == "planning":
        monkeypatch.setattr(coordinator.RunCoordinator, "_create_plan", infrastructure_failure)
    else:
        monkeypatch.setattr(coordinator, "run_preflight", infrastructure_failure)
    artifacts = tmp_path / failed_phase
    options = parse_options(
        [
            *_arguments(),
            "--live",
            "--accept-paid-traffic",
            "--real-inference-attested",
            "--artifact-dir",
            str(artifacts),
        ]
    )
    receipt = await execute(options)
    assert receipt["state"] == "failed"
    assert receipt["retrieval"]["retrieval_agrees"] is True
    assert receipt["runner_context_closed"] is True
    assert receipt["passed"] is False
    assert receipt["deployed_app_tested"] is False
    assert receipt["app_metadata_checked"] is False
    assert receipt["client_invocation_observed"] is False
    assert receipt["successful_completion_observed"] is False
    assert (artifacts / receipt["run_id"] / "profiling.json").is_file()
    # A fresh real SDK/storage owner must retain the same terminal result across
    # status, result, report and the failure report returned by wait. No new run
    # is submitted, and the forbidden transports/process hook remains installed.
    async with original_factory(
        artifact_dir=artifacts, targets={}, settings=Settings(connections={})
    ) as reopened:
        status = await reopened.status(receipt["run_id"])
        result = await reopened.result(receipt["run_id"])
        report = await reopened.report(receipt["run_id"])
        with pytest.raises(RunFailed) as failure:
            await reopened.wait(receipt["run_id"], timeout=1)
        assert status.id == result.id == report.run.id
        assert status.status == result.status == report.run.status == "failed"
        assert status.phases == result.phases == report.run.phases
        assert result == report.run == failure.value.report.run
        assert report == failure.value.report
        assert result.metrics is None
        if failed_phase == "planning":
            assert result.evidence.internal_profiling.state == "unavailable"
            assert result.evidence.internal_profiling.configured is None
            assert result.evidence.internal_profiling.observed_count == 0
            assert result.evidence.internal_profiling.total_count is None
            assert result.evidence.internal_profiling.coverage is None
            # The report's empty presentation shell is not collected evidence.
            assert report.profiling.total_requests == 0
            assert report.profiling.traced_requests == 0
        else:
            # A frozen plan followed by failed preflight retains its independently
            # recorded zero measured attempts, not the planless unknown total.
            assert result.evidence.internal_profiling.total_count == 0


def test_actual_ambient_profile_guard_blocks_before_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from benchmark_agents import providers, target_resolver

    def forbidden_client(**kwargs: Any) -> None:
        raise AssertionError("Ambient conflict must reject before SDK construction")

    monkeypatch.setattr(providers, "workspace_client", forbidden_client)
    monkeypatch.setattr(target_resolver, "workspace_client", forbidden_client)
    monkeypatch.setenv("DATABRICKS_HOST", "https://notebook-injected-host.cloud.databricks.com")
    result = readiness(parse_options(_arguments()))
    assert not result["driver_profile_ready"]
    assert not result["worker_oauth_ready"]
    assert result["inference_invocations"] == 0
    assert result["blocker_codes"] == ["profile_conflict"]
    assert len(result["blockers"]) == 1
    assert "rejects ambient" in result["blockers"][0]
    assert "notebook-injected-host" not in str(result)


def test_exact_workspace_checked_before_oauth_or_app_discovery(
    native_workspace: Callable[..., tuple[Any, list[str]]],
) -> None:
    _, events = native_workspace(host="https://private-other-workspace.cloud.databricks.com")
    result = readiness(parse_options(_arguments()))
    assert events == ["selected-client"]
    assert result["blocker_codes"] == ["workspace_mismatch"]
    assert not result["driver_profile_ready"]
    assert result["inference_invocations"] == 0
    assert "private-other-workspace" not in json.dumps(result)


@pytest.mark.parametrize(
    ("setup", "code", "events"),
    [
        ({"oauth": False}, "driver_oauth_unavailable", ["selected-client"]),
        ({"token_error": True}, "driver_oauth_unavailable", ["selected-client", "oauth"]),
        ({"token_type": "Basic"}, "driver_oauth_unavailable", ["selected-client", "oauth"]),
        ({"token_value": ""}, "driver_oauth_unavailable", ["selected-client", "oauth"]),
        (
            {"discovery_error": True},
            "app_discovery_failed",
            ["selected-client", "oauth", "app-discovery"],
        ),
        (
            {"app_url": "https://user:private-url-marker@app.example.com"},
            "app_deployment_unavailable",
            ["selected-client", "oauth", "app-discovery"],
        ),
        (
            {"app_url": None},
            "app_deployment_unavailable",
            ["selected-client", "oauth", "app-discovery"],
        ),
    ],
)
def test_native_metadata_failures_have_distinct_safe_diagnostics(
    native_workspace: Callable[..., tuple[Any, list[str]]],
    setup: dict[str, Any],
    code: str,
    events: list[str],
) -> None:
    _, observed = native_workspace(**setup)
    result = readiness(parse_options(_arguments()))
    assert observed == events
    assert result["blocker_codes"] == [code]
    assert not result["driver_profile_ready"]
    assert not result["worker_oauth_ready"]
    assert result["inference_invocations"] == 0
    assert "marker" not in json.dumps(result)


def test_client_construction_failure_is_safe_and_not_app_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from benchmark_agents import providers, target_resolver

    def failed_client(*, profile: str) -> None:
        assert profile == "operator-selected-profile"
        raise ValueError("private-constructor-marker")

    monkeypatch.setattr(providers, "workspace_client", failed_client)
    monkeypatch.setattr(target_resolver, "workspace_client", failed_client)
    result = readiness(parse_options(_arguments()))
    assert result["blocker_codes"] == ["driver_authentication_failed"]
    assert result["inference_invocations"] == 0
    assert "private-constructor-marker" not in json.dumps(result)


@pytest.mark.parametrize("worker_metadata", ["null", "[]", '{"worker_oauth_ready": false}'])
def test_worker_metadata_failure_preserves_native_binding_without_token_copy(
    native_workspace: Callable[..., tuple[Any, list[str]]],
    monkeypatch: pytest.MonkeyPatch,
    worker_metadata: str,
) -> None:
    _, events = native_workspace()
    original_spawn = subprocess.Popen
    children: list[subprocess.Popen[bytes]] = []

    def child_metadata(arguments: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        """Emit inert diagnostic bytes, never initialize an SDK/auth provider."""
        events.append("worker-check")
        connection = json.loads(arguments[-1])
        assert connection["url"] == "https://selected-app.databricksapps.com/api/invocations"
        assert connection["profile"] == "operator-selected-profile"
        assert connection["app_name"] == "operator-selected-app"
        assert connection["auth"] == "databricks-app"
        assert "controlled-auth-marker" not in arguments[-1]
        assert "env" not in kwargs
        assert kwargs["start_new_session"] is False
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.DEVNULL
        child = original_spawn(
            [sys.executable, "-c", f"import sys; sys.stdout.write({worker_metadata!r})"],
            **kwargs,
        )
        children.append(child)
        return child

    monkeypatch.setattr(subprocess, "Popen", child_metadata)
    try:
        result = readiness(parse_options(_arguments()))
        assert events == ["selected-client", "oauth", "app-discovery", "worker-check"]
        assert result["blocker_codes"] == ["worker_oauth_unavailable"]
        assert result["driver_profile_ready"]
        assert not result["worker_oauth_ready"]
        assert result["inference_invocations"] == 0
        assert "controlled-auth-marker" not in json.dumps(result)
        assert len(children) == 1 and children[0].returncode == 0
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)


def test_notebook_never_imports_agent_or_serving_helper() -> None:
    path = ROOT / "examples/journeys/serverless_runner_databricks_app_target.py"
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported = {
        alias.name if isinstance(node, ast.Import) else node.module
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = {"langgraph", "agents", "crewai", "uvicorn", "evalsurge.serving"}
    assert not any(
        name and any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)
        for name in imported
    )
    assert "serverless_sdk_journeys" not in imported
    assert "evalsurge.serverless" in imported
    assert not any(name and name.startswith("scripts") for name in imported)
    assert "sys.path.insert" not in text
    assert 'widgets.text("source_root"' not in text
    assert '"allow_paid_inference", "false"' in text
    assert "not proven live" in text
    assert "deployed Databricks App" in text


def test_retained_helper_sources_are_diagnostic_not_app_coverage() -> None:
    harness = (ROOT / "scripts/validation/serverless_sdk_journeys.py").read_text(encoding="utf-8")
    notebook = (ROOT / "scripts/validation/serverless_helper_notebook.py").read_text(
        encoding="utf-8"
    )
    assert "Historical diagnostic" in harness
    assert "not the intended hosted-agent journey" in harness
    assert "Historical diagnostic" in notebook
    assert "not deployed-App coverage" in notebook
