"""Runner: local Python. Target: a separately hosted, real, instrumented HTTP agent.

Evaluation stays off. The existing excluded inference probe must have a real,
complete, correlated MLflow trace before measured traffic starts. This runner
does not instrument or host the customer's agent or create tracking resources.
"""

import argparse

from benchmark_agents.settings import Settings, TraceSettings
from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference, format_summary


def request() -> RunCreate:
    """Build a bounded five-attempt load-only smoke; construction makes no calls."""
    return RunCreate(
        name="local-runner-traced-http-target-smoke",
        target=TargetReference(connection_id="agent"),
        cases=[Case(input={"query": "Can an opened item be refunded?"})],
        load=Load(concurrency=5, duration_seconds=10, max_requests=5, timeout_seconds=40),
    )


def main() -> None:
    """Use an exact operator trace scope, independent of evaluation policy.

    Side Effects:
        Up to six actual target invocations (one excluded probe, five measured),
        one Locust worker and protected local artifacts. Scoped trace reads happen
        outside measured dispatch. No planners/judges or experiment creation.
        Native framework/model instrumentation must be configured in the target.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Authorized http-json endpoint of the real instrumented agent")
    parser.add_argument("--tracking-uri", required=True, help="Exact operator tracking destination")
    parser.add_argument(
        "--experiment-id", required=True, help="Existing authorized trace experiment"
    )
    parser.add_argument("--allow-paid-inference", action="store_true")
    args = parser.parse_args()
    if not args.allow_paid_inference:
        parser.error("Review six possible real agent calls; pass --allow-paid-inference.")
    try:
        settings = Settings(
            tracking_uri=args.tracking_uri,
            tracing=TraceSettings(enabled=True, experiment_ids=(args.experiment_id,), max_traces=5),
        )
        agent = Agent.http(args.url, protocol="http-json")
    except ValueError:
        parser.error(
            "Review the exact endpoint, safe tracking destination and authorized experiment."
        )
    with EvalSurge(
        artifact_dir="artifacts/local-runner-traced-http-target",
        targets={"agent": agent},
        settings=settings,
    ) as client:
        report = client.start(request()).wait(timeout=300)
        print(format_summary(report))


if __name__ == "__main__":
    main()
