# Run EvalSurge locally against your hosted agent

Install EvalSurge on your laptop or another approved Linux/macOS machine. Choose
one target: an existing HTTP endpoint or an already deployed Databricks agent App.
Traffic originates on the machine running this Python code; the target performs
the agent's model calls. No EvalSurge API server, notebook or runner App is needed.

LangGraph, OpenAI Agents and CrewAI are examples of agents you can bring, not an
EvalSurge framework allowlist. An already compatible endpoint needs no wrapper or
framework-specific runner configuration.

## 1. Install the runner

Use Python 3.11+ and the reviewed wheel you actually received. Public publication
is not verified. This command illustrates the current source build; receiving a
wheel and importing it do not establish live target validation:

```bash
python3 -m venv .venv-runner
source .venv-runner/bin/activate
python -m pip install './evalsurge-0.2.1.dev2026101203-py3-none-any.whl[local]'
python -c 'from evalsurge import Agent, EvalSurge, RunCreate, format_summary; print("Local SDK imports available")'
```

`[local]` supplies the direct-execution dependencies. `[server]` remains a
compatible name for that stack; neither requires starting an API server. The
agent's framework dependencies belong in its own environment. See
[installation and artifact-verification boundaries](../../docs/INSTALLATION.md)
for the `uv` alternative.

## 2. Bind one target

For an existing HTTP agent, use its exact endpoint and serving contract:

```python
from evalsurge import Agent

target = Agent.http("http://127.0.0.1:9001/invoke", protocol="http-json")
```

For `http-json`, EvalSurge sends your `Case.input` unchanged as the POST body and
expects JSON with a nonempty completed answer, for example
`{"outputs": "Opened items cannot be refunded."}`. This nonstreaming contract
does not provide TTFT. Choose an explicit supported adapter for other compatible
endpoints; see [the endpoint contract](../../docs/AGENT_INTEGRATION.md).
The sample agent binds loopback only. To use an authenticated HTTPS endpoint,
bind an operator-owned credential separately using the
[HTTP runner's `--bearer-token-env` option](local_runner_http_target.py), never a
token in the benchmark request or command argument.

For an already deployed Databricks agent App, replace the HTTP binding:

```python
from evalsurge import Agent

target = Agent.databricks_app(
    "YOUR_ALREADY_DEPLOYED_AGENT_APP",
    profile="YOUR_EXPLICIT_OAUTH_PROFILE",
)
```

Select a profile authorized for that exact workspace/App; no default profile is
chosen. The default adapter uses DurableAgentServer's synchronous
`/api/invocations` contract. Discovery and refreshable authentication stay in the
target binding, not the request. EvalSurge does not deploy the App, provision its
store, configure agent memory or switch serving protocols automatically.
For another supported App protocol, select it explicitly as documented in
[the target guide](../../docs/TARGETS.md).

## 3. Run the same small benchmark

After reviewing the target, dataset and traffic, save your chosen binding and this
code in `benchmark.py`. Replace the sample question with an input your agent
accepts. The consent guard starts false deliberately:

```python
from evalsurge import Case, EvalSurge, Load, RunCreate, TargetReference, format_summary

request = RunCreate(
    name="first-hosted-agent-smoke",
    target=TargetReference(connection_id="agent"),
    cases=[Case(input={"query": "Can an opened item be refunded?"})],
    load=Load(concurrency=5, duration_seconds=10, max_requests=5, timeout_seconds=40),
)

ALLOW_REAL_INFERENCE = False
if not ALLOW_REAL_INFERENCE:
    raise RuntimeError("Review this exact target and six possible agent invocations first")

with EvalSurge(artifact_dir="artifacts/first-smoke", targets={"agent": target}) as client:
    report = client.start(request).wait(timeout=300)
    print(format_summary(report))
```

Once you explicitly approve the bound, change the guard and run
`python benchmark.py` in the activated runner environment. There are at
most five measured agent invocations plus one excluded first-case readiness probe.
Probe failure stops before measured load. A ten-second dispatch window is not a
total-runtime deadline: setup, preflight and drain add time, and the request cap
can end dispatch sooner. One agent invocation can make multiple model/tool calls;
these bounds are not a token or spend quota.

The ready-made scripts use this same request without requiring copied Python:
copy [the HTTP script](local_runner_http_target.py) or
[the App script](local_runner_databricks_app_target.py) from the reviewed source
into your runner directory. Examples are not installed by the wheel. Then run
one explicitly selected target:

```bash
python local_runner_http_target.py \
  http://127.0.0.1:9001/invoke --allow-paid-inference
python local_runner_databricks_app_target.py \
  YOUR_ALREADY_DEPLOYED_AGENT_APP --profile YOUR_EXPLICIT_OAUTH_PROFILE --allow-paid-inference
```

## 4. Inspect the report; opt in to judging separately

`format_summary(report)` displays lifecycle, latency observations, throughput,
errors, quality coverage and generator limits without printing prompts/answers.
The typed `Report` retains detailed evidence; full JSON can contain sensitive
inputs, answers and judge rationales. Keep artifacts private.

Evaluation defaults to off: these smokes make no planner or judge calls. For
answer-based judging, use your cases, captured answers and authoritative
references. No agent reinvocation is performed during judging. Explicit catalog
judges, reviewed custom aliases and automatic planning are illustrated in
[the dataset/judge examples](../quality/README.md). Judge provider configuration
is separate from the agent's model configuration. Answer-only judges need no
tracing; trace-aware judges require their internal evidence. If you separately
enable internal profiling, correlated trace readiness is required even with
evaluation off; see [the profiling guide](../../docs/PROFILING_AND_EVALUATION.md).

Completion is not a passing quality verdict. Five requests also do not establish
sustainable capacity or zero generator overhead. Check timing coverage, error
rate and generator evidence together; see [measurement definitions](../../docs/MEASUREMENT_ACCURACY.md).

## Need a real sample agent first?

Keep the sample agent process/environment separate from the runner. Copy
[real_framework_agent.py](../real_framework_agent.py) and
[real_framework_handler.py](../real_framework_handler.py) into the same directory.
For LangGraph or OpenAI Agents, the compatible example dependencies can be installed
from the reviewed wheel into a separate agent environment:

```bash
python3 -m venv .venv-agent
.venv-agent/bin/python -m pip install './evalsurge-0.2.1.dev2026101203-py3-none-any.whl[agents]'
.venv-agent/bin/python real_framework_agent.py \
  --framework langgraph --profile YOUR_EXPLICIT_PROFILE \
  --workspace-host https://YOUR_WORKSPACE.cloud.databricks.com \
  --model YOUR_APPROVED_MODEL --api mlflow-responses --port 9001 \
  --live --accept-paid-traffic
```

For OpenAI Agents, use `--framework openai-agents` instead. Select the actual
model endpoint and a supported API route explicitly; the sample has no model or
fixture fallback. Without `--live` it prints a no-network plan, not an agent run.
The sample helper is stateless, nonstreaming and emits no internal traces.
Stop the agent process after your approved test.

CrewAI uses [crewai_agent.py](../crewai_agent.py) with the same canonical handler
in a separately reviewed environment, not the runner's `[agents]` dependencies.
Its current ChromaDB advisory gate is unresolved; do not execute the blocked
candidate or report it as real-model coverage. See
[the CrewAI prerequisite record](agent_apps/crewai/README.md).

To host any of these samples on an App, use the separately reviewed
[native agent-App preparation guide](agent_apps/README.md). Prepared source is
not a deployed agent. If you already have a compatible production App, no sample
deployment or framework-specific configuration is needed.

The [six-cell local-runner matrix](FRAMEWORK_MATRIX.md) records the evidence
boundaries. A [dedicated load-test App](app_runner/README.md) remains a separately
gated runner example; notebook sources are retained but validation is deferred.
