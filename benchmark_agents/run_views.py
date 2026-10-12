"""FastAPI-independent presentation shared by direct execution and REST.

These functions only read existing owned artifacts. They do not resolve targets,
invoke models, assign quality thresholds, or export operator configuration.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from .models import ProfilingSummary
from .v2_models import (
    DecisionSummary,
    EvaluationOutcome,
    EvidenceCapabilities,
    EvidenceCapability,
    Links,
    Performance,
    PhaseStates,
    Report,
    Result,
    RunStatus,
)

if TYPE_CHECKING:
    from .coordinator import RunCoordinator

TERMINAL = {"completed", "completed_with_gaps", "failed", "interrupted", "cancelled"}


def _evidence_entry(
    *,
    configured: bool | None,
    observed: int,
    total: int | None,
    terminal: bool,
    guidance: str,
) -> EvidenceCapability:
    """Reduce existing measured evidence without turning configuration into verification.

    Args:
        configured: Frozen feature selection, or unknown historical configuration.
        observed: Recorded measured attempts or valid assessment/profile evidence;
            readiness probes are excluded. Failed attempts are load evidence too.
        total: Measured attempts or eligible scorer/attempt pairs, when recorded.
        terminal: Whether no additional run evidence can arrive.
        guidance: Fixed safe explanation without workload or operator values.

    Returns:
        Independent evidence state and coverage. An observed false judge verdict
        remains evidence, never a quality pass or an execution error.
    """
    state = (
        "observed"
        if observed
        else "off"
        if configured is False
        else "unavailable"
        if terminal
        else "pending"
    )
    return EvidenceCapability(
        configured=configured,
        state=state,
        observed_count=observed,
        total_count=total,
        coverage=observed / total if total else None,
        guidance=guidance,
    )


def _assessment_evidence(
    names: set[str],
    configured: bool | None,
    evaluation: EvaluationOutcome,
    terminal: bool,
    guidance: str,
) -> EvidenceCapability:
    """Count measured native assessments, never readiness or mere scorer configuration.

    Args:
        names: Frozen selected scorer identifiers for this evidence capability.
        configured: Whether these criteria were selected, or historical unknown.
        evaluation: Existing typed post-load outcomes; no scorer is executed here.
        terminal: Whether the run cannot produce further evidence.
        guidance: Fixed capability-specific corrective explanation.

    Returns:
        Coverage across eligible scorer/attempt pairs, not a pass rate, population
        estimate, or number of unique requests. Missing totals remain unknown.
    """
    outcomes = [item for item in evaluation.results if item.scorer in names]
    observed = sum(item.scored or 0 for item in outcomes if item.status in {"completed", "partial"})
    total = (
        sum(item.eligible or 0 for item in outcomes)
        if outcomes
        and len(outcomes) == len(names)
        and {item.scorer for item in outcomes} == names
        and all(item.eligible is not None for item in outcomes)
        else None
    )
    return _evidence_entry(
        configured=configured,
        observed=observed,
        total=total,
        terminal=terminal,
        guidance=guidance,
    )


def _evidence_capabilities(
    run: dict[str, Any],
    metrics: Performance | None,
    evaluation: EvaluationOutcome,
    profiling: ProfilingSummary | None,
    *,
    evaluation_off: bool,
) -> EvidenceCapabilities:
    """Present independent evidence from frozen policy and existing detached summaries.

    Args:
        run: Owned snapshot; private configuration is inspected but never exported.
        metrics: Existing measured client observations, excluding inference probes.
        evaluation: Existing measured captured-answer assessments.
        profiling: Already verified measured trace coverage, when supplied.
        evaluation_off: Explicit performance-only policy, including legacy calls.

    Returns:
        Four independent capabilities with no target, judge, auth or store calls.
        Successful readiness cannot establish measured evidence or capacity.
    """
    terminal = run["status"] in TERMINAL
    plan = run.get("plan")
    names = {item["scorer"] for item in (plan or {}).get("recommendations", [])}
    trace_names = {
        f"registered:{item['alias']}"
        for item in (plan or {}).get("registered_scorers", [])
        if "trace" in item.get("required_fields", [])
    }
    trace_names |= {
        item["scorer"]
        for item in (plan or {}).get("recommendations", [])
        if "trace" in item.get("required_fields", [])
    }
    trace_names &= names
    selection_recorded = bool(plan) and "recommendations" in plan
    answer_names = (
        names - trace_names
        if selection_recorded
        else {item.scorer for item in evaluation.results if item.source == "catalog"}
    )
    answer_configured = (
        False if evaluation_off else bool(answer_names) if selection_recorded else None
    )
    trace_judges_configured = (
        False if evaluation_off else bool(trace_names) if selection_recorded else None
    )
    profiling_configured = bool(plan["trace_source"]) if plan and "trace_source" in plan else None
    historical_guidance = (
        " Historical registered-scorer requirements are unknown; their observed assessments "
        "remain in evaluation.results without invented answer-only/trace-required classification."
        if not selection_recorded
        else ""
    )
    return EvidenceCapabilities(
        load_measurements=_evidence_entry(
            configured=True,
            observed=metrics.requests if metrics else 0,
            total=metrics.requests if metrics else None,
            terminal=terminal,
            guidance="Counts cover recorded measured attempts, including failures, not successful "
            "latency coverage or measurement completeness. Inspect timing coverage and all-attempt "
            "errors separately. One run does not establish sustainable capacity.",
        ),
        answer_evaluation=_assessment_evidence(
            answer_names,
            answer_configured,
            evaluation,
            terminal,
            "Answer-only judges use captured inputs, answers and authoritative references, "
            "without tracing or target reinvocation. Inspect per-scorer verdicts and coverage; "
            "assessment completion is not a quality pass." + historical_guidance,
        ),
        internal_profiling=_evidence_entry(
            configured=profiling_configured,
            observed=profiling.traced_requests if profiling else 0,
            total=profiling.total_requests if profiling else None,
            terminal=terminal,
            guidance="Optional profiling needs agent-side trace export and exact run/request "
            "correlation in authorized experiments. Leaving it off does not disable load "
            "measurements or answer-only judging.",
        ),
        trace_aware_evaluation=_assessment_evidence(
            trace_names,
            trace_judges_configured,
            evaluation,
            terminal,
            "Selected trace-required judges need a verified correlated inference-probe trace "
            "before load and verified captured traces for measured assessments. A ready probe "
            "does not guarantee measured trace coverage or a passing verdict."
            + historical_guidance,
        ),
    )


def status_view(run: dict[str, Any]) -> RunStatus:
    """Reduce owned state to public lifecycle status without protected contents."""
    planning = run.get("planning_status", "completed")
    status = "planning" if run["status"] == "queued" and planning == "running" else run["status"]
    return RunStatus(
        id=run["id"],
        status=status,
        name=run.get("name"),
        links=Links.for_run(run["id"]),
        phases=PhaseStates(
            planning=planning,
            inference=run.get("preflight", {}).get("status", "not_run"),
            evaluation_readiness=run.get("evaluation_preflight", {}).get("status", "not_run"),
            load=run["load_status"],
            profiling=run.get("profiling_status", "pending"),
            evaluation=run["evaluation_status"],
        ),
        poll_after_seconds=0 if status in TERMINAL else 1,
    )


def result_view(run: dict[str, Any], profiling: ProfilingSummary | None = None) -> Result:
    """Present descriptive performance and quality evidence, never a quality gate.

    Args:
        run: Detached coordinator snapshot with independent phase evidence.
        profiling: Optional verified internal trace coverage.

    Returns:
        Typed protected assessments and metrics without target/auth configuration.
    """
    status = status_view(run)
    metrics = run.get("metrics") or None
    performance = (
        "complete"
        if metrics and metrics.get("measurement_complete") and run["load_status"] == "completed"
        else "incomplete"
        if metrics
        else "not_run"
        if run["status"] in TERMINAL
        else "pending"
    )
    off = run.get("evaluation_mode") == "off" or (
        run.get("evaluation_mode") is None
        and run["config"]["evaluation"].get("scorers") == []
        and not (run.get("plan") or {}).get("recommendations")
    )
    quality = (
        "off"
        if off
        else "available"
        if run["evaluation_status"] == "completed"
        else "unavailable"
        if run["status"] in TERMINAL
        else "pending"
    )
    measured = (
        Performance.model_validate(
            {key: value for key, value in metrics.items() if key in Performance.model_fields}
        )
        if metrics
        else None
    )
    health = measured.generator_health if measured else None
    if health and (
        health.status == "degraded" or health.journal.writer_failures or not health.journal.drained
    ):
        # Fail-safe presentation if a historical/externally stored summary has an
        # inconsistent completeness flag. This does not rewrite owned artifacts.
        health.status = "degraded"
        measured.measurement_complete = False
        performance = "incomplete"
    evaluation = EvaluationOutcome.model_validate(run.get("evaluation", {}))
    evidence = _evidence_capabilities(run, measured, evaluation, profiling, evaluation_off=off)
    gaps = []
    if performance == "incomplete":
        gaps.append("incomplete_measurements")
    if quality == "unavailable":
        gaps.append("evaluation_unavailable")
    if run.get("planning_error"):
        gaps.append("planning_failed")
    if (
        profiling
        and evidence.internal_profiling.configured is not False
        and profiling.total_requests
        and profiling.traced_requests < profiling.total_requests
    ):
        gaps.append("internal_trace_coverage")
    if run.get("profiling_status") == "failed":
        gaps.append("profiling_failed")
    if measured:
        if measured.generator_health is None:
            gaps.append("generator_health_unavailable")
        elif measured.generator_health.status == "degraded":
            gaps.append("generator_degraded")
    return Result(
        **status.model_dump(exclude={"poll_after_seconds"}),
        summary=DecisionSummary(performance=performance, quality=quality, evidence_gaps=gaps),
        evidence=evidence,
        metrics=measured,
        preflight=run.get("preflight", {"status": "not_run"}),
        evaluation_preflight=run.get("evaluation_preflight", {"status": "not_run"}),
        evaluation=evaluation,
        load_error=run.get("load_error"),
        planning_error=run.get("planning_error"),
    )


def report_view(
    coordinator: "RunCoordinator", run_id: UUID, offset: int = 0, limit: int = 25
) -> Report:
    """Read one bounded protected report, including failures before a plan exists.

    Args:
        coordinator: Open exclusively owned runtime; no new owner is created.
        run_id: Existing run identifier.
        offset: Nonnegative profile-row offset.
        limit: One through one hundred profile rows.

    Returns:
        Typed report with independent phases and available evidence.

    Raises:
        CoordinatorError: Run missing, pagination invalid, or report not ready.
    """
    from .coordinator import CoordinatorError

    if (
        type(offset) is not int
        or not 0 <= offset <= 10_000
        or type(limit) is not int
        or not 1 <= limit <= 100
    ):
        raise CoordinatorError(422, "Invalid report pagination")
    run = coordinator.read_run(run_id)
    if run.get("plan") is None:
        if run["status"] not in TERMINAL:
            raise CoordinatorError(409, "Report is not ready", {"Retry-After": "1"})
        profiling = ProfilingSummary(
            total_requests=0,
            traced_requests=0,
            coverage=0,
            notes=["Planning did not permit target traffic."],
        )
        return Report(
            # An empty presentation shell is not collected profiling evidence.
            # Preserve unknown totals exactly as standalone result retrieval does.
            run=result_view(run),
            profiling=profiling,
            requests=[],
            offset=offset,
            limit=limit,
            total=0,
        )
    legacy = coordinator.get_report(run_id, offset, limit)
    return Report(
        run=result_view(run, legacy.profiling),
        profiling=legacy.profiling,
        requests=legacy.requests,
        offset=offset,
        limit=limit,
        total=legacy.total,
    )
