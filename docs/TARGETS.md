# Bring a local HTTP agent or a Databricks App

Both are supported through the same coordinator, fail-fast preflights, sole
Locust engine, and captured-answer evaluation. Your agent must already be running,
reachable from the runner, and compatible with a supported input/response contract.
EvalSurge does not deploy agents, import remote source, run arbitrary Python
callables, or automatically instrument an agent's internal model/tools/memory.

## Choose where load runs

- `EvalSurge.local()` / `local_async()`: install `evalsurge[server]`; your Python
  process's machine runs Locust. Bind an authorized HTTP endpoint with `Agent.http()`.
- `/v2` with the remote SDK/CLI: the lightweight `evalsurge` client submits work to
  a separately installed API server. The API host runs Locust; the operator registers
  either target type and end users select `target.connection_id`.
- `/v1`: retained URL-based compatibility with exact operator destination/auth
  policy. Remote callers do not acquire permission to submit arbitrary targets.

`127.0.0.1` means the **runner's** loopback, not the remote submitter's computer.
Containers/notebooks must use an address reachable from their actual runner.
Plain HTTP is supported on loopback; remote operator-bound targets require HTTPS.
Configure service authentication/TLS for remote EvalSurge access. See
[Python usage](PYTHON_API.md), [v2 setup](V2_API.md), and
[runner placement](USAGE.md#where-to-run-evalsurge).

## Register both targets

Illustrative operator TOML, with no credentials. Replace the App/profile placeholders
only after explicitly selecting an authorized profile. Registration does not deploy
an App or consent to model/tool/judge traffic.

```toml
artifact_dir = "artifacts"

[connections.local-agent]
kind = "http"
url = "http://127.0.0.1:9001/chat"
protocols = ["openai-chat"]

[connections.app-agent]
kind = "databricks-app"
app_name = "your-app-name"
profile = "YOUR_SELECTED_OAUTH_PROFILE"
protocols = ["databricks-agent-runtime"]
```

Start one API owner with this file:

```bash
BENCHMARK_CONFIG=operator.toml uv run --no-sync uvicorn benchmark_agents.api:app \
  --host 127.0.0.1 --port 8000 --no-proxy-headers
```

The operator owns profiles, URLs, authentication, tracking stores, and scorer code.
App discovery uses the selected SDK workspace; refreshed OAuth stays bound to the
exact discovered origin. Public requests never contain workspace hosts, App URLs,
profiles or OAuth tokens. Conflicting ambient SDK identity/destination settings
fail closed; PAT is not accepted for App access.

## The same end-user request

Submit `POST /v2/runs` with a new `Idempotency-Key`:

```json
{
  "name": "performance-baseline",
  "target": {"connection_id": "local-agent"},
  "cases": [{"input": {"query": "Reply with a short greeting."}}],
  "load": {
    "concurrency": 5,
    "duration_seconds": 180,
    "max_requests": 500,
    "timeout_seconds": 60
  }
}
```

Change only `connection_id` to `app-agent` for the App. This is a bounded request
shape, not permission to send live traffic: review internal agent actions/cost
controls first. The request cap can stop dispatch before three minutes; one excluded
probe and drain add time. Poll the receipt's status link, then read result/report.
Wait timeouts do not cancel accepted work; cancellation cannot undo side effects.

Omitted evaluation means **off**: no planner or judge calls. Use explicit scorer IDs
or opt-in `mode: "automatic"` for judging. Correctness needs your authoritative
references in `cases[].reference`; they are not generated from the agent's answer.
Planning/readiness/judging can incur extra costs. Judges use captured answers,
never reinvoke the target.

## Supported wire contracts

| Protocol | Request | Response / timing |
| --- | --- | --- |
| `openai-chat` | Exactly `query` or `messages`; Chat messages/model, `stream=true` | Supported Chat Completions SSE; answer-text TTFT |
| `mlflow-agent-server` | Exactly `query` or `messages`; `input` messages, `stream=true` | Supported Responses-style SSE; answer-text TTFT |
| `databricks-agent-runtime` | Exactly `query` or `messages`; generated invocation/session IDs, `stream=false`, `background=false` | Completed invocation with string, `answer`, or supported completed assistant messages; no JSON TTFT/first-event or token usage |
| `http-json` | Raw nonempty case input object, unchanged | Complete JSON object with nonempty `outputs` text, optional validated usage/trace ID; no TTFT/first-event |

The App default is current DurableAgentServer `/api/invocations`. Existing MLflow
AgentServer Apps explicitly select `mlflow-agent-server` for `/responses`. No
protocol negotiation, fallback traffic, hidden polling, or target retry occurs.

Fixed message adapters reject extra top-level fields: `custom_inputs`, actor identity,
per-case model routing and resume state are not silently dropped. Nested messages
remain unchanged. `http-json` is an explicit response contract, not a generic custom
App decoder. Background/resumable/HITL execution and operator input mappings remain
deferred. Upstream feature support does not imply EvalSurge support.

Runtime session IDs order invocations; they do not themselves configure agent memory.
Default per-attempt sessions avoid accidentally sharing a conversation. An operator-
fixed session can serialize requests and change answers if the target implements
history. Runtime Store execution persistence is distinct from Session Store transcript
history and Memory Store cross-session facts. The App's internal model API is also
separate from its public protocol: our sample uses a Responses model internally
while exposing `/api/invocations`. Verify model API support independently.

## Verification boundaries

Controlled tests exercise local HTTP, real frameworks/native MLflow, remote SDK/API,
Databricks SDK/OAuth boundaries, and one Locust engine. The October 7 consented
native App check passed fail-fast, 500/500 measured requests at concurrency five,
and a tiny explicit relevance/correctness check. See [VALIDATION.md](../VALIDATION.md)
for the retained failure, correction, budgets, and gaps. It used the local facade/
registered resolver, not a deployed EvalSurge service or live `/v2` HTTP submission.

Endpoint-only access cannot reveal internal tool/model/memory timings. Profiling
requires authorized correlated agent-side MLflow traces. The sample has no agent
memory or tracing. No short single-level run establishes sustainable capacity,
general agent compatibility, judge calibration, or shared-hosting readiness.
