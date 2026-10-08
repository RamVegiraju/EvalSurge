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
and [the streaming HTTP script](examples/journeys/direct_http.py).

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
provide answer-text TTFT or token usage. See [the App script](examples/journeys/direct_app.py)
and [framework/hosting examples](docs/FRAMEWORK_TARGET_EXAMPLES.md).

## From a Databricks notebook

Use the same Python request and App binding on the notebook driver. Start with
classic compute; serverless validation is separate. The [notebook source
example](examples/journeys/classic_notebook.py) is consent-gated and includes
context-managed cleanup. Configure an explicitly selected OAuth profile on the
driver first; a profile on your laptop is not automatically present in a notebook.
App access and the spawned worker's authentication must both be verified.

These new journey samples have static contract coverage; their presence is not
evidence that all notebook/hosting combinations passed live validation. Consult
[the validation record](VALIDATION.md) for actual model, hosting, and traffic bounds.
The October 8 serverless HTTP/API validation failed without a final receipt;
notebook-to-App worker authentication and current deployed-App journeys remain
unverified. The notebook example is not a supported-serverless claim.

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
- [Dependencies](docs/DEPENDENCIES.md) · [Security](SECURITY.md) · [Production gates](docs/PRODUCTION_READINESS.md)

See [CONTRIBUTING.md](CONTRIBUTING.md) for development checks and inference disclosure.
Licensed under [MIT](LICENSE).
