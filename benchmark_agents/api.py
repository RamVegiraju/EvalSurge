"""HTTP validation, authorization, and presentation over the shared coordinator."""

import hmac
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import APIKeyHeader
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles

from .configuration import configured_environment, getenv
from .coordinator import CoordinatorError, RunCoordinator
from .middleware import BodyLimitMiddleware
from .models import (
    Accepted,
    ErrorResponse,
    Evaluation,
    Plan,
    RequestPage,
    RunPage,
    RunReport,
    RunRequest,
    RunResponse,
)
from .openapi import install_schema

ARTIFACTS = Path(os.getenv("BENCHMARK_ARTIFACT_DIR", "artifacts"))
api_key = APIKeyHeader(name="X-API-Key", auto_error=False)
logger = logging.getLogger(__name__)


async def authorize(request: Request, key: Annotated[str | None, Depends(api_key)]) -> None:
    """Enforce the single-tenant service's inbound access policy.

    Args:
        request: Incoming request with the transport's client address.
        key: Optional X-API-Key header resolved by FastAPI.

    Raises:
        HTTPException: 401 when a configured key is missing or invalid, or 403 when
            an unkeyed server receives a non-loopback request.

    A configured key is required even on loopback. Proxy-header trust must remain
    disabled for unkeyed local access; this is not resource-level tenant authorization.
    """
    expected = getenv("BENCHMARK_API_KEY")
    if expected:
        if key is None or not hmac.compare_digest(key, expected):
            raise HTTPException(401, "Invalid or missing API key")
    elif not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "Configure BENCHMARK_API_KEY for non-loopback access")


def create_app(artifact_dir: Path | None = None, *, config_path: Path | None = None) -> FastAPI:
    """Build the REST adapter with an isolated single-owner run coordinator.

    Args:
        artifact_dir: Storage root; defaults to BENCHMARK_ARTIFACT_DIR or artifacts.
        config_path: Optional bounded operator TOML/YAML configuration file.

    Returns:
        A FastAPI application whose lifespan owns and drains the coordinator.

    Use one process per POSIX artifact directory. REST and the local Python facade
    use the same lifecycle and Locust engine, not separate load implementations.
    """
    from .diagnostics import startup_diagnostics
    from .settings import SettingsError, load_settings
    from .v2 import install_routes

    settings = load_settings(config_path) if config_path or os.getenv("BENCHMARK_CONFIG") else None
    values = settings.to_environment() if settings else None
    coordinator = RunCoordinator(artifact_dir or (settings.artifact_dir if settings else ARTIFACTS))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Acquire coordinator ownership and always drain/release it at shutdown."""
        await coordinator.open()
        try:
            yield
        finally:
            await coordinator.close()

    errors = {
        code: {"model": ErrorResponse, "description": message}
        for code, message in {
            401: "API key missing or invalid",
            403: "Access denied",
            404: "Resource not found",
            409: "Resource state conflict",
            413: "Request body exceeds the configured limit",
            422: "Invalid request",
            429: "Benchmark already active",
            502: "Planner provider failure",
            500: "Unexpected server failure",
        }.items()
    }
    app = FastAPI(
        title="EvalSurge",
        version="0.2.0",
        description="Check inference once before benchmarking one concurrency level, "
        "then evaluate captured answers with a frozen plan. "
        "Local, single-tenant prototype; not a maximum-capacity discovery service.",
        contact={
            "name": "EvalSurge maintainers",
            "url": "https://github.com/RamVegiraju/EvalSurge",
        },
        servers=[
            {
                "url": "/",
                "description": "Current API origin; gzip available for large JSON responses. Bind to loopback for local HTTP; use TLS for remote access.",
            }
        ],
        lifespan=lifespan,
        dependencies=[Depends(authorize)],
        responses=errors,
        docs_url=None,
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
    )
    app.state.coordinator = coordinator
    app.state.startup_diagnostics = (
        startup_diagnostics(settings, environ=values) if settings else None
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(BodyLimitMiddleware)
    app.mount("/reports", StaticFiles(directory=Path(__file__).with_name("static"), html=True))
    app.mount("/docs", StaticFiles(directory=Path(__file__).with_name("docs_ui"), html=True))

    async def legacy_docs(request: Request) -> RedirectResponse:
        """Redirect the public legacy documentation URL to same-origin Swagger UI."""
        return RedirectResponse(f"{request.scope.get('root_path', '')}/docs/")

    app.add_route("/redoc", legacy_docs, methods=["GET"], include_in_schema=False)

    @app.middleware("http")
    async def request_metadata(request: Request, call_next: Any) -> Response:
        """Attach safe correlation, cache, content-sniffing, and CSP metadata."""
        request.state.request_id = str(uuid4())
        try:
            with configured_environment(values):
                response = await call_next(request)
        except Exception as error:
            logger.error("Request failed: %s", type(error).__name__, exc_info=True)
            response = await unexpected_error(request, error)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        return response

    def error_body(request: Request, code: str, message: str) -> dict[str, Any]:
        """Build the common envelope; never serialize input values or credentials."""
        detail: dict[str, Any] = {
            "code": code,
            "message": message,
            "request_id": request.state.request_id,
        }
        if request.url.path.startswith("/v2/"):
            codes = {
                401: "authentication_required",
                403: "access_denied",
                404: "resource_not_found",
                409: "resource_conflict",
                413: "input_limit",
                422: "invalid_request",
                429: "runner_busy",
                500: "internal_error",
                502: "target_resolution_failed",
            }
            number = (
                int(code.removeprefix("http_"))
                if code.startswith("http_")
                else 422
                if code == "validation_error"
                else 500
            )
            detail.update(
                code=codes.get(number, "request_failed"),
                phase="admission",
                retryable=number in {429, 502, 503},
                guidance="Check request and operator configuration; poll an admitted run before submitting again.",
            )
        return {"error": detail}

    @app.exception_handler(CoordinatorError)
    async def coordinator_error(request: Request, error: CoordinatorError) -> JSONResponse:
        """Translate domain failure without making the coordinator depend on HTTP."""
        code = "internal_error" if error.status_code == 500 else f"http_{error.status_code}"
        body = error_body(request, code, str(error))
        if (
            request.url.path.startswith("/v2/")
            and error.status_code == 409
            and error.headers
            and error.headers.get("Retry-After")
            and request.url.path.endswith("/report")
        ):
            body["error"].update(code="report_not_ready", phase="report", retryable=True)
        return JSONResponse(
            body,
            status_code=error.status_code,
            headers=error.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
        """Preserve the existing HTTP error envelope and retry headers."""
        return JSONResponse(
            error_body(request, f"http_{error.status_code}", str(error.detail)),
            status_code=error.status_code,
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        """Return validation locations/messages without submitted input values."""
        message = (
            "Invalid request fields"
            if request.url.path.startswith("/v2/")
            else "; ".join(
                ".".join(str(part) for part in failure["loc"]) + ": " + failure["msg"]
                for failure in error.errors()
            )
        )
        return JSONResponse(error_body(request, "validation_error", message), status_code=422)

    @app.exception_handler(SettingsError)
    async def settings_error(request: Request, error: SettingsError) -> JSONResponse:
        """Expose only the configuration loader's fixed safe diagnostic."""
        return JSONResponse(error_body(request, "http_422", str(error)), status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        """Do not expose unexpected exception text to HTTP clients."""
        return JSONResponse(
            error_body(request, "internal_error", "Unexpected server error"), status_code=500
        )

    @app.post("/v1/evaluation-plans", response_model=Plan, status_code=201, tags=["Plans"])
    async def evaluation_plan(evaluation: Evaluation, response: Response) -> Plan:
        """Persist scorer recommendations, evidence requirements, sampling policy, and judge model.

        \f
        Planning may invoke the configured provider before this acknowledgment.
        """
        plan = await coordinator.evaluation_plan(evaluation)
        response.headers["Location"] = f"/v1/evaluation-plans/{plan.id}"
        return plan

    @app.get("/v1/evaluation-plans/{plan_id}", response_model=Plan, tags=["Plans"])
    async def get_plan(plan_id: UUID) -> Plan:
        """Retrieve a frozen plan for inspection and reuse in subsequent runs."""
        return coordinator.get_plan(plan_id)

    @app.post("/v1/runs", response_model=Accepted, status_code=202, tags=["Runs"])
    async def submit(
        request: RunRequest,
        response: Response,
        idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
    ) -> Accepted:
        """Check inference and selected judges before starting bounded load.

        The extra first-case request can execute tools and incur cost; it is excluded
        from load metrics, profiles, and benchmark quality scores. Selected criteria
        also assess that captured answer once with zero catalog SDK retries.
        Poll preflight/evaluation_preflight for safe corrective guidance; worker
        failures appear in load_error. Idempotency-Key replays the same submission.

        \f
        Admission, plan freezing, recovery, and work ownership belong to the coordinator.
        """
        accepted = await coordinator.submit(request, idempotency_key)
        response.headers["Location"] = accepted.url
        response.headers["Retry-After"] = "1"
        return accepted

    @app.get("/v1/runs", response_model=RunPage, tags=["Runs"])
    async def list_runs(
        offset: Annotated[int, Query(ge=0, description="Zero-based history offset")] = 0,
        limit: Annotated[int, Query(ge=1, le=100, description="Maximum runs per page")] = 50,
        status: Annotated[
            str | None, Query(description="Optional exact lifecycle status filter")
        ] = None,
    ) -> RunPage:
        """List persisted local runs without exposing captured prompts or answers."""
        return coordinator.list_runs(offset, limit, status)

    @app.get("/v1/runs/{run_id}", response_model=RunResponse, tags=["Runs"])
    async def get_run(run_id: UUID) -> RunResponse:
        """Read the inference check, separate phase outcomes, metrics, and frozen plan."""
        return coordinator.get_run(run_id)

    @app.get("/v1/runs/{run_id}/requests", response_model=RequestPage, tags=["Runs"])
    async def get_requests(
        run_id: UUID,
        offset: Annotated[int, Query(ge=0, description="Zero-based record offset")] = 0,
        limit: Annotated[int, Query(ge=1, le=100, description="Maximum records per page")] = 50,
    ) -> RequestPage:
        """Page through captured responses; partial records remain available after interruption."""
        return coordinator.get_requests(run_id, offset, limit)

    @app.get("/v1/runs/{run_id}/report", response_model=RunReport, tags=["Reports"])
    async def get_report(
        run_id: UUID,
        offset: Annotated[int, Query(ge=0, description="Zero-based attempt offset")] = 0,
        limit: Annotated[int, Query(ge=1, le=100, description="Maximum heatmap rows")] = 25,
    ) -> RunReport:
        """Join performance, frozen quality policy, and a bounded heatmap/waterfall page.

        Report data is authenticated like all run resources. The public static shell
        at /reports/ contains no run data or credentials. Times remain agent-relative;
        missing or failed trace collection is represented explicitly.
        """
        return coordinator.get_report(run_id, offset, limit)

    @app.post("/v1/runs/{run_id}/cancel", response_model=Accepted, tags=["Runs"])
    async def cancel(run_id: UUID) -> Accepted:
        """Stop preflight/load dispatch and drain active requests; judging cancellation is unsupported."""
        return coordinator.cancel(run_id)

    install_routes(app, coordinator)
    install_schema(app)
    return app


app = create_app()
