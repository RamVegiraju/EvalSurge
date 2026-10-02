# EvalSurge

A local-first Python REST API for benchmarking hosted agents with Locust, then evaluating the captured answers with MLflow. **Alpha, single tenant, one active run per process, Linux/macOS.**

Give it a streaming endpoint, an objective, workload samples, and target concurrency. EvalSurge freezes an evaluation plan, exercises the endpoint, and scores a representative sample of the captured responses. Description-only requests can recommend scorers and identify missing evidence; load generation requires at least one sample.

## Start locally

```bash
uv sync --locked --group dev
uv run uvicorn benchmark_agents.api:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Interactive API documentation is at `http://127.0.0.1:8000/docs`. The import package is currently `benchmark_agents`; the distribution and project are named EvalSurge.

Try a complete local mock run without LLM credentials:

```bash
uv run python examples/smoke_test.py
```

For a separate mock endpoint, run `uv run uvicorn examples.mock_agent:app --port 9001`. Then:

```bash
curl http://127.0.0.1:8000/v1/runs \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: first-local-run' \
  -d '{
    "target": {"url": "http://127.0.0.1:9001/chat"},
    "evaluation": {
      "description": "Answer refund questions accurately",
      "scorers": [],
      "samples": [{"inputs": {"query": "Can I refund an opened item?"}}]
    },
    "load": {"concurrency": 3, "max_requests": 20}
  }'
```

`scorers: []` explicitly requests performance only. Omit `scorers` to use the LLM planner; supply names to bypass it. Poll the `Location` header returned with HTTP 202. A run is terminal at `completed`, `completed_with_gaps`, `failed`, `interrupted`, or `cancelled`. Always inspect `load_status`, `evaluation_status`, request error rate, and quality coverage; a completed phase is not a quality pass.

## Databricks inference and judging

Use Databricks SDK authentication. Copy `.env.example` to `.env` and configure your CLI profile. The live example loads it; for the server, use `uv run uvicorn benchmark_agents.api:app --env-file .env --no-proxy-headers`.

Both planning and judging default to `databricks-gpt-5-4-mini` in an explicitly configured workspace. Model availability, prices, and endpoint revisions are workspace/provider concerns; no pricing guarantee or model calibration is implied. Override `BENCHMARK_PLANNER_MODEL` and `BENCHMARK_JUDGE_MODEL` on the server.

Target credentials belong to **server-owned connections**. A request supplies `connection_id`, never an environment variable containing a credential. Example server configuration:

```dotenv
DATABRICKS_CONFIG_PROFILE=YOUR_PROFILE
BENCHMARK_CONNECTIONS='{"workspace":{"url":"https://YOUR-WORKSPACE.cloud.databricks.com/serving-endpoints/chat/completions","auth":"databricks"}}'
BENCHMARK_PLANNER_MODEL=databricks-gpt-5-4-mini
BENCHMARK_JUDGE_MODEL=databricks-gpt-5-4-mini
MLFLOW_TRACKING_URI=sqlite:///mlflow.db
```

The request's target URL must exactly match its connection. For bearer authentication, the operator can configure `{"url":"https://agent.example/chat","auth":"bearer","token_env":"AGENT_TOKEN"}`. Remote connections require HTTPS. Unauthenticated remote URLs require an exact entry in `BENCHMARK_ALLOWED_TARGETS` (JSON array). Loopback URLs are allowed for local testing. Redirects and ambient netrc/proxy credentials are disabled in the Locust worker.

Run the small live validation in your configured workspace (one planner call, four target calls, up to four assessments per selected scorer, with bounded judge retries):

```bash
uv run python examples/locust_databricks_e2e.py
```

No LiteLLM or `databricks-openai` dependency is used. Judging uses native MLflow `@scorer` wrappers around shipped MLflow rubrics and direct OpenAI-compatible Databricks calls authenticated by the SDK. These are not MLflow managed judges. Internal prompt imports are isolated, MLflow is constrained to 3.16.x, and source hashes detect rubric changes.

## API

| Operation | Purpose |
| --- | --- |
| `POST /v1/evaluation-plans` | Create a persisted plan from a description and optional samples; returns 201 + Location |
| `GET /v1/evaluation-plans/{plan_id}` | Inspect the frozen plan |
| `POST /v1/runs` | Validate, freeze a plan, then start load; returns 202 + Location + Retry-After |
| `GET /v1/runs?offset=0&limit=50&status=completed` | Compact persisted run history |
| `GET /v1/runs/{run_id}` | Status, metrics, quality results, and plan |
| `GET /v1/runs/{run_id}/requests?offset=0&limit=50` | Captured response records; maximum page size 100 |
| `POST /v1/runs/{run_id}/cancel` | Stop new requests and drain active load |

Plan creation and run submission can wait for the planner before responding; use a client timeout suited to the provider. A previously inspected `plan_id` avoids planning on submission. Its evaluation description, samples, scorers, and budget must match exactly. Changing only the target or load settings allows reuse.

`Idempotency-Key` applies to run submission and persists with local artifacts. Reusing the key with different input returns 409. A concurrent run returns 429 + Retry-After. Validation errors use a consistent envelope and do not echo submitted values. All responses carry `X-Request-ID` and `Cache-Control: no-store`.

JSON uses snake_case consistently with Python. The published OpenAPI schema is in [docs/openapi.json](docs/openapi.json). Version 0.2 breaks the unpublished 0.1 template; see [the migration notes](docs/API_REVIEW.md).

## Measurements and evaluation

- One closed-loop concurrency level, zero think time, round-robin workload cases. Duration and request count both cap dispatch; in-flight work drains under a deadline. This measures performance, **not maximum sustainable capacity**.
- TPS uses elapsed time from Locust test start through drain, including ramp-up, auth, and journal overhead; subprocess bootstrap and post-run judging are excluded. Reported peak in flight measures HTTP calls, not merely configured users.
- `ttft_ms` measures HTTP dispatch to the first nonempty answer-text delta received by the client. Metadata, tool calls, and hidden reasoning do not count. This approximates first visible answer availability; browser buffering/rendering is outside the measurement. Authentication time is separate.
- Percentiles describe successful requests only; failed requests remain in raw records and error-rate denominators. Interrupted attempts are excluded from completed TPS. Token throughput uses provider-reported counts and includes a coverage fraction.
- Evaluation runs after load on captured answers. It does not reinvoke the target. Sampling shuffles case × four elapsed-time bins using a fixed seed, then balances across strata. Coverage and selected request IDs are retained per scorer. Means describe that balanced sample, not a population-weighted estimate.
- Relevance and safety need outputs; correctness also needs authoritative `expected_response` or `expected_facts`. Groundedness returns `needs_data` until retrieval trace ingestion exists. Missing evidence never receives a passing score.
- Plans record judge model/workspace/profile, rubric version/hash, dataset and evaluation hashes, seed, policy, and budgets. A hosted endpoint can still change its underlying model; use versioned endpoints for stronger reproducibility.

Framework labels are limited to LangGraph and OpenAI Agents. Actual interoperability is through `openai-chat` and `mlflow-agent-server` streaming wire adapters. There is no automatic instrumentation of an arbitrary remote agent, no internal span latency map yet, and no claim that every framework deployment exposes these contracts.

## Reliability and scope

Every attempt gets a flushed start record and completion record in `artifacts/<run-id>/requests.jsonl`. Worker exits retain completed responses and mark unfinished attempts `WorkerInterrupted`. Phase snapshots and reusable plans survive process restarts. This is local-disk recovery, not a durable queue or automatic job resumption. Filesystem loss and shared/network storage are outside the durability guarantee. Flushes add load-generator overhead; monitor the generator before interpreting high-throughput results.

Use one Uvicorn process and persistent local storage. A filesystem lock rejects competing API processes. After a hard parent crash, restart recovery requests an old worker to stop; its bounded requests may still drain. Do not use this alpha as a multi-user hosted service. Shared deployment needs connection ACLs, egress enforcement, durable worker leases, distributed storage, quota enforcement, and stronger isolation. See [SECURITY.md](SECURITY.md).

## Development

```bash
uv sync --locked --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv build
```

Tests run the production Locust subprocess against localhost, including cancellation, authentication failure, truncation, timeout, and killed-worker recovery. They do not call paid models. Live validation is explicit and separate. See [VALIDATION.md](VALIDATION.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [CONTRIBUTING.md](CONTRIBUTING.md).
