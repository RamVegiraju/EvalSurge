# Configuration and usage

Start with the [README quickstart](../README.md). This guide covers hosted
connections, evaluation planning, API behavior, and bounded live examples.
The public Python import and distribution are `evalsurge`; existing
`benchmark_agents` modules remain supported. See [local Python usage](PYTHON_API.md)
for benchmarking without starting the REST server and the supported JSON contract.

## MLflow experiment links

Reports link to the agent's authorized trace experiments and the actual experiment
used for post-load evaluations. The stores can be different; the judge/model
workspace is never assumed to be the tracking workspace. Older reports without
recorded evaluation experiment IDs omit those links rather than guessing.

For a local SQLite store, configure the API's `.env`:

```dotenv
MLFLOW_TRACKING_URI=sqlite:///mlflow.db
BENCHMARK_MLFLOW_UI_URL=http://127.0.0.1:5000
```

Start the UI against the **same database**, from the same working directory:

```bash
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5000
```

For Databricks tracking, explicitly set the selected profile and its UI workspace:

```dotenv
MLFLOW_TRACKING_URI=databricks://YOUR_CONFIRMED_PROFILE
BENCHMARK_MLFLOW_UI_URL=https://YOUR-WORKSPACE.cloud.databricks.com
```

HTTP(S) tracking stores default to their tracking URL; set the UI override when
the browser UI has a different base or reverse-proxy prefix. The override only
applies when the current `MLFLOW_TRACKING_URI` matches the run's frozen store.
Remote UI destinations require HTTPS; plain HTTP is allowed only for loopback.
Credentials, query strings, fragments, and unsafe URLs are omitted. Clicking a
link opens a new tab without forwarding the API key or referrer. MLflow's own
permissions still apply, and links do not imply that an experiment is reachable
or public. Link creation performs no MLflow lookup or model call.

## Where to run EvalSurge

Today, the FastAPI process starts Locust as a subprocess **on the API host**. A
caller that submits a run from another machine does not move the load generator:
the API host sends target requests, stores the journal and reports, and collects
traces for profiling. Run one API owner with persistent local POSIX storage, as
described under [measurement and recovery](#measurement-limits-and-recovery).

With `EvalSurge.local()` or `EvalSurge.local_async()`, no API server is involved:
the Python caller's machine runs Locust and owns the artifacts. The placement
and resource guidance below applies to whichever machine generates the load.

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
supported protocol. App-native OAuth refresh is not yet implemented.
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

Benchmark quality scores captured answers **after load**, without calling the target
again. Before load, each selected criterion must complete one excluded readiness
assessment of the inference probe. Sampling balances randomized case/time strata with a frozen seed and
per-scorer budget. Read `eligible`, `attempted`, `scored`, `judge_errors`, selected
request IDs, and coverage together. Completion is not a quality verdict.

Expand **Failed assessment details** in the report to see each failed boolean
verdict's judge rationale and request/case ID. Python and REST expose the same
entries at `run.evaluation["results"][...]["assessments"]`. Judge execution errors
show safe codes and next steps instead; no explanation is invented when missing.
Rationales are bounded protected content and may quote private inputs or answers.

Relevance and safety need outputs; correctness also needs authoritative
`expected_response` or `expected_facts`. The direct catalog groundedness wrapper
is not implemented and remains `needs_data`. Brought trace-aware MLflow judges
can be operator-allowlisted; missing evidence never becomes a passing assessment.
See [judges and dataset integration](PROFILING_AND_EVALUATION.md).

## Fail-fast readiness checks

Before any agent invocation, the service validates the frozen evaluation setup:
all selected criteria must be ready, catalog judges need a configured provider,
and the first sample needs references required by correctness or a brought scorer.
A selected `needs_data` criterion blocks load; remove it or supply its evidence.
Use `scorers: []` and `registered_scorers: []` for performance only.

Every new run checks the first workload sample once, at concurrency one, before
measured load. The same target/model, adapter, usage setting, operator-owned
credentials, and `load.timeout_seconds` apply. HTTP 200 alone is insufficient:
the supported SSE response must finish normally with nonempty answer text, or
`http-json` must return a complete valid nonempty answer object. Redirects,
provider error events, malformed/empty/truncated responses, and deadlines fail.

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

This check is **one extra agent invocation** beyond `load.max_requests`, can execute
tools/mutate memory/warm caches, and can incur provider cost. It has no retries
or automatic provider/model adjustment. Captures stay in protected
`preflights/{run_id}/` artifacts and are excluded from measured counts, timings,
profiles, quality sampling, and benchmark scores. Planning still occurs before preflight.

If judging is selected, the service reuses that answer for **one readiness
assessment per criterion** before spawning measured load. A false/zero verdict is
valid; an execution failure or missing assessment is not. Catalog readiness uses
the frozen timeout/token cap, zero SDK retries, and no additional MLflow rate-limit
retries. Brought scorers retain their operator-owned transport/retry behavior.
Trace-required scorers also need a verified, correctly correlated probe trace.

Judge failure returns `status: "failed"`, `load_status: "skipped"`, and
`evaluation_preflight.error` with `code`, `message`, `guidance`, and the failed
`scorer`. Errors distinguish authentication, rate limits, connection/timeouts,
invalid verdicts, missing evidence, and evaluation-backend failures without exposing
provider text. A worker launch/exit/deadline failure instead exposes `load_error`.
The report shows both. Passing readiness does not guarantee later provider
availability, valid answers for every case, or quality under load.

Post-load evaluation stops starting further criteria after an execution failure.
Native MLflow may already have dispatched multiple assessments within the current
criterion; those are not retractable. Measured latency/throughput remains readable
if later evaluation fails; inspect `evaluation.error` or per-criterion errors and
the `completed_with_gaps` outcome instead of treating completion as success.

Cancellation during preflight stops further dispatch and drains the active check;
load does not start. Restart cancels abandoned workers and marks the run interrupted
without replaying agent actions. See [ADR 0006](adr/0006-evaluation-readiness.md).

## Framework agent benchmarks

The agent-oriented [LangGraph](../examples/langgraph_benchmark.py) and
[OpenAI Agents](../examples/openai_agents_benchmark.py) samples use the public
Python facade, not REST polling. They call the existing instrumented
`examples/framework_agent.py` endpoints at `/langgraph/chat` and
`/openai-agents/chat`, respectively.

Each combines two-user load, a ten-second dispatch window, at most ten measured
requests, and explicit relevance/correctness judges with authoritative references.
Post-load scoring is capped at five answers per judge. Configuration and the
excluded inference/judge-readiness checks must pass before measured load starts.

Follow the [framework example guide](../examples/README.md#framework-agent-benchmarks)
to start the agent server and configure the benchmark process's judge/tracking
environment, then run one sample at a time:

```bash
uv run --no-sync python -m examples.langgraph_benchmark
uv run --no-sync python -m examples.openai_agents_benchmark
```

The server defaults to fixture model responses, but configured judge calls can
incur costs. Internal heatmaps additionally require authorized trace collection.
Local tests exercise real framework/Locust/MLflow APIs with controlled provider
boundaries; this is not a paid/live validation claim. For the credential-free,
performance-only mock quickstart, use
[python_benchmark.py](../examples/python_benchmark.py).

## Python requests client

With the API and authorized agent running:

```bash
uv run --no-sync python -m scripts.validation.python_requests_benchmark \
  --api-url http://127.0.0.1:8000 \
  --target-url http://127.0.0.1:9001/chat \
  --concurrency 5 --duration 300 --max-requests 5000 --wait-timeout 600
```

This advanced [REST helper](../scripts/validation/python_requests_benchmark.py) uses a normal
`requests.Session`: one `POST /v1/runs`, status polling, and a printed report URL.
For local benchmarking without REST or polling, start with the
[minimal Python examples](../examples/README.md).
For report JSON, use `GET /v1/runs/{run_id}/report`. The client
disables ambient credentials/proxies, redirects, and retries, and uses one
idempotency key. Set `BENCHMARK_API_KEY` if the API requires it.
The default is performance-only; the sample mock does not call an LLM.

For real evaluation, save a full run request with your reviewed target/model,
cases/references, load settings, and scorer or `plan_id` selection, then use
`--request-file request.json` instead of `--target-url`. Credentials and trace
destinations remain server-owned. The request file is sent without load overrides.
Submission can perform planning before 202; set `--http-read-timeout` accordingly.

The client prints the terminal status and safe failure guidance. Failed/cancelled/
interrupted runs exit nonzero; `completed_with_gaps` returns a report with a warning,
not a passing evaluation. A client timeout or Ctrl-C stops waiting, not the server.
Do not blindly resubmit an uncertain POST: reconcile its printed idempotency key
with server history. A new CLI invocation uses a new key and can duplicate actions.

The submitted body looks like this; `samples` is the actual workload, not a health check:

```python
body = {
    "target": {"url": "http://127.0.0.1:9001/chat"},
    "evaluation": {
        "description": "Performance-only benchmark; no quality judging requested.",
        "scorers": [],
        "registered_scorers": [],
        "samples": [{"inputs": {"query": "Reply with a short greeting."}}],
    },
    "load": {"concurrency": 5, "duration_seconds": 300, "max_requests": 5000},
}
```

Send it as `session.post(api_url + "/v1/runs", json=body, ...)`, including one
`Idempotency-Key` and appropriate network timeouts, as in the tested example.

## How long does a run take?

`duration_seconds` limits **new load dispatch**, not time until the final report:

```text
total ≈ planning + setup checks + worker startup + one agent probe
      + judge readiness + load window + active-request drain
      + trace collection + sampled quality evaluation
```

- Dispatch stops at duration **or** `max_requests`, whichever comes first. With
  five users and a 300-second window, the test can issue thousands of requests:
  concurrency is simultaneous users, not total calls. At steady state with no
  think time, approximate calls are `concurrency × duration / mean request latency`.
  This estimate excludes startup, ramp-up, auth/journal overhead, and the request cap.
- A five-minute performance-only run usually needs the five-minute window plus
  two worker startups, one probe, and drain. A fast mock may hit its cap much
  sooner. It is not a promised completion SLA.
- Each selected judge adds one readiness assessment, then at most
  `max_scored_requests` measured answers **per scorer**. More criteria/answers,
  slow models, provider rate limits/retries, tracking writes, and trace-export lag
  can add seconds or minutes. Scoring begins after load; it is not included in
  request latency. Readiness assessments are extra and excluded from quality scores.
- `load.timeout_seconds` is the per-target-request deadline. Locust's parent
  watchdog allows the dispatch duration plus that timeout plus 45 seconds of
  startup/cleanup grace, then up to five seconds for termination before kill.
  There is no hard overall report deadline.
- `--wait-timeout` or Python `run.wait(timeout=...)` bounds caller waiting only.
  HTTP connect/read timeouts are separate inactivity limits, not job deadlines
  or hard wall-clock limits on a peer that continuously sends bytes.
- Catalog `judge_timeout_seconds` configures SDK transport timeouts, not a hard
  whole-phase deadline. Readiness has zero catalog SDK retries; post-load scoring
  uses the frozen retry cap. Authentication, native MLflow setup/tracking writes,
  and retry backoff can add time beyond one model request.

Native scorer code runs in a thread, not a hard execution sandbox. Registered
scorer transports/retries are operator-owned. Trace collection's 60-second
fetch-admission budget does not interrupt an already-stalled remote call. Configure
transport limits and use the phase statuses to locate delay; hard phase isolation
remains a [shared-hosting gate](PRODUCTION_READINESS.md).

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
uv run --no-sync python -m scripts.validation.framework_e2e \
  --live --profile YOUR_CONFIRMED_PROFILE --model YOUR_VERIFIED_ENDPOINT
```

This sends one preflight plus two measured target requests per framework at
concurrency two, one planner call per framework, and at most one captured measured
answer plus one readiness assessment per selected catalog scorer.
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

The smaller `uv run --no-sync python -m scripts.validation.locust_databricks_e2e` loads `.env` and
uses one planner call, one preflight plus four measured target calls, and up to four
quality assessments plus one readiness assessment per selected scorer, with bounded
catalog judge retries. Both examples require explicit workspace
configuration and authorization for the target traffic.

For contributing checks and recorded results, see
[CONTRIBUTING.md](../CONTRIBUTING.md) and [VALIDATION.md](../VALIDATION.md).
