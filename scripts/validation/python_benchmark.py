"""Advanced CLI for bounded Python benchmarks and retained failure reports."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from evalsurge import Agent, EvalSurge, Load, RunFailed, Sample


def parse_options(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse bounded benchmark settings without invoking the target.

    Args:
        arguments: Explicit CLI arguments, or None to read the process arguments.

    Returns:
        Settings for an existing authorized endpoint and local artifact directory.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:9001/chat")
    parser.add_argument(
        "--protocol",
        choices=["openai-chat", "mlflow-agent-server", "http-json"],
        default="openai-chat",
    )
    parser.add_argument("--duration", type=float, default=180, help="Dispatch window in seconds.")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--max-requests", type=int, default=10_000)
    parser.add_argument("--request-timeout", type=float, default=10)
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/python-benchmark"))
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """Run preflight/load, save the bounded report page, and print overall metrics.

    Args:
        arguments: Optional CLI arguments for the authorized agent and load bounds.

    Returns:
        Zero for completed lifecycle states, one for failed/cancelled/interrupted runs.
        Individual request errors remain visible in metrics; zero is not a quality pass.

    Raises:
        ValueError: Target or load settings are invalid, before agent traffic starts.
        OSError: Artifact storage is unavailable.

    Duration limits dispatch, not preflight/startup/drain. The first sample is one
    additional invocation. The default local mock makes no model calls; replacing
    its URL can execute tools or incur spend. Saved data includes protected inputs.
    """
    options = parse_options(arguments)
    load = Load(
        concurrency=options.concurrency,
        duration_seconds=options.duration,
        max_requests=options.max_requests,
        timeout_seconds=options.request_timeout,
    )
    artifact_dir = options.artifact_dir.resolve()
    with EvalSurge.local(artifact_dir=artifact_dir) as client:
        run = client.start(
            agent=Agent.http(options.url, protocol=options.protocol),
            cases=[Sample(inputs={"query": "Can I refund an opened item?"})],
            load=load,
        )
        print(
            f"Started {run.id}: up to {load.duration_seconds:g} seconds, "
            f"{load.concurrency} users, {load.max_requests} measured attempts.",
            file=sys.stderr,
            flush=True,
        )
        try:
            report = run.wait(timeout=load.duration_seconds + load.timeout_seconds + 90)
        except RunFailed as failure:
            print(str(failure), file=sys.stderr)
            report = failure.report
        report_file = artifact_dir / f"{run.id}-report.json"
        report_file.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "run_id": report.run.id,
                "status": report.run.status,
                "preflight": report.run.preflight.status,
                "metrics": report.run.metrics,
                "report_file": str(report_file),
            },
            indent=2,
        )
    )
    return int(report.run.status in {"failed", "cancelled", "interrupted"})


if __name__ == "__main__":
    raise SystemExit(main())
