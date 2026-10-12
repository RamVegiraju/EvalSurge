"""Check a genuinely installed wheel without agent, inference, or cloud calls.

Unlike inference integration checks, this harness only imports contracts, opens
and closes an empty direct SDK context, inspects packaged assets and asks Locust
to list its installed User class. No agent benchmark or target invocation is started.
An explicit timing-only option additionally exercises four native Locust/storage
modes against an inert loopback timing endpoint, never a substitute agent/model.
Locked dependencies are installed into fresh base/local/server environments; this is
not a public package-index publication check or a fresh dependency resolution.
"""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from uuid import uuid4

Surface = Literal["base", "local", "server"]
Installer = Literal["uv", "pip"]
_SERVER_PACKAGES = (
    "fastapi",
    "uvicorn",
    "locust",
    "gevent",
    "mlflow",
    "openai",
    "databricks-sdk",
    "requests",
    "python-dotenv",
)
_OS_ENVIRONMENT = frozenset(
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


def _installed_path(module: str) -> Path:
    """Require a module beneath this isolated environment's installed packages.

    Args:
        module: Already imported package/module name, never customer code.

    Returns:
        Its exact installed file path.

    Raises:
        AssertionError: Imports escaped this environment into an editable checkout.
    """
    path = Path(sys.modules[module].__file__).resolve()
    assert Path(sys.prefix).resolve() in path.parents, "Import escaped the isolated installation"
    assert "site-packages" in path.parts, "Expected an ordinary wheel installation"
    return path


def _base_checks() -> None:
    """Check remote-only imports and actionable direct-execution errors, without HTTP."""
    from evalsurge import (
        Case,
        EvalSurge,
        GeneratorHealth,
        Load,
        MissingServerDependenciesError,
        RemoteClient,
        RunCreate,
        TargetReference,
    )
    from evalsurge.calibration import calibrate, calibrate_async
    from evalsurge.cli import main
    from evalsurge.serverless import launch_runner, launch_runner_async

    _installed_path("evalsurge")
    _installed_path("benchmark_agents.v2_models")
    _installed_path("evalsurge.calibration")
    _installed_path("evalsurge.serverless")
    assert all(
        callable(helper)
        for helper in (calibrate, calibrate_async, launch_runner, launch_runner_async)
    )
    for package in _SERVER_PACKAGES:
        try:
            importlib.metadata.distribution(package)
        except importlib.metadata.PackageNotFoundError:
            continue
        raise AssertionError("Unexpected server distribution in base installation: " + package)
    assert "benchmark_agents.coordinator" not in sys.modules
    assert "evalsurge.client" not in sys.modules
    model = RunCreate(
        target=TargetReference(connection_id="schema-only"),
        cases=[Case(input={"diagnostic_only": True})],
        load=Load(concurrency=1, duration_seconds=0.1, max_requests=1),
    )
    assert model.evaluation.mode == "off"
    assert GeneratorHealth.model_json_schema()["properties"]["status"]["enum"] == [
        "unknown",
        "degraded",
    ]
    with EvalSurge.remote("http://127.0.0.1:9", typed=True) as remote:
        assert isinstance(remote, RemoteClient)
    for operation in (EvalSurge, EvalSurge.local, EvalSurge.local_async):
        try:
            operation()
        except MissingServerDependenciesError as error:
            assert "evalsurge[local]" in str(error)
            assert "evalsurge[server]" in str(error)
        else:
            raise AssertionError("Direct execution lacked missing-extra guidance")
    stderr, stdout = StringIO(), StringIO()
    with redirect_stderr(stderr), redirect_stdout(stdout):
        assert main(["doctor", "--local"]) == 2
    assert "evalsurge[local]" in stderr.getvalue()
    assert "evalsurge[server]" in stderr.getvalue()
    assert "benchmark_agents.coordinator" not in sys.modules


def _presentation_checks() -> None:
    """Exercise installed retrieval/summary functions on schema-only cancelled DTOs.

    No run is started, inferred, substituted or recorded as a benchmark outcome.
    The values validate Pydantic/public helper branches only, on both dependency
    surfaces. The renderer may not expose private names or credential-free links.
    """
    from evalsurge import Links, Report, Result, RunStatus, __version__, format_summary
    from evalsurge._retrieval import retrieval_evidence

    _installed_path("evalsurge._retrieval")
    _installed_path("evalsurge.summary")
    _installed_path("evalsurge._version")
    assert importlib.metadata.version("evalsurge") == __version__
    identifier = uuid4()
    result = Result(
        id=identifier,
        name="private-installation-schema-marker",
        status="cancelled",
        phases={
            "planning": "cancelled",
            "inference": "not_run",
            "evaluation_readiness": "not_run",
            "load": "skipped",
            "profiling": "skipped",
            "evaluation": "skipped",
        },
        links=Links.for_run(str(identifier)),
        summary={"performance": "not_run", "quality": "off"},
        preflight={},
        evaluation_preflight={},
    )
    status = RunStatus(
        id=identifier, status=result.status, phases=result.phases, links=result.links
    )
    report = Report(
        run=result,
        profiling={"total_requests": 0, "traced_requests": 0, "coverage": 0},
        requests=[],
        offset=0,
        limit=1,
        total=0,
    )
    evidence = retrieval_evidence(identifier, status, result, report, report, remote=False)
    assert evidence["retrieval_agrees"] is True
    assert evidence["remote_work_may_remain_active"] is False
    assert evidence["preflight_code"] is None
    summary = format_summary(result)
    assert format_summary(report) == summary
    assert "Lifecycle: cancelled." in summary
    assert "Performance: not_run." in summary
    assert "private-installation" not in summary
    assert str(identifier) not in summary


def _timing_only_checks(work: Path) -> int:
    """Exercise installed native workers with at most nine NON-agent HTTP requests.

    Args:
        work: Isolated installation check directory, never a customer artifact root.

    Returns:
        Actual timing-marker loopback dispatch count, separately from agent calls.

    Raises:
        AssertionError: Native completion/fault accounting or owned cleanup failed.

    Side Effects:
        Four owned Locust children, an inert endpoint, native storage-delay/fault
        probes and protected artifacts. No agent/model/auth/cloud calls or accuracy
        certification; every artifact is reclaimed with the enclosing check directory.
    """
    from evalsurge.calibration import calibrate

    receipt = calibrate(work / "timing-only", concurrency=1, max_requests=4, duration_seconds=0.5)
    assert receipt["completed"], "Installed native timing lifecycle did not complete"
    assert receipt["accuracy_certified"] is False
    assert all(receipt[name] == 0 for name in ("agent_calls", "model_calls", "cloud_calls"))
    assert {mode["mode"] for mode in receipt["modes"]} == {
        "native",
        "native_fsync_delay",
        "fail_start_before_write",
        "fail_completion_before_write",
    }
    assert all(mode["expected_lifecycle_observed"] for mode in receipt["modes"])
    assert all(
        receipt["cleanup"][name] is True
        for name in (
            "timing_server_stopped",
            "timing_handlers_stopped",
            "worker_exit_receipts_present",
            "worker_pid_exit_observed",
        )
    )
    assert receipt["cleanup"]["recorded_worker_count"] == 4
    assert 0 < receipt["timing_requests"] <= 9
    return receipt["timing_requests"]


def _server_checks(*, timing_only: bool = False) -> int:
    """Check installed native paths/assets; optional NON-agent timing is explicit."""
    from benchmark_agents import api, locust_runner
    from benchmark_agents.models import RunRequest
    from evalsurge import Agent, EvalSurge
    from evalsurge.calibration import calibrate, calibrate_async
    from evalsurge.cli import main
    from evalsurge.serverless import budget_record, parse_options, request

    for package in _SERVER_PACKAGES:
        importlib.metadata.distribution(package)
    # The locked Locust release itself requires pytest. Its presence is not
    # evidence that EvalSurge's dev group was installed; reject dev-only tools.
    for package in ("pytest-asyncio", "ruff", "hatchling", "langgraph", "openai-agents"):
        try:
            importlib.metadata.distribution(package)
        except importlib.metadata.PackageNotFoundError:
            continue
        raise AssertionError("Unexpected development/example dependency: " + package)
    installed = _installed_path("benchmark_agents.locust_runner").parent
    _installed_path("evalsurge")
    _installed_path("evalsurge.calibration")
    _installed_path("evalsurge.serverless")
    assert callable(calibrate) and callable(calibrate_async)
    assert Path(locust_runner.__file__).parent == installed
    assert Path(api.__file__).parent == installed
    # Exercise the installed public constructor without SDK construction, token
    # resolution or run admission. This is packaging coverage, not native OAuth.
    native_target = Agent.databricks_app(
        "installation-only",
        auth="app-runtime",
        workspace="https://installation-only.invalid",
        runner_app="installation-only-runner",
        client_id="11111111-2222-3333-4444-555555555555",
    )
    native_binding = native_target.registration.operator_record()
    assert native_binding["app_auth"] == "app-runtime"
    assert "profile" not in native_binding
    assert "client_secret" not in native_binding
    options = parse_options(
        [
            "--workspace",
            "https://installation-only.invalid",
            "--app-name",
            "installation-only",
            "--profile",
            "never-authenticated",
            "--target-model",
            "never-invoked",
            "--source-revision",
            "installation-only",
        ]
    )
    assert budget_record(options)["paid_traffic_authorized_by_this_record"] is False
    assert budget_record(options)["deployed_app_tested"] is False
    assert request().evaluation.mode == "off"
    for filename in (
        "locustfile.py",
        "static/index.html",
        "static/report.js",
        "static/report.css",
        "docs_ui/index.html",
        "docs_ui/vendor/swagger-ui-bundle.js",
        "docs_ui/vendor/swagger-ui.css",
        "docs_ui/vendor/manifest.json",
    ):
        assert (installed / filename).is_file(), "Installed asset missing: " + filename
    timing_dispatches = 0
    with TemporaryDirectory(prefix="evalsurge-installed-owner-") as temporary:
        work = Path(temporary)
        target = Agent.http("http://127.0.0.1:9/never-invoked", protocol="http-json")
        with EvalSurge(artifact_dir=work / "sync", targets={"agent": target}):
            pass

        async def check_async() -> None:
            async with EvalSurge.local_async(
                artifact_dir=work / "async", targets={"agent": target}
            ):
                pass

        asyncio.run(check_async())
        # Real Locust imports the wheel-owned entrypoint but --list exits before
        # test_start, authentication, journal creation, or target dispatch.
        worker = work / "worker"
        worker.mkdir(mode=0o700)
        configuration = RunRequest(
            target={"url": "http://127.0.0.1:9/never-invoked", "adapter": "http-json"},
            evaluation={
                "description": "Installed module discovery only; no benchmark",
                "scorers": [],
                "samples": [{"inputs": {"diagnostic_only": True}}],
            },
            load={"concurrency": 1, "duration_seconds": 0.1, "max_requests": 1},
        )
        config = worker / "config.json"
        config.write_text(configuration.model_dump_json(), encoding="utf-8")
        (worker / "connection.json").write_text(
            json.dumps({"url": str(configuration.target.url), "auth": "none"}),
            encoding="utf-8",
        )
        environment = {
            **{name: os.environ[name] for name in _OS_ENVIRONMENT if name in os.environ},
            "BENCHMARK_LOCUST_CONFIG": str(config),
            "BENCHMARK_LOCUST_RESULT": str(worker / "result.json"),
            "BENCHMARK_LOCUST_CANCEL": str(worker / "cancel"),
            "BENCHMARK_RUN_ID": "installed-module-discovery-only",
        }
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-m",
                "locust",
                "-f",
                str(installed / "locustfile.py"),
                "--list",
            ],
            cwd=worker,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        assert "AgentUser" in result.stdout
        assert not (worker / "requests.jsonl").exists()
        assert not (worker / "result.json").exists()
        if timing_only:
            timing_dispatches = _timing_only_checks(work)
    assert callable(main)
    return timing_dispatches


def installed_checks(surface: Surface, *, timing_only: bool = False) -> None:
    """Run installed checks only inside the selected isolated environment.

    Args:
        surface: Base client, local execution alias, or compatible server installation.
        timing_only: Explicit bounded NON-agent timing option for server checks.

    Side Effects:
        Imports wheel code, creates/reclaims temporary empty SDK artifacts and
        starts one module-listing Locust child. The explicit timing option adds
        four native workers and at most nine inert HTTP requests. Zero auth/agent/model calls.
    """
    timing_dispatches = 0
    _presentation_checks()
    if surface == "base":
        _base_checks()
    else:
        timing_dispatches = _server_checks(timing_only=timing_only)
    print(
        json.dumps(
            {
                "surface": surface,
                "distribution_version": importlib.metadata.version("evalsurge"),
                "installed_checks": "passed",
                "agent_calls": 0,
                "model_calls": 0,
                "target_dispatches": 0,
                "cloud_calls": 0,
                "non_agent_timing_dispatches": timing_dispatches,
                "accuracy_certified": False,
            }
        )
    )


def _install_step(
    command: list[str], *, work: Path, environment: dict[str, str], log: Path
) -> None:
    """Keep installer diagnostics private, including selected registry addresses.

    Args:
        command: Explicit uv arguments, potentially containing a private index selector.
        work: Private isolated installation working directory.
        environment: Detached OS/cache selectors, never model-provider credentials.
        log: New protected diagnostic file; its contents are not exported.

    Raises:
        RuntimeError: A bounded install failed; details remain in protected diagnostics.
        OSError: The private log cannot be created.
    """
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        try:
            result = subprocess.run(
                command,
                cwd=work,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=240,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "Installation deadline exceeded; inspect protected diagnostics"
            ) from None
    if result.returncode:
        raise RuntimeError("Locked installation failed; inspect protected diagnostics")


def _pip_command(python: Path, operation: Literal["install", "check"]) -> list[str]:
    """Build a native pip command without running it or reading package configuration.

    Args:
        python: Interpreter inside the verifier's fresh stdlib virtual environment.
        operation: Dependency installation or installed-graph consistency check.

    Returns:
        Explicit interpreter/module arguments with pip's update notification disabled.

    Side Effects:
        None. The caller supplies a detached environment with pip config disabled,
        and explicitly selects an approved index or no-index wheel installation.
    """
    return [str(python), "-m", "pip", "--disable-pip-version-check", operation]


def _dependency_install_command(
    python: Path,
    *,
    installer: Installer,
    dependency_index: str,
    manifest: Path,
    offline: bool = False,
) -> list[str]:
    """Build exact locked-manifest installer arguments without executing them.

    Args:
        python: Interpreter belonging to the verifier's isolated environment.
        installer: Native pip or uv's compatible installer.
        dependency_index: Explicit operator-selected approved package source.
        manifest: Hash-pinned requirements exported from the unchanged lock.
        offline: Restrict uv to its artifact cache; pip is rejected by ``verify``.

    Returns:
        Installer-specific requirements-file arguments with dependency resolution
        disabled. Pip requires singular ``--requirement``; plural abbreviates its
        unrelated PEP 723 ``--requirements-from-script`` option in recent releases.

    Side Effects:
        None. The caller detaches credentials and ambient package configuration.
    """
    command = (
        _pip_command(python, "install")
        if installer == "pip"
        else ["uv", "--no-config", "pip", "install", "--python", str(python)]
    ) + [
        "--require-hashes",
        "--no-deps",
        "--index-url" if installer == "pip" else "--default-index",
        dependency_index,
        "--requirement" if installer == "pip" else "--requirements",
        str(manifest),
    ]
    if offline:
        command.append("--offline")
    return command


def verify(
    wheel: Path,
    *,
    surface: Surface,
    offline: bool = False,
    dependency_index: str | None = None,
    evidence_dir: Path | None = None,
    timing_only: bool = False,
    installer: Installer = "uv",
) -> None:
    """Install exact locked dependencies and a wheel outside the source checkout.

    Args:
        wheel: Trusted current build artifact, installed without dependency resolution.
        surface: Base client, local execution alias, or compatible server installation.
        offline: Use cached authentic locked artifacts only; never switch indexes.
        dependency_index: Explicit operator-approved index. Dependency versions/hashes
            still come unchanged from the lock; this does not change its provenance.
        evidence_dir: Optional new private evidence directory for installer diagnostics.
        timing_only: Explicit bounded NON-agent timing run in a local/server environment.
        installer: uv (default), or fresh stdlib-venv pip using an explicit approved
            online source. Pip does not reuse uv's artifact cache.

    Raises:
        subprocess.CalledProcessError: Installation, dependency or installed checks fail.
        subprocess.TimeoutExpired: A bounded installation/check does not complete.
        RuntimeError: Installation failed without exposing a private index/diagnostic.
        ValueError: Pip was requested without an explicit online approved source.

    Side Effects:
        Creates/removes a private temporary environment with uv or stdlib venv.
        The default offline
        path matches authentic lock provenance. An explicitly selected approved
        index instead receives a hash-pinned manifest exported from that lock:
        uv verifies artifact hashes, and no cache origin/lock record is relabelled.
        No provider settings/tokens/notebook context enter check children.
    """
    if installer == "pip" and (dependency_index is None or offline):
        raise ValueError("Pip verification requires an explicit approved online dependency source")
    root = Path(__file__).resolve().parents[1]
    lock_digest = hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()
    with TemporaryDirectory(prefix="evalsurge-install-") as temporary:
        work = Path(temporary)
        environment = {name: os.environ[name] for name in _OS_ENVIRONMENT if name in os.environ}
        if "UV_CACHE_DIR" in os.environ:
            environment["UV_CACHE_DIR"] = os.environ["UV_CACHE_DIR"]
        if installer == "pip":
            # Suppress all pip configuration files in this detached child, including
            # leftover extra indexes. No global user/tool configuration is changed.
            environment["PIP_CONFIG_FILE"] = os.devnull
        environment["UV_PROJECT_ENVIRONMENT"] = str(work / "venv")
        if evidence_dir is not None:
            evidence_dir.mkdir(mode=0o700, exist_ok=True)
            metadata = evidence_dir.lstat()
            if (
                not evidence_dir.is_dir()
                or metadata.st_uid != os.geteuid()
                or metadata.st_mode & 0o077
            ):
                raise ValueError("Installation evidence requires an owner-only directory")
        logs = work / "diagnostics" if evidence_dir is None else evidence_dir / surface
        logs.mkdir(mode=0o700, exist_ok=False)
        command = [
            "uv",
            "--no-config",
            "sync",
            "--project",
            str(root),
            "--locked",
            "--no-dev",
            "--no-install-project",
            "--python",
            sys.executable,
            "--default-index",
            "https://pypi.org/simple",
        ]
        if surface != "base":
            command.extend(["--extra", surface])
        if offline:
            command.append("--offline")
        python = work / "venv" / "bin" / "python"
        if dependency_index is None:
            _install_step(
                command, work=work, environment=environment, log=logs / "sync.private.log"
            )
        else:
            manifest = logs / "locked-requirements.txt"
            export = [
                "uv",
                "--no-config",
                "export",
                "--project",
                str(root),
                "--python",
                sys.executable,
                "--locked",
                "--no-dev",
                "--no-emit-project",
                "--format",
                "requirements-txt",
                "--offline",
                "--default-index",
                "https://pypi.org/simple",
                "--output-file",
                str(manifest),
            ]
            if surface != "base":
                export.extend(["--extra", surface])
            _install_step(
                export, work=work, environment=environment, log=logs / "export.private.log"
            )
            manifest.chmod(0o600)
            _install_step(
                (
                    [sys.executable, "-m", "venv", str(work / "venv")]
                    if installer == "pip"
                    else [
                        "uv",
                        "--no-config",
                        "venv",
                        "--python",
                        sys.executable,
                        str(work / "venv"),
                    ]
                ),
                work=work,
                environment=environment,
                log=logs / "venv.private.log",
            )
            install = _dependency_install_command(
                python,
                installer=installer,
                dependency_index=dependency_index,
                manifest=manifest,
                offline=offline,
            )
            _install_step(
                install, work=work, environment=environment, log=logs / "dependencies.private.log"
            )
            (logs / "provenance.safe.json").write_text(
                json.dumps(
                    {
                        "dependency_source": "explicit-operator-approved-index",
                        "installer": installer,
                        "surface": surface,
                        "artifact_hashes_required": True,
                        "lock_unchanged": lock_digest
                        == hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest(),
                        "lock_sha256": lock_digest,
                        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                        "public_index_install_established": False,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            (logs / "provenance.safe.json").chmod(0o600)
        wheel_requirement = str(wheel.resolve()) + (f"[{surface}]" if surface != "base" else "")
        wheel_command = (
            _pip_command(python, "install")
            if installer == "pip"
            else ["uv", "pip", "install", "--python", str(python)]
        )
        _install_step(
            wheel_command
            + [
                "--no-deps",
                "--no-index",
                wheel_requirement,
            ],
            work=work,
            environment=environment,
            log=logs / "wheel.private.log",
        )
        _install_step(
            (
                _pip_command(python, "check")
                if installer == "pip"
                else ["uv", "pip", "check", "--python", str(python)]
            ),
            work=work,
            environment=environment,
            log=logs / "check.private.log",
        )
        checked_environment = {
            name: os.environ[name] for name in _OS_ENVIRONMENT if name in os.environ
        }
        installed_command = [
            str(python),
            "-I",
            str(Path(__file__).resolve()),
            "--check-installed",
            surface,
        ]
        if timing_only and surface != "base":
            installed_command.append("--timing-only")
        subprocess.run(
            installed_command,
            cwd=work,
            env=checked_environment,
            check=True,
            timeout=60,
        )
        subprocess.run(
            [str(work / "venv" / "bin" / "evalsurge"), "--help"],
            cwd=work,
            env=checked_environment,
            check=True,
            timeout=30,
        )
        if surface != "base":
            # These are copied/downloaded onboarding scripts, not wheel-owned
            # assets. -I and the external cwd prevent their imports from using
            # the checkout; --help exits before consent, auth or target setup.
            for filename, required_option in (
                ("local_runner_http_target.py", "--protocol"),
                ("local_runner_databricks_app_target.py", "--profile"),
            ):
                result = subprocess.run(
                    [str(python), "-I", str(root / "examples" / "journeys" / filename), "--help"],
                    cwd=work,
                    env=checked_environment,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30,
                )
                assert required_option in result.stdout
                assert "--allow-paid-inference" in result.stdout
            print(
                json.dumps(
                    {
                        "installed_journey_script_help_checks": 2,
                        "agent_calls": 0,
                        "authentication_calls": 0,
                    }
                )
            )
        if hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest() != lock_digest:
            raise RuntimeError("Lock changed during isolated installation verification")


def main() -> None:
    """Verify explicit or sole built wheel; installed child checks never rebuild it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--surface", choices=("base", "local", "server", "all"), default="all")
    parser.add_argument("--installer", choices=("uv", "pip"), default="uv")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--timing-only",
        action="store_true",
        help="Also run at most nine inert loopback NON-agent timing requests (local/server only)",
    )
    parser.add_argument(
        "--dependency-index", help="Explicit approved package source; never changes lock hashes"
    )
    parser.add_argument(
        "--evidence-dir", type=Path, help="New private installer evidence directory"
    )
    parser.add_argument(
        "--check-installed", choices=("base", "local", "server"), help=argparse.SUPPRESS
    )
    options = parser.parse_args()
    if options.check_installed:
        installed_checks(options.check_installed, timing_only=options.timing_only)
        return
    if options.wheel is None:
        wheels = list((Path(__file__).resolve().parents[1] / "dist").glob("evalsurge-*.whl"))
        if len(wheels) != 1:
            parser.error("Select an explicit --wheel or exactly one build artifact")
        options.wheel = wheels[0]
    for surface in ("base", "local", "server") if options.surface == "all" else (options.surface,):
        verify(
            options.wheel,
            surface=surface,
            offline=options.offline,
            dependency_index=options.dependency_index,
            evidence_dir=options.evidence_dir,
            timing_only=options.timing_only,
            installer=options.installer,
        )


if __name__ == "__main__":
    main()
