# Examples

Start here for the public Python API. These scripts call an existing agent;
they do not start an EvalSurge server, implement polling, or manage credentials.
Only benchmark endpoints and agent actions you are authorized to exercise.

New integrations use one `RunCreate` request and direct execution by default:

| Example | Load-generator location | Agent target |
| --- | --- | --- |
| [local_runner_http_target.py](journeys/local_runner_http_target.py) | Local Python/laptop | Separately hosted real HTTP agent |
| [local_runner_databricks_app_target.py](journeys/local_runner_databricks_app_target.py) | Local Python/laptop | Already deployed Databricks App |
| [serverless_runner_databricks_app_target.py](journeys/serverless_runner_databricks_app_target.py) | Serverless notebook; prepared/authentication-blocked | Already deployed App; not yet live-validated from a notebook |
| [Classic notebook](journeys/classic_notebook.py) | Retained classic driver; deferred | Deployed App; not evidence of serverless support |
| [Dataset and judges](quality/README.md) | Caller selects the runner | Explicit catalog, reviewed custom alias, automatic, and readiness edges |

Install `evalsurge[server]`, then run a selected real target only after reviewing
the bound of five measured agent invocations plus one excluded probe (not a
model/tool-call or spend quota):

```bash
uv run python -m examples.journeys.local_runner_http_target \
  http://127.0.0.1:9001/invoke --allow-paid-inference
uv run python -m examples.journeys.local_runner_databricks_app_target \
  your-deployed-app --profile YOUR_SELECTED_OAUTH_PROFILE --allow-paid-inference
```

These scripts do not deploy targets, select a default profile, or substitute
fixture completions when a live target is unavailable. Static schema checks are
not a claim of end-to-end notebook/live coverage. The new serverless sample is
**prepared, authentication-blocked—not live-validated**. It runs only the load
generator, never an agent/helper in the notebook. Its initial budget is one
excluded probe plus one measured App invocation at concurrency one, evaluation
off; a reviewed no-tool App must enforce the declared <=512 output-token limit.
Driver/profile, independent-worker OAuth and deployed-App readiness must pass
before separately approved model traffic. See
[the notebook checklist](../scripts/validation/README.md#serverless-notebook-validation),
[the target guide](../docs/TARGETS.md) and
[actual validation](../VALIDATION.md).

## Sample classifications

Examples are customer implementations, not an EvalSurge framework allowlist.
Keep hosting and inference claims separate:

| Sample or harness | Hosting / execution | Inference and evidence boundary |
| --- | --- | --- |
| [real_framework_agent.py](real_framework_agent.py) | Real customer-process LangGraph, OpenAI Agents or CrewAI behind the optional JSON helper | Explicit real Responses model; no fixture fallback. Stateless/nonstreaming; no memory, traces or TTFT. CrewAI uses a separate reviewed environment |
| [local_runner_http_target.py](journeys/local_runner_http_target.py) | Laptop → already hosted HTTP endpoint | Calls the supplied endpoint; does not deploy or establish its framework/model by itself |
| [local_runner_databricks_app_target.py](journeys/local_runner_databricks_app_target.py) | Laptop → already deployed Databricks App | Exact App/profile selection; not a local stand-in for App hosting |
| [serverless_runner_databricks_app_target.py](journeys/serverless_runner_databricks_app_target.py) / [serverless_runner_app_target.py](../scripts/validation/serverless_runner_app_target.py) | Serverless EvalSurge/Locust runner → existing deployed App | Prepared/authentication-blocked. Zero-inference guards pass; no live notebook-to-App success, API execution, cancellation or fail-fast claim |
| [serverless_sdk_journeys.py](../scripts/validation/serverless_sdk_journeys.py) | Retained notebook-local helper diagnostic | Not the intended notebook-runner → deployed-App sample; it does not validate that journey and is not an additional agent-hosting option |
| [quality examples](quality/README.md) | Explicit/automatic evaluation over supplied cases and captured answers | Separate opt-in planner/judge budget; not exercised by the current load-only smokes |
| [framework_agent.py](framework_agent.py) / [mock_agent.py](mock_agent.py) | Retained instrumented demo / deterministic transport tutorial | Controlled inference paths are explicitly labeled; require disclosure/approval and never count as real-model validation |

Notebook validation is **serverless-only**; local-Python real-agent checks are a
separate runner journey. Use short functional smokes before any larger tests.
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
