"""Packaged serverless load-generator -> deployed App authentication gate.

The notebook runs EvalSurge/Locust only; all agent/model execution stays inside
the selected deployed App. This module never imports customer agent frameworks,
starts an agent helper or exports notebook credentials. Current profile-only App
binding and native notebook OAuth worker availability are separate prerequisites.
Selecting the name of a laptop profile does not install that identity in a Job.

No live submission is implied by this file. A maintainer must review the current
wheel, deployed source/output limit and operator-provisioned OAuth M2M profile before
approving this initial <=1 preflight + <=1 measured App-invocation smoke test.
That bound is on invocations, not arbitrary agent model/tool turns or money.
"""

import argparse
import asyncio
import configparser
import json
import os
import re
import signal
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from benchmark_agents.v2_models import Result, RunCreate

_WORKER_CHECK = """
import json
import sys
from benchmark_agents.connections import Connection
from benchmark_agents.providers import workspace_client
from benchmark_agents.target_resolver import app_authentication
try:
    connection = Connection.model_validate_json(sys.argv[1])
    identity_matches = False
    if len(sys.argv) > 2:
        expected = json.loads(sys.argv[2])
        config = workspace_client(profile=connection.profile).config
        identity_matches = (
            config.host.rstrip('/') == expected['workspace']
            and config.auth_type == 'oauth-m2m'
            and config.client_id == expected['client_id']
        )
        if not identity_matches:
            raise ValueError
    headers = app_authentication(connection)()
    ready = bool(headers.get('Authorization'))
    print(json.dumps({'worker_oauth_ready': ready,
        'worker_identity_matches': identity_matches}))
except Exception:
    print(json.dumps({'worker_oauth_ready': False, 'worker_identity_matches': False}))
"""

_CHILD_OS_ENVIRONMENT = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TZ",
        "TMPDIR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "LD_LIBRARY_PATH",
    }
)
_PROFILE_FIELDS = frozenset({"host", "auth_type", "client_id", "client_secret"})


class PortableOAuthConfigurationError(ValueError):
    """A fixed value-free error for an operator-owned portable OAuth source."""


def validate_portable_profile(options: argparse.Namespace) -> None:
    """Validate an operator-provisioned M2M file without auth or network calls.

    Args:
        options: Explicit config-file, profile, workspace and expected client ID.

    Raises:
        PortableOAuthConfigurationError: The source is unsafe, unsupported or not
            bound to the selected workspace/identity. No source value is returned.

    Side Effects:
        Reads at most 64 KiB of an existing private local configuration file. Does
        not create, copy, edit or delete credentials. The operator owns rotation
        and must keep its private directory and ancestor path stable throughout
        the run. Same-user mutation between checks and SDK reads is a residual
        local-operator risk, not a sandbox guarantee. A named laptop OAuth cache
        and notebook-native token are not accepted as a substitute.
    """
    path = options.oauth_config_file
    if path is None or not options.oauth_client_id:
        raise PortableOAuthConfigurationError("Explicit portable OAuth configuration required")
    descriptor: int | None = None
    try:
        if not path.is_absolute() or path != Path(os.path.normpath(path)):
            raise ValueError
        for index, parent in enumerate(path.parents):
            ancestor = parent.lstat()
            if not stat.S_ISDIR(ancestor.st_mode) or ancestor.st_uid not in {0, os.geteuid()}:
                raise ValueError
            if index == 0:
                if ancestor.st_uid != os.geteuid() or ancestor.st_mode & 0o077:
                    raise ValueError
            elif ancestor.st_mode & 0o022 and not (
                ancestor.st_uid == 0 and ancestor.st_mode & stat.S_ISVTX
            ):
                raise ValueError
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o077
            or metadata.st_nlink != 1
            or not 0 < metadata.st_size <= 65_536
        ):
            raise ValueError
        with os.fdopen(descriptor, encoding="utf-8") as source:
            descriptor = None
            # Disable DEFAULT inheritance, including empty DEFAULT declarations;
            # every real named section must be the explicit selected profile.
            configuration = configparser.ConfigParser(interpolation=None, default_section="")
            configuration.read_string(source.read(65_537))
            after = os.fstat(source.fileno())
        selected_path = path.lstat()
        fields = ("st_dev", "st_ino", "st_uid", "st_mode", "st_nlink", "st_size", "st_mtime_ns")
        if any(
            getattr(item, field) != getattr(metadata, field)
            for item in (after, selected_path)
            for field in fields
        ):
            raise ValueError
        if configuration.defaults() or configuration.sections() != [options.profile]:
            raise ValueError
        selected = configuration[options.profile]
        if (
            set(selected) != _PROFILE_FIELDS
            or selected["host"].rstrip("/") != options.workspace
            or selected["auth_type"] != "oauth-m2m"
            or selected["client_id"] != options.oauth_client_id
            or not selected["client_secret"].strip()
        ):
            raise ValueError
    except Exception:  # noqa: BLE001 - never return config keys, secret values or paths
        raise PortableOAuthConfigurationError(
            "Portable OAuth configuration must be private, exact and operator provisioned"
        ) from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def isolated_runner_environment(
    options: argparse.Namespace, source_root: Path, values: dict[str, str]
) -> dict[str, str]:
    """Build a fresh process environment, never mutate notebook credentials.

    Args:
        options: Exact operator-selected profile-file selectors.
        source_root: Reviewed validation source directory, not customer agent code.
        values: Notebook environment used only for the fixed OS/certificate allowlist.

    Returns:
        Detached environment without notebook credential/routing inputs, proxy,
        netrc, arbitrary Python paths or model/provider settings. The unchanged
        target resolver must still admit the exact named profile in each process.

    Raises:
        PortableOAuthConfigurationError: A portable source was not explicitly selected.

    No access token or client secret is placed in the returned environment.
    ``HOME`` retains its existing OS meaning; no alternative profile is selected.
    """
    if options.oauth_config_file is None or not options.oauth_client_id:
        raise PortableOAuthConfigurationError("Explicit portable OAuth configuration required")
    return {
        **{name: values[name] for name in _CHILD_OS_ENVIRONMENT if name in values},
        "DATABRICKS_CONFIG_FILE": str(options.oauth_config_file),
        "DATABRICKS_CONFIG_PROFILE": options.profile,
        "PYTHONPATH": str(source_root),
        "PYTHONNOUSERSITE": "1",
        "PYTHONUNBUFFERED": "1",
    }


def parse_options(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Validate exact operator selections without auth, deployment or inference.

    Args:
        arguments: Explicit CLI arguments; omission reads process argv.

    Returns:
        Reviewed selections with fixed two-invocation and token-declaration bounds.

    Raises:
        SystemExit: Required selection, consent or fixed bound is invalid.

    The output-token bound is an attestation about deployed agent configuration,
    not a field sent to the App. The serving contract owns its model token limit.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--oauth-config-file", type=Path)
    parser.add_argument("--oauth-client-id")
    parser.add_argument("--target-model", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--deployed-max-output-tokens", type=int, default=512)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--check-authentication", action="store_true")
    parser.add_argument("--accept-paid-traffic", action="store_true")
    parser.add_argument("--real-inference-attested", action="store_true")
    options = parser.parse_args(arguments)
    try:
        parsed = urlsplit(options.workspace)
        valid = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.path in {"", "/"}
            and parsed.port in {None, 443}
        )
    except ValueError:
        valid = False
    if not valid:
        parser.error("--workspace must be the exact selected HTTPS workspace origin")
    options.workspace = options.workspace.rstrip("/")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,29}", options.app_name):
        parser.error("--app-name must select one already deployed authorized App")
    for name in ("profile", "target_model", "source_revision"):
        value = getattr(options, name)
        if not value.strip() or len(value) > 512:
            parser.error(f"--{name.replace('_', '-')} must be an explicit bounded selection")
    if bool(options.oauth_config_file) != bool(options.oauth_client_id):
        parser.error("--oauth-config-file and --oauth-client-id must be selected together")
    if options.oauth_config_file is not None and (
        not options.oauth_config_file.is_absolute()
        or not options.oauth_client_id.strip()
        or len(options.oauth_client_id) > 512
        or any(character in options.oauth_client_id for character in "\r\n\x00")
    ):
        parser.error("Portable OAuth requires an absolute file and explicit bounded client ID")
    if options.check_authentication and (options.live or options.oauth_config_file is None):
        parser.error("--check-authentication requires portable OAuth selectors and excludes --live")
    if not 1 <= options.deployed_max_output_tokens <= 512:
        parser.error("The reviewed deployed model output limit must be 1..512 tokens")
    if options.live and not (
        options.accept_paid_traffic and options.real_inference_attested and options.artifact_dir
    ):
        parser.error(
            "--live requires --accept-paid-traffic, --real-inference-attested "
            "and dedicated --artifact-dir; maintainer auth/traffic review remains required"
        )
    return options


def budget_record(options: argparse.Namespace) -> dict[str, Any]:
    """Describe the intended topology/bounds; declarations are not live evidence."""
    return {
        "runner": "serverless-notebook",
        "target_hosting": "deployed-databricks-app",
        "app_name": options.app_name,
        "workspace": options.workspace,
        "declared_model": options.target_model,
        "declared_source_revision": options.source_revision,
        "declared_deployed_max_output_tokens": options.deployed_max_output_tokens,
        "concurrency": 1,
        "max_requests": 0 if options.check_authentication else 1,
        "maximum_app_invocations": 0 if options.check_authentication else 2,
        "evaluation": "off",
        "native_notebook_driver_auth_is_worker_evidence": False,
        "api_execution_tested": False,
        "app_metadata_checked": False,
        "client_invocation_observed": False,
        "successful_completion_observed": False,
        "deployed_app_tested": False,
        "paid_traffic_authorized_by_this_record": False,
        "portable_oauth_source_selected": options.oauth_config_file is not None,
        "portable_oauth_source_verified": False,
        "authentication_only": options.check_authentication,
    }


def request() -> "RunCreate":
    """Build one measured attempt plus the existing excluded target preflight.

    This smoke checks the runner/target boundary, not capacity. No scorer planner,
    judge or target-model fallback is configured; references/answers are retained
    by the normal protected report store, never exported in the safe receipt.
    """
    from evalsurge import Case, Load, RunCreate, TargetReference

    return RunCreate(
        name="serverless-runner-databricks-app-target-smoke",
        target=TargetReference(connection_id="agent"),
        cases=[Case(input={"query": "Reply briefly: can an opened item be refunded?"})],
        load=Load(concurrency=1, duration_seconds=5, max_requests=1, timeout_seconds=30),
    )


def readiness(options: argparse.Namespace) -> dict[str, Any]:
    """Check the existing profile-bound driver and independent worker without inference.

    Args:
        options: Exact operator App/profile selectors previously validated.

    Returns:
        Content-free booleans, fixed blocker codes and actionable guidance. No
        token, SDK message, profile content, raw child output or headers are returned.

    Side Effects:
        When the profile/ambient-override guard permits admission, may make bounded
        OAuth and App metadata reads in driver and worker. It never sends an agent
        request or modifies the environment. Child process has a 30-second limit.
        OAuth providers can outlive SDK nominal driver metadata timeout budgets.

    Native notebook runtime-OAuth is not copied to the child. The child must own a
    supported refreshable OAuth source itself, using the unchanged public binding.
    No missing profile is generated or read from a laptop as a workaround.

    The diagnostic harness uses the resolver's unchanged override and origin guards
    directly so it can verify the exact workspace before App discovery and identify
    the failing stage. SDK construction may itself initialize host/auth metadata.
    """
    from benchmark_agents.connections import Connection
    from benchmark_agents.providers import workspace_client
    from benchmark_agents.target_resolver import (
        TargetResolutionError,
        _app_origin,
        _reject_profile_overrides,
    )
    from evalsurge import Agent

    agent = Agent.databricks_app(options.app_name, profile=options.profile)
    result: dict[str, Any] = {
        "driver_profile_ready": False,
        "driver_identity_matches": False,
        "worker_oauth_ready": False,
        "worker_identity_matches": False,
        "portable_oauth_source_verified": False,
        "inference_invocations": 0,
        "blocker_codes": [],
        "blockers": [],
    }

    def blocked(code: str, guidance: str) -> dict[str, Any]:
        """Attach one fixed, content-free admission failure to the safe receipt."""
        result["blocker_codes"].append(code)
        result["blockers"].append(guidance)
        return result

    if options.oauth_config_file is not None:
        try:
            validate_portable_profile(options)
        except PortableOAuthConfigurationError:
            return blocked(
                "portable_oauth_configuration_invalid",
                "Select an existing private operator-provisioned OAuth M2M profile file "
                "bound to the approved workspace and expected service-principal client ID. "
                "No credential source is created, copied or substituted.",
            )
        if os.environ.get("DATABRICKS_CONFIG_FILE") != str(options.oauth_config_file):
            return blocked(
                "portable_oauth_selector_mismatch",
                "Owner process does not use the exact selected portable configuration file. "
                "Launch the reviewed isolated owner; no selector is overridden in place.",
            )
    try:
        _reject_profile_overrides()
    except TargetResolutionError:
        return blocked(
            "profile_conflict",
            "Current App binding rejects ambient notebook destination/identity overrides "
            "or conflicting configuration selectors. Use an isolated, explicitly selected "
            "portable OAuth profile. No token copying or override-guard bypass is supported.",
        )
    try:
        workspace = workspace_client(profile=options.profile)
        host = workspace.config.host
    except Exception:  # noqa: BLE001 - provider messages may contain private configuration
        return blocked(
            "driver_authentication_failed",
            "Selected-profile SDK construction or authentication failed. Verify that this "
            "runner has the explicitly selected supported OAuth configuration; no alternate "
            "profile, host or authentication fallback is permitted.",
        )
    if not isinstance(host, str) or host.rstrip("/") != options.workspace:
        return blocked(
            "workspace_mismatch",
            "Selected profile does not establish the explicitly approved workspace. "
            "No alternate profile, host or authentication fallback is permitted.",
        )
    if options.oauth_config_file is not None and (
        workspace.config.auth_type != "oauth-m2m"
        or workspace.config.client_id != options.oauth_client_id
    ):
        return blocked(
            "oauth_identity_mismatch",
            "SDK configuration does not establish the explicitly selected OAuth M2M "
            "identity. No native notebook credential or alternate identity is substituted.",
        )
    result["driver_identity_matches"] = options.oauth_config_file is not None
    try:
        token = workspace.config.oauth_token()
        if not token.access_token or token.token_type not in {None, "Bearer", "bearer"}:
            raise ValueError
    except Exception:  # noqa: BLE001 - provider messages may contain private configuration
        return blocked(
            "driver_oauth_unavailable",
            "Selected driver profile has no verified refreshable App OAuth token. "
            "PAT/basic credentials and driver-token copying are not supported; configure "
            "the reviewed OAuth source before App discovery or load.",
        )
    del token
    try:
        app = workspace.apps.get(name=options.app_name)
    except Exception:  # noqa: BLE001 - provider messages may contain resource or token values
        return blocked(
            "app_discovery_failed",
            "App discovery failed in the explicitly approved workspace. Verify the selected "
            "App exists and the selected identity can read its metadata; no other workspace "
            "or App is substituted.",
        )
    try:
        origin = _app_origin(app.url)
    except Exception:  # noqa: BLE001 - SDK-returned deployment values stay private
        return blocked(
            "app_deployment_unavailable",
            "Selected App has no valid deployed HTTPS origin. Verify its deployment is "
            "ready before retrying; no guessed URL, redirect or local substitute is used.",
        )
    selected = agent.registration.protocols[0]
    path = "/api/invocations" if selected == "databricks-agent-runtime" else "/responses"
    connection = Connection(
        url=origin + path,
        auth="databricks-app",
        profile=options.profile,
        app_name=options.app_name,
    )
    result["driver_profile_ready"] = True
    try:
        arguments = [sys.executable, "-c", _WORKER_CHECK, connection.model_dump_json()]
        if options.oauth_config_file is not None:
            arguments.append(
                json.dumps({"workspace": options.workspace, "client_id": options.oauth_client_id})
            )
        child = subprocess.Popen(
            arguments,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            # Keep the diagnostic inside the isolated owner group. An owner
            # timeout/notebook cancellation must not leave a detached auth child.
            start_new_session=False,
            bufsize=0,
        )
        output, failure, closed = _capture_owner_output(child, timeout=30, own_group=False)
        checked = (
            json.loads(output.splitlines()[-1])
            if child.returncode == 0 and failure is None and closed
            else {}
        )
        result["worker_oauth_ready"] = (
            isinstance(checked, dict) and checked.get("worker_oauth_ready") is True
        )
        result["worker_identity_matches"] = (
            isinstance(checked, dict) and checked.get("worker_identity_matches") is True
        )
    except (subprocess.TimeoutExpired, ValueError, IndexError, OSError):
        result["worker_oauth_ready"] = False
    if not result["worker_oauth_ready"]:
        return blocked(
            "worker_oauth_unavailable",
            "Independent Locust worker has no verified refreshable App OAuth source. "
            "Driver-native runtime-OAuth depends on notebook context unavailable to that "
            "subprocess. Stop before load; request a reviewed operator-auth design.",
        )
    if options.oauth_config_file is not None and not result["worker_identity_matches"]:
        return blocked(
            "worker_identity_mismatch",
            "Independent worker has not established the exact approved OAuth M2M identity "
            "and workspace. No alternate credential source is substituted.",
        )
    result["portable_oauth_source_verified"] = options.oauth_config_file is not None
    return result


def _invocation_evidence(result: "Result") -> dict[str, bool]:
    """Describe observed client dispatch/completion, not terminal-run existence.

    Args:
        result: Already retrieved typed metadata; probe timings are excluded from
            measured metrics. No request body, answer or trace is read here.

    Returns:
        Safe booleans. Probe latency/HTTP status, a passed probe, a measured HTTP
        in-flight peak or measured successful completions establish recorded
        client dispatch. Starts/attempt counts alone do not: authentication,
        planning and worker-launch failures can occur before dispatch. Successful
        completion is independent from run completion, report parity and quality.
        The compatibility ``deployed_app_tested`` flag matches client dispatch.

    Side Effects:
        None. A dispatched timeout/connection failure does not prove that the App
        received it, executed a model/tool, or returned a completed answer. Missing
        historical dispatch evidence remains false rather than inferred from a
        terminal lifecycle. This is not independent real-model attestation.
    """
    probe = result.preflight
    metrics = result.metrics
    successful = probe.status == "passed" or (
        metrics is not None and metrics.successful_requests > 0
    )
    observed = (
        successful
        or probe.latency_ms is not None
        or probe.http_status is not None
        or (
            metrics is not None
            and metrics.observed_peak_in_flight is not None
            and metrics.observed_peak_in_flight > 0
        )
    )
    return {
        "client_invocation_observed": observed,
        "successful_completion_observed": successful,
        "deployed_app_tested": observed,
    }


async def execute(options: argparse.Namespace) -> dict[str, Any]:
    """After consent/auth gates, run the generator-only two-invocation smoke test.

    Args:
        options: Previously validated exact selections and explicit live consent.

    Returns:
        Safe receipt including independent retrieval consistency, never raw answers.
        An auth failure returns ``blocked`` with zero inference, not a passed Job.

    Raises:
        PermissionError: Consent/attestation is absent, before auth/network calls.
        ValueError: Artifacts path is not empty, before inference.

    Side Effects:
        Uses existing coordinator/Locust subprocess and protected local storage.
        Up to two App invocations; the deployed source must enforce declared model
        limits. Context exit cleans runner lifecycle, not App/Lakebase resources.
    """
    if not (
        options.live
        and options.accept_paid_traffic
        and options.real_inference_attested
        and options.artifact_dir is not None
    ):
        raise PermissionError("Explicit reviewed live consent is required before auth or traffic")
    path = options.artifact_dir
    if path.exists() and any(path.iterdir()):
        raise ValueError("Select an empty dedicated artifacts directory")
    receipt = {**budget_record(options), "passed": False, "state": "not_started"}
    checked = await asyncio.to_thread(readiness, options)
    receipt["authentication"] = checked
    receipt["app_metadata_checked"] = checked.get("driver_profile_ready") is True
    receipt["portable_oauth_source_verified"] = checked["portable_oauth_source_verified"]
    if checked["blockers"]:
        return {**receipt, "state": "blocked", "inference_invocations": 0}

    from evalsurge import Agent, EvalSurge, RunFailed

    from ._retrieval import retrieval_evidence

    async with EvalSurge.local_async(
        artifact_dir=path,
        targets={"agent": Agent.databricks_app(options.app_name, profile=options.profile)},
    ) as client:
        handle = await client.start(request())
        try:
            report = await handle.wait(timeout=120)
        except RunFailed as error:
            report = error.report
        state = await handle.status()
        result = await handle.result()
        fetched = await handle.report()
        evidence = retrieval_evidence(handle.id, state, result, report, fetched, remote=False)
        receipt["retrieval"] = evidence
        receipt["run_id"] = str(handle.id)
        receipt["state"] = report.run.status
        receipt.update(_invocation_evidence(result))
        receipt["passed"] = (
            report.run.status == "completed"
            and evidence["retrieval_agrees"]
            and result.metrics is not None
            and result.metrics.measurement_complete
            and result.summary.performance == "complete"
            and result.metrics.successful_requests == 1
            and result.metrics.error_rate == 0
        )
    receipt["runner_context_closed"] = True
    return receipt


def _reaped_owner_group_absent(child: subprocess.Popen[bytes]) -> bool:
    """Observe group absence after reaping; permission errors remain unknown.

    Args:
        child: Known launcher child created with ``start_new_session=True``.

    Returns:
        True only when the owner was reaped and a read-only process-group probe
        raises ``ProcessLookupError``. A surviving group or any other OS error
        remains false; neither an exited owner nor ``PermissionError`` proves
        that descendants are absent.

    Side Effects:
        One signal-zero visibility probe, with no process termination or wait.
    """
    if child.returncode is None:
        return False
    try:
        os.killpg(child.pid, 0)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    return False


def _stop_owner_group(child: subprocess.Popen[bytes]) -> bool:
    """Terminate and reap only this launcher's newly isolated process group.

    Args:
        child: A process created below with ``start_new_session=True``.

    Returns:
        Whether the owner is reaped and its process group is no longer present.

    Side Effects:
        Sends TERM then KILL after a five-second cooperative grace period. This
        cannot undo model/tool calls already dispatched, nor prove remote cleanup.
        It never signals the notebook's process group or any configured resource.
    """
    if child.pid == os.getpgrp():
        return False
    try:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            child.wait(timeout=5)
            return True
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            child.poll()
            try:
                os.killpg(child.pid, 0)
            except ProcessLookupError:
                child.wait(timeout=5)
                return True
            time.sleep(0.1)
        with suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=5)
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            return True
        return False
    except (OSError, subprocess.TimeoutExpired):
        # Unverifiable group state is not absence. Reap only the known child;
        # never send another terminating group signal with unverified ownership.
        # macOS can transiently report EPERM during termination before reaping;
        # a subsequent read-only ESRCH observation is still required for success.
        return _stop_diagnostic(child) and _reaped_owner_group_absent(child)


def _stop_diagnostic(child: subprocess.Popen[bytes]) -> bool:
    """Reap the auth-only child without signalling its notebook/owner process group.

    The diagnostic inherits its owner's group so abrupt owner cancellation can
    also reach it. During normal diagnostic timeout/overflow only this process is
    terminated. Portable M2M has no CLI/provider subprocess fallback; any later
    owned descendants are still contained by outer owner-group cleanup. Returns
    false if a child cannot be reaped, never an optimistic cleanup claim.
    """
    try:
        if child.poll() is None:
            with suppress(ProcessLookupError):
                child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                with suppress(ProcessLookupError):
                    child.kill()
                child.wait(timeout=5)
        return child.returncode is not None
    except (OSError, subprocess.TimeoutExpired):
        return False


def _capture_owner_output(
    child: subprocess.Popen[bytes],
    *,
    timeout: float = 210,
    cancellation: threading.Event | None = None,
    own_group: bool = True,
) -> tuple[bytes, str | None, bool]:
    """Receive at most 64 KiB and reap the owned group or auth-only child on failure.

    Args:
        child: Owner or auth-only diagnostic with stdout pipe/discarded stderr.
        timeout: Overall owner deadline in seconds, not a target latency clock.
        cancellation: Notebook-await cancellation signal owned by the async launcher.
        own_group: Whether this child owns its newly isolated process group. The
            auth-only diagnostic instead inherits that group and is reaped alone.

    Returns:
        Bounded private bytes, optional fixed error code, and group-cleanup result.
        No temporary output spool is written. A pipe limits unread buffering;
        Exceeding the byte cap terminates the owner group, or only an auth
        diagnostic that inherits that group. Outer launcher cleanup still owns
        the full group; no output is dropped and pretended to be success.

    Raises:
        BaseException: Notebook interrupt, after owned-group cleanup is attempted.

    Side Effects:
        One daemon native reader thread; its lifetime and retained bytes are
        bounded. Normal owner exit is not enough: remaining descendants trigger
        cleanup and a failed receipt. Remote model/tool calls cannot be rolled back.
    """
    captured = bytearray()
    exceeded = threading.Event()
    read_failed = threading.Event()
    stream = child.stdout
    stop = _stop_owner_group if own_group else _stop_diagnostic
    if stream is None:
        return b"", "runner_receipt_unavailable", stop(child)

    def read() -> None:
        """Drain a bounded owned pipe, never export its raw bytes or errors."""
        try:
            while chunk := stream.read(4096):
                if len(captured) + len(chunk) > 65_536:
                    exceeded.set()
                    return
                captured.extend(chunk)
        except OSError:
            read_failed.set()
        finally:
            stream.close()

    reader = threading.Thread(target=read, name="evalsurge-owner-receipt", daemon=True)
    reader.start()
    failure: str | None = None
    cleaned = False
    deadline = time.monotonic() + timeout
    try:
        while child.poll() is None:
            if cancellation is not None and cancellation.is_set():
                failure = "runner_cancelled"
                break
            if exceeded.is_set() or read_failed.is_set():
                failure = (
                    "runner_output_limit" if exceeded.is_set() else "runner_receipt_unavailable"
                )
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure = "runner_deadline"
                break
            with suppress(subprocess.TimeoutExpired):
                child.wait(timeout=min(remaining, 0.2))
        if failure:
            cleaned = stop(child)
        elif not own_group:
            cleaned = child.returncode is not None
        else:
            # Group membership is still checked after the owner has been reaped.
            try:
                os.killpg(child.pid, 0)
            except ProcessLookupError:
                cleaned = True
            except OSError:
                cleaned = _stop_diagnostic(child) and _reaped_owner_group_absent(child)
                if not cleaned:
                    failure = "runner_process_group_unverified"
            else:
                cleaned = _stop_owner_group(child)
                failure = "owner_descendant_cleanup_required"
        reader.join(timeout=5)
        if reader.is_alive():
            failure = "runner_output_cleanup_unverified"
            cleaned = False
        elif exceeded.is_set():
            failure = "runner_output_limit"
        elif read_failed.is_set():
            failure = "runner_receipt_unavailable"
    except BaseException:
        with suppress(Exception):
            stop(child)
        with suppress(Exception):
            reader.join(timeout=5)
        raise
    return bytes(captured), failure, cleaned


def _portable_auth_verified(receipt: dict[str, Any]) -> bool:
    """Require independent owner/worker OAuth identity evidence, not a valid file."""
    authentication = receipt.get("authentication")
    return isinstance(authentication, dict) and all(
        authentication.get(name) is True
        for name in (
            "driver_profile_ready",
            "driver_identity_matches",
            "worker_oauth_ready",
            "worker_identity_matches",
            "portable_oauth_source_verified",
        )
    )


def launch_runner(
    options: argparse.Namespace,
    source_root: Path | None = None,
    *,
    cancellation: threading.Event | None = None,
) -> dict[str, Any]:
    """Launch the existing direct runner without inheriting notebook auth context.

    Args:
        options: Validated selections/consent plus the operator's portable M2M file.
        source_root: Optional reviewed package root for source-checkout validation.
            None uses this installed package's directory; no checkout or customer
            agent source is needed by a wheel-installed notebook.
        cancellation: Optional async-owner signal; never obtained from public input.

    Returns:
        Aggregate safe receipt. Dry-run returns bounds with no file/auth/network
        access. Configuration failure blocks before auth/model calls. A runtime
        timeout/error cannot claim zero calls or successful lifecycle cleanup.

    Side Effects:
        Live consent permits one newly isolated owner process and normal Locust
        workers. Stdout has a 64 KiB retained-byte cap; overflowing terminates the
        owned group. No stdout spool is written and raw output/stderr is never
        exported. Owner deadline is 210 seconds. Interrupt cleanup reraises the
        interrupt and cannot produce a successful notebook receipt.
        Existing credential files, Apps and historical artifacts are untouched.

    Raises:
        ValueError: Reviewed source root is missing or not a directory.
        PermissionError: Required real-inference attestation/consent is missing.

    ``--check-authentication`` is a separately selected zero-inference diagnostic;
    it may exchange OAuth and read App metadata, never start a benchmark. Selecting
    this mode still requires explicit resource/metadata-access approval.
    """
    if not (options.live or options.check_authentication):
        return budget_record(options)
    if cancellation is not None and cancellation.is_set():
        return {
            **budget_record(options),
            "state": "blocked",
            "passed": False,
            "inference_invocations": 0,
            "blocker_codes": ["runner_cancelled_before_start"],
        }
    source_root = Path(__file__).resolve().parent.parent if source_root is None else source_root
    if not source_root.is_absolute() or not source_root.is_dir():
        raise ValueError("Select the exact reviewed validation source directory")
    if options.live and not (
        options.accept_paid_traffic and options.real_inference_attested and options.artifact_dir
    ):
        raise PermissionError("Explicit reviewed live consent is required before auth or traffic")
    try:
        validate_portable_profile(options)
    except PortableOAuthConfigurationError:
        return {
            **budget_record(options),
            "state": "blocked",
            "passed": False,
            "inference_invocations": 0,
            "blocker_codes": ["portable_oauth_configuration_invalid"],
        }
    arguments = [sys.executable, "-m", "evalsurge.serverless"]
    for name in (
        "workspace",
        "app_name",
        "profile",
        "oauth_config_file",
        "oauth_client_id",
        "target_model",
        "source_revision",
        "deployed_max_output_tokens",
        "artifact_dir",
    ):
        value = getattr(options, name)
        if value is not None:
            arguments.extend(["--" + name.replace("_", "-"), str(value)])
    if options.check_authentication:
        arguments.append("--check-authentication")
    else:
        arguments.extend(["--live", "--accept-paid-traffic", "--real-inference-attested"])
    selected_environment = isolated_runner_environment(options, source_root, dict(os.environ))
    child = subprocess.Popen(  # noqa: S603 - fixed module and reviewed bounded selectors
        arguments,
        cwd=source_root,
        env=selected_environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        bufsize=0,
    )
    output, failure, closed = _capture_owner_output(child, cancellation=cancellation)
    try:
        receipt = json.loads(output.splitlines()[-1])
        fields = set(budget_record(options)) | {
            "authentication",
            "retrieval",
            "run_id",
            "state",
            "passed",
            "runner_context_closed",
            "inference_invocations",
            "blocker_codes",
        }
        if (
            not isinstance(receipt, dict)
            or set(receipt) - fields
            or child.returncode != 0
            or failure
            or receipt.get("runner") != "serverless-notebook"
            or receipt.get("target_hosting") != "deployed-databricks-app"
            or not isinstance(receipt.get("passed"), bool)
        ):
            raise ValueError
    except (ValueError, IndexError):
        receipt = {
            **budget_record(options),
            "state": "blocked",
            "passed": False,
            "inference_invocations": "unknown",
            "blocker_codes": [failure or "runner_receipt_unavailable"],
        }
    receipt["owner_process_group_closed"] = closed
    receipt["portable_oauth_source_verified"] = _portable_auth_verified(receipt)
    if receipt["passed"] and not (
        closed
        and receipt["portable_oauth_source_verified"]
        and receipt.get("runner_context_closed") is True
    ):
        receipt["passed"] = False
        receipt["state"] = "blocked"
        receipt.setdefault("blocker_codes", []).append("runner_evidence_incomplete")
    return receipt


async def launch_runner_async(
    options: argparse.Namespace, source_root: Path | None = None
) -> dict[str, Any]:
    """Keep notebook await cancellation coupled to the owned native runner.

    Args:
        options: Explicit bounded selections, portable source and selected consent mode.
        source_root: Optional reviewed package root; None uses the installed
            wheel without requiring a checkout or importing customer agent code.

    Returns:
        The launcher's safe receipt after native thread/process-group cleanup.

    Raises:
        BaseException: Notebook await cancellation/interrupt after cleanup is
            requested and the owned launcher thread finishes. Cancelling an
            ``asyncio.to_thread`` await alone cannot stop its native thread.

    Side Effects:
        Owns one shielded launcher task and a private cancellation event. Repeated
        await cancellation cannot detach that task or claim benchmark success.
        A dispatched remote call still cannot be rolled back by local termination.
    """
    cancellation = threading.Event()
    owned = asyncio.create_task(
        asyncio.to_thread(launch_runner, options, source_root, cancellation=cancellation)
    )
    try:
        return await asyncio.shield(owned)
    except BaseException:
        cancellation.set()
        while not owned.done():
            try:
                await asyncio.shield(owned)
            except asyncio.CancelledError:
                cancellation.set()
            except Exception:  # noqa: BLE001 - preserve the original notebook interrupt
                break
        # Retrieve a completed failure to avoid unhandled background-task logs;
        # its private exception is not substituted for the original interruption.
        if owned.done() and not owned.cancelled():
            with suppress(Exception):
                owned.result()
        raise


def main(arguments: Sequence[str] | None = None) -> None:
    """Emit only a safe owner receipt; never export an authentication traceback."""
    options = parse_options(arguments)
    try:
        if options.check_authentication:
            checked = readiness(options)
            receipt = {
                **budget_record(options),
                "passed": False,
                "state": "blocked" if checked["blockers"] else "authentication_ready",
                "inference_invocations": 0,
                "authentication": checked,
                "app_metadata_checked": checked.get("driver_profile_ready") is True,
                "portable_oauth_source_verified": checked["portable_oauth_source_verified"],
            }
        else:
            receipt = asyncio.run(execute(options)) if options.live else budget_record(options)
    except Exception:  # noqa: BLE001 - unknown call count after a failed owned run
        receipt = {
            **budget_record(options),
            "passed": False,
            "state": "blocked",
            "inference_invocations": "unknown",
            "blocker_codes": ["owner_execution_failed"],
        }
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
