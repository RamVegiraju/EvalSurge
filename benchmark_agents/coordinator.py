"""Single-owner run lifecycle shared by Python and REST; no HTTP dependencies."""

import asyncio
import copy
import fcntl
import json
import math
import os
from pathlib import Path
from typing import Any, TextIO
from uuid import UUID, uuid4

from openai import OpenAIError

from .adapters import InvalidInput
from .connections import Connection, resolve_connection, validate_connection
from .evaluation_errors import evaluation_error
from .evaluation_preflight import configuration_error, run_evaluation_preflight
from .evaluator import evaluate
from .limits import MAX_REQUEST_BYTES
from .locust_runner import preflight_result, run_load, run_preflight
from .models import (
    Accepted,
    Evaluation,
    EvaluationError,
    EvaluationPreflight,
    LoadError,
    Plan,
    PreflightError,
    PreflightResult,
    ProfilingPreflight,
    ProfilingReadinessError,
    ProfilingSummary,
    RequestPage,
    RequestProfile,
    RunPage,
    RunReport,
    RunRequest,
    RunResponse,
    RunSummary,
)
from .planner import PlannerResponseError, create_plan, fingerprint
from .profiling import PROFILE_NOTES, collect_profiles
from .report_links import experiment_links
from .runner import payload
from .storage import atomic_json, recover_rows
from .v2_models import RunStatus


class CoordinatorError(Exception):
    """Safe domain failure; REST maps status/headers to its existing envelope."""

    def __init__(
        self, status_code: int, message: str, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.headers = headers


class RunCoordinator:
    """Own one artifact directory and one active run on one asyncio event loop.

    Call open before use and close before discarding the loop. Instances are not
    thread-safe. Closing stops dispatch and drains owned work, including judging;
    it does not retract target actions or impose a hard deadline on scorer code.
    """

    def __init__(self, artifact_dir: Path) -> None:
        """Initialize independent state without acquiring storage or starting work.

        Args:
            artifact_dir: Operator-owned POSIX directory, resolved before use.
        """
        self.root = artifact_dir.resolve()
        self.runs: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.cancellations: dict[str, asyncio.Event] = {}
        self.orphan_workers: dict[Path, int] = {}
        self.submission = asyncio.Lock()
        self.planning = asyncio.Lock()
        self.index: dict[str, dict[str, Any]] = {}
        self._lock: TextIO | None = None
        self._closing = False
        self._shutdown = asyncio.Lock()
        self._volatile: set[str] = set()
        self._storage_failed = False

    async def open(self) -> None:
        """Acquire exclusive POSIX storage ownership and recover interrupted metadata.

        Raises:
            OSError: Storage or its nonblocking exclusive lock is unavailable.
            RuntimeError: This coordinator is already open.

        Recovery signals abandoned workers but never replays inference or resumes
        jobs. A failed initialization releases the lock before propagating.
        """
        if self._lock is not None or self._closing:
            raise RuntimeError("Coordinator is already open")
        self.root.mkdir(parents=True, exist_ok=True)
        lock = (self.root / ".service.lock").open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for snapshot in self.root.glob("*.json"):
                try:
                    key = str(UUID(snapshot.stem))
                except ValueError:
                    continue
                summary_path = self.root / "summaries" / snapshot.name
                stored = json.loads(snapshot.read_text())
                self.index[key] = {
                    field: stored.get(field)
                    for field in (
                        "id",
                        "status",
                        "load_status",
                        "evaluation_status",
                        "evaluation_mode",
                        "idempotency_key_hash",
                        "request_hash",
                    )
                }
                if (
                    stored.get("planning_status") in {"pending", "running"}
                    or self.index[key]["status"] == "preflighting"
                ):
                    self.index[key].update(
                        status="interrupted", load_status="skipped", evaluation_status="skipped"
                    )
                elif self.index[key]["status"] in {"queued", "running", "profiling", "evaluating"}:
                    self.index[key]["status"] = "interrupted"
                    for phase in ("load_status", "evaluation_status"):
                        if self.index[key][phase] in {"queued", "running", "pending"}:
                            self.index[key][phase] = "interrupted"
                atomic_json(summary_path, self.index[key])
            worker_files = [
                *self.root.glob("*/worker.json"),
                *self.root.glob("preflights/*/worker.json"),
            ]
            for worker_file in worker_files:
                directory = worker_file.parent
                if not (directory / "result.json").exists():
                    (directory / "cancel").touch(exist_ok=True)
                    self.orphan_workers[directory] = json.loads(worker_file.read_text())["pid"]
        except BaseException:
            lock.close()
            raise
        self._lock = lock

    async def close(self) -> None:
        """Stop admission, finish pending submissions/planning, drain, and unlock.

        Concurrent close calls serialize. Pending planners finish while storage is
        still owned; a submission cannot dispatch once shutdown has begun.
        Cancelling the close waiter does not release ownership before drain.
        """
        cleanup = asyncio.create_task(self._close_owned_work())
        cancelled = False
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                cancelled = True
        cleanup.result()
        if cancelled:
            raise asyncio.CancelledError

    async def _close_owned_work(self) -> None:
        """Serialize cleanup while preserving ownership until all writers finish."""
        async with self._shutdown:
            if self._lock is None:
                return
            self._closing = True
            try:
                async with self.submission:
                    for event in self.cancellations.values():
                        event.set()
                    if self.tasks:
                        await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
                    async with self.planning:
                        pass
            finally:
                self._lock.close()
                self._lock = None
                self._closing = False

    def _require_open(self) -> None:
        if self._lock is None or self._closing:
            raise RuntimeError("Coordinator is not open")

    def _persist(self, run_id: str) -> None:
        """Atomically snapshot owned state and compact idempotency/history metadata.

        Args:
            run_id: Identifier of an in-memory run owned by this instance.

        Raises:
            OSError: Local persistence fails; snapshots are not a disk-loss guarantee.
        """
        self._index_run(run_id)
        try:
            atomic_json(self.root / f"{run_id}.json", self.runs[run_id])
            atomic_json(self.root / "summaries" / f"{run_id}.json", self.index[run_id])
        except OSError:
            self._storage_failed = True
            raise

    def _index_run(self, run_id: str) -> None:
        """Keep in-process history truthful even when disk persistence fails."""
        self.index[run_id] = {
            key: self.runs[run_id].get(key)
            for key in (
                "id",
                "status",
                "load_status",
                "evaluation_status",
                "evaluation_mode",
                "idempotency_key_hash",
                "request_hash",
            )
        }

    def _require_storage(self) -> None:
        if self._storage_failed:
            raise CoordinatorError(
                500, "Artifact persistence failed; restore storage and restart the runner"
            )

    def _persist_plan(self, plan: Plan) -> None:
        """Persist a frozen plan before scheduling any agent traffic.

        Args:
            plan: Completed frozen plan whose planning may already have incurred cost.

        Raises:
            CoordinatorError: Persistence failed; new planning/admission stops until restart.
        """
        try:
            atomic_json(self.root / "plans" / f"{plan.id}.json", plan.model_dump())
        except OSError as error:
            self._storage_failed = True
            raise CoordinatorError(
                500,
                "Evaluation plan could not be persisted; no agent preflight or load was started",
            ) from error

    @staticmethod
    def _check_size(request: RunRequest | Evaluation) -> None:
        """Bound the UTF-8 serialized policy/workload before copying or planning."""
        try:
            size = len(request.model_dump_json().encode("utf-8"))
        except ValueError:
            raise CoordinatorError(422, "Workload must contain JSON-serializable values") from None
        if size > MAX_REQUEST_BYTES:
            raise CoordinatorError(413, "Request body exceeds the eight-megabyte limit")

    def read_run(self, run_id: UUID) -> dict[str, Any]:
        """Read detached state for shared presentation without exposing mutable ownership.

        Args:
            run_id: Existing local resource identifier.

        Returns:
            Independent protected state; callers must not publish operator fields.

        Raises:
            CoordinatorError: No run exists.
            RuntimeError: Storage is not owned or is closing.

        Recovery follows existing behavior and never reinvokes a target.
        """
        return copy.deepcopy(self._read_run(run_id))

    def read_status(self, run_id: UUID) -> RunStatus:
        """Project detached content-free status without copying protected run payloads.

        Args:
            run_id: Existing resource in this coordinator's owned artifact store.

        Returns:
            Typed lifecycle and independent phases; no case, request or report rows.

        Raises:
            CoordinatorError: Run is unknown or persisted metadata is unavailable.
            RuntimeError: Storage is not owned or is closing.

        Active runs use in-memory state. Historical cache misses retain the existing
        snapshot read; this does not implement an indexed metadata store.
        """
        from .run_views import status_view

        return status_view(self._read_run(run_id))

    def _read_run(self, run_id: UUID) -> dict[str, Any]:
        """Read owned state or recover an abandoned snapshot without replaying actions.

        Args:
            run_id: Validated local resource identifier.

        Returns:
            Internal mutable state, or an interrupted recovered snapshot. Public
            getters detach this result before returning it to callers.

        Raises:
            CoordinatorError: No run exists.
            RuntimeError: Storage is not owned or is closing.

        Recovery may create a cancellation marker, never another target invocation.
        """
        self._require_open()
        key = str(run_id)
        if key in self.runs:
            return self.runs[key]
        path = self.root / f"{key}.json"
        if not path.exists():
            raise CoordinatorError(404, "Unknown run")
        result = json.loads(path.read_text())
        if result.get("planning_status") in {"pending", "running"}:
            result.update(
                status="interrupted",
                planning_status="interrupted",
                load_status="skipped",
                evaluation_status="skipped",
                profiling_status="skipped",
                preflight=PreflightResult(status="not_run").model_dump(),
                evaluation_preflight=EvaluationPreflight(status="not_run").model_dump(),
                profiling_preflight=ProfilingPreflight(status="not_run").model_dump(),
            )
        if result["status"] == "preflighting":
            probe_root = self.root / "preflights" / key
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
            readiness = result.get("evaluation_preflight", {})
            if readiness.get("status") in {"pending", "running"}:
                result["evaluation_preflight"] = {
                    **readiness,
                    "status": "interrupted",
                }
            profile_check = result.get("profiling_preflight", {})
            if profile_check.get("status") in {"pending", "running"}:
                result["profiling_preflight"] = {**profile_check, "status": "interrupted"}
        elif result["status"] in {"queued", "running", "profiling", "evaluating"}:
            result["status"] = "interrupted"
            profile_check = result.get("profiling_preflight", {})
            if profile_check.get("status") in {"pending", "running"}:
                result["profiling_preflight"] = {**profile_check, "status": "interrupted"}
            readiness = result.get("evaluation_preflight", {})
            if readiness.get("status") in {"pending", "running"}:
                result["evaluation_preflight"] = {**readiness, "status": "interrupted"}
            if result["load_status"] in {"queued", "running"}:
                result["load_status"] = "interrupted"
                if (self.root / key).exists():
                    (self.root / key / "cancel").touch(exist_ok=True)
                result["requests"], _ = recover_rows(self.root / key)
            if result["evaluation_status"] in {"pending", "running"}:
                result["evaluation_status"] = "interrupted"
        if result["load_status"] == "interrupted":
            result["requests"], _ = recover_rows(self.root / key)
            recovered = self.root / key / "result.json"
            if recovered.exists():
                result["metrics"] = json.loads(recovered.read_text())["summary"]
                result["metrics"]["measurement_complete"] = False
        return result

    async def _create_plan(self, evaluation: Evaluation) -> Plan:
        """Translate recognized planning failures into content-free domain errors.

        Args:
            evaluation: Validated policy and user-supplied evidence.

        Returns:
            Unpersisted frozen plan.

        Raises:
            CoordinatorError: Invalid input/configuration or upstream planner failure.
        """
        try:
            return await create_plan(evaluation)
        except PlannerResponseError as error:
            raise CoordinatorError(502, "Planner returned an invalid recommendation") from error
        except ValueError as error:
            raise CoordinatorError(
                422, "Invalid evaluation or server planning configuration"
            ) from error
        except OpenAIError as error:
            raise CoordinatorError(
                502, "Planner provider failed; check server configuration"
            ) from error

    async def evaluation_plan(self, evaluation: Evaluation) -> Plan:
        """Freeze and persist an evaluation plan; may invoke the configured planner.

        Args:
            evaluation: Criteria, evidence, and optional explicit scorer selections.

        Returns:
            Persisted plan ready for inspection and exact-input reuse.

        Raises:
            CoordinatorError: Planning/run admission is busy or planning fails.
        """
        self._require_open()
        self._require_storage()
        self._check_size(evaluation)
        if self.planning.locked() or self.tasks or self.submission.locked():
            raise CoordinatorError(429, "Planning or a benchmark is active", {"Retry-After": "5"})
        async with self.planning:
            plan = await self._create_plan(evaluation.model_copy(deep=True))
            self._persist_plan(plan)
        return plan

    def get_plan(self, plan_id: UUID) -> Plan:
        """Read a frozen plan.

        Args:
            plan_id: Resource identifier returned by plan creation.

        Returns:
            Detached validated plan.

        Raises:
            CoordinatorError: No persisted plan exists.
        """
        self._require_open()
        path = self.root / "plans" / f"{plan_id}.json"
        if not path.exists():
            raise CoordinatorError(404, "Unknown evaluation plan")
        return Plan.model_validate_json(path.read_text())

    async def submit(
        self,
        request: RunRequest,
        idempotency_key: str | None = None,
        *,
        connection: Connection | None = None,
        defer_planning: bool = False,
        submission_hash: str | None = None,
        name: str | None = None,
        evaluation_mode: str | None = None,
    ) -> Accepted:
        """Validate, freeze, persist, and schedule one run; never infer inline.

        Args:
            request: Bounded workload, target, and optional frozen-plan reference.
            idempotency_key: At most 128 characters binding this body to a run.
            connection: Trusted local operator binding, not exposed by REST.
                Otherwise resolve the existing server-owned environment policy.
            defer_planning: Persist admission and plan inside the owned run task.
            submission_hash: Trusted canonical v2 body hash for idempotency.
            name: Bounded v2 display name, independent of evaluation inputs.
            evaluation_mode: Explicit v2 evaluation policy for result presentation.

        Returns:
            Queued acknowledgment or the original matching idempotent submission.

        Raises:
            CoordinatorError: Safe input, admission, plan, or idempotency conflict.

        Input and resolved connection are copied before scheduling, so caller
        mutation cannot alter admitted work. Secrets remain environment references.
        """
        self._require_open()
        self._check_size(request)
        request = RunRequest.model_validate(request.model_dump(mode="json"))
        if idempotency_key is not None and len(idempotency_key) > 128:
            raise CoordinatorError(422, "Idempotency-Key exceeds 128 characters")
        if not request.evaluation.samples:
            raise CoordinatorError(
                422, "Load requires samples; use evaluation-plans for description-only planning"
            )
        try:
            binding = (
                validate_connection(request.target, connection)
                if connection is not None
                else resolve_connection(request.target)
            )
            for sample in request.evaluation.samples:
                payload(request, sample)
        except InvalidInput as error:
            raise CoordinatorError(422, str(error)) from error
        except ValueError as error:
            raise CoordinatorError(422, "Invalid target connection or workload envelope") from error
        async with self.submission:
            self._require_open()
            key_hash = fingerprint(idempotency_key) if idempotency_key else None
            request_body = request.model_dump(mode="json")
            request_hash = submission_hash or fingerprint(request_body)
            replay_hashes = {request_hash}
            if (
                submission_hash is None
                and not request.target.session_id
                and not request.target.session_per_request
            ):
                old_body = {
                    **request_body,
                    "target": {
                        name: value
                        for name, value in request_body["target"].items()
                        if name not in {"session_id", "session_per_request"}
                    },
                }
                replay_hashes.add(fingerprint(old_body))
                if request.target.request_usage:
                    replay_hashes.add(
                        fingerprint(
                            {
                                **old_body,
                                "target": {
                                    name: value
                                    for name, value in old_body["target"].items()
                                    if name != "request_usage"
                                },
                            }
                        )
                    )
            if request.target.request_usage and submission_hash is None:
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
                for prior in self.index.values():
                    if prior.get("idempotency_key_hash") == key_hash:
                        if prior["request_hash"] not in replay_hashes:
                            raise CoordinatorError(
                                409, "Idempotency-Key was used with a different body"
                            )
                        stored = self._read_run(UUID(prior["id"]))
                        return Accepted(
                            id=stored["id"], status=stored["status"], url=f"/v1/runs/{stored['id']}"
                        )
            self._require_storage()
            if self.tasks:
                raise CoordinatorError(429, "One benchmark may run at a time", {"Retry-After": "5"})
            if self.planning.locked():
                raise CoordinatorError(429, "Planning is active", {"Retry-After": "5"})
            for directory, pid in list(self.orphan_workers.items()):
                if (directory / "result.json").exists():
                    self.orphan_workers.pop(directory)
                    continue
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    self.orphan_workers.pop(directory)
            if self.orphan_workers:
                raise CoordinatorError(409, "A prior worker is draining after restart; retry later")
            plan = None
            if request.plan_id:
                try:
                    plan = self.get_plan(UUID(request.plan_id))
                except ValueError as error:
                    raise CoordinatorError(422, "Invalid plan_id") from error
                if plan.evaluation_hash != fingerprint(request.evaluation.model_dump()):
                    raise CoordinatorError(
                        409, "Evaluation data or policy differs from the frozen plan"
                    )
            elif not defer_planning:
                async with self.planning:
                    plan = await self._create_plan(request.evaluation)
                self._persist_plan(plan)
            self._require_open()
            run_id = str(uuid4())
            self.runs[run_id] = {
                "id": run_id,
                "status": "queued",
                "load_status": "queued",
                "evaluation_status": "pending",
                "preflight": PreflightResult(status="pending").model_dump(),
                "evaluation_preflight": EvaluationPreflight(status="pending").model_dump(),
                "profiling_preflight": ProfilingPreflight(status="pending").model_dump(),
                "config": request.model_dump(mode="json"),
                "plan": plan.model_dump() if plan else None,
                "planning_status": "pending" if plan is None else "completed",
                "name": name,
                "evaluation_mode": evaluation_mode,
                "trace_coverage": "Internal spans are collected after load when explicitly configured.",
                "idempotency_key_hash": key_hash,
                "request_hash": request_hash,
            }
            self.cancellations[run_id] = asyncio.Event()
            try:
                self._persist(run_id)
            except OSError as error:
                self._storage_failed = True
                self.cancellations.pop(run_id, None)
                if (self.root / f"{run_id}.json").exists():
                    self.runs[run_id].update(
                        status="failed",
                        load_status="skipped",
                        evaluation_status="skipped",
                        profiling_status="skipped",
                        preflight=PreflightResult(status="not_run").model_dump(),
                        requests=[],
                        error_type="PersistenceFailed",
                    )
                    self._volatile.add(run_id)
                    self._index_run(run_id)
                else:
                    self.runs.pop(run_id, None)
                    self.index.pop(run_id, None)
                raise CoordinatorError(
                    500,
                    "Run admission could not be persisted; no agent preflight or load was started",
                ) from error
            self.tasks[run_id] = asyncio.create_task(self._execute(run_id, request, plan, binding))
            return Accepted(id=run_id, status="queued", url=f"/v1/runs/{run_id}")

    def _skip_load(self, run_id: str, status: str) -> None:
        """Retain a zero-load failure report, excluding all probe contents."""
        self.runs[run_id].update(
            status=status,
            load_status="skipped",
            evaluation_status="skipped",
            profiling_status="skipped",
            requests=[],
            trace_coverage="No measured load requests; pre-load checks did not permit load.",
        )
        if self.runs[run_id]["preflight"]["status"] == "pending":
            self.runs[run_id]["preflight"] = PreflightResult(status="not_run").model_dump()
        if self.runs[run_id]["evaluation_preflight"]["status"] == "pending":
            self.runs[run_id]["evaluation_preflight"] = EvaluationPreflight(
                status="not_run"
            ).model_dump()
        if self.runs[run_id].get("profiling_preflight", {}).get("status") == "pending":
            self.runs[run_id]["profiling_preflight"] = ProfilingPreflight(
                status="not_run"
            ).model_dump()
        profiling = ProfilingSummary(
            total_requests=0,
            traced_requests=0,
            coverage=0,
            notes=[
                "No load test was started. Readiness probes are excluded from measured metrics and quality results."
            ],
        )
        atomic_json(self.root / run_id / "profiling.json", profiling.model_dump())

    async def _probe_readiness(
        self,
        run_id: str,
        plan: Plan,
        row: dict[str, Any],
        verified_traces: dict[str, Any] | None = None,
    ) -> EvaluationPreflight:
        """Check selected judges against one protected, already captured probe.

        Args:
            run_id: Admitted run's correlation identifier.
            plan: Frozen scorer definitions and operator-owned evidence scope.
            row: Successful excluded probe record, never a measured attempt.
            verified_traces: Optional scoped traces already checked independently
                of judges; reuse avoids duplicate collector work.

        Returns:
            Readiness execution state, independent of the assessment's quality.

        Required trace-collection failures return safe readiness errors and do
        not execute judges; the caller retains the failed phase and skips load.
        Only trace-required registered judges cause probe trace reads. Collection
        writes content-free readiness artifacts; selected judges may incur their
        separately configured model calls. The target is never invoked here.
        Trace collection runs in a thread without a hard execution deadline.
        Native judging owns a separately bounded/cancellable child process;
        trusted scorer code is not a sandbox and committed calls cannot be undone.
        """
        probe_traces = verified_traces or {}
        trace_scorers = [
            item for item in plan.registered_scorers if "trace" in item.required_fields
        ]
        if trace_scorers and verified_traces is None:
            try:
                _coverage, probe_traces = await asyncio.to_thread(
                    collect_profiles,
                    [row],
                    run_id,
                    plan.trace_source.model_copy(update={"max_traces": 1})
                    if plan.trace_source
                    else None,
                    self.root / "preflights" / run_id / "readiness-profiles",
                )
            except Exception:  # noqa: BLE001
                return EvaluationPreflight(
                    status="failed",
                    error=EvaluationError(
                        code="evaluation_trace_collection_failed",
                        message="Required inference-probe trace evidence could not be collected.",
                        guidance="Check operator trace-store access, exact experiment/correlation scope, and readiness artifact storage before a new run. Load did not start.",
                        scorer=f"registered:{trace_scorers[0].alias}",
                    ),
                )
        return await asyncio.to_thread(
            run_evaluation_preflight,
            row,
            plan,
            probe_traces,
            cancellation=self.cancellations[run_id],
        )

    async def _profiling_readiness(
        self, run_id: str, plan: Plan, row: dict[str, Any]
    ) -> tuple[ProfilingReadinessError | None, dict[str, Any]]:
        """Verify the excluded probe's actual trace independently of evaluation.

        Args:
            run_id: Exact admitted benchmark UUID.
            plan: Frozen operator trace scope and collection limits.
            row: Captured successful excluded inference probe, not a measured row.

        Returns:
            Safe readiness failure or None, plus verified native Trace objects for
            reuse by selected trace-dependent judges. Disabled tracing does no read.

        Side Effects:
            Configured tracing reads only the returned trace ID under exact
            experiment/run/request checks, then writes protected content-free
            probe profiles. No target, planner or judge is invoked. Bounded
            collector retries stay outside measured load; remote transport
            timeouts remain operator-owned rather than a hard thread deadline.
        """
        if plan.trace_source is None:
            return None, {}
        try:
            coverage, traces = await asyncio.to_thread(
                collect_profiles,
                [row],
                run_id,
                plan.trace_source.model_copy(update={"max_traces": 1}),
                self.root / "preflights" / run_id / "readiness-profiles",
            )
        except Exception:  # noqa: BLE001 - fixed guidance excludes trace-store/provider details
            return ProfilingReadinessError(
                code="trace_readiness_failed",
                message="Inference completed, but its configured trace could not be collected. "
                "Check operator tracking-store access and transport timeouts; load did not start.",
            ), {}
        if coverage.traced_requests != 1 or row["request_id"] not in traces:
            if coverage.gaps.get("unsupported_scope"):
                return ProfilingReadinessError(
                    message="Inference completed, but the configured UC trace scope cannot "
                    "yet be verified; load did not start.",
                    guidance="Governed Unity Catalog IDs are retained, but experiment scope "
                    "must be verified before collecting them. Do not silently switch to "
                    "legacy storage; use an explicitly supported trace scope or wait for "
                    "reviewed UC scope support.",
                ), {}
            return ProfilingReadinessError(
                code="trace_readiness_failed",
                message="Inference completed, but a complete correlated trace was unavailable. "
                "Enable agent-side export, return its real trace ID, and attach exact benchmark "
                "run/request metadata in an authorized experiment. Check sampling and export "
                "lag; load did not start.",
            ), {}
        return None, traces

    def _fail_profiling_readiness(
        self, run_id: str, request_id: str, error: ProfilingReadinessError
    ) -> None:
        """Skip load for missing probe evidence without changing inference success.

        Args:
            run_id: Admitted run whose successful excluded probe is retained.
            request_id: That probe's exact request correlation ID.
            error: Fixed content-free trace readiness guidance.

        Side Effects:
            Stores independent failed profiling readiness and a zero-load profile
            shell. Selected judges are not run; raw probe input/output is excluded.
        """
        run = self.runs[run_id]
        run["profiling_preflight"] = ProfilingPreflight(
            status="failed", request_id=request_id, error=error
        ).model_dump()
        if run["evaluation_preflight"]["status"] == "running":
            run["evaluation_preflight"] = EvaluationPreflight(status="not_run").model_dump()
        self._skip_load(run_id, "failed")
        run["profiling_status"] = "failed"

    async def _execute(
        self, run_id: str, request: RunRequest, plan: Plan | None, connection: Connection
    ) -> None:
        """Advance one owned run; preserve independent evidence at job boundaries.

        Args:
            run_id: Identifier already admitted and durably snapshotted.
            request: Detached bounded target/workload settings.
            plan: Persisted frozen evaluation policy, or None for deferred planning.
            connection: Detached exact operator binding used by both workers.

        Only passed inference and selected-judge readiness checks permit load.
        Readiness reuses the excluded probe; profiling and quality scoring follow
        the measured window without reinvoking the target. Ordinary job failures
        become safe terminal reports with independent evidence.
        Final persistence always releases in-memory task/cancellation ownership.
        """
        run = self.runs[run_id]
        cancel = self.cancellations[run_id]
        try:
            if plan is None:
                if cancel.is_set():
                    run["planning_status"] = "cancelled"
                    self._skip_load(run_id, "cancelled")
                    return
                run["planning_status"] = "running"
                self._persist(run_id)
                try:
                    async with self.planning:
                        plan = await self._create_plan(request.evaluation)
                    self._persist_plan(plan)
                except Exception:  # noqa: BLE001
                    run["planning_status"] = "failed"
                    run["planning_error"] = {
                        "code": "planning_failed",
                        "message": "Evaluation planning could not complete.",
                        "guidance": "Check operator provider and scorer configuration before a new run.",
                    }
                    run["preflight"] = PreflightResult(status="not_run").model_dump()
                    self._skip_load(run_id, "failed")
                    return
                run["plan"] = plan.model_dump()
                run["planning_status"] = "completed"
                self._persist(run_id)
            run.update(status="preflighting")
            if cancel.is_set():
                run["evaluation_preflight"] = EvaluationPreflight(status="cancelled").model_dump()
                self._skip_load(run_id, "cancelled")
                return
            run["evaluation_preflight"] = EvaluationPreflight(
                status="running" if plan.recommendations or plan.source == "llm" else "skipped"
            ).model_dump()
            self._persist(run_id)
            setup_error = await asyncio.to_thread(
                configuration_error, plan, request.evaluation.samples[0]
            )
            if setup_error is not None:
                run["evaluation_preflight"] = EvaluationPreflight(
                    status="failed", error=setup_error
                ).model_dump()
                run["preflight"] = PreflightResult(status="not_run").model_dump()
                self._skip_load(run_id, "failed")
                run["evaluation_status"] = "failed"
                run["evaluation"] = {"status": "failed", "error": setup_error.model_dump()}
                return
            run.update(
                status="preflighting", preflight=PreflightResult(status="running").model_dump()
            )
            self._persist(run_id)
            probe = await run_preflight(
                request, run_id, cancel, artifact_dir=self.root, connection=connection
            )
            run["preflight"] = probe.model_dump()
            if probe.status != "passed" or cancel.is_set():
                status = (
                    "cancelled"
                    if cancel.is_set() or probe.status == "cancelled"
                    else "interrupted"
                    if probe.status == "interrupted"
                    else "failed"
                )
                if status == "failed":
                    run["error_type"] = "PreflightFailed"
                self._skip_load(run_id, status)
                if run["evaluation_preflight"]["status"] == "running":
                    run["evaluation_preflight"]["status"] = (
                        "cancelled" if cancel.is_set() else "not_run"
                    )
                return
            if plan.trace_source or plan.recommendations:
                probe_rows, _ = recover_rows(self.root / "preflights" / run_id)
                if len(probe_rows) != 1 or not probe_rows[0].get("success"):
                    raise RuntimeError("Successful inference probe capture is unavailable")
                run["profiling_preflight"] = ProfilingPreflight(
                    status="running" if plan.trace_source else "skipped",
                    request_id=probe_rows[0]["request_id"],
                ).model_dump()
                self._persist(run_id)
                trace_error, verified_traces = await self._profiling_readiness(
                    run_id, plan, probe_rows[0]
                )
                if cancel.is_set():
                    if plan.trace_source:
                        run["profiling_preflight"]["status"] = "cancelled"
                    if run["evaluation_preflight"]["status"] == "running":
                        run["evaluation_preflight"] = EvaluationPreflight(
                            status="cancelled"
                        ).model_dump()
                    self._skip_load(run_id, "cancelled")
                    return
                if trace_error is not None:
                    self._fail_profiling_readiness(run_id, probe_rows[0]["request_id"], trace_error)
                    return
                if plan.trace_source:
                    run["profiling_preflight"]["status"] = "passed"
            else:
                run["profiling_preflight"] = ProfilingPreflight(status="skipped").model_dump()
            if plan.recommendations:
                checked = await self._probe_readiness(
                    run_id, plan, probe_rows[0], verified_traces if plan.trace_source else None
                )
                run["evaluation_preflight"] = checked.model_dump()
                atomic_json(
                    self.root / "preflights" / run_id / "evaluation.json", checked.model_dump()
                )
                self._persist(run_id)
                if checked.status != "passed" or cancel.is_set():
                    self._skip_load(run_id, "cancelled" if cancel.is_set() else "failed")
                    if checked.error is not None:
                        run["evaluation_status"] = "failed"
                        run["evaluation"] = {
                            "status": "failed",
                            "error": checked.error.model_dump(),
                        }
                    return
            if cancel.is_set():
                self._skip_load(run_id, "cancelled")
                return
            run.update(status="running", load_status="running")
            self._persist(run_id)
            rows, summary = await run_load(
                request, run_id, cancel, artifact_dir=self.root, connection=connection
            )
            run.update(
                requests=rows,
                metrics=summary,
                load_status=summary.get("load_status", "completed"),
                status="profiling",
            )
            if run["load_status"] != "completed" and not cancel.is_set():
                run["load_error"] = LoadError(
                    code="worker_timeout" if summary.get("worker_timed_out") else "worker_failed",
                    message="The load worker did not produce complete measurements.",
                    guidance="Check protected worker logs, process exit status, and the runner environment before retrying.",
                ).model_dump()
            self._persist(run_id)
            try:
                profiling, traces = await asyncio.to_thread(
                    collect_profiles, rows, run_id, plan.trace_source, self.root / run_id
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
                atomic_json(self.root / run_id / "profiling.json", profiling.model_dump())
            run["trace_coverage"] = (
                f"{profiling.traced_requests}/{profiling.total_requests} attempts have "
                "correlated internal spans; remaining attempts are client-only."
            )
            if run["load_status"] != "completed" or cancel.is_set():
                run.update(
                    status="cancelled" if cancel.is_set() else "interrupted",
                    evaluation_status="skipped",
                )
            else:
                run.update(status="evaluating", evaluation_status="running")
                self._persist(run_id)
                try:
                    run["evaluation"] = await asyncio.to_thread(
                        evaluate, rows, plan, traces, cancellation=cancel
                    )
                except Exception as error:  # noqa: BLE001
                    run["evaluation"] = {
                        "status": "failed",
                        "error_type": type(error).__name__,
                        "error": evaluation_error(error).model_dump(),
                    }
                run["evaluation_status"] = run["evaluation"]["status"]
                run["status"] = (
                    "completed"
                    if run["evaluation_status"] == "completed"
                    or (not plan.recommendations and request.evaluation.scorers == [])
                    else "completed_with_gaps"
                )
        except Exception as error:  # noqa: BLE001
            run.update(status="failed", error_type=type(error).__name__)
            if run["preflight"]["status"] == "running":
                run["preflight"] = PreflightResult(
                    status="failed",
                    error=PreflightError(
                        code="worker_failed",
                        message="Inference preflight failed. Load test did not start. Check server worker configuration.",
                    ),
                ).model_dump()
                self._skip_load(run_id, "failed")
                if run["evaluation_preflight"]["status"] == "running":
                    run["evaluation_preflight"]["status"] = "not_run"
            if run["load_status"] == "running":
                run["load_status"] = "failed"
                run["load_error"] = LoadError(
                    code="worker_start_failed" if isinstance(error, OSError) else "worker_failed",
                    message="The load worker could not start or complete.",
                    guidance="Check the runner Python environment, Locust installation, process permissions, and protected worker logs.",
                ).model_dump()
                try:
                    run["requests"], _ = recover_rows(self.root / run_id)
                except OSError:
                    run["requests"] = []
                    self._storage_failed = True
            if run["evaluation_status"] == "pending":
                run["evaluation_status"] = "skipped"
            if run["evaluation_preflight"]["status"] == "running":
                self._skip_load(run_id, "failed")
                run["evaluation_preflight"] = EvaluationPreflight(
                    status="failed", error=evaluation_error(error)
                ).model_dump()
                run["evaluation_status"] = "failed"
                run["evaluation"] = {
                    "status": "failed",
                    "error": evaluation_error(error).model_dump(),
                }
            profile_path = self.root / run_id / "profiling.json"
            if not profile_path.exists():
                rows = run.get("requests", [])
                run["profiling_status"] = "failed"
                profiling = ProfilingSummary(
                    total_requests=len(rows),
                    traced_requests=0,
                    coverage=0,
                    gaps={"collection_failed": len(rows)},
                    notes=[
                        *PROFILE_NOTES,
                        "Run processing failed; no internal profiles are available.",
                    ],
                )
                try:
                    atomic_json(profile_path, profiling.model_dump())
                except OSError:
                    self._storage_failed = True
        finally:
            persisted = False
            try:
                self._persist(run_id)
                persisted = True
            except OSError:
                self._storage_failed = True
                self._volatile.add(run_id)
            finally:
                self.tasks.pop(run_id, None)
                self.cancellations.pop(run_id, None)
                if persisted:
                    self.runs.pop(run_id, None)

    @staticmethod
    def _page_bounds(offset: int, limit: int) -> None:
        if offset < 0 or not 1 <= limit <= 100:
            raise CoordinatorError(422, "Page requires offset >= 0 and 1 <= limit <= 100")

    def list_runs(self, offset: int = 0, limit: int = 50, status: str | None = None) -> RunPage:
        """Page compact history without captured prompts/answers; UUID ordering.

        Args:
            offset: Zero-based filtered history offset.
            limit: Maximum summaries, from 1 to 100.
            status: Optional exact lifecycle status filter.

        Returns:
            Bounded summaries and total matching resources.
        """
        self._require_open()
        self._page_bounds(offset, limit)
        items = [
            RunSummary(
                id=run_id,
                status=run["status"],
                load_status=run["load_status"],
                evaluation_status=run["evaluation_status"],
                url=f"/{'v2' if run.get('evaluation_mode') is not None else 'v1'}/runs/{run_id}",
            )
            for run_id, run in sorted(self.index.items())
            if status is None or run["status"] == status
        ]
        return RunPage(
            items=items[offset : offset + limit], offset=offset, limit=limit, total=len(items)
        )

    def get_run(self, run_id: UUID) -> RunResponse:
        """Return a detached snapshot excluding raw captures/internal hashes.

        Args:
            run_id: Existing local resource identifier.

        Returns:
            Independent phase outcomes, metrics, frozen policy, and protected
            judge rationales that may quote captured request contents.

        Raises:
            CoordinatorError: No run exists.
        """
        run = self._read_run(run_id)
        if run.get("plan") is None:
            raise CoordinatorError(409, "Evaluation plan is not available", {"Retry-After": "1"})
        return RunResponse.model_validate(
            {key: value for key, value in run.items() if key in RunResponse.model_fields}
        ).model_copy(deep=True)

    def get_requests(self, run_id: UUID, offset: int = 0, limit: int = 50) -> RequestPage:
        """Page captures in start order; unfinished active attempts remain in_flight.

        Args:
            run_id: Existing local resource identifier.
            offset: Zero-based attempt offset.
            limit: Maximum sensitive captured records, from 1 to 100.

        Returns:
            Detached captures and total attempt count.
        """
        self._page_bounds(offset, limit)
        run = self._read_run(run_id)
        rows = run.get("requests")
        if rows is None:
            rows, _ = recover_rows(
                self.root / str(run_id), interrupted=run["load_status"] not in {"queued", "running"}
            )
        return RequestPage(
            items=rows[offset : offset + limit], offset=offset, limit=limit, total=len(rows)
        ).model_copy(deep=True)

    def get_report(self, run_id: UUID, offset: int = 0, limit: int = 25) -> RunReport:
        """Join detached metrics, quality policy, and bounded content-free profiles.

        Args:
            run_id: Existing local resource identifier.
            offset: Zero-based heatmap/profile offset.
            limit: Maximum profiles, from 1 to 100.

        Returns:
            One report page; times are agent-relative milliseconds and gaps remain
            explicit. The result never embeds raw source traces.

        Raises:
            CoordinatorError: Unknown run, invalid page, or profiling not yet ready.
        """
        self._page_bounds(offset, limit)
        run = self._read_run(run_id)
        path = self.root / str(run_id) / "profiling.json"
        if run["load_status"] == "skipped":
            profiling = ProfilingSummary(
                total_requests=0,
                traced_requests=0,
                coverage=0,
                notes=[
                    "No load test was started. The inference probe and judge-readiness checks are excluded from benchmark metrics, profiles, and quality results."
                ],
            )
        elif not path.exists():
            if run["status"] in {"queued", "preflighting", "running", "profiling", "evaluating"}:
                raise CoordinatorError(409, "Report profiling is not ready", {"Retry-After": "1"})
            rows = run.get("requests")
            if rows is None:
                rows, _ = recover_rows(self.root / str(run_id))
            profiling = ProfilingSummary(
                total_requests=len(rows),
                traced_requests=0,
                coverage=0,
                gaps={"collection_failed": len(rows)},
                notes=[
                    *PROFILE_NOTES,
                    "Profiling artifacts are unavailable for this terminal run; internal timing is unknown.",
                ],
            )
        else:
            profiling = ProfilingSummary.model_validate_json(path.read_text())
        if str(run_id) in self._volatile:
            profiling.notes.append(
                "Final state could not be persisted. This in-process result may be lost on restart."
            )
        order = self.root / str(run_id) / "profile-order.json"
        profiles = []
        if path.exists() and order.exists():
            identifiers = json.loads(order.read_text())
            for request_id in identifiers[offset : offset + limit]:
                profile_path = self.root / str(run_id) / "profiles" / f"{request_id}.json"
                profiles.append(RequestProfile.model_validate_json(profile_path.read_text()))
        else:
            rows = run.get("requests")
            if rows is None:
                rows, _ = recover_rows(self.root / str(run_id))
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
        response = self.get_run(run_id)
        return RunReport(
            run=response,
            profiling=profiling,
            requests=profiles,
            offset=offset,
            limit=limit,
            total=profiling.total_requests,
            mlflow_experiments=experiment_links(response.plan, response.evaluation),
        )

    def cancel(self, run_id: UUID) -> Accepted:
        """Stop preflight/load dispatch and drain; judging cancellation is unsupported.

        Args:
            run_id: Existing run owned by this coordinator.

        Returns:
            Request acknowledgment, not proof that active actions are stopped.

        Raises:
            CoordinatorError: Run is missing or no longer in a cancellable phase.
        """
        run = self._read_run(run_id)
        key = str(run_id)
        if key not in self.cancellations or run["status"] not in {
            "queued",
            "preflighting",
            "running",
        }:
            raise CoordinatorError(409, "Run is not in a cancellable load phase")
        self.cancellations[key].set()
        return Accepted(id=key, status="cancellation_requested", url=f"/v1/runs/{key}")

    async def wait(self, run_id: UUID, timeout: float | None = None) -> RunReport:
        """Wait for owned work and return its first report page.

        Args:
            run_id: Existing run; recovered runs are never resumed.
            timeout: Positive seconds to wait, or None to wait indefinitely.

        Raises:
            TimeoutError: Waiting expires; the underlying run remains active.
            CoordinatorError: Run missing or report unavailable.

        Cancelling the waiter never cancels inference. Use cancel explicitly.
        """
        self._read_run(run_id)
        if timeout is not None and (timeout <= 0 or not math.isfinite(timeout)):
            raise ValueError("timeout must be positive finite seconds")
        task = self.tasks.get(str(run_id))
        if task is not None:
            await asyncio.wait_for(asyncio.shield(task), timeout)
        return self.get_report(run_id)
