"""Post-run scoring through native MLflow APIs; no agent reinvocation."""

import math
from numbers import Real
from typing import Any

from .configuration import getenv
from .evaluation_details import REQUEST_TAG, assessment_details
from .evaluation_errors import evaluation_error
from .models import Plan
from .planner import has_reference
from .sampling import select_rows
from .scorer_registry import definition_hash, load_scorer


def _verified_metrics(name: str, values: list[Any], expected: int) -> dict[str, float]:
    """Return a mean only for complete finite, durably verified scalar scores."""
    if len(values) != expected or not values or not all(isinstance(v, Real) for v in values):
        return {}
    try:
        numeric = [float(value) for value in values]
        if not all(math.isfinite(value) for value in numeric):
            return {}
        mean = math.fsum(value / len(numeric) for value in numeric)
    except OverflowError:
        return {}
    return {f"{name}/mean": mean} if math.isfinite(mean) else {}


def evaluate(
    rows: list[dict[str, Any]],
    plan: Plan,
    traces: dict[str, Any] | None = None,
    *,
    fail_fast: bool = True,
    phase: str = "evaluation",
    cancellation: Any = None,
) -> dict[str, Any]:
    """Score captured answers using the frozen plan, without reinvoking the target.

    Args:
        rows: Captured attempts containing success, request_id, case_id, inputs,
            outputs, expectations, and optional start_offset_ms.
        plan: Sole source of scorer, workspace, rubric, sampling, and judge budgets.
        traces: Correlated actual MLflow Trace objects collected after load.
        fail_fast: Stop dispatching further criteria after an assessment failure.
        phase: MLflow run tag separating readiness assessments from benchmark quality.
        cancellation: Optional owner event exposing ``is_set``; cancellation stops
            the evaluation child, but cannot undo already dispatched provider calls.

    Returns:
        Separate evaluation status, scorer results, selected request IDs, coverage,
        MLflow run IDs, and bounded request-correlated assessments/rationales.
        Rationales are protected evaluation content, not content-free telemetry.
        Missing evidence or configuration is an explicit gap;
        a completed assessment can still have a false quality verdict.

    Native work runs in an owned process with startup configuration established
    before MLflow imports. No caller-global environment, tracking state or cached
    exporter is changed. Async callers should offload this owner to a thread.
    """
    if not any(item.status == "ready" for item in plan.recommendations):
        return {
            "status": "no_ready_scorers",
            "results": [],
            "needs_data": [
                item.model_dump() for item in plan.recommendations if item.status == "needs_data"
            ],
        }
    from .evaluation_process import evaluate_in_process

    return evaluate_in_process(
        rows, plan, traces or {}, fail_fast=fail_fast, phase=phase, cancellation=cancellation
    )


def _evaluate_native(
    rows: list[dict[str, Any]],
    plan: Plan,
    traces: dict[str, Any] | None = None,
    *,
    fail_fast: bool = True,
    phase: str = "evaluation",
) -> dict[str, Any]:
    """Execute the frozen policy inside its serial, synchronous native worker.

    Args:
        rows: Selected captured attempts; never target invocation instructions.
        plan: Frozen operator-owned scorer and reference configuration.
        traces: Previously verified native target traces, when explicitly required.
        fail_fast: Stop criteria after any execution or persistence failure.
        phase: Readiness/quality tag on new evaluation runs.

    Returns:
        Safe, request-correlated assessments and independent evaluation outcomes.

    This private implementation makes judge calls and native artifact writes only
    in a separately owned process; direct use does not establish process isolation.
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
    experiment_id = getenv("MLFLOW_EXPERIMENT_ID")
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
        from .evaluation_process import verify_durable_assessments

        frame = verify_durable_assessments(frame, selected, metric_name, result.run_id, client)
        assessments = assessment_details(
            frame,
            selected,
            recommendation.scorer,
            metric_name,
            catalog=reference is None,
            run_id=result.run_id,
        )
        observed = [
            item["value"]
            for item in assessments
            if item["status"] in {"passed", "failed", "scored"} and item["value"] is not None
        ]
        scored = len(observed)
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
                "metrics": _verified_metrics(metric_name, observed, len(selected)),
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
