# Bring a local HTTP agent or a Databricks App

Agent frameworks are not the integration boundary. Any framework or custom
implementation can be benchmarked when its hosted endpoint satisfies a supported
wire contract. Named framework examples are not a supported-framework allowlist.

Both are supported through the same coordinator, fail-fast preflights, sole
Locust engine, and captured-answer evaluation. Your agent must already be running,
reachable from the runner, and compatible with a supported input/response contract.
EvalSurge does not deploy agents, import remote source, run arbitrary Python
callables, or automatically instrument an agent's internal model/tools/memory.
Copyable LangGraph and OpenAI Agents requests for both hosting options are in
[the four framework-target examples](FRAMEWORK_TARGET_EXAMPLES.md).
For the minimal JSON contract and a thin wrapper around an existing LangGraph,
OpenAI agent, or CrewAI crew, start with [the hosted-agent recipe](AGENT_INTEGRATION.md).
Users choose the bounded concurrency to test; knowing the target's capacity is
not an admission requirement. A successful first-case probe proves protocol
readiness for that case, not capacity or every case's compatibility.

## Direct Python setup

Use `EvalSurge(targets={"agent": Agent.http(url)})` or bind an existing App with
`Agent.databricks_app(name, profile="YOUR_SELECTED_OAUTH_PROFILE")` outside the
benchmark request. `client.start(RunCreate(...))` selects the alias through
`target.connection_id` in either case. No API server or operator TOML is required.
See [the Python guide](PYTHON_API.md) and [journey scripts](../examples/README.md).
The direct caller is the operator; profiles and credentials remain configuration,
not public request fields. Hosting/authentication resolution remains independent
of the selected wire protocol.

## Choose where load runs

- `EvalSurge(...)` / `EvalSurge.local()` / `local_async()`: install
  `evalsurge[server]`; your Python caller's machine runs the load. Bind an authorized
  HTTP endpoint or deployed App outside the v2 request.
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

## Optional server: register both targets

The following registration is only needed for [server execution](OPTIONAL_SERVER.md),
not the direct Python setup above.

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
| `http-json` | Raw nonempty case input object, unchanged | Complete JSON object with nonempty `outputs` text, optional validated usage/trace ID; no TTFT/first-event |
| `openai-chat` | Exactly `query` or `messages`; Chat messages/model, `stream=true` | Supported Chat Completions SSE; answer-text TTFT |
| `databricks-agent-runtime` | Exactly `query` or `messages`; generated invocation/session IDs, `stream=false`, `background=false` | Completed invocation with string, `answer`, or supported completed assistant messages; no JSON TTFT/first-event or token usage |

The App default is current DurableAgentServer `/api/invocations`. No
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

## Legacy protocol compatibility

Existing MLflow AgentServer Apps can explicitly select `mlflow-agent-server`
for `/responses`. This adapter accepts exactly `query` or `messages`, sends
`{"input": [...], "stream": true}`, and requires supported Responses-style SSE
with answer text and terminal completion. It remains available for existing
HTTP/App bindings, not as a recommended path for new App deployments.

Official [Agent Server guidance](https://docs.databricks.com/aws/en/agents/deploy/agent-server),
checked October 8, 2026, labels MLflow AgentServer **legacy** and recommends
DurableAgentServer. It does not state a removal date on that page. Removing
EvalSurge's public adapter requires a migration/release decision and maintainer
review; hiding it from onboarding does not silently change existing requests.

## Verification boundaries

Controlled tests exercise local HTTP, real frameworks/native MLflow, remote SDK/API,
Databricks SDK/OAuth boundaries, and one Locust engine. On October 8, both native
LangGraph and OpenAI Agents Apps passed 500/500 measured requests at five users
through actual loopback HTTP v2 submission, with separate failed probes stopping
all measured traffic. These samples used real GPT-OSS-120B, no tools/history/traces,
and evaluation off. See [the framework examples](FRAMEWORK_TARGET_EXAMPLES.md) and
[VALIDATION.md](../VALIDATION.md) for exact revisions, budgets and limitations.

The historical October 7 consented
native App check passed fail-fast, 500/500 measured requests at concurrency five,
and a tiny explicit relevance/correctness check. See [VALIDATION.md](../VALIDATION.md)
for the retained failure, correction, budgets, and gaps. It used the local facade/
registered resolver, not a deployed EvalSurge service or live `/v2` HTTP submission.

Endpoint-only access cannot reveal internal tool/model/memory timings. Profiling
requires authorized correlated agent-side MLflow traces. The live samples have no
agent memory or tracing. No short single-level run establishes sustainable capacity,
general agent compatibility, judge calibration, or shared-hosting readiness.
