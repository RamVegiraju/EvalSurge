# Bring your hosted agent: end to end

EvalSurge benchmarks an HTTP service, not a particular agent framework. Keep your
existing graph, agent, crew, model provider and tools. Expose a compatible endpoint,
bind it in Python, supply cases, and choose the load to test. No EvalSurge API
server is needed for direct execution.

The framework examples below are recipes, not an allowlist. An agent built with
any other framework, another programming language, or custom code uses exactly
the same endpoint contract and benchmark request. No new EvalSurge framework
integration is required for compatible HTTP invocation and answer evaluation.
Internal profiling/trace-aware judging has a separate optional evidence contract.

## What you bring

1. A running, authorized endpoint reachable from the machine running EvalSurge.
2. A supported input/answer contract. The simplest is POST JSON in, `outputs` text out.
3. Representative cases and bounded traffic you are authorized to generate.
4. Optional evaluation policy and authoritative reference answers/facts.
5. Optional agent-side MLflow instrumentation for internal profiling/trace-aware judges.

You do not need to know supported concurrency. It is the number of clients to try,
not a capacity declaration. Begin with a small bounded run; increase load after
reviewing latency/errors and provider/tool costs. One load level cannot discover
sustainable capacity. The single excluded preflight validates the first case's
contract/readiness, not all cases, thread safety or concurrency capacity.

## 1. Expose your existing local agent

If your service already has a [supported endpoint](TARGETS.md#supported-wire-contracts),
skip this step. Otherwise use a thin adapter in **your agent project**, not in the
load generator. The optional helper below and the manual recipe both call your
existing handler inside its own process; neither makes EvalSurge import your agent.

### Optional framework-neutral serving helper

Install the optional server dependencies alongside your existing framework:

```bash
uv add 'evalsurge[server]'
```

Save this as `agent_server.py`. Implement `answer_case` with one of the framework
bridges below, or your own real handler. This helper does not choose/change its
provider or substitute a model completion:

```python
from typing import Any

from evalsurge.serving import AgentAnswer, InvocationContext, create_app

from your_agent_bridge import answer_case


async def answer(inputs: dict[str, Any], context: InvocationContext) -> AgentAnswer:
    """Execute this project's real agent and select its completed text answer."""
    completed = await answer_case(inputs["query"], request_id=context.session_id)
    return AgentAnswer(outputs=completed)


app = create_app(answer, isolation="request")
```

Start it locally with `uv run uvicorn agent_server:app --host 127.0.0.1 --port 9001`,
then bind `Agent.http("http://127.0.0.1:9001/invoke", protocol="http-json")` in
the Python example below. **The helper has no built-in authentication.** Loopback
is the tutorial default; add customer-owned authentication middleware or an
authenticated gateway before exposing it on a network. Correlation headers are
untrusted labels and never authorize access or identify a tenant.

The helper preserves the complete nonempty input object: it does not strip
`custom_inputs`, nested routing fields or your framework's state. Your handler
still owns its input schema and explicit mapping. Request bodies are limited to
eight megabytes, including chunked bodies; malformed/nonfinite JSON, duplicate
keys and invalid UTF-8 are rejected before customer execution. Handler exceptions
and invalid/empty final answers produce fixed, safe failed HTTP responses—not
success-shaped error text. Exactly one handler call is made; no retries occur.

Choose state keys deliberately:

| `isolation` | `context.session_id` semantics | Required context |
| --- | --- | --- |
| `request` | Fresh attempt/request key | Standalone calls permitted; absent benchmark headers generate a fresh opaque key |
| `case` | One key per run and case | Valid benchmark run, request and case headers |
| `shared` | One shared key per run | Valid benchmark run and request headers |

The runner sends `X-Benchmark-Run-ID`, `X-Benchmark-Request-ID` and
`X-Benchmark-Case-ID`. Malformed, duplicated or incomplete benchmark headers are
rejected with a safe 400. `context.run_id`, `request_id` and `case_id` are available
for customer instrumentation separately from the state key. Generated standalone
keys are not traces. Keys do not isolate shared tools, caches, stores or mutable
globals, and this helper does not create session persistence or agent memory.
The excluded readiness probe uses the run's first case and can modify case/shared
state before measured load. Use `request` isolation for independent benchmark
attempts unless your intended production behavior requires a shared session.

If your handler already obtains actual evidence, supply it explicitly:
`AgentAnswer(outputs=completed, trace_id=root_trace_id,
usage={"output_tokens": actual_output_token_count})`. The complete JSON response
is limited to two megabytes. Trace IDs are bounded printable ASCII strings and
are returned consistently in JSON and `X-MLflow-Trace-ID`; counts must be
nonnegative integers. Omit evidence you do not have. The helper does not instrument
or export traces, estimate token counts, implement deadlines for customer code,
or manufacture streaming/TTFT. HTTP latency includes the completed handler and
response serialization. Customer code owns timeouts and cancellation cleanup.

These helper checks cover schemas, correlation, routing and intentional
pre-provider failures without model inference. They do not establish successful
live framework execution or a deployed App. See [validation](../VALIDATION.md)
for separately retained real-model evidence and current gaps.

### Manual HTTP wrapper

If you prefer to keep a separate serving implementation in your project, install
FastAPI/Uvicorn alongside your existing framework:

```bash
uv add fastapi uvicorn
```

Save this as `agent_server.py`. Implement `answer_case` using one bridge below;
`your_agent_bridge` is your module, not an EvalSurge package.

```python
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from your_agent_bridge import answer_case

app = FastAPI()


class AgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=100_000)


@app.post("/invoke")
async def invoke(body: AgentInput, request: Request) -> dict[str, str]:
    """Run one caller-owned agent attempt and return its completed answer.

    Args:
        body: Query for this example's agent input schema.
        request: HTTP request carrying the benchmark correlation headers.

    Returns:
        The nonempty final answer, not tool events or intermediate state.

    Raises:
        HTTPException: The agent returns no final text. Agent exceptions otherwise
            propagate as failed requests; they are not converted into success text.

    Side effects and model/tool costs belong to the existing agent. The request ID
    isolates framework state; this recipe does not add tracing, retries or memory.
    """
    request_id = request.headers.get("X-Benchmark-Request-ID") or str(uuid4())
    answer = await answer_case(body.query, request_id=request_id)
    if not isinstance(answer, str) or not answer.strip():
        raise HTTPException(status_code=502, detail="Agent produced no completed answer text")
    return {"outputs": answer}
```

Implement `answer_case(query, *, request_id)` in `your_agent_bridge.py` using your
existing agent execution method and return its completed text answer. It can call
any framework; the HTTP wrapper and benchmark do not change. Await async execution;
offload blocking execution from the server event loop deliberately, accounting for
thread-pool limits. Preserve agent failures instead of returning success-shaped
error text. Use the request ID to isolate conversation state where applicable.

The following **optional examples** show three common implementations. Choose one
or write your own. Imports refer to your existing project. These recipes assume
final text output; adapt your actual state/input schema deliberately. Do not
stringify arbitrary graph/crew state as the answer.

### LangGraph bridge

For an existing compiled graph with a `messages` state:

```python
from your_agent import graph


async def answer_case(query: str, *, request_id: str) -> str:
    """Run a messages-state graph in a separate request thread, returning final text."""
    state = await graph.ainvoke(
        {"messages": [{"role": "user", "content": query}]},
        config={"configurable": {"thread_id": request_id}},
    )
    if state.get("__interrupt__"):
        raise ValueError("This benchmark requires an uninterrupted completed graph")
    message = state["messages"][-1]
    if message.type != "ai" or getattr(message, "tool_calls", None):
        raise ValueError("Graph did not return a final assistant answer")
    return str(message.text)
```

The thread ID isolates checkpointed conversation state; it does not isolate
shared stores, tools or mutable globals. If your graph has a different state
schema, map that schema and select its actual final answer instead.

### OpenAI Agents bridge

For an existing agent configured for text final output:

```python
from agents import Runner

from your_agent import agent


async def answer_case(query: str, *, request_id: str) -> str:
    """Run an existing text-output agent without sharing a conversation session."""
    result = await Runner.run(agent, input=query)
    if not isinstance(result.final_output, str):
        raise ValueError("Configure text final output or map the structured answer explicitly")
    return result.final_output
```

This does not change the agent's provider/model. The request ID is available for
optional tracing; this bridge does not reuse a session or response continuation.
Agent/tool configuration can still contain shared state or native retries.

### CrewAI bridge

Build a fresh crew per request rather than concurrently reusing mutable crew state:

```python
from your_agent import build_crew


async def answer_case(query: str, *, request_id: str) -> str:
    """Run a fresh customer-owned crew and return its final raw text."""
    crew = build_crew()
    result = await crew.kickoff_async(inputs={"query": query})
    return result.raw
```

Your task templates must consume `{query}`; map different task placeholders
explicitly. CrewAI documents `kickoff_async` as thread-based, and `akickoff` as
native async. Thread-pool limits can therefore affect measured concurrency.
CrewAI is not a bundled dependency or a live-validated first-party integration;
this is a documentation recipe for the existing framework-neutral JSON boundary.

Start the agent server in its own terminal:

```bash
uv run uvicorn agent_server:app --host 127.0.0.1 --port 9001
```

Keep model/tool credentials in the agent process. This is a local recipe, not a
public server hardening guide. Preserve production behavior: do not swallow
errors, add benchmark-only model fallbacks, or remove required context. If your
agent needs extra fields, extend your server's schema and supply them in
`Case.input`; the `http-json` adapter forwards that object unchanged.

## 2. Run the same benchmark

Install the execution stack in the benchmark project:

```bash
uv add 'evalsurge[server]'
```

Save this as `benchmark.py` and run `uv run python benchmark.py` after authorizing
the model/tool traffic. It makes at most ten measured agent invocations plus one
excluded first-case probe. Each invocation may make several internal model/tool calls.

```python
from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference

request = RunCreate(
    name="first-benchmark",
    target=TargetReference(connection_id="agent"),
    cases=[Case(input={"query": "Give a short greeting."})],
    load=Load(concurrency=2, duration_seconds=10, max_requests=10, timeout_seconds=60),
)

with EvalSurge(
    artifact_dir="artifacts/first-benchmark",
    targets={"agent": Agent.http("http://127.0.0.1:9001/invoke", protocol="http-json")},
) as client:
    run = client.start(request)
    report = run.wait(timeout=300)
    print(report.model_dump_json(indent=2))
```

Evaluation is off. Inspect preflight/load outcomes even if the run failed; a wait
timeout does not cancel work. JSON answers provide latency/throughput/errors, not
TTFT. Use a supported streaming endpoint for answer-text TTFT, not an artificial
stream of a previously completed answer. Protect retained inputs/answers and the
artifact directory. See [reports](REPORTS_AND_JUDGES.md) for typed outcomes and HTML access.

## 3. Or bind your deployed Databricks App

For new deployments, use DurableAgentServer. The
[official Agent Server guide](https://docs.databricks.com/aws/en/agents/deploy/agent-server)
recommends it and explains adapting an existing agent. LangGraph/OpenAI templates
connect the framework to the server; a custom framework needs an invocation
handler. Return supported final text, such as `{"answer": answer}`, and expose
`/api/invocations`. Hosting on Apps alone does not make an arbitrary route compatible.

Keep the `request` above and replace only the target binding:

```python
target = Agent.databricks_app(
    "your-deployed-app",
    profile="YOUR_SELECTED_OAUTH_PROFILE",
)
with EvalSurge(artifact_dir="artifacts/app-benchmark", targets={"agent": target}) as client:
    report = client.start(request).wait(timeout=300)
    print(report.model_dump_json(indent=2))
```

EvalSurge sends input messages to the native invocation handler and uses its
synchronous completed result. This is a different envelope from the local
`http-json` wrapper; a custom handler must map the messages to its own graph/crew
inputs. Model/provider calls inside the agent remain independent of this envelope.

The SDK resolves the App and refreshes OAuth. The selected identity needs access
to the App; deployment/model/tool permissions belong to the App configuration.
Current native invocation runs have no TTFT or token-usage extraction. Runtime
Store/session IDs are not MLflow traces or automatic agent memory.

[Framework/App examples](FRAMEWORK_TARGET_EXAMPLES.md) and
[validation](../VALIDATION.md) record actual coverage and gaps. There is no native
CrewAI App deployment/trace validation in the repository. Existing legacy
`/responses` deployments have [separate compatibility instructions](TARGETS.md#legacy-protocol-compatibility),
not a second onboarding path.

## 4. Add answer evaluation

Use `Case(input=..., reference=...)` and `EvaluationPolicy` from the
[README example](../README.md#add-your-dataset-and-judges). Configure the judge
provider outside the request; the hosted agent's model is not automatically the
judge. The current catalog judges require Databricks provider configuration even
for an agent hosted elsewhere. Reviewed registered judges retain their own provider.

- Explicit mode selects fixed criteria; automatic mode opts into constrained planning.
- Relevance/safety use captured inputs/answers. Correctness needs your authoritative
  `expected_response` or `expected_facts`, including for the first-case readiness probe.
- Judging never reinvokes the target. It checks the captured probe for readiness,
  then samples captured measured answers through native MLflow evaluation.
- References/rationales may contain sensitive data disclosed to the configured judge.

## Optional internal tracing

HTTP invocation and internal tracing are independent contracts. Answer evaluation
does not require traces. Internal timing and trace-required judges do.

1. Instrument the **agent process** with MLflow, using appropriate framework autologging
   or explicit spans. Keep a root span alive until the whole invocation completes.
2. Read `X-Benchmark-Run-ID` and `X-Benchmark-Request-ID` from the incoming request.
   Attach `evalsurge.run_id` and `evalsurge.request_id` to root trace metadata.
3. Return the root ID in `X-MLflow-Trace-ID` (all supported protocols), `trace_id`
   (`http-json`), or a supported SSE trace event. Native App JSON uses the header.
4. Enable EvalSurge tracing with an authorized tracking URI, exact experiment
   allowlist and bounded trace/span budget. Tracking credentials stay outside `RunCreate`.
5. Export completed traces from the agent. EvalSurge fetches returned IDs after load,
   validates exact scope/correlation/tree integrity, and reports missing evidence.

EvalSurge cannot flush exports in a different agent process or turn a returned ID
into instrumentation. OpenAI native tracing, CrewAI tracing or LangSmith tracing
alone are not the current MLflow collection contract. Use one reviewed tracing
strategy, not duplicate exporters/spans. See the
[detailed tracing/scorer contract](PROFILING_AND_EVALUATION.md).

## Verification and extension boundaries

These new bridge snippets have syntax/schema checks only; they are not fresh
end-to-end agent/model or App validation. LangGraph/OpenAI native integration
evidence exists separately in `VALIDATION.md`; it does not establish CrewAI parity.

Future serving options should add hosting/authentication resolution independently
of wire encoding and trace collection, reusing the same `RunCreate`, Locust and
captured-answer evaluator. The proposed
[integration design](adr/0012-hosted-agent-integration-contract.md) records the
compatibility, measurement and verification gates. The optional serving helper is
an additive bridge to the existing `http-json` contract, not a new load engine,
hosting resolver, trace backend or framework allowlist.

Official framework APIs checked October 8, 2026:
[LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api),
[OpenAI Agents execution](https://openai.github.io/openai-agents-python/running_agents/),
[CrewAI execution/output](https://docs.crewai.com/en/concepts/crews).
