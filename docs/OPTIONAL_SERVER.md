# Optional EvalSurge server

Use direct [Python execution](PYTHON_API.md) first. A server is useful when the
runner must live on a dedicated host or share operator-owned registrations. It
does not change the request vocabulary or create a second load engine.

## Register targets on the runner

Install `evalsurge[server]` on the runner. Keep this private operator TOML outside
public benchmark requests:

```toml
artifact_dir = "artifacts/server"

[connections.agent]
kind = "http"
url = "http://127.0.0.1:9001/chat"
protocols = ["openai-chat"]

# For an App, replace that binding with:
# [connections.agent]
# kind = "databricks-app"
# app_name = "your-deployed-app"
# profile = "YOUR_SELECTED_OAUTH_PROFILE"
# protocols = ["databricks-agent-runtime"]
```

Start one API owner/worker:

```bash
BENCHMARK_CONFIG=operator.toml uv run uvicorn benchmark_agents.api:app \
  --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Registrations do not deploy agents or grant spend consent. Configure
`BENCHMARK_API_KEY` and terminate TLS before serving beyond loopback. This local
alpha has one tenant and one active run; a shared key is not tenant isolation.
See [production gates](PRODUCTION_READINESS.md) before shared hosting.

## Submit the same request

```python
from evalsurge import Case, EvalSurge, Load, RunCreate, TargetReference

request = RunCreate(
    target=TargetReference(connection_id="agent"),
    cases=[Case(input={"query": "Give a short greeting."})],
    load=Load(concurrency=2, duration_seconds=10, max_requests=10),
)
with EvalSurge.remote("http://127.0.0.1:8000", typed=True) as client:
    report = client.start(request).wait(timeout=300)
    print(report.model_dump_json(indent=2))
```

HTTPX/Pydantic-only clients can use the base `evalsurge` install. Profiles, target
URLs, App authentication, and registered judge code remain on the server.
For a protected server, pass `api_key=os.environ["EVALSURGE_API_KEY"]` after
importing `os`. That service key stays outside the benchmark request and is not
target authentication. The CLI reads `EVALSURGE_API_KEY` itself.

REST uses `POST /v2/runs` and typed status/result/report/cancel resource paths.
The [v2 guide](V2_API.md) has the full lifecycle, safe error envelope, and CLI
commands. CLI summaries show available measurements; `--json` explicitly exports
protected structured data. Target discovery lists registrations without invoking
agents or enumerating Apps. The four existing [framework request files](FRAMEWORK_TARGET_EXAMPLES.md)
remain server-ready examples.

Traffic comes from the API host, even when you submit from a laptop/notebook.
The target must be reachable from that host. Wait timeout is not cancellation;
do not resubmit uncertain admissions without an idempotency key.

## Open a retained report

Close the direct Python client before starting another owner of its artifacts:

```bash
BENCHMARK_ARTIFACT_DIR=artifacts/first-benchmark uv run uvicorn \
  benchmark_agents.api:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Open `http://127.0.0.1:8000/reports/?run=YOUR_RUN_ID`. The page is a data-free shell;
enter the API key if configured. It fetches protected report data same-origin.
Keys are kept in memory, not the URL or persistent browser storage. The
[report guide](REPORTS_AND_JUDGES.md) explains suggestions, assessments, metrics,
trace pages, and gaps. This is not standalone HTML export.

## Legacy v1

`/v1` remains supported for existing integrations and frozen-plan workflows.
Legacy explicit `scorers=[]` disables judging; legacy `scorers=None` can invoke
planning. Prefer `RunCreate`/`EvaluationPolicy` and `/v2` for new work.
