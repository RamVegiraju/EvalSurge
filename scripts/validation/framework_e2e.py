"""Bounded full API/Locust/framework/trace/report validation, optionally with real Databricks LLMs."""

import argparse
import asyncio
import json
import os
import socket
from pathlib import Path
from typing import Any

import httpx
import uvicorn

from benchmark_agents.api import create_app as create_api
from benchmark_agents.providers import DEFAULT_FM_ENDPOINT
from benchmark_agents.storage import atomic_json
from examples.framework_agent import create_app as create_agent

TERMINAL = {"completed", "completed_with_gaps", "failed", "interrupted", "cancelled"}


def configure_live_models(
    profile: str | None,
    model: str,
    planner_model: str | None = None,
    judge_model: str | None = None,
) -> None:
    """Configure explicit model roles for a paid local integration smoke test.

    Args:
        profile: Exact profile previously confirmed by the operator.
        model: Target-agent endpoint, also the default for planning and judging.
        planner_model: Explicit planner endpoint override, never a runtime fallback.
        judge_model: Explicit catalog-judge endpoint override, never a runtime fallback.

    Raises:
        ValueError: No confirmed profile was supplied.

    This mutates process-owned environment settings before application startup.
    It performs no inference, profile discovery, or automatic capability negotiation.
    """
    if not profile:
        raise ValueError("--live requires the explicitly confirmed --profile")
    os.environ.update(
        DATABRICKS_CONFIG_PROFILE=profile,
        BENCHMARK_PLANNER_MODEL=planner_model or model,
        BENCHMARK_JUDGE_MODEL=judge_model or model,
        BENCHMARK_LLM_PROVIDER="databricks",
    )


async def validate(
    live: bool,
    profile: str | None,
    model: str,
    directory: Path,
    serve: bool = False,
    agent_port: int = 9001,
    api_port: int = 9002,
    frameworks: tuple[str, ...] = ("langgraph", "openai-agents"),
    planner_model: str | None = None,
    judge_model: str | None = None,
) -> list[dict[str, Any]]:
    """Exercise both real frameworks through the complete public API and Locust path.

    Live mode requires an explicitly chosen profile. It sends one inference preflight
    plus two measured synthetic requests per selected framework at concurrency two,
    one planner call per framework, one readiness assessment on the captured probe
    per selected criterion, and at most one measured capture per catalog scorer.
    These are logical assessment counts, not a dollar or provider-attempt quota.
    Model calls have no provider
    retries in the demos; planning/judging use their documented bounded retries.
    All traces and reports remain in the selected local artifact directory.
    Optional planner/judge overrides keep role capabilities explicit; they do not
    retry a rejected request with another model or change the hosted-target settings.
    """
    directory.mkdir(parents=True, exist_ok=True)
    if live:
        configure_live_models(profile, model, planner_model, judge_model)
    elif planner_model or judge_model:
        raise ValueError("Planner and judge model overrides require --live")
    os.environ["EVALSURGE_DEMO_MODEL"] = model
    os.environ["MLFLOW_TRACKING_URI"] = f"sqlite:///{directory.resolve()}/mlflow.db"
    os.environ.pop("MLFLOW_EXPERIMENT_ID", None)
    os.environ["BENCHMARK_TRACE_ENABLED"] = "true"
    servers, sockets, running = [], [], []
    summaries = []
    try:
        for app, port in [(create_agent(live), agent_port), (create_api(directory), api_port)]:
            connection = socket.socket()
            connection.bind(("127.0.0.1", port))
            sockets.append(connection)
            server = uvicorn.Server(uvicorn.Config(app, log_level="warning", proxy_headers=False))
            servers.append(server)
            running.append(asyncio.create_task(server.serve(sockets=[connection])))
            for _ in range(500):
                if server.started:
                    break
                if running[-1].done():
                    await running[-1]
                    raise RuntimeError("Local validation server failed to start")
                await asyncio.sleep(0.01)
            if not server.started:
                raise TimeoutError("Local validation server startup exceeded five seconds")
        agent_url = f"http://127.0.0.1:{sockets[0].getsockname()[1]}"
        api_url = f"http://127.0.0.1:{sockets[1].getsockname()[1]}"
        headers = (
            {"X-API-Key": os.environ["BENCHMARK_API_KEY"]} if os.getenv("BENCHMARK_API_KEY") else {}
        )
        async with httpx.AsyncClient(timeout=180, headers=headers, trust_env=False) as client:
            for framework in frameworks:
                disclosure = (await client.get(f"{agent_url}/manifest/{framework}")).json()
                os.environ["BENCHMARK_TRACE_EXPERIMENT_IDS"] = json.dumps(
                    [disclosure["trace_experiment_id"]]
                )
                evaluation = {
                    "description": "Answer refund questions relevantly and accurately using the supplied reference policy.",
                    "agent_manifest": disclosure["agent_manifest"],
                    "samples": [
                        {
                            "inputs": {"query": "Can I refund an opened item?"},
                            "expectations": {
                                "expected_response": "Opened items cannot be refunded."
                            },
                        }
                    ],
                    "max_scored_requests": 1,
                    "registered_scorers": [],
                    **({} if live else {"scorers": []}),
                }
                planned = await client.post(f"{api_url}/v1/evaluation-plans", json=evaluation)
                planned.raise_for_status()
                plan = planned.json()
                if live and not any(item["status"] == "ready" for item in plan["recommendations"]):
                    raise AssertionError("Live planner provided no executable quality criteria")
                body = {
                    "target": {"url": f"{agent_url}/{framework}/chat", "framework": framework},
                    "evaluation": evaluation,
                    "plan_id": plan["id"],
                    "load": {
                        "concurrency": 2,
                        "max_requests": 2,
                        "duration_seconds": 60 if live else 3,
                        "timeout_seconds": 60 if live else 10,
                    },
                }
                response = await client.post(
                    f"{api_url}/v1/runs",
                    json=body,
                    headers={"Idempotency-Key": f"{framework}-{plan['id']}"},
                )
                response.raise_for_status()
                run_url = api_url + response.json()["url"]
                for _ in range(3000):
                    current = await client.get(run_url)
                    current.raise_for_status()
                    run = current.json()
                    if run["status"] in TERMINAL:
                        break
                    await asyncio.sleep(0.1)
                if run["status"] not in {"completed", "completed_with_gaps"}:
                    raise AssertionError(f"Unexpected run outcome: {run}")
                if run["preflight"]["status"] != "passed":
                    raise AssertionError(f"Framework preflight failed: {run['preflight']}")
                if run["metrics"]["successful_requests"] != 2:
                    raise AssertionError(f"Framework load failed: {run}")
                if live and (
                    not run["evaluation"].get("results")
                    or any(
                        result["status"] != "completed" for result in run["evaluation"]["results"]
                    )
                ):
                    raise AssertionError(f"Live judge assessment failed: {run['evaluation']}")
                report_response = await client.get(run_url + "/report")
                report_response.raise_for_status()
                report = report_response.json()
                if report["profiling"]["coverage"] != 1:
                    raise AssertionError(f"Incomplete trace correlation: {report['profiling']}")
                for request_profile in report["requests"]:
                    categories = {span["category"] for span in request_profile["spans"]}
                    if not {"tool", "model", "memory"} <= categories:
                        raise AssertionError(f"Missing framework span types: {request_profile}")
                summary = {
                    "framework": framework,
                    "id": run["id"],
                    "mode": "live-databricks" if live else "provider-fixture",
                    "model": model if live else "fixture",
                    "planner_model": plan["planner_model"],
                    "judge_model": plan["judge_model"],
                    "preflight": run["preflight"],
                    "metrics": run["metrics"],
                    "evaluation": run["evaluation"],
                    "profiling": report["profiling"],
                    "span_count": sum(len(request["spans"]) for request in report["requests"]),
                    "report_url": f"{api_url}/reports/?run={run['id']}",
                }
                summaries.append(summary)
                atomic_json(directory / f"{framework}-report.json", report)
                print(json.dumps(summary, indent=2), flush=True)
            atomic_json(directory / "validation.json", summaries)
            if serve:
                print("Reports remain available until Ctrl-C.", flush=True)
                while not any(server.should_exit for server in servers):
                    await asyncio.sleep(0.5)
    finally:
        for server in servers:
            server.should_exit = True
        await asyncio.gather(*running, return_exceptions=True)
        for connection in sockets:
            connection.close()
    return summaries


def main() -> None:
    """Parse explicit live-test consent and resource locations; no profile is auto-selected."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Opt in to bounded paid Databricks calls"
    )
    parser.add_argument("--profile", help="Exact workspace profile confirmed by the operator")
    parser.add_argument("--model", default=DEFAULT_FM_ENDPOINT)
    parser.add_argument("--planner-model", help="Explicit planner endpoint; defaults to --model")
    parser.add_argument(
        "--judge-model", help="Explicit catalog judge endpoint; defaults to --model"
    )
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/framework-e2e"))
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--agent-port", type=int, default=9001)
    parser.add_argument("--api-port", type=int, default=9002)
    parser.add_argument(
        "--framework",
        action="append",
        choices=("langgraph", "openai-agents"),
        help="Limit validation to selected frameworks; defaults to both",
    )
    options = parser.parse_args()
    asyncio.run(
        validate(
            options.live,
            options.profile,
            options.model,
            options.artifact_dir,
            options.serve,
            options.agent_port,
            options.api_port,
            tuple(dict.fromkeys(options.framework or ("langgraph", "openai-agents"))),
            options.planner_model,
            options.judge_model,
        )
    )


if __name__ == "__main__":
    main()
