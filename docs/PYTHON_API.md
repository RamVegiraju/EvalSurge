# Python API: direct execution first

Install `evalsurge[server]` for direct execution; `evalsurge[agents]` additionally
includes LangGraph and OpenAI Agents for the repository demos. The base package
contains lightweight remote SDK/CLI dependencies. Public request/result models
are available from `evalsurge` without loading the execution stack.

## One request, two targets

```python
from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference

request = RunCreate(
    name="baseline",
    target=TargetReference(connection_id="agent"),
    cases=[Case(input={"query": "Give a short greeting."})],
    load=Load(concurrency=2, duration_seconds=10, max_requests=10),
)

agent = Agent.http("http://127.0.0.1:9001/chat")
# Instead, for an already deployed DurableAgentServer App:
# agent = Agent.databricks_app("your-app", profile="YOUR_SELECTED_OAUTH_PROFILE")

with EvalSurge(artifact_dir="artifacts/baseline", targets={"agent": agent}) as client:
    run = client.start(request, idempotency_key="baseline-1")
    report = run.wait(timeout=300)
    print(report.model_dump_json(indent=2))
```

`EvalSurge(...)` is direct execution; `EvalSurge.local(...)` is its explicit alias.
The caller owns target settings and the artifact directory. The request contains
only an alias, cases, load, and evaluation policy. No server is started.
`start()` also accepts finite JSON-compatible mappings through the same schema.
Both modes apply the same eight-million-byte UTF-8 limit without ASCII-escaping
Unicode. Raw mappings cannot contain Python-only values such as `datetime`; a
validated `RunCreate` uses its public Pydantic JSON serialization in both modes.
Unknown fields and invalid values receive bounded field-specific guidance.

An explicit `artifact_dir` overrides operator settings. If omitted, supplied
`Settings.artifact_dir` is used, or settings are loaded once from the operator file
and environment. Without configuration the legacy default remains `artifacts`.
The coordinator and private worker snapshot use the same
selected directory. Target bindings and settings are copied before work starts.

`cases[].input` holds agent inputs; `reference` holds authoritative evaluation
evidence. Fixed message adapters require exactly `query` or `messages`; custom
routing, actor, resume, or other top-level inputs are rejected, not discarded.
Raw `http-json` inputs follow their separate contract.

## Protocol and connection

`Agent.http(url, protocol="openai-chat")` selects the wire envelope independently
of hosting. Supported alternatives are `mlflow-agent-server`, `databricks-agent-runtime`,
and `http-json`; see [target wire contracts](TARGETS.md#supported-wire-contracts).
Framework names do not select a protocol automatically.

Unauthenticated loopback HTTP needs only the explicit URL. An HTTPS bearer target
uses an operator-owned environment reference, never a token in the request:

```python
from evalsurge import Connection

agent = Agent.http(
    "https://your-authorized-agent.example/chat",
    connection=Connection(
        url="https://your-authorized-agent.example/chat",
        auth="bearer",
        token_env="AGENT_BEARER_TOKEN",
    ),
)
```

Databricks Apps use `Agent.databricks_app(name, profile=...)`; no arbitrary App URL
or workspace host belongs in `RunCreate`. Binding construction does not invoke
the agent. Resolution/authentication uses the explicit profile and existing
operator resolver; OAuth refresh stays bound to the discovered origin. PAT App
access, contradictory ambient SDK settings, and protocol fallback are unsupported.
An existing legacy AgentServer App uses `protocol="mlflow-agent-server"` explicitly.

## Typed lifecycle

| Method | Unified return | Meaning |
| --- | --- | --- |
| `client.start(request)` | Run handle | Admission and background work, not inference success |
| `run.status()` | `RunStatus` | Current independent phase states |
| `run.result()` | `Result` | Typed metrics, evaluation outcomes, coverage, and gaps |
| `run.report(offset=0, limit=25)` | `Report` | Result plus one bounded profile page |
| `run.wait(timeout=None)` | `Report` | Wait for terminal outcome; `None` has no client wait deadline |
| `run.cancel()` | `Acknowledgment` | Request stop/drain; not proof that work has stopped |

Use an explicit finite wait budget in interactive work. A client wait timeout
does not cancel the run. Failure exceptions retain the report; inspect independent
preflight, evaluation-readiness, load, and evidence outcomes. Successful lifecycle
completion is not a quality pass. `completed_with_gaps` preserves available evidence.

Cancellation stops new preflight/load dispatch and drains active work; it cannot
undo model/tool actions and does not promise to interrupt native judging. Report
pages are limited to 100 profiles; the initial report is not every trace in a run.

The context closes its owned work and releases storage ownership on normal exit
or error. Cleanup can wait for active requests and post-load work. Do not share
one artifact directory with another client/API owner. Persisted interrupted work
is not automatically resumed. Protect retained prompts, answers, and references.

## Evaluation and your dataset

Evaluation is off when omitted. Use `EvaluationPolicy(mode="explicit", scorers=...)`
for fixed criteria or `mode="automatic"` for opt-in selection. Target inference,
planning, and judging are separate model roles; configure providers outside the
request. See [quality samples](../examples/quality/README.md) for JSON datasets,
catalog criteria, brought reviewed judges, and fail-fast evidence edges.

The first case incurs one excluded inference probe. Selected judges reuse it for
one extra readiness assessment each, then judge sampled captured answers after
load. No target reinvocation during evaluation. A false quality verdict is a valid
assessment, not a readiness execution failure. Missing correctness references,
required traces, or provider configuration remain explicit failures/gaps.

## Databricks notebook

**Prepared, authentication-blocked—not live-validated.** Review
[the serverless runner-only source notebook](../examples/journeys/serverless_runner_databricks_app_target.py)
and its [readiness harness](../scripts/validation/serverless_runner_app_target.py).
Their availability does not establish supported live notebook-to-App execution.

The notebook is the EvalSurge/Locust **load generator**; the target agent remains
in its deployed Databricks App. This is a runner-location choice, not an additional
agent-hosting option. Use the same public `RunCreate` request and context cleanup
as a laptop run. The current scope is serverless only; the retained
[classic notebook source](../examples/journeys/classic_notebook.py) is deferred.
A laptop profile is not notebook authentication, and driver-only credential
success is not evidence the spawned worker can authenticate.
The [serverless runner status](SERVERLESS_RUNNER_STATUS.md) explains why hosting
FastAPI in the notebook does not repair worker OAuth, and why calling an external
API instead changes the load-generator location.

`Agent.databricks_app` currently requires a selected profile; it does not accept
an injected native notebook SDK client. The operator resolver rejects ambient
destination/identity overrides before App discovery. Independently, native
driver `runtime-oauth` relies on notebook context unavailable to the Locust
subprocess in the retained prerequisite check. Do not copy notebook tokens or
laptop OAuth-cache/profile files, bypass the guard or silently select a new
principal. A supported operator-auth change requires an ADR and maintainer review.

The initial sample performs at most one excluded inference preflight and one
measured App invocation at concurrency one, evaluation off. Before authorizing
traffic, verify the driver/profile binding, independent worker OAuth, exact
deployed-App readiness and reviewed no-tool source with a <=512 output-token
limit. This is an App-invocation bound, not a generic model/tool-turn or dollar
quota. The native async context uses notebook top-level `await` and closes its
runner lifecycle; it does not delete Apps or Lakebase. Optional remote/API
execution, fail-fast and cancellation are separate notebook validation gates.
See [the validation checklist](../scripts/validation/README.md#serverless-notebook-validation).

Serverless notebook execution is a separate validation gate: subprocess execution,
credential availability, local storage locking, egress, and notebook shutdown all
need real checks. Neither sample code nor classic success proves serverless support.
Samples do not provision compute, Apps or models. The notebook-local helper
diagnostic is not a substitute for the intended deployed-App target.

The October 8 serverless HTTP/API job failed: its Python kernel exited and its
output included an MLflow experiment/store startup mismatch. It returned no final
receipt, so request counts, active cancellation and cleanup are not established.
The harness's experiment-ID leak and native Uvicorn startup-exit path are covered
by local storage/lifespan regressions, but have not been revalidated live.
The corrected zero-inference prerequisite confirmed driver OAuth, loopback and
POSIX lock/fsync; independent worker runtime-OAuth still failed. Notebook-to-App
validation therefore remains authentication-blocked. Neither Job success nor
the historical notebook-hosted helper establishes a deployed-App pass. See
[validation](../VALIDATION.md).

## Optional remote execution

```python
with EvalSurge.remote("http://127.0.0.1:8000", typed=True) as client:
    report = client.start(request).wait(timeout=300)
    print(report.model_dump_json(indent=2))
```

The server must register `agent` itself. Local `targets` are not uploaded.
Traffic originates on the API host; `127.0.0.1` in a registered endpoint means
that host. Configure remote service credentials outside the request, and use TLS
beyond loopback. [Optional server setup](OPTIONAL_SERVER.md) covers registration,
CLI, and authentication.

### Open a retained report

Direct execution returns JSON/models, not an HTTP server. After closing the
client, serve the same artifact directory using [the report instructions](OPTIONAL_SERVER.md#open-a-retained-report).
The browser displays frozen suggestions and actual assessments separately. V2
`Report` intentionally omits the frozen plan; see [report details](REPORTS_AND_JUDGES.md).

## Compatibility interfaces

`/v1` and existing local keyword calls remain supported:

```python
from evalsurge import Sample

with EvalSurge.local(artifact_dir="artifacts/legacy") as client:
    run = client.start(
        agent=Agent.http("http://127.0.0.1:9001/chat"),
        cases=[Sample(inputs={"query": "Give a short greeting."})],
        load=Load(concurrency=2, duration_seconds=10, max_requests=10),
    )
    legacy_report = run.wait(timeout=300)
```

These calls return legacy `RunReport`. Legacy `Evaluation(scorers=None)` requests
planning, while `scorers=[]` disables it; new `EvaluationPolicy` defaults to off.
Without explicit context `settings` or `targets`, legacy calls retain their
submission-time operator environment and ignore the unused registered-target
registry. Unified calls freeze context configuration and validate any selected
registry before discovery or admission. Both inherit an enclosing task-local
operator scope without changing process environment values.
Existing `EvalSurge.remote(url)` and `RemoteClient` retain dictionary behavior.
Use `typed=True` for the unified remote return types. Do not mix the return shapes.
Native local async execution remains `EvalSurge.local_async(...)`. The prepared
serverless runner-only notebook uses this context with top-level `await`; the
retained synchronous examples do not establish notebook authentication support.

### Three-minute example

The retained [legacy Python sample](../examples/python_benchmark.py) runs a
credential-free mock at concurrency five for at most 180 seconds/10,000 measured
requests. It is a controlled transport tutorial, not real inference validation.
The [framework examples](../examples/README.md#framework-agent-benchmarks) retain
their existing explicit quality flow and disclosure requirements.
