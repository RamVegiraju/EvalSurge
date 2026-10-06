"""Post-run scoring through native MLflow APIs; no agent reinvocation."""

import os
from typing import Any

from .evaluation_details import REQUEST_TAG, assessment_details
from .evaluation_errors import evaluation_error
from .models import Plan
from .planner import has_reference
from .sampling import select_rows
from .scorer_registry import definition_hash, load_scorer


def evaluate(
    rows: list[dict[str, Any]],
    plan: Plan,
    traces: dict[str, Any] | None = None,
    *,
    fail_fast: bool = True,
    phase: str = "evaluation",
) -> dict[str, Any]:
    """Score captured answers using the frozen plan, without reinvoking the target.

    Args:
        rows: Captured attempts containing success, request_id, case_id, inputs,
            outputs, expectations, and optional start_offset_ms.
        plan: Sole source of scorer, workspace, rubric, sampling, and judge budgets.
        traces: Correlated actual MLflow Trace objects collected after load.
        fail_fast: Stop dispatching further criteria after an assessment failure.
        phase: MLflow run tag separating readiness assessments from benchmark quality.

    Returns:
        Separate evaluation status, scorer results, selected request IDs, coverage,
        MLflow run IDs, and bounded request-correlated assessments/rationales.
        Rationales are protected evaluation content, not content-free telemetry.
        Missing evidence or configuration is an explicit gap;
        a completed assessment can still have a false quality verdict.

    This synchronous function performs paid judge calls and writes MLflow artifacts
    when configured. Async callers should offload it to a thread. Individual judge
    failures are captured by MLflow; evaluation-wide exceptions propagate to the
    API job boundary so load measurements can still be retained.
    """
    model = plan.judge_model
    traces = traces or {}
    registered = {
        f"registered:{reference.alias}": reference for reference in plan.registered_scorers
    }
    ready = [r for r in plan.recommendations if r.status == "ready"]
    missing = [r.model_dump() for r in plan.recommendations if r.status == "needs_data"]
    if not ready:
        return {"status": "no_ready_scorers", "results": [], "needs_data": missing}
    if not registered and (not model or not plan.judge_host):
        return {
            "status": "needs_configuration",
            "required": ["DATABRICKS_CONFIG_PROFILE or DATABRICKS_HOST with SDK authentication"],
            "results": [],
        }
    import mlflow

    from .judges import direct_scorer, rubric_hash

    if plan.tracking_uri:
        mlflow.set_tracking_uri(plan.tracking_uri)
    if plan.rubric_hash != rubric_hash():
        return {"status": "configuration_changed", "results": []}

    from mlflow.tracking import MlflowClient

    client = MlflowClient(tracking_uri=plan.tracking_uri)
    experiment_id = os.getenv("MLFLOW_EXPERIMENT_ID")
    if not experiment_id:
        experiment = client.get_experiment_by_name("benchmark-agents")
        experiment_id = (
            experiment.experiment_id if experiment else client.create_experiment("benchmark-agents")
        )
    results = []
    for recommendation in ready:
        errors = []
        reference = registered.get(recommendation.scorer)
        if reference:
            scorer = load_scorer(reference, plan.tracking_uri)
            if definition_hash(scorer) != reference.definition_hash:
                results.append({"scorer": recommendation.scorer, "status": "configuration_changed"})
                if fail_fast:
                    break
                continue
        elif not model or not plan.judge_host:
            results.append({"scorer": recommendation.scorer, "status": "needs_configuration"})
            if fail_fast:
                break
            continue
        else:
            scorer = direct_scorer(
                recommendation.scorer,
                model,
                plan,
                on_error=lambda error: errors.append(
                    evaluation_error(error, recommendation.scorer).model_dump()
                ),
            )
        eligible = [
            r
            for r in rows
            if r["success"]
            and (recommendation.scorer != "correctness" or has_reference(r["expectations"]))
            and (
                not reference
                or "trace" not in reference.required_fields
                or r["request_id"] in traces
            )
            and (
                not reference
                or "expectations" not in reference.required_fields
                or r["expectations"]
            )
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
            if fail_fast:
                break
            continue
        data = [
            {
                "request_id": r["request_id"],
                "tags": {REQUEST_TAG: r["request_id"]},
                "inputs": r["inputs"],
                "outputs": r["outputs"],
                "expectations": r["expectations"],
                **(
                    {"trace": traces[r["request_id"]]}
                    if reference and "trace" in reference.required_fields
                    else {}
                ),
            }
            for r in selected
        ]
        try:
            with mlflow.start_run(
                experiment_id=experiment_id,
                nested=mlflow.active_run() is not None,
                tags={"evalsurge.phase": phase},
            ):
                result = mlflow.genai.evaluate(data=data, scorers=[scorer])
        except Exception as error:  # noqa: BLE001
            diagnostic = evaluation_error(error, recommendation.scorer).model_dump()
            results.append(
                {
                    "scorer": recommendation.scorer,
                    "status": "failed",
                    "attempted": len(selected),
                    "scored": 0,
                    "judge_errors": len(selected),
                    "error": diagnostic,
                    "request_ids": [r["request_id"] for r in selected],
                    "assessments": [
                        {
                            "request_id": row["request_id"],
                            "case_id": row.get("case_id"),
                            "status": "error",
                            "value": None,
                            "rationale": None,
                            "rationale_truncated": False,
                            "error": diagnostic,
                        }
                        for row in selected
                    ],
                    "coverage": coverage,
                }
            )
            if fail_fast:
                break
            continue
        metric_name = (
            reference.name
            if reference
            else "relevance_to_query"
            if recommendation.scorer == "relevance"
            else recommendation.scorer
        )
        frame = result.result_df
        assessments = assessment_details(
            frame,
            selected,
            recommendation.scorer,
            metric_name,
            catalog=reference is None,
            run_id=result.run_id,
        )
        values = frame.get(f"{metric_name}/value") if frame is not None else None
        scored = int(values.notna().sum()) if values is not None else 0
        observed = values.dropna().tolist() if values is not None else []
        pass_rate = (
            sum(bool(value) for value in observed) / len(observed)
            if observed and all(isinstance(value, bool) for value in observed)
            else None
        )
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
                "assessments": assessments,
                "mlflow_run_id": result.run_id,
                "mlflow_experiment_id": str(experiment_id),
                "metrics": result.metrics,
                "pass_rate": pass_rate,
                "source": "registered-mlflow" if reference else "catalog",
                "version": reference.version if reference else plan.rubric_version,
            }
        )
        if status != "completed":
            results[-1]["error"] = (
                (errors[0] if errors else None)
                or next((item["error"] for item in assessments if item["error"] is not None), None)
                or {
                    "code": "assessment_missing",
                    "message": "The scorer did not produce every selected assessment.",
                    "guidance": "Check the registered scorer output type and assessment name against its frozen definition.",
                    "scorer": recommendation.scorer,
                }
            )
            if fail_fast:
                break
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
