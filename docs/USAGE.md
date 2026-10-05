# Configuration and usage

Start with the [README quickstart](../README.md). This guide covers hosted
connections, evaluation planning, API behavior, and bounded live examples.
The Python import package is `benchmark_agents`; the distribution is `evalsurge`.

## Where to run EvalSurge

Today, the FastAPI process starts Locust as a subprocess **on the API host**. A
caller that submits a run from another machine does not move the load generator:
the API host sends target requests, stores the journal and reports, and collects
traces for profiling. Run one API owner with persistent local POSIX storage, as
described under [measurement and recovery](#measurement-limits-and-recovery).

| Goal | Runner placement | What the result means |
| --- | --- | --- |
| Integration check or small comparison | Your workstation | Confirms the connection, protocol, report, and judges; workstation and internet variability can dominate. |
| Repeatable service load | A dedicated VM or container with stable CPU, memory, disk, and egress, separate from the agent | Measures the target from that runner's network path. Keep placement and resources fixed across comparisons. |
| User-perceived latency by geography | Separate runners in the client regions of interest | Includes each region's network path; do not compare it as if it were server-only latency. |

A short-lived CI job can run smoke checks if it exports protected artifacts before
its filesystem is discarded. Its changing machine and network make it a poor
baseline for capacity comparisons.
If the API is reachable beyond loopback, follow the [security boundary](../SECURITY.md)
for authentication and TLS; this single-tenant release is not a shared service.

For a Databricks App target, run EvalSurge outside the **agent App's compute** on
a dedicated host that can reach the App URL and use an operator-owned authorized
connection. A runner in the same cloud region is useful for service-side load
comparisons; a runner in the user's region is useful for end-user latency. The
current `databricks` connection accepts workspace-host URLs only; an App URL
currently needs an exact URL-bound bearer connection, a valid token, and a
supported streaming protocol. App-native OAuth refresh is not yet implemented.
The local alpha does not provide a managed distributed runner or a one-click
Databricks Job deployment. If using short-lived job compute, arrange the API
lifecycle, credentials, reachable target, and persistent POSIX artifacts yourself.

The runner has its own ceiling: CPU, memory, open sockets/file descriptors,
network bandwidth and egress quotas, authentication, and journal disk I/O can
limit dispatch or raise latency. The target, its model/tool dependencies, and
the network path can limit it too. Client latency is measured from this runner
after authentication at HTTP dispatch; it is not browser latency. Run throughput
includes ramp-up, authentication, journaling, and drain. This release does not
measure runner resource saturation or distinguish a runner ceiling from a target
ceiling. Record runner size/region, target region, network path, workload, and
concurrency with results; monitor runner CPU, memory, sockets, egress, and disk
I/O separately. If those saturate, increase runner resources and repeat before
making a target-capacity claim. One closed-loop load level is descriptive, not a
maximum sustainable throughput measurement.

## Connections and authentication

Target credentials belong to server-owned connections, not benchmark request
bodies. Configure `.env` from [`.env.example`](../.env.example) and start the API
with the file explicitly:

```bash
uv run uvicorn benchmark_agents.api:app --env-file .env \
  --host 127.0.0.1 --port 8000 --no-proxy-headers
```

A Databricks connection uses an explicitly selected SDK/CLI profile:

```dotenv
DATABRICKS_CONFIG_PROFILE=YOUR_CONFIRMED_PROFILE
BENCHMARK_CONNECTIONS='{"workspace":{"url":"https://YOUR-WORKSPACE.cloud.databricks.com/serving-endpoints/chat/completions","auth":"databricks"}}'
BENCHMARK_PLANNER_MODEL=databricks-gpt-5-4-mini
BENCHMARK_JUDGE_MODEL=databricks-gpt-5-4-mini
MLFLOW_TRACKING_URI=sqlite:///mlflow.db
```

Supply `target.connection_id: "workspace"` and the exact configured URL. Verify
model availability in your workspace; endpoint names do not pin model revisions.
Do not commit `.env`, credentials, profiles, or live artifacts.

Bearer connections use operator configuration such as:

```json
{
  "agent": {
    "url": "https://agent.example/chat",
    "auth": "bearer",
    "token_env": "AGENT_TOKEN"
  }
}
```

Set `BENCHMARK_CONNECTIONS` to this JSON and keep `AGENT_TOKEN` on the server.
Remote connections require HTTPS. Unauthenticated remote URLs require an exact
entry in `BENCHMARK_ALLOWED_TARGETS` (JSON array); loopback is allowed for testing.
Redirects and ambient proxy/netrc credentials are disabled in the load worker.

For inbound authentication, set `BENCHMARK_API_KEY` and send `X-API-Key` on every
API call. Documentation and the data-free report shell are public metadata;
report JSON remains authenticated. Keys entered in the UI are not persisted.
See [security and deployment boundaries](../SECURITY.md) before remote access.

## Planning and evaluation

Omit `evaluation.scorers` for LLM suggestions, set an explicit catalog list to
bypass planning, or use `[]` for no catalog judging. Configure planner/judge
providers on the server; see the [support matrix](MODEL_COMPATIBILITY.md).
Registered MLflow aliases are independently selectable.

`POST /v1/evaluation-plans` accepts an objective and optional samples/manifest.
Description-only planning may identify useful criteria and missing evidence,
but load generation requires at least one sample. Inspect each recommendation's
rationale, readiness, and required fields; LLM suggestions are not calibrated
criteria or proof of runtime capabilities.

Submit a reviewed `plan_id` to reuse its frozen policy. Its description, manifest,
samples, scorers, and budgets must match exactly; target/load settings may change.
Old plan formats may need recreation. Plans bind trace scope, rubric/data hashes,
registered scorer versions, sampling settings, and judge budgets.

Evaluation scores captured answers **after load**, without calling the target
again. Sampling balances randomized case/time strata with a frozen seed and
per-scorer budget. Read `eligible`, `attempted`, `scored`, `judge_errors`, selected
request IDs, and coverage together. Completion is not a quality verdict.

Relevance and safety need outputs; correctness also needs authoritative
`expected_response` or `expected_facts`. The direct catalog groundedness wrapper
is not implemented and remains `needs_data`. Brought trace-aware MLflow judges
can be operator-allowlisted; missing evidence never becomes a passing assessment.
See [judges and dataset integration](PROFILING_AND_EVALUATION.md).

## Fail-fast inference check

Every new run checks the first workload sample once, at concurrency one, before
measured load. The same target/model, adapter, usage setting, operator-owned
credentials, and `load.timeout_seconds` apply. HTTP 200 alone is insufficient:
the SSE response must finish normally with nonempty answer text. Redirects,
provider error events, malformed/empty/truncated streams, and deadlines fail.

Submission still returns 202; poll `GET /v1/runs/{run_id}`. A failed check returns
`status: "failed"`, skipped load/profiling/evaluation, and diagnostics such as:

```json
{
  "status": "failed",
  "load_status": "skipped",
  "preflight": {
    "status": "failed",
    "request_id": "probe-correlation-id",
    "http_status": 401,
    "error": {
      "code": "target_http_error",
      "message": "Inference preflight failed. Load test did not start. Check target access and endpoint configuration."
    }
  }
}
```

The report displays the same safe error; probe prompts/responses/provider bodies
are not error details. Use the probe `request_id` to inspect your agent's logs or
correlated trace. Fix the target or server-owned connection and submit with
a new idempotency key. Replaying the original key does not repeat inference.
Old saved runs show `preflight.status: "not_run"`, not a retroactive success.

This check is **one extra invocation** beyond `load.max_requests`, can execute
tools/mutate memory/warm caches, and can incur provider cost. It has no retries
or automatic provider/model adjustment. Captures stay in protected
`preflights/{run_id}/` artifacts and are excluded from measured counts, timings,
profiles, sampling, and judging. Passing proves only that this one request worked,
not agent quality or capacity. Planning still occurs before preflight.

Cancellation during preflight stops further dispatch and drains the active check;
load does not start. Restart cancels abandoned workers and marks the run interrupted
without replaying agent actions. See [ADR 0004](adr/0004-fail-fast-inference-preflight.md).

## Setup inspection and traces

For an opt-in draft manifest:

```bash
uv run python -m scripts.scan_agent path/to/agent.py \
  --framework openai-agents --name "My agent"
```

The bounded AST scanner never imports/executes agent code or exports raw source,
constants, or docstrings. Review and enrich its names/capabilities before sharing.
Dynamic setup is not detected, and there is no arbitrary remote source crawler.

For profiling, configure `BENCHMARK_TRACE_ENABLED=true`, `MLFLOW_TRACKING_URI`,
and `BENCHMARK_TRACE_EXPERIMENT_IDS` (JSON array). An explicitly configured
`MLFLOW_EXPERIMENT_ID` can supply the scope. Targets must return their trace ID
and record exact run/request correlation metadata. Full instrumentation and
registered-scorer contracts are in [the integration guide](PROFILING_AND_EVALUATION.md).

## API operations

| Operation | Purpose |
| --- | --- |
| `POST /v1/evaluation-plans` | Create a frozen plan; 201 + Location |
| `GET /v1/evaluation-plans/{plan_id}` | Inspect a plan |
| `POST /v1/runs` | Start a run; 202 + Location + Retry-After |
| `GET /v1/runs?offset=0&limit=50` | Compact persisted history |
| `GET /v1/runs/{run_id}` | Phase statuses, metrics, and evaluation |
| `GET /v1/runs/{run_id}/requests?offset=0&limit=50` | Captured responses |
| `GET /v1/runs/{run_id}/report?offset=0&limit=25` | Performance, quality, and trace profiles |
| `POST /v1/runs/{run_id}/cancel` | Stop preflight/load dispatch and drain active requests |

Request/report pages are bounded to 100 records. Planning/submission can wait for
the provider; choose a suitable client timeout. A reviewed `plan_id` avoids
planning during submission.

Run-submission `Idempotency-Key` records persist locally. Same key/different input
returns 409. Active planning/runs return 429 + Retry-After. Bodies, including
chunked bodies, are limited to 8 MB (413). Safe error envelopes omit submitted
values and retain correlation/no-store headers. History reads compact metadata.

Browse the self-hosted `/docs/` or [OpenAPI schema](openapi.json). `/redoc` redirects
to the same supported UI. The experimental 0.2 API breaks the original 0.1
contract; see [migration notes](API_REVIEW.md).

## Measurement limits and recovery

One closed-loop load level uses sequential users, zero think time, round-robin
cases, duration/request caps, and bounded drain. Throughput includes ramp-up,
authentication, journaling, and drain; preflight, process startup, planning, and evaluation
are outside the measurement window.

Request latency and answer-text TTFT start after authentication at HTTP dispatch.
TTFT excludes metadata, tools, and hidden reasoning, and does not measure browser
paint. Percentiles describe successful requests only; errors retain their own
denominators. Token throughput includes provider-usage coverage.

Trace self time subtracts the union of child intervals. Wall occupancy handles
overlap without summing inclusive spans into wall time. Parallel occupancy can
include duplicate instrumentation; client-minus-agent time is unattributed.
Endpoint-only reports cannot invent internal timing or causal bottlenecks.
Short smoke tests establish wiring, not capacity or judge calibration.

Flushed journals, atomic snapshots, and partial recovery retain local evidence.
Restarts mark abandoned work interrupted; they do not resume a durable queue.
Use one API owner and persistent local POSIX storage. Protect captured prompts,
responses, and references with permissions and retention. Local disk loss is
outside the recovery guarantee. See [architecture](../ARCHITECTURE.md) and
[shared-hosting release gates](PRODUCTION_READINESS.md).

## Bounded live validation

Live examples are **paid**, opt-in, and require your explicitly selected
Databricks profile and verified endpoint:

```bash
uv run python -m examples.framework_e2e \
  --live --profile YOUR_CONFIRMED_PROFILE --model YOUR_VERIFIED_ENDPOINT
```

This sends one preflight plus two measured target requests per framework at
concurrency two, one planner call per framework, and at most one captured measured
answer per selected catalog scorer.
Use `--framework langgraph` or `--framework openai-agents` for one integration.
Tools/references are synthetic; traces/reports stay local.

`--model` selects the target and defaults both planner and judge to that endpoint.
Use `--planner-model` and `--judge-model` to choose different, compatible models
explicitly before the run. For example, a Claude target can use a verified
JSON-object-capable GPT endpoint for planning/judging. No provider error triggers
an automatic model change.

For demo models that reject the streamed-usage extension, set
`EVALSURGE_DEMO_REQUEST_USAGE=false` before running the helper. This is separate
from the hosted-target adapter's `target.request_usage` setting. Missing provider
usage stays unknown; tracing and quality evaluation still run.

Demo target calls have no provider retries and a 1,024-completion-token bound;
planner/judge retries have separate limits. Compatibility presets are exact
provider/model matches, not universal model settings. Review
[model compatibility](MODEL_COMPATIBILITY.md) before changing them.

The smaller `uv run python examples/locust_databricks_e2e.py` loads `.env` and
uses one planner call, one preflight plus four measured target calls, and up to four assessments per selected
scorer, with bounded judge retries. Both examples require explicit workspace
configuration and authorization for the target traffic.

For contributing checks and recorded results, see
[CONTRIBUTING.md](../CONTRIBUTING.md) and [VALIDATION.md](../VALIDATION.md).
