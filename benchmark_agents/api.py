"""Single-process asynchronous REST API for reproducible local benchmarks."""

import asyncio
import hmac
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from openai import OpenAIError
from starlette.middleware.gzip import GZipMiddleware

from .connections import resolve_connection
from .evaluator import evaluate
from .locust_runner import run_load
from .models import (
    Accepted,
    ErrorResponse,
    Evaluation,
    Plan,
    RequestPage,
    RunPage,
    RunRequest,
    RunResponse,
    RunSummary,
)
from .openapi import install_schema
from .planner import create_plan, fingerprint
from .runner import payload
from .storage import atomic_json, recover_rows

ARTIFACTS = Path(os.getenv("BENCHMARK_ARTIFACT_DIR", "artifacts"))
api_key = APIKeyHeader(name="X-API-Key", auto_error=False)


async def authorize(request: Request, key: Annotated[str | None, Depends(api_key)]) -> None:
    """Allow unauthenticated loopback development; require a server key otherwise."""
    expected = os.getenv("BENCHMARK_API_KEY")
    if expected:
        if key is None or not hmac.compare_digest(key, expected):
            raise HTTPException(401, "Invalid or missing API key")
    elif not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "Configure BENCHMARK_API_KEY for non-loopback access")


async def plan_or_error(evaluation: Evaluation) -> Plan:
    """Translate provider failures into stable, credential-free HTTP errors."""
    try:
        return await create_plan(evaluation)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except OpenAIError as error:
        raise HTTPException(502, "Planner provider failed; check server configuration") from error


def create_app(artifact_dir: Path | None = None) -> FastAPI:
    """Create isolated application state. Run one API process per artifact directory."""
    root = artifact_dir or ARTIFACTS
    runs: dict[str, dict[str, Any]] = {}
    tasks: dict[str, asyncio.Task] = {}
    cancellations: dict[str, asyncio.Event] = {}
    orphan_workers: dict[Path, int] = {}
    submission = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        root.mkdir(parents=True, exist_ok=True)
        # Fail fast on accidental multi-worker deployment (local POSIX service).
        import fcntl

        with (root / ".service.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for worker_file in root.glob("*/worker.json"):
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
            422: "Invalid request",
            429: "Benchmark already active",
            502: "Planner provider failure",
        }.items()
    }
    app = FastAPI(
        title="EvalSurge",
        version="0.2.0",
        description="Benchmark one concurrency level, then evaluate captured answers with a frozen plan. "
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
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.middleware("http")
    async def request_metadata(request: Request, call_next: Any) -> Response:
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def error_body(request: Request, code: str, message: str) -> dict[str, Any]:
        return {"error": {"code": code, "message": message, "request_id": request.state.request_id}}

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return JSONResponse(
            error_body(request, f"http_{error.status_code}", str(error.detail)),
            status_code=error.status_code,
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # Do not echo submitted values, which can include private prompts.
        message = "; ".join(
            ".".join(str(x) for x in e["loc"]) + ": " + e["msg"] for e in error.errors()
        )
        return JSONResponse(error_body(request, "validation_error", message), status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(
            error_body(request, "internal_error", "Unexpected server error"), status_code=500
        )

    def persist(run_id: str) -> None:
        atomic_json(root / f"{run_id}.json", runs[run_id])

    def read_run(run_id: UUID) -> dict[str, Any]:
        key = str(run_id)
        if key in runs:
            return runs[key]
        path = root / f"{key}.json"
        if not path.exists():
            raise HTTPException(404, "Unknown run")
        result = json.loads(path.read_text())
        if result["status"] in {"queued", "running", "evaluating"}:
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

    async def execute(run_id: str, request: RunRequest, plan: Plan) -> None:
        run = runs[run_id]
        try:
            run.update(status="running", load_status="running")
            persist(run_id)
            rows, summary = await run_load(
                request, run_id, cancellations[run_id], artifact_dir=root
            )
            run.update(
                requests=rows, metrics=summary, load_status=summary.get("load_status", "completed")
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
                    run["evaluation"] = await asyncio.to_thread(
                        evaluate, rows, plan, request.evaluation
                    )
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
            if run["load_status"] == "running":
                run["load_status"] = "failed"
                run["requests"], _ = recover_rows(root / run_id)
            if run["evaluation_status"] == "pending":
                run["evaluation_status"] = "skipped"
        finally:
            persist(run_id)
            tasks.pop(run_id, None)
            cancellations.pop(run_id, None)

    @app.post("/v1/evaluation-plans", response_model=Plan, status_code=201, tags=["Plans"])
    async def evaluation_plan(evaluation: Evaluation, response: Response) -> Plan:
        """Persist scorer recommendations, evidence requirements, sampling policy, and judge model."""
        plan = await plan_or_error(evaluation)
        atomic_json(root / "plans" / f"{plan.id}.json", plan.model_dump())
        response.headers["Location"] = f"/v1/evaluation-plans/{plan.id}"
        return plan

    @app.get("/v1/evaluation-plans/{plan_id}", response_model=Plan, tags=["Plans"])
    async def get_plan(plan_id: UUID) -> Plan:
        """Retrieve a frozen plan for inspection and reuse in subsequent runs."""
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
        """Start a bounded benchmark. Idempotency-Key safely retries a submission with the same body."""
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
            request_hash = fingerprint(request.model_dump(mode="json"))
            if key_hash:
                for path in root.glob("*.json"):
                    prior = json.loads(path.read_text())
                    if prior.get("idempotency_key_hash") == key_hash:
                        if prior["request_hash"] != request_hash:
                            raise HTTPException(
                                409, "Idempotency-Key was used with a different body"
                            )
                        response.headers["Location"] = f"/v1/runs/{prior['id']}"
                        return Accepted(
                            id=prior["id"], status=prior["status"], url=response.headers["Location"]
                        )
            if tasks:
                raise HTTPException(
                    429, "One benchmark may run at a time", headers={"Retry-After": "5"}
                )
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
                plan = await plan_or_error(request.evaluation)
                atomic_json(root / "plans" / f"{plan.id}.json", plan.model_dump())
            run_id = str(uuid4())
            runs[run_id] = {
                "id": run_id,
                "status": "queued",
                "load_status": "queued",
                "evaluation_status": "pending",
                "config": request.model_dump(mode="json"),
                "plan": plan.model_dump(),
                "trace_coverage": "Client measurements only; internal trace ingestion is not implemented",
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
        """List persisted local runs without exposing captured prompts or answers."""
        items = []
        for path in sorted(root.glob("*.json")):
            try:
                run_id = UUID(path.stem)
            except ValueError:
                continue
            run = read_run(run_id)
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
        """Read separate load and evaluation statuses, metrics, and the frozen plan."""
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
        """Page through captured responses; partial records remain available after interruption."""
        run = read_run(run_id)
        rows = run.get("requests")
        if rows is None:
            rows, _ = recover_rows(
                root / str(run_id), interrupted=run["load_status"] not in {"queued", "running"}
            )
        return RequestPage(
            items=rows[offset : offset + limit], offset=offset, limit=limit, total=len(rows)
        )

    @app.post("/v1/runs/{run_id}/cancel", response_model=Accepted, tags=["Runs"])
    async def cancel(run_id: UUID) -> Accepted:
        """Stop dispatching requests and drain in-flight work; evaluation cancellation is unsupported."""
        run = read_run(run_id)
        key = str(run_id)
        if key not in cancellations or run["status"] == "evaluating":
            raise HTTPException(409, "Run is not in a cancellable load phase")
        cancellations[key].set()
        return Accepted(id=key, status="cancellation_requested", url=f"/v1/runs/{key}")

    install_schema(app)
    return app


app = create_app()
