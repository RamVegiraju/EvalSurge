# ADR 0009: Simple v2 façade and Databricks App boundaries

- Status: Incremental implementation; designated maintainer review required
- Date: 2026-10-07

## Context

EvalSurge's v1 contract accurately exposes its evidence pipeline, but the basic
performance workflow requires callers to understand evaluation planning, endpoint
protocol details, polling, and operator connection configuration. Databricks Agent
Runtime also adds an App resolver and a durable invocation protocol that are not the
same concern: an App is a hosting and authentication location, while
`/api/invocations` is one invocation protocol. Treating either as the other would
couple the load engine to one hosting provider.

The current runtime owns one POSIX artifact directory, admits one run, and starts one
Locust subprocess on the API host. Databricks Apps have ephemeral local storage, a
short shutdown grace period, horizontally scaled web instances, and bounded proxy
request lifetimes. Deploying that coordinator unchanged as an App would make run
ownership and evidence durability unreliable.

Expected initial load remains local and bounded: one active run, at most 100 closed-
loop users, 10,000 attempts, and a one-hour dispatch window. Capacity campaigns run
ordered single-level stages through the same engine; they do not create a second load
implementation or claim sustainable capacity without warmup, repetition, thresholds,
and generator-health evidence.

## Decision

1. Keep `/v1` compatible and add a `/v2` façade translated into the existing
   coordinator. The basic request contains a registered target, independent cases,
   bounded load, and an explicit evaluation mode: `off` (default), `automatic`, or
   `explicit`. `off` cannot invoke a planner or judge.
2. Keep endpoint URLs and credentials operator-owned. A basic v2 caller selects only
   an opaque registered target name. Direct URLs remain an advanced local Python/v1
   facility and are never combined with caller-supplied credential names.
3. Separate provider concerns behind four boundaries:
   - `TargetResolver` maps an operator-owned target name to an exact URL, protocol,
     authentication source, and non-secret metadata.
   - `InvocationProtocol` encodes and decodes one fixed wire contract.
   - `RunnerBackend` executes an immutable single-level run.
   - `EvidenceStore` persists metadata and bounded artifacts.
   The local implementations remain authoritative for this milestone.
4. Add a Databricks App resolver that uses the Databricks SDK and operator-selected
   server configuration. The public API never accepts a Databricks profile, OAuth
   token, workspace host, or arbitrary App URL. Authentication refreshes at request
   time and is bound to the resolved App origin.
5. Support synchronous Durable Agent Server `/api/invocations` first, including a
   client invocation identifier and optional session identifier where the frozen
   target permits it. Legacy MLflow Agent Server `/responses` remains supported.
   Background execution, event reconnection, and cancellation require a separate
   lifecycle design before use in measured load.
6. Return v2 admission immediately after validation and admission. Planning is a run
   phase, not work performed before the 202 response. The remote SDK owns polling and
   honors server retry guidance. v2 errors use stable domain codes with `phase`,
   `retryable`, and safe guidance; v1 envelopes remain compatible.
7. Expose lightweight status and a separate typed result/report. Compute a decision
   summary from independently retained performance, quality, and evidence-gap states;
   do not turn lifecycle completion into a quality pass.
8. Add secret-free capabilities and configuration diagnostics. Capabilities may list
   registered target names and protocols, limits, and evaluation/tracing readiness,
   but never URLs, workspace hosts, profiles, environment variable names, or tokens.
9. Add bounded names, tags, timestamps, cursor history, export, archive, and retention
   primitives for local storage. These features do not imply tenant isolation.
10. Model capacity campaigns as ordered submissions to the existing runner boundary.
    Warmup observations are excluded, stages are repeated, acceptance thresholds are
    explicit, and runner placement and generator health are evidence.

## Data flow

`v2 request -> registered target lookup -> v1 translation -> admission -> optional
planning -> inference/evaluation preflights -> one Locust run -> trace collection ->
captured-answer evaluation -> typed summary/report`.

For Databricks Apps, target lookup resolves `app name -> exact App origin + Agent
Runtime path -> SDK-owned OAuth header source`. Locust still performs the invocation;
the resolver does not invoke the target. Correlation identifiers flow through the
request and returned trace header/event into the existing bounded collector.

## Failure modes and safeguards

- Unknown, disabled, or unauthorized targets fail before planning or traffic.
- App lookup or OAuth failures use stable safe codes and never echo SDK exceptions.
- App discovery/authentication is thread-offloaded before admission, but nominal
  SDK HTTP/retry budgets do not bound credential refresh or CLI subprocess wall
  time. Hard termination requires the deferred process-isolation production gate.
- A failed inference or judge preflight prevents measured load, as in v1.
- Worker spawn failure remains a separate load failure with no judging.
- Duplicate v2 submissions require an idempotency key with identical canonical input.
- Background Agent Runtime jobs are not silently polled or replayed; the synchronous
  adapter rejects unsupported responses.
- Campaigns stop on configured saturation/failure rules and preserve completed stages.
- Local disk loss, process loss, or multiple App replicas remain unsupported until a
  durable runner and evidence store are implemented.

## Bottlenecks and scaling path

Locust CPU, sockets, network placement, journal fsyncs, target capacity, trace reads,
and judge throughput can each dominate elapsed time. The report must distinguish the
dispatch window from preflight, drain, profiling, and evaluation. One concurrency
sample is descriptive, not a capacity limit.

Hosting the control plane on Databricks Apps is deferred until `RunnerBackend` dispatches
to a dedicated worker or Lakeflow Job and `EvidenceStore` uses a transactional metadata
store such as Lakebase plus an object/Volume artifact store. That design also requires
leases with fencing, heartbeats, per-run ownership, native identities, quotas, egress
policy, retention, and a shutdown-safe web tier.

## Compatibility and trade-offs

The v2 translation avoids a flag-day coordinator rewrite and leaves v1 clients valid,
at the cost of maintaining two public schemas during the 0.x period. Registered target
presets make the golden path smaller and safer, but require operator setup. Synchronous
Agent Runtime support is less feature-complete than background/resumable execution,
but produces unambiguous per-attempt timing without hidden polling. Provider-neutral
interfaces add modest structure now and prevent Databricks App discovery, OAuth, and
wire semantics from becoming hard-coded Locust behavior.

## Validation

Contract tests must cover v1 compatibility, v2 translation and default-off evaluation,
safe domain errors, SDK polling, App resolution/OAuth boundaries, protocol decoding,
capability redaction, lifecycle bounds, and campaign stop rules. Live Databricks tests
remain opt-in and require an explicit `--profile`, user consent, and a bounded budget.
The ordinary suite uses controlled SDK/provider boundaries and no paid calls.

## Implementation scope — October 7

This increment implements v2 admission/status/results/report/cancel/capabilities,
deferred owned planning, SDK/CLI, task-local operator settings, static diagnostics,
and synchronous App resolution/OAuth/protocol support. It retains concrete local
coordinator/storage boundaries rather than adding unused runner/store dispatchers.
Items 9–10 (full lifecycle/retention and capacity campaigns), distributed backends,
background Agent Runtime execution, and shared hosting remain future work.

SDK source inspection established that ambient host/credential fields take precedence
over named profile fields. App resolution fails closed on those overrides instead
of mutating the process environment or guessing credential provenance. Configured
protocol order selects the operator default. Default App sessions are per attempt;
fixed operator sessions explicitly opt into stateful conversation behavior.
