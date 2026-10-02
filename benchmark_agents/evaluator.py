"""Post-run scoring through native MLflow APIs; no agent reinvocation."""

import os
from typing import Any

from .models import Evaluation, Plan
from .planner import has_reference
from .sampling import select_rows


def evaluate(rows: list[dict[str, Any]], plan: Plan, config: Evaluation) -> dict[str, Any]:
    """Apply ready scorers to captured answers and retain per-scorer coverage."""
    model = plan.judge_model
    ready = [r for r in plan.recommendations if r.status == "ready"]
    missing = [r.model_dump() for r in plan.recommendations if r.status == "needs_data"]
    if not ready:
        return {"status": "no_ready_scorers", "results": [], "needs_data": missing}
    if not model or not plan.judge_host:
        return {
            "status": "needs_configuration",
            "required": ["DATABRICKS_CONFIG_PROFILE or DATABRICKS_HOST with SDK authentication"],
            "results": [],
        }
    import mlflow

    from .judges import direct_scorer, rubric_hash

    if plan.rubric_hash != rubric_hash():
        return {"status": "configuration_changed", "results": []}

    if not os.getenv("MLFLOW_EXPERIMENT_ID"):
        mlflow.set_experiment("benchmark-agents")
    results = []
    for recommendation in ready:
        eligible = [
            r
            for r in rows
            if r["success"]
            and (recommendation.scorer != "correctness" or has_reference(r["expectations"]))
        ]
        selected, coverage = select_rows(eligible, rows, plan)
        if not selected:
            results.append(
                {
                    "scorer": recommendation.scorer,
                    "status": "no_eligible_outputs",
                    "scored": 0,
                    "coverage": coverage,
                }
            )
            continue
        data = [
            {"inputs": r["inputs"], "outputs": r["outputs"], "expectations": r["expectations"]}
            for r in selected
        ]
        result = mlflow.genai.evaluate(
            data=data, scorers=[direct_scorer(recommendation.scorer, model, plan)]
        )
        metric_name = (
            "relevance_to_query" if recommendation.scorer == "relevance" else recommendation.scorer
        )
        frame = result.result_df
        values = frame.get(f"{metric_name}/value") if frame is not None else None
        scored = int(values.notna().sum()) if values is not None else 0
        status = "completed" if scored == len(selected) else "partial" if scored else "failed"
        results.append(
            {
                "scorer": recommendation.scorer,
                "status": status,
                "eligible": len(eligible),
                "coverage": coverage,
                "attempted": len(selected),
                "scored": scored,
                "judge_errors": len(selected) - scored,
                "request_ids": [r["request_id"] for r in selected],
                "mlflow_run_id": result.run_id,
                "metrics": result.metrics,
            }
        )
    return {
        "status": "completed_with_errors"
        if any(r["status"] != "completed" for r in results)
        else "completed_with_gaps"
        if missing
        else "completed",
        "needs_data": missing,
        "request_coverage": {
            "total": len(rows),
            "successful": sum(bool(r["success"]) for r in rows),
            "failed": sum(not r["success"] for r in rows),
        },
        "judge_model": model,
        "transport": "databricks-sdk",
        "results": results,
    }
