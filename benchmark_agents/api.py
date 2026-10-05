"""Single-process asynchronous REST API for reproducible local benchmarks."""

import asyncio
import hmac
import json
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
from openai import OpenAIError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles

from .connections import resolve_connection
from .evaluator import evaluate
from .locust_runner import preflight_result, run_load, run_preflight
from .middleware import BodyLimitMiddleware
from .models import (
    Accepted,
    ErrorResponse,
    Evaluation,
    Plan,
    PreflightError,
    PreflightResult,
    ProfilingSummary,
    RequestPage,
    RequestProfile,
    RunPage,
    RunReport,
    RunRequest,
    RunResponse,
    RunSummary,
)
from .openapi import install_schema
from .planner import PlannerResponseError, create_plan, fingerprint
from .profiling import PROFILE_NOTES, collect_profiles
from .runner import payload
from .storage import atomic_json, recover_rows

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
    expected = os.getenv("BENCHMARK_API_KEY")
    if expected:
        if key is None or not hmac.compare_digest(key, expected):
            raise HTTPException(401, "Invalid or missing API key")
    elif not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "Configure BENCHMARK_API_KEY for non-loopback access")


async def plan_or_error(evaluation: Evaluation) -> Plan:
    """Create a plan and translate recognized failures into HTTP exceptions.

    Args:
        evaluation: Validated criteria, samples, and optional explicit scorer IDs.

    Returns:
        An unpersisted evaluation plan.

    Raises:
        HTTPException: Sanitized 422 for input/configuration errors, or 502 for
            malformed upstream output and provider inference failure.
    """
    try:
        return await create_plan(evaluation)
    except PlannerResponseError as error:
        raise HTTPException(502, "Planner returned an invalid recommendation") from error
    except ValueError as error:
        raise HTTPException(422, "Invalid evaluation or server planning configuration") from error
    except OpenAIError as error:
        raise HTTPException(502, "Planner provider failed; check server configuration") from error


def create_app(artifact_dir: Path | None = None) -> FastAPI:
    """Build an isolated, single-run API application with persistent local artifacts.

    Args:
        artifact_dir: Storage root; defaults to BENCHMARK_ARTIFACT_DIR or artifacts.

    Returns:
        A FastAPI application with independent run, task, and cancellation state.

    Its lifespan holds a POSIX filesystem lock, signals abandoned workers on restart,
    and drains owned tasks on shutdown. Use one process per artifact directory; there
    is no durable queue, automatic run resumption, or distributed ownership.
    """
    root = artifact_dir or ARTIFACTS
    runs: dict[str, dict[str, Any]] = {}
    tasks: dict[str, asyncio.Task] = {}
    cancellations: dict[str, asyncio.Event] = {}
    orphan_workers: dict[Path, int] = {}
    submission = asyncio.Lock()
    planning = asyncio.Lock()
    index: dict[str, dict[str, Any]] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Hold the storage ownership lock and drain API-owned work at shutdown.

        Args:
            app: Application context supplied by FastAPI.

        Yields:
            Control after storage initialization and abandoned-worker cancellation.

        Raises:
            OSError: Storage setup or the exclusive process lock cannot be acquired.
        """
        root.mkdir(parents=True, exist_ok=True)
        # Fail fast on accidental multi-worker deployment (local POSIX service).
        import fcntl

        with (root / ".service.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for snapshot in root.glob("*.json"):
                try:
                    key = str(UUID(snapshot.stem))
                except ValueError:
                    continue
                summary_path = root / "summaries" / snapshot.name
                stored = json.loads(
                    summary_path.read_text() if summary_path.exists() else snapshot.read_text()
                )
                index[key] = {
                    field: stored.get(field)
                    for field in (
                        "id",
                        "status",
                        "load_status",
                        "evaluation_status",
                        "idempotency_key_hash",
                        "request_hash",
                    )
                }
                if index[key]["status"] == "preflighting":
                    index[key].update(
                        status="interrupted", load_status="skipped", evaluation_status="skipped"
                    )
                elif index[key]["status"] in {"queued", "running", "profiling", "evaluating"}:
                    index[key]["status"] = "interrupted"
                    for phase in ("load_status", "evaluation_status"):
                        if index[key][phase] in {"queued", "running", "pending"}:
                            index[key][phase] = "interrupted"
                atomic_json(summary_path, index[key])
            worker_files = [*root.glob("*/worker.json"), *root.glob("preflights/*/worker.json")]
            for worker_file in worker_files:
                directory = worker_file.parent
                if not (directory / "result.json").exists():
                    (directory / "cancel").touch(exist_ok=True)
                    orphan_workers[directory] = json.loads(worker_file.read_text())["pid"]
            yield
            for event in cancellations.values():
                event.set()
            if tasks:
                await asyncio.gather(*list(tasks.values()), return_exceptions=True)
            fcntl.flock(lock, fcntl.LOCK_UN)

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
        """Assign a correlation UUID and decorate responses returned by the stack.

        Args:
            request: Incoming request; its state receives the request identifier.
            call_next: Downstream ASGI middleware and route dispatcher.

        Returns:
            The downstream response with request-ID and no-store headers.
            Unexpected errors also retain safe error bodies and metadata headers.
        """
        request.state.request_id = str(uuid4())
        try:
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
        """Build the common error envelope using this request's correlation UUID."""
        return {"error": {"code": code, "message": message, "request_id": request.state.request_id}}

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
        """Render a FastAPI HTTP exception while preserving its retry headers."""
        return JSONResponse(
            error_body(request, f"http_{error.status_code}", str(error.detail)),
            status_code=error.status_code,
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        """Return validation locations and messages without serializing input values."""
        # Do not echo submitted values, which can include private prompts.
        message = "; ".join(
            ".".join(str(x) for x in e["loc"]) + ": " + e["msg"] for e in error.errors()
        )
        return JSONResponse(error_body(request, "validation_error", message), status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        """Return a generic 500 envelope without exposing unexpected exception details."""
        return JSONResponse(
            error_body(request, "internal_error", "Unexpected server error"), status_code=500
        )

    def persist(run_id: str) -> None:
        """Atomically snapshot the current in-memory state for an owned run."""
        atomic_json(root / f"{run_id}.json", runs[run_id])
        index[run_id] = {
            key: runs[run_id].get(key)
            for key in (
                "id",
                "status",
                "load_status",
                "evaluation_status",
                "idempotency_key_hash",
                "request_hash",
            )
        }
        atomic_json(root / "summaries" / f"{run_id}.json", index[run_id])

    def read_run(run_id: UUID) -> dict[str, Any]:
        """Read owned state or reconstruct an abandoned persisted run.

        Args:
            run_id: Validated run identifier.

        Returns:
            Current in-memory state, or a recovered snapshot with unfinished phases
            marked interrupted. Recovery may create a worker cancellation marker,
            but does not resume work or rewrite the persisted run snapshot.

        Raises:
            HTTPException: 404 when the run snapshot does not exist.
        """
        key = str(run_id)
        if key in runs:
            return runs[key]
        path = root / f"{key}.json"
        if not path.exists():
            raise HTTPException(404, "Unknown run")
        result = json.loads(path.read_text())
        if result["status"] == "preflighting":
            probe_root = root / "preflights" / key
            if probe_root.exists():
                (probe_root / "cancel").touch(exist_ok=True)
            probe_path = probe_root / "preflight.json"
            probe = (
                PreflightResult.model_validate_json(probe_path.read_text())
                if probe_path.exists()
                else preflight_result(recover_rows(probe_root)[0], {"load_status": "interrupted"})
            )
            result.update(
                status="interrupted",
                load_status="skipped",
                evaluation_status="skipped",
                profiling_status="skipped",
                preflight=probe.model_dump(),
                requests=[],
                trace_coverage="No measured load requests; inference preflight did not permit load.",
            )
        elif result["status"] in {"queued", "running", "profiling", "evaluating"}:
            result["status"] = "interrupted"
            if result["load_status"] in {"queued", "running"}:
                result["load_status"] = "interrupted"
                if (root / key).exists():
                    (root / key / "cancel").touch(exist_ok=True)
                result["requests"], _ = recover_rows(root / key)
            if result["evaluation_status"] in {"pending", "running"}:
                result["evaluation_status"] = "interrupted"
        if result["load_status"] == "interrupted":
            result["requests"], _ = recover_rows(root / key)
            recovered = root / key / "result.json"
            if recovered.exists():
                result["metrics"] = json.loads(recovered.read_text())["summary"]
                result["metrics"]["measurement_complete"] = False
        return result

    def skip_load(run_id: str, status: str) -> None:
        """Retain a terminal zero-load report without collecting or judging probe data.

        Args:
            run_id: API-owned run whose preflight did not permit load.
            status: Overall failed, cancelled, or interrupted outcome.

        The run owns no measured attempts. No metric values are invented, and a
        bounded report snapshot keeps the preflight failure visible in the UI.
        """
        run = runs[run_id]
        run.update(
            status=status,
            load_status="skipped",
            evaluation_status="skipped",
            profiling_status="skipped",
            requests=[],
            trace_coverage="No measured load requests; inference preflight did not permit load.",
        )
        profiling = ProfilingSummary(
            total_requests=0,
            traced_requests=0,
            coverage=0,
            notes=[
                "No load test was started. Preflight is excluded from metrics, profiles, and judging."
            ],
        )
        atomic_json(root / run_id / "profiling.json", profiling.model_dump())

    async def execute(run_id: str, request: RunRequest, plan: Plan) -> None:
        """Advance an admitted run through preflight, load, evaluation, and cleanup.

        Args:
            run_id: Identifier already registered in run and cancellation state.
            request: Validated endpoint and workload configuration.
            plan: Persisted evaluation policy frozen before load dispatch.

        Only a passed first-case inference check allows load. Its independent
        captures never enter metrics or judging. Phase snapshots retain measurements
        when evaluation fails. Cancellation/interruption skips judging. Job-boundary
        failures become safe statuses; final persistence releases task ownership.
        """
        run = runs[run_id]
        try:
            run.update(
                status="preflighting", preflight=PreflightResult(status="running").model_dump()
            )
            persist(run_id)
            probe = await run_preflight(request, run_id, cancellations[run_id], artifact_dir=root)
            run["preflight"] = probe.model_dump()
            if probe.status != "passed" or cancellations[run_id].is_set():
                status = (
                    "cancelled"
                    if cancellations[run_id].is_set() or probe.status == "cancelled"
                    else "interrupted"
                    if probe.status == "interrupted"
                    else "failed"
                )
                if status == "failed":
                    run["error_type"] = "PreflightFailed"
                skip_load(run_id, status)
                return
            run.update(status="running", load_status="running")
            persist(run_id)
            rows, summary = await run_load(
                request, run_id, cancellations[run_id], artifact_dir=root
            )
            run.update(
                requests=rows, metrics=summary, load_status=summary.get("load_status", "completed")
            )
            run["status"] = "profiling"
            persist(run_id)
            try:
                profiling, traces = await asyncio.to_thread(
                    collect_profiles, rows, run_id, plan.trace_source, root / run_id
                )
                run["profiling_status"] = "completed"
            except Exception as error:  # noqa: BLE001
                traces = {}
                profiling = ProfilingSummary(
                    total_requests=len(rows),
                    traced_requests=0,
                    coverage=0,
                    gaps={"collection_failed": len(rows)},
                    notes=[*PROFILE_NOTES, f"Collection failed: {type(error).__name__}"],
                )
                run["profiling_status"] = "failed"
                atomic_json(root / run_id / "profiling.json", profiling.model_dump())
            run["trace_coverage"] = (
                f"{profiling.traced_requests}/{profiling.total_requests} attempts have "
                "correlated internal spans; remaining attempts are client-only."
            )
            if run["load_status"] != "completed" or cancellations[run_id].is_set():
                run.update(
                    status="cancelled" if cancellations[run_id].is_set() else "interrupted",
                    evaluation_status="skipped",
                )
            else:
                run.update(status="evaluating", evaluation_status="running")
                persist(run_id)
                try:
                    run["evaluation"] = await asyncio.to_thread(evaluate, rows, plan, traces)
                except Exception as error:  # noqa: BLE001 - preserve load artifacts at job boundary
                    run["evaluation"] = {"status": "failed", "error_type": type(error).__name__}
                run["evaluation_status"] = run["evaluation"]["status"]
                run["status"] = (
                    "completed"
                    if run["evaluation_status"] == "completed"
                    or (not plan.recommendations and request.evaluation.scorers == [])
                    else "completed_with_gaps"
                )
        except Exception as error:  # noqa: BLE001 - persist failures at background job boundary
            run.update(status="failed", error_type=type(error).__name__)
            if run["preflight"]["status"] == "running":
                run["preflight"] = PreflightResult(
                    status="failed",
                    error=PreflightError(
                        code="worker_failed",
                        message="Inference preflight failed. Load test did not start. Check server worker configuration.",
                    ),
                ).model_dump()
                skip_load(run_id, "failed")
            if run["load_status"] == "running":
                run["load_status"] = "failed"
                run["requests"], _ = recover_rows(root / run_id)
            if run["evaluation_status"] == "pending":
                run["evaluation_status"] = "skipped"
        finally:
            persist(run_id)
            tasks.pop(run_id, None)
            cancellations.pop(run_id, None)
            runs.pop(run_id, None)

    @app.post("/v1/evaluation-plans", response_model=Plan, status_code=201, tags=["Plans"])
    async def evaluation_plan(evaluation: Evaluation, response: Response) -> Plan:
        """Persist scorer recommendations, evidence requirements, sampling policy, and judge model.

        \f
        Args:
            evaluation: Planning input; samples can be absent at this stage.
            response: FastAPI response used to attach the resource's Location header.

        Returns:
            The frozen plan after its local snapshot is written.

        Planning may make a provider call before this 201 response is returned.
        """
        if planning.locked() or tasks:
            raise HTTPException(
                429, "Planning or a benchmark is active", headers={"Retry-After": "5"}
            )
        async with planning:
            plan = await plan_or_error(evaluation)
        atomic_json(root / "plans" / f"{plan.id}.json", plan.model_dump())
        response.headers["Location"] = f"/v1/evaluation-plans/{plan.id}"
        return plan

    @app.get("/v1/evaluation-plans/{plan_id}", response_model=Plan, tags=["Plans"])
    async def get_plan(plan_id: UUID) -> Plan:
        """Retrieve a frozen plan for inspection and reuse in subsequent runs.

        \f
        Args:
            plan_id: Identifier returned by plan creation.

        Returns:
            The persisted plan, validated against the current model.

        Raises:
            HTTPException: 404 when no plan snapshot exists.
        """
        path = root / "plans" / f"{plan_id}.json"
        if not path.exists():
            raise HTTPException(404, "Unknown evaluation plan")
        return Plan.model_validate_json(path.read_text())

    @app.post("/v1/runs", response_model=Accepted, status_code=202, tags=["Runs"])
    async def submit(
        request: RunRequest,
        response: Response,
        idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
    ) -> Accepted:
        """Check inference once, then start bounded load only if it passes.

        The extra first-case request can execute tools and incur cost; it is excluded
        from load metrics, profiling, and judging. Poll the run's preflight result
        for safe failure details. Idempotency-Key replays the same submission.

        \f
        Args:
            request: Validated target, nonempty workload, and optional reusable plan.
            response: Receives Location and the initial polling delay.
            idempotency_key: Optional key binding this exact request body to one run.

        Returns:
            The queued run or an existing submission matching the key and body.

        Raises:
            HTTPException: 422 for unsupported workload or target settings, 409 for
                conflicting keys, frozen inputs, or draining orphan workers, and
                429 while an owned run is active.

        Admission is serialized. Planning and persistence finish before the background
        task is created, so this 202 response is not a durable-queue acknowledgment.
        Default-on usage also accepts the legacy request hash that omitted this field;
        disabling usage changes the request and must conflict with that legacy key.
        """
        if not request.evaluation.samples:
            raise HTTPException(
                422, "Load requires samples; use evaluation-plans for description-only planning"
            )
        try:
            resolve_connection(request.target)
            for sample in request.evaluation.samples:
                payload(request, sample)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        async with submission:
            key_hash = fingerprint(idempotency_key) if idempotency_key else None
            request_body = request.model_dump(mode="json")
            request_hash = fingerprint(request_body)
            replay_hashes = {request_hash}
            if request.target.request_usage:
                legacy_body = {
                    **request_body,
                    "target": {
                        name: value
                        for name, value in request_body["target"].items()
                        if name != "request_usage"
                    },
                }
                replay_hashes.add(fingerprint(legacy_body))
            if key_hash:
                for prior in index.values():
                    if prior.get("idempotency_key_hash") == key_hash:
                        if prior["request_hash"] not in replay_hashes:
                            raise HTTPException(
                                409, "Idempotency-Key was used with a different body"
                            )
                        response.headers["Location"] = f"/v1/runs/{prior['id']}"
                        response.headers["Retry-After"] = "1"
                        prior = read_run(UUID(prior["id"]))
                        return Accepted(
                            id=prior["id"], status=prior["status"], url=response.headers["Location"]
                        )
            if tasks:
                raise HTTPException(
                    429, "One benchmark may run at a time", headers={"Retry-After": "5"}
                )
            if planning.locked():
                raise HTTPException(429, "Planning is active", headers={"Retry-After": "5"})
            for directory, pid in list(orphan_workers.items()):
                if (directory / "result.json").exists():
                    orphan_workers.pop(directory)
                    continue
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    orphan_workers.pop(directory)
            if orphan_workers:
                raise HTTPException(409, "A prior worker is draining after restart; retry later")
            if request.plan_id:
                try:
                    plan = await get_plan(UUID(request.plan_id))
                except ValueError as error:
                    raise HTTPException(422, "Invalid plan_id") from error
                if plan.evaluation_hash != fingerprint(request.evaluation.model_dump()):
                    raise HTTPException(
                        409, "Evaluation data or policy differs from the frozen plan"
                    )
            else:
                async with planning:
                    plan = await plan_or_error(request.evaluation)
                atomic_json(root / "plans" / f"{plan.id}.json", plan.model_dump())
            run_id = str(uuid4())
            runs[run_id] = {
                "id": run_id,
                "status": "queued",
                "load_status": "queued",
                "evaluation_status": "pending",
                "preflight": PreflightResult(status="pending").model_dump(),
                "config": request.model_dump(mode="json"),
                "plan": plan.model_dump(),
                "trace_coverage": "Internal spans are collected after load when explicitly configured.",
                "idempotency_key_hash": key_hash,
                "request_hash": request_hash,
            }
            cancellations[run_id] = asyncio.Event()
            persist(run_id)
            tasks[run_id] = asyncio.create_task(execute(run_id, request, plan))
            response.headers["Location"] = f"/v1/runs/{run_id}"
            response.headers["Retry-After"] = "1"
            return Accepted(id=run_id, status="queued", url=response.headers["Location"])

    @app.get("/v1/runs", response_model=RunPage, tags=["Runs"])
    async def list_runs(
        offset: Annotated[int, Query(ge=0, description="Zero-based history offset")] = 0,
        limit: Annotated[int, Query(ge=1, le=100, description="Maximum runs per page")] = 50,
        status: Annotated[
            str | None, Query(description="Optional exact lifecycle status filter")
        ] = None,
    ) -> RunPage:
        """List persisted local runs without exposing captured prompts or answers.

        \f
        Args:
            offset: Zero-based position in the filtered history.
            limit: Maximum summaries returned, bounded to 100.
            status: Optional exact overall lifecycle status.

        Returns:
            Compact summaries in UUID order and the total matching history size.
            Pagination bounds the response; the compact metadata index supplies
            filtering/counts without reading captured payloads.
        """
        items = []
        for run_id, run in sorted(index.items()):
            if status is None or run["status"] == status:
                items.append(
                    RunSummary(
                        id=str(run_id),
                        status=run["status"],
                        load_status=run["load_status"],
                        evaluation_status=run["evaluation_status"],
                        url=f"/v1/runs/{run_id}",
                    )
                )
        return RunPage(
            items=items[offset : offset + limit], offset=offset, limit=limit, total=len(items)
        )

    @app.get("/v1/runs/{run_id}", response_model=RunResponse, tags=["Runs"])
    async def get_run(run_id: UUID) -> RunResponse:
        """Read the inference check, separate phase outcomes, metrics, and frozen plan.

        \f
        Args:
            run_id: Identifier returned by run submission.

        Returns:
            A snapshot excluding captured request rows and internal idempotency hashes.
            Overall completion is a lifecycle outcome, not a passing quality verdict.

        Raises:
            HTTPException: 404 when the run does not exist.
        """
        run = read_run(run_id)
        return RunResponse.model_validate(
            {k: v for k, v in run.items() if k in RunResponse.model_fields}
        )

    @app.get("/v1/runs/{run_id}/requests", response_model=RequestPage, tags=["Runs"])
    async def get_requests(
        run_id: UUID,
        offset: Annotated[int, Query(ge=0, description="Zero-based record offset")] = 0,
        limit: Annotated[int, Query(ge=1, le=100, description="Maximum records per page")] = 50,
    ) -> RequestPage:
        """Page through captured responses; partial records remain available after interruption.

        \f
        Args:
            run_id: Identifier whose run snapshot and journal are inspected.
            offset: Zero-based attempt offset.
            limit: Maximum rows returned, bounded to 100.

        Returns:
            Known attempts and their total count. Active journal starts without
            completions are exposed as in_flight rather than failed attempts.

        Raises:
            HTTPException: 404 when the run does not exist.
        """
        run = read_run(run_id)
        rows = run.get("requests")
        if rows is None:
            rows, _ = recover_rows(
                root / str(run_id), interrupted=run["load_status"] not in {"queued", "running"}
            )
        return RequestPage(
            items=rows[offset : offset + limit], offset=offset, limit=limit, total=len(rows)
        )

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
        run = read_run(run_id)
        path = root / str(run_id) / "profiling.json"
        if run["load_status"] == "skipped":
            profiling = ProfilingSummary(
                total_requests=0,
                traced_requests=0,
                coverage=0,
                notes=[
                    "No load test was started. Preflight is excluded from metrics, profiles, and judging."
                ],
            )
        elif not path.exists():
            raise HTTPException(409, "Report profiling is not ready", headers={"Retry-After": "1"})
        else:
            profiling = ProfilingSummary.model_validate_json(path.read_text())
        order = root / str(run_id) / "profile-order.json"
        profiles = []
        if order.exists():
            identifiers = json.loads(order.read_text())
            for request_id in identifiers[offset : offset + limit]:
                profile_path = root / str(run_id) / "profiles" / f"{request_id}.json"
                profiles.append(RequestProfile.model_validate_json(profile_path.read_text()))
        else:
            rows = run.get("requests")
            if rows is None:
                rows, _ = recover_rows(root / str(run_id))
            profiles = [
                RequestProfile(
                    request_id=row["request_id"],
                    case_id=row.get("case_id", 0),
                    success=row["success"],
                    latency_ms=row.get("latency_ms"),
                    status="collection_failed",
                )
                for row in rows[offset : offset + limit]
            ]
        return RunReport(
            run=RunResponse.model_validate(
                {key: value for key, value in run.items() if key in RunResponse.model_fields}
            ),
            profiling=profiling,
            requests=profiles,
            offset=offset,
            limit=limit,
            total=profiling.total_requests,
        )

    @app.post("/v1/runs/{run_id}/cancel", response_model=Accepted, tags=["Runs"])
    async def cancel(run_id: UUID) -> Accepted:
        """Stop preflight/load dispatch and drain active requests; judging cancellation is unsupported.

        \f
        Args:
            run_id: Identifier of an API-owned run queued, preflighting, or loading.

        Returns:
            A cancellation_requested acknowledgment, not proof that drain is complete.

        Raises:
            HTTPException: 404 for an unknown run, or 409 outside cancellable load.
        """
        run = read_run(run_id)
        key = str(run_id)
        if key not in cancellations or run["status"] not in {"queued", "preflighting", "running"}:
            raise HTTPException(409, "Run is not in a cancellable load phase")
        cancellations[key].set()
        return Accepted(id=key, status="cancellation_requested", url=f"/v1/runs/{key}")

    install_schema(app)
    return app


app = create_app()
