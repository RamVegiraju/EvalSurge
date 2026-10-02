"""Live FM planning, answer generation, and positive/negative MLflow judging.

Small validation only: one planning request, one inference request, and four judge
requests. Does not load test the workspace or modify remote resources.
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from benchmark_agents.evaluator import evaluate
from benchmark_agents.models import Evaluation
from benchmark_agents.planner import create_plan
from benchmark_agents.providers import DEFAULT_FM_ENDPOINT, planner_client


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    directory = Path("artifacts")
    directory.mkdir(exist_ok=True)
    os.environ["MLFLOW_TRACKING_URI"] = f"sqlite:///{directory.resolve()}/live-validation.db"
    question = "Can I refund an opened item?"
    expected = "Opened items are not refundable."
    config = Evaluation.model_validate(
        {
            "description": "A refund-policy assistant. Its answers must address the user's question and be correct according to the supplied reference policy. Do not assess unrelated safety criteria.",
            "samples": [
                {"inputs": {"query": question}, "expectations": {"expected_response": expected}}
            ],
        }
    )
    plan = await create_plan(config)
    assert {r.scorer for r in plan.recommendations} >= {"relevance", "correctness"}, plan
    missing = await create_plan(Evaluation(description=config.description, scorers=["correctness"]))
    assert missing.recommendations[0].status == "needs_data"
    async with planner_client() as client:
        inference = await client.chat.completions.create(
            model=os.getenv("BENCHMARK_PLANNER_MODEL", DEFAULT_FM_ENDPOINT),
            messages=[
                {"role": "system", "content": f"Answer concisely using this policy: {expected}"},
                {"role": "user", "content": question},
            ],
        )
    answer = inference.choices[0].message.content
    assert answer
    rows = [
        {
            "success": True,
            "case_id": 0,
            "request_id": name,
            "inputs": {"query": question},
            "outputs": output,
            "expectations": {"expected_response": expected},
        }
        for name, output in [
            ("live-inference", answer),
            ("intentionally-incorrect", "Yes, opened items are always eligible for a full refund."),
        ]
    ]
    result = await asyncio.to_thread(evaluate, rows, plan, config)
    correctness = next(r for r in result["results"] if r["scorer"] == "correctness")
    assert correctness["metrics"].get("correctness/mean") == 0.5, correctness
    output = {
        "plan": plan.model_dump(),
        "missing_reference": missing.model_dump(),
        "inference_endpoint": os.getenv("BENCHMARK_PLANNER_MODEL", DEFAULT_FM_ENDPOINT),
        "generated_answer": answer,
        "evaluation": result,
    }
    (directory / "databricks-validation.json").write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
