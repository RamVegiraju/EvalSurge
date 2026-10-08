# ADR 0012: A small hosted-agent contract with independent evidence capabilities

- Date: October 8, 2026
- Status: Proposed; documentation applied, no runtime/API removal implemented
- Review owner: designated repository maintainer

## Context and load assumptions

Users want to benchmark an existing LangGraph, OpenAI Agents, CrewAI or other agent
without learning the coordinator's internals. Framework, hosting, invocation wire
format and trace export are different concerns. An endpoint is not evidence of
internal spans; traces are not mandatory for answer-only evaluation. Requiring users
to know supported concurrency defeats the purpose of a load test.

The beginner workload remains two closed-loop users, a ten-second dispatch ceiling,
ten measured attempts and one excluded first-case probe. It is a bounded first
observation, not a capacity result. Existing limits remain one active run per owner,
100 users, 10,000 attempts, 1,000 cases and an 8 MB request. Each agent invocation
can make multiple model/tool calls; request caps are not spend caps. Optional
evaluation adds judge readiness and sampled assessments, plus planning in automatic
mode. Trace collection remains opt-in and bounded, currently up to 200 traces.

## Proposed design and current documentation decisions

1. Publish two onboarding choices: an existing HTTP endpoint and a deployed
   Databricks App. Direct Python is the default; remote execution stays optional.
   Both use the same `RunCreate`, cases, load and evaluation vocabulary.
   Framework names are illustrative recipes, not an allowlist or a required SDK
   dependency. Any framework/custom implementation satisfying the endpoint
   contract uses the same invocation and answer-evaluation pipeline. Adding a
   framework alone does not require an EvalSurge hosting or protocol adapter;
   internal trace instrumentation has its own separate compatibility boundary.
2. Recommend the explicit `http-json` contract for a minimal custom endpoint:
   forward nonempty case input unchanged, require a complete nonempty `outputs`
   string, and retain optional validated trace/usage evidence. Thin framework
   wrappers live in the customer's agent process. Do not make Locust import or
   execute uploaded graphs, agents, crews or arbitrary decoder code.
3. Recommend DurableAgentServer `/api/invocations` for new Databricks Apps.
   Current official docs label MLflow AgentServer legacy, not a dated removal.
   Remove its choice from beginner documentation, not existing runtime enums,
   registered targets, v1 contracts or SDK bindings. A later public-adapter removal
   requires a release/migration decision, caller inventory, focused regressions
   and designated review. No fallback or protocol probing traffic is introduced.
4. Describe concurrency as the load users choose to attempt. The first-case probe
   validates protocol/readiness, not target capacity or all cases. Incremental
   capacity campaigns require separate warmup/repetition/SLO and generator-health
   semantics; do not silently auto-increase load or infer capacity from a smoke run.
5. Make evidence capabilities independent: client measurements, answer evaluation,
   optional internal profiling and trace-required evaluation. Only trace-required
   scorers require verified probe traces before measured load. Missing optional
   traces remain gaps; answer-only judges still operate on eligible captured answers.
6. Keep future extension boundaries small and aligned with ADR 0009:
   - Hosting resolver/authentication: bind operator identity to an exact destination.
   - Invocation protocol: encode input and decode completion/answer/timing/IDs.
   - Trace source/collector: obtain authorized, correlated internal evidence.
   - Existing runner/evidence persistence: execute and retain measurements.
   New hosts reuse an existing protocol where possible. A new trace exporter does
   not require a new load engine or hosting provider. Do not add unused abstract
   dispatchers or untrusted runtime plugins just to represent this separation.
7. A future capability/readiness presentation should distinguish configured,
   observed and unavailable evidence, with safe corrective guidance. Static doctor
   must remain non-invoking. One consented inference preflight stays explicit; no
   hidden diagnostic model calls, retries or synthetic trace substitution.
8. A future convenience serving helper can normalize customer-owned execution to
   the simple contract and propagate correlation. It must preserve actual inputs,
   failure/completion, state isolation and timing. It is not shipped by this ADR;
   framework recipes are documentation, not production deployments or live parity.

## Data flow and ownership

`existing framework -> customer-owned hosted adapter -> authorized HTTP endpoint`.

`direct/remote RunCreate -> operator binding + hosting resolver -> protocol
validation -> frozen evaluation plan -> one excluded probe + selected-judge
readiness -> one Locust load run -> protected journal -> independent scoped trace
collection -> native MLflow scoring of captured answers -> typed report`.

Agent-side instrumentation exports full traces to its authorized MLflow store and
returns root IDs. EvalSurge validates experiment, trace ID and exact run/request
metadata; it does not search arbitrary workspace traces or infer spans from HTTP.
Raw workload/evaluation content is protected; profiling projections remain
content-free. Credentials, source, registry destinations and trace scopes are
operator-owned, not submitted in public `RunCreate`.

## Bottlenecks, failure modes and trade-offs

- The JSON recipe is easy to implement but intentionally sacrifices TTFT and
  per-token timing. Do not simulate streaming after a complete answer to recover it.
- Adapter/schema/auth failures stop measured load. Overload during measured load
  remains evidence, not proof of an invalid integration. No automatic target retry
  means provider/agent-native retries must be disclosed separately.
- Shared framework/session state, CrewAI thread-pool limits, model/tool throttling,
  runner CPU/network/journal fsync and trace export lag can affect measurements.
  Request-isolated IDs do not guarantee isolation of shared stores/tools/globals.
- Native Runtime session ordering may serialize a fixed shared session; default
  per-attempt sessions do not themselves enable history or memory. Runtime Store
  persistence is not trace instrumentation.
- A successful first-case probe cannot guarantee all cases, concurrency capacity,
  future trace export, judge calibration or sustainable throughput. Missing
  optional evidence and independent phase failures must stay visible.
- Keeping a legacy adapter preserves callers at the cost of an advanced compatibility
  surface. Deleting it without migration would simplify internals but break existing
  HTTP/App targets and published API schemas.
- Hosting/framework-neutral invocation does not promise universal judge providers
  or trace stores. Catalog judges currently use Databricks; internal collection
  currently uses MLflow. CrewAI and new hosts need their own real integration evidence.
- Shared hosting still requires the isolation, egress, quotas, durable ownership,
  retention and dedicated-runner gates in `docs/PRODUCTION_READINESS.md`.

## Verification and next implementation gates

Documentation checks compile bridge snippets and validate request/target schemas
without importing customer agents or invoking models. They establish no runtime
behavior, tracing parity or live deployment result. Record checks in `VALIDATION.md`.

Before shipping serving helpers, new protocols, trace backends or protocol removal,
obtain maintainer review and test real frameworks/native MLflow with authorized
provider boundaries. Before live verification, select the exact profile/resources,
authorize traffic/spend, test first-case failure, measured load, capture/judging,
trace correlation and cleanup, and retain failed evidence. Existing controlled
inference suites need the explicit approval in `AGENTS.md` before execution.

Priority after documentation: reviewed serving/correlation recipes and actual
framework/hosting evidence; then deliberate adapter lifecycle/capabilities and
capacity campaigns. Preserve one Locust engine and no target reinvocation by judges.

## Sources

Official [Databricks Agent Server](https://docs.databricks.com/aws/en/agents/deploy/agent-server)
and [query contract](https://docs.databricks.com/aws/en/agents/query-llms), retrieved
October 8, 2026, recommend DurableAgentServer and label `/responses` servers legacy.
See existing [ADR 0009](0009-v2-databricks-app-boundaries.md),
[ADR 0010](0010-client-input-and-failure-contracts.md) and
[ADR 0011](0011-unified-direct-and-remote-sdk.md) for implemented boundaries.
