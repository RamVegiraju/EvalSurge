"""Runner: local Python/laptop. Target: an already deployed Databricks App agent.

Only EvalSurge/Locust runs on the caller's machine. The real agent and its model
calls remain in the selected App. OAuth profile configuration is operator-owned
and never part of the benchmark request. This script provisions no resources.
"""

import argparse

from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference


def request() -> RunCreate:
    """Build the same five-attempt workload used by the local HTTP runner sample."""
    return RunCreate(
        name="local-runner-databricks-app-target-smoke",
        target=TargetReference(connection_id="agent"),
        cases=[Case(input={"query": "Can an opened item be refunded?"})],
        load=Load(concurrency=5, duration_seconds=10, max_requests=5, timeout_seconds=40),
    )


def main() -> None:
    """Resolve one explicitly selected App and generate bounded load locally.

    Side Effects:
        Uses the selected refreshable OAuth identity and owns local artifacts and
        one Locust worker. Up to six App invocations include the excluded probe;
        each can incur multiple model/tool calls. No deployment, token copying,
        model fallback, planning or judging. Completion is not a quality verdict.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app_name", help="Exact name of your authorized deployed agent App")
    parser.add_argument("--profile", required=True, help="Explicit selected OAuth profile")
    parser.add_argument("--allow-paid-inference", action="store_true")
    args = parser.parse_args()
    if not args.allow_paid_inference:
        parser.error("Review six possible App invocations; pass --allow-paid-inference.")
    with EvalSurge(
        artifact_dir="artifacts/local-runner-databricks-app-target",
        targets={"agent": Agent.databricks_app(args.app_name, profile=args.profile)},
    ) as client:
        report = client.start(request()).wait(timeout=300)
        print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
