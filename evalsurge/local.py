"""Unified direct v2 execution over the existing local coordinator and Locust.

Legacy keyword calls remain available. New requests use opaque aliases bound by
the operator context, never credentials or provider routing inside RunCreate.
"""

import asyncio
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any
from uuid import UUID

from benchmark_agents.configuration import configured_environment, environment
from benchmark_agents.coordinator import CoordinatorError, RunCoordinator
from benchmark_agents.models import Accepted, RunReport
from benchmark_agents.planner import fingerprint
from benchmark_agents.run_views import TERMINAL, report_view, result_view
from benchmark_agents.settings import ConnectionSettings, Settings, load_settings
from benchmark_agents.target_resolver import TargetResolutionError, resolve_registered_target
from benchmark_agents.v2_models import Acknowledgment, Links, Report, Result, RunCreate, RunStatus
from benchmark_agents.validation import encode_request

from .client import Agent, AsyncRun, Run, RunFailed
from .client import AsyncClient as LegacyAsyncClient
from .client import Client as LegacyClient


def _operator_snapshot(
    targets: Mapping[str, Agent] | None,
    settings: Settings | None,
    artifact_dir: str | Path | None,
) -> tuple[Mapping[str, ConnectionSettings], Mapping[str, str]]:
    """Freeze effective operator configuration without discovery or credential resolution.

    Args:
        targets: Context-owned aliases; target objects are copied, not retained.
        settings: Optional immutable operator settings; omission loads configuration.
        artifact_dir: Explicit storage override; omission honors the loaded settings.

    Returns:
        Immutable registered bindings and an isolated private runtime snapshot.
        Implicit environment registry parsing waits for unified admission;
        snapshots can contain secrets and must never be serialized or logged.

    Raises:
        TypeError: Invalid target/settings types.
        ValueError: Unsupported aliases or duplicate registration ownership.
        SettingsError: Invalid selected operator configuration.

    Side Effects:
        May read one bounded operator file through load_settings(). No profile
        files, target authentication, external calls or artifact creation occur.
    """
    if settings is not None and not isinstance(settings, Settings):
        raise TypeError("settings must be operator Settings")
    values = dict(environment())
    loading = dict(values)
    deferred_connections = (
        settings is None and targets is None and "BENCHMARK_CONNECTIONS" in values
    )
    if deferred_connections:
        # Legacy calls supply an exact Agent, so their unused v2 registry must
        # not reject construction. Unified admission validates the frozen raw
        # registry before resolving any target; no invalid binding is accepted.
        loading["BENCHMARK_CONNECTIONS"] = "{}"
    configured = settings or load_settings(environ=loading)
    bindings = dict(configured.connections)
    if targets is not None:
        if not isinstance(targets, Mapping):
            raise TypeError("targets must map aliases to Agent objects")
        for name, agent in targets.items():
            if not isinstance(agent, Agent):
                raise TypeError("targets must map aliases to Agent objects")
            if name in bindings:
                raise ValueError("Target alias already belongs to operator settings")
            bindings[name] = agent.registration
    # Reuse the operator registry's alias and cardinality constraints.
    checked = Settings(connections=bindings).connections
    snapshot = configured.to_environment(values)
    selected = Path(artifact_dir) if artifact_dir is not None else configured.artifact_dir
    snapshot["BENCHMARK_ARTIFACT_DIR"] = str(selected)
    snapshot["BENCHMARK_CONNECTIONS"] = json.dumps(
        {alias: binding.operator_record() for alias, binding in checked.items()}
    )
    if deferred_connections:
        snapshot["BENCHMARK_CONNECTIONS"] = values["BENCHMARK_CONNECTIONS"]
    return MappingProxyType(dict(checked)), MappingProxyType(snapshot)


def _detached_request(config: Mapping[str, Any] | RunCreate) -> RunCreate:
    """Validate a finite bounded request before admission, never serialize credentials."""
    request, _ = encode_request(config)
    return request


async def _wait_observed(
    coordinator: RunCoordinator,
    run_id: UUID,
    timeout: float | None,
    on_status: Callable[[RunStatus], None],
    *,
    clock: Callable[[], float] | None = None,
) -> None:
    """Observe owned lifecycle at one-second intervals without cancelling run work.

    Args:
        coordinator: Open direct client's exclusive coordinator, not a load worker.
        run_id: Existing unified run whose protected payload stays in the coordinator.
        timeout: Positive finite waiter seconds or no deadline.
        on_status: Short synchronous callback receiving a detached typed status.
        clock: Internal monotonic seconds seam; defaults to the owning loop clock.

    Raises:
        TimeoutError: Wait budget expires, including observer time.
        CoordinatorError: Run or report lookup fails.
        Exception: Observer errors propagate without cancelling the run.

    Side Effects:
        Owns only a shielded waiter task and content-free in-memory status reads.
        No target requests, extra load engines or measured-worker logging occur.
        Slow observers can consume caller resources; this is not a zero-overhead
        guarantee. Cancelling this waiter leaves inference ownership unchanged.
    """
    if timeout is not None and (timeout <= 0 or not math.isfinite(timeout)):
        raise ValueError("timeout must be positive finite seconds")
    loop = asyncio.get_running_loop()
    now = clock or loop.time
    deadline = now() + timeout if timeout is not None else None
    waiter = asyncio.create_task(coordinator.wait(run_id, timeout))

    def remaining() -> float | None:
        """Include observer time and never begin another callback after expiry."""
        budget = deadline - now() if deadline is not None else None
        if budget is not None and budget <= 0:
            raise TimeoutError("Wait timed out; underlying run was not cancelled.")
        return budget

    try:
        while True:
            remaining()
            on_status(coordinator.read_status(run_id))
            budget = remaining()
            if waiter.done():
                await waiter
                return
            await asyncio.wait({waiter}, timeout=min(1, budget) if budget is not None else 1)
    finally:
        if not waiter.done():
            waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


@dataclass(frozen=True, slots=True)
class AsyncDirectRun:
    """Typed handle tied to a native async context and its opening event loop."""

    id: UUID
    _client: "AsyncClient" = field(repr=False)

    async def status(self) -> RunStatus:
        """Read lightweight independent phases."""
        return await self._client.status(self.id)

    async def result(self) -> Result:
        """Read measured performance and available protected assessments."""
        return await self._client.result(self.id)

    async def report(self, *, offset: int = 0, limit: int = 25) -> Report:
        """Read protected evidence with bounded profile pagination."""
        return await self._client.report(self.id, offset=offset, limit=limit)

    async def wait(
        self,
        timeout: float | None = None,
        *,
        on_status: Callable[[RunStatus], None] | None = None,
    ) -> Report:
        """Wait in seconds, optionally observing typed status outside the load worker."""
        return await self._client.wait(self.id, timeout=timeout, on_status=on_status)

    async def cancel(self) -> Acknowledgment:
        """Stop new dispatch; already active requests drain."""
        return await self._client.cancel(self.id)


class AsyncClient(LegacyAsyncClient):
    """Direct request vocabulary; native async ownership and legacy calls are preserved."""

    def __init__(
        self,
        artifact_dir: str | Path | None = None,
        *,
        targets: Mapping[str, Agent] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._legacy_ambient = targets is None and settings is None
        self._bindings, self._operator = _operator_snapshot(targets, settings, artifact_dir)
        super().__init__(Path(self._operator["BENCHMARK_ARTIFACT_DIR"]))

    async def __aenter__(self) -> "AsyncClient":
        with configured_environment(self._operator):
            await super().__aenter__()
        return self

    async def close(self) -> None:
        """Drain owned work and release storage without changing process configuration."""
        with configured_environment(self._operator):
            await super().close()

    def _legacy_environment(self) -> Mapping[str, str]:
        """Copy private legacy submission settings with this context's storage owner.

        Returns:
            Effective submission-time settings unless explicit context settings
            or bindings own them. Contains private values; never export or log.
        """
        values = dict(environment()) if self._legacy_ambient else dict(self._operator)
        values["BENCHMARK_ARTIFACT_DIR"] = str(self._artifact_dir)
        return values

    async def start(
        self,
        config: Mapping[str, Any] | RunCreate | None = None,
        *,
        idempotency_key: str | None = None,
        **legacy: Any,
    ) -> AsyncDirectRun | AsyncRun:
        """Admit a v2 request or preserve the legacy keyword-only submission.

        Args:
            config: V2 request with an alias, workload and explicit optional evaluation.
            idempotency_key: Optional bounded replay key for this canonical request.
            **legacy: Existing agent/cases/load/evaluation/plan_id arguments, only
                when config is omitted.

        Returns:
            Typed direct handle for v2; existing handle for legacy keyword calls.

        Raises:
            RequestValidationError: Safe field-specific schema errors.
            ValueError: JSON bounds, replay header, or conflicting call forms.
            CoordinatorError: Unknown alias/scorer or safe admission/resolution failure.
        """
        if config is None:
            # Preserve legacy submission-time configuration, including an
            # experiment created after context entry. Explicit operator settings
            # or targets instead retain their context-owned frozen snapshot.
            with configured_environment(self._legacy_environment()):
                return await super().start(idempotency_key=idempotency_key, **legacy)
        with configured_environment(self._operator):
            if legacy:
                raise TypeError("Do not combine a unified request with legacy start arguments")
            request = _detached_request(config)
            coordinator = self._owned_coordinator()
            canonical = fingerprint(
                {"api_version": "v2", "request": request.model_dump(mode="json")}
            )
            if idempotency_key is not None and (
                not isinstance(idempotency_key, str)
                or not 1 <= len(idempotency_key) <= 128
                or any(not 33 <= ord(char) <= 126 for char in idempotency_key)
            ):
                raise ValueError("Idempotency key must contain 1 to 128 printable ASCII characters")
            if idempotency_key:
                key_hash = fingerprint(idempotency_key)
                for prior in coordinator.index.values():
                    if prior.get("idempotency_key_hash") == key_hash:
                        if prior.get("request_hash") != canonical:
                            raise CoordinatorError(
                                409, "Idempotency-Key was used with a different body"
                            )
                        return AsyncDirectRun(UUID(prior["id"]), self)
            settings = load_settings(environ=self._operator)
            if request.target.connection_id not in settings.connections:
                raise CoordinatorError(422, "Unknown registered target")
            try:
                # Validate scorer selection without network/authentication.
                from benchmark_agents.models import Target

                request.translate(Target(url="http://127.0.0.1/validation"), set(settings.scorers))
                target, connection = await asyncio.to_thread(
                    resolve_registered_target, request.target.connection_id, settings.connections
                )
                translated = request.translate(target, set(settings.scorers))
            except TargetResolutionError:
                raise CoordinatorError(
                    502, "Registered target resolution failed; check operator configuration"
                ) from None
            except ValueError:
                raise CoordinatorError(
                    422, "Invalid registered target or scorer configuration"
                ) from None
            accepted = await coordinator.submit(
                translated,
                idempotency_key,
                connection=connection,
                defer_planning=True,
                submission_hash=canonical,
                name=request.name,
                evaluation_mode=request.evaluation.mode,
            )
            return AsyncDirectRun(UUID(accepted.id), self)

    async def status(self, run_id: UUID | str) -> RunStatus:
        """Read a detached public lifecycle, without prompts or target configuration."""
        with configured_environment(self._operator):
            return self._owned_coordinator().read_status(UUID(str(run_id)))

    async def result(self, run_id: UUID | str) -> Result:
        """Read independent performance/quality; false verdicts are not failures."""
        with configured_environment(self._operator):
            coordinator = self._owned_coordinator()
            run = coordinator.read_run(UUID(str(run_id)))
            profiling = (
                coordinator.get_report(UUID(str(run_id))).profiling
                if run["status"] in TERMINAL and run.get("plan")
                else None
            )
            return result_view(run, profiling)

    async def report(
        self, run_id: UUID | str, *, offset: int = 0, limit: int = 25
    ) -> Report | RunReport:
        """Read typed reports for unified runs; preserve legacy reports for old runs."""
        with configured_environment(self._operator):
            coordinator = self._owned_coordinator()
            identifier = UUID(str(run_id))
            if coordinator.read_run(identifier).get("evaluation_mode") is None:
                return await super().report(identifier, offset=offset, limit=limit)
            return report_view(coordinator, identifier, offset, limit)

    async def wait(
        self,
        run_id: UUID | str,
        timeout: float | None = None,
        *,
        on_status: Callable[[RunStatus], None] | None = None,
    ) -> Report | RunReport:
        """Wait without cancelling the run; lifecycle failures retain inspectable reports.

        A completed run can have negative quality verdicts. Only failed,
        interrupted or cancelled lifecycle states raise RunFailed.
        A short synchronous observer receives content-free status at one-second
        intervals plus initial/terminal observations on the owning loop. Its time
        consumes waiter budget; exceptions
        propagate without cancelling inference. Legacy runs omit this observer.
        """
        with configured_environment(self._operator):
            coordinator = self._owned_coordinator()
            identifier = UUID(str(run_id))
            if coordinator.read_run(identifier).get("evaluation_mode") is None:
                if on_status is not None:
                    raise ValueError("Status observers require a unified run")
                return await super().wait(identifier, timeout)
            observer_failed = False

            def observe(status: RunStatus) -> None:
                nonlocal observer_failed
                try:
                    if on_status is not None:
                        on_status(status)
                except Exception:
                    observer_failed = True
                    raise

            try:
                if on_status is None:
                    await coordinator.wait(identifier, timeout)
                else:
                    await _wait_observed(coordinator, identifier, timeout, observe)
            except CoordinatorError as error:
                if (
                    observer_failed
                    or error.status_code != 409
                    or coordinator.read_run(identifier)["status"] not in TERMINAL
                ):
                    raise
            report = report_view(coordinator, identifier)
            if report.run.status in {"failed", "interrupted", "cancelled"}:
                raise RunFailed(report)
            return report

    async def cancel(self, run_id: UUID | str) -> Acknowledgment | Accepted:
        """Request dispatch cancellation; active requests and trusted scorers drain."""
        with configured_environment(self._operator):
            coordinator = self._owned_coordinator()
            identifier = UUID(str(run_id))
            unified = coordinator.read_run(identifier).get("evaluation_mode") is not None
            accepted = coordinator.cancel(identifier)
            return (
                Acknowledgment(
                    id=accepted.id, status=accepted.status, links=Links.for_run(accepted.id)
                )
                if unified
                else accepted
            )


@dataclass(frozen=True, slots=True)
class DirectRun:
    """Typed synchronous handle; owned work stays on the client's dedicated loop."""

    id: UUID
    _client: "Client" = field(repr=False)

    def status(self) -> RunStatus:
        """Read independent lifecycle phases."""
        return self._client.status(self.id)

    def result(self) -> Result:
        """Read descriptive performance and quality evidence."""
        return self._client.result(self.id)

    def report(self, *, offset: int = 0, limit: int = 25) -> Report:
        """Read protected evidence with bounded profile pagination."""
        return self._client.report(self.id, offset=offset, limit=limit)

    def wait(
        self,
        timeout: float | None = None,
        *,
        on_status: Callable[[RunStatus], None] | None = None,
    ) -> Report:
        """Wait in seconds, optionally observing typed status outside the load worker."""
        return self._client.wait(self.id, timeout, on_status=on_status)

    def cancel(self) -> Acknowledgment:
        """Stop new dispatch; active requests drain."""
        return self._client.cancel(self.id)


class Client(LegacyClient):
    """Default direct context, safe to open from a notebook's existing event loop."""

    def __init__(
        self,
        artifact_dir: str | Path | None = None,
        *,
        targets: Mapping[str, Agent] | None = None,
        settings: Settings | None = None,
    ) -> None:
        async_client = AsyncClient(artifact_dir, targets=targets, settings=settings)
        super().__init__(async_client._artifact_dir)
        self._async_client = async_client

    def start(
        self,
        config: Mapping[str, Any] | RunCreate | None = None,
        *,
        idempotency_key: str | None = None,
        **legacy: Any,
    ) -> DirectRun | Run:
        """Start a copied v2 request, or preserve legacy keyword submission behavior."""
        self._require_open()
        if config is None:
            with configured_environment(self._async_client._legacy_environment()):
                return super().start(idempotency_key=idempotency_key, **legacy)
        if legacy:
            raise TypeError("Do not combine a unified request with legacy start arguments")
        request = _detached_request(config)
        run = self._call(lambda: self._async_client.start(request, idempotency_key=idempotency_key))
        return DirectRun(run.id, self)

    def status(self, run_id: UUID | str) -> RunStatus:
        """Read typed status on the owning loop."""
        self._require_open()
        return self._call(lambda: self._async_client.status(run_id))

    def result(self, run_id: UUID | str) -> Result:
        """Read typed result on the owning loop."""
        self._require_open()
        return self._call(lambda: self._async_client.result(run_id))

    def wait(
        self,
        run_id: UUID | str,
        timeout: float | None = None,
        *,
        on_status: Callable[[RunStatus], None] | None = None,
    ) -> Report | RunReport:
        """Wait without cancelling work; observers run on the dedicated owning loop.

        Observer exceptions propagate and consume waiter budget, but do not cancel
        underlying work. Context exit still owns normal dispatch cancellation/drain.
        """
        self._require_open()
        return self._call(lambda: self._async_client.wait(run_id, timeout, on_status=on_status))

    def report(self, run_id: UUID | str, *, offset: int = 0, limit: int = 25) -> Report | RunReport:
        """Read a typed unified report or the compatible legacy report."""
        self._require_open()
        return self._call(lambda: self._async_client.report(run_id, offset=offset, limit=limit))

    def cancel(self, run_id: UUID | str) -> Acknowledgment | Accepted:
        """Request cancellation once; active calls drain, terminal runs reject it."""
        self._require_open()
        return self._call(lambda: self._async_client.cancel(run_id))
