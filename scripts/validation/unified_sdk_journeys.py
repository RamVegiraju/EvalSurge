"""Consent-gated direct SDK validation with real frameworks/models, never fixtures.

Dry-run validates selections and prints only traffic bounds. Live HTTP mode starts
the existing native LangGraph/OpenAI Agents demo with live=True; App mode targets
an existing deployment. Neither deploys resources or configures notebook compute.
Evaluation is off. Cancellation is a separately opted-in second bounded run.
"""

import argparse
import asyncio
import json
import math
import os
import re
import socket
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .dispatch_observer import DispatchObserver, wait_for_active_dispatch


class _LiveConfigurationError(ValueError):
    """Fixed operator guidance safe to print before protected artifacts exist."""


async def _serve_without_host_exit(server: Any, listener: socket.socket) -> None:
    """Contain native Uvicorn process exits inside an owned validation task.

    Args:
        server: Actual Uvicorn server; no transport or framework is substituted.
        listener: Caller-owned loopback socket; the caller closes it on failure.

    Raises:
        RuntimeError: Uvicorn requests process exit, including lifespan startup
            failure. Fixed guidance never exposes a framework/provider exception.

    Side Effects:
        Runs the server normally. Catch SystemExit before it escapes the task and
        terminates the notebook host; cancellation and other failures propagate.
        This changes harness ownership only, not invocation or load measurements.
    """
    try:
        await server.serve(sockets=[listener])
    except SystemExit:
        raise RuntimeError("Owned loopback server startup or execution failed") from None


def parse_options(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Validate operator selections without reading credentials or sending traffic.

    Args:
        arguments: CLI arguments; None reads the process argument vector.

    Returns:
        Bounded selections. Profiles/model/App identifiers are never auto-selected.

    Raises:
        SystemExit: A selection or finite traffic bound is missing/invalid.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journey", required=True, choices=("http", "app"))
    parser.add_argument("--framework", required=True, choices=("langgraph", "openai-agents"))
    parser.add_argument("--profile", required=True)
    parser.add_argument("--target-model", help="Explicit serving endpoint for the live HTTP demo.")
    parser.add_argument("--app-name", help="Existing operator-authorized App; never deployed here.")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--max-requests", type=int, default=5)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--exercise-cancel", action="store_true")
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--accept-paid-traffic", action="store_true")
    options = parser.parse_args(arguments)
    if not options.profile.strip() or len(options.profile) > 512:
        parser.error("--profile must name one explicitly selected profile")
    if options.journey == "http" and (not options.target_model or not options.target_model.strip()):
        parser.error("HTTP validation requires an explicitly selected --target-model")
    if options.journey == "app" and (
        not options.app_name or not re.fullmatch(r"[a-z][a-z0-9-]{0,29}", options.app_name)
    ):
        parser.error("App validation requires a valid existing --app-name")
    if not 1 <= options.concurrency <= 5 or not 1 <= options.max_requests <= 20:
        parser.error("--concurrency must be 1..5 and --max-requests 1..20")
    for name, maximum in (("duration", 180), ("timeout", 60)):
        if (
            not math.isfinite(getattr(options, name))
            or not 0.1 <= getattr(options, name) <= maximum
        ):
            parser.error(f"--{name} must be finite, between 0.1 and {maximum} seconds")
    if options.live and (not options.accept_paid_traffic or options.artifact_dir is None):
        parser.error("--live requires --accept-paid-traffic and a dedicated --artifact-dir")
    return options


def budget_record(options: argparse.Namespace) -> dict[str, Any]:
    """Return content-free bounds, not model/tool spend or sustainable capacity.

    Args:
        options: Already validated selections.

    Returns:
        Maximum top-level target attempts, including excluded preflights. The HTTP
        negative probe deliberately reaches an unknown route, not a model.
    """
    runs = 2 if options.exercise_cancel else 1
    negative_probes = int(options.journey == "http")
    return {
        "live": options.live,
        "journey": options.journey,
        "framework": options.framework,
        "concurrency": options.concurrency,
        "dispatch_seconds_per_run": options.duration,
        "per_attempt_timeout_seconds": options.timeout,
        "normal_run_count": runs,
        "max_measured_invocations": runs * options.max_requests,
        "max_model_bearing_probe_invocations": runs,
        "max_negative_route_probes_without_model_dispatch": negative_probes,
        "max_total_target_attempts": runs * (options.max_requests + 1) + negative_probes,
        "exercise_cancel": options.exercise_cancel,
        "evaluation_mode": "off",
        "inference_stubbed": False,
        "model_calls_per_agent_invocation_bounded": False,
        "monetary_quota_enforced": False,
        "sustainable_capacity_established": False,
    }


async def _report_after_wait(run: Any, timeout: float) -> Any:
    """Retain failed phase reports without printing private provider exceptions.

    Args:
        run: Unified native-async run handle.
        timeout: Positive whole-lifecycle waiting bound in seconds.

    Returns:
        Typed Report, including a terminal failure carried by its exception.

    Raises:
        Exception: Non-report-bearing SDK, transport, or timeout failure.
    """
    try:
        return await run.wait(timeout=timeout)
    except Exception as error:  # noqa: BLE001 - preserve safe failure reports, not raw messages
        if getattr(error, "report", None) is None:
            raise
        return error.report


def _content_free_report(report: Any) -> dict[str, Any]:
    """Reduce typed evidence to lifecycle and metrics, omitting workload/rationales."""
    return {
        "run_id": str(report.run.id),
        "status": report.run.status,
        "phases": report.run.phases.model_dump(mode="json"),
        "summary": report.run.summary.model_dump(mode="json"),
        "metrics": report.run.metrics.model_dump(mode="json") if report.run.metrics else None,
    }


async def _close_framework_server(
    server: Any,
    server_task: asyncio.Task[None] | None,
    listener: socket.socket | None,
    record: dict[str, Any],
) -> None:
    """Stop owned HTTP serving and close its socket even when shutdown fails.

    Args:
        server: Owned Uvicorn server, or None for App validation.
        server_task: Its serving task, never a target inference task.
        listener: Harness-owned loopback socket, if HTTP serving was started.
        record: Validation evidence updated with content-free cleanup status.

    Raises:
        BaseException: Shutdown fails or is cancelled; never records a pass.

    Side Effects:
        Requests graceful shutdown with a 60-second bound and always closes the
        listener. Caller must persist the record in a separate finally block.
    """
    try:
        if server is not None:
            server.should_exit = True
        if server_task is not None:
            await asyncio.wait_for(server_task, timeout=60)
        record["framework_server_closed"] = True
    except BaseException:
        record["passed"] = False
        record["framework_server_closed"] = False
        record["cleanup_error"] = "framework_server_shutdown_failed"
        raise
    finally:
        if listener is not None:
            listener.close()


def _validate_http_profile_environment() -> None:
    """Reject ambient SDK routing/credentials before live HTTP agent startup.

    Raises:
        ValueError: The selected profile could be overridden by ambient or
            task-local SDK configuration. The diagnostic never exports values.

    Reuses the target resolver's installed SDK metadata checks. No authentication,
    profile-file read or network call occurs, and no credentials are cleared.
    """
    from benchmark_agents.target_resolver import TargetResolutionError, _reject_profile_overrides

    try:
        _reject_profile_overrides()
    except TargetResolutionError:
        raise _LiveConfigurationError(
            "Live HTTP validation profile conflicts with ambient SDK configuration; "
            "use an isolated operator environment"
        ) from None


async def execute(options: argparse.Namespace) -> dict[str, Any]:
    """Exercise real native frameworks or an existing App through the direct SDK.

    Args:
        options: Live-consented selections with dedicated, empty protected storage.

    Returns:
        Content-free validation record. A finished run is not a quality verdict.
        App framework identity requires separate deployed-source verification.

    Raises:
        ValueError: Live consent/storage/profile isolation is missing.
        Exception: Authentication, startup, lifecycle or cleanup fails; no fallback.

    Side Effects:
        Live HTTP mode sets this harness process's provider/tracking environment
        before starting the existing demo. Owns one local Uvicorn agent and the
        normal SDK coordinator/Locust; App mode starts no HTTP server. Traffic can
        execute tools/incur spend. Protected artifacts persist; no resources are
        deployed/deleted and no profile, model or retry fallback is introduced.
    """
    if not options.live or not options.accept_paid_traffic or options.artifact_dir is None:
        raise _LiveConfigurationError(
            "Live validation requires explicit consent and protected storage"
        )
    if options.journey == "http":
        _validate_http_profile_environment()
    directory = options.artifact_dir.resolve()
    if directory.exists() and any(directory.iterdir()):
        raise _LiveConfigurationError(
            "Select new or empty storage; previous evidence is never overwritten"
        )
    from benchmark_agents.storage import atomic_json
    from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference

    directory.mkdir(parents=True, exist_ok=True)
    record = {**budget_record(options), "checks": [], "passed": False}
    atomic_json(directory / "journey-validation.json", record)
    server = None
    server_task = None
    listener = None
    observer = None
    try:
        if options.journey == "http":
            import uvicorn

            from examples.framework_agent import create_app

            os.environ.update(
                DATABRICKS_CONFIG_PROFILE=options.profile,
                EVALSURGE_DEMO_MODEL=options.target_model,
                MLFLOW_TRACKING_URI=f"sqlite:///{directory}/agent-traces.db",
            )
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            observer = DispatchObserver(create_app(live=True), f"/{options.framework}/chat")
            server = uvicorn.Server(
                uvicorn.Config(observer, log_level="warning", proxy_headers=False)
            )
            server_task = asyncio.create_task(_serve_without_host_exit(server, listener))
            for _ in range(1000):
                if server.started:
                    break
                if server_task.done():
                    await server_task
                    raise RuntimeError("Live framework server did not start")
                await asyncio.sleep(0.01)
            if not server.started:
                raise TimeoutError("Live framework startup exceeded ten seconds")
            origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
            bindings = {
                "agent": Agent.http(f"{origin}/{options.framework}/chat"),
                "negative_route": Agent.http(f"{origin}/not-an-agent"),
            }
        else:
            bindings = {"agent": Agent.databricks_app(options.app_name, profile=options.profile)}
        request = RunCreate(
            target=TargetReference(connection_id="agent"),
            cases=[Case(input={"query": "Can an opened item be refunded?"})],
            load=Load(
                concurrency=options.concurrency,
                duration_seconds=options.duration,
                max_requests=options.max_requests,
                timeout_seconds=options.timeout,
            ),
        )
        wait_bound = options.duration + 2 * options.timeout + 120
        async with EvalSurge.local_async(artifact_dir=directory, targets=bindings) as client:
            run = await client.start(request)
            report = await _report_after_wait(run, wait_bound)
            record["checks"].append({"check": "normal_run", **_content_free_report(report)})
            status = await run.status()
            result = await run.result()
            retrieved = await run.report()
            record["typed_retrieval_agrees"] = status.id == result.id == retrieved.run.id == run.id
            metrics = result.metrics
            succeeded = (
                result.preflight.status == "passed"
                and result.phases.load == "completed"
                and metrics is not None
                and metrics.successful_requests > 0
                and metrics.error_rate == 0
            )
            # A failed real run stops this harness; never continue to spend more.
            if succeeded and options.journey == "http":
                bad_request = request.model_copy(
                    update={"target": TargetReference(connection_id="negative_route")}, deep=True
                )
                failed = await client.start(bad_request)
                failed_report = await _report_after_wait(failed, wait_bound)
                fail_fast = (
                    failed_report.run.preflight.status == "failed"
                    and failed_report.run.phases.load == "skipped"
                    and (
                        failed_report.run.metrics is None or failed_report.run.metrics.requests == 0
                    )
                )
                record["checks"].append(
                    {
                        "check": "pre_provider_fail_fast",
                        "passed": fail_fast,
                        **_content_free_report(failed_report),
                    }
                )
                succeeded = succeeded and fail_fast
            if options.exercise_cancel and succeeded:
                cancelling = await client.start(request)
                state, counts = await wait_for_active_dispatch(cancelling, observer, wait_bound)
                measured_observed = state.status == "running" and counts["measured_inflight"] > 0
                acknowledgment = await cancelling.cancel() if state.status == "running" else None
                cancelled_report = await _report_after_wait(cancelling, wait_bound)
                exercised = measured_observed and cancelled_report.run.status == "cancelled"
                record["checks"].append(
                    {
                        "check": "cancellation",
                        "requested": acknowledgment.status if acknowledgment else "not_requested",
                        "measured_dispatch_observed_at_cancel": measured_observed,
                        "measured_inflight_at_cancel": counts["measured_inflight"],
                        "measured_receipts_at_cancel": counts["measured_received"],
                        "receipt_observation_available": observer is not None,
                        "dispatch_cancellation_exercised": exercised,
                        **_content_free_report(cancelled_report),
                    }
                )
                # Natural completion is not proof of active-dispatch cancellation.
                succeeded = succeeded and exercised
            record["passed"] = succeeded and record["typed_retrieval_agrees"]
        record["sdk_context_closed"] = True
        return record
    finally:
        try:
            await _close_framework_server(server, server_task, listener, record)
        finally:
            atomic_json(directory / "journey-validation.json", record)


def main(arguments: Sequence[str] | None = None) -> int:
    """Print only bounds/results; dry-run never imports a framework or SDK backend."""
    options = parse_options(arguments)
    if not options.live:
        print(json.dumps(budget_record(options), indent=2))
        return 0
    try:
        record = asyncio.run(execute(options))
    except _LiveConfigurationError as error:
        print(str(error))
        return 2
    except Exception:  # noqa: BLE001 - fixed message, never credentials/provider exception text
        print("Live journey failed; inspect protected artifacts. No fixture fallback occurred.")
        return 1
    print(json.dumps(record, indent=2))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
