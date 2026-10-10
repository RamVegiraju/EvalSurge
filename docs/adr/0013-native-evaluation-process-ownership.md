# ADR 0013: Native evaluation process ownership

- Status: Proposed; designated maintainer review required
- Date: 2026-10-09
- Scope: Native readiness/post-load evaluation, not load generation

## Context

The local MVP owns one benchmark and one Locust engine, at most 1,000 selected
captures per scorer, frozen references/plans and independent phase outcomes.
Native MLflow SQLite persistence lost assessments under concurrent nested SQL
sessions. Offline native storage testing reproduced the failure; fresh serial
process-owned settings retained exact assessments. See the
[diagnosis record](../EVALUATION_STORAGE_DIAGNOSIS.md) for evidence and limits.
Native MLflow reads actual environment and caches exporter state; EvalSurge
task-local configuration cannot safely configure it through ContextVars alone.

## Proposed decision and data flow

Use an owned evaluation child process with bounded startup, execution,
persistence verification and cleanup. For local SQLite, configure serial native
workers and synchronous nonbatch export before native imports. Never mutate
caller/API/notebook global environment or patch installed package internals.

Frozen operator configuration and selected captured pairs → protected child
input → native scorer/evaluation → exact durable feedback verification → bounded
result → report. No target invocation; readiness must pass before measured load.
All evaluation startup/persistence stays outside the measured load interval.
Real target traces are supplied only when required and already validated; capture
artifacts do not masquerade as target/internal traces. Credentials remain
operator-owned, never persisted in environment snapshots or public requests.
Payloads are bounded and protected (0700 directories, 0600 files).

## Failure ownership and trust

Verify exact request tags and source-run metadata, not means or HTTP 200s. Missing,
duplicate or failed persistence, process exit, timeout and cancellation are phase
errors/gaps; false quality verdicts are valid completed assessments. The owner
must terminate/clean workers/exporters and account for committed provider calls.
Termination cannot undo dispatched model calls or trusted scorer side effects.
Registered scorers remain operator-reviewed code, not caller plugins/a sandbox.
Never export raw exceptions, secrets, source or protected diagnostic payloads.

If cleanup itself fails, retain the original timeout/cancellation diagnostic and
record private cleanup uncertainty; a successful result must become failed.
The current regression covers verification failure after stopping a real child,
not continued ownership of an unreaped live child. General cleanup-failure
ownership and parent-crash recovery remain hardening gates. The narrow validation
lease separately requires reaping and verifies PID/process-group absence before
dispatching its next stage. It must stop on uncertainty, not infer cleanup from
having sent a kill signal. Child auth/configuration is inherited through a
detached operator environment; it is not an environment credential allowlist.

Recovery preserves original failed evidence. Quality-only reruns require new
explicit bounds and derived supplemental plans with lineage and exact changed
fields; never silently rewrite frozen destinations or overwrite the failed run.

## Bottlenecks, alternatives and trade-offs

Serial persistence optimizes completeness/ownership over quality throughput;
it does not improve target latency. Startup and bounded capture/trace serialization
add time outside load. A 1,000-row criterion with retries can run much longer than
parallel scoring; provide a separate phase deadline. Capture/trace size governs
memory and storage cost. Cross-process trusted scorer/trace compatibility needs
validation; do not assume it from catalog checks.

The implemented worker deadline begins after parent-side serialization/private
file writing; it is not an end-to-end phase hard deadline. JSON encoding also
materializes content before checking the 128 MiB transfer ceiling. Parent-side
scorer loading, planning and trace collection have separate ownership gaps.
Sending group SIGKILL and reaping the leader does not independently inventory
every descendant; deliberately detached processes and parent crashes remain
outside this mechanism. The bounded live recovery separately checked PID/group
absence. Do not generalize that receipt into universal cleanup or a scorer sandbox.

Pre-staging alone leaves cloning/judge-autotracing concurrency risks and cannot
fabricate internal evidence. Enlarging pools masks contention without establishing
correctness. In-process environment mutation conflicts with unrelated MLflow work
and cached exporters. Remote-store policy may later differ after review; this is
not authorization for distributed infrastructure or shared hosting.

## Compatibility and release gates

Preserve `/v1`, `/v2`, legacy/unified SDKs, frozen sampling/scorer definitions,
per-phase outcomes and the sole Locust engine. No new public credential/plugin
fields, inferred references, framework dependency or target reinvocation.

Required: designated review; native storage regressions with scorer-owned spans
and exact source-run metadata; missing/duplicate failure tests; bounded private
transport, timeout/cancellation/recovery and parent-state isolation; registered
trace-required scorer coverage; separately approved real-model App/local testing.
Controlled-provider tests require explicit disclosure/approval and do not establish
live inference. A storage pass does not establish judge calibration or capacity.

Current status: **proposal with checkpoint implementation; designated review and
broader release verification remain pending**.
Native storage/process regressions pass; independent implementation review
identified and prompted a readiness-diagnostic repair. The October 10 bounded
real-model recovery completed, with exact durable catalog assessments and a
45-check independent saved-evidence audit. Original failed evidence remains
unchanged. Designated maintainer review, trace-consuming registered-scorer
semantics and genuinely live-child cleanup-failure supervision remain separate
gates. See `VALIDATION.md` for actual passing and failing checks; this ADR is not
a release sign-off.
