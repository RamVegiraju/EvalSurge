"""FastAPI-independent presentation shared by direct execution and REST.

These functions only read existing owned artifacts. They do not resolve targets,
invoke models, assign quality thresholds, or export operator configuration.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from .models import ProfilingSummary
from .v2_models import DecisionSummary, Links, Performance, PhaseStates, Report, Result, RunStatus

if TYPE_CHECKING:
    from .coordinator import RunCoordinator

TERMINAL = {"completed", "completed_with_gaps", "failed", "interrupted", "cancelled"}


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
    gaps = []
    if performance == "incomplete":
        gaps.append("incomplete_measurements")
    if quality == "unavailable":
        gaps.append("evaluation_unavailable")
    if run.get("planning_error"):
        gaps.append("planning_failed")
    if (
        profiling
        and profiling.total_requests
        and profiling.traced_requests < profiling.total_requests
    ):
        gaps.append("internal_trace_coverage")
    if run.get("profiling_status") == "failed":
        gaps.append("profiling_failed")
    return Result(
        **status.model_dump(exclude={"poll_after_seconds"}),
        summary=DecisionSummary(performance=performance, quality=quality, evidence_gaps=gaps),
        metrics=Performance.model_validate(
            {key: value for key, value in metrics.items() if key in Performance.model_fields}
        )
        if metrics
        else None,
        preflight=run.get("preflight", {"status": "not_run"}),
        evaluation_preflight=run.get("evaluation_preflight", {"status": "not_run"}),
        evaluation=run.get("evaluation", {}),
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
            run=result_view(run, profiling),
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
