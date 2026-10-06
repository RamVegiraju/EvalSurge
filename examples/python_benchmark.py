"""Benchmark an existing HTTP agent for three minutes; quality judging is disabled."""

import sys

from evalsurge import Agent, EvalSurge, Load, Sample


def main() -> None:
    """Run the public Python API and print its report; failures raise RunFailed."""
    with EvalSurge.local(artifact_dir="artifacts/python-benchmark") as client:
        run = client.start(
            agent=Agent.http("http://127.0.0.1:9001/chat"),
            cases=[Sample(inputs={"query": "Can I refund an opened item?"})],
            load=Load(concurrency=5, duration_seconds=180, max_requests=10_000),
        )
        report = run.wait(timeout=600)
        print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit("For CLI flags, use python -m scripts.validation.python_benchmark.")
    main()
