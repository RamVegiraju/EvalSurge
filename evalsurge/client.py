"""Python contexts and run handles over the single-owner benchmark coordinator.

Local runs generate traffic from this Python process's machine, without an HTTP
server. The coordinator owns admission, persistence, recovery, preflight, and
Locust; these clients only adapt its calling convention. Artifact directories
contain protected workload/evaluation data and must not be shared between owners.
"""

import asyncio
import threading
from collections.abc import Callable, Coroutine, Sequence
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, TypeVar
from uuid import UUID

from benchmark_agents.connections import Connection, validate_connection
from benchmark_agents.coordinator import RunCoordinator
from benchmark_agents.models import (
    Accepted,
    Evaluation,
    Load,
    RunReport,
    RunRequest,
    Sample,
    Target,
)

from .remote import RemoteClient

Protocol = Literal["openai-chat", "mlflow-agent-server", "http-json"]
Result = TypeVar("Result")


class Agent:
    """An explicitly authorized endpoint with independent wire and auth settings.

    Connections contain credential references, not resolved tokens. Properties
    return detached copies so later caller mutation cannot change this binding.
    """

    def __init__(self, target: Target, connection: Connection | None = None) -> None:
        """Revalidate and detach an exact binding without reading credential secrets.

        Args:
            target: Supported endpoint wire contract.
            connection: Explicit operator-owned settings; omission authorizes
                unauthenticated access to the target.

        Raises:
            ValueError: Target, credential transport, or connection is invalid.
        """
        self._target = Target.model_validate(target.model_dump(mode="json"))
        binding = (
            Connection.model_validate(connection.model_dump(mode="json"))
            if connection is not None
            else Connection(url=str(self._target.url))
        )
        self._connection = validate_connection(self._target, binding)

    @classmethod
    def http(
        cls,
        url: str,
        *,
        protocol: Protocol = "openai-chat",
        model: str = "agent",
        request_usage: bool = True,
        connection: Connection | None = None,
    ) -> "Agent":
        """Bind a hosted HTTP agent without resolving secrets or sending traffic.

        Args:
            url: Exact authorized URL, without userinfo, query, or fragment.
            protocol: OpenAI chat SSE, MLflow agent SSE, or the HTTP JSON contract.
                JSON sends Sample.inputs unchanged and expects a nonempty
                outputs string, with optional usage.output_tokens and trace_id.
            model: Target identifier sent by adapters that use a model field.
                No provider-specific parameters or fallbacks are inferred.
            request_usage: Request optional OpenAI SSE usage. Other protocols
                ignore this flag; absent usage remains unknown.
            connection: Operator-owned binding to this exact URL. Omission
                explicitly authorizes unauthenticated access to the chosen URL.

        Returns:
            Detached endpoint and connection settings.

        Raises:
            ValueError: URL/protocol is invalid, a connection differs, or remote
                transport is not HTTPS. Loopback HTTP is supported.

        This does not mutate environment configuration. Bearer tokens remain
        references to operator-selected environment variables.
        """
        return cls(
            Target(url=url, adapter=protocol, model=model, request_usage=request_usage), connection
        )

    @property
    def target(self) -> Target:
        """Return a detached wire contract, with no resolved credential values."""
        return self._target.model_copy(deep=True)

    @property
    def connection(self) -> Connection:
        """Return a detached exact-URL operator binding."""
        return self._connection.model_copy(deep=True)


class RunFailed(RuntimeError):
    """A terminal failure with its detached report, not private provider errors."""

    def __init__(self, report: RunReport) -> None:
        self.report = report.model_copy(deep=True)
        message = f"Benchmark run {report.run.id} {report.run.status}."
        if report.run.preflight.error is not None:
            message += " " + report.run.preflight.error.message
        elif report.run.evaluation_preflight.error is not None:
            failure = report.run.evaluation_preflight.error
            message += f" {failure.message} {failure.guidance}"
        elif report.run.load_error is not None:
            message += f" {report.run.load_error.message} {report.run.load_error.guidance}"
        super().__init__(message)


def _checked_report(report: RunReport) -> RunReport:
    """Raise only for failed lifecycle states; quality/evidence gaps are returned."""
    if report.run.status in {"failed", "interrupted", "cancelled"}:
        raise RunFailed(report)
    return report


def _request(
    agent: Agent,
    cases: Sequence[Sample],
    load: Load,
    evaluation: Evaluation | None,
    plan_id: str | UUID | None,
) -> RunRequest:
    """Validate and detach inputs before admission, without implicit paid planning.

    Args:
        agent: Explicit endpoint/connection authorization.
        cases: Nonempty bounded workload; retained references are copied.
        load: Closed-loop dispatch and deadline limits, in seconds.
        evaluation: Opt-in evaluation policy. Empty samples inherit cases; a
            nonempty sample list must match cases, including reference evidence.
        plan_id: Optional existing frozen-plan UUID; the coordinator checks it.

    Returns:
        An independent validated request. Omitted evaluation disables both
        catalog and registered scorers explicitly.

    Raises:
        TypeError: Arguments are not the public contract types.
        ValueError: Cases are empty, invalid, oversized, or conflict with samples.
    """
    if not isinstance(agent, Agent):
        raise TypeError("agent must be an Agent")
    if not isinstance(load, Load):
        raise TypeError("load must be a Load")
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise TypeError("cases must be a sequence of Sample objects")
    if not cases:
        raise ValueError("cases must contain at least one Sample")
    if len(cases) > 1000:
        raise ValueError("cases must contain at most 1000 samples")
    if any(not isinstance(sample, Sample) for sample in cases):
        raise TypeError("cases must contain Sample objects")
    samples = [sample.model_dump(mode="json") for sample in cases]
    if evaluation is None:
        policy = {
            "description": "Performance-only benchmark",
            "scorers": [],
            "registered_scorers": [],
        }
    else:
        if not isinstance(evaluation, Evaluation):
            raise TypeError("evaluation must be an Evaluation")
        policy = evaluation.model_dump(mode="json")
        if policy["samples"] and policy["samples"] != samples:
            raise ValueError("evaluation.samples must match cases, including expectations")
    policy["samples"] = samples
    return RunRequest(
        target=agent.target,
        evaluation=Evaluation.model_validate(policy),
        load=Load.model_validate(load.model_dump(mode="json")),
        plan_id=str(plan_id) if plan_id is not None else None,
    )


@dataclass(frozen=True, slots=True)
class AsyncRun:
    """A run identifier tied to an open native-async client."""

    id: UUID
    _client: "AsyncClient" = field(repr=False)

    async def wait(self, timeout: float | None = None) -> RunReport:
        """Wait in seconds without cancelling work on timeout; raise RunFailed."""
        return await self._client.wait(self.id, timeout=timeout)

    async def report(self, *, offset: int = 0, limit: int = 25) -> RunReport:
        """Read a bounded report page; failed reports remain inspectable."""
        return await self._client.report(self.id, offset=offset, limit=limit)

    async def cancel(self) -> Accepted:
        """Request dispatch cancellation; active requests drain before completion."""
        return await self._client.cancel(self.id)


class AsyncClient:
    """Native-async local context; all operations stay on its opening event loop.

    Exiting stops new dispatch, drains admitted work, and releases the coordinator
    storage lock. It cannot undo tool actions or impose deadlines on trusted judge
    code. The context cannot be reopened after closing.
    """

    def __init__(self, artifact_dir: str | Path) -> None:
        self._artifact_dir = Path(artifact_dir)
        self._coordinator: RunCoordinator | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._state: Literal["new", "opening", "open", "closing", "closed"] = "new"
        self._close_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> "AsyncClient":
        """Acquire exclusive storage; fail rather than sharing another owner's work."""
        if self._state != "new":
            raise RuntimeError("EvalSurge context cannot be entered more than once")
        self._state = "opening"
        self._loop = asyncio.get_running_loop()
        coordinator = RunCoordinator(self._artifact_dir)
        try:
            await coordinator.open()
        except BaseException:
            self._state = "closed"
            raise
        self._coordinator = coordinator
        self._state = "open"
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    def _owned_coordinator(self) -> RunCoordinator:
        """Require an open context on its original loop, before any mutation."""
        if self._state != "open" or self._coordinator is None:
            raise RuntimeError("EvalSurge client is not open; use it inside its context")
        if asyncio.get_running_loop() is not self._loop:
            raise RuntimeError("Async EvalSurge client belongs to a different event loop")
        return self._coordinator

    async def close(self) -> None:
        """Cancel dispatch, drain owned work despite waiter cancellation, and unlock.

        Repeated calls are safe on the owning loop. No hard shutdown deadline is
        promised for operator-owned scorers. Cancelling close is propagated only
        after its coordinator has drained and released storage ownership.
        """
        if self._state in {"new", "closed"}:
            self._state = "closed"
            return
        if asyncio.get_running_loop() is not self._loop:
            raise RuntimeError("Async EvalSurge client belongs to a different event loop")
        if self._state == "opening":
            raise RuntimeError("EvalSurge client is still opening")
        if self._close_task is None:
            coordinator = self._owned_coordinator()
            self._state = "closing"
            self._close_task = asyncio.create_task(coordinator.close())
        cancelled = False
        try:
            while True:
                try:
                    await asyncio.shield(self._close_task)
                    break
                except asyncio.CancelledError:
                    if self._close_task.cancelled():
                        raise
                    cancelled = True
        finally:
            if self._close_task.done():
                self._state = "closed"
        if cancelled:
            raise asyncio.CancelledError

    async def start(
        self,
        *,
        agent: Agent,
        cases: Sequence[Sample],
        load: Load,
        evaluation: Evaluation | None = None,
        idempotency_key: str | None = None,
        plan_id: str | UUID | None = None,
    ) -> AsyncRun:
        """Admit a copied workload and return a handle before preflight/load.

        Args:
            agent: Authorized endpoint with an independent exact connection.
            cases: Nonempty workload and optional authoritative references.
            load: Explicit closed-loop limits; requests may execute tools.
            evaluation: Opt-in policy; omission disables paid planning/judging.
                Supplying planner-selected scorers can incur separate spend.
            idempotency_key: Optional bounded key; identical replay reuses a run.
            plan_id: Reuse a frozen plan with exactly matching evaluation policy.

        Returns:
            Handle scoped to this context. Waiting includes preflight and report
            completion, not just the measured load window.

        Raises:
            RuntimeError: Context is closed or used on another loop.
            ValueError: Workload validation fails or samples conflict with cases.
            CoordinatorError: Safe admission, configuration, or replay failure.
        """
        coordinator = self._owned_coordinator()
        request = _request(agent, cases, load, evaluation, plan_id)
        accepted = await coordinator.submit(request, idempotency_key, connection=agent.connection)
        return AsyncRun(UUID(accepted.id), self)

    async def wait(self, run_id: UUID | str, timeout: float | None = None) -> RunReport:
        """Wait for a run and return its first page, preserving gaps as evidence.

        Args:
            run_id: Run in this artifact directory, including recovered history.
            timeout: Positive finite seconds, or None for no waiter deadline.

        Returns:
            Detached report; completed_with_gaps is not a failed transport.

        Raises:
            TimeoutError: Waiter expires; the underlying run is not cancelled.
            RunFailed: Run failed, was interrupted, or was cancelled.
            CoordinatorError: Safe lookup or report availability failure.
            RuntimeError: Client is not open on its owning loop.
        """
        report = await self._owned_coordinator().wait(UUID(str(run_id)), timeout)
        return _checked_report(report)

    async def report(self, run_id: UUID | str, *, offset: int = 0, limit: int = 25) -> RunReport:
        """Read a detached profile page, including terminal failures.

        Offset is nonnegative and limit is 1–100; reports are unavailable before
        profiling is ready. Safe CoordinatorError preserves that distinction.
        """
        return self._owned_coordinator().get_report(UUID(str(run_id)), offset, limit)

    async def cancel(self, run_id: UUID | str) -> Accepted:
        """Stop new probe/load dispatch; active requests drain and judging is not cancelled."""
        return self._owned_coordinator().cancel(UUID(str(run_id)))


@dataclass(frozen=True, slots=True)
class Run:
    """A synchronous run handle tied to an open dedicated-loop client."""

    id: UUID
    _client: "Client" = field(repr=False)

    def wait(self, timeout: float | None = None) -> RunReport:
        """Wait in seconds without cancelling work on timeout; raise RunFailed."""
        return self._client.wait(self.id, timeout=timeout)

    def report(self, *, offset: int = 0, limit: int = 25) -> RunReport:
        """Read a bounded report page; failed reports remain inspectable."""
        return self._client.report(self.id, offset=offset, limit=limit)

    def cancel(self) -> Accepted:
        """Request dispatch cancellation; active requests drain before completion."""
        return self._client.cancel(self.id)


class Client:
    """Synchronous local context running its coordinator on a dedicated thread.

    This does not nest asyncio.run inside a caller's existing notebook/event loop.
    Blocking calls still block their calling thread; async applications should use
    local_async or asyncio.to_thread, especially when they also serve the target.
    """

    def __init__(self, artifact_dir: str | Path) -> None:
        self._async_client = AsyncClient(artifact_dir)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready: Future[None] = Future()
        self._state: Literal["new", "opening", "open", "closing", "closed"] = "new"

    def _serve(self) -> None:
        """Own loop/executor shutdown in the worker thread, including failed startup."""
        try:
            with asyncio.Runner() as runner:
                self._loop = runner.get_loop()
                self._ready.set_result(None)
                self._loop.run_forever()
        except BaseException as error:
            if not self._ready.done():
                self._ready.set_exception(error)
            else:
                raise
        finally:
            self._loop = None

    def _call(
        self,
        operation: Callable[[], Coroutine[Any, Any, Result]],
        *,
        defer_interrupts: bool = False,
    ) -> Result:
        """Serialize an operation on the loop, without nesting a caller's asyncio.

        Args:
            operation: Factory called only after validating thread/loop ownership.
            defer_interrupts: Finish shutdown before propagating an interrupt.

        Returns:
            The coroutine's result.

        Raises:
            RuntimeError: The loop is absent or this call would deadlock it.
            BaseException: Coroutine failures propagate. Caller interruption
                cancels only the operation waiter unless draining shutdown.
        """
        loop = self._loop
        if loop is None:
            raise RuntimeError("EvalSurge client event loop is not running")
        if threading.current_thread() is self._thread:
            raise RuntimeError("Use local_async from the EvalSurge event-loop thread")
        future = asyncio.run_coroutine_threadsafe(operation(), loop)
        interruption: KeyboardInterrupt | SystemExit | None = None
        while True:
            try:
                result = future.result()
                break
            except (KeyboardInterrupt, SystemExit) as error:
                if not defer_interrupts or future.done():
                    if not future.done():
                        future.cancel()
                    raise
                interruption = error
            except BaseException:
                if not future.done():
                    future.cancel()
                raise
        if interruption is not None:
            raise interruption
        return result

    def __enter__(self) -> "Client":
        """Start the dedicated loop and acquire exclusive coordinator storage."""
        if self._state != "new":
            raise RuntimeError("EvalSurge context cannot be entered more than once")
        self._state = "opening"
        self._thread = threading.Thread(target=self._serve, name="evalsurge-local")
        try:
            self._thread.start()
            self._ready.result()
            self._call(self._async_client.__aenter__)
        except BaseException:
            self.close()
            raise
        self._state = "open"
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _require_open(self) -> None:
        if self._state != "open":
            raise RuntimeError("EvalSurge client is not open; use it inside its context")

    def close(self) -> None:
        """Stop dispatch, drain work, release storage, and join the dedicated thread.

        Closing is idempotent. Context owners must not close concurrently with
        another close operation. Trusted scorer shutdown has no hard deadline.
        """
        if self._state in {"new", "closed"}:
            self._state = "closed"
            return
        self._state = "closing"
        loop = self._loop
        try:
            if loop is not None:
                self._call(self._async_client.close, defer_interrupts=True)
        finally:
            if loop is not None and not loop.is_closed():
                loop.call_soon_threadsafe(loop.stop)
            if self._thread is not None and self._thread.ident is not None:
                self._thread.join()
            self._state = "closed"

    def start(
        self,
        *,
        agent: Agent,
        cases: Sequence[Sample],
        load: Load,
        evaluation: Evaluation | None = None,
        idempotency_key: str | None = None,
        plan_id: str | UUID | None = None,
    ) -> Run:
        """Admit detached inputs on the shared coordinator; no implicit judging.

        Arguments and failures match AsyncClient.start. Copies are made on the
        calling thread before handing ownership to the loop. This starts one
        extra first-case probe before measured traffic; use wait for its outcome.
        """
        self._require_open()
        request = _request(agent, cases, load, evaluation, plan_id)
        connection = agent.connection

        async def submit() -> Run:
            accepted = await self._async_client._owned_coordinator().submit(
                request, idempotency_key, connection=connection
            )
            return Run(UUID(accepted.id), self)

        return self._call(submit)

    def wait(self, run_id: UUID | str, timeout: float | None = None) -> RunReport:
        """Wait in seconds; timeout leaves the run active, failures carry a report."""
        self._require_open()
        return self._call(lambda: self._async_client.wait(run_id, timeout))

    def report(self, run_id: UUID | str, *, offset: int = 0, limit: int = 25) -> RunReport:
        """Read a bounded detached report page without raising RunFailed."""
        self._require_open()
        return self._call(lambda: self._async_client.report(run_id, offset=offset, limit=limit))

    def cancel(self, run_id: UUID | str) -> Accepted:
        """Request cancellation of load dispatch, retaining the safe acknowledgment."""
        self._require_open()
        return self._call(lambda: self._async_client.cancel(run_id))


class EvalSurge:
    """Factories for local contexts using one coordinator and one Locust engine."""

    @staticmethod
    def remote(base_url: str, *, api_key: str | None = None, **kwargs: Any) -> RemoteClient:
        """Create a remote HTTP client; the API host remains the load generator.

        Args:
            base_url: Authorized HTTPS API origin, or HTTP loopback for local tests.
            api_key: Optional in-memory service key; never included in URLs.
            **kwargs: RemoteClient timeout, transport, and polling options.

        Returns:
            Unopened remote client. Enter its context to own and close HTTP resources.
        """
        return RemoteClient(base_url, api_key=api_key, **kwargs)

    @staticmethod
    def local(*, artifact_dir: str | Path = "artifacts") -> Client:
        """Create a sync context; the current machine is the load generator.

        Args:
            artifact_dir: Protected persistent storage; its POSIX ownership lock
                prevents concurrent use by another local or REST coordinator.

        Returns:
            Unopened context. Enter it before starting runs or reading history.
        """
        return Client(artifact_dir)

    @staticmethod
    def local_async(*, artifact_dir: str | Path = "artifacts") -> AsyncClient:
        """Create a native-async context on the opening event loop.

        Artifact ownership and traffic location match local; no HTTP server or
        temporary process-global configuration is created by either interface.
        """
        return AsyncClient(artifact_dir)
