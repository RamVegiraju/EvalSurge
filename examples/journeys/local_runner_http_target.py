"""Runner: local Python/laptop. Target: a separately hosted real HTTP agent.

EvalSurge generates load; it never imports or hosts the customer's agent. Start
the agent separately and select its exact reachable endpoint. The default is the
minimal nonstreaming http-json contract. This file does not run on a notebook.
"""

import argparse

from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference


def request() -> RunCreate:
    """Build a five-attempt load-only smoke; construction makes no network calls."""
    return RunCreate(
        name="local-runner-http-target-smoke",
        target=TargetReference(connection_id="agent"),
        cases=[Case(input={"query": "Can an opened item be refunded?"})],
        load=Load(concurrency=5, duration_seconds=10, max_requests=5, timeout_seconds=40),
    )


def main() -> None:
    """Run from this machine against the selected customer-owned HTTP endpoint.

    Side Effects:
        Owns one local Locust worker and protected artifacts. Up to five measured
        invocations plus one excluded probe may incur actual model/tool costs.
        Evaluation is off; no planner or judge calls. This is a functional smoke,
        not sustainable-capacity evidence or a model-call/token/spend quota.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Exact authorized endpoint of the existing real agent")
    parser.add_argument(
        "--protocol",
        choices=("http-json", "openai-chat", "mlflow-agent-server"),
        default="http-json",
    )
    parser.add_argument("--allow-paid-inference", action="store_true")
    args = parser.parse_args()
    if not args.allow_paid_inference:
        parser.error("Review six possible agent invocations; pass --allow-paid-inference.")
    with EvalSurge(
        artifact_dir="artifacts/local-runner-http-target",
        targets={"agent": Agent.http(args.url, protocol=args.protocol)},
    ) as client:
        report = client.start(request()).wait(timeout=300)
        print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
