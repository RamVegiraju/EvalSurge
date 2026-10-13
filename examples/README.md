# Examples

Start with the [local runner quickstart](journeys/LOCAL_RUNNER_QUICKSTART.md):
install EvalSurge, bind your existing agent, provide cases and load bounds, then
inspect a typed report. EvalSurge generates traffic on your machine; the agent
runs at its own HTTP endpoint or in an already deployed Databricks App.
No separate EvalSurge API server, operator TOML, notebook or runner App is needed
for this journey. Credentials stay in target configuration, outside `RunCreate`.

| Choose your agent target | Example | Where traffic originates |
| --- | --- | --- |
| Existing HTTP endpoint | [local_runner_http_target.py](journeys/local_runner_http_target.py) | Your local Python process and its Locust worker |
| Already deployed Databricks agent App | [local_runner_databricks_app_target.py](journeys/local_runner_databricks_app_target.py) | Your local Python process and its Locust worker |

Both scripts use the same cases, load and evaluation policy: five concurrent
users, at most five measured invocations, a ten-second dispatch window and one
excluded readiness probe. Evaluation defaults to off. These are short functional
smokes, not sustainable-capacity tests or model/token/spend quotas.

For independent profiling with evaluation off, use
[local_runner_traced_http_target.py](journeys/local_runner_traced_http_target.py).
It uses the same five-request bound but requires an existing instrumented agent,
exact tracking destination and authorized experiment. Its source/request/native
local-telemetry contracts are tested; this new journey has not yet received fresh
real-agent validation. Governed Databricks UC collection remains fail-closed, not
a demonstrated App tracing path. See [profiling setup](../docs/PROFILING_AND_EVALUATION.md).

For named tools and a deliberately slow step, use the
[multi-tool heatmap sample](journeys/multitool_heatmap/README.md): an actual serial
LangGraph workflow, three actual tools over disclosed synthetic documents,
one eligibility decision and a real model answer. Separate agent and runner
entrypoints keep tool work out of Locust. The four-measured-request workload
compares normal shipping with an injected two-second agent-side delay. Its
underlying real-model smoke and rendered report passed; the original async-export
probe remains failed, and browser visual verification remains unavailable.

Install the [reviewed wheel](../docs/INSTALLATION.md) with `[local]`; `[server]`
remains the compatible extra name and neither requires starting an API server.
The wheel does not include example source files. Copy either script into the
installed environment, review your exact target and six possible agent
invocations, then explicitly authorize traffic:

```bash
python local_runner_http_target.py \
  http://127.0.0.1:9001/invoke --allow-paid-inference
python local_runner_databricks_app_target.py \
  your-deployed-app --profile YOUR_SELECTED_OAUTH_PROFILE --allow-paid-inference
```

From a reviewed source checkout, the equivalent module commands are
`uv run --frozen --no-sync python -m examples.journeys.local_runner_http_target`
and `uv run --frozen --no-sync python -m examples.journeys.local_runner_databricks_app_target`,
with the same arguments. Framework implementation examples require their source
files and separately installed framework dependencies; `[agents]` installs the
LangGraph/OpenAI Agents dependencies, not those files.

These scripts do not deploy targets, select a default profile or substitute
fixture completions when a live target is unavailable. LangGraph, OpenAI Agents
and CrewAI are customer-agent examples, not a framework allowlist. The
[framework/hosting matrix](journeys/FRAMEWORK_MATRIX.md) keeps six local-runner
combinations explicit. No framework-specific EvalSurge setting is required when
an endpoint satisfies the documented contract.
Four reduced real-model basic smokes passed on October 12 against the reviewed
pip-installed `0.2.1.dev2026101202` wheel: LangGraph and OpenAI Agents, each hosted
over local HTTP or in an existing Databricks agent App. All used actual
`system.ai.gpt-oss-120b`, one excluded probe plus one measured invocation,
concurrency one and evaluation off, without fixtures. Typed retrieval and cleanup
passed; the two target Apps were stopped with resources/deployments preserved.
That is **4/6 basic cells**, not six passes, unchanged five-request sample coverage,
judging, active cancellation, accuracy certification or current-template deployment.
Runner-App installation/execution is a separate gate, not established by local
traffic to an App target. CrewAI's advisory and native deployment gates remain
unresolved. See [the retained live evidence](../docs/LIVE_MATRIX_RESULTS.md)
and [current demo readiness](../docs/DEMO_READINESS.md).

## Prepared and deferred runner options

These sources remain available separately from the local quickstart:

| Example | Load-generator location | Current boundary |
| --- | --- | --- |
| [Private direct runner App](journeys/app_runner/README.md) | Dedicated `load-test` App; separate from the agent App | Prepared, disabled; dependency installation and live execution remain unverified |
| [serverless_runner_http_target.py](journeys/serverless_runner_http_target.py) | Serverless notebook | Retained optional source, outside requested live scope |
| [serverless_runner_databricks_app_target.py](journeys/serverless_runner_databricks_app_target.py) | Serverless notebook | Deferred; historical authentication blocker retained |
| [Classic notebook](journeys/classic_notebook.py) | Classic notebook driver | Retained, deferred; not serverless evidence |
| [Dataset and judges](quality/README.md) | Your selected supported runner | Explicit, registered and automatic judging; readiness edges |

The runner-App template requires its own reviewed installation, resource binding,
private artifact export and fresh bounded-traffic approval. Its stopped diagnostic
deployment did not install or execute EvalSurge or make model calls. The managed
volume `ram_artifacts.evalsurge_validation.runner_artifacts` and grants were
provisioned, but do not establish a successful cloud benchmark. See
[the App-runner handoff](../docs/SESSION_HANDOFF.md) for exact retained state.
For a cloud runner, `localhost` is that cloud runtime, not your laptop; a local
HTTP agent needs a separately authorized reachable HTTPS origin. Samples create
no tunnel or network-permission changes. Notebook validation remains deferred.

## Sample classifications

Examples are customer implementations, not an EvalSurge framework allowlist.
Keep hosting and inference claims separate:

The [demo readiness matrix](../docs/DEMO_READINESS.md) ties these claims to the
current versioned artifact. The four fresh installed-runner basic-smoke receipts
are separate from example code and older historical validation. They establish
observed execution/completeness, not calibrated accuracy of the measurement implementation.

| Sample or harness | Hosting / execution | Inference and evidence boundary |
| --- | --- | --- |
| [real_framework_agent.py](real_framework_agent.py) | Real customer-process agent behind the optional EvalSurge JSON helper | Explicit real Responses model; no fixture fallback. The observed CrewAI candidate cannot share this helper's dependency stack; use the standalone endpoint below. No memory, traces or TTFT |
| [real_framework_handler.py](real_framework_handler.py) | Shared customer-owned model/handler source, not a runner or server | Standard-library import boundary; optional real framework imports at construction. Does not make an incompatible environment compatible or establish inference |
| [crewai_agent.py](crewai_agent.py) | Standalone loopback CrewAI HTTP agent, in its own environment | Isolated dependency install/check passed; ChromaDB advisory gate failed, so no actual-model inference. See the [prerequisite record](journeys/agent_apps/crewai/README.md) |
| [native agent-App projects](journeys/agent_apps/README.md) | Separate LangGraph/OpenAI Agents/CrewAI agent Apps, not the runner App | Prepared DurableAgentServer source; dependencies, supported deployment/Runtime Store provisioning and actual inference remain separate gates. No fresh live deployment evidence |
| [local_runner_http_target.py](journeys/local_runner_http_target.py) | Laptop → already hosted HTTP endpoint | Calls the supplied endpoint; does not deploy or establish its framework/model by itself |
| [multi-tool heatmap](journeys/multitool_heatmap/README.md) | Local Python runner → separate loopback HTTP LangGraph agent | Real model plus three actual tools over synthetic files; deliberate shipping delay and sample-only synchronous local trace export. Public-file checks are offline, not new live inference |
| [local_runner_databricks_app_target.py](journeys/local_runner_databricks_app_target.py) | Laptop → already deployed Databricks App | Exact App/profile selection; not a local stand-in for App hosting |
| [Private direct runner App](journeys/app_runner/README.md) | Dedicated `load-test` App → separate HTTP/App agent | Prepared; disabled installation failed and stopped diagnostic remains. EvalSurge startup, live native worker OAuth, protected export and actual-model traffic remain unverified |
| [serverless_runner_databricks_app_target.py](journeys/serverless_runner_databricks_app_target.py) / [serverless_runner_app_target.py](../scripts/validation/serverless_runner_app_target.py) | Deferred serverless EvalSurge/Locust runner → existing deployed App | Historical authentication blocker retained; zero-inference guards do not establish notebook-to-App success |
| [serverless_sdk_journeys.py](../scripts/validation/serverless_sdk_journeys.py) | Retained notebook-local helper diagnostic | Not the intended notebook-runner → deployed-App sample; it does not validate that journey and is not an additional agent-hosting option |
| [quality examples](quality/README.md) | Explicit/automatic evaluation over supplied cases and captured answers | Separate opt-in planner/judge budget; not exercised by the current load-only smokes |
| [framework_agent.py](framework_agent.py) / [mock_agent.py](mock_agent.py) | Retained instrumented demo / deterministic transport tutorial | Controlled inference paths are explicitly labeled; require disclosure/approval and never count as real-model validation |

The primary quickstart uses a **local-Python runner** for either target hosting
choice. Dedicated-App runner installation is separately gated; notebook
validation is **deferred**. Use short functional smokes before any larger tests.
The notebook-to-App authentication blocker, approved App names and exact pass/failure
records are in [hosted journey validation](../docs/HOSTED_JOURNEY_VALIDATION.md).
An approved name or a successful local run is not evidence that an App was deployed.
The older [direct_http.py](journeys/direct_http.py) and
[direct_app.py](journeys/direct_app.py) names remain compatibility examples;
their original ten-request bounds differ from the new five-request smokes.

For optional REST, CLI, and remote SDK examples of each framework under both
hosting options, use [the four-target guide](../docs/FRAMEWORK_TARGET_EXAMPLES.md),
[JSON request files](requests/local-langgraph.json), and [operator TOML](requests/operator.toml).
The following older scripts remain compatibility examples:

| Example | Purpose |
| --- | --- |
| [python_benchmark.py](python_benchmark.py) | Credential-free mock quickstart: performance-only load and a JSON report. |
| [langgraph_benchmark.py](langgraph_benchmark.py) | LangGraph agent: load plus explicit relevance/correctness evaluation. |
| [openai_agents_benchmark.py](openai_agents_benchmark.py) | OpenAI Agents agent: load plus explicit relevance/correctness evaluation. |

## Credential-free mock quickstart

This mock is a controlled transport tutorial, not actual agent/LLM validation.
Before running controlled tests or CI, disclose the provider boundary and obtain
approval under [the engineering policy](../AGENTS.md). From the checkout, after
[installation](../README.md#start-in-python), start the
deterministic sample agent in one terminal:

```bash
uv run --no-sync uvicorn examples.mock_agent:app --host 127.0.0.1 --port 9001 --no-proxy-headers
```

In another terminal:

```bash
uv run --no-sync python -m examples.python_benchmark
```

Edit `Agent.http(...)`, `cases`, and `Load(...)` directly for your own agent.
Set `protocol="http-json"` for the [supported JSON contract](../docs/PYTHON_API.md#protocol-and-connection).
No model calls are made by the mock; your own agent may execute tools or incur costs.
The library handles preflight, load, persistence, and report generation.

The script uses five concurrent users, a three-minute dispatch window, and at
most 10,000 measured requests. It prints the report JSON, including `run.id`, `run.metrics`, and
`run.evaluation`. Runs are retained under `artifacts/python-benchmark/`.
Duration limits dispatch; the request cap can end it sooner. Startup, readiness,
drain, profiling, and judging add time. A failed preflight raises `RunFailed`
with its report, instead of silently starting load.

## Framework agent benchmarks

These are small public Python requests against the instrumented agents in
[framework_agent.py](framework_agent.py), not standalone agent implementations.
Both use `EvalSurge.local()`, two concurrent users, a ten-second dispatch window,
at most ten measured requests, authoritative refund-policy references, and explicit
`relevance`/`correctness` judges. Each judge scores at most five measured answers;
neither script calls a planner.

Stop the mock if it occupies port 9001, then start the framework server:

```bash
EVALSURGE_DEMO_LIVE=false MLFLOW_MODEL_CATALOG_URI='' \
  uv run --no-sync python -m examples.framework_agent
```

The command above explicitly selects controlled model responses. It serves real
LangGraph and OpenAI Agents with synthetic tools, isolated
memory, and MLflow instrumentation. Its model responses are fixtures by default;
the command does not opt in to live model inference.

Before running either benchmark, configure the authorized judge model/workspace
and tracking settings in the benchmark process's environment as described in the
[integration guide](../docs/PROFILING_AND_EVALUATION.md). The scripts do not load
`.env`, select a profile, or manage credentials. Catalog judging currently
requires Databricks and explicit workspace configuration. **Configured judge
calls can incur costs even when the agent's model responses are fixtures.**

Run one benchmark at a time in another terminal:

```bash
uv run --no-sync python -m examples.langgraph_benchmark
uv run --no-sync python -m examples.openai_agents_benchmark
```

| Benchmark | Existing agent endpoint | Artifact directory |
| --- | --- | --- |
| LangGraph | `http://127.0.0.1:9001/langgraph/chat` | `artifacts/langgraph-benchmark/` |
| OpenAI Agents | `http://127.0.0.1:9001/openai-agents/chat` | `artifacts/openai-agents-benchmark/` |

Both print combined `RunReport` JSON with load metrics and evaluation results.
MLflow may print evaluation progress first. Configure authorized trace collection
against the agent's tracking store and experiment for internal heatmaps; agent
instrumentation alone does not enable the runner's trace collection.
Judging reuses captured answers, not new agent invocations. Each selected judge
also checks the excluded first answer for readiness. References are your ground
truth, not automatically generated answers. Failed configuration or readiness
stops load; a completed evaluation is not necessarily a passing quality verdict.
Protect reports and artifacts: they can contain prompts, answers, and rationales.

Local tests exercise actual framework runners, Locust, and native MLflow with
controlled provider boundaries. That is not paid/live validation, model-quality
calibration, or sustainable-capacity evidence. Existing controlled inference
tests/CI need explicit disclosure and approval before execution. For live
validation select an exact authorized profile and bounded traffic; missing auth
or deployment is a blocker, not permission to substitute fixtures.

## Supporting agents and advanced tooling

- [mock_agent.py](mock_agent.py): small deterministic SSE target, no model credentials.
- [framework_agent.py](framework_agent.py): instrumented LangGraph/OpenAI Agents demo with tools and memory; its implementation is intentionally more involved.
- [real_framework_agent.py](real_framework_agent.py): native LangGraph/OpenAI Agents/CrewAI handlers for the generic JSON helper, with explicit real Responses API selection and no fixture path. See the exact live receipts rather than inferring successful inference from configuration checks; CrewAI requires a separately reviewed installation. This stateless sample emits no trace evidence or TTFT.
- [Python guide](../docs/PYTHON_API.md): authentication, async usage, protocols, and opening the report UI.
- [Validation tools](../scripts/validation/README.md): advanced CLI flags, remote REST polling, and opt-in framework/provider integration checks.
