# Hosted-agent integration contract

## Minimum and optional evidence

Minimum: an authorized streaming URL exposing the selected wire adapter, workload
samples, and load limits. Tools/memory may exist internally, but endpoint-only access
cannot reveal their timing. Without instrumentation the report remains client-only.
`framework` is descriptive; it does not cause the benchmark server to import a remote
agent or guess its setup.

Optional: a reviewed manifest, references, trusted registered judges, and instrumented
MLflow traces. The demo framework integrations are real OSS examples, not remote
auto-instrumentation. Their in-memory/checkpoint sessions are request-isolated and
do not implement production durable multi-turn memory.

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

Enable `mlflow.langchain.autolog()` for LangGraph and
`mlflow.openai.autolog(disable_openai_agent_tracer=True)` for OpenAI Agents. The latter
replaces native export processors; configure this deliberately in an owned process.
Mark custom memory I/O spans with `evalsurge.category=memory`. Retrieval spans should
record actual documents for trace-aware judges, not only a count.

The collector flushes process-local MLflow exports outside the load window, then
fetches and retries eventual remote exports with bounded
backoff, validates experiment and exact correlation, and rejects incomplete/invalid
trees. A 60-second admission deadline bounds starting fetches, not a stalled remote
transport call. Remote MLflow HTTP timeouts/retries must be configured; hard process
deadlines for this phase are a production gate.

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
not a bare `trace_id` column.

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

The GPT-5.4 mini demo uses `reasoning_effort="none"` for tool-enabled Chat
Completions. Its endpoint rejects reasoning-enabled function tools on that wire
API; the LangGraph demo's non-tool model call can use low reasoning. Validate model
capabilities before changing these settings; do not retry incompatible payloads.

## Planning and approval

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
