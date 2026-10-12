"""Private one-shot App runner; no inbound benchmark service or agent hosting.

Construction is non-networked. Enabled execution consumes one external approval
claim before inference, uses the existing direct SDK/Locust engine, and exports
protected artifacts after cleanup. Nothing here certifies generator accuracy.
"""

import asyncio
import hashlib
import io
import ipaddress
import json
import os
import re
import stat
import tempfile
import zipfile
from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evalsurge import Case, Load, RunCreate, TargetReference

if TYPE_CHECKING:
    from evalsurge import Agent

MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_FILES = 512


class OperatorConfig(BaseModel):
    """Reviewed nonsecret configuration, never accepted from an HTTP caller."""

    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool = False
    accept_paid_traffic: bool = False
    real_inference_attested: bool = False
    approval_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    approval_expires_at: str = Field(max_length=64)
    workspace: str = Field(max_length=512)
    workspace_id: str | None = Field(default=None, pattern=r"^[1-9][0-9]{0,19}$", repr=False)
    target_kind: Literal["http", "databricks-app"]
    http_url: str | None = Field(default=None, max_length=2048)
    bearer_token_env: str | None = Field(
        default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,255}$", repr=False
    )
    app_name: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{0,29}$")
    app_auth: Literal["profile", "app-runtime"] = "profile"
    runner_app: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{0,29}$")
    profile: str | None = Field(default=None, min_length=1, max_length=128)
    oauth_config_file: str | None = Field(default=None, max_length=2048)
    oauth_client_id: str | None = Field(default=None, min_length=1, max_length=512)
    target_model: str = Field(min_length=1, max_length=128)
    source_revision: str = Field(min_length=1, max_length=128)
    deployed_max_output_tokens: int = Field(default=512, ge=1, le=512)
    reviewed_version: str = Field(min_length=1, max_length=128)
    reviewed_wheel: str = Field(pattern=r"^wheel/[a-zA-Z0-9_.-]+\.whl$")
    reviewed_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_binding(self) -> "OperatorConfig":
        """Require exact target/credential selection without authentication or traffic."""
        workspace = urlsplit(self.workspace)
        if (
            workspace.scheme != "https"
            or not workspace.hostname
            or workspace.username
            or workspace.password
            or workspace.path
            or workspace.query
            or workspace.fragment
            or workspace.port not in {None, 443}
        ):
            raise ValueError("Select the exact HTTPS workspace origin")
        if self.target_kind == "http":
            if not self.http_url or any(
                (
                    self.app_name,
                    self.profile,
                    self.oauth_config_file,
                    self.oauth_client_id,
                    self.runner_app,
                    self.workspace_id,
                )
            ):
                raise ValueError("HTTP requires one URL and no App credential fields")
            if self.app_auth != "profile":
                raise ValueError("HTTP cannot select App authentication")
            if urlsplit(self.http_url).scheme != "https":
                raise ValueError("Cloud runner HTTP targets require HTTPS")
            http_binding(self)
            hostname = (urlsplit(self.http_url).hostname or "").lower().rstrip(".")
            if hostname == "localhost" or (hostname or "").endswith(".localhost"):
                raise ValueError("The target must be separate and reachable from the App")
            try:
                address = ipaddress.ip_address(hostname or "")
            except ValueError:
                address = None
            if address is not None and (address.is_loopback or address.is_unspecified):
                raise ValueError("The target must be separate and reachable from the App")
        else:
            if self.http_url or self.bearer_token_env is not None:
                raise ValueError("App authentication does not accept HTTP credential fields")
            if self.app_auth == "app-runtime":
                native_app_binding(self)
            elif (
                self.runner_app
                or self.workspace_id
                or not all(
                    (self.app_name, self.profile, self.oauth_config_file, self.oauth_client_id)
                )
            ):
                raise ValueError("App requires an explicit portable profile and no HTTP URL")
        return self


def native_app_binding(config: OperatorConfig) -> "Agent":
    """Construct the selected native binding without reading credentials or sending traffic.

    Args:
        config: Private fixed runner/target identity metadata; not an HTTP request.

    Returns:
        Public direct SDK binding with the runner's expected principal client UUID.

    Raises:
        ValueError: Native mode is absent or profile/file fields conflict.

    Side Effects:
        None. No credential, profile, SDK, model or volume call is made.
    """
    from evalsurge import Agent

    if config.app_auth != "app-runtime" or config.profile or config.oauth_config_file:
        raise ValueError("Native App requires its own explicit identity without a profile file")
    return Agent.databricks_app(
        config.app_name,
        auth="app-runtime",
        workspace=config.workspace,
        workspace_id=config.workspace_id,
        runner_app=config.runner_app,
        client_id=config.oauth_client_id,
    )


def http_binding(config: OperatorConfig) -> "Agent":
    """Build an exact HTTP target using only an optional operator bearer reference.

    Args:
        config: Validated private HTTP configuration. A bearer field names an
            existing environment variable; it must never contain its value.

    Returns:
        An inert public SDK binding, outside RunCreate and safe execution receipts.

    Raises:
        ValueError: The configuration selects an App, lacks an HTTP URL, is not
            HTTPS, or fails the existing exact connection validation.

    Side Effects:
        None. No environment value, SDK auth, target or model is accessed. Normal
        workers later resolve the protected value at dispatch; the operator must
        provision it separately, without adding it to source/config/requests.
    """
    from evalsurge import Agent, Connection

    if config.target_kind != "http" or not config.http_url:
        raise ValueError("Select a reviewed HTTP target for this binding")
    if urlsplit(config.http_url).scheme != "https":
        raise ValueError("Bearer and cloud HTTP targets require HTTPS")
    return Agent.http(
        config.http_url,
        protocol="http-json",
        connection=Connection(
            url=config.http_url,
            auth="bearer" if config.bearer_token_env is not None else "none",
            token_env=config.bearer_token_env,
        ),
    )


def read_config(path: Path) -> OperatorConfig:
    """Read bounded nonsecret operator JSON; errors never disclose submitted values.

    Args:
        path: Selected local deployment configuration, not request input.

    Returns:
        Strict target/consent declarations; construction performs no network call.

    Raises:
        ValueError: File or configuration is invalid, with fixed safe guidance.

    Side Effects:
        Reads at most 64 KiB. Does not read OAuth profile contents or create files.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, encoding="utf-8") as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= 65_536:
                raise ValueError
            return OperatorConfig.model_validate_json(source.read(65_537))
    except Exception:  # noqa: BLE001 - raw validation errors can contain operator values
        raise ValueError("Review the fixed operator configuration; no run was admitted") from None


def validate_approval(config: OperatorConfig, *, now: datetime) -> None:
    """Check fresh bounded consent at each admission/target-start boundary.

    Args:
        config: Fixed operator-owned live consent and approval-expiry declarations.
        now: Timezone-aware current time; no wall-clock lookup happens in this helper.

    Raises:
        ValueError: Consent is missing or approval is expired, unbounded or malformed.

    Side Effects:
        None. This is an admission/start gate, not a hard deadline or revocation
        mechanism for already dispatched target, SDK discovery or storage calls.
    """
    if not (config.enabled and config.accept_paid_traffic and config.real_inference_attested):
        raise ValueError("Explicit real-inference consent is required")
    try:
        expires = datetime.fromisoformat(config.approval_expires_at.replace("Z", "+00:00"))
        if (
            now.tzinfo is None
            or expires.tzinfo is None
            or not now < expires <= now + timedelta(minutes=10)
        ):
            raise ValueError
    except Exception:  # noqa: BLE001 - no submitted expiry or operator values
        raise ValueError("Consent expired or reviewed approval did not match") from None


def validate_launch(config: OperatorConfig, deployment_root: Path, *, now: datetime) -> None:
    """Check fresh live consent and exact installed artifact before SDK access.

    Args:
        config: Operator-owned configuration with explicit consent attestations.
        deployment_root: Reviewed App source directory containing the selected wheel.
        now: Timezone-aware current UTC time used to validate the short approval.

    Raises:
        ValueError: Consent, expiry, wheel SHA256 or installed version does not match.

    Side Effects:
        Reads the wheel and distribution metadata only; never authenticates or invokes.
        The wheel digest does not establish every installed dependency's provenance.
    """
    validate_approval(config, now=now)
    try:
        wheel = deployment_root / config.reviewed_wheel
        if wheel.is_symlink() or not wheel.is_file():
            raise ValueError
        with wheel.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest != config.reviewed_sha256 or version("evalsurge") != config.reviewed_version:
            raise ValueError
    except Exception:  # noqa: BLE001 - no private artifact paths or metadata values
        raise ValueError("Consent expired or reviewed installed artifact did not match") from None


def request() -> RunCreate:
    """Construct one measured request plus the existing excluded probe, without traffic."""
    return RunCreate(
        name="databricks-app-runner-fixed-target-smoke",
        target=TargetReference(connection_id="agent"),
        cases=[Case(input={"query": "Reply briefly: can an opened item be refunded?"})],
        load=Load(concurrency=1, duration_seconds=5, max_requests=1, timeout_seconds=30),
    )


def export_root(volume: str) -> str:
    """Validate the fixed volume-resource root, never a caller-chosen file destination."""
    # UC volume valueFrom can supply its three-part securable name, not a mount.
    if not volume.startswith("/"):
        parts = volume.split(".")
        if len(parts) != 3 or any(not re.fullmatch(r"[a-zA-Z0-9_-]+", part) for part in parts):
            raise ValueError("Select an exact protected Unity Catalog volume resource")
        volume = "/Volumes/" + "/".join(parts)
    path = PurePosixPath(volume)
    if (
        str(path) != volume
        or len(path.parts) != 5
        or path.parts[:2] != ("/", "Volumes")
        or any(not re.fullmatch(r"[a-zA-Z0-9_.-]+", part) for part in path.parts[2:])
        or any(part in {".", ".."} for part in path.parts)
    ):
        raise ValueError("Select an exact protected Unity Catalog volume resource")
    return volume + "/evalsurge-app-runner"


def archive_artifacts(directory: Path) -> io.BytesIO:
    """Bound a protected post-load evidence archive without following symlinks.

    Args:
        directory: This execution's exclusive local artifact root, never profile storage.

    Returns:
        ZIP stream containing protected prompts/answers/metadata, not public telemetry.

    Raises:
        ValueError: A member is unsafe or the 512-file/64-MiB bound is exceeded.
        OSError: Owned artifact evidence cannot be read.

    Side Effects:
        Reads artifacts only after owner cleanup. No auth, model calls or file deletion.
    """
    stream = io.BytesIO()
    count = total = 0
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ValueError("Unsafe evidence archive member")
            if not path.is_file():
                continue
            count += 1
            total += path.stat().st_size
            if count > MAX_ARCHIVE_FILES or total > MAX_ARCHIVE_BYTES:
                raise ValueError("Evidence archive exceeds the fixed export bound")
            archive.write(path, arcname=str(path.relative_to(directory)))
    if stream.tell() > MAX_ARCHIVE_BYTES:
        raise ValueError("Evidence archive exceeds the fixed export bound")
    stream.seek(0)
    return stream


async def _http_run(config: OperatorConfig, artifact_dir: Path) -> dict[str, Any]:
    """Use the public direct SDK; context ownership drains Locust before returning."""
    return await _direct_run(http_binding(config), artifact_dir)


async def _direct_run(agent: "Agent", artifact_dir: Path) -> dict[str, Any]:
    """Run the fixed approved request through one public direct context and retrieve its report.

    Args:
        agent: Explicit operator-owned HTTP/native App binding, never caller-selected.
        artifact_dir: This execution's protected local evidence directory.

    Returns:
        Content-free lifecycle/retrieval observations after context cleanup.

    Side Effects:
        Runs at most one excluded inference probe and one measured target invocation,
        evaluation off. Failed runs retain reports; cleanup precedes cloud export.
        Native authentication/discovery failures are not model success evidence.
    """
    from evalsurge import EvalSurge, RunFailed

    async with EvalSurge.local_async(
        artifact_dir=artifact_dir,
        targets={"agent": agent},
    ) as client:
        handle = await client.start(request())
        try:
            report = await handle.wait(timeout=120)
        except RunFailed as error:
            report = error.report
        state = await handle.status()
        result = await handle.result()
        retrieved = await handle.report()
        agrees = (
            state.id == result.id == report.run.id == retrieved.run.id == handle.id
            and state.status == result.status
            and result == report.run == retrieved.run
            and report == retrieved
        )
        receipt = {
            "state": result.status,
            "run_id": str(handle.id),
            "retrieval_agrees": agrees,
            "passed": (
                result.status == "completed"
                and agrees
                and result.metrics is not None
                and result.metrics.measurement_complete
                and result.summary.performance == "complete"
                and result.metrics.successful_requests == 1
                and result.metrics.error_rate == 0
            ),
        }
    return {**receipt, "runner_context_closed": True}


async def _app_run(config: OperatorConfig, artifact_dir: Path) -> dict[str, Any]:
    """Select explicit native direct execution or the unchanged portable-profile launcher."""
    if config.app_auth == "app-runtime":
        return await _direct_run(native_app_binding(config), artifact_dir)
    from evalsurge.serverless import launch_runner_async, parse_options

    arguments = ["--live", "--accept-paid-traffic", "--real-inference-attested"]
    for name in (
        "workspace",
        "app_name",
        "profile",
        "oauth_config_file",
        "oauth_client_id",
        "target_model",
        "source_revision",
        "deployed_max_output_tokens",
    ):
        arguments.extend(["--" + name.replace("_", "-"), str(getattr(config, name))])
    arguments.extend(["--artifact-dir", str(artifact_dir)])
    receipt = await launch_runner_async(parse_options(arguments))
    # The reusable launcher's historical topology label is not App-runner evidence.
    receipt.pop("runner", None)
    receipt.pop("native_notebook_driver_auth_is_worker_evidence", None)
    return receipt


async def _store_call(function: Any, *args: Any, **kwargs: Any) -> Any:
    """Await one owned SDK operation even if its coroutine owner is cancelled.

    Args:
        function: An operator-selected SDK/file operation, never uploaded code.
        *args: Fixed operation arguments owned by this execution.
        **kwargs: Fixed operation options, including false overwrite for exports.

    Returns:
        Operation result after the owned thread finishes.

    Raises:
        asyncio.CancelledError: Cancellation, after the owned operation finishes.
        Exception: The SDK/file operation failed; the outer owner sanitizes it.

    Side Effects:
        Runs the call outside the event loop and measured load. Python cannot
        safely kill its thread; repeated cancellation must not detach it. The
        configured timeout is not a platform SIGKILL guarantee.
    """
    pending = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(pending)
    except asyncio.CancelledError:
        while not pending.done():
            try:
                await asyncio.shield(pending)
            except asyncio.CancelledError:
                continue
            except Exception:  # noqa: BLE001 - consume result without exposing SDK errors
                break
        if not pending.cancelled():
            with suppress(Exception):
                pending.result()
        raise


def _native_app_identity(workspace: str, values: Mapping[str, str]) -> str:
    """Require exact native workspace/client selectors before SDK construction.

    Args:
        workspace: Reviewed exact HTTPS workspace origin.
        values: Native App environment, never values accepted from HTTP callers.

    Returns:
        Native client identifier for in-memory SDK agreement checks only.

    Raises:
        ValueError: Native host/client/secret selectors are absent or mismatched.

    Side Effects:
        None. No Config/client construction, authentication or file access. No
        value is logged or included in public status or protected report receipts.
    """
    native_id = values.get("DATABRICKS_CLIENT_ID")
    native_host = values.get("DATABRICKS_HOST")
    if (
        not native_id
        or not values.get("DATABRICKS_CLIENT_SECRET")
        or not native_host
        or native_host.rstrip("/") != workspace
    ):
        raise ValueError("Native assigned App identity must match the selected workspace")
    return native_id


def _assigned_store(config: OperatorConfig) -> Any:
    """Construct the exact native App client only inside an owned off-loop call.

    Args:
        config: Reviewed workspace origin; not an HTTP caller's configuration.

    Returns:
        Native WorkspaceClient after assigned M2M identity agreement.

    Raises:
        ValueError: Runtime credentials or workspace/client identity do not match.
        Exception: Native SDK initialization/discovery failed; the owner sanitizes it.

    Side Effects:
        Config/WorkspaceClient initialization may perform OAuth/OIDC discovery.
        Config transport settings do not bound the installed SDK's independent
        OIDC discovery client's default 300-second retry/60-second timeout. This
        operation must be owned through cancellation; it is not a hard deadline.
        No environment value is logged, copied to a file or returned separately.
    """
    native_id = _native_app_identity(config.workspace, os.environ)
    if config.app_auth == "app-runtime":
        # Reuse exactly the production identity/resource checks before claim writes,
        # rather than allowing export authentication to bypass native admission.
        from benchmark_agents.target_resolver import _native_workspace_app

        workspace, _ = _native_workspace_app(
            native_app_binding(config).registration, config.app_name
        )
        return workspace
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config

    store = WorkspaceClient(
        config=Config(
            host=config.workspace,
            auth_type="oauth-m2m",
            http_timeout_seconds=5,
            retry_timeout_seconds=1,
        )
    )
    if (
        store.config.host.rstrip("/") != config.workspace
        or store.config.auth_type != "oauth-m2m"
        or store.config.client_id != native_id
    ):
        raise ValueError("Assigned App identity does not match the selected workspace")
    return store


async def _export_evidence(
    *,
    config: OperatorConfig,
    directory: Path | None,
    store: Any,
    root: str,
    receipt: dict[str, Any],
    status: dict[str, str | bool],
) -> None:
    """Export post-load evidence; publish journey success only after both uploads.

    Args:
        config: Operator approval identifier, already consumed before inference.
        directory: Exclusive local evidence root, or None after an early failure.
        store: Already-checked assigned-principal SDK client.
        root: Validated protected volume resource root.
        receipt: Captured benchmark outcome; a pass is not yet export success.
        status: Content-free owner projection, which remains nonpassing in flight.

    Raises:
        asyncio.CancelledError: Export was interrupted; owned operations finish
            first, and the projection remains nonpassing.

    Side Effects:
        Owns bounded archival reads and non-overwriting artifact/receipt writes
        after SDK cleanup. Exception/cancellation does not certify delivery or
        delete evidence. Benchmark outcome remains independently visible.
    """
    benchmark_passed = receipt.get("passed") is True
    status.update(
        benchmark_passed=benchmark_passed,
        passed=False,
        protected_export_ready=False,
        export_status="running",
    )
    try:
        artifact_exported = False
        if directory is not None:
            archive = await _store_call(archive_artifacts, directory)
            with zipfile.ZipFile(archive) as opened:
                has_members = bool(opened.namelist())
            archive.seek(0)
            if has_members:
                await _store_call(
                    store.files.upload,
                    f"{root}/{config.approval_id}.artifacts.zip",
                    archive,
                    overwrite=False,
                )
                artifact_exported = True
        exported_receipt = {
            **receipt,
            "runner": "databricks-app",
            "evaluation": "off",
            "maximum_agent_invocations": 2,
            "artifact_exported": artifact_exported,
            "benchmark_passed": benchmark_passed,
            "passed": benchmark_passed and artifact_exported,
        }
        await _store_call(
            store.files.upload,
            f"{root}/{config.approval_id}.receipt.json",
            io.BytesIO(json.dumps(exported_receipt, sort_keys=True).encode()),
            overwrite=False,
        )
        status.update(
            protected_export_ready=artifact_exported,
            passed=benchmark_passed and artifact_exported,
            export_status="complete" if artifact_exported else "no_artifact_evidence",
        )
    except asyncio.CancelledError:
        status.update(
            passed=False,
            protected_export_ready=False,
            state="export_interrupted",
            export_status="interrupted",
        )
        raise
    except Exception:  # noqa: BLE001 - protected export failure remains content-free
        status.update(
            protected_export_ready=False,
            passed=False,
            state="export_failed",
            export_status="failed",
        )


async def run_once(
    config: OperatorConfig, deployment_root: Path, status: dict[str, str | bool]
) -> None:
    """Consume one external claim, run once, and export protected evidence post-load.

    Args:
        config: Reviewed fixed operator selections, never HTTP request parameters.
        deployment_root: Source location of the exact reviewed wheel.
        status: Content-free in-memory lifecycle projection owned by this App.

    Side Effects:
        Enabled execution uses the assigned App principal to reserve/export files
        in one protected volume. Target execution uses existing direct SDK/Locust;
        at most two agent invocations, no judges/planner. SDK cleanup precedes export.
        Never removes claims, local evidence, credentials or external resources.

    Cancellation:
        Cancelling this task propagates to its owned SDK/launcher and awaits its
        cleanup. Forced platform kill can lose evidence and prevent export. An
        already consumed volume claim remains consumed; no automatic retry occurs.
    """
    receipt: dict[str, Any] = {"passed": False, "state": "blocked"}
    directory: Path | None = None
    store: Any = None
    root: str | None = None
    consumed = False
    try:
        validate_launch(config, deployment_root, now=datetime.now(UTC))
        root = export_root(os.environ.get("EVALSURGE_EXPORT_VOLUME", ""))
        store = await _store_call(_assigned_store, config)
        await _store_call(store.files.create_directory, root)
        claim = io.BytesIO(
            json.dumps(
                {"approval_id": config.approval_id, "version": config.reviewed_version},
                sort_keys=True,
            ).encode()
        )
        validate_approval(config, now=datetime.now(UTC))
        await _store_call(
            store.files.upload,
            f"{root}/{config.approval_id}.claim.json",
            claim,
            overwrite=False,
        )
        consumed = True
        status.update(state="running", approval_consumed_observed=True)
        directory = Path(tempfile.mkdtemp(prefix="evalsurge-private-app-runner-"))
        validate_approval(config, now=datetime.now(UTC))
        receipt = await (
            _app_run(config, directory)
            if config.target_kind == "databricks-app"
            else _http_run(config, directory)
        )
    except asyncio.CancelledError:
        receipt = {"passed": False, "state": "cancelled", "cleanup_observation": "interrupted"}
        status["state"] = "cancelled"
        raise
    except Exception:  # noqa: BLE001 - no raw provider, SDK, path or credential values
        receipt = {"passed": False, "state": "blocked", "blocker_code": "review_execution_gate"}
    finally:
        status.update(
            state=str(receipt["state"]),
            benchmark_passed=receipt.get("passed") is True,
            passed=False,
        )
        if consumed and store is not None and root is not None:
            await _export_evidence(
                config=config,
                directory=directory,
                store=store,
                root=root,
                receipt=receipt,
                status=status,
            )
