"""Versioned HTTP façade over one coordinator, with safe result presentation."""

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, FastAPI, Header, Query, Response

from .coordinator import CoordinatorError, RunCoordinator
from .diagnostics import Capabilities, build_capabilities
from .planner import fingerprint
from .run_views import TERMINAL, report_view, result_view, status_view
from .settings import load_settings
from .v2_models import (
    Acknowledgment,
    Links,
    Report,
    Result,
    RunCreate,
    RunStatus,
    V2ErrorResponse,
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
                    stored = coordinator.read_run(UUID(prior["id"]))
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
        view = status_view(coordinator.read_run(run_id))
        response.headers["Retry-After"] = str(int(view.poll_after_seconds))
        return view

    @router.get("/runs/{run_id}/result", response_model=Result)
    async def result(run_id: UUID) -> Result:
        """Read measured performance and protected quality evidence, including partial failures."""
        run = coordinator.read_run(run_id)
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
        return report_view(coordinator, run_id, offset, limit)

    @router.post("/runs/{run_id}/cancel", response_model=Acknowledgment)
    async def cancel(run_id: UUID) -> Acknowledgment:
        """Stop new dispatch and drain active calls; already executed actions remain."""
        accepted = coordinator.cancel(run_id)
        return Acknowledgment(
            id=accepted.id, status=accepted.status, links=Links.for_run(accepted.id)
        )

    app.include_router(router)
