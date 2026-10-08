"""Benchmark an already deployed real Databricks App using an explicit OAuth profile."""

import argparse

from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference


def request() -> RunCreate:
    """Build the same v2 request used for direct HTTP; it contains no profile."""
    return RunCreate(
        name="direct-app-baseline",
        target=TargetReference(connection_id="agent"),
        cases=[Case(input={"query": "Give a short greeting."})],
        load=Load(concurrency=2, duration_seconds=10, max_requests=10, timeout_seconds=60),
    )


def main() -> None:
    """Resolve the user-selected App and run only after bounded-traffic consent.

    Side effects:
        Uses the selected OAuth identity for discovery and up to eleven actual
        App invocations including the excluded probe. Each can perform multiple
        model/tool calls; this is not a model/token/spend quota. Retains protected
        local artifacts. Does not deploy or provision cloud resources.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app_name", help="Name of your authorized, deployed App")
    parser.add_argument("--profile", required=True, help="Explicit selected OAuth profile")
    parser.add_argument("--allow-paid-inference", action="store_true")
    args = parser.parse_args()
    if not args.allow_paid_inference:
        parser.error("Review the traffic/tool costs, then pass --allow-paid-inference.")
    with EvalSurge(
        artifact_dir="artifacts/direct-app",
        targets={"agent": Agent.databricks_app(args.app_name, profile=args.profile)},
    ) as client:
        report = client.start(request()).wait(timeout=300)
        print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
