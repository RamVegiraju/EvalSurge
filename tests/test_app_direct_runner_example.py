"""Non-inference App-runner source/schema/storage checks; no SDK/provider calls.

These tests do not demonstrate cloud installation, App deployment, worker OAuth,
cloud claim atomicity or actual model inference. Inert thread/file fixtures check
local ownership only, and never replace a hosted agent or LLM response.
"""

import ast
import asyncio
import hashlib
import json
import threading
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from examples.journeys.app_runner import app as app_module
from examples.journeys.app_runner import runner

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "journeys" / "app_runner"


def configuration(**updates):
    """Read the disabled nonsecret template; no live source or model is consulted."""
    values = json.loads((SAMPLE / "operator.example.json").read_text())
    return runner.OperatorConfig.model_validate({**values, **updates})


@pytest.mark.parametrize("template", ["operator.example.json", "operator.native.example.json"])
def test_disabled_templates_require_an_explicit_reviewed_artifact_hash(template: str) -> None:
    """Keep template hashes inert; never reuse evidence for a different wheel."""
    values = json.loads((SAMPLE / template).read_text())
    assert values["enabled"] is False
    assert values["reviewed_sha256"] == "0" * 64


def test_app_runner_has_read_only_content_free_routes_and_no_benchmark_api() -> None:
    routes = {route.path: route.methods for route in app_module.app.routes}
    assert routes == {"/healthz": {"GET"}, "/status": {"GET"}}
    assert app_module.health() == {"service": "private-evalsurge-direct-runner", "health": "up"}
    assert set(app_module.status()) == {
        "state",
        "passed",
        "benchmark_passed",
        "approval_consumed_observed",
        "protected_export_ready",
        "export_status",
    }
    assert "benchmark_agents.api" not in (SAMPLE / "app.py").read_text()
    assert app_module.app.openapi_url is None


def test_disabled_app_lifecycle_performs_no_sdk_work() -> None:
    """Run its real disabled lifespan only; this is not a stubbed inference test."""

    async def check():
        async with app_module.lifespan(app_module.app):
            assert app_module.status()["state"] == "disabled"
            assert app_module.status()["approval_consumed_observed"] is False

    asyncio.run(check())


def test_fixed_request_is_small_direct_load_only_and_has_no_operator_secrets() -> None:
    request = runner.request()
    assert request.load.concurrency == 1
    assert request.load.max_requests == 1
    assert request.load.duration_seconds == 5
    assert request.load.timeout_seconds == 30
    assert request.evaluation.mode == "off"
    assert "profile" not in request.model_dump_json()
    assert "workspace" not in request.model_dump_json()
    assert "workspace_id" not in request.model_dump_json()


def test_native_sample_workspace_identifier_is_operator_owned_and_not_a_profile_field() -> None:
    """Check inert operator bindings only, without SDK construction or inference."""
    values = json.loads((SAMPLE / "operator.native.example.json").read_text())
    config = runner.OperatorConfig.model_validate(values)
    assert config.workspace_id == "1234567890123456"
    assert runner.native_app_binding(config).registration.workspace_id == config.workspace_id
    with pytest.raises(ValidationError):
        configuration(workspace_id=config.workspace_id)


@pytest.mark.parametrize("workspace_id", ["", "0", "01", "1" * 21, "-1", " 1", "1.0"])
def test_native_sample_rejects_noncanonical_workspace_identifier(workspace_id: str) -> None:
    """Reject invalid operator IDs without SDK construction or inference."""
    values = json.loads((SAMPLE / "operator.native.example.json").read_text())
    with pytest.raises(ValidationError):
        runner.OperatorConfig.model_validate({**values, "workspace_id": workspace_id})


def test_exact_http_and_app_bindings_are_separate() -> None:
    app_config = configuration()
    assert app_config.target_kind == "databricks-app"
    assert app_config.enabled is False
    http_config = configuration(
        target_kind="http",
        http_url="https://agent.example.com/invoke",
        app_name=None,
        profile=None,
        oauth_config_file=None,
        oauth_client_id=None,
    )
    assert http_config.http_url == "https://agent.example.com/invoke"
    with pytest.raises(ValidationError):
        configuration(target_kind="http", http_url="https://agent.example.com/invoke")
    with pytest.raises(ValidationError):
        configuration(http_url="https://agent.example.com/invoke")


def test_native_app_runner_configuration_is_inert_and_distinct(monkeypatch) -> None:
    """Construct public native identity bindings only, without SDK/model fixtures."""
    import databricks.sdk

    monkeypatch.setattr(
        databricks.sdk, "WorkspaceClient", lambda **_: pytest.fail("SDK construction")
    )
    values = json.loads((SAMPLE / "operator.native.example.json").read_text())
    config = runner.OperatorConfig.model_validate(values)
    assert config.enabled is False
    agent = runner.native_app_binding(config)
    assert agent.registration.app_auth == "app-runtime"
    assert agent.registration.profile is None
    assert agent.registration.runner_app == "your-runner-app"
    assert "client_secret" not in config.model_dump_json()
    assert "oauth_config_file" not in runner.request().model_dump_json()
    for changes in (
        {"profile": "selected"},
        {"oauth_config_file": "/private/config"},
        {"runner_app": None},
        {"oauth_client_id": "12345"},
        {"target_kind": "http", "http_url": "https://agent.example/invoke"},
    ):
        with pytest.raises(ValidationError):
            runner.OperatorConfig.model_validate({**values, **changes})


def test_native_app_bundle_is_standalone_with_explicit_target_and_volume_resources() -> None:
    import yaml

    bundle = yaml.safe_load((SAMPLE / "databricks.native.yml").read_text())
    assert set(bundle["variables"]) == {"runner_app_name", "result_volume", "target_app_name"}
    app = bundle["resources"]["apps"]["private_runner"]
    resources = {item["name"]: item for item in app["resources"]}
    assert resources["benchmark-target"]["app"] == {
        "name": "${var.target_app_name}",
        "permission": "CAN_USE",
    }
    assert resources["result-artifacts"]["uc_securable"]["permission"] == "WRITE_VOLUME"
    assert resources["result-artifacts-read"]["uc_securable"]["permission"] == "READ_VOLUME"
    assert app["config"]["command"] == ["python", "app.py"]


@pytest.mark.parametrize("template", ["databricks.yml", "databricks.native.yml"])
def test_bundle_and_runtime_volume_environment_use_their_distinct_contract_keys(
    template: str,
) -> None:
    """Validate configuration schemas only; no deployment, authentication or inference."""
    bundle = yaml.safe_load((SAMPLE / template).read_text())
    config = bundle["resources"]["apps"]["private_runner"]["config"]
    bundle_environment = {item["name"]: item for item in config["env"]}
    runtime = yaml.safe_load((SAMPLE / "app.yaml").read_text())
    runtime_environment = {item["name"]: item for item in runtime["env"]}
    assert bundle_environment["EVALSURGE_EXPORT_VOLUME"] == {
        "name": "EVALSURGE_EXPORT_VOLUME",
        "value_from": "result-artifacts",
    }
    assert runtime_environment["EVALSURGE_EXPORT_VOLUME"] == {
        "name": "EVALSURGE_EXPORT_VOLUME",
        "valueFrom": "result-artifacts",
    }
    assert runtime["command"] == config["command"]


@pytest.mark.parametrize(
    "hostname", ["localhost", "LOCALHOST.", "127.0.0.1", "0.0.0.0", "[::1]", "[::]"]
)
def test_app_runner_never_teaches_laptop_loopback_as_reachable(hostname: str) -> None:
    with pytest.raises(ValidationError):
        configuration(
            target_kind="http",
            http_url=f"https://{hostname}:9000/invoke",
            app_name=None,
            profile=None,
            oauth_config_file=None,
            oauth_client_id=None,
        )


@pytest.mark.parametrize(
    "path", ["/tmp/anything", "/Volumes/c/s/v/extra", "/Volumes/c/s/../v", "/Volumes/c/s/v?x"]
)
def test_only_exact_protected_volume_resource_root_is_accepted(path: str) -> None:
    with pytest.raises(ValueError):
        runner.export_root(path)
    assert runner.export_root("/Volumes/catalog/schema/volume") == (
        "/Volumes/catalog/schema/volume/evalsurge-app-runner"
    )
    assert runner.export_root("catalog.schema.volume") == (
        "/Volumes/catalog/schema/volume/evalsurge-app-runner"
    )


def test_nonsecret_config_errors_are_fixed_value_free_and_bounded(tmp_path: Path) -> None:
    path = tmp_path / "operator.json"
    marker = "DO_NOT_DISCLOSE_THIS_SECRET"
    path.write_text(json.dumps({"secret": marker}))
    with pytest.raises(ValueError) as error:
        runner.read_config(path)
    assert marker not in str(error.value)
    assert "operator.json" not in str(error.value)
    path.write_bytes(b" " * 65_537)
    with pytest.raises(ValueError):
        runner.read_config(path)


def test_fresh_consent_and_artifact_hash_gate_uses_only_local_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Synthetic file bytes are an artifact-check fixture, never agent output."""
    wheel = tmp_path / "wheel" / "reviewed.whl"
    wheel.parent.mkdir()
    wheel.write_bytes(b"inert-local-artifact-check-fixture")
    now = datetime.now(UTC)
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    monkeypatch.setattr(runner, "version", lambda _name: "test-artifact-version")
    cfg = configuration(
        enabled=True,
        accept_paid_traffic=True,
        real_inference_attested=True,
        approval_expires_at=(now + timedelta(minutes=5)).isoformat(),
        reviewed_wheel="wheel/reviewed.whl",
        reviewed_sha256=digest,
        reviewed_version="test-artifact-version",
    )
    runner.validate_launch(cfg, tmp_path, now=now)
    for update in (
        {"enabled": False},
        {"accept_paid_traffic": False},
        {"real_inference_attested": False},
        {"approval_expires_at": (now - timedelta(seconds=1)).isoformat()},
        {"approval_expires_at": (now + timedelta(minutes=11)).isoformat()},
        {"reviewed_sha256": "0" * 64},
    ):
        with pytest.raises(ValueError):
            runner.validate_launch(cfg.model_copy(update=update), tmp_path, now=now)


def test_approval_is_rechecked_after_elapsed_setup_without_auth_or_inference() -> None:
    """Pure time-boundary checks; no SDK discovery or target dispatch is simulated."""
    admitted_at = datetime(2026, 10, 11, 16, 0, tzinfo=UTC)
    expiry = admitted_at + timedelta(seconds=30)
    cfg = configuration(
        enabled=True,
        accept_paid_traffic=True,
        real_inference_attested=True,
        approval_expires_at=expiry.isoformat(),
    )
    runner.validate_approval(cfg, now=admitted_at)
    runner.validate_approval(cfg, now=expiry - timedelta(microseconds=1))
    for current in (expiry, expiry + timedelta(seconds=1), admitted_at.replace(tzinfo=None)):
        with pytest.raises(ValueError, match="Consent expired"):
            runner.validate_approval(cfg, now=current)
    for raw_expiry in ("not-an-expiry", expiry.replace(tzinfo=None).isoformat()):
        with pytest.raises(ValueError, match="Consent expired"):
            runner.validate_approval(
                cfg.model_copy(update={"approval_expires_at": raw_expiry}), now=admitted_at
            )
    with pytest.raises(ValueError, match="Consent expired"):
        runner.validate_approval(
            cfg.model_copy(
                update={"approval_expires_at": (admitted_at + timedelta(minutes=11)).isoformat()}
            ),
            now=admitted_at,
        )


def test_approval_rechecks_immediately_precede_claim_and_target_branch() -> None:
    """AST-only dispatch-order contract; no auth/storage/target path is executed."""
    tree = ast.parse((SAMPLE / "runner.py").read_text())
    once = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_once"
    )
    guarded = next(node for node in once.body if isinstance(node, ast.Try))
    statements = [ast.unparse(node) for node in guarded.body]
    claim = next(index for index, source in enumerate(statements) if "store.files.upload" in source)
    dispatch = next(index for index, source in enumerate(statements) if "receipt = await" in source)
    assert statements[claim - 1] == "validate_approval(config, now=datetime.now(UTC))"
    assert statements[dispatch - 1] == "validate_approval(config, now=datetime.now(UTC))"
    assert any(
        "await _store_call(_assigned_store, config)" in source for source in statements[:claim]
    )


def test_evidence_archive_is_bounded_and_rejects_symlinks(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "run.json").write_text('{"state":"failed"}')
    archive = runner.archive_artifacts(artifacts)
    with zipfile.ZipFile(archive) as opened:
        assert opened.namelist() == ["run.json"]
        assert json.loads(opened.read("run.json")) == {"state": "failed"}
    (artifacts / "link").symlink_to(tmp_path)
    with pytest.raises(ValueError):
        runner.archive_artifacts(artifacts)


def test_cancelled_inert_thread_call_is_owned_until_it_finishes() -> None:
    """Real thread synchronization; no SDK transport, framework or model is mocked."""
    entered = threading.Event()
    released = threading.Event()
    finished = threading.Event()

    def inert_local_operation():
        entered.set()
        assert released.wait(timeout=3)
        finished.set()

    async def check():
        task = asyncio.create_task(runner._store_call(inert_local_operation))
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()

    asyncio.run(check())


def test_sample_sources_compile_and_external_writes_never_overwrite() -> None:
    for filename in ("app.py", "runner.py"):
        ast.parse((SAMPLE / filename).read_text())
    source = (SAMPLE / "runner.py").read_text()
    assert source.count("overwrite=False") == 3
    assert "files.delete" not in source
    assert "os.environ[" not in source
    assert "retry_timeout_seconds=1" in source
    assert 'auth_type="oauth-m2m"' in source
    assert 'values.get("DATABRICKS_CLIENT_ID")' in source
    assert 'values.get("DATABRICKS_CLIENT_SECRET")' in source
    assert "store.config.client_id != native_id" in source
    assert (SAMPLE / "requirements.txt").read_text().count("[server]") == 1
    assert "pypi-proxy" not in "".join(path.read_text() for path in SAMPLE.glob("*.txt"))
    bundle = (SAMPLE / "databricks.yml").read_text()
    assert "permission: READ_VOLUME" in bundle
    assert "permission: WRITE_VOLUME" in bundle
    assert "value_from: result-artifacts" in bundle
    assert (SAMPLE / ".gitignore").read_text().startswith("wheel/\noperator.json\n")


def test_bundle_resources_use_native_sdk_volume_permissions_without_authentication() -> None:
    """Native SDK data classes only; no client, credential provider or API is constructed."""
    from databricks.sdk.service.apps import AppResource

    bundle = yaml.safe_load((SAMPLE / "databricks.yml").read_text())
    declaration = bundle["resources"]["apps"]["private_runner"]
    resources = [AppResource.from_dict(item).as_dict() for item in declaration["resources"]]
    assert [item["uc_securable"]["permission"] for item in resources] == [
        "WRITE_VOLUME",
        "READ_VOLUME",
    ]
    assert all(item["uc_securable"]["securable_type"] == "VOLUME" for item in resources)
    assert all(
        item["uc_securable"]["securable_full_name"] == "${var.result_volume}" for item in resources
    )
    runtime = yaml.safe_load((SAMPLE / "app.yaml").read_text())
    assert runtime["command"] == declaration["config"]["command"]


def test_cloud_http_has_explicit_https_guidance_before_native_agent_binding() -> None:
    with pytest.raises(ValidationError, match="Cloud runner HTTP targets require HTTPS"):
        configuration(
            target_kind="http",
            http_url="http://agent.example.com/invoke",
            app_name=None,
            profile=None,
            oauth_config_file=None,
            oauth_client_id=None,
        )


def test_native_app_identity_gate_is_pure_and_workspace_bound() -> None:
    workspace = "https://your-workspace.cloud.databricks.com"
    values = {
        "DATABRICKS_HOST": workspace + "/",
        "DATABRICKS_CLIENT_ID": "inert-client-id",
        "DATABRICKS_CLIENT_SECRET": "INERT_SECRET_NEVER_LOGGED",
    }
    assert runner._native_app_identity(workspace, values) == "inert-client-id"
    for key in values:
        with pytest.raises(ValueError) as error:
            runner._native_app_identity(workspace, {k: v for k, v in values.items() if k != key})
        assert "INERT_SECRET_NEVER_LOGGED" not in str(error.value)
        assert workspace not in str(error.value)
    with pytest.raises(ValueError):
        runner._native_app_identity("https://other-workspace.cloud.databricks.com", values)


def test_sdk_initialization_occurs_only_in_an_owned_off_loop_operation() -> None:
    tree = ast.parse((SAMPLE / "runner.py").read_text())
    assigned = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_assigned_store"
    )
    once = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_once"
    )
    assigned_source = ast.unparse(assigned)
    assert assigned_source.index("_native_app_identity(") < assigned_source.index(
        "WorkspaceClient("
    )
    assert "await _store_call(_assigned_store, config)" in ast.unparse(once)
    assert "WorkspaceClient(" not in ast.unparse(once)


class InertLocalExportStore:
    """Real local-file sink for export ownership tests; no SDK/auth/cloud/provider.

    This intentionally replaces only a storage boundary, never a framework,
    target, inference transport or completion. Input receipts are lifecycle-only
    projection fixtures; structural files contain no agent responses.
    """

    def __init__(self, directory: Path, *, pause: str | None = None, fail: str | None = None):
        self.files = self
        self.directory = directory
        self.pause = pause
        self.fail = fail
        self.entered = threading.Event()
        self.released = threading.Event()
        self.finished = threading.Event()

    def upload(self, path, contents, *, overwrite):
        assert overwrite is False
        if self.pause and path.endswith(self.pause):
            self.entered.set()
            assert self.released.wait(timeout=3)
        if self.fail and path.endswith(self.fail):
            raise ValueError("inert-local-export-failure")
        with (self.directory / Path(path).name).open("xb") as output:
            output.write(contents.read())
        if self.pause and path.endswith(self.pause):
            self.finished.set()


def test_export_only_marks_journey_passed_after_artifact_and_receipt_finish(tmp_path: Path) -> None:
    """Exercise pure export projection/local files, not a claimed successful agent run."""
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "structural.json").write_text("{}")
    store = InertLocalExportStore(tmp_path, pause=".receipt.json")
    status = {"state": "completed", "passed": False}

    async def check():
        task = asyncio.create_task(
            runner._export_evidence(
                config=configuration(),
                directory=artifacts,
                store=store,
                root="/Volumes/c/s/v/evalsurge-app-runner",
                receipt={"state": "completed", "passed": True},
                status=status,
            )
        )
        assert await asyncio.to_thread(store.entered.wait, 3)
        assert status["passed"] is False
        assert status["benchmark_passed"] is True
        assert status["protected_export_ready"] is False
        store.released.set()
        await task
        assert status["passed"] is True
        assert status["export_status"] == "complete"
        assert status["protected_export_ready"] is True

    asyncio.run(check())


@pytest.mark.parametrize("stage", [".artifacts.zip", ".receipt.json"])
def test_cancelled_local_export_never_publishes_false_journey_success(
    tmp_path: Path, stage: str
) -> None:
    """Interrupt inert local storage; no inference outcome is executed or substituted."""
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "structural.json").write_text("{}")
    store = InertLocalExportStore(tmp_path, pause=stage)
    status = {"state": "completed", "passed": False}

    async def check():
        task = asyncio.create_task(
            runner._export_evidence(
                config=configuration(),
                directory=artifacts,
                store=store,
                root="/Volumes/c/s/v/evalsurge-app-runner",
                receipt={"state": "completed", "passed": True},
                status=status,
            )
        )
        assert await asyncio.to_thread(store.entered.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert status["passed"] is False
        store.released.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert store.finished.is_set()
        assert status["passed"] is False
        assert status["benchmark_passed"] is True
        assert status["protected_export_ready"] is False
        assert status["state"] == "export_interrupted"
        assert status["export_status"] == "interrupted"

    asyncio.run(check())


def test_failed_local_receipt_export_retains_separate_benchmark_projection(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "structural.json").write_text("{}")
    status = {"state": "completed", "passed": False}
    store = InertLocalExportStore(tmp_path, fail=".receipt.json")
    asyncio.run(
        runner._export_evidence(
            config=configuration(),
            directory=artifacts,
            store=store,
            root="/Volumes/c/s/v/evalsurge-app-runner",
            receipt={"state": "completed", "passed": True},
            status=status,
        )
    )
    assert status["benchmark_passed"] is True
    assert status["passed"] is False
    assert status["protected_export_ready"] is False
    assert status["export_status"] == "failed"
