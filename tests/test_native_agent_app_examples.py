"""Pure source/configuration/staging checks; no model fixtures, auth or deployment.

These tests never construct a native Runtime, execute a framework handler, replace
a provider transport or contact any service. The native projects remain prepared
examples until separately approved actual deployment/inference validation passes.
"""

import ast
import asyncio
import hashlib
import json
import shutil
import tomllib
from contextlib import suppress
from pathlib import Path
from threading import Event
from typing import Any

import pytest
import yaml

from examples.journeys.agent_apps.shared.native_agent import (
    AppSelection,
    create_native_app,
    validate_model_destination,
    validate_native_input,
    validate_runtime_store_environment,
)
from examples.journeys.agent_apps.stage_shared_sources import main, stage_project
from examples.real_framework_handler import owned_thread

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "examples/journeys/agent_apps"
TEMPLATES = {"langgraph": "langgraph", "openai_agents": "openai"}
ALL_TEMPLATES = (*TEMPLATES, "crewai")


def inert_environment() -> dict[str, str]:
    """Supply symbolic values solely to pure configuration validation, not the SDK."""
    return {
        "EVALSURGE_SAMPLE_WORKSPACE_HOST": "https://approved-workspace.example.invalid",
        "DATABRICKS_HOST": "https://approved-workspace.example.invalid",
        "MODEL_SERVICE_NAME": "system.ai.selected-model-service",
        "DATABRICKS_CLIENT_ID": "inert-app-id",
        "DATABRICKS_CLIENT_SECRET": "inert-symbolic-value-never-used-for-auth",
    }


def public_source_checkout(tmp_path: Path) -> Path:
    """Copy only the public files that staging reads, never private bundles/.git."""
    target = tmp_path / "public-source-checkout"
    sources = [
        ROOT / "examples/real_framework_handler.py",
        DIRECTORY / "shared/native_agent.py",
        DIRECTORY / "reviewed_sources.json",
    ]
    sources.extend(
        DIRECTORY / template / filename
        for template in ALL_TEMPLATES
        for filename in (
            "README.md",
            "app.py",
            "app.yaml",
            "agent.toml",
            "pyproject.toml",
            "model_resource.example.json",
        )
        if (DIRECTORY / template / filename).exists()
    )
    for source in sources:
        destination = target / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return target


def test_selection_is_secret_free_without_resolving_credentials() -> None:
    """Validate native App selections only; symbolic credentials never reach an SDK."""
    selection = AppSelection.from_environment(inert_environment())
    assert selection.workspace_host == "https://approved-workspace.example.invalid"
    assert selection.model == "system.ai.selected-model-service"
    assert selection.max_output_tokens == 512
    assert selection.timeout_seconds == 30
    assert selection.base_url.endswith("/ai-gateway/mlflow/v1")
    assert "inert-app-id" not in repr(selection)
    assert "inert-symbolic-value" not in repr(selection)


@pytest.mark.parametrize(
    "host",
    (
        "",
        "REPLACE_WITH_EXACT_HTTPS_WORKSPACE_ORIGIN",
        "http://workspace.example.invalid",
        "HTTPS://workspace.example.invalid",
        "https://workspace.example.invalid/",
        "https://workspace.example.invalid/path",
        "https://workspace.example.invalid?query=true",
        "https://workspace.example.invalid#fragment",
        "https://workspace.example.invalid:443",
        "https://private-label@workspace.example.invalid",
        "https://[bad-bracket",
        "https://work\tspace.example.invalid",
        "https://work\nspace.example.invalid",
        " https://workspace.example.invalid",
        "https://workspace.example.invalid\x00",
        "https://workspace.example.invalid\x7f",
        "https://workspace.example.invalid\\path",
    ),
)
def test_invalid_workspace_origins_fail_before_authentication(host: str) -> None:
    """Intentional pre-authentication failures; no inference is exercised."""
    environment = inert_environment() | {
        "EVALSURGE_SAMPLE_WORKSPACE_HOST": host,
        "DATABRICKS_HOST": host,
    }
    with pytest.raises(ValueError, match="exact HTTPS workspace origin"):
        AppSelection.from_environment(environment)


def test_workspace_mismatch_rejects_without_disclosing_submitted_origins() -> None:
    environment = inert_environment() | {"DATABRICKS_HOST": "https://different.example.invalid"}
    with pytest.raises(ValueError, match="match the approved origin") as failure:
        AppSelection.from_environment(environment)
    assert "different.example.invalid" not in str(failure.value)


def test_uppercase_scheme_fails_during_selection_construction_before_sdk_setup() -> None:
    """Reject a noncanonical origin in the pure constructor, without native imports."""
    with pytest.raises(ValueError, match="exact HTTPS workspace origin"):
        AppSelection("HTTPS://approved-workspace.example.invalid", "selected-model")


@pytest.mark.parametrize("model", ("", " ", "model/route", "https://model.invalid", "x" * 129))
def test_invalid_model_resource_selection_fails_before_authentication(model: str) -> None:
    with pytest.raises(ValueError, match="MODEL_SERVICE_NAME"):
        AppSelection.from_environment(inert_environment() | {"MODEL_SERVICE_NAME": model})


@pytest.mark.parametrize("selector", ("DATABRICKS_TOKEN", "DATABRICKS_CONFIG_PROFILE"))
def test_pat_or_laptop_profile_is_not_silently_used(selector: str) -> None:
    with pytest.raises(ValueError, match="not a token or profile") as failure:
        AppSelection.from_environment(inert_environment() | {selector: "private-marker"})
    assert "private-marker" not in str(failure.value)


@pytest.mark.parametrize("auth_type", ("pat", "databricks-cli", "runtime", "oauth-u2m"))
def test_only_explicit_app_oauth_is_permitted(auth_type: str) -> None:
    with pytest.raises(ValueError, match="requires oauth-m2m"):
        AppSelection.from_environment(inert_environment() | {"DATABRICKS_AUTH_TYPE": auth_type})


@pytest.mark.parametrize("key", ("DATABRICKS_CLIENT_ID", "DATABRICKS_CLIENT_SECRET"))
@pytest.mark.parametrize("value", ("", " "))
def test_missing_app_oauth_credentials_are_configuration_failures(key: str, value: str) -> None:
    with pytest.raises(ValueError, match="App-injected OAuth client credentials"):
        AppSelection.from_environment(inert_environment() | {key: value})


@pytest.mark.parametrize("tokens", (0, 513, True, 1.5))
def test_operator_token_bounds_cannot_be_relaxed(tokens: int) -> None:
    with pytest.raises(ValueError, match="output-token cap"):
        AppSelection("https://approved.example.invalid", "selected-model", tokens)


@pytest.mark.parametrize("timeout", (0, 31, float("inf"), float("nan"), True))
def test_operator_timeout_bounds_cannot_be_relaxed(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout"):
        AppSelection("https://approved.example.invalid", "selected-model", timeout_seconds=timeout)


def test_exact_single_user_message_is_preserved_without_inference() -> None:
    query = "  Is an unopened item returnable after 20 days?  "
    assert validate_native_input([{"role": "user", "content": query}], attempt=1) == query


@pytest.mark.parametrize(
    "value",
    (
        None,
        {},
        [],
        ["query"],
        [{"role": "user", "content": "question"}] * 2,
        [{"role": "assistant", "content": "question"}],
        [{"role": "user", "content": ""}],
        [{"role": "user", "content": " "}],
        [{"role": "user", "content": "x" * 513}],
        [{"role": "user", "content": {"private": "invalid"}}],
        [{"role": "user", "content": "question", "custom_inputs": {"actor": "ignored?"}}],
        [{"role": "user", "content": "question", "model": "must-not-route"}],
    ),
)
def test_unsupported_inputs_are_rejected_not_dropped(value: Any) -> None:
    """Intentional pre-provider validation only, never a fake successful agent."""
    with pytest.raises(ValueError):
        validate_native_input(value, attempt=1)


@pytest.mark.parametrize("attempt", (0, 2, True, "1"))
def test_recovery_or_untyped_attempt_is_rejected_before_inference(attempt: int) -> None:
    with pytest.raises(ValueError, match="recovery/reinvocation is disabled"):
        validate_native_input([{"role": "user", "content": "question"}], attempt=attempt)


def test_intentional_pre_provider_failure_is_labeled_not_model_success() -> None:
    with pytest.raises(ValueError, match="Intentional pre-provider failure; no model was called"):
        validate_native_input(
            [{"role": "user", "content": "__evalsurge_fail_preflight__"}], attempt=1
        )


def test_model_destination_is_exact_before_credentials_are_requested() -> None:
    selection = AppSelection.from_environment(inert_environment())
    validate_model_destination("POST", f"{selection.base_url}/responses", selection)


@pytest.mark.parametrize(
    "method,url",
    (
        ("GET", "https://approved-workspace.example.invalid/ai-gateway/mlflow/v1/responses"),
        ("POST", "https://other.example.invalid/ai-gateway/mlflow/v1/responses"),
        ("POST", "https://approved-workspace.example.invalid/ai-gateway/openai/v1/responses"),
        ("POST", "https://approved-workspace.example.invalid/ai-gateway/mlflow/v1/responses?x=1"),
        ("POST", "https://approved-workspace.example.invalid/ai-gateway/mlflow/v1/responses/"),
    ),
)
def test_model_destination_cannot_be_changed_by_a_transport_request(method: str, url: str) -> None:
    with pytest.raises(ValueError, match="outside the approved"):
        validate_model_destination(method, url, AppSelection.from_environment(inert_environment()))


def test_unknown_native_framework_fails_before_optional_runtime_import() -> None:
    with pytest.raises(ValueError, match="prepared native App framework"):
        create_native_app("not-a-framework")


@pytest.mark.parametrize("template,framework", TEMPLATES.items())
def test_native_template_manifest_has_explicit_candidate_dependencies(
    template: str, framework: str
) -> None:
    """Read public metadata; no installer/native optional package is executed."""
    project = tomllib.loads((DIRECTORY / template / "pyproject.toml").read_text())
    assert project["project"]["requires-python"] == ">=3.11,<3.12"
    dependencies = project["project"]["dependencies"]
    assert "databricks-agentbricks==0.4.0" in dependencies
    assert "databricks-sdk==0.148.0" in dependencies
    assert "openai==3.22.1" in dependencies
    assert all("==" in item for item in dependencies)
    assert not any(item.startswith(("evalsurge", "locust", "crewai")) for item in dependencies)
    assert project["tool"]["uv"]["package"] is False
    if framework == "langgraph":
        assert "langgraph==1.2.12" in dependencies
        assert not any(item.startswith("openai-agents") for item in dependencies)
    else:
        assert "openai-agents==0.22.3" in dependencies
        assert not any(item.startswith("langgraph") for item in dependencies)
    agent = tomllib.loads((DIRECTORY / template / "agent.toml").read_text())
    assert agent["schema_version"] == 1
    assert agent["agent"] == {
        "framework": framework,
        "server": "agentbricks",
        "deployment_name": "REPLACE_WITH_OPERATOR_SELECTED_APP_NAME",
    }


@pytest.mark.parametrize("template", TEMPLATES)
def test_native_app_environment_is_resource_bound_without_secrets(template: str) -> None:
    configuration = yaml.safe_load((DIRECTORY / template / "app.yaml").read_text())
    assert configuration["command"] == ["uv", "run", "--no-dev", "python", "app.py"]
    environment = {value["name"]: value for value in configuration["env"]}
    assert set(environment) == {"EVALSURGE_SAMPLE_WORKSPACE_HOST", "MODEL_SERVICE_NAME"}
    assert environment["MODEL_SERVICE_NAME"] == {"name": "MODEL_SERVICE_NAME", "valueFrom": "model"}
    assert environment["EVALSURGE_SAMPLE_WORKSPACE_HOST"]["value"].startswith("REPLACE_")
    assert "resources" not in configuration


def test_native_source_keeps_actual_runtime_and_shared_handler_boundaries() -> None:
    """Syntax/AST regression only; does not certify native startup/model behavior."""
    source = (DIRECTORY / "shared/native_agent.py").read_text()
    tree = ast.parse(source)
    compile(tree, "native_agent.py", "exec")
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "databricks_agentkit" in imports
    assert "real_framework_handler" in imports
    assert not imports.intersection(
        {"evalsurge", "evalsurge.serving", "benchmark_agents.providers"}
    )
    assert "DefaultAsyncHttpxClient" in source
    assert "await owned_thread(configure)" in source
    assert "await owned_thread(config.authenticate)" in source
    assert "validate_runtime_store_environment(os.environ)" in source
    assert 'config_file="/dev/null"' in source
    assert "async with native_lifespan(app)" in source
    assert "@app.invoke" in source
    assert "@app.recover" not in source
    assert "answer.output_tokens" in source
    assert "answer.usage" not in source
    assert "follow_redirects=False" in source and "trust_env=False" in source
    assert "max_retries=0" in source
    assert "create_real_app" not in source
    for name in ALL_TEMPLATES:
        filename = DIRECTORY / name / "app.py"
        compile(filename.read_text(), str(filename), "exec")


def test_managed_store_guard_precedes_native_import_and_construction() -> None:
    """Check startup ordering without constructing Runtime or replacing its imports."""
    tree = ast.parse((DIRECTORY / "shared/native_agent.py").read_text())
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "create_native_app"
    )
    guard = next(
        node
        for node in function.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "validate_runtime_store_environment"
    )
    native_import = next(
        node
        for node in function.body
        if isinstance(node, ast.ImportFrom) and node.module == "databricks_agentkit"
    )
    construction = next(
        node
        for node in function.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "DurableAgentServer"
    )
    assert isinstance(guard.value.args[0], ast.Attribute)
    assert isinstance(guard.value.args[0].value, ast.Name)
    assert guard.value.args[0].value.id == "os" and guard.value.args[0].attr == "environ"
    assert guard.lineno < native_import.lineno < construction.lineno


def test_shared_source_hashes_are_exact_and_not_historical_bundle_paths() -> None:
    review = json.loads((DIRECTORY / "reviewed_sources.json").read_text())
    assert review["schema_version"] == 1
    assert set(review["shared_source_sha256"]) == {
        "examples/real_framework_handler.py",
        "examples/journeys/agent_apps/shared/native_agent.py",
    }
    for relative_path, approved_digest in review["shared_source_sha256"].items():
        assert hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest() == approved_digest
    assert "/private/tmp" not in json.dumps(review)


@pytest.mark.parametrize("template", ALL_TEMPLATES)
def test_staging_prepares_exact_agent_source_and_records_pending_gates(
    template: str, tmp_path: Path
) -> None:
    """Perform temporary public-file writes only; no deployment or model calls."""
    destination = tmp_path / template
    manifest_path = stage_project(template, repository_root=ROOT, destination=destination)
    manifest = json.loads(manifest_path.read_text())
    assert manifest["template"] == template
    assert manifest["prepared_only"] is True
    assert manifest["dependency_resolution"] == manifest["deployment"] == "not_run"
    assert manifest["live_inference"] == "not_run"
    assert manifest["deployment_route"] == (
        "unresolved" if template == "crewai" else "agentbricks_deploy"
    )
    expected = {
        "real_framework_handler.py",
        "native_agent.py",
        "app.py",
        "app.yaml",
        "agent.toml",
        "pyproject.toml",
    }
    if template == "crewai":
        expected.remove("agent.toml")
        expected.update({"README.md", "model_resource.example.json"})
    assert set(manifest["files"]) == expected
    for filename, record in manifest["files"].items():
        actual = (destination / filename).read_bytes()
        assert actual == (ROOT / record["source"]).read_bytes()
        assert hashlib.sha256(actual).hexdigest() == record["sha256"]
    assert not (destination / "uv.lock").exists()
    assert not (destination / "wheels").exists()


def test_staging_refuses_existing_destination_without_overwriting(tmp_path: Path) -> None:
    destination = tmp_path / "operator-owned"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("operator-owned")
    with pytest.raises(ValueError, match="must not already exist"):
        stage_project("langgraph", repository_root=ROOT, destination=destination)
    assert marker.read_text() == "operator-owned"
    assert set(destination.iterdir()) == {marker}


def test_staging_rejects_changed_shared_source_before_creating_project(tmp_path: Path) -> None:
    checkout = public_source_checkout(tmp_path)
    handler = checkout / "examples/real_framework_handler.py"
    handler.write_bytes(handler.read_bytes() + b"\n# unreviewed change\n")
    destination = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="shared source changed"):
        stage_project("langgraph", repository_root=checkout, destination=destination)
    assert not destination.exists()


def test_staging_rejects_symlinked_shared_source(tmp_path: Path) -> None:
    checkout = public_source_checkout(tmp_path)
    source = checkout / "examples/real_framework_handler.py"
    source.unlink()
    source.symlink_to(ROOT / "examples/real_framework_handler.py")
    with pytest.raises(ValueError, match="absent or is a symlink"):
        stage_project("langgraph", repository_root=checkout, destination=tmp_path / "reject")


def test_staging_never_maps_an_unknown_framework_to_another(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="explicitly"):
        stage_project("unknown", repository_root=ROOT, destination=tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()


def test_preparation_cli_does_not_claim_deployment_or_inference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(
        [
            "--template",
            "openai_agents",
            "--repository-root",
            str(ROOT),
            "--destination",
            str(tmp_path / "prepared-project"),
        ]
    )
    assert "deployment and live inference are not run" in capsys.readouterr().out


def test_crewai_unresolved_route_is_not_a_false_managed_cli_label() -> None:
    """Read the declared scope; no CrewAI import/fixture/inference occurs."""
    source = " ".join((DIRECTORY / "crewai/README.md").read_text().split())
    assert "not proof that CrewAI cannot be hosted on Databricks Apps" in source
    assert "macOS-compatible dependency constraints" in source
    assert "not a deployed or live-validated example" in source
    assert "deployment route unresolved" in source
    assert "must not be independently created, bound or changed" in source
    assert "not been verified for this installed version" in source
    assert 'create_native_app("crewai")' in (DIRECTORY / "crewai/app.py").read_text()
    assert not (DIRECTORY / "crewai/agent.toml").exists()


def test_crewai_constraints_do_not_claim_an_audited_release_or_app_lock() -> None:
    """Inspect project metadata only, not installed CrewAI/model APIs."""
    project = tomllib.loads((DIRECTORY / "crewai/pyproject.toml").read_text())
    dependencies = project["project"]["dependencies"]
    assert "crewai==1.15.23" in dependencies
    assert "openai>=2.30.0,<3" in dependencies
    assert "pydantic>=2.11.9,<2.13" in dependencies
    assert "databricks-agentbricks==0.4.0" in dependencies
    assert not any(
        item.startswith(("evalsurge", "locust", "openai-agents")) for item in dependencies
    )
    assert not any("agentbricks[" in item for item in dependencies)
    assert not (DIRECTORY / "crewai/uv.lock").exists()
    assert (
        "macOS-compatible dependency constraints"
        in (DIRECTORY / "crewai/pyproject.toml").read_text()
    )


def test_crewai_prerequisite_report_preserves_failed_advisory_and_native_route_gates() -> None:
    """Keep documented prerequisite evidence distinct from model/deployment success."""
    source = " ".join((DIRECTORY / "crewai/README.md").read_text().split())
    assert "162 distributions" in source
    assert "advisory gate failed" in source
    assert "inspected, not installed" in source
    for advisory in (
        "PYSEC-2026-311",
        "PYSEC-2026-3813",
        "PYSEC-2026-3814",
        "PYSEC-2026-3815",
    ):
        assert advisory in source
    assert "Do not suppress those findings" in source
    assert "every fresh CrewAI live matrix cell are **not run**" in source


def test_crewai_raw_resource_example_is_not_an_sdk_enum_or_resource_list_replace() -> None:
    """Read placeholder JSON; do not submit it to any CLI/API or mutate resources."""
    resource = json.loads((DIRECTORY / "crewai/model_resource.example.json").read_text())
    assert resource == {
        "name": "model",
        "uc_securable": {
            "securable_full_name": "system.ai.REPLACE_WITH_EXPLICIT_MODEL_SERVICE",
            "securable_type": "MODEL_SERVICE",
            "permission": "EXECUTE",
        },
    }
    assert "resources" not in resource
    configuration = yaml.safe_load((DIRECTORY / "crewai/app.yaml").read_text())
    environment = {entry["name"]: entry for entry in configuration["env"]}
    assert environment["CREWAI_DISABLE_TELEMETRY"]["value"] == "true"
    assert environment["MODEL_SERVICE_NAME"]["valueFrom"] == "model"
    assert all("SECRET" not in name and "TOKEN" not in name for name in environment)
    assert not any("PROFILE" in name for name in environment)
    assert not any("RUNTIME_STORE" in name for name in environment)


def managed_store_environment() -> dict[str, str]:
    """Return symbolic references for configuration validation, not real resources."""
    return {
        "DATABRICKS_AGENTBRICKS_RUNTIME_STORE_LAKEBASE_BRANCH": "selected-branch-reference",
        "DATABRICKS_AGENTBRICKS_RUNTIME_STORE_DATABASE": "selected-database-reference",
        "DATABRICKS_AGENTBRICKS_RUNTIME_STORE_USERNAME": "selected-username-reference",
    }


def test_managed_store_validation_is_not_a_connection_or_readiness_check() -> None:
    validate_runtime_store_environment(managed_store_environment())


@pytest.mark.parametrize("field", tuple(managed_store_environment()))
@pytest.mark.parametrize("value", ("", " ", "REPLACE_WITH_SELECTION"))
def test_absent_or_placeholder_store_selection_never_defaults_to_memory(
    field: str, value: str
) -> None:
    with pytest.raises(ValueError, match="Select the managed Runtime Store"):
        validate_runtime_store_environment(managed_store_environment() | {field: value})


def test_process_local_store_marker_cannot_override_deployed_durability() -> None:
    with pytest.raises(ValueError, match="managed durable Runtime Store"):
        validate_runtime_store_environment(
            managed_store_environment() | {"DATABRICKS_AGENTBRICKS_RUNTIME_STORE_LOCAL": "TRUE"}
        )


def test_unreviewed_legacy_store_route_is_not_silently_selected() -> None:
    with pytest.raises(ValueError, match="reviewed managed store route"):
        validate_runtime_store_environment(
            managed_store_environment()
            | {"DATABRICKS_AGENTBRICKS_RUNTIME_STORE_LAKEBASE_ENDPOINT": "legacy-reference"}
        )


@pytest.mark.parametrize("value", (None, True, 42))
def test_invalid_host_types_are_safe_configuration_failures(value: Any) -> None:
    with pytest.raises(ValueError, match="exact HTTPS workspace origin"):
        AppSelection(value, "selected-model")


async def wait_for_thread_start(started: Event) -> None:
    """Wait at most one second for a local inert thread, without an auth/model stub."""
    async with asyncio.timeout(1):
        while not started.is_set():
            await asyncio.sleep(0.001)


async def observe_thread_cleanup(task: asyncio.Task[Any], release: Event) -> None:
    """Release and observe each test-owned inert thread, including failure paths."""
    release.set()
    with suppress(asyncio.CancelledError):
        await asyncio.wait_for(asyncio.shield(task), 3)


@pytest.mark.asyncio
async def test_canonical_owned_thread_preserves_native_result_and_failure() -> None:
    """Execute real stdlib thread scheduling only; no provider is mocked/called."""
    assert await owned_thread(sum, (1, 2, 3)) == 6

    def failure() -> None:
        raise ValueError("inert native failure")

    with pytest.raises(ValueError, match="inert native failure"):
        await owned_thread(failure)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancellations", (1, 2))
@pytest.mark.parametrize("worker_fails", (False, True))
async def test_native_sdk_thread_ownership_retains_cancellation_until_work_settles(
    cancellations: int, worker_fails: bool
) -> None:
    """Thread-only cancellation: no Runtime construction, SDK auth or inference.

    The native entrypoint imports this exact checksum-staged canonical helper.
    Its real thread keeps running after cancellation, must be observed before
    propagation, and cannot replace caller cancellation with a later failure.
    """
    started, release, finished = Event(), Event(), Event()

    def work() -> int:
        started.set()
        try:
            if not release.wait(timeout=2):
                raise TimeoutError("inert test thread did not receive its release")
            if worker_fails:
                raise ValueError("inert worker failure after cancellation")
            return 7
        finally:
            finished.set()

    task = asyncio.create_task(owned_thread(work))
    try:
        await wait_for_thread_start(started)
        for _ in range(cancellations):
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
        assert not finished.is_set()
        # Unrelated event-loop work continues while the real owned thread waits.
        assert await owned_thread(sum, (2, 3)) == 5
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert finished.is_set()
    finally:
        await observe_thread_cleanup(task, release)
