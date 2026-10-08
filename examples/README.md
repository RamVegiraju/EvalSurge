# Examples

Start here for the public Python API. These scripts call an existing agent;
they do not start an EvalSurge server, implement polling, or manage credentials.
Only benchmark endpoints and agent actions you are authorized to exercise.

These examples use runner-local HTTP agents. Databricks Apps are also supported
through registered targets in `/v2`; see [the target guide](../docs/TARGETS.md).
The local Python interface has no App-specific convenience factory.
For REST, CLI, and remote SDK examples of each framework under both hosting
options, use [the four-target guide](../docs/FRAMEWORK_TARGET_EXAMPLES.md) and its
[JSON request files](requests/local-langgraph.json) / [operator TOML](requests/operator.toml).

| Example | Purpose |
| --- | --- |
| [python_benchmark.py](python_benchmark.py) | Credential-free mock quickstart: performance-only load and a JSON report. |
| [langgraph_benchmark.py](langgraph_benchmark.py) | LangGraph agent: load plus explicit relevance/correctness evaluation. |
| [openai_agents_benchmark.py](openai_agents_benchmark.py) | OpenAI Agents agent: load plus explicit relevance/correctness evaluation. |

## Credential-free mock quickstart

From the checkout, after [installation](../README.md#credential-free-quickstart-legacy-v1), start the
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

This serves real LangGraph and OpenAI Agents with synthetic tools, isolated
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
calibration, or sustainable-capacity evidence.

## Supporting agents and advanced tooling

- [mock_agent.py](mock_agent.py): small deterministic SSE target, no model credentials.
- [framework_agent.py](framework_agent.py): instrumented LangGraph/OpenAI Agents demo with tools and memory; its implementation is intentionally more involved.
- [Python guide](../docs/PYTHON_API.md): authentication, async usage, protocols, and opening the report UI.
- [Validation tools](../scripts/validation/README.md): advanced CLI flags, remote REST polling, and opt-in framework/provider integration checks.
