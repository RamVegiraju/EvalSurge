"""Run a small, explicitly approved benchmark against an existing real HTTP agent."""

import argparse

from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference


def request() -> RunCreate:
    """Build ten measured attempts at most; no authentication or inference occurs."""
    return RunCreate(
        name="direct-http-baseline",
        target=TargetReference(connection_id="agent"),
        cases=[Case(input={"query": "Give a short greeting."})],
        load=Load(concurrency=2, duration_seconds=10, max_requests=10, timeout_seconds=60),
    )


def main() -> None:
    """Benchmark the selected target only after paid-inference consent.

    Side effects:
        Starts one local worker and retains protected artifacts. The selected
        agent must use an actual LLM; ten measured agent invocations plus one
        excluded readiness probe can incur multiple model/tool calls and costs.
        These are invocation bounds, not model/token/spend quotas. No target retries.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Exact authorized endpoint of your real agent")
    parser.add_argument(
        "--protocol",
        choices=("openai-chat", "mlflow-agent-server", "http-json"),
        default="openai-chat",
    )
    parser.add_argument("--allow-paid-inference", action="store_true")
    args = parser.parse_args()
    if not args.allow_paid_inference:
        parser.error("Review the traffic/tool costs, then pass --allow-paid-inference.")
    with EvalSurge(
        artifact_dir="artifacts/direct-http",
        targets={"agent": Agent.http(args.url, protocol=args.protocol)},
    ) as client:
        report = client.start(request()).wait(timeout=300)
        print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
