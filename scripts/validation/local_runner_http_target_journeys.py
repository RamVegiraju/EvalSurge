"""Runner: local machine. Target: owned real LangGraph/OpenAI Agents HTTP helper.

No agent is hosted in a notebook or substituted with fixture inference. The load
case executes the public local_runner_http_target.request() unchanged through
direct SDK or an optional local REST server. Fail-fast is explicitly pre-provider;
active cancellation is a separate bounded run, never a replay of a failed probe.
Dry-run makes no network calls. Live model traffic requires consent and a separately
coordinated lease; the CLI cannot enforce other processes' model-call budgets.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import secrets
import socket
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager, suppress
from importlib.metadata import version
from pathlib import Path
from typing import Any

from examples.real_framework_agent import ModelSelection, create_real_app
from scripts.validation.dispatch_observer import (
    DispatchObserver,
    wait_for_active_dispatch,
    wait_for_active_dispatch_sync,
)
from scripts.validation.hosted_journeys import retrieval_evidence
from scripts.validation.unified_sdk_journeys import _serve_without_host_exit


def parse_options(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Validate exact operator selections and finite traffic before native imports.

    Args:
        arguments: Explicit CLI arguments, or the process command line.

    Returns:
        Fixed five-user/five-measured selections and fresh storage destination.

    Raises:
        SystemExit: Selection/consent is absent or invalid. No profile is inferred.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", required=True, choices=("langgraph", "openai-agents"))
    parser.add_argument("--execution", choices=("direct", "api"), default="direct")
    parser.add_argument("--scenario", choices=("load", "fail-fast", "cancel"), default="load")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--workspace-host", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api", required=True, choices=("mlflow-responses", "openai-responses"))
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--accept-paid-traffic", action="store_true")
    options = parser.parse_args(arguments)
    try:
        ModelSelection(options.profile, options.model, options.api, options.workspace_host)
    except ValueError as error:
        parser.error(str(error))
    if options.live and options.scenario != "fail-fast" and not options.accept_paid_traffic:
        parser.error(
            "Actual model calls require --accept-paid-traffic and a separate traffic lease"
        )
    return options


def benchmark_request(scenario: str) -> Any:
    """Reuse the public sample object; modify only the declared no-inference case.

    Args:
        scenario: load/cancel reuse identical public request; fail-fast adds an
            unsupported field rejected by the real handler before the provider.

    Returns:
        Strict v2 RunCreate with the advertised five-user/five-attempt ceiling.

    Raises:
        ValueError: An unknown scenario was supplied; no arbitrary override exists.
    """
    from examples.journeys.local_runner_http_target import request

    if scenario not in {"load", "fail-fast", "cancel"}:
        raise ValueError("Select a declared local HTTP journey scenario")
    result = request()
    if (
        result.load.concurrency != 5
        or result.load.max_requests != 5
        or result.load.duration_seconds != 10
        or result.load.timeout_seconds != 40
        or result.evaluation.mode != "off"
    ):
        raise ValueError("The public request changed; review and reauthorize its traffic bounds")
    if scenario == "fail-fast":
        from evalsurge import Case

        result.cases = [
            Case(input={"query": "Can an opened item be refunded?", "unsupported": True})
        ]
    return result


def validate_api_environment() -> None:
    """Reject ambient operator overrides instead of changing shared process state.

    The native settings loader gives environment overrides precedence over its
    file. The validation API must use its generated exact loopback binding/key,
    tracing-off policy and owned artifacts, not unrelated ambient registrations.
    Credential values are neither printed nor persisted by this check.
    """
    if any(name.startswith("BENCHMARK_") for name in os.environ):
        raise ValueError("Remove ambient benchmark configuration before the owned local API test")


def plan_record(options: argparse.Namespace) -> dict[str, Any]:
    """Return content-free bounded selections; never claim successful inference."""
    request = benchmark_request(options.scenario)
    return {
        "runner_location": "local machine",
        "target_hosting": "local HTTP agent",
        "execution": options.execution,
        "framework": options.framework,
        "scenario": options.scenario,
        "profile": options.profile,
        "model": options.model,
        "model_api": options.api,
        "inference_stubbed": False,
        "negative_test_only": options.scenario == "fail-fast",
        "evaluation": "off",
        "load": request.load.model_dump(mode="json"),
        "max_target_attempts": request.load.max_requests + 1,
        "max_physical_model_attempts": 0 if options.scenario == "fail-fast" else 6,
        "max_output_tokens_per_call": 512,
        "model_timeout_seconds": 30,
        "handler_timeout_seconds": 35,
        "model_retries": 0,
        "public_request": "examples/journeys/local_runner_http_target.py:request",
        "capacity_claim": False,
        "passed": False,
    }


@asynccontextmanager
async def owned_server(app: Any, receipt: dict[str, Any], label: str) -> AsyncIterator[str]:
    """Own one native loopback socket and lifespan through graceful shutdown.

    Args:
        app: Actual ASGI agent or EvalSurge API, not a transport simulation.
        receipt: Content-free cleanup fields updated even after startup failure.
        label: Distinguishes agent from optional API resource ownership.

    Yields:
        Loopback origin while its actual native lifespan remains running.

    Raises:
        Exception: Startup/execution fails; caller records only the class.

    Side Effects:
        Binds one local socket. Closes the listener after up to 45-second graceful
        drain, never before it. Startup performs no agent inference.
    """
    import uvicorn

    listener = socket.socket()
    task = None
    server = uvicorn.Server(
        uvicorn.Config(app, log_level="critical", proxy_headers=False, access_log=False)
    )
    try:
        listener.bind(("127.0.0.1", 0))
        task = asyncio.create_task(_serve_without_host_exit(server, listener))
        for _ in range(1000):
            if server.started:
                break
            if task.done():
                await task
                raise RuntimeError("Owned loopback server exited during startup")
            await asyncio.sleep(0.01)
        if not server.started:
            raise TimeoutError("Native startup exceeded ten seconds")
        receipt[f"{label}_started"] = True
        yield f"http://127.0.0.1:{listener.getsockname()[1]}"
    finally:
        server.should_exit = True
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=45)
                receipt[f"{label}_lifespan_closed"] = True
            except (Exception, asyncio.CancelledError) as error:  # noqa: BLE001 - safe cleanup receipt
                receipt[f"{label}_lifespan_closed"] = False
                receipt[f"{label}_cleanup_failure_type"] = type(error).__name__
                task.cancel()
                with suppress(Exception, asyncio.CancelledError):
                    await task
        listener.close()
        receipt[f"{label}_listener_closed"] = listener.fileno() == -1


def record_retrieval(
    run: Any, status: Any, result: Any, waited: Any, report: Any
) -> dict[str, Any]:
    """Project native typed terminal/report equality without prompts or answer export."""
    return {
        "run_id": str(run.id),
        "status": result.status,
        "phases": result.phases.model_dump(mode="json"),
        "preflight": result.preflight.status,
        "metrics": result.metrics.model_dump(mode="json") if result.metrics else None,
        "report_total": report.total,
        "report_page_size": len(report.requests),
        **retrieval_evidence(run.id, status, result, waited, report, remote=False),
    }


def record_cancellation(status: Any, counts: dict[str, int], acknowledgment: Any) -> dict[str, Any]:
    """Record observed active measured arrival; no claim of killing provider work."""
    active = status.status == "running" and counts["measured_inflight"] > 0
    return {
        "status_at_cancel": status.status,
        "measured_dispatch_observed_at_cancel": active,
        "measured_receipts_at_cancel": counts["measured_received"],
        "measured_inflight_at_cancel": counts["measured_inflight"],
        "cancellation_ack": acknowledgment.status if acknowledgment else None,
        "dispatch_cutoff_before_cap_established": False,
        "provider_work_termination_established": False,
    }


async def direct_journey(
    options: argparse.Namespace, endpoint: str, observer: DispatchObserver, directory: Path
) -> tuple[dict[str, Any], Any]:
    """Run one direct native-async SDK lifecycle with the sole Locust engine."""
    from benchmark_agents.settings import Settings
    from evalsurge import Agent, EvalSurge

    receipt: dict[str, Any] = {}
    async with EvalSurge.local_async(
        artifact_dir=directory / "benchmark",
        settings=Settings(),
        targets={"agent": Agent.http(endpoint, protocol="http-json")},
    ) as client:
        run = await client.start(benchmark_request(options.scenario))
        if options.scenario == "cancel":
            status, counts = await wait_for_active_dispatch(run, observer, 150)
            ack = await run.cancel() if status.status == "running" else None
            receipt.update(record_cancellation(status, counts, ack))
        try:
            waited = await run.wait(timeout=150)
        except Exception as error:  # noqa: BLE001 - terminal failed/cancelled report remains inspectable
            if getattr(error, "report", None) is None:
                raise
            waited = error.report
        status, result, report = await run.status(), await run.result(), await run.report()
        receipt.update(record_retrieval(run, status, result, waited, report))
    receipt["sdk_context_closed"] = True
    return receipt, report


def remote_journey(
    options: argparse.Namespace, origin: str, key: str, observer: DispatchObserver
) -> tuple[dict[str, Any], Any]:
    """Use the actual typed HTTP SDK in a thread while both owned servers progress.

    Remote context closure does not stop service-owned work; terminal/report parity
    must be established before the caller drains its owned API lifespan.
    """
    from evalsurge import EvalSurge

    receipt: dict[str, Any] = {}
    with EvalSurge.remote(origin, api_key=key, typed=True) as client:
        run = client.start(benchmark_request(options.scenario))
        if options.scenario == "cancel":
            status, counts = wait_for_active_dispatch_sync(run, observer, 150)
            ack = run.cancel() if status.status == "running" else None
            receipt.update(record_cancellation(status, counts, ack))
        try:
            waited = run.wait(timeout=150)
        except Exception as error:  # noqa: BLE001 - native terminal report only, no provider text
            if getattr(error, "report", None) is None:
                raise
            waited = error.report
        status, result, report = run.status(), run.result(), run.report()
        receipt.update(record_retrieval(run, status, result, waited, report))
    receipt["sdk_context_closed"] = True
    return receipt, report


def journey_passed(options: argparse.Namespace, receipt: dict[str, Any]) -> bool:
    """Require actual model evidence for positive cases and zero for the negative."""
    if receipt.get("failure_type") or not receipt.get("report_json_path"):
        return False
    if not receipt.get("retrieval_agrees") or not receipt.get("sdk_context_closed"):
        return False
    if not all(
        receipt.get(f"{label}_{field}")
        for label in ("agent",)
        for field in ("lifespan_closed", "listener_closed")
    ):
        return False
    if options.execution == "api" and not all(
        receipt.get(field)
        for field in (
            "api_lifespan_closed",
            "api_listener_closed",
            "api_auth_rejection_confirmed",
            "report_shell_retrieved",
        )
    ):
        return False
    counts = receipt.get("model_transport_evidence", {})
    metrics = receipt.get("metrics")
    if options.scenario == "fail-fast":
        return bool(
            counts == {"outbound_attempts": 0, "completed_responses": 0}
            and receipt.get("status") == "failed"
            and receipt.get("preflight") == "failed"
            and receipt.get("preflight_code") == "target_http_error"
            and receipt.get("phases", {}).get("load") == "skipped"
            and (metrics is None or metrics["requests"] == 0)
            and receipt.get("target_receipts", {}).get("received") == 1
        )
    dispatches = counts.get("outbound_attempts", 0)
    if not 2 <= dispatches <= 6 or counts.get("completed_responses") != dispatches:
        return False
    if options.scenario == "cancel":
        return bool(
            receipt.get("measured_dispatch_observed_at_cancel")
            and receipt.get("cancellation_ack") == "cancellation_requested"
            and receipt.get("status") == "cancelled"
        )
    return bool(
        dispatches == 6
        and receipt.get("preflight") == "passed"
        and receipt.get("phases", {}).get("load") == "completed"
        and metrics is not None
        and metrics["requests"] == metrics["successful_requests"] == 5
        and metrics["error_rate"] == 0
        and receipt.get("report_total") == 5
        and receipt.get("report_page_size") == 5
    )


async def execute(options: argparse.Namespace) -> dict[str, Any]:
    """Exercise one consented real HTTP journey and retain protected failed evidence.

    Args:
        options: Exact profile/model/API, declared scenario/mode and fresh directory.

    Returns:
        Safe receipt with physical transport counters, terminal/report equality and
        cleanup. Full typed report and normal journals stay in protected files.

    Raises:
        ValueError: Live consent or a fresh nonsymlink destination is absent.

    Side Effects:
        Owns real agent/native client lifespans and one normal Locust worker. API
        mode additionally owns one loopback REST server and its storage. Load or
        cancel sends at most six physical model calls; fail-fast sends zero. Every
        model request has a 512-output-token cap/no retries/no tools. No evaluation,
        deployment, notebook execution or model/API fallback occurs.
    """
    if not options.live or (options.scenario != "fail-fast" and not options.accept_paid_traffic):
        raise ValueError("Live/paid consent is required before resource creation")
    from benchmark_agents.storage import atomic_json

    directory = options.artifact_dir.absolute()
    if directory.is_symlink() or (directory.exists() and any(directory.iterdir())):
        raise ValueError("Select fresh empty protected evidence storage")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    receipt = plan_record(options)
    distributions = ["openai", "databricks-sdk", "locust", "mlflow", options.framework]
    receipt["versions"] = {name: version(name) for name in distributions}
    receipt["sample_sha256"] = hashlib.sha256(
        Path("examples/real_framework_agent.py").read_bytes()
    ).hexdigest()
    receipt["public_request_sha256"] = hashlib.sha256(
        Path("examples/journeys/local_runner_http_target.py").read_bytes()
    ).hexdigest()
    receipt_path = directory / "receipt.json"
    atomic_json(receipt_path, receipt)
    logging.disable(logging.CRITICAL)
    selected = ModelSelection(options.profile, options.model, options.api, options.workspace_host)
    app = create_real_app(options.framework, selected)
    observer = DispatchObserver(app, "/invoke")
    try:
        async with owned_server(observer, receipt, "agent") as agent_origin:
            endpoint = f"{agent_origin}/invoke"
            if options.execution == "direct":
                outcome, report = await direct_journey(options, endpoint, observer, directory)
            else:
                import httpx

                from benchmark_agents.api import create_app

                validate_api_environment()
                key = secrets.token_urlsafe(32)
                config = directory / "operator.yaml"
                # JSON is a strict YAML subset; atomic_json creates mode-0600 files.
                # This exact loopback binding/key is operator owned, never RunCreate.
                atomic_json(
                    config,
                    {
                        "artifact_dir": str(directory / "benchmark"),
                        "api_key": key,
                        "connections": {
                            "agent": {"kind": "http", "url": endpoint, "protocols": ["http-json"]}
                        },
                        "tracing": {"enabled": False},
                    },
                )
                api = create_app(config_path=config)
                async with owned_server(api, receipt, "api") as origin:
                    async with httpx.AsyncClient(trust_env=False, timeout=5) as http:
                        rejected = await http.get(f"{origin}/v2/capabilities")
                        receipt["api_auth_rejection_confirmed"] = rejected.status_code == 401
                        shell = await http.get(f"{origin}/reports/")
                        receipt["report_shell_retrieved"] = shell.status_code == 200
                    if not receipt["api_auth_rejection_confirmed"]:
                        raise RuntimeError("Local REST service authentication was not enforced")
                    outcome, report = await asyncio.to_thread(
                        remote_journey, options, origin, key, observer
                    )
            receipt.update(outcome)
            report_path = directory / "typed-report.json"
            atomic_json(report_path, report.model_dump(mode="json"))
            receipt["report_json_path"] = str(report_path)
            receipt["target_receipts"] = observer.snapshot(receipt["run_id"])
    except Exception as error:  # noqa: BLE001 - safe failure class; preserve native protected journals
        receipt["failure_type"] = type(error).__name__
    finally:
        receipt["model_transport_evidence"] = dict(app.state.inference_evidence)
        receipt["passed"] = journey_passed(options, receipt)
        atomic_json(receipt_path, receipt)
    return receipt


def main(arguments: Sequence[str] | None = None) -> int:
    """Print a nonnetworked plan or safe live receipt; never print provider exceptions."""
    options = parse_options(arguments)
    if not options.live:
        print(json.dumps(plan_record(options), sort_keys=True))
        return 0
    receipt = asyncio.run(execute(options))
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
