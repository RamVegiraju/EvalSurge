# EvalSurge

Framework-agnostic load testing and evaluation for hosted agents.

**Bring your agent. Give us an endpoint and test cases. EvalSurge measures its
performance under load and evaluates its captured answers when you enable judging.**

Use any agent framework or your own implementation. The integration boundary is
the hosted endpoint's input/answer contract, not the framework inside it. Run
directly from Python; an EvalSurge API server is optional.

- Performance: latency, throughput, errors, and answer-text TTFT for supported SSE.
- Evaluation: opt-in catalog or reviewed MLflow judges, with per-judge coverage.
- Profiling: heatmaps and waterfalls when the agent exports correlated MLflow traces.

Local alpha: Linux/macOS, single tenant, one active run per artifact owner. A single
load level is an observation, not proof of sustainable capacity.

## Bring your agent

You do **not** need to know your agent's supported concurrency before testing.
Concurrency is the number of simultaneous clients you want EvalSurge to try.
Start small, inspect latency/errors, and increase the bounded load deliberately.
Automatic capacity discovery is not implemented yet.

- **Your HTTP server:** expose a reachable POST endpoint that accepts your case
  input as JSON and returns `{"outputs": "the completed answer"}`. Use
  `protocol="http-json"`; existing compatible streaming endpoints are also supported.
- **Your Databricks App:** deploy with DurableAgentServer and bind the App name
  and an explicitly selected OAuth profile. EvalSurge handles discovery and authentication.
- **Evaluation:** inputs and captured answers are enough for answer-based judges;
  correctness also needs your references. Internal traces are optional, not a
  prerequisite for all evaluation.

Follow the [end-to-end hosted-agent recipe](docs/AGENT_INTEGRATION.md) for any
framework. It shows the thin server wrapper, shared benchmark request, optional
judging, and trace requirements. LangGraph, OpenAI Agents and CrewAI are examples,
not a framework allowlist; another framework needs no new EvalSurge adapter if
its endpoint already satisfies the same contract.
EvalSurge does not import a graph, deploy your agent, or automatically instrument
its internals. Keep endpoint/provider credentials outside the benchmark request.
If you do not already have a compatible endpoint, the optional
[`evalsurge.serving` helper](docs/AGENT_INTEGRATION.md) calls your own async handler
inside the agent process. It preserves JSON inputs, validates completed answers,
and passes correlation/state keys. Choose isolation explicitly; authentication,
agent memory and trace instrumentation remain yours. Existing compatible
endpoints need no wrapper.

## Start in Python

Requires Python 3.11+ and an authorized agent that already uses a real model.
Install the execution dependencies in your project:

```bash
uv add 'evalsurge[server]'
```

No EvalSurge server, operator TOML, or REST polling is needed:

```python
from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference

request = RunCreate(
    name="first-benchmark",
    target=TargetReference(connection_id="agent"),
    cases=[Case(input={"query": "Give a short greeting."})],
    load=Load(concurrency=2, duration_seconds=10, max_requests=10),
)

with EvalSurge(
    artifact_dir="artifacts/first-benchmark",
    targets={"agent": Agent.http("http://127.0.0.1:9001/invoke", protocol="http-json")},
) as client:
    run = client.start(request)
    report = run.wait(timeout=300)
    print(report.model_dump_json(indent=2))
```

Evaluation defaults to off: no planner or judge calls. The agent itself can incur
cost and execute tools. Before measured load, one extra first-case invocation
checks readiness. It is excluded from the metrics; failure stops load. The request
cap can end dispatch before ten seconds. Startup, preflight, drain, and optional
profiling/judging add time.

The HTTP example sends `{"query": "Give a short greeting."}` unchanged and expects
`application/json` with a nonempty `outputs` string. It does not provide TTFT.
If your existing endpoint speaks streaming Chat Completions, explicitly use
`protocol="openai-chat"` instead. See [supported target protocols](docs/TARGETS.md#supported-wire-contracts)
and [the local-runner HTTP-target script](examples/journeys/local_runner_http_target.py).

Inspect `report.run.evidence` for separate load, captured-answer evaluation,
internal profiling and trace-aware evaluation states. Configured is not observed;
missing optional traces do not prevent ordinary answer judging. A completed
assessment can still have a false verdict. See
[evidence and readiness](docs/EVIDENCE_CAPABILITIES.md).

## Target a Databricks App

Keep App identity and the explicitly selected OAuth profile in target
configuration, outside the benchmark request. Use the same `request` as above:

```python
with EvalSurge(
    artifact_dir="artifacts/app-benchmark",
    targets={
        "agent": Agent.databricks_app("your-deployed-app", profile="YOUR_SELECTED_OAUTH_PROFILE")
    },
) as client:
    report = client.start(request).wait(timeout=300)
    print(report.model_dump_json(indent=2))
```

The default is DurableAgentServer's synchronous `/api/invocations` contract.
EvalSurge resolves the App through the selected Databricks SDK
profile and refreshes OAuth; it does not deploy the agent, provision Lakebase,
negotiate protocols, or retry model requests. Native invocation JSON does not
provide answer-text TTFT or token usage. See [the local-runner App-target script](examples/journeys/local_runner_databricks_app_target.py)
and [framework/hosting examples](docs/FRAMEWORK_TARGET_EXAMPLES.md).

## From a Databricks notebook

**Prepared, authentication-blocked—not live-validated.** The
[runner-only serverless notebook sample](examples/journeys/serverless_runner_databricks_app_target.py)
is available for review and dry-run planning. Do not submit its model-bearing Job
until the supported operator-owned authentication design and deployed-App
readiness have been reviewed.

Notebook compute is a **load-generator location**, not another agent-hosting
option. The intended serverless journey runs EvalSurge/Locust on the notebook
driver and sends traffic to an already deployed App; it does not host an agent
inside that notebook. The same v2 cases/load/evaluation vocabulary applies.
Classic compute is deferred from the current validation. The retained
[classic source](examples/journeys/classic_notebook.py) is not a serverless pass.

Authentication must work both for App discovery and in the spawned load worker.
A profile on your laptop is not automatically present in a notebook, and notebook
driver OAuth alone does not establish worker authentication. The current public
App binding requires an explicit profile and rejects contradictory ambient
identity/destination settings. Native notebook OAuth is unavailable to the
independent worker in the retained serverless prerequisite check. No token is
copied into sample source, workload JSON or Job parameters to bypass either gate.
See [the serverless/API topology diagnosis](docs/SERVERLESS_RUNNER_STATUS.md)
for what failed and the reviewed authentication work still needed.

The initial notebook sample is bounded to **one excluded probe plus one measured
App invocation**, concurrency one, with evaluation off. Select an already deployed,
ready no-tool agent whose reviewed source enforces at most 512 output tokens per
model response. App invocations are not a generic model/tool-call or spending cap.
Driver/profile readiness, independent worker OAuth, deployed App readiness and
explicit traffic approval are all required; optional API execution, fail-fast and
cancellation need separate validation. See [the notebook validation checklist](scripts/validation/README.md#serverless-notebook-validation).

The samples' static contract coverage is not evidence that all notebook/hosting
combinations passed live validation. Consult
[the validation record](VALIDATION.md) for actual model, hosting, and traffic bounds.
The [hosted-journey matrix](docs/HOSTED_JOURNEY_VALIDATION.md) lists current
resources, retained failures and the bounded next live-validation plan.
The retained October 8 notebook-local HTTP/API run failed without a final receipt;
later zero-inference prerequisites confirmed driver OAuth but failed independent
worker OAuth. These are distinct from notebook-to-App validation. Current journey
results and blockers are kept in the hosted-journey record, not inferred from an
example's presence.

## Where requests originate

Direct Python sends benchmark traffic from the Python caller's machine: your
laptop, or the notebook driver. Optional remote SDK/REST execution sends traffic
from the EvalSurge API host, not the submitting laptop. Thus `127.0.0.1` means
the runner's loopback. Network location and runner resources affect the result.
Use a runner separate from the target for repeatable measurements.

## Add your dataset and judges

Use `Case(input=..., reference=...)` or load your own JSON dataset into `cases`.
References are your authoritative facts, not answers generated by the planner:

```python
from evalsurge import EvaluationPolicy

judged = request.model_copy(
    update={
        "cases": [
            Case(
                input={"query": "Can an opened item be refunded?"},
                reference={"expected_facts": ["Opened items cannot be refunded."]},
            )
        ],
        "evaluation": EvaluationPolicy(
            mode="explicit",
            description="Apply the stated refund policy faithfully.",
            scorers=["relevance", "correctness"],
            max_scored_requests=5,
        ),
    }
)
```

Configure the catalog judge provider separately before submitting this request.
For automatic selection, use `EvaluationPolicy(mode="automatic", description=...)`
without scorer IDs. The planner selects from supported criteria and approved
registered aliases; it cannot invent ground truth or judge code. You can also
select your already reviewed, operator-registered judge as `registered:policy`.
See [copyable dataset, explicit, custom, automatic, and edge-case samples](examples/quality/README.md).

Judging reuses captured answers, never invokes the agent again. Each selected
judge also performs an extra excluded readiness assessment. `max_scored_requests`
is a sample budget per judge, not a dollar/token/retry cap.

For internal waterfalls or judges that inspect tools/retrieval/memory, export
correlated MLflow traces from the agent and configure authorized tracking access
in EvalSurge. A protocol, framework name, App Runtime Store, or returned trace ID
alone does not supply internal traces. Missing trace coverage is reported, not inferred.
See [the optional tracing recipe](docs/AGENT_INTEGRATION.md#optional-internal-tracing).

## Read the report

Both direct and typed remote run handles expose `status()`, `result()`, `report()`,
`wait()`, and `cancel()`. Results separate load completion, quality outcomes, and
evidence gaps. A completed run can have failed quality assessments; missing
TTFT/traces remain unknown. See [reports and judges](docs/REPORTS_AND_JUDGES.md)
for the generated structure and browser sections.

The Python API returns typed data, not a running report web server. If you want
the browser report, close the direct client and then serve its retained artifact
directory using [the optional server guide](docs/OPTIONAL_SERVER.md#open-a-retained-report).
Reports can contain prompts, answers, references, and judge rationales; protect them.

Client timings include transport and load-generator effects. Local diagnostics
found small native journal costs, but blocking journal I/O can delay other users;
zero overhead and cloud/serverless disk behavior are not established. See
[measurement accuracy and its limits](docs/MEASUREMENT_ACCURACY.md).

## Optional server and compatibility

Use [optional server execution](docs/OPTIONAL_SERVER.md) to move the runner off
your laptop. `EvalSurge.remote(url, typed=True).start(request)` accepts the same
v2 model; the server owns target registration and credentials. The base
`evalsurge` install remains a lightweight remote client/CLI.

Existing `/v1`, `EvalSurge.local().start(agent=..., cases=..., ...)`, and dictionary
remote SDK calls remain compatibility interfaces. The legacy [credential-free
mock tutorial](examples/README.md#credential-free-mock-quickstart) is retained and
explicitly does not validate real model inference.
Existing MLflow AgentServer `/responses` bindings remain
[advanced compatibility](docs/TARGETS.md#legacy-protocol-compatibility), not the
recommended Databricks deployment path.

## Documentation

- [Python request, lifecycle, auth, and compatibility](docs/PYTHON_API.md)
- [Bring any agent framework: end-to-end](docs/AGENT_INTEGRATION.md)
- [Framework/hosting examples](docs/FRAMEWORK_TARGET_EXAMPLES.md) · [Examples index](examples/README.md)
- [v2 REST and CLI](docs/V2_API.md) · [Optional server](docs/OPTIONAL_SERVER.md)
- [Traces, registered judges, and evidence](docs/PROFILING_AND_EVALUATION.md)
- [Architecture](ARCHITECTURE.md) · [Validation](VALIDATION.md)
- [Measurement accuracy and observer effects](docs/MEASUREMENT_ACCURACY.md)
- [Dependencies](docs/DEPENDENCIES.md) · [Security](SECURITY.md) · [Production gates](docs/PRODUCTION_READINESS.md)

See [CONTRIBUTING.md](CONTRIBUTING.md) for development checks and inference disclosure.
Licensed under [MIT](LICENSE).
