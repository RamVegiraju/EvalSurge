# Registered-target API, SDK, and Databricks Apps

`/v2` provides admission, lightweight status, typed results, paginated reports,
cancellation, and static capabilities over the existing coordinator and Locust
engine. The runner remains a local single-owner service. `/v1` and the local
Python API remain available.

End users can select either a locally hosted HTTP agent or a Databricks App from
the operator registry. Both use the same request and execution pipeline; see
[the two-target guide](TARGETS.md). Localhost refers to the API/load-generator
host, not a remote submitter's laptop.

Plain `evalsurge` installs only the remote SDK/CLI and their HTTPX/Pydantic
dependencies. Install `evalsurge[server]` to run local
benchmarks or the API. `evalsurge[agents]` includes server plus framework dependencies;
the existing checkout `uv sync --locked --extra agents --group dev` remains valid.
Local imports/factories report a missing-extra diagnostic in a remote-only install.

Start the API with proxy headers disabled:

```bash
BENCHMARK_CONFIG=operator.toml uv run --no-sync uvicorn benchmark_agents.api:app \
  --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Protect the operator file and artifacts. Configure `BENCHMARK_API_KEY` when serving
remote clients and terminate TLS. Credentials remain in operator environment/SDK
configuration, never in public benchmark requests.

## Operator configuration

TOML works with the standard library. YAML requires optional PyYAML; safe loading
rejects executable tags, references, and duplicate keys. Files and JSON environment
registries are capped at one million bytes. Environment values override file fields;
an environment registry replaces the complete file registry. Existing
`BENCHMARK_CONNECTIONS`, provider, tracking, tracing, and API-key settings remain
supported. Explicit `create_app(config_path=Path(...))` wins over
`BENCHMARK_CONFIG`. File-backed applications capture a private runtime snapshot
at creation; subsequent file edits require restarting the application. No process
environment is temporarily changed.

For an ordinary HTTP agent:

```toml
artifact_dir = "artifacts"

[connections.refund-agent]
url = "http://127.0.0.1:9001/chat"
protocols = ["openai-chat"]
```

Supported HTTP protocols are `openai-chat`, `mlflow-agent-server` (`/responses`),
`http-json`, and `databricks-agent-runtime`. The first declared protocol is the
operator default; legacy presets with no list default to `openai-chat`. Use
`auth = "bearer"` with `token_env = "OPERATOR_TOKEN"` for an HTTPS credential-bound
HTTP target. Bearer values are read from the runtime environment at dispatch and
never copied to artifacts. File-backed applications capture that private environment
at creation, including bearer values; restart or recreate the application after
rotating those credentials. Legacy applications without a configuration file read
the current process environment at dispatch.

For a Databricks App, the operator selects the exact SDK profile:

```toml
[connections.refund-agent]
kind = "databricks-app"
app_name = "refund-agent"
profile = "YOUR_EXPLICIT_PROFILE"
protocols = ["databricks-agent-runtime"]
```

This is the App default for DurableAgentServer/Agent Bricks CLI deployments.
The [current official query guide](https://docs.databricks.com/aws/en/agents/query-llms)
(checked October 7, 2026) distinguishes that invocation API from legacy MLflow
AgentServer and LongRunningAgentServer Apps. For an existing MLflow App, use the
same registration with `protocols = ["mlflow-agent-server"]` to select `/responses`.
No protocol detection, fallback traffic, or alternate engine is used.

App URLs come from `WorkspaceClient.apps.get(name=...)`; the public request cannot
choose workspace hosts, profiles, App URLs, or OAuth tokens. Authentication requires
SDK OAuth, refreshes per attempt, and stays bound to the discovered exact origin.
The SDK loads ambient credential/host settings before profile fields. App resolution
therefore rejects conflicting `DATABRICKS_HOST` or SDK credential overrides in both
process and captured runtime settings. Run with an isolated profile-based operator
environment; profile/config-file selectors are allowed. PAT authentication is not
accepted for Apps. These controls are covered with the native SDK and controlled
HTTP boundaries. A separate bounded native App check passed using the local
facade/registered resolver; it did not deploy EvalSurge or exercise live `/v2`
HTTP submission. See [the validation record](../VALIDATION.md); this does not
establish universal App compatibility or production readiness.
App profiles require the same configuration-file selector in the API process and
frozen worker environment because SDK CLI OAuth subprocesses inherit the process
environment. Different selectors fail closed before SDK resolution; static local
doctor reports this conflict without opening either configuration file.

App lookup/authentication runs in a thread before admission and can contact the
workspace/auth service. It never invokes the agent. Static capabilities and doctor
perform no lookup, authentication, scorer deserialization, or target invocation.
SDK HTTP/retry budgets are not hard discovery or OAuth wall-time deadlines:
credential refresh or a CLI credential subprocess can stall. Thread offloading
keeps the event loop responsive but cannot terminate that work, so App admission
can wait before returning 202. Process-isolated discovery/authentication with hard
deadlines remains a production gate; do not treat nominal SDK timeouts as proof
of a bounded admission latency.

The runtime adapter uses synchronous JSON `POST /api/invocations` with
`id`, `input`, `stream: false`, `background: false`, and an isolated session UUID
per attempt. Invocation IDs match journal request IDs. It supports the documented
string/`answer` outputs and CLI-template completed assistant-message output.
Background, incomplete, interrupted, mismatched-ID, or unsupported responses fail
preflight/load safely. No polling or replay is hidden inside an attempt. JSON TTFT
and first-event timing are unavailable; token usage is currently unknown for this
adapter. Legacy `/responses` accepts returned MLflow trace
metadata, including the native final trace event, without synthesizing internal spans.

An optional operator `session_id` deliberately shares invocation ordering.
It can serialize requests and change answers when the target implements history;
the identifier alone does not configure memory. The default isolated
sessions avoid accidental shared conversation state; the probe still performs an
extra invocation and can warm caches or execute external actions.

For `openai-chat`, `mlflow-agent-server`, and `databricks-agent-runtime`, every
case's `input` must contain exactly one of `query` (a nonempty string) or `messages`
(a nonempty list of role-bearing message objects). Nested messages are transmitted
unchanged. Extra top-level fields are rejected before planning/inference, never
discarded. This includes `custom_inputs`, `actor`, per-case `model`, and `resume`:
although upstream servers support some of these, EvalSurge's fixed adapters do not
yet have an operator-governed mapping for them. Put evaluation references in
`reference`, not `input`. The explicit `http-json` contract sends its raw input body
unchanged and requires its documented response shape; it is not an arbitrary
AgentServer compatibility adapter.

For live App testing, follow the [bounded smoke-test guide](DATABRICKS_APP_VALIDATION.md).
It requires a selected profile, App/protocol, safe prompt, and traffic/spend consent;
its default dry run makes no workspace or inference calls.

## Submit and retrieve a benchmark

```python
from evalsurge import EvalSurge

request = {
    "name": "refund-baseline",
    "target": {"connection_id": "refund-agent"},
    "cases": [{"input": {"query": "Can I refund an opened item?"}}],
    "load": {"concurrency": 3, "duration_seconds": 10, "max_requests": 20},
}

with EvalSurge.remote("http://127.0.0.1:8000") as client:
    run = client.start(request, idempotency_key="refund-baseline-001")
    report = run.wait(timeout=120)
    print(report["run"]["summary"])
```

The acknowledgement contains an ID and resource links. SDK methods return bounded
JSON mappings; the server validates status/result/report envelopes and client
performance metrics with Pydantic models. Native assessment variants remain bounded
protected dictionaries. Service keys are held in memory and sent only in headers.
The SDK constructs paths from validated IDs, does not follow returned links or
redirects, honors polling guidance, and never automatically retries mutations.
Waiting timeouts leave server work running; cancellation is an explicit operation.
`run.cancel()` can return `status: "cancellation_requested"`; this acknowledges
the request, not completed cancellation. Poll for the persisted terminal state.
Already dispatched calls drain and their side effects are not rolled back.

Evaluation defaults to `off` and cannot call the planner or judges. `automatic`
opts into bounded catalog and allowlisted-scorer planning; `explicit` requires `scorers`, using catalog
IDs or approved `registered:alias` IDs. Supply authoritative `reference` objects
on cases for correctness, and a meaningful evaluation `description`. Registered
scorers remain trusted exact-version operator code, not uploaded caller code.

To enable automatic judge selection, configure planner and catalog-judge endpoints
in the operator file using the exact profile and endpoints you selected:

```toml
[provider]
name = "databricks"
profile = "YOUR_EXPLICIT_PROFILE"
planner_model = "YOUR_PLANNER_ENDPOINT"
judge_model = "databricks:/YOUR_JUDGE_ENDPOINT"
```

Then submit this complete request through the SDK or save it as `benchmark.json`
for the CLI. The target remains the registered connection above:

```json
{
  "name": "refund-quality-baseline",
  "target": {"connection_id": "refund-agent"},
  "cases": [{
    "input": {"query": "Can I refund an opened item?"},
    "reference": {"expected_response": "Opened items cannot be refunded."}
  }],
  "load": {"concurrency": 3, "duration_seconds": 10, "max_requests": 20},
  "evaluation": {
    "mode": "automatic",
    "description": "Assess whether answers address refund questions and correctly apply the supplied refund policy.",
    "max_scored_requests": 5
  }
}
```

Automatic mode asks the configured planner to select criteria, then runs selected
ready judges; it does not merely display suggestions. Planner, judge-readiness, and
post-load judge calls can incur spend. The planner does not select model endpoints
or invent authoritative references. Its selections remain uncalibrated, and selected
criteria with missing evidence prevent measured load. To fix the criteria yourself,
use `"mode": "explicit"` with `"scorers": ["relevance", "correctness"]` instead.

After validation and target resolution, `/v2/runs` returns `202` before planning.
Planning is persisted as a run phase; failures remain reportable with skipped load.
One inference preflight and selected judge-readiness assessments precede measured
traffic. Judging uses captured answers. Independent phase results, quality errors,
and trace gaps survive failures. A completed lifecycle is not a passing quality
verdict. The summary never claims sustainable capacity from one concurrency level.

The HTTP resources are `/v2/runs`, `/v2/runs/{id}`, `/result`, `/report`, `/cancel`,
and `/v2/capabilities`. Report pages accept `offset >= 0` and `1 <= limit <= 100`.
Errors include safe `code`, `phase`, `retryable`, `guidance`, and request correlation.
`report_not_ready` is a transient 409; idempotency conflicts are not retryable.
Reusing an idempotency key binds the complete canonical request, including its name.
Restart recovery never repeats planning or agent actions. SDK report links open the
existing protected report shell for runs with frozen plans; deferred planning
failures render through its same-origin v2 fallback as well. History retains v1
links for v1 runs and advertises v2 links for v2 runs, including planless failures.

V2 schema failures also include at most 20 sanitized `error.errors` entries, e.g.:

```json
{
  "location": ["body", "load", "concurrency"],
  "code": "out_of_bounds",
  "message": "Must be greater than or equal to 1"
}
```

These entries contain public field names and safe constraints, never submitted
values or raw validator errors. Unknown input keys become `<extra>`. Correct the
listed fields and resubmit; later issues may be omitted by the bound. V1's error
envelope remains unchanged.

```bash
EVALSURGE_URL=http://127.0.0.1:8000 uv run --no-sync evalsurge doctor
uv run --no-sync evalsurge run benchmark.json --wait --timeout 120 --open-report
```

For remote access, set `EVALSURGE_API_KEY` without putting the key in arguments or
URLs. `doctor` retrieves static capabilities; it reports configuration, not live
health. Local operators can also call `benchmark_agents.diagnostics.doctor()` to
inspect their file/environment without starting storage or contacting providers.

## Deferred milestones

History cursors, timestamps, tags, retention/export/archive/delete, and ordered
capacity campaigns remain later work. There is still one active run, up to 100
users, 10,000 attempts, 1,000 cases, and an eight-million-byte request limit.
EvalSurge itself is not deployed inside a production Databricks App: durable
workers/Jobs, transactional metadata/leases, object storage, tenant isolation,
quotas, and generator-health evidence must satisfy
[the production gates](PRODUCTION_READINESS.md). See
[ADR 0009](adr/0009-v2-databricks-app-boundaries.md) for the architecture and
maintainer-review requirement. Live validation needs a separately authorized
profile and bounded traffic/spend.
