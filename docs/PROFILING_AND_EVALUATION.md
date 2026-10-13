# Hosted-agent integration contract

## Minimum and optional evidence

Minimum: an authorized HTTP URL exposing a supported SSE or JSON adapter, workload
samples, and load limits. Tools/memory may exist internally, but endpoint-only access
cannot reveal their timing. Without instrumentation the report remains client-only.
`framework` is descriptive; it does not cause the benchmark server to import a remote
agent or guess its setup.

Answer-based judging can use captured inputs, outputs and authoritative references
without internal traces. Traces are required for internal profiling and explicitly
trace-dependent registered scorers, not for evaluation as a whole. HTTP protocol
compatibility and MLflow evidence compatibility are independent. Start with the
[end-to-end integration recipe](AGENT_INTEGRATION.md) for the minimum server
contract and optional trace checklist.

Optional: a reviewed manifest, references, trusted registered judges, and instrumented
MLflow traces. The demo framework integrations are real OSS examples, not remote
auto-instrumentation. Their in-memory/checkpoint sessions are request-isolated and
do not implement production durable multi-turn memory.

This applies equally to runner-local HTTP agents and Databricks App targets;
[supported targets](TARGETS.md) documents their different discovery/authentication
but shared inference/load/evaluation path. An App Runtime Store/session ID does
not supply agent memory or MLflow traces.

## Load-only tracing golden path

Evaluation and tracing are independent. Keep `evaluation.mode="off"` (the default)
and configure a private operator trace scope in the runner:

```python
from benchmark_agents.settings import Settings, TraceSettings
from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference

settings = Settings(
    tracking_uri="http://localhost:5000",  # existing operator-owned store
    tracing=TraceSettings(enabled=True, experiment_ids=("123",), max_traces=100),
)
request = RunCreate(
    target=TargetReference(connection_id="agent"),
    cases=[Case(input={"query": "Can an opened item be refunded?"})],
    load=Load(concurrency=5, duration_seconds=10, max_requests=5),
)
with EvalSurge(
    targets={"agent": Agent.http("http://127.0.0.1:8000/invoke", protocol="http-json")},
    settings=settings,
) as client:
    report = client.start(request).wait()
```

Start the actual agent and tracking service separately; neither is created by this
example. The `local_runner_traced_http_target.py` journey provides the same bounded
load-only flow with explicit endpoint, tracking URI and experiment arguments.
The same request vocabulary can bind `Agent.databricks_app(...)`, but the current
collector supports experiment-scoped trace locations only. MLflow's newer UC
schema/table-prefix trace IDs are retained, but collection returns
`unsupported_scope` without fetching protected trace content until experiment
membership has a reviewed verification contract. Governed Databricks trace
coverage is therefore not yet established. Do not silently use legacy
storage to bypass this limitation. Trace-read credentials belong to the runner;
trace-export credentials and instrumentation belong to the agent.
Do not put either into RunCreate. A profile reference in `databricks://<profile>`
must be explicitly selected; no profile or broad experiment is auto-discovered.

Before measured traffic, configured tracing now verifies a complete, correctly
scoped trace from the **same excluded inference probe**, even with no judges.
Missing/invalid exports or mismatched metadata fail with `trace_readiness_failed`
and safe guidance in independent `profiling_preflight`; the probe's successful
inference remains `passed`, profiling fails and measured load is skipped. No
additional target invocation occurs. Successful readiness verifies one trace,
not all future exports, concurrency capacity, or instrumentation fidelity.

In an agent process using the optional HTTP serving helper, an explicit boundary
wrapper can preserve real correlation:

```python
from evalsurge.serving import create_app
from evalsurge.tracing import traced_handler

# real_handler is your existing async agent handler returning AgentAnswer.
# Configure local tracking/auth and select an existing experiment beforehand.
app = create_app(
    traced_handler(real_handler, experiment_id="123"),
    isolation="request",
)
```

This wrapper executes the handler once, records actual protected input/output,
attaches benchmark run/request metadata, and returns the real trace ID. It does
not create experiments, enable autologging, or invent model/tool/retrieval spans.
Enable and verify the native integration for your framework in the agent process
(for example, LangGraph uses `mlflow.langchain.autolog()`); do not stack duplicate
instrumentation. Existing native serving roots can attach the correlation metadata
directly instead. Additional threads require deliberate context propagation.
Handler exceptions retain their real native error-trace IDs in safe HTTP headers;
failed HTTP attempts can therefore remain correlated without becoming successes.
No trace ID is invented when the process/network fails before returning headers.

On Databricks, select/provision governed Unity Catalog trace storage separately,
including catalog/schema, SQL warehouse and the exact bound experiment. Use the
agent's native instrumentation: this experiment-only helper explicitly rejects
Databricks tracking URIs rather than overriding a governed destination with legacy
storage. Governed collection remains blocked as described above; neither the
helper nor the runner provisions resources.
Enable asynchronous agent export and flush at lifecycle cleanup, not per request.
Instrumentation/export overhead remains in measured response latency; it is not
subtracted or claimed to be zero.

Every invocation may export a trace, but report collection is bounded (at most
200 traces per run, 1,000 spans per trace). Sampling, scope, export and collection
budgets remain explicit gaps. A boundary-only span establishes mapping and handler
duration, **not internal bottlenecks**. Uninstrumented endpoints remain supported
as client-only reports with unknown internal timings rather than invented zeros.
See [ADR 0020](adr/0020-load-only-correlated-trace-readiness.md) for semantics,
failure behavior, review gates and limitations.

## Correlation

EvalSurge forwards `X-Benchmark-Run-ID` and `X-Benchmark-Request-ID`. Inside the agent's
root MLflow span, attach:

```python
mlflow.update_current_trace(
    metadata={
        "evalsurge.run_id": run_id,
        "evalsurge.request_id": request_id,
    }
)
```

Return `X-MLflow-Trace-ID` if the root ID is available before response headers, or emit
one single-line metadata event:

```text
data: {"type":"evalsurge.trace","trace_id":"tr-..."}
```

The metadata event starts first-event timing, **not answer-text TTFT**. Keep the root
alive through streaming, tools, and memory writes. Drain OpenAI Agent `stream_events()`
until it finishes; final text alone is not runner completion.

The shipped LangGraph demo enables `mlflow.langchain.autolog()`. Its OpenAI Agents
counterpart wraps the public model-stream hook in one explicit MLflow span and
disables both OpenAI autologging and native Agents trace export. This avoids duplicate
instrumentation and a provider-null-ID reconstruction failure. Do not stack tracing
strategies or assume a different provider works without checking actual traces.
MLflow's native Agents/OpenAI integrations are alternatives to review deliberately
in an owned agent process, not automatically enabled by EvalSurge. See
[the verified model/instrumentation boundaries](MODEL_COMPATIBILITY.md).
Mark custom memory I/O spans with `evalsurge.category=memory`. Retrieval spans should
record actual documents for trace-aware judges, not only a count.

The collector flushes process-local MLflow exports outside the load window, then
fetches and retries eventual remote exports with bounded
backoff, validates experiment and exact correlation, and rejects incomplete/invalid
trees. A 60-second admission deadline bounds starting fetches, not a stalled remote
transport call. Remote MLflow HTTP timeouts/retries must be configured; hard process
deadlines for this phase are a production gate.

Native incremental export can make spans visible before benchmark correlation
metadata. Only absent run/request keys in an already matching trace/experiment
receive the existing four-fetch visibility budget (0.5/2/4-second backoff).
Every reread must pass all exact scope checks; conflicting present values fail
immediately. Exhausted absence stays a `missing` evidence gap, never permission
to load or judge. No target is reinvoked and no agent-side flush is added.

For a bounded demonstration with three actual tools and a disclosed slow shipping
step, see [the multi-tool heatmap sample](../examples/journeys/multitool_heatmap/README.md).
Its earlier source-workflow smoke used real model inference; native collector
regressions and public sample contract checks are separate non-inference evidence.

## Honest attribution

- Inclusive spans can overlap and must not be summed into wall time.
- Self time subtracts the union of direct-child intervals.
- Wall occupancy chooses deepest active leaves; multiple leaves become `parallel`.
- Simultaneous trace leaves are not proof of independent concurrent operations:
  duplicate or misparented instrumentation can contribute to the `parallel` bucket.
- Waterfall timestamps are relative to the agent root, not a synchronized client clock.
- Client-minus-agent duration is a nonnegative difference, not proven network time.
- Missing traces, invalid trees, rejected scope, collection failure, and budgets remain
  explicit coverage gaps. No exact causal critical path is reconstructed.
- Hotspots are inclusive per-name p50/p95 across observed spans, not causal diagnoses.
- A short, single-level closed-loop run cannot establish sustainable capacity.

## Bringing MLflow judges and data

Supply cases through `evaluation.samples`, including authoritative `expectations`.
The service never fabricates those references. If no cases exist, planning can suggest
criteria, but load generation remains blocked until cases are supplied.

Operators configure `BENCHMARK_SCORERS` as JSON:

```json
{
  "policy": {
    "name": "policy_accuracy",
    "experiment_id": "123",
    "version": 2,
    "required_fields": ["inputs", "outputs", "expectations"],
    "description": "Check responses against authoritative policy"
  }
}
```

Use `evaluation.registered_scorers=["policy"]`. With no explicit catalog selections,
the LLM may also suggest allowlisted aliases unless this field is `[]`. The server
retrieves the **exact** version via `mlflow.genai.scorers.get_scorer`, freezes public
serialized-definition hashes, and rechecks them before scoring. No source uploads or
caller-selected store URLs are accepted. Registered scorers run through native
`mlflow.genai.evaluate`; trace-aware data includes actual correlated **Trace objects**,
not a bare `trace_id` column. Only scorers explicitly requiring `trace` receive that
column, and every selected record has a verified Trace. Output-only scoring never
mixes traced records with nullable/missing traces.

Before load, selected judges assess the captured first-case probe once. Missing
required evidence/trace, provider errors, or absent assessments block load with
safe guidance; a negative quality verdict does not. These native readiness runs
are tagged `evalsurge.phase=evaluation-preflight`, separate from benchmark scores.
See [readiness and time budgets](USAGE.md#fail-fast-readiness-checks).

MLflow 3.16 permits built-in and `make_judge` registrations on OSS stores. Decorator
`@scorer` registration is restricted to Databricks tracking for security; this API
does not bypass that restriction. Keep custom code in a reviewed environment.

`max_scored_requests` bounds selected answers **per scorer**, not native judge provider
retries, extraction calls, model tokens, or spend. Registered judge model/transport
configuration is retained in its version, and timeout/provider budgets must be reviewed
by the operator. The API's direct catalog judge budgets do not override brought judges.

Read each criterion's `eligible`, `attempted`, `scored`, `judge_errors`, selected request
IDs, native MLflow metrics, and run ID. A boolean-only scorer exposes a descriptive
sample pass rate; numeric/categorical scores do not get reinterpreted as pass/fail.
No overall aggregate pass rate is manufactured.

Each criterion also records `assessments`, one entry per selected request, joined
by exact request-ID tags rather than prompt equality or completion order:

```json
{
  "request_id": "request-123",
  "case_id": 0,
  "status": "failed",
  "value": false,
  "rationale": "The answer allows a refund after the policy deadline.",
  "rationale_truncated": false,
  "error": null
}
```

`passed`/`failed` describe boolean quality verdicts; `scored` has no inferred
threshold. `error` means judge execution failed and includes fixed safe
`error.code`, `message`, and corrective `guidance`, not raw provider/scorer text.
`unavailable` means missing/ambiguous request-correlated evidence. Case IDs are
zero-based. Scalar values are previews; strings and rationales are bounded to
2,000 characters, non-scalar values are omitted, and `rationale_truncated` marks
shortened explanations. Full values remain in MLflow. The sample budget bounds
detail count (at most 1,000 per criterion). Missing rationales remain null.

The report's **Failed assessment details** section shows every recorded negative
boolean verdict and its judge rationale, separately from execution errors.
Rationales may quote private evaluation content; protect reports and do not treat
these explanations as calibrated truth or content-free profiling. Historical
reports without details are not silently backfilled or re-judged.

The October 4 selected-workspace GPT-5.4 mini demo uses `reasoning_effort="none"`
for tool-enabled Chat Completions. That endpoint rejected reasoning-enabled function
tools on that wire
API; the LangGraph demo's non-tool model call can use low reasoning. Validate model
capabilities before changing these settings; do not retry incompatible payloads.

## Planning and approval

This section describes v1 plan inspection/reuse. V2 and the unified direct
`RunCreate` policy default evaluation to off; automatic mode explicitly opts into
planning inside the run. Legacy local `Evaluation(scorers=None)` instead requests
planning; use `scorers=[]` to disable it. For explicit catalog criteria, your own
reviewed registered judge, client-loaded datasets, and evidence edge cases, see
[the quality samples](../examples/quality/README.md).
See [the v2 policy](V2_API.md#submit-and-retrieve-a-benchmark).

`POST /v1/evaluation-plans` accepts an objective and optional `agent_manifest`. The
LLM sees bounded previews, capabilities, and eligible aliases. Deterministic code
checks readiness; a manifest never substitutes for runtime evidence. Inspect the plan
and submit its `plan_id` to approve/reuse it. Changed manifest/data/scorer policy is
rejected. Plans in older formats should be recreated for the new evidence contract.

The first catalog is deliberately small: relevance, correctness, safety, and an
explicitly unimplemented groundedness gap. For custom tool selection, memory fidelity,
or policy checks, bring reviewed registered judges. Automatic creation/calibration of
new arbitrary judges and synthetic benchmark dataset generation are not yet shipped.

## Primary interface references

- [OpenAI Agents streaming lifecycle](https://openai.github.io/openai-agents-python/streaming/)
- [LangGraph custom streaming](https://docs.langchain.com/oss/python/langgraph/streaming)
- [MLflow tracing](https://mlflow.org/docs/latest/genai/tracing/)
- [MLflow scorer registry API](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.genai.html)

Public documentation and installed package implementations are cross-checked by
native integration tests; package lock versions, not examples copied from a skill,
determine supported behavior.
