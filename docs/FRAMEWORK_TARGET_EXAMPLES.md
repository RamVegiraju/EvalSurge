# LangGraph and OpenAI Agents: local HTTP or Databricks Apps

These four `/v2/runs` requests use the same API, coordinator, fail-fast preflight,
and sole Locust engine. The framework is an implementation detail of your agent;
hosting and the public invocation protocol are separate choices. The operator
registers each target, and callers select only its `connection_id`.

| Agent | Registered alias / request file | Operator-selected public contract |
| --- | --- | --- |
| Local LangGraph | `local-langgraph` — [JSON](../examples/requests/local-langgraph.json) | `openai-chat`, `/langgraph/chat` in the repository demo |
| Local OpenAI Agents | `local-openai-agents` — [JSON](../examples/requests/local-openai-agents.json) | `openai-chat`, `/openai-agents/chat` in the repository demo |
| Databricks App LangGraph | `databricks-langgraph` — [JSON](../examples/requests/databricks-langgraph.json) | `databricks-agent-runtime`, `/api/invocations` |
| Databricks App OpenAI Agents | `databricks-openai-agents` — [JSON](../examples/requests/databricks-openai-agents.json) | `databricks-agent-runtime`, `/api/invocations` |

The local endpoints below are wrappers around the real frameworks, not the
LangGraph Platform API or an automatically discovered OpenAI API. Your own hosted
agent must expose one of EvalSurge's [supported wire contracts](TARGETS.md#supported-wire-contracts).
Using OpenAI Agents does not require an OpenAI-hosted model: its internal model
provider/API is independent of the App's public `/api/invocations` contract.

## Operator setup

From the checkout, install the framework/server dependencies:

```bash
uv sync --locked --extra agents --group dev --default-index https://pypi.org/simple
```

For the two local examples, start the existing demo in one terminal:

```bash
EVALSURGE_DEMO_LIVE=false MLFLOW_MODEL_CATALOG_URI='' \
  uv run --no-sync python -m examples.framework_agent
```

Both compiled LangGraph and OpenAI Agents Runner execute real tools and isolated
memory with MLflow instrumentation. Only model responses are deterministic fixtures;
this command makes no paid model calls. Stop another sample occupying port 9001
before starting it. Do not expose this synthetic demo publicly.

The complete four-target [operator TOML](../examples/requests/operator.toml) matches
the request files. For local-only use, its App placeholders can remain unchanged:
selecting a local alias does not resolve or invoke an App. In a second terminal:

```bash
BENCHMARK_CONFIG=examples/requests/operator.toml \
  uv run --no-sync uvicorn benchmark_agents.api:app \
  --host 127.0.0.1 --port 8000 --no-proxy-headers
```

For App use, copy this TOML into a protected, uncommitted operator file first
(for example under the ignored `artifacts/` directory). Replace each `app_name`
with your existing deployed App and `profile` with an explicitly selected OAuth
profile. Start the API with `BENCHMARK_CONFIG` pointing to that private file.
Restart after file changes; configuration is captured at application creation.
Registration does not deploy an App or provision a store. Never put real profile
names, credentials, or workspace destinations in the committed examples.

Current [Databricks Agent Server guidance](https://docs.databricks.com/aws/en/agents/deploy/agent-server)
(checked October 8, 2026) recommends DurableAgentServer, including LangGraph and
OpenAI Agents templates, with `/api/invocations`. Its required Lakebase Runtime
Store persists invocation execution; it does not itself enable transcript history
or long-term agent memory. Deployment and model/resource permissions are separate
operator work; see the [App validation runbook](DATABRICKS_APP_VALIDATION.md).

For an existing legacy MLflow AgentServer App, explicitly change that registration
to `protocols = ["mlflow-agent-server"]` for `/responses`. Do not change the public
benchmark request. EvalSurge does not negotiate protocols, fall back, poll a
background invocation, or retry target traffic. A native App must complete within
the synchronous foreground contract.

The API host runs Locust. `127.0.0.1:9001` is therefore the API/load-generator
machine, not a remote submitter's laptop. Containers need runner-reachable
addresses. App discovery uses the operator-owned Databricks SDK profile and obtains
the App URL server-side; OAuth refresh stays bound to that exact origin. Public
requests cannot contain URLs, protocols, workspace hosts, profiles, or OAuth tokens.
See [configuration/authentication boundaries](V2_API.md#operator-configuration).

## Four example requests

Every request below uses concurrency five, a 180-second dispatch ceiling, at most
500 measured requests, and a 60-second request timeout. The cap can finish a fast
run sooner than three minutes. Startup, preflight, and drain add time. These are
traffic limits, not a spend quota or proof of sustainable capacity.

### Local LangGraph

Save as [local-langgraph.json](../examples/requests/local-langgraph.json):

```json
{
  "name": "local-langgraph-baseline",
  "target": {"connection_id": "local-langgraph"},
  "cases": [{"input": {"query": "Can I refund an opened item?"}}],
  "load": {
    "concurrency": 5,
    "duration_seconds": 180,
    "max_requests": 500,
    "timeout_seconds": 60
  }
}
```

### Local OpenAI Agents

Save as [local-openai-agents.json](../examples/requests/local-openai-agents.json):

```json
{
  "name": "local-openai-agents-baseline",
  "target": {"connection_id": "local-openai-agents"},
  "cases": [{"input": {"query": "Can I refund an opened item?"}}],
  "load": {
    "concurrency": 5,
    "duration_seconds": 180,
    "max_requests": 500,
    "timeout_seconds": 60
  }
}
```

### Databricks App LangGraph

Requires the deployed App and a completed private operator registration. Save as
[databricks-langgraph.json](../examples/requests/databricks-langgraph.json):

```json
{
  "name": "databricks-langgraph-baseline",
  "target": {"connection_id": "databricks-langgraph"},
  "cases": [{"input": {"query": "Can I refund an opened item?"}}],
  "load": {
    "concurrency": 5,
    "duration_seconds": 180,
    "max_requests": 500,
    "timeout_seconds": 60
  }
}
```

### Databricks App OpenAI Agents

Requires the deployed App and a completed private operator registration. Save as
[databricks-openai-agents.json](../examples/requests/databricks-openai-agents.json):

```json
{
  "name": "databricks-openai-agents-baseline",
  "target": {"connection_id": "databricks-openai-agents"},
  "cases": [{"input": {"query": "Can I refund an opened item?"}}],
  "load": {
    "concurrency": 5,
    "duration_seconds": 180,
    "max_requests": 500,
    "timeout_seconds": 60
  }
}
```

Evaluation is omitted in all four, so it is **off**: no planner or judge calls.
Your real App can still incur model/tool/resource costs. Review its internal limits
and side effects, then explicitly authorize bounded live traffic before submitting
an App request. The local fixture demo needs no Databricks profile or model consent.

Fixed message adapters accept exactly one `query` or `messages` input field.
Nested messages are preserved, but extra top-level fields such as `custom_inputs`,
actor identity, per-case model routing, and resume state are rejected, not ignored.
Authoritative evaluation facts belong in `cases[].reference`, not in `input`.

## Submit with REST, CLI, or SDK

Choose one file, and run one benchmark at a time. For the loopback, unauthenticated
API above, a REST submission looks like:

```bash
curl --fail-with-body -sS http://127.0.0.1:8000/v2/capabilities
curl --fail-with-body -sS http://127.0.0.1:8000/v2/runs \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: local-langgraph-example-001' \
  --data-binary @examples/requests/local-langgraph.json
```

Use the corresponding filename for another example and a fresh idempotency key
for a new run. Reusing a key with the exact same body returns the original receipt;
changing its body causes a conflict. The `202` receipt contains the run ID and
status/result/report/cancel resource links. Poll `GET /v2/runs/{id}`, then fetch
`GET /v2/runs/{id}/result` or `/report` after terminal completion. The report shell
is `/reports/?run={id}`. Inspect failed/cancelled/interrupted outcomes too, not just
`completed` or `completed_with_gaps`.

The CLI consumes the same JSON without embedding service keys in commands:

```bash
uv run --no-sync evalsurge doctor --url http://127.0.0.1:8000
uv run --no-sync evalsurge run examples/requests/local-langgraph.json \
  --url http://127.0.0.1:8000 --wait --timeout 600 --open-report \
  --idempotency-key local-langgraph-example-002
```

Use `EVALSURGE_URL` and `EVALSURGE_API_KEY` for an authorized remote service;
configure server authentication and TLS first. `doctor`/capabilities are static
configuration checks: they do not invoke an agent or prove runtime health.

The lightweight remote Python SDK also accepts every request file:

```python
import json
import os
from pathlib import Path

from evalsurge import EvalSurge

request = json.loads(Path("examples/requests/local-langgraph.json").read_text())
with EvalSurge.remote(
    os.getenv("EVALSURGE_URL", "http://127.0.0.1:8000"),
    api_key=os.getenv("EVALSURGE_API_KEY"),
) as client:
    run = client.start(request, idempotency_key="local-langgraph-example-003")
    report = run.wait(timeout=600)
    print(run.id, report["run"]["status"], run.report_url)
```

`run.status()`, `run.result()`, and `run.report(offset=0, limit=25)` retrieve separate
bounded resources. `run.cancel()` requests cancellation; `cancellation_requested`
is an acknowledgment, not terminal cancellation. In-flight calls drain and their
side effects are not rolled back. A wait timeout or closing the client leaves
accepted work running. See [the remote API guide](V2_API.md).

## Fail-fast, evaluation, and test boundaries

Before measured traffic, EvalSurge validates setup and makes one excluded first-case
inference probe through the same Locust path. A failed probe stops measured load;
inspect the report's safe phase diagnostics. The probe can execute tools, warm
caches, mutate memory, or incur spend even when load never starts. It is not one
of the 500 measured requests, and there is no automatic target retry.

For quality checks, explicitly add `evaluation.mode = "explicit"` with scorer IDs,
or opt in to `"automatic"` planning. Supply your authoritative references for
correctness. The planner selects supported criteria, not your agent's model or
invented ground truth. Selected judges check the captured probe for excluded
readiness and score captured measured answers; they never reinvoke the agent.
See [the complete automatic request](V2_API.md#submit-and-retrieve-a-benchmark).

The local SSE contracts support answer-text TTFT; the native synchronous App JSON
contract has no TTFT/first-event or token-usage measurements. Endpoint-only access
cannot reveal internal model/tool/memory timings: authorized correlated agent-side
MLflow traces are required. Instrumenting the demo does not automatically authorize
the runner to collect those traces.

End-to-end regression evidence is recorded in [VALIDATION.md](../VALIDATION.md).
Controlled tests run real frameworks, REST/SDK, Locust, and native MLflow against
controlled provider boundaries. Both unchanged local JSON examples additionally
completed their 500-request cap at concurrency five with zero errors, one excluded
probe each, full timing/usage coverage and 200 profiled captures each (300 explicit
trace-budget gaps). Real tools and isolated memory executed, but provider responses
were synthetic: these results are integration evidence, not live-model performance.

App-boundary tests alone are not evidence of deployed App health. On October 8,
both frameworks were additionally deployed as native Apps with managed Runtime
Stores and verified source revisions. Both unchanged App JSON examples completed
500/500 successes with zero errors at five users against real GPT-OSS-120B. Each
also had a separate intentional failed probe proving zero measured traffic after
failed preflight. Exact revisions, run IDs, timing, boundaries and protected
resource records are recorded in [VALIDATION.md](../VALIDATION.md).

These live samples are stateless/tool-free and quality-off; they do not duplicate
the local demo's tool/memory/MLflow instrumentation. They establish native deployed
invocation and fail-fast compatibility, not App TTFT/token usage, internal traces,
live transcript/long-term memory, judging or production recovery. The earlier
October 7 OpenAI Agents App check remains historical evidence, not proof that
that App still exists. New live traffic always requires an exact selected profile,
target and consent. No single five-user smoke run establishes sustainable capacity
or judge calibration.
