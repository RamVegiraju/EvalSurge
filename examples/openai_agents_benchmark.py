"""Benchmark the instrumented OpenAI Agents demo with load and quality judging."""

import sys

from evalsurge import Agent, EvalSurge, Evaluation, Load, Sample


def main() -> None:
    """Run the OpenAI Agents benchmark and print its combined report."""
    cases = [
        Sample(
            inputs={"query": "Can I refund an opened item?"},
            expectations={"expected_response": "Opened items cannot be refunded."},
        )
    ]
    with EvalSurge.local(artifact_dir="artifacts/openai-agents-benchmark") as client:
        run = client.start(
            agent=Agent.http("http://127.0.0.1:9001/openai-agents/chat"),
            cases=cases,
            load=Load(concurrency=2, duration_seconds=10, max_requests=10),
            evaluation=Evaluation(
                description="Answer refund questions according to the reference policy.",
                scorers=["relevance", "correctness"],
                max_scored_requests=5,
            ),
        )
        print(run.wait(timeout=300).model_dump_json(indent=2))


if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit("This example does not accept CLI flags; edit its Python settings.")
    main()
