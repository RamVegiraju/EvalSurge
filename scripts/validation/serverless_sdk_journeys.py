"""Historical diagnostic for notebook-driver-local HTTP/helper execution.

Use from a dedicated serverless notebook with the installed wheel and the source
``examples``/``scripts`` packages available. No job is submitted by this module.
Dry-run emits bounds only. ``prerequisite_probe`` checks native driver auth,
loopback sockets and the Locust executable without making any model calls. Live
execution requires explicit consent, endpoint, workspace and empty private storage.

This topology is notebook -> HTTP framework server on the notebook driver, or
notebook -> authenticated loopback EvalSurge API -> that HTTP framework server.
Neither is notebook -> deployed Databricks App. The profile-only App resolver is
unchanged; notebook/App identity and deployment validation remain separate gates.
This module is not the intended hosted-agent journey. Use the separate
``serverless_runner_app_target`` readiness gate and runner-only notebook sample
for that topology; never substitute this diagnostic for deployed-App coverage.
"""

import argparse
import asyncio
import hashlib
import math
import os
import secrets
import socket
import sys
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager, contextmanager, suppress
from importlib.metadata import version
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .dispatch_observer import (
    DispatchObserver,
    wait_for_active_dispatch,
    wait_for_active_dispatch_sync,
)
from .hosted_journeys import retrieval_evidence
from .unified_sdk_journeys import (
    _content_free_report,
    _report_after_wait,
    _serve_without_host_exit,
)


def parse_options(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse bounded operator selections without auth, I/O or inference.

    Args:
        arguments: Optional explicit CLI arguments; omission reads argv.

    Returns:
        Explicit selections, never an automatically chosen model/workspace.

    Raises:
        SystemExit: Unsafe origin, missing consent or invalid finite bounds.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--target-model", required=True)
    parser.add_argument(
        "--framework", required=True, choices=("langgraph", "openai-agents", "crewai")
    )
    parser.add_argument(
        "--model-api", required=True, choices=("mlflow-responses", "openai-responses")
    )
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--max-requests", type=int, default=5)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--exercise-cancel", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--accept-paid-traffic", action="store_true")
    options = parser.parse_args(arguments)
    try:
        parsed = urlsplit(options.workspace)
        port = parsed.port
    except ValueError:
        parser.error("--workspace must be an explicitly approved HTTPS workspace origin")
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or port not in {None, 443}
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        parser.error("--workspace must be an explicitly approved HTTPS workspace origin")
    options.workspace = options.workspace.rstrip("/")
    if not options.target_model.strip() or len(options.target_model) > 512:
        parser.error("--target-model must name the explicitly approved serving endpoint")
    if not 1 <= options.concurrency <= 5 or not 1 <= options.max_requests <= 20:
        parser.error("--concurrency must be 1..5 and --max-requests 1..20")
    if not 1 <= options.max_output_tokens <= 512:
        parser.error("--max-output-tokens must be 1..512")
    for name, maximum in (("duration", 180), ("timeout", 30)):
        value = getattr(options, name)
        if not math.isfinite(value) or not 0.1 <= value <= maximum:
            parser.error(f"--{name} must be finite and between 0.1 and {maximum} seconds")
    if options.live and (not options.accept_paid_traffic or options.artifact_dir is None):
        parser.error("--live requires --accept-paid-traffic and dedicated --artifact-dir")
    return options


def budget_record(options: argparse.Namespace) -> dict[str, Any]:
    """Return aggregate direct/API invocation bounds, never a monetary quota.

    Each mode has one model-bearing preflight per run. A failed normal run stops
    further runs. Unknown-route probes make no inference calls. These reviewed
    no-tool examples make one call per LangGraph/OpenAI Agents invocation and at
    most two per CrewAI invocation; provider retries are disabled. Output-token
    settings are requests to the provider, not an enforced monetary quota.
    """
    modes = 2
    runs = modes * (2 if options.exercise_cancel else 1)
    return {
        "live": options.live,
        "topology": "notebook-driver-http-and-authenticated-loopback-api",
        "framework": options.framework,
        "model_api": options.model_api,
        "max_output_tokens_per_model_call": options.max_output_tokens,
        "concurrency": options.concurrency,
        "dispatch_seconds_per_run": options.duration,
        "per_attempt_timeout_seconds": options.timeout,
        "normal_run_count": runs,
        "max_measured_invocations": runs * options.max_requests,
        "max_model_bearing_probe_invocations": runs,
        "max_negative_route_probes_without_model_dispatch": modes,
        "max_total_target_attempts": runs * (options.max_requests + 1) + modes,
        "evaluation_mode": "off",
        "inference_stubbed": False,
        "deployed_app_tested": False,
        "model_calls_per_agent_invocation_bounded": True,
        "max_model_calls_per_agent_invocation": 2 if options.framework == "crewai" else 1,
        "max_model_calls": runs
        * (options.max_requests + 1)
        * (2 if options.framework == "crewai" else 1),
        "metadata_retry_window_seconds": 1,
        "monetary_quota_enforced": False,
        "sustainable_capacity_established": False,
    }


def driver_workspace(expected_origin: str) -> Any:
    """Create caller-owned refreshable OAuth using only notebook-driver identity.

    Args:
        expected_origin: Exact user-approved workspace origin, without a slash.

    Returns:
        SDK WorkspaceClient authenticated by runtime-oauth, not a laptop profile.

    Raises:
        RuntimeError: Not running on a notebook driver, auth unavailable or native
            runtime selected a different workspace. Raw SDK messages are hidden.

    OAuth token exchange may make workspace authentication calls, never model
    inference. Tokens remain inside the SDK provider; no token is copied to a
    file, profile, subprocess configuration, environment variable or job parameter.
    The supplied origin is checked *after* runtime auth resolves its native host.
    """
    if not os.environ.get("DATABRICKS_RUNTIME_VERSION"):
        raise RuntimeError("Notebook driver authentication is unavailable")
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config

    try:
        workspace = WorkspaceClient(
            config=Config(
                host=expected_origin,
                auth_type="runtime-oauth",
                scopes=["all-apis"],
                http_timeout_seconds=20,
                retry_timeout_seconds=1,
            )
        )
        if workspace.config.host.rstrip("/") != expected_origin:
            raise ValueError
        workspace.config.oauth_token()
        return workspace
    except Exception:  # noqa: BLE001 - SDK messages may include private auth configuration
        raise RuntimeError("Notebook OAuth or exact workspace verification failed") from None


def _create_driver_helper(options: argparse.Namespace, workspace: Any) -> Any:
    """Own the latest generic helper's actual guarded Responses/framework clients.

    Args:
        options: Explicit framework, model, API route and bounded model settings.
        workspace: Caller-owned native runtime-OAuth client for the exact notebook
            workspace. It stays in this driver process; no profile/token is copied.

    Returns:
        Real FastAPI /invoke helper with request-local framework state and clients
        closed after owned server shutdown. Startup does not call any model.

    Raises:
        ValueError: Configured host is different, framework/configuration invalid.
        ImportError: A selected framework is unavailable; never installs/falls back.

    Side Effects:
        Native SDK refresh is requested by model dispatch inside the agent process.
        Each request makes bounded actual Responses calls; no tools, judging,
        profiling or tracing are silently added. Locust uses loopback HTTP only.
        The model-selection profile label below is descriptive metadata, not a
        named-profile lookup: only the supplied runtime workspace authenticates.
    """
    from evalsurge.serving import AgentAnswer, InvocationContext, create_app
    from examples.real_framework_agent import (
        ModelSelection,
        build_handler,
        response_completion_guard,
    )

    if workspace.config.host.rstrip("/") != options.workspace:
        raise ValueError("Runtime identity does not resolve to the approved workspace")
    selection = ModelSelection(
        profile="notebook-driver-runtime-oauth",
        model=options.target_model,
        api=options.model_api,
        expected_host=options.workspace,
        max_output_tokens=options.max_output_tokens,
        timeout_seconds=options.timeout,
    )
    resources: dict[str, Any] = {}

    async def handler(inputs: dict[str, Any], context: InvocationContext) -> AgentAnswer:
        return await resources["handler"](inputs, context)

    app = create_app(handler, isolation="request")
    app.state.inference_evidence = {"outbound_attempts": 0, "completed_responses": 0}

    async def record_dispatch(request: Any) -> None:
        """Count actual outbound attempts, never retaining request/credential data."""
        app.state.inference_evidence["outbound_attempts"] += 1

    async def record_completion(response: Any) -> None:
        """Count only HTTP successes accepted by the preceding raw completion guard."""
        if 200 <= response.status_code < 300:
            app.state.inference_evidence["completed_responses"] += 1

    @asynccontextmanager
    async def lifespan(app: Any) -> AsyncIterator[None]:
        import httpx
        from openai import AsyncOpenAI

        from benchmark_agents.providers import DatabricksAuth

        async with (
            httpx.AsyncClient(
                auth=DatabricksAuth(workspace),
                trust_env=False,
                follow_redirects=False,
                timeout=selection.timeout_seconds,
                event_hooks={
                    "request": [record_dispatch],
                    "response": [response_completion_guard, record_completion],
                },
            ) as http,
            AsyncOpenAI(
                base_url=selection.base_url,
                api_key="sdk-auth",
                http_client=http,
                max_retries=0,
                timeout=selection.timeout_seconds,
            ) as client,
        ):
            resources["handler"] = build_handler(
                options.framework, client, selection, http_client=http
            )
            try:
                yield
            finally:
                resources.clear()

    app.router.lifespan_context = lifespan
    return app


async def prerequisite_probe(expected_origin: str) -> dict[str, Any]:
    """Check driver auth, a bound loopback socket and Locust launch, no inference.

    Args:
        expected_origin: Exact user-approved workspace origin.

    Returns:
        Value-free prerequisites and installed package versions. Auth requests can
        occur, but no agent, model provider or deployed App is invoked.

    Raises:
        RuntimeError: Authentication or local prerequisites are unavailable.
        TimeoutError: Locust executable inspection exceeds 30 seconds.
    """
    await asyncio.to_thread(driver_workspace, expected_origin)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "locust",
        "--version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(process.communicate(), timeout=30)
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
    if process.returncode != 0:
        raise RuntimeError("Notebook Locust executable is unavailable")
    return {
        "inference_calls": 0,
        "driver_oauth_ready": True,
        "workspace_matches": True,
        "loopback_socket_ready": True,
        "locust_executable_ready": True,
        "versions": {
            name: version(name)
            for name in ("evalsurge", "databricks-sdk", "locust", "langgraph", "openai-agents")
        },
        "deployed_app_tested": False,
    }


@contextmanager
def _owned_demo_environment(values: dict[str, str]) -> Iterator[None]:
    """Scope only demo/API settings before startup and after owned resources close.

    Args:
        values: Harness-owned settings for this dedicated validation process.

    Side Effects:
        A new tracking store starts without a previous store's experiment ID.
        Native MLflow writes that ID during setup; restore its original value,
        including absence, after owned resources drain, even when startup fails.

    No Databricks authentication setting is modified. This is a dedicated notebook
    validation process, not a thread-safe configuration interface for shared apps.
    """
    owned = dict(values)
    if "MLFLOW_TRACKING_URI" in owned:
        owned["MLFLOW_EXPERIMENT_ID"] = ""
    previous = {key: os.environ.get(key) for key in owned}
    os.environ.update(owned)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


async def _serve(app: Any) -> tuple[Any, asyncio.Task[Any], socket.socket, str]:
    """Own one loopback Uvicorn task; close sockets on every startup failure."""
    import uvicorn

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", proxy_headers=False))
    task = asyncio.create_task(_serve_without_host_exit(server, listener))
    try:
        for _ in range(3000):
            if server.started:
                return server, task, listener, f"http://127.0.0.1:{listener.getsockname()[1]}"
            if task.done():
                await task
                raise RuntimeError("Loopback server did not start")
            await asyncio.sleep(0.01)
        raise TimeoutError("Loopback server startup exceeded 30 seconds")
    except BaseException:
        server.should_exit = True
        if not task.done():
            task.cancel()
        with suppress(BaseException):
            await task
        listener.close()
        raise


async def _close_servers(
    servers: list[tuple[Any, asyncio.Task[Any], socket.socket, str]], record: dict[str, Any]
) -> None:
    """Close API before agent, trying every resource even after shutdown failures.

    Args:
        servers: Owned server/task/listener tuples in startup order; emptied here.
        record: Content-free evidence; cleanup failures cannot become a pass.

    Raises:
        RuntimeError: Any server failed shutdown within its 60-second bound.

    Listeners always close. The enclosing caller must persist evidence in finally
    even if cleanup fails; trusted/native code is not a hard isolation sandbox.
    """
    failed = False
    for server, task, listener, _ in reversed(servers):
        server.should_exit = True
        try:
            await asyncio.wait_for(task, timeout=60)
        except BaseException:  # noqa: BLE001 - finish all owned cleanup, hide exception detail
            failed = True
        finally:
            listener.close()
    servers.clear()
    record["owned_resources_closed"] = not failed
    if failed:
        record["passed"] = False
        record["cleanup_error"] = "owned_server_shutdown_failed"
        raise RuntimeError("Owned loopback server cleanup failed")


def _successful(report: Any) -> bool:
    """Require real preflight/measured success; completion alone is not quality."""
    run = report.run
    return (
        run.preflight.status == "passed"
        and run.phases.load == "completed"
        and run.metrics is not None
        and run.metrics.successful_requests > 0
        and run.metrics.error_rate == 0
    )


def _failed_fast(report: Any) -> bool:
    """Unknown routes must fail the real HTTP probe before measured dispatch."""
    run = report.run
    return (
        run.preflight.status == "failed"
        and run.phases.load == "skipped"
        and (run.metrics is None or run.metrics.requests == 0)
    )


async def _exercise_direct(
    options: argparse.Namespace, bindings: dict[str, Any], observer: DispatchObserver
) -> list[dict]:
    """Use the async direct handle so the owned HTTP agent can run on this loop."""
    from evalsurge import EvalSurge, TargetReference

    request = _request(options)
    bound = options.duration + 2 * options.timeout + 120
    checks: list[dict] = []
    async with EvalSurge.local_async(
        artifact_dir=options.artifact_dir / "direct", targets=bindings
    ) as client:
        run = await client.start(request)
        report = await _report_after_wait(run, bound)
        status, result, retrieved = await run.status(), await run.result(), await run.report()
        parity = retrieval_evidence(run.id, status, result, report, retrieved, remote=False)
        passed = _successful(report) and parity["retrieval_agrees"]
        checks.append(
            {"check": "direct_normal", "passed": passed, **_content_free_report(report), **parity}
        )
        if not passed:
            return checks
        bad = request.model_copy(update={"target": TargetReference(connection_id="negative")})
        failed_run = await client.start(bad)
        report = await _report_after_wait(failed_run, bound)
        parity = retrieval_evidence(
            failed_run.id,
            await failed_run.status(),
            await failed_run.result(),
            report,
            await failed_run.report(),
            remote=False,
        )
        failed_fast = _failed_fast(report) and parity["retrieval_agrees"]
        checks.append(
            {
                "check": "direct_pre_provider_fail_fast",
                "passed": failed_fast,
                **_content_free_report(report),
                **parity,
            }
        )
        if not failed_fast or not options.exercise_cancel:
            return checks
        run = await client.start(request)
        status, counts = await wait_for_active_dispatch(run, observer, bound)
        active = status.status == "running"
        measured_observed = active and counts["measured_inflight"] > 0
        acknowledgment = await run.cancel() if active else None
        report = await _report_after_wait(run, bound)
        parity = retrieval_evidence(
            run.id, await run.status(), await run.result(), report, await run.report(), remote=False
        )
        checks.append(
            {
                "check": "direct_active_cancel",
                "passed": measured_observed
                and report.run.status == "cancelled"
                and parity["retrieval_agrees"],
                "acknowledgment": acknowledgment.status if acknowledgment else None,
                "measured_dispatch_observed_at_cancel": measured_observed,
                "measured_inflight_at_cancel": counts["measured_inflight"],
                "measured_receipts_at_cancel": counts["measured_received"],
                "naturally_completed_before_cancel": status.status
                in {"completed", "completed_with_gaps"},
                **_content_free_report(report),
                **parity,
            }
        )
    return checks


def _request(options: argparse.Namespace) -> Any:
    """Build the same public v2 request for direct/remote, with evaluation off."""
    from evalsurge import Case, Load, RunCreate, TargetReference

    return RunCreate(
        target=TargetReference(connection_id="agent"),
        cases=[Case(input={"query": "Can an opened item be refunded?"})],
        load=Load(
            concurrency=options.concurrency,
            duration_seconds=options.duration,
            max_requests=options.max_requests,
            timeout_seconds=options.timeout,
        ),
    )


def _exercise_api(
    options: argparse.Namespace, origin: str, key: str, observer: DispatchObserver
) -> list[dict]:
    """Run sync typed remote on its owned thread, never block the agent event loop."""
    import httpx

    from evalsurge import EvalSurge, TargetReference

    checks: list[dict] = []
    with httpx.Client(trust_env=False, timeout=10) as transport:
        unauthorized = transport.get(origin + "/v2/capabilities")
        authorized = transport.get(origin + "/v2/capabilities", headers={"X-API-Key": key})
    authentication = unauthorized.status_code == 401 and authorized.status_code == 200
    checks.append({"check": "api_authentication", "passed": authentication})
    if not authentication:
        return checks
    request = _request(options)
    bound = options.duration + 2 * options.timeout + 120
    with EvalSurge.remote(origin, api_key=key, typed=True, poll_interval=0.05) as client:

        def wait(run: Any) -> Any:
            try:
                return run.wait(timeout=bound)
            except Exception as error:
                if getattr(error, "report", None) is None:
                    raise
                return error.report

        run = client.start(request)
        report = wait(run)
        status, result, retrieved = run.status(), run.result(), run.report()
        parity = retrieval_evidence(run.id, status, result, report, retrieved, remote=True)
        passed = _successful(report) and parity["retrieval_agrees"]
        checks.append(
            {"check": "api_normal", "passed": passed, **_content_free_report(report), **parity}
        )
        if not passed:
            return checks
        bad = request.model_copy(update={"target": TargetReference(connection_id="negative")})
        failed_run = client.start(bad)
        report = wait(failed_run)
        parity = retrieval_evidence(
            failed_run.id,
            failed_run.status(),
            failed_run.result(),
            report,
            failed_run.report(),
            remote=True,
        )
        failed_fast = _failed_fast(report) and parity["retrieval_agrees"]
        checks.append(
            {
                "check": "api_pre_provider_fail_fast",
                "passed": failed_fast,
                **_content_free_report(report),
                **parity,
            }
        )
        if not failed_fast or not options.exercise_cancel:
            return checks
        run = client.start(request)
        status, counts = wait_for_active_dispatch_sync(run, observer, bound)
        active = status.status == "running"
        measured_observed = active and counts["measured_inflight"] > 0
        acknowledgment = run.cancel() if active else None
        report = wait(run)
        parity = retrieval_evidence(
            run.id, run.status(), run.result(), report, run.report(), remote=True
        )
        checks.append(
            {
                "check": "api_active_cancel",
                "passed": measured_observed
                and report.run.status == "cancelled"
                and parity["retrieval_agrees"],
                "acknowledgment": acknowledgment.status if acknowledgment else None,
                "measured_dispatch_observed_at_cancel": measured_observed,
                "measured_inflight_at_cancel": counts["measured_inflight"],
                "measured_receipts_at_cancel": counts["measured_received"],
                "naturally_completed_before_cancel": status.status
                in {"completed", "completed_with_gaps"},
                **_content_free_report(report),
                **parity,
            }
        )
    return checks


async def execute(options: argparse.Namespace) -> dict[str, Any]:
    """Exercise real framework inference and both SDK modes on a notebook driver.

    Args:
        options: Parsed explicit live consent, target model and traffic bounds.

    Returns:
        Protected validation record with phase/metric evidence and cleanup status.
        No inputs, answers, provider tokens or API service key are exported.

    Raises:
        ValueError: Consent/storage missing or prior evidence would be overwritten.
        Exception: Prerequisite, server, transport or cleanup failure, no fallback.

    Side Effects:
        Driver OAuth exchange, actual model/tool traffic, protected local artifacts,
        two owned loopback Uvicorn servers, and the existing sole Locust engine.
        In-memory key is never persisted. All owned servers/coordinators/model
        transports close before return. No App/job/cluster resources are provisioned.
        Use a dedicated notebook task; local driver artifacts are not durable.
    """
    if not options.live or not options.accept_paid_traffic or options.artifact_dir is None:
        raise ValueError("Live validation requires explicit consent and protected storage")
    directory = options.artifact_dir.resolve()
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Select empty storage; previous evidence is never overwritten")
    options.artifact_dir = directory
    from benchmark_agents.storage import atomic_json
    from evalsurge import Agent

    workspace = await asyncio.to_thread(driver_workspace, options.workspace)
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        **budget_record(options),
        "workspace": options.workspace,
        "model_endpoint": options.target_model,
        "driver_authentication": "runtime-oauth",
        "checks": [],
        "passed": False,
        "app_journey": "not_exercised_profile_auth_contract_and_deployment_unavailable",
    }
    servers: list[tuple[Any, asyncio.Task[Any], socket.socket, str]] = []
    helper: Any | None = None
    path = directory / "serverless-journey-validation.json"
    atomic_json(path, record)
    try:
        from benchmark_agents.api import create_app as api_app
        from examples import real_framework_agent

        selected_distribution = {
            "langgraph": "langgraph",
            "openai-agents": "openai-agents",
            "crewai": "crewai",
        }[options.framework]
        record["versions"] = {
            name: version(name)
            for name in (
                "evalsurge",
                "databricks-sdk",
                "locust",
                "httpx",
                "openai",
                "uvicorn",
                selected_distribution,
            )
        }
        record["source_sha256"] = {
            "serverless_sdk_journeys.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "real_framework_agent.py": hashlib.sha256(
                Path(real_framework_agent.__file__).read_bytes()
            ).hexdigest(),
        }
        record["agent_handler_deadline_seconds"] = options.timeout + 5

        key = secrets.token_urlsafe(32)
        values = {
            "EVALSURGE_DEMO_MODEL": options.target_model,
            "MLFLOW_TRACKING_URI": f"sqlite:///{directory}/agent-traces.db",
            "BENCHMARK_API_KEY": key,
            "BENCHMARK_TRACE_ENABLED": "false",
            "CREWAI_DISABLE_TELEMETRY": "true",
        }
        with _owned_demo_environment(values):
            try:
                helper = _create_driver_helper(options, workspace)
                observer = DispatchObserver(helper, "/invoke")
                serving = await _serve(observer)
                servers.append(serving)
                agent_origin = serving[3]
                bindings = {
                    "agent": Agent.http(f"{agent_origin}/invoke", protocol="http-json"),
                    "negative": Agent.http(f"{agent_origin}/not-an-agent"),
                }
                checks = await _exercise_direct(options, bindings, observer)
                record["checks"].extend(checks)
                if all(check["passed"] for check in checks):
                    # JSON is valid YAML. This file contains exact local targets;
                    # the service key remains private runtime state, not a file.
                    config = directory / "loopback-api.yaml"
                    atomic_json(
                        config,
                        {
                            "artifact_dir": str(directory / "api"),
                            "connections": {
                                alias: binding.registration.operator_record()
                                for alias, binding in bindings.items()
                            },
                        },
                    )
                    api = await _serve(api_app(config_path=config))
                    servers.append(api)
                    record["checks"].extend(
                        await asyncio.to_thread(_exercise_api, options, api[3], key, observer)
                    )
                record["passed"] = all(check["passed"] for check in record["checks"])
            finally:
                # Failure paths drain inside this scope too: API first, then agent,
                # and only then restore owned settings/service authentication.
                await _close_servers(servers, record)
    except BaseException as error:
        record["passed"] = False
        record["failure_class"] = type(error).__name__
        raise
    finally:
        try:
            if servers:
                await _close_servers(servers, record)
        finally:
            if helper is not None:
                record["model_transport_evidence"] = dict(helper.state.inference_evidence)
            atomic_json(path, record)
    return record
