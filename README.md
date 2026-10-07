# EvalSurge

A local-first Python library and REST API for benchmarking hosted agents.

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
uv sync --locked --default-index https://pypi.org/simple --extra agents --group dev
uv run --no-sync uvicorn benchmark_agents.api:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

API docs: `http://127.0.0.1:8000/docs/`. Keep one API worker.
The API host also runs the Locust load generator. A laptop is suitable for this
quickstart; use a separate, dedicated runner for repeatable load measurements.
Runner size and network location affect the result. See [where to run
EvalSurge](docs/USAGE.md#where-to-run-evalsurge).

The quickstart selects public PyPI explicitly and reuses the installed environment.
See [dependency setup and update limits](docs/DEPENDENCIES.md) if your network restricts package access.

### 2. Start the sample agent

In a second terminal, from the repository:

```bash
uv run --no-sync uvicorn examples.mock_agent:app --host 127.0.0.1 --port 9001 --no-proxy-headers
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

Before load, the API checks evaluation setup, invokes the first sample once, and
checks each selected judge against that captured answer. Failure stops load and
shows corrective guidance in the API and report. These extra checks can incur
cost; they are excluded from benchmark metrics and quality scores.

### 4. View the result

Poll until `completed` or `completed_with_gaps`:

```bash
curl --fail-with-body -sS "http://127.0.0.1:8000/v1/runs/$RUN_ID" \
  | jq '{status, preflight, evaluation_preflight, load_status, load_error, evaluation_status, metrics}'
```

`failed`, `cancelled`, and `interrupted` are also terminal; inspect their phase
statuses. Open `http://127.0.0.1:8000/reports/?run=YOUR_RUN_ID` with the returned ID.
For JSON, use `GET /v1/runs/{run_id}/report`.

The mock makes no LLM calls and has no internal traces. For **LangGraph and OpenAI
Agents** with tools, memory, and tracing, see the
[framework agent benchmarks](examples/README.md#framework-agent-benchmarks).

## Benchmark your agent

Replace `target.url` with your authorized supported HTTP endpoint and supply workload
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

### Registered targets and automatic judging (v2)

For the simpler API, the operator registers a target such as `refund-agent` and
configures the planner and judge provider. Clients submit `POST /v2/runs` without
sending endpoint URLs, Databricks profiles, or OAuth tokens:

```json
{
  "name": "refund-quality-baseline",
  "target": {"connection_id": "refund-agent"},
  "cases": [{
    "input": {"query": "Can I refund an opened item?"},
    "reference": {"expected_response": "Opened items are not refundable."}
  }],
  "load": {"concurrency": 3, "duration_seconds": 10, "max_requests": 20},
  "evaluation": {
    "mode": "automatic",
    "description": "Answer refund questions accurately according to the refund policy.",
    "max_scored_requests": 20
  }
}
```

This reference is illustrative; replace it with your authoritative policy.
`automatic` lets the configured LLM recommend supported judges and operator-approved
registered scorers. EvalSurge validates evidence/readiness and freezes the plan;
the model cannot create scorer code or change load limits. Planning and judging
can incur cost, and the sample budget is per selected judge. Judging reuses captured
answers; one additional inference probe occurs before measured load.

Omit `evaluation` or use `mode: "off"` for performance-only runs. Use
`mode: "explicit"` with `scorers` to choose criteria yourself. V2 returns `202`
before planning; poll the returned status link and inspect independent phase
outcomes. `/v1/evaluation-plans` remains available for suggestion/review before
running; v2 automatic mode plans within the run.

See [v2 operator setup, Databricks Apps, remote SDK, and CLI](docs/V2_API.md).

### Python API

With your agent running, no EvalSurge web server is required:

```python
from evalsurge import Agent, EvalSurge, Load, Sample

with EvalSurge.local(artifact_dir="artifacts/python") as client:
    run = client.start(
        agent=Agent.http("http://127.0.0.1:9001/chat"),
        cases=[
            Sample(
                inputs={"query": "Can I refund an opened item?"},
                expectations={"expected_response": "Opened items are not refundable."},
            )
        ],
        load=Load(concurrency=3, max_requests=20, duration_seconds=10),
    )
    report = run.wait(timeout=120)
    print(report.model_dump_json(indent=2))
```

The default is performance-only; enable judging explicitly. `wait()` raises
`RunFailed` with the report if preflight or the run fails. Use `EvalSurge.local_async()` in
async applications. See [Python usage and the JSON contract](docs/PYTHON_API.md).
Local Python runs generate load on this machine; REST runs generate load on the API host.

Start with the credential-free [mock Python quickstart](examples/python_benchmark.py).
For load plus explicit relevance/correctness evaluation of framework agents, use
[LangGraph](examples/langgraph_benchmark.py) or
[OpenAI Agents](examples/openai_agents_benchmark.py); see the
[example guide](examples/README.md#framework-agent-benchmarks) for agent startup,
judge configuration, and costs. Advanced CLI and integration runners live
separately under `scripts/validation/`.
For a three-minute run and report UI, see [the Python example](docs/PYTHON_API.md#three-minute-example).
For an existing REST server, use the [Python Requests example](docs/USAGE.md#python-requests-client).
Duration limits dispatch, not total runtime; the request cap may stop it sooner.
See [runtime and timeouts](docs/USAGE.md#how-long-does-a-run-take).

### Optional quality evaluation

Configure the [judge and MLflow tracking settings](docs/USAGE.md#planning-and-evaluation),
then pass this policy as `evaluation=evaluation` to `client.start(...)`:

```python
from evalsurge import Evaluation

evaluation = Evaluation(
    description="Apply the refund policy correctly.",
    scorers=["relevance", "correctness"],
    registered_scorers=[],
    max_scored_requests=20,
)
```

Correctness uses the authoritative `expectations` supplied in each case.
`max_scored_requests` is EvalSurge's sample budget **per judge**, not a load limit
or an MLflow requirement. Judges reuse captured answers, never reinvoke the agent.

### Example report output

Illustrative JSON excerpt **with judging enabled**, showing one failed assessment.
IDs/timings vary; configuration, other assessments, and profile fields are omitted.
The performance-only quickstart instead returns `evaluation.status: "no_ready_scorers"`.

```json
{
  "run": {
    "id": "00000000-0000-4000-8000-000000000001",
    "status": "completed",
    "metrics": {
      "requests": 20,
      "successful_requests": 20,
      "error_rate": 0.0,
      "successful_tps": 40.0,
      "timing_successful_only": {
        "latency_ms": {"count": 20, "p50": 52.0, "p95": 55.0, "p99": 58.0},
        "ttft_ms": {"count": 20, "p50": 26.0, "p95": 28.0, "p99": 30.0}
      }
    },
    "evaluation": {
      "status": "completed",
      "results": [{
        "scorer": "correctness",
        "attempted": 20,
        "scored": 20,
        "judge_errors": 0,
        "pass_rate": 0.8,
        "assessments": [{
          "request_id": "00000000-0000-4000-8000-000000000002",
          "case_id": 0,
          "status": "failed",
          "value": false,
          "rationale": "The answer allowed a refund for an opened item.",
          "rationale_truncated": false,
          "error": null
        }]
      }]
    }
  }
}
```

Lifecycle `completed` is not a quality pass. Judge execution errors show safe
diagnostics instead of quality verdicts. Heatmaps require correlated agent-side
traces; the Python API returns data, not a running report server.
Protect reports: judge rationales can quote private inputs, answers, and references.

## Documentation

- [Registered-target v2 API, remote SDK/CLI, and Databricks Apps](docs/V2_API.md)
- [Configuration, API operations, and live examples](docs/USAGE.md)
- [Traces, manifests, MLflow judges, and datasets](docs/PROFILING_AND_EVALUATION.md)
- [Architecture](ARCHITECTURE.md) · [Code guide](docs/CODE_GUIDE.md) · [Validation](VALIDATION.md)
- [Dependencies](docs/DEPENDENCIES.md) · [Security](SECURITY.md) · [Deployment gates](docs/PRODUCTION_READINESS.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and checks. Report bugs or ask
questions in [GitHub Issues](https://github.com/RamVegiraju/EvalSurge/issues);
report security issues privately as described in [SECURITY.md](SECURITY.md).

Licensed under [MIT](LICENSE).
