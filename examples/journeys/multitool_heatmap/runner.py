"""Local traffic generator → separately hosted real multi-tool HTTP agent.

This module constructs only the public request and binds operator trace scope;
it imports no agent code and never creates or flushes a tracing destination.
"""

import argparse

from benchmark_agents.settings import Settings, TraceSettings
from evalsurge import (
    Agent,
    Case,
    EvalSurge,
    Load,
    RunCreate,
    RunFailed,
    TargetReference,
    format_summary,
)


def request() -> RunCreate:
    """Return four measured attempts plus one excluded probe; no calls at construction."""
    return RunCreate(
        name="local-runner-multitool-heatmap-smoke",
        target=TargetReference(connection_id="agent"),
        cases=[
            Case(
                input={
                    "query": "Can I return order DEMO-42, and what refund will I receive?",
                    "order_id": "DEMO-42",
                    "scenario": scenario,
                },
            )
            for scenario in ("delayed", "normal")
        ],
        load=Load(concurrency=5, duration_seconds=10, max_requests=4, timeout_seconds=40),
    )


def main() -> None:
    """Run one bounded smoke using the exact endpoint and operator trace experiment.

    Side Effects:
        At most five agent invocations: one excluded probe and four measured.
        Locust traffic originates locally; trace reads occur outside dispatch.
        Protected local reports are written. No planner, judge or target deployment.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Exact authorized agent /invoke endpoint")
    parser.add_argument("--tracking-uri", required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--artifact-dir", required=True, help="Private output directory")
    parser.add_argument("--allow-paid-inference", action="store_true")
    args = parser.parse_args()
    if not args.allow_paid_inference:
        parser.error("Review five possible real model calls; pass --allow-paid-inference.")
    failure: RunFailed | None = None
    with EvalSurge(
        artifact_dir=args.artifact_dir,
        targets={"agent": Agent.http(args.url, protocol="http-json")},
        settings=Settings(
            tracking_uri=args.tracking_uri,
            tracing=TraceSettings(enabled=True, experiment_ids=(args.experiment_id,), max_traces=4),
        ),
    ) as client:
        try:
            report = client.start(request()).wait(timeout=300)
        except RunFailed as error:
            # Failed readiness is retained and viewable, never replaced by another
            # probe/model call. Preserve the failure exit after releasing storage.
            failure = error
            report = error.report
        print(format_summary(report))
    # The direct runner has released its exclusive artifact-directory ownership.
    # This is a link for the optional existing viewer, not a newly started server.
    print(f"Run ID: {report.run.id}")
    print(
        f"Report URL (start the optional viewer first): http://127.0.0.1:9003/reports/?run={report.run.id}"
    )
    if failure is not None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
