# ADR 0006: Evaluation readiness before measured load

- Date: October 5, 2026
- Status: Proposed for maintainer review; implemented for the local alpha
- Review owner: repository maintainer
- Extends: ADR 0004 inference checks and ADR 0005 shared coordination

## Context and assumptions

A successful agent invocation does not establish a working judge or MLflow backend.
The retained five-minute run completed load but failed evaluation when partial
trace coverage produced a nullable native Trace column. A long paid benchmark
should not be the first exercise of its selected evaluation pipeline.

Keep one local owner, one Locust engine, frozen operator-owned destinations/scorers,
and asynchronous REST admission. Bounds remain 100 users, 10,000 attempts,
1,000 cases, an eight-MB workload/policy, and bounded trace/span pages. Concurrency
is not a request count; steady-state request rate is approximately users divided
by mean latency with zero think time, subject to generator and downstream limits.
The existing journal/storage/generator bottlenecks remain unchanged.

## Decision and data flow

1. Freeze/reuse the plan, then validate selected criteria, first-case references,
   provider configuration, rubric hashes, and trusted scorer definitions before
   agent traffic. A selected `needs_data` criterion blocks load; explicit empty
   selections request performance only.
2. Invoke case zero once through the existing authorized Locust preflight. Reuse
   its successful capture rather than executing another agent/tool action.
3. For every selected criterion, run one native MLflow readiness assessment,
   sequentially, with `max_scored_requests=1`. Catalog readiness uses the frozen
   timeout/token cap and zero SDK retries. False/zero verdicts are valid completed
   assessments; missing assessments, provider/backend errors, or missing required
   evidence block load. Explicit trace-required scorers require a verified probe
   Trace within the frozen experiment/correlation scope.
4. Return provider failures as native `Feedback(error=AssessmentError(...))`,
   containing only safe fixed diagnostics and no value. This avoids MLflow's
   additional rate-limit retry layer; post-load catalog scoring uses only its
   frozen SDK retry budget. Registered scorers retain operator-owned transport,
   concurrency, extraction, timeout, and retry behavior.
5. Give a native Trace column only to registered scorers explicitly requiring
   `trace`, with a Trace on every eligible record. Output/reference-only criteria
   receive homogeneous inputs/outputs/expectations even with partial trace coverage.
6. Only passing readiness permits measured load. Worker creation errors are
   terminal immediately; exit/deadline/incomplete-result diagnostics retain partial
   evidence. A nonstandard worker exit cannot certify complete measurements.
7. Profiling and sampled quality scoring follow load as before. Stop starting
   further criteria on evaluation failure; already-dispatched native batch work
   is not retractable. Preserve load metrics and all independent phase outcomes.

Readiness adds at most one catalog provider attempt per selected criterion and
one small native evaluation record/run per criterion. It does not add another
target request. Native runs carry `evalsurge.phase=evaluation-preflight`; protected
probe artifacts stay outside measured counts, profiles, sampling, and quality
results. Total report time includes planning, startup, probes, judging, dispatch,
drain, trace collection, and post-load evaluation, not only the requested duration.

## Failures, trust, and trade-offs

Readiness spends a small extra judge budget to avoid a full benchmark with known
broken judging. First-case readiness is not provider availability, all-case
compatibility, capacity, or quality certification. Agent tools/memory/cache effects
and judge disclosure/spend remain explicit. No credential routing, fallback model,
target retry, caller scorer code, or remote registry destination is introduced.

Safe `evaluation_preflight.error` and `load_error` contain fixed codes/messages/
guidance. Reports and Python clients show them without exposing provider bodies,
exceptions, prompts, or credential values. Static failures avoid target calls.
Cancellation waits for in-progress trusted work before preventing load; recovery
marks abandoned readiness interrupted and idempotency never replays actions.

Native scorer threads and trace transports are not a hard execution sandbox.
Trace-fetch admission budgets cannot interrupt already-stalled calls. Hard phase
deadlines/process isolation, quotas, and multi-tenant controls remain release gates.

## Compatibility and verification

REST still returns 202 for admitted work, not a synchronous inference/judge verdict.
Additive `evaluation_preflight`/`load_error` fields preserve historical defaults:
old checks are `not_run`, never retroactively successful. Saved runs/plans are not
rewritten. The deliberate behavior change is that selected unusable criteria now
block load instead of waiting until post-load scoring to reveal known gaps.

Verify native MLflow partial-trace/error contracts, no extra provider retries,
negative versus missing verdicts, reference/trace requirements, inference/spawn
failure, cancellation/restart/idempotency, retained post-load metrics, text-only UI,
actual Requests/Uvicorn/Locust/report round trips, OpenAPI, and packaged assets.
Validate against installed pinned OSS source; latest-upstream upgrades remain
subject to official metadata, compatible resolution, and the dependency policy.
The original failed paid report remains failed; controlled regressions are not a
paid end-to-end retest or production sign-off. Maintainer review is required.
