"""Versioned HTTP façade over one coordinator, with safe result presentation."""

import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, FastAPI, Header, Query, Response

from .coordinator import CoordinatorError, RunCoordinator
from .diagnostics import Capabilities, build_capabilities
from .models import ProfilingSummary
from .planner import fingerprint
from .settings import load_settings
from .v2_models import (
    Acknowledgment,
    DecisionSummary,
    Links,
    Performance,
    PhaseStates,
    Report,
    Result,
    RunCreate,
    RunStatus,
    V2ErrorResponse,
)

TERMINAL = {"completed", "completed_with_gaps", "failed", "interrupted", "cancelled"}


def status_view(run: dict[str, Any]) -> RunStatus:
    """Reduce a persisted run to lightweight public phase status.

    Args:
        run: Coordinator-owned detached snapshot or active state.

    Returns:
        No operator destinations, credentials, workload, or assessment contents.
    """
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
    """Compute descriptive completion and gaps without assigning quality thresholds.

    Args:
        run: Coordinator state with independently retained evidence.
        profiling: Optional verified profile coverage, read from existing artifacts.

    Returns:
        Typed metrics and protected assessments; no target configuration or plan secrets.
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


def install_routes(app: FastAPI, coordinator: RunCoordinator) -> None:
    """Install authenticated v2 routes; application middleware owns configuration.

    Args:
        app: Existing REST application with inbound auth, body bounds, and safe errors.
        coordinator: Its exclusively owned local runtime; no alternate load engine.
    """
    from .configuration import environment
    from .target_resolver import TargetResolutionError, resolve_registered_target

    errors = {
        code: {"model": V2ErrorResponse, "description": description}
        for code, description in {
            401: "Authentication required",
            403: "Access denied",
            404: "Resource not found",
            409: "Resource conflict",
            413: "Input exceeds limit",
            422: "Invalid request",
            429: "Runner busy",
            500: "Server failure",
            502: "Target resolution failed",
        }.items()
    }
    router = APIRouter(prefix="/v2", tags=["Benchmarks v2"], responses=errors)

    @router.post("/runs", response_model=Acknowledgment, status_code=202)
    async def start(
        request: RunCreate,
        response: Response,
        idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
    ) -> Acknowledgment:
        """Admit a registered workload; planning and preflights execute after the receipt.

        Each admitted run performs one extra inference probe and optional judge-readiness
        assessments. Those calls can execute tools and incur cost, and are excluded from
        measured results. Idempotency binds the complete canonical v2 request.
        """
        canonical = fingerprint({"api_version": "v2", "request": request.model_dump(mode="json")})
        if idempotency_key:
            key_hash = fingerprint(idempotency_key)
            for prior in coordinator.index.values():
                if prior.get("idempotency_key_hash") == key_hash:
                    if prior.get("request_hash") != canonical:
                        raise CoordinatorError(
                            409, "Idempotency-Key was used with a different body"
                        )
                    stored = coordinator._read_run(UUID(prior["id"]))
                    ack = Acknowledgment(
                        id=stored["id"], status=stored["status"], links=Links.for_run(stored["id"])
                    )
                    response.headers.update({"Location": ack.links.status, "Retry-After": "1"})
                    return ack
        settings = load_settings(environ=environment())
        if request.target.connection_id not in settings.connections:
            raise CoordinatorError(422, "Unknown registered target")
        try:
            from .models import Target

            request.translate(Target(url="http://127.0.0.1/validation"), set(settings.scorers))
        except ValueError as error:
            raise CoordinatorError(422, "Unknown registered scorer") from error
        try:
            target, connection = await asyncio.to_thread(
                resolve_registered_target, request.target.connection_id, settings.connections
            )
            translated = request.translate(target, set(settings.scorers))
        except TargetResolutionError as error:
            raise CoordinatorError(
                502, "Registered target resolution failed; check operator configuration"
            ) from error
        except ValueError as error:
            raise CoordinatorError(
                422, "Invalid registered target or scorer configuration"
            ) from error
        accepted = await coordinator.submit(
            translated,
            idempotency_key,
            connection=connection,
            defer_planning=True,
            submission_hash=canonical,
            name=request.name,
            evaluation_mode=request.evaluation.mode,
        )
        links = Links.for_run(accepted.id)
        response.headers.update({"Location": links.status, "Retry-After": "1"})
        return Acknowledgment(id=accepted.id, status=accepted.status, links=links)

    @router.get("/capabilities", response_model=Capabilities)
    async def capabilities() -> Capabilities:
        """Read secret-free static capabilities; this does not certify runtime availability."""
        values = environment()
        return build_capabilities(load_settings(environ=values), environ=values)

    @router.get("/runs/{run_id}", response_model=RunStatus)
    async def status(run_id: UUID, response: Response) -> RunStatus:
        """Poll lifecycle and independent phases without transferring report contents."""
        view = status_view(coordinator._read_run(run_id))
        response.headers["Retry-After"] = str(int(view.poll_after_seconds))
        return view

    @router.get("/runs/{run_id}/result", response_model=Result)
    async def result(run_id: UUID) -> Result:
        """Read measured performance and protected quality evidence, including partial failures."""
        run = coordinator._read_run(run_id)
        profiling = None
        if run["status"] in TERMINAL and run.get("plan"):
            profiling = coordinator.get_report(run_id).profiling
        return result_view(run, profiling)

    @router.get("/runs/{run_id}/report", response_model=Report)
    async def report(
        run_id: UUID,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
    ) -> Report:
        """Read a bounded content-free profile page alongside protected assessment results."""
        run = coordinator._read_run(run_id)
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

    @router.post("/runs/{run_id}/cancel", response_model=Acknowledgment)
    async def cancel(run_id: UUID) -> Acknowledgment:
        """Stop new dispatch and drain active calls; already executed actions remain."""
        accepted = coordinator.cancel(run_id)
        return Acknowledgment(
            id=accepted.id, status=accepted.status, links=Links.for_run(accepted.id)
        )

    app.include_router(router)
