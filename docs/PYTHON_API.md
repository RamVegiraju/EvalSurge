# Python API: direct execution first

Install the [reviewed wheel](INSTALLATION.md) with `[server]` for direct execution;
`[agents]` additionally installs LangGraph and OpenAI Agents dependencies for the
repository demos, not the example source files. The base package
contains lightweight remote SDK/CLI dependencies. Public request/result models
are available from `evalsurge` without loading the execution stack.

## One request, two targets

```python
from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference, format_summary

request = RunCreate(
    name="baseline",
    target=TargetReference(connection_id="agent"),
    cases=[Case(input={"query": "Give a short greeting."})],
    load=Load(concurrency=2, duration_seconds=10, max_requests=10),
)

agent = Agent.http("http://127.0.0.1:9001/invoke", protocol="http-json")
# Instead, for an already deployed DurableAgentServer App:
# agent = Agent.databricks_app("your-app", profile="YOUR_SELECTED_OAUTH_PROFILE")

with EvalSurge(artifact_dir="artifacts/baseline", targets={"agent": agent}) as client:
    run = client.start(request, idempotency_key="baseline-1")
    report = run.wait(timeout=300)
    print(format_summary(report))
```

`EvalSurge(...)` is direct execution; `EvalSurge.local(...)` is its explicit alias.
The HTTP endpoint above uses the [framework-neutral JSON contract](AGENT_INTEGRATION.md):
it accepts `{"query": "..."}` and returns `{"outputs": "completed answer"}`.
For an existing OpenAI Chat Completions endpoint, explicitly select
`protocol="openai-chat"`; the constructor's legacy default remains compatible.
The caller owns target settings and the artifact directory. The request contains
only an alias, cases, load, and evaluation policy. No server is started.
`start()` also accepts finite JSON-compatible mappings through the same schema.
Both modes apply the same eight-million-byte UTF-8 limit without ASCII-escaping
Unicode. Raw mappings cannot contain Python-only values such as `datetime`; a
validated `RunCreate` uses its public Pydantic JSON serialization in both modes.
Unknown fields and invalid values receive bounded field-specific guidance.

`format_summary(run.result())` and `format_summary(run.report())` use the same
content-free renderer as the CLI: lifecycle, independent phase/quality outcomes,
metrics, coverage and generator limitations. A completed lifecycle is not a
passing quality check. Inspect typed fields explicitly for detailed evidence;
`model_dump_json()` is a protected export that may include prompts, answers and
judge rationales, not the default presentation.

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

For a private Databricks App that **generates load**, native operator authentication
is an explicit alternative, not a fallback from a failed profile:

```python
agent = Agent.databricks_app(
    "your-agent-app",
    auth="app-runtime",
    workspace="https://your-workspace.cloud.databricks.com",
    runner_app="your-runner-app",
    client_id="00000000-0000-0000-0000-000000000000",  # Actual runner SP client UUID.
)
```

Replace every identity placeholder and omit `profile`. The runner App must declare
the separate target App resource with `CAN_USE`. The expected client ID is its
`service_principal_client_id`, not the numeric principal or App OAuth audience ID.
Both actual/scoped native environment selectors must agree before SDK use; explicit
M2M providers independently refresh in each Locust worker. No user/notebook token or
profile file is copied. These identity selectors remain outside `RunCreate` and
do not change hosting/protocol selection or the load engine. See
[the private App runner](../examples/journeys/app_runner/README.md) and [ADR 0019](adr/0019-explicit-native-app-runner-authentication.md).
This implemented path has controlled SDK-boundary checks, not live deployment or
measurement evidence. It is the current dedicated-App runner path; the selected
`load-test` shell is stopped and undeployed, and protected export still needs an
exact private schema/volume within `ram_artifacts`. Native App mode does not solve
serverless notebook auth; notebook validation is deferred from this milestone.

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

## Retained Databricks notebook path — deferred

**Deferred by user October 11, 2026; historically authentication-blocked, not
live-validated.** The active installation/load-generation choices are local
Python and the [dedicated runner App](../examples/journeys/app_runner/README.md).
No notebook credential is required for this milestone. Historical failures and
source remain preserved; the following describes the deferred path, not current
onboarding or an execution approval. Review
[the serverless runner-only source notebook](../examples/journeys/serverless_runner_databricks_app_target.py)
and its [readiness harness](../scripts/validation/serverless_runner_app_target.py).
Their availability does not establish supported live notebook-to-App execution.

The notebook is the EvalSurge/Locust **load generator**; the target agent remains
in its deployed Databricks App. This is a runner-location choice, not an additional
agent-hosting option. Use the same public `RunCreate` request and context cleanup
as a laptop run. The former notebook scope was serverless only; the retained
[classic notebook source](../examples/journeys/classic_notebook.py) is deferred.
A laptop profile is not notebook authentication, and driver-only credential
success is not evidence the spawned worker can authenticate.
The sample now offers a reviewed portable-M2M launcher using an already provisioned
private profile file and explicitly selected service-principal client ID. Each
owned process refreshes OAuth independently; the sample does not create credentials
or copy notebook tokens. This path remains unvalidated live until the operator
selects the credential source/permissions and bounded traffic. See proposed ADR 0015.
The installed package provides `evalsurge.serverless`; the source notebook imports
that helper without a repository checkout or validation-script import. Its repaired
post-authentication execution branch has offline regression coverage, not a live
serverless authentication or benchmark pass.
The [serverless runner status](SERVERLESS_RUNNER_STATUS.md) explains why hosting
FastAPI in the notebook does not repair worker OAuth, and why calling an external
API instead changes the load-generator location.

For the notebook journey, `Agent.databricks_app` still requires the selected
portable profile; native App mode is not notebook auth and accepts no injected
native notebook SDK client. Profile resolution rejects ambient
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

If notebook validation is resumed, it has separate gates: subprocess execution,
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
    print(format_summary(report))
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
Native local async execution remains `EvalSurge.local_async(...)`. The retained,
deferred serverless runner-only notebook uses this context with top-level `await`; the
retained synchronous examples do not establish notebook authentication support.

### Three-minute example

The retained [legacy Python sample](../examples/python_benchmark.py) runs a
credential-free mock at concurrency five for at most 180 seconds/10,000 measured
requests. It is a controlled transport tutorial, not real inference validation.
The [framework examples](../examples/README.md#framework-agent-benchmarks) retain
their existing explicit quality flow and disclosure requirements.
