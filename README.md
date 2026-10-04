# EvalSurge

A local-first Python REST API for benchmarking hosted agents.

- **Performance:** latency, time to first answer token, throughput, and errors.
- **Evaluation:** suggested judges, brought MLflow judges, and per-criterion results.
- **Profiling:** request heatmaps and tool/model/memory waterfalls from correlated MLflow traces.

**Local alpha:** Linux/macOS, single tenant, one active run. Not a shared production
service, and a single load level does not establish sustainable capacity.

## Quickstart

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and `jq` for the sample
request. No model credentials or paid calls are needed.

### 1. Install and start the API

```bash
git clone https://github.com/RamVegiraju/EvalSurge.git
cd EvalSurge
uv sync --locked --extra agents --group dev
uv run uvicorn benchmark_agents.api:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

API docs: `http://127.0.0.1:8000/docs/`. Keep one API worker.
The lockfile currently uses a package mirror; see [dependency setup limitations](docs/DEPENDENCIES.md#index-limitation--october-4-2026) if it is unavailable.

### 2. Start the sample agent

In a second terminal, from the repository:

```bash
uv run uvicorn examples.mock_agent:app --host 127.0.0.1 --port 9001 --no-proxy-headers
```

### 3. Send a benchmark request

In a third terminal:

```bash
RUN_ID=$(curl --fail-with-body -sS http://127.0.0.1:8000/v1/runs \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: first-local-run' \
  -d '{
    "target": {"url": "http://127.0.0.1:9001/chat"},
    "evaluation": {
      "description": "Answer refund questions accurately",
      "scorers": [],
      "samples": [{"inputs": {"query": "Can I refund an opened item?"}}]
    },
    "load": {"concurrency": 3, "max_requests": 20, "duration_seconds": 10}
  }' | jq -er '.id')
echo "$RUN_ID"
```

The API returns **202 Accepted**. `scorers: []` disables planning and judging.
Use a new idempotency key for a new run; the same key and body replay the original.

### 4. View the result

Poll until `completed` or `completed_with_gaps`:

```bash
curl --fail-with-body -sS "http://127.0.0.1:8000/v1/runs/$RUN_ID" \
  | jq '{status, load_status, profiling_status, evaluation_status, metrics}'
```

`failed`, `cancelled`, and `interrupted` are also terminal; inspect their phase
statuses. Open `http://127.0.0.1:8000/reports/?run=YOUR_RUN_ID` with the returned ID.
For JSON, use `GET /v1/runs/{run_id}/report`.

The mock has no internal traces. To try real **LangGraph and OpenAI Agents**
with tools, memory, and tracing, stop the mock and run:

```bash
uv run python -m examples.framework_e2e --serve
```

This prints report URLs on port 9002. Model responses are fixtures, judging is
disabled, and no paid calls are made. Stop with Ctrl-C.

## Benchmark your agent

Replace `target.url` with your authorized streaming endpoint and supply workload
samples. Set `target.model` if required by its protocol.

- **Suggested judges:** configure a planner, omit `evaluation.scorers`, and review
  `POST /v1/evaluation-plans` before submitting its `plan_id`.
- **Your judges and data:** supply samples/references and select operator-allowlisted
  MLflow aliases through `evaluation.registered_scorers`.
- **Internal profiling:** correlate agent-side MLflow traces; an endpoint alone
  cannot reveal tool or memory timing.

The report separates judge rationale/readiness from scored outcomes, coverage,
and errors. Missing evidence never counts as a pass. Catalog judging currently
requires Databricks; see [provider compatibility](docs/MODEL_COMPATIBILITY.md).

Remote/authenticated agents require [server-owned connections](docs/USAGE.md#connections-and-authentication).
If `BENCHMARK_API_KEY` is configured, add `X-API-Key` to API calls or enter it in
the report form. Only benchmark agents you are authorized to exercise.

## Documentation

- [Configuration, API operations, and live examples](docs/USAGE.md)
- [Traces, manifests, MLflow judges, and datasets](docs/PROFILING_AND_EVALUATION.md)
- [Architecture](ARCHITECTURE.md) · [Code guide](docs/CODE_GUIDE.md) · [Validation](VALIDATION.md)
- [Dependencies](docs/DEPENDENCIES.md) · [Security](SECURITY.md) · [Deployment gates](docs/PRODUCTION_READINESS.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and checks. Report bugs or ask
questions in [GitHub Issues](https://github.com/RamVegiraju/EvalSurge/issues);
report security issues privately as described in [SECURITY.md](SECURITY.md).

Licensed under [MIT](LICENSE).
