# ADR 0004: Fail-fast inference before measured load

- Date: October 5, 2026
- Status: Proposed for maintainer review; implemented for the local alpha
- Review owner: repository maintainer

## Context and assumptions

A valid target URL or HTTP 200 does not establish working inference. Authentication,
provider settings, tool execution, or streaming can fail on the first invocation.
Starting concurrent load in that state duplicates failures, cost, and agent actions.
Preserve one Locust engine, the asynchronous 202 run lifecycle, frozen plans, and
historical evidence. The local service still admits only one run.

## Decision and data flow

1. Validate input/admission/idempotency and freeze or reuse the evaluation plan.
   Planning can still make a provider call before submission returns.
2. Persist `preflighting` with load queued. Use the existing Locust worker with
   concurrency one, one attempt, and the original per-attempt deadline.
3. Send workload case zero using the same adapter, model, usage setting, exact
   connection, authentication, and SSE validation as measured load. The probe must
   finish with a 2xx SSE response, complete nonempty answer, complete journal, and
   successful worker exit. No retries, redirect following, or model fallback.
4. Only a passed check launches the configured load worker. Preflight storage under
   `preflights/{run_id}/` is separate from measured journals under `{run_id}/`.
   Correlation uses the same run ID and a unique probe request ID.
5. Failure terminates the run with `status=failed`, safe `preflight.error` guidance,
   and skipped load/profiling/evaluation. A report with no measured rows remains
   readable. Cancellation/interruption also prevents load.
6. The probe is excluded from load counts, timing/throughput, trace profiles,
   sampling, and judging. It is not a quality verdict or a capacity certification.

## Bounds, failures, and trust

Each successful run makes **one extra agent invocation** beyond `load.max_requests`.
It may incur spend, execute tools, mutate memory, or warm caches. Users must authorize
those actions; there is no rollback. The probe sends the first case, not a synthetic
health check. It does not prove that other cases, later requests, or load levels work.

The worker has a five-second dispatch window, the same 0.1–120-second full-request
deadline, and the existing 45-second outer startup grace. Thus the parent deadline
is at most 170 seconds, followed by at most five seconds for termination/kill.
Cancelled active inference drains; it cannot retract a dispatched tool action.
The extra sequential subprocess adds startup latency outside measured load.
One probe duplicates only the first case/config and at most two journal events;
response output remains capped at two million characters. Protected raw artifacts
are not exposed as measured request records.

Errors expose fixed categories/guidance, HTTP status, and correlation IDs, never
provider bodies, exception text, prompts, or credential values. Requests can wrap
a streaming read timeout as ConnectionError; deadline classification uses the
observed lifecycle clock, not exception-message matching.

Restart recovery reads probe evidence and cancels abandoned preflight workers.
It never replays the probe or resumes load. Idempotent replay returns the original
terminal run; new attempts require a new submission key. Worker startup/storage
errors fail closed and skip load.

## Compatibility and trade-offs

No request fields, dependencies, frozen-plan hashes, or submission hashes change.
Existing snapshots default to `preflight.status=not_run`; they are not retroactively
validated. New `preflighting` and `skipped` lifecycle values require enum-aware
clients to update. 202 acknowledges admission, not inference success; callers poll
the run or report for failure. A synchronous 502 would conflate admission with the
background operation and lose the existing resource/idempotency/report contract.

Separate workers favor clear measurement/evidence boundaries and shared code over
one-worker phase-switch complexity. The price is one startup plus one invocation
and possible agent/cache state changes. No hosted-provider capability matrix or
automatic request adjustment is introduced. Shared-hosting gates remain unchanged.

## Verification and references

Regression coverage uses real localhost Locust subprocesses, both wire adapters,
real LangGraph/OpenAI Agents with controlled model transports, failed and complete
streams, missing credentials, deadlines, cancellation, restart/idempotency, safe
reports, and shipped report JavaScript. Live paid validation needs separate consent.

Upstream contracts: [Locust headless execution and stop timeout](https://docs.locust.io/en/stable/running-without-web-ui.html)
and [Requests streaming behavior](https://requests.readthedocs.io/en/latest/user/advanced/#streaming-requests).
Maintainer review is still required for the lifecycle and runner change.
