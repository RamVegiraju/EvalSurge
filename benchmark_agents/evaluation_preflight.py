"""Check frozen evaluation setup and one captured probe before allowing measured load."""

from typing import Any

from .evaluation_errors import evaluation_error
from .evaluator import evaluate
from .judges import rubric_hash
from .models import EvaluationError, EvaluationPreflight, Plan, Sample
from .planner import has_reference
from .scorer_registry import definition_hash, load_scorer


def configuration_error(plan: Plan, sample: Sample) -> EvaluationError | None:
    """Validate criteria, first-case evidence, and frozen implementations without inference.

    Args:
        plan: Operator-owned frozen model/scorer settings.
        sample: First workload case used by the existing inference preflight.

    Returns:
        Fixed safe corrective guidance, or None when local checks pass.

    Registered scorer loading is trusted operator code and may access its configured
    registry. This does not execute the target or judge model.
    """
    if not plan.recommendations:
        if plan.source == "explicit":
            return None
        return EvaluationError(
            code="no_ready_scorers",
            message="No executable evaluation criteria were selected.",
            guidance="Select supported criteria with sufficient evidence, or use scorers=[] for performance only.",
        )
    registered = {
        f"registered:{reference.alias}": reference for reference in plan.registered_scorers
    }
    for recommendation in plan.recommendations:
        name = recommendation.scorer
        if recommendation.status != "ready":
            return EvaluationError(
                code="evaluation_missing_evidence",
                message="A selected criterion is not ready for evaluation.",
                guidance="Supply its required evidence or remove it from the selected criteria before starting load.",
                scorer=name,
            )
        reference = registered.get(name)
        if name == "correctness" and not has_reference(sample.expectations):
            return EvaluationError(
                code="evaluation_missing_evidence",
                message="The first workload case has no correctness reference.",
                guidance="Supply expected_response or expected_facts for the first case used to check judging.",
                scorer=name,
            )
        if reference and "expectations" in reference.required_fields and not sample.expectations:
            return EvaluationError(
                code="evaluation_missing_evidence",
                message="The first workload case lacks the registered scorer's reference data.",
                guidance="Provide the frozen scorer's required expectations on the first case.",
                scorer=name,
            )
        if not reference and (not plan.judge_model or not plan.judge_host):
            return EvaluationError(
                code="evaluation_needs_configuration",
                message="The selected catalog judge has no configured provider.",
                guidance="Configure an explicit operator-owned judge model and workspace/profile, or request performance only.",
                scorer=name,
            )
        if reference:
            try:
                scorer = load_scorer(reference, plan.tracking_uri)
                unchanged = definition_hash(scorer) == reference.definition_hash
            except Exception as error:  # noqa: BLE001
                return evaluation_error(error, name)
            if not unchanged:
                return EvaluationError(
                    code="evaluation_configuration_changed",
                    message="The registered scorer no longer matches the frozen plan.",
                    guidance="Review its definition and create a new evaluation plan before starting load.",
                    scorer=name,
                )
    if plan.rubric_hash != rubric_hash():
        return EvaluationError(
            code="evaluation_configuration_changed",
            message="The installed evaluation rubrics no longer match the frozen plan.",
            guidance="Create a new plan using the installed compatible MLflow version.",
        )
    return None


def run_evaluation_preflight(
    row: dict[str, Any], plan: Plan, traces: dict[str, Any] | None = None
) -> EvaluationPreflight:
    """Run one native assessment per criterion, stopping at the first execution failure.

    Args:
        row: Successful inference-probe capture, never a measured load row.
        plan: Frozen evaluation policy; the original is never modified.
        traces: Verified actual probe Trace objects for explicitly trace-required scorers.

    Returns:
        Readiness only: false/zero quality verdicts are valid completed assessments.
        Missing assessments or execution failures prevent measured load.

    Catalog judging makes at most one provider attempt per criterion with the
    frozen timeout/token cap and zero SDK retries. Trusted registered scorers own
    their own deadlines/retries; this thread is not a hard execution sandbox.
    Native runs are tagged evaluation-preflight and excluded from quality results.
    """
    outcome = EvaluationPreflight(status="running")
    traces = traces or {}
    for recommendation in plan.recommendations:
        name = recommendation.scorer
        reference = next(
            (item for item in plan.registered_scorers if f"registered:{item.alias}" == name),
            None,
        )
        if reference and "trace" in reference.required_fields and row["request_id"] not in traces:
            outcome.status = "failed"
            outcome.error = EvaluationError(
                code="evaluation_missing_trace",
                message="The inference probe has no verified trace for the selected scorer.",
                guidance="Check agent instrumentation, trace correlation, and the frozen experiment scope.",
                scorer=name,
            )
            return outcome
        probe_plan = plan.model_copy(
            update={
                "recommendations": [recommendation],
                "max_scored_requests": 1,
                "judge_max_retries": 0,
            },
            deep=True,
        )
        try:
            result = evaluate(
                [row],
                probe_plan,
                traces,
                fail_fast=True,
                phase="evaluation-preflight",
            )
        except Exception as error:  # noqa: BLE001
            outcome.status = "failed"
            outcome.error = evaluation_error(error, name)
            return outcome
        outcome.checked_scorers.append(name)
        assessments = result.get("results", [])
        if (
            result.get("status") != "completed"
            or len(assessments) != 1
            or assessments[0].get("scored") != 1
            or assessments[0].get("status") != "completed"
        ):
            outcome.status = "failed"
            detail = assessments[0].get("error") if assessments else None
            outcome.error = (
                EvaluationError.model_validate(detail)
                if detail
                else EvaluationError(
                    code="assessment_missing",
                    message="The scorer did not produce a complete readiness assessment.",
                    guidance="Check its frozen definition, required evidence, and configured judge model.",
                    scorer=name,
                )
            )
            return outcome
    outcome.status = "passed"
    return outcome
