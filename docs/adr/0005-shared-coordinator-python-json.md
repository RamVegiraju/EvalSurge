# ADR 0005: Shared coordinator, local Python API, and bounded JSON transport

- Date: October 5, 2026
- Status: Proposed for maintainer review; implemented for the local alpha
- Review owner: repository maintainer

## Context and assumptions

Owners need a Python call without manually starting Uvicorn or assembling
environment connection JSON. Hosted HTTP agents need not stream or expose a
specific agent framework. Preserve one Locust engine, the first-case preflight,
frozen plans, phase independence, safe HTTP errors, recovery, and idempotency.

Keep existing single-owner POSIX storage and workload limits: one active run,
100 users, 10,000 measured attempts, 1,000 cases, and at most 100 report rows/page.
Each run still adds one preflight action. Assuming a 2 KB journal event pair,
10,000 requests retain roughly 20 MB before snapshots, profiles, and traces.
The worst-case JSON body is two million decoded bytes per active request:
100 users can retain roughly 200 MB of bodies before parser/capture overhead.
These are resource estimates, not tested capacity. No new provider spend is
implied by a performance-only Python example.

## Decision and data flow

1. Extract `RunCoordinator` from FastAPI's closures. It owns the storage lock,
   admission, persisted plans, idempotency index, tasks, cancellation, recovery,
   preflight, load, profiling, and evaluation. REST only validates/authenticates
   HTTP and presents the domain results/errors with the existing envelope.
2. Publish `evalsurge` as a small facade over this coordinator. Synchronous contexts
   own a coordinator thread/event loop; async contexts use the caller's loop.
   No nested event loop, web-server startup, or second load engine.
3. Separate `Agent.http` wire protocol from its exact operator connection.
   Validate and copy inputs/bindings before scheduling. Pass the binding to both
   subprocesses instead of temporarily mutating global environment configuration.
   Bearer credentials remain inherited environment references; no token values
   enter serialized connection records. REST never accepts a caller binding.
4. Add `http-json`: raw sample inputs → bounded JSON object with nonempty outputs,
   optional known output-token count, and optional trace ID. JSON body reading
   uses streaming transport only to enforce limits/deadlines, not to claim TTFT.
   Preflight and load share adapter logic. Missing usage/TTFT stays unknown.
5. Python waits raise a report-carrying safe `RunFailed` for failed/cancelled/
   interrupted runs. Waiting timeouts do not cancel owned work. Completion with
   gaps is a readable lifecycle outcome, not a passing quality verdict.
6. Context exit stops admission, drains pending planning/submission and owned work,
   and releases the same filesystem lock as REST. It cannot roll back tools or
   impose a hard sandbox/deadline on native scorer code.
7. Enforce the shared eight-million-byte UTF-8 policy/workload limit before
   planning. On persistence failure, fail closed for new admission and keep an
   explicit terminal in-process receipt where possible. Do not replay an
   unscheduled queued receipt or lose terminal state solely because fsync fails.

## Failures, trust, and trade-offs

Loop/thread isolation makes sync Python and async applications usable at the cost
of context ownership and explicit blocking semantics. Use async clients when the
target shares the caller's event loop. One coordinator avoids lifecycle drift;
REST remains asynchronous 202, while Python can await the existing resource.
Deep copies protect admitted runs and returned snapshots from caller mutation.

JSON's narrow explicit schema favors clear provider-independent semantics over
arbitrary JSONPath/configuration or executable adapters. Invalid media/body/type,
empty answers, inconsistent trace identifiers, HTTP errors, and deadlines fail
early. Agent errors never become retries or automatic model fallbacks. Profiles
require the same experiment/correlation checks; JSON trace IDs are not evidence
until verified. Raw captures remain sensitive local evidence.

The coordinator does not relocate load: local Python generates load locally;
REST still generates it on the service host. Runner CPU/network/fsync can become
the bottleneck. Capacity methodology and shared-hosting gates are unchanged.
Heavy optional-dependency redesign is deferred until imports and planning rubric
dependencies can be separated without breaking current environments.

Snapshot and compact-summary writes are not one filesystem transaction. Startup
therefore rebuilds compact metadata from authoritative run snapshots once, rather
than trust potentially stale summaries after a partial write. This sacrifices
cold-start I/O to preserve truthful history; paginated history still uses the
compact in-memory index. Indexed transactional storage remains a hosting gate.
Final write failures retain readable in-process terminal outcomes and warn that
they may be lost on restart. Missing terminal profiling artifacts produce an
explicit gap report, not an indefinitely pending report. Shutdown remains shielded
through repeated waiter cancellation until owned writers drain.

## Compatibility, review, and verification

Keep `benchmark_agents` imports and existing REST routes/statuses. New request
adapter/error enum members are additive but enum-exhaustive clients must update.
Preserve legacy default-on usage idempotency hashes and frozen plan format 3.
No migration rewrites saved evidence or repeats old requests.

Verify REST regressions and local sync/async facade behavior, input isolation,
lock ownership, shutdown/cancellation, idempotency/restart, actual Locust JSON/SSE
success/failure/deadline paths, missing usage/TTFT, both real frameworks, native
MLflow judging, report rendering, OpenAPI, and wheel packaging.
Maintainer review remains required. Databricks App resolver/OAuth, tracing helpers,
staged capacity tests, optional extras, public-index release, and paid validation
are explicitly deferred, not silently claimed by this milestone.
