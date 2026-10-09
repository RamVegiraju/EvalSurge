"""One real-model preflight plus one measured request for a selected local handler.

No fixture, retry, model/API/token fallback, judging or deployment occurs. Defaults
are a no-network plan. This deliberately small canary is not a capacity test.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import socket
from collections.abc import Sequence
from contextlib import suppress
from importlib.metadata import version
from pathlib import Path
from typing import Any

from examples.real_framework_agent import ModelSelection, create_real_app
from scripts.validation.dispatch_observer import DispatchObserver
from scripts.validation.unified_sdk_journeys import _serve_without_host_exit


async def execute(options: argparse.Namespace) -> dict[str, Any]:
    """Execute the explicitly selected real canary and retain value-free evidence.

    Args:
        options: Consent-gated fixed canary selections and fresh protected storage.

    Returns:
        Lifecycle, actual dispatch/completion counters, package/source identities
        and typed result/report agreement. Prompts/answers remain private artifacts.

    Side Effects:
        Starts one real loopback framework agent and the existing Locust engine;
        owns and closes both. Maximum target attempts are two, with at most four
        model requests for CrewAI and two otherwise. A failed probe skips load.
        Existing failed receipts are never overwritten; native errors are recorded
        by class only. Model timeout is 30 seconds, handler 35, HTTP runner 40.
    """
    from benchmark_agents.storage import atomic_json
    from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference

    directory = options.artifact_dir.resolve()
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Select fresh empty protected storage")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    selected = ModelSelection(options.profile, options.model, options.api, options.workspace_host)
    distributions = ["openai", "databricks-sdk", "locust", "mlflow"]
    distributions.append(
        {"langgraph": "langgraph", "openai-agents": "openai-agents", "crewai": "crewai"}[
            options.framework
        ]
    )
    record: dict[str, Any] = {
        "framework": options.framework,
        "model": options.model,
        "api": options.api,
        "profile": options.profile,
        "evaluation": "off",
        "inference_stubbed": False,
        "bounds": {
            "concurrency": 1,
            "measured": 1,
            "excluded_probe": 1,
            "max_output_tokens": 512,
            "model_timeout_seconds": 30,
            "handler_timeout_seconds": 35,
            "runner_timeout_seconds": 40,
            "max_model_calls": 4 if options.framework == "crewai" else 2,
        },
        "versions": {name: version(name) for name in distributions},
        "sample_sha256": hashlib.sha256(
            Path("examples/real_framework_agent.py").read_bytes()
        ).hexdigest(),
        "passed": False,
    }
    atomic_json(directory / "receipt.json", record)
    # Suppress native/provider exception text on the terminal; phase receipts and
    # protected normal run artifacts retain failed attempts. No secrets are printed.
    logging.disable(logging.CRITICAL)
    os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
    os.environ["OTEL_SDK_DISABLED"] = "true"
    app = create_real_app(options.framework, selected)
    observer = DispatchObserver(app, "/invoke")
    server_task = None
    server = None
    listener = None
    try:
        import uvicorn

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        server = uvicorn.Server(
            uvicorn.Config(observer, log_level="critical", proxy_headers=False, access_log=False)
        )
        server_task = asyncio.create_task(_serve_without_host_exit(server, listener))
        for _ in range(1000):
            if server.started:
                break
            if server_task.done():
                await server_task
                raise RuntimeError("Native sample did not start")
            await asyncio.sleep(0.01)
        if not server.started:
            raise TimeoutError("Native startup exceeded ten seconds")
        origin = f"http://127.0.0.1:{listener.getsockname()[1]}/invoke"
        request = RunCreate(
            target=TargetReference(connection_id="agent"),
            cases=[Case(input={"query": "Can an opened item be refunded?"})],
            load=Load(concurrency=1, duration_seconds=10, max_requests=1, timeout_seconds=40),
        )
        async with EvalSurge.local_async(
            artifact_dir=directory / "benchmark",
            targets={"agent": Agent.http(origin, protocol="http-json")},
        ) as client:
            run = await client.start(request)
            record["run_id"] = str(run.id)
            atomic_json(directory / "receipt.json", record)
            try:
                waited = await run.wait(timeout=150)
            except Exception as error:
                if getattr(error, "report", None) is None:
                    raise
                waited = error.report
            status = await run.status()
            result = await run.result()
            report = await run.report()
            record.update(
                status=result.status,
                phases=result.phases.model_dump(mode="json"),
                preflight=result.preflight.model_dump(mode="json"),
                metrics=result.metrics.model_dump(mode="json") if result.metrics else None,
                typed_retrieval_agrees=(
                    status.id == result.id == report.run.id == waited.run.id == run.id
                    and status.status == result.status == report.run.status == waited.run.status
                    and result.model_dump(mode="json") == report.run.model_dump(mode="json")
                ),
            )
            record["passed"] = bool(
                result.preflight.status == "passed"
                and result.phases.load == "completed"
                and result.metrics is not None
                and result.metrics.requests == 1
                and result.metrics.successful_requests == 1
                and result.metrics.error_rate == 0
                and record["typed_retrieval_agrees"]
            )
        record["sdk_context_closed"] = True
    except Exception as error:  # noqa: BLE001 - retain safe failure class, never raw provider content
        record["failure_type"] = type(error).__name__
    finally:
        if server is not None:
            server.should_exit = True
        if server_task is not None:
            try:
                await asyncio.wait_for(server_task, timeout=45)
                record["agent_lifespan_closed"] = True
            except (Exception, asyncio.CancelledError) as error:  # noqa: BLE001 - cleanup receipt only
                record["agent_lifespan_closed"] = False
                record["cleanup_failure_type"] = type(error).__name__
                server_task.cancel()
                with suppress(Exception, asyncio.CancelledError):
                    await server_task
        if listener is not None:
            listener.close()
        record["model_transport_evidence"] = dict(app.state.inference_evidence)
        record["passed"] = bool(
            record["passed"]
            and record.get("sdk_context_closed")
            and record.get("agent_lifespan_closed")
        )
        atomic_json(directory / "receipt.json", record)
    return record


def main(arguments: Sequence[str] | None = None) -> None:
    """Print bounded plans or execute explicitly consented real canaries."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--framework", required=True, choices=("langgraph", "openai-agents", "crewai")
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--workspace-host", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api", required=True, choices=("mlflow-responses", "openai-responses"))
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--accept-paid-traffic", action="store_true")
    options = parser.parse_args(arguments)
    ModelSelection(options.profile, options.model, options.api, options.workspace_host)
    if not options.live:
        print(
            json.dumps(
                {
                    "live": False,
                    "framework": options.framework,
                    "max_target_attempts": 2,
                    "max_model_attempts": 4 if options.framework == "crewai" else 2,
                    "evaluation": "off",
                }
            )
        )
        return
    if not options.accept_paid_traffic:
        parser.error("--live requires explicit --accept-paid-traffic")
    receipt = asyncio.run(execute(options))
    print(json.dumps(receipt, sort_keys=True))
    raise SystemExit(0 if receipt["passed"] else 1)


if __name__ == "__main__":
    main()
