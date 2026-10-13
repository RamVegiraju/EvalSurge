# ADR 0021: content-free live CLI lifecycle progress

Status: proposed; designated maintainer review required before release.
Date: October 12, 2026.

## Context and load assumptions

The CLI prints admission and the final summary, leaving users without updates
during inference preflight, measured load, trace collection or judging. Progress
must not add per-request logging, model calls, trace fetches or another load engine.
The current lightweight status has phase states, not live request counters or
streaming latency estimates. Completed-run metrics remain the authoritative
summary. Existing workload limits and timing definitions are unchanged.

## Decision and data flow

Add an optional synchronous `on_status` observer to unified direct and remote
waiters. Remote observation reuses each validated lifecycle polling response;
it adds no HTTP status polling. Direct observation reads the coordinator's
lightweight in-memory status at one-second intervals plus initial/terminal
observations while the existing shielded wait task runs. Status is projected before
copying protected cases/request rows; historical cache misses still read their
existing snapshot. The Locust subprocess and request clocks are unchanged.

`run -> existing waiter -> content-free status -> observer -> CLI stderr`

The CLI enables progress for an interactive waiting session, with explicit
`--progress` / `--no-progress` overrides. Explicit progress requires `--wait` or
local execution, which already waits for owned cleanup. Output includes elapsed
wait time, an allowlisted lifecycle and allowlisted independent phase states.
Phase changes are printed immediately when observed; unchanged phases get a
bounded heartbeat. No names, prompts, answers, references, judge rationales,
destinations, credentials or server-supplied diagnostics are printed. Structured
JSON stays alone on stdout. No live throughput/latency is invented.

## Failure modes, ownership and bottlenecks

Observer callbacks execute on the waiting caller's context (the owning async
loop for direct clients), not in the Locust worker. Keep them short: slow output
or callbacks consume waiter budget and can consume caller resources. This is
not a zero-observer-overhead or generator-accuracy claim. The direct observer
checks its deadline before every callback and
clamps its poll wait to the remaining budget. A blocking callback itself cannot
be forcibly interrupted. Sync-client reentry from its owning-loop callback is
rejected by the existing thread guard.
Callback exceptions abort waiting and propagate, but never cancel the underlying
run. Cancellation
of a direct observer task only cancels the shielded waiter; context exit still
owns dispatch cancellation/drain. Remote timeout still leaves server work active.
Rate limits, server polling hints, safe failures and bounded report retrieval
remain owned by the existing remote waiter.

## Compatibility and trade-offs

Callbacks and CLI switches are additive. Omitted callbacks preserve existing
wait behavior and return models. Legacy local keyword runs remain compatible
without progress; a requested observer is limited to unified runs. Legacy remote
callbacks receive validated lifecycle dictionaries; typed remote/direct callbacks
receive `RunStatus`. No REST schema or persistence changes are required.

This optimizes useful lifecycle visibility and avoids extra remote requests;
it deliberately defers live request counters and partial metric aggregation,
which need a separate measurement/persistence contract. Full agent validation
requires separately approved real-model traffic; lifecycle presentation tests
make no inference calls.
