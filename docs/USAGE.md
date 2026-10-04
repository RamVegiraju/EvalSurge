# Configuration and usage

Start with the [README quickstart](../README.md). This guide covers hosted
connections, evaluation planning, API behavior, and bounded live examples.
The Python import package is `benchmark_agents`; the distribution is `evalsurge`.

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
| `POST /v1/runs/{run_id}/cancel` | Stop new load dispatch and drain active requests |

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
authentication, journaling, and drain; process startup, planning, and evaluation
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

This sends two target requests per framework at concurrency two, one planner call
per framework, and at most one captured answer per selected catalog scorer.
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
uses one planner call, four target calls, and up to four assessments per selected
scorer, with bounded judge retries. Both examples require explicit workspace
configuration and authorization for the target traffic.

For contributing checks and recorded results, see
[CONTRIBUTING.md](../CONTRIBUTING.md) and [VALIDATION.md](../VALIDATION.md).
