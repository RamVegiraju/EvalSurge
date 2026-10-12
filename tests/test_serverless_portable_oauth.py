"""Pure configuration and native process checks, never agent/model inference.

Synthetic credential text exists only in test-owned private files; it is never
sent to OAuth or provider transports. Native Python children only emit bounded
diagnostic bytes or wait for process-lifecycle checks. These tests establish no
live notebook identity, App readiness, deployment or benchmark coverage.
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

from scripts.validation import serverless_runner_app_target as harness

ROOT = Path(__file__).resolve().parents[1]
HOST = "https://explicit-workspace.cloud.databricks.com"
PROFILE = "explicit-runner-profile"
CLIENT_ID = "9a92d178-486b-4a63-a010-29a81a95040d"
PRIVATE_MARKER = "synthetic-config-secret-never-transmitted"


def _arguments() -> list[str]:
    """Construct lexical selections only; never resolve a configured profile."""
    return [
        "--workspace",
        HOST,
        "--app-name",
        "explicit-app",
        "--profile",
        PROFILE,
        "--target-model",
        "declared-real-model",
        "--source-revision",
        "declared-reviewed-source",
    ]


def _profile(tmp_path: Path, *, content: str | None = None) -> Path:
    """Write synthetic private configuration, not a usable live credential."""
    path = tmp_path / "private-oauth-profile"
    path.write_text(
        content
        or f"[{PROFILE}]\nhost={HOST}\nauth_type=oauth-m2m\n"
        f"client_id={CLIENT_ID}\nclient_secret={PRIVATE_MARKER}\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def _options(path: Path, *extra: str) -> Any:
    """Parse the exact synthetic source path, not its authentication contents."""
    return harness.parse_options(
        [*_arguments(), "--oauth-config-file", str(path), "--oauth-client-id", CLIENT_ID, *extra]
    )


def test_private_m2m_configuration_is_lexically_bound_without_network(tmp_path: Path) -> None:
    path = _profile(tmp_path)
    before = path.read_bytes()
    options = _options(path)
    assert harness.validate_portable_profile(options) is None
    assert path.read_bytes() == before
    record = harness.budget_record(options)
    assert record["portable_oauth_source_selected"] is True
    assert record["portable_oauth_source_verified"] is False
    assert str(path) not in json.dumps(record)
    assert CLIENT_ID not in json.dumps(record)
    assert PRIVATE_MARKER not in json.dumps(record)


@pytest.mark.parametrize(
    "replacement",
    [
        ("auth_type=oauth-m2m", "auth_type=runtime-oauth"),
        ("auth_type=oauth-m2m", "auth_type=databricks-cli"),
        ("auth_type=oauth-m2m", "auth_type=pat"),
        (f"host={HOST}", "host=https://unapproved-workspace.cloud.databricks.com"),
        (f"client_id={CLIENT_ID}", "client_id=unselected-principal"),
        (f"client_secret={PRIVATE_MARKER}", "client_secret= "),
        (f"[{PROFILE}]", "[unselected-profile]"),
        (f"[{PROFILE}]", f"[DEFAULT]\ntoken={PRIVATE_MARKER}\n[{PROFILE}]"),
        (f"[{PROFILE}]", f"[DEFAULT]\n[{PROFILE}]"),
        ("auth_type=oauth-m2m", f"auth_type=oauth-m2m\ntoken={PRIVATE_MARKER}"),
        ("auth_type=oauth-m2m", "auth_type=oauth-m2m\ntoken_audience=unreviewed"),
        ("auth_type=oauth-m2m", "auth_type=oauth-m2m\nunknown_field=private-value"),
        (f"[{PROFILE}]", "invalid-configuration-with-private-value"),
    ],
)
def test_unsupported_profile_sources_never_export_values(
    tmp_path: Path, replacement: tuple[str, str]
) -> None:
    path = _profile(tmp_path)
    path.write_text(path.read_text().replace(*replacement), encoding="utf-8")
    with pytest.raises(harness.PortableOAuthConfigurationError) as error:
        harness.validate_portable_profile(_options(path))
    assert PRIVATE_MARKER not in str(error.value)
    assert "unselected" not in str(error.value)
    assert str(path) not in str(error.value)


@pytest.mark.parametrize("mode", [0o604, 0o640, 0o644, 0o660])
def test_shared_credential_file_modes_reject_before_auth(tmp_path: Path, mode: int) -> None:
    path = _profile(tmp_path)
    path.chmod(mode)
    with pytest.raises(harness.PortableOAuthConfigurationError):
        harness.validate_portable_profile(_options(path))


def test_multiple_profiles_and_oversized_sources_are_rejected(tmp_path: Path) -> None:
    path = _profile(tmp_path)
    path.write_text(path.read_text() + "\n[another-profile]\nhost=other\n", encoding="utf-8")
    with pytest.raises(harness.PortableOAuthConfigurationError):
        harness.validate_portable_profile(_options(path))
    path.write_text("private-value" * 10_000, encoding="utf-8")
    with pytest.raises(harness.PortableOAuthConfigurationError):
        harness.validate_portable_profile(_options(path))


def test_links_and_nonregular_sources_are_rejected_without_blocking(tmp_path: Path) -> None:
    target = _profile(tmp_path)
    symlink = tmp_path / "linked-profile"
    symlink.symlink_to(target)
    with pytest.raises(harness.PortableOAuthConfigurationError):
        harness.validate_portable_profile(_options(symlink))
    hardlink = tmp_path / "hardlinked-profile"
    os.link(target, hardlink)
    with pytest.raises(harness.PortableOAuthConfigurationError):
        harness.validate_portable_profile(_options(target))
    fifo = tmp_path / "nonregular-profile"
    os.mkfifo(fifo, 0o600)
    with pytest.raises(harness.PortableOAuthConfigurationError):
        harness.validate_portable_profile(_options(fifo))


def test_private_parent_and_non_symlink_ancestry_are_required(tmp_path: Path) -> None:
    directory = tmp_path / "owner-directory"
    directory.mkdir(mode=0o700)
    path = _profile(directory)
    directory.chmod(0o755)
    with pytest.raises(harness.PortableOAuthConfigurationError):
        harness.validate_portable_profile(_options(path))
    directory.chmod(0o700)
    ancestor = tmp_path / "alias-directory"
    ancestor.symlink_to(directory, target_is_directory=True)
    with pytest.raises(harness.PortableOAuthConfigurationError):
        harness.validate_portable_profile(_options(ancestor / path.name))


@pytest.mark.parametrize(
    "extra",
    [
        ["--oauth-config-file", "relative-config"],
        ["--oauth-client-id", CLIENT_ID],
        ["--oauth-config-file", "/absolute-config", "--oauth-client-id", " "],
        ["--oauth-config-file", "/absolute-config", "--oauth-client-id", "bad\nidentity"],
        ["--check-authentication"],
    ],
)
def test_portable_selectors_and_diagnostic_gate_reject_ambiguity(extra: list[str]) -> None:
    with pytest.raises(SystemExit):
        harness.parse_options([*_arguments(), *extra])


def test_child_environment_excludes_notebook_credentials_and_preserves_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from benchmark_agents.configuration import configured_environment
    from benchmark_agents.target_resolver import _reject_profile_overrides

    options = _options(_profile(tmp_path))
    inherited = {
        "HOME": "/unchanged-os-home",
        "PATH": "/reviewed-bin",
        "SSL_CERT_FILE": "/reviewed-certificates",
        "DATABRICKS_HOST": "https://notebook-injected-workspace",
        "DATABRICKS_TOKEN": PRIVATE_MARKER,
        "DATABRICKS_AUTH_TYPE": "runtime-oauth",
        "DATABRICKS_CLIENT_SECRET": PRIVATE_MARKER,
        "DATABRICKS_RUNTIME_VERSION": "serverless-context",
        "DATABRICKS_CONFIG_FILE": "/unselected-existing-config",
        "DATABRICKS_CONFIG_PROFILE": "unselected-profile",
        "OPENAI_API_KEY": PRIVATE_MARKER,
        "ARM_CLIENT_SECRET": PRIVATE_MARKER,
        "MLFLOW_TRACKING_TOKEN": PRIVATE_MARKER,
        "BENCHMARK_JUDGE_MODEL": "unselected-model",
        "PYTHONPATH": "/unreviewed-python-code",
        "PYTHONSTARTUP": "/unreviewed-python-code",
        "HTTP_PROXY": "http://credential-forwarding-proxy",
    }
    before = inherited.copy()
    child = harness.isolated_runner_environment(options, ROOT, inherited)
    assert inherited == before
    assert child["HOME"] == inherited["HOME"]
    assert child["SSL_CERT_FILE"] == inherited["SSL_CERT_FILE"]
    assert child["PYTHONPATH"] == str(ROOT)
    assert child["DATABRICKS_CONFIG_PROFILE"] == PROFILE
    assert child["DATABRICKS_CONFIG_FILE"] == str(options.oauth_config_file)
    assert PRIVATE_MARKER not in str(child)
    assert set(name for name in child if name.startswith("DATABRICKS_")) == {
        "DATABRICKS_CONFIG_PROFILE",
        "DATABRICKS_CONFIG_FILE",
    }
    monkeypatch.setattr(os, "environ", child)
    with configured_environment(child):
        _reject_profile_overrides()  # Native SDK field metadata only; no auth/request.


def test_profile_readiness_rejects_selector_mismatch_before_sdk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from benchmark_agents import providers

    def forbidden_client(**kwargs: Any) -> None:
        raise AssertionError("No SDK or OAuth access is permitted in this test")

    monkeypatch.setattr(providers, "workspace_client", forbidden_client)
    monkeypatch.delenv("DATABRICKS_CONFIG_FILE", raising=False)
    result = harness.readiness(_options(_profile(tmp_path)))
    assert result["blocker_codes"] == ["portable_oauth_selector_mismatch"]
    assert result["portable_oauth_source_verified"] is False
    assert result["inference_invocations"] == 0
    assert PRIVATE_MARKER not in json.dumps(result)


def test_dry_run_does_not_read_profile_or_launch_process(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Dry-run must not read or start anything")

    monkeypatch.setattr(harness, "validate_portable_profile", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    options = _options(Path("/absent-private-source"))
    receipt = harness.launch_runner(options, Path("/absent-reviewed-source"))
    assert receipt["portable_oauth_source_verified"] is False
    assert receipt["deployed_app_tested"] is False


def test_packaged_helper_and_legacy_script_share_one_implementation() -> None:
    """Verify import compatibility only; do not initialize any provider or target."""
    from evalsurge import serverless

    assert harness is serverless
    assert harness.__name__ == "evalsurge.serverless"


def test_default_package_root_launches_packaged_module_without_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use one inert native child; SDK, OAuth, Locust and agent code never execute."""
    native_popen = subprocess.Popen
    selected_root = Path(harness.__file__).resolve().parent.parent

    def only_diagnostic_bytes(arguments: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        assert arguments[:3] == [sys.executable, "-m", "evalsurge.serverless"]
        assert kwargs["cwd"] == selected_root
        assert kwargs["env"]["PYTHONPATH"] == str(selected_root)
        assert "scripts.validation" not in str(arguments)
        return native_popen([sys.executable, "-c", "print('not-a-provider-receipt')"], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", only_diagnostic_bytes)
    receipt = harness.launch_runner(_options(_profile(tmp_path), "--check-authentication"))
    assert receipt["passed"] is False
    assert receipt["owner_process_group_closed"] is True
    assert receipt["portable_oauth_source_verified"] is False


def test_packaged_module_dry_run_requires_no_checkout_or_credential_source() -> None:
    """Run real module parsing only; dry-run does not read/authenticate credentials."""
    completed = subprocess.run(
        [sys.executable, "-m", "evalsurge.serverless", *_arguments()],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["deployed_app_tested"] is False
    assert receipt["portable_oauth_source_verified"] is False


def test_missing_profile_live_gate_blocks_before_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Missing source must reject before auth or child creation")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    options = _options(
        tmp_path / "absent-source",
        "--live",
        "--accept-paid-traffic",
        "--real-inference-attested",
        "--artifact-dir",
        str(tmp_path / "unused-artifacts"),
    )
    receipt = harness.launch_runner(options, ROOT)
    assert receipt["state"] == "blocked"
    assert receipt["inference_invocations"] == 0
    assert receipt["portable_oauth_source_verified"] is False


def test_authentication_only_has_zero_target_budget_and_no_paid_gate(tmp_path: Path) -> None:
    options = _options(_profile(tmp_path), "--check-authentication")
    record = harness.budget_record(options)
    assert record["authentication_only"] is True
    assert record["maximum_app_invocations"] == 0
    assert record["max_requests"] == 0
    assert record["deployed_app_tested"] is False
    with pytest.raises(SystemExit):
        _options(_profile(tmp_path), "--check-authentication", "--live")


def _native_child(code: str, *, own_group: bool = True) -> subprocess.Popen[bytes]:
    """Start only native timing/byte emission; never import SDK/framework/provider."""
    return subprocess.Popen(
        [sys.executable, "-c", code],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=own_group,
        bufsize=0,
    )


def test_native_owner_bytes_are_bounded_and_group_is_reaped() -> None:
    child = _native_child("print('pure-process-diagnostic')")
    output, failure, closed = harness._capture_owner_output(child, timeout=5)
    assert output == b"pure-process-diagnostic\n"
    assert failure is None
    assert closed is True
    assert child.returncode == 0


def test_native_output_overflow_cannot_be_accepted_as_success() -> None:
    child = _native_child("import os; os.write(1, b'x' * 1000000)")
    output, failure, closed = harness._capture_owner_output(child, timeout=5)
    assert len(output) <= 65_536
    assert failure == "runner_output_limit"
    assert closed is True
    assert child.returncode is not None


def test_native_diagnostic_overflow_reaps_only_child() -> None:
    """Auth diagnostic bytes stay bounded without signalling the owning group."""
    owner_group = os.getpgrp()
    child = _native_child("import os; os.write(1, b'x' * 1000000)", own_group=False)
    try:
        assert os.getpgid(child.pid) == owner_group
        output, failure, closed = harness._capture_owner_output(child, timeout=5, own_group=False)
        assert len(output) <= 65_536
        assert failure == "runner_output_limit"
        assert closed is True
        assert child.returncode is not None
        assert os.getpgrp() == owner_group
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)


def test_group_verification_permission_error_never_certifies_cleanup(monkeypatch) -> None:
    """Unverifiable group state fails closed even when its known child is reaped."""
    child = _native_child("import time; time.sleep(30)")
    original_signal = os.killpg

    def unavailable(group: int, action: int) -> None:
        if group == child.pid and action == 0:
            raise PermissionError("synthetic-native-process-control-failure")
        original_signal(group, action)

    monkeypatch.setattr(os, "killpg", unavailable)
    try:
        assert harness._stop_owner_group(child) is False
        assert child.returncode is not None
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)


def test_post_reap_absence_resolves_transient_group_verification(monkeypatch) -> None:
    """Require a real absence observation after a transient OS permission error.

    The native inert child is actually terminated and reaped. Only the first
    group-visibility check receives a synthetic OS error; no agent, model, OAuth
    response or successful cleanup result is supplied by the test.
    """
    child = _native_child("import time; time.sleep(30)")
    original_signal = os.killpg
    visibility_error = False
    actions: list[int] = []

    def transient(group: int, action: int) -> None:
        nonlocal visibility_error
        assert group == child.pid
        actions.append(action)
        if action == 0 and not visibility_error:
            visibility_error = True
            raise PermissionError("synthetic-transient-native-process-control-failure")
        original_signal(group, action)

    monkeypatch.setattr(os, "killpg", transient)
    try:
        assert harness._stop_owner_group(child) is True
        assert child.returncode is not None
        assert visibility_error is True
        # Once visibility became unknown, only a read-only absence probe follows.
        assert actions == [signal.SIGTERM, 0, 0]
        with pytest.raises(ProcessLookupError):
            original_signal(child.pid, 0)
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)


def test_normal_exit_with_unverifiable_group_is_not_success(monkeypatch) -> None:
    """Normal process exit does not hide inability to verify descendant cleanup."""
    child = _native_child("print('inert-diagnostic-only')")
    original_signal = os.killpg

    def unavailable(group: int, action: int) -> None:
        if group == child.pid and action == 0:
            raise PermissionError("synthetic-native-process-control-failure")
        original_signal(group, action)

    monkeypatch.setattr(os, "killpg", unavailable)
    output, failure, closed = harness._capture_owner_output(child, timeout=5)
    assert output == b"inert-diagnostic-only\n"
    assert failure == "runner_process_group_unverified"
    assert closed is False
    assert child.returncode == 0


def test_normal_exit_transient_verification_requires_observed_group_absence(monkeypatch) -> None:
    """A reaped native owner is accepted only after a real absent-group probe."""
    child = _native_child("print('inert-diagnostic-only')")
    original_signal = os.killpg
    visibility_error = False
    actions: list[int] = []

    def transient(group: int, action: int) -> None:
        nonlocal visibility_error
        assert group == child.pid
        actions.append(action)
        if action == 0 and not visibility_error:
            visibility_error = True
            raise PermissionError("synthetic-transient-native-process-control-failure")
        original_signal(group, action)

    monkeypatch.setattr(os, "killpg", transient)
    output, failure, closed = harness._capture_owner_output(child, timeout=5)
    assert output == b"inert-diagnostic-only\n"
    assert failure is None
    assert closed is True
    assert child.returncode == 0
    assert actions == [0, 0]
    with pytest.raises(ProcessLookupError):
        original_signal(child.pid, 0)


def test_interrupt_survives_unverifiable_group_cleanup(monkeypatch) -> None:
    """Cleanup errors cannot mask the notebook interrupt or detach its known child."""
    child = _native_child("import time; time.sleep(30)")
    original_poll = child.poll
    original_signal = os.killpg
    interrupted = False

    def interrupt_once() -> int | None:
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise KeyboardInterrupt
        return original_poll()

    def unavailable(group: int, action: int) -> None:
        if group == child.pid and action == 0:
            raise PermissionError("synthetic-native-process-control-failure")
        original_signal(group, action)

    monkeypatch.setattr(child, "poll", interrupt_once)
    monkeypatch.setattr(os, "killpg", unavailable)
    try:
        with pytest.raises(KeyboardInterrupt):
            harness._capture_owner_output(child, timeout=5)
        assert child.returncode is not None
    finally:
        if original_poll() is None:
            child.kill()
        child.wait(timeout=5)


def test_native_deadline_terminates_owned_group_without_success() -> None:
    child = _native_child("import time; time.sleep(30)")
    output, failure, closed = harness._capture_owner_output(child, timeout=0.05)
    assert output == b""
    assert failure == "runner_deadline"
    assert closed is True
    assert child.returncode is not None


def test_notebook_interrupt_reaps_child_and_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = _native_child("import time; time.sleep(30)")
    poll = child.poll
    interrupted = False

    def interrupt_once() -> int | None:
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise KeyboardInterrupt
        return poll()

    monkeypatch.setattr(child, "poll", interrupt_once)
    with pytest.raises(KeyboardInterrupt):
        harness._capture_owner_output(child, timeout=5)
    assert child.returncode is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(child.pid, 0)


def test_remaining_descendant_is_not_mistaken_for_owner_cleanup() -> None:
    code = (
        "import subprocess,sys\n"
        "subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
        "print('owner-exited-not-a-lifecycle-receipt')\n"
    )
    child = _native_child(code)
    _, failure, closed = harness._capture_owner_output(child, timeout=5)
    assert failure == "owner_descendant_cleanup_required"
    assert child.returncode == 0
    # Some test hosts retain an orphan zombie until their PID 1 reaps it. Never
    # turn that unresolved group membership into successful lifecycle evidence.
    if closed:
        with pytest.raises(ProcessLookupError):
            os.killpg(child.pid, 0)
    else:
        # The retained negative observation stays negative. The host may reap
        # the group before this best-effort test-owned cleanup signal.
        with suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)


@pytest.mark.parametrize(
    "output",
    [
        "not-json-with-private-output",
        "[]",
        json.dumps({"passed": True}),
        json.dumps(
            {
                "runner": "serverless-notebook",
                "target_hosting": "deployed-databricks-app",
                "passed": False,
                "state": "blocked",
                "unexpected_private_field": PRIVATE_MARKER,
            }
        ),
    ],
)
def test_launcher_bad_diagnostic_receipt_never_proves_oauth_or_exports_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: str
) -> None:
    """Use byte-emitting native children, not substituted benchmark/inference phases."""
    native_popen = subprocess.Popen

    def only_diagnostic_bytes(arguments: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        assert "--check-authentication" in arguments
        assert "--live" not in arguments
        assert PRIVATE_MARKER not in str(arguments)
        assert PRIVATE_MARKER not in str(kwargs["env"])
        return native_popen([sys.executable, "-c", f"print({output!r})"], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", only_diagnostic_bytes)
    options = _options(_profile(tmp_path), "--check-authentication")
    receipt = harness.launch_runner(options, ROOT)
    assert receipt["passed"] is False
    assert receipt["state"] == "blocked"
    assert receipt["portable_oauth_source_verified"] is False
    assert receipt["owner_process_group_closed"] is True
    assert receipt["blocker_codes"] == ["runner_receipt_unavailable"]
    assert PRIVATE_MARKER not in json.dumps(receipt)
    assert "private-output" not in json.dumps(receipt)


def test_launcher_timeout_keeps_authentication_unverified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise native owner timeout only; SDK/OAuth/agent code never runs."""
    native_popen = subprocess.Popen
    bounded_capture = harness._capture_owner_output

    def only_wait(arguments: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        return native_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)

    def short_deadline(
        child: subprocess.Popen[bytes], **kwargs: Any
    ) -> tuple[bytes, str | None, bool]:
        return bounded_capture(child, timeout=0.05)

    monkeypatch.setattr(subprocess, "Popen", only_wait)
    monkeypatch.setattr(harness, "_capture_owner_output", short_deadline)
    receipt = harness.launch_runner(_options(_profile(tmp_path), "--check-authentication"), ROOT)
    assert receipt["blocker_codes"] == ["runner_deadline"]
    assert receipt["passed"] is False
    assert receipt["portable_oauth_source_verified"] is False
    assert receipt["owner_process_group_closed"] is True
    assert receipt["inference_invocations"] == "unknown"


@pytest.mark.asyncio
async def test_notebook_await_cancellation_drains_owned_thread_and_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancel native waiting children only; never launch SDK/OAuth/Locust/inference."""
    native_popen = subprocess.Popen
    created = threading.Event()
    children: list[subprocess.Popen[bytes]] = []

    def only_wait(arguments: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        child = native_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        children.append(child)
        created.set()
        return child

    monkeypatch.setattr(subprocess, "Popen", only_wait)
    owned = asyncio.create_task(
        harness.launch_runner_async(_options(_profile(tmp_path), "--check-authentication"), ROOT)
    )
    assert await asyncio.to_thread(created.wait, 5)
    owned.cancel()
    with pytest.raises(asyncio.CancelledError):
        await owned
    assert len(children) == 1
    assert children[0].returncode is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(children[0].pid, 0)


@pytest.mark.parametrize(
    "field",
    [
        "driver_profile_ready",
        "driver_identity_matches",
        "worker_oauth_ready",
        "worker_identity_matches",
        "portable_oauth_source_verified",
    ],
)
def test_valid_file_alone_never_proves_independent_oauth(field: str) -> None:
    authentication = {
        name: True
        for name in (
            "driver_profile_ready",
            "driver_identity_matches",
            "worker_oauth_ready",
            "worker_identity_matches",
            "portable_oauth_source_verified",
        )
    }
    authentication[field] = False
    assert harness._portable_auth_verified({"authentication": authentication}) is False
    assert harness._portable_auth_verified({"portable_oauth_source_verified": True}) is False
