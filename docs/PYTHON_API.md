# Python API

The distribution is `evalsurge`; the public import is `evalsurge`. The existing
`benchmark_agents` modules remain available for the REST application and compatibility.
From a checkout, install with
`uv sync --locked --default-index https://pypi.org/simple --extra agents --group dev`.

The checkout uses an authentic public-PyPI recovery lock, with installation
verified on macOS/Python 3.12 including agents/dev dependencies on October 5, 2026.
It removes the private-mirror origins responsible for earlier CI install failures;
it is not a fresh latest-compatible resolution or a current Linux CI result.
Latest-compatible upgrades, the supported Linux/Python matrix, and clean published
release installation remain subject to the [dependency release gates](DEPENDENCIES.md).

## Local benchmark

Start the deterministic sample agent from a checkout:

```bash
uv run --no-sync uvicorn examples.mock_agent:app --host 127.0.0.1 --port 9001 --no-proxy-headers
```

Then run:

```python
from evalsurge import Agent, EvalSurge, Load, RunFailed, Sample

with EvalSurge.local(artifact_dir="artifacts/python") as client:
    run = client.start(
        agent=Agent.http("http://127.0.0.1:9001/chat"),
        cases=[Sample(inputs={"query": "Can I refund an opened item?"})],
        load=Load(concurrency=2, duration_seconds=5, max_requests=3),
        idempotency_key="first-python-run",
    )
    try:
        report = run.wait(timeout=120)
    except RunFailed as failure:
        print(failure)
        report = failure.report
    print(report.model_dump_json(indent=2))
```

`start()` freezes a plan and schedules preflight; it does not guarantee inference
success. `wait()` returns a typed `RunReport`, or raises `RunFailed` for a failed,
cancelled, or interrupted run. `completed_with_gaps` is returned normally: inspect
evaluation and trace coverage, not just the lifecycle status.

The first sample is one extra invocation beyond `max_requests`. It may execute
tools, mutate memory, and incur spend. It is excluded from benchmark metrics and
quality scores; selected judges reuse its answer for readiness before load.
`RunFailed` includes safe guidance for inference, judge readiness, or worker failure.
No retries, redirect following, model substitution, or automatic parameter repair.

`run.report(offset=0, limit=25)` reads a bounded profile page. It may be unavailable
before profiling. Pages are limited to 100 rows; the initial report is not the
entire large-run waterfall. `run.cancel()` requests dispatch stop and drain during
preflight/load, not judging cancellation. A wait timeout only stops waiting.

The context owns one POSIX artifact directory, requests cancellation on exit,
and drains its work before releasing ownership. Do not open the same directory
in a simultaneous REST server or another local client. Context exit can wait for
active requests and post-load work; scorer code has no hard execution sandbox.
Artifacts retain prompts, outputs, and references; protect them and set retention.

### Three-minute example

From this checkout, start the sample agent in one terminal:

```bash
uv run --no-sync uvicorn examples.mock_agent:app --host 127.0.0.1 --port 9001 --no-proxy-headers
```

In another terminal, run the [minimal Python example](../examples/python_benchmark.py):

```bash
uv run --no-sync python -m examples.python_benchmark
```

It uses five concurrent users and at most 10,000 measured requests, plus one excluded
preflight. Dispatch ends when duration or the request cap is reached, whichever
comes first; startup and drain add time. Judging is off, the mock makes no model
calls, and an endpoint without traces cannot show internal tool/model timings.
The command prints report JSON, including `run.id` and `run.metrics`, and retains
the run under `artifacts/python-benchmark/`. That JSON contains the first bounded
request page; journals retain all attempts. Edit the endpoint, cases, and `Load`
directly in the example; there is no EvalSurge server setup or polling code to copy.

To view the existing report UI after the Python command exits:

```bash
BENCHMARK_ARTIFACT_DIR=artifacts/python-benchmark uv run --no-sync uvicorn \
  benchmark_agents.api:app --host 127.0.0.1 --port 9002 --no-proxy-headers
```

Open `http://127.0.0.1:9002/reports/?run=YOUR_RUN_ID` with the printed `run.id`.
If the service has an API key configured, enter it in the report form.
Only use an authorized endpoint; replacing the mock URL can execute agent actions
and incur model/tool costs. For CLI flags such as `--duration` or `--concurrency`,
use the [advanced validation CLI](../scripts/validation/README.md).

For load plus explicit relevance/correctness evaluation of framework agents, use
the [LangGraph sample](../examples/langgraph_benchmark.py) or
[OpenAI Agents sample](../examples/openai_agents_benchmark.py). Both use this
facade against the corresponding `examples/framework_agent.py` endpoint, supply
authoritative references, and cap post-load scoring at five answers per judge.
The framework target defaults to fixture model responses, but configured judges
can still incur costs. See the
[framework example guide](../examples/README.md#framework-agent-benchmarks) for
server startup, judge/tracking configuration, endpoint URLs, and artifact paths.
Local tests use controlled provider boundaries, not paid/live validation.

For the REST API with ordinary Python `requests`, use the
[request-to-report example](USAGE.md#python-requests-client). Total runtime includes
setup, readiness, drain, profiling, and judging in addition to dispatch:
see [runtime and timeouts](USAGE.md#how-long-does-a-run-take).

## Async applications and notebooks

```python
async with EvalSurge.local_async(artifact_dir="artifacts/async") as client:
    run = await client.start(
        agent=Agent.http("http://127.0.0.1:9001/chat"),
        cases=[Sample(inputs={"query": "Can I refund?"})],
        load=Load(concurrency=1, duration_seconds=5, max_requests=1),
    )
    report = await run.wait(timeout=120)
```

Use the async form when the target runs on the same event loop. The synchronous
form uses a dedicated coordinator thread/loop, not nested `asyncio.run`, but its
blocking calls can still block your notebook/application loop.

Serialized UTF-8 workloads/policies are capped at eight million bytes before
planning, in addition to case/load/page bounds. Persistence failures stop new
admission. A terminal in-process receipt can remain readable with an explicit
durability warning, but it is not guaranteed to survive restart; restore storage
and reopen the runner. Restart never resumes or replays target actions.

## Protocol and connection

`Agent.http(url, protocol=..., connection=...)` keeps the wire format independent
from reachability/authentication. Supported protocols:

| Protocol | Request | Response | TTFT |
| --- | --- | --- | --- |
| `openai-chat` (default) | Chat messages, model, `stream: true` | Chat Completions SSE | First answer-text delta |
| `mlflow-agent-server` | `input` messages, `stream: true` | Responses-style SSE | First answer-text delta |
| `http-json` | Exact `Sample.inputs` object | JSON object with `outputs` text | Unavailable |

For `http-json`, a sample `Sample(inputs={"query": "Hello", "session_id": "demo"})`
sends exactly `{"query":"Hello","session_id":"demo"}`. A successful response is:

```json
{"outputs":"Hello!","usage":{"output_tokens":3},"trace_id":"tr-optional"}
```

`outputs` must be a nonblank string. If `usage` is present, `usage.output_tokens`
must be a nonnegative integer, not a Boolean; absent usage remains unknown, not
zero. Optional trace IDs must be nonblank strings of at most 128 characters and
agree with `X-MLflow-Trace-ID` when both are supplied. Responses require 2xx,
`application/json` content type (parameters allowed; `+json` types are not
supported), valid UTF-8, and a complete body within the two-million-byte decoded
limit and request deadline. Malformed, empty, oversized, or wrong-type responses
fail preflight before load.
This is a documented contract, not support for arbitrary JSON layouts or user
plugins. JSON has latency/throughput, but `ttft_ms` and `first_event_ms` stay null.

The local caller is the operator. Its explicit connection is URL-bound and never
temporarily changes global connection configuration:

```python
from evalsurge import Agent, Connection

url = "https://agent.example/invoke"
agent = Agent.http(
    url,
    protocol="http-json",
    connection=Connection(url=url, auth="bearer", token_env="AGENT_TOKEN"),
)
```

Keep `AGENT_TOKEN` in the runner environment, not in source or report URLs.
Remote connections require HTTPS. The Databricks workspace auth binding still
requires an explicitly selected profile and the matching workspace host; App URL
resolution and App OAuth onboarding are a separate milestone.

## Evaluation and profiling

Python defaults to `scorers=[]` and `registered_scorers=[]`: no implicit paid
planner/judge call. Pass `Evaluation(description=..., samples=cases, ...)`
explicitly to request configured suggestions or judges. Cases and evaluation
samples must agree. Planner, judge, trusted scorer registry, and trace source
remain operator-configured; see [integration](PROFILING_AND_EVALUATION.md).
The facade does not reinvoke the target during judging.

Endpoint-only reports provide black-box metrics. Internal heatmaps need existing
agent-side correlated MLflow traces; an endpoint cannot reveal tool/memory time.
The Python API returns report data, not a running browser/report server.
After closing the client, a REST server can open the same artifact directory to
inspect saved runs through the existing report UI.

## Where load runs

Local Python uses this process's machine for Locust; REST uses the API host,
not the remote submitter. Use a laptop for smoke checks and a dedicated runner
separate from the agent for repeatable load tests. Record runner location, machine
size, network path, and dependency versions. Runner saturation and network latency
can distort results; this milestone does not automatically diagnose generator
saturation or establish sustainable capacity from one short concurrency level.
