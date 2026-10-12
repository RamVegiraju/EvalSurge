# Local runner: framework and agent-hosting examples

The [local runner quickstart](LOCAL_RUNNER_QUICKSTART.md) has two target choices:
an existing HTTP agent or an already deployed Databricks agent App. Install
EvalSurge locally and use the same `RunCreate` workload for either. No EvalSurge
API server, notebook or runner App is needed in the primary journey.
The hosted endpoint's contract is the integration boundary; framework names
describe customer-owned implementations, not a runner plugin or allowlist.

## Six local-runner combinations

These six cells define the primary onboarding matrix. Traffic always originates
on the local machine; model inference happens in the separate agent process/App.
Four rows now have fresh basic-smoke evidence for the reviewed
`0.2.1.dev2026101202` wheel; CrewAI's two rows remain blocked.

| Agent framework | Agent hosting | Runner | Retained evidence and current gap |
| --- | --- | --- | --- |
| LangGraph | HTTP | Local Python | Current installed-wheel real-model basic smoke passed |
| LangGraph | Databricks App | Local Python | Current installed-wheel real-model basic smoke passed against retained deployment |
| OpenAI Agents | HTTP | Local Python | Current installed-wheel real-model basic smoke passed |
| OpenAI Agents | Databricks App | Local Python | Current installed-wheel real-model basic smoke passed against retained deployment |
| CrewAI | HTTP | Local Python | Compatibility install passed; ChromaDB advisory gate blocks live inference |
| CrewAI | Databricks App | Local Python | Advisory and supported native deployment/managed-store gates unresolved |

This is **four of six successful basic live cells**, not six passes or complete
scenario coverage. Each used actual `system.ai.gpt-oss-120b`, one excluded probe
and one measured invocation, concurrency one and evaluation off. No provider
fixtures were used. Typed retrieval and observed cleanup passed; both agent Apps
are now stopped with their resources/deployments retained. These reduced copies
did not exercise the published five-request scripts unchanged, judging, active
cancellation, calibrated accuracy or current-template App deployment. Exact
models, budgets, failures and versions remain in
[the live evidence record](../../docs/LIVE_MATRIX_RESULTS.md) and
[current demo readiness](../../docs/DEMO_READINESS.md).

## Retained cloud-runner sources

The original inventory also has six dedicated runner-App cells and three
serverless notebook→App cells. They are preserved separately, not setup
requirements or passed cells in this local quickstart. The private runner-App
installation remains gated; notebook validation is **deferred**. The optional
[serverless→HTTP source](serverless_runner_http_target.py) is retained outside
the requested live notebook scope.

A dedicated runner App is separate from the target agent App and must pass its
own artifact installation, identity, egress, storage and real-inference gates.
The stopped stdlib registry diagnostic did not install or execute EvalSurge or
perform model calls. See [the private runner-App guide](app_runner/README.md)
and [the current handoff](../../docs/SESSION_HANDOFF.md). For such a cloud runner,
`127.0.0.1` is not your laptop: an HTTP agent needs an explicitly approved reachable
HTTPS origin. No sample creates a tunnel, exposes a loopback agent publicly,
copies credentials or substitutes a cloud-hosted fake agent.

## One public request shape

[framework_runner_matrix.py](framework_runner_matrix.py) retains all fifteen
historical/prepared labels with the same public `RunCreate`, `Case`, and `Load`
contract. Filter `runner == "local"` to select the six primary cells; the inventory
CLI prints retained cloud labels too, not fifteen validated environments. The framework
does not change request encoding. HTTP targets use the minimal `http-json`
contract; deployed App targets use the configured native App protocol. Agent
profiles and destinations remain in `Agent` bindings, outside the request.

These source-check commands do not authenticate, start Locust, deploy, or make
model calls:

```bash
uv run --frozen --no-sync python -m examples.journeys.framework_runner_matrix matrix
uv run --frozen --no-sync python -m examples.journeys.framework_runner_matrix request \
  --framework crewai --runner local --hosting http \
  --http-url http://127.0.0.1:9001/invoke
uv run --frozen --no-sync python -m examples.journeys.framework_runner_matrix request \
  --framework openai-agents --runner local --hosting databricks-app \
  --app-name YOUR_DEPLOYED_AGENT_APP --profile YOUR_EXPLICIT_PROFILE
```

The request has evaluation off, concurrency one, at most one measured invocation,
and one extra excluded preflight. Each agent invocation can make multiple model
or tool calls: an invocation limit is not a model/token/spend quota. The matrix
helper does not itself execute benchmarks and is not an authorization mechanism.

### Optional HTTP authentication

The local HTTP runner and matrix configuration helper support an operator-owned
bearer environment-variable **reference**. Use
`--bearer-token-env AGENT_BEARER_TOKEN` and provision the
secret separately through an approved operator mechanism. Do not put its value
in the benchmark request, source or CLI argument. Bearer bindings require HTTPS,
including loopback; App targets reject HTTP bearer selections and use their own
explicit App authentication. Binding/schema checks do not prove that the secret
exists in a worker or that ingress authentication succeeds. Retained cloud
sources have separate credential/resource configuration; they are not required
by the local onboarding journey.

### Explicit load plus evaluation

The helper accepts `evaluation="explicit"` to select **relevance** and
**correctness**, with at most one measured capture selected per scorer. It makes
no provider call while constructing the request. References are never guessed
from an arbitrary agent URL or framework name:

```python
from evalsurge import Case
from examples.journeys.framework_runner_matrix import Journey, request

journey = Journey("langgraph", "local", "http")

# ONLY for an agent actually running the exact synthetic refund-policy sample:
config = request(journey, evaluation="explicit", sample_refund_policy=True)

# For other agents, supply the authoritative input/reference you own instead:
config = request(
    journey,
    evaluation="explicit",
    case=Case(
        input={"query": "What is the authorized demo color?"},
        reference={"expected_response": "Blue."},
    ),
)
```

The blue-answer case is an illustrative caller-owned dataset shape, not a claim
about the refund agent. Use your actual authoritative facts. A nonempty
`expected_response` or `expected_facts` is required for explicit correctness.
`sample_refund_policy=True` explicitly affirms the selected agent's synthetic
policy is the policy in [real_framework_handler.py](../real_framework_handler.py):
"Opened items cannot be refunded." It is rejected when mixed with custom cases
or when evaluation is off.

Equivalent **configuration-only** commands are:

```bash
uv run --frozen --no-sync python -m examples.journeys.framework_runner_matrix request \
  --framework langgraph --runner local --hosting http \
  --http-url http://127.0.0.1:9001/invoke \
  --evaluation explicit --sample-refund-policy
uv run --frozen --no-sync python -m examples.journeys.framework_runner_matrix request \
  --framework openai-agents --runner local --hosting databricks-app \
  --app-name YOUR_DEPLOYED_AGENT_APP --profile YOUR_EXPLICIT_PROFILE \
  --evaluation explicit --query "What is the authorized demo color?" \
  --reference-fact "The authorized demo color is blue."
```

The judge endpoint/provider/profile is a **separate operator selection** from the
agent's inference model/profile. Configure it outside `RunCreate`, through your
private operator settings/environment and the client's `settings=` binding; see
[the quality guide](../quality/README.md). Never put judge credentials in cases or
the printed request. For this explicit mode there is no scorer-selection planner.
Automatic planning is separately opt-in through `EvaluationPolicy(mode="automatic")`
and requires its own approved provider/resources; this matrix helper deliberately
does not activate it or choose a planner model.

Budget agent and judge traffic separately. The agent can receive one excluded
preflight plus one measured invocation. Selected judges first check readiness
against the **captured probe**, excluded from reported quality counts, and later
score captured measured answers. With two explicit scorers and one measured
capture, this allows up to two readiness assessments plus two measured assessments
when every phase succeeds; provider retries/attempts and model/token/spend limits
are independently configured. Catalog judge readiness uses zero SDK retries;
measured catalog judging uses the separately frozen retry cap. No judging phase
reinvokes the target. Failed judge
readiness stops before measured load and remains a separate phase outcome.
Successful execution is not the same as a passing quality assessment: report
per-scorer assessed/pass/error counts, eligible/selected coverage and evidence gaps.

For an explicitly approved real run from your local runner, use the same public
SDK pattern for either target:

```python
from evalsurge import Agent, Case, EvalSurge, Load, RunCreate, TargetReference, format_summary

# Select ONE operator-owned target. No framework selector is needed.
agent = Agent.http("http://127.0.0.1:9001/invoke", protocol="http-json")
# agent = Agent.databricks_app("YOUR_DEPLOYED_AGENT_APP", profile="YOUR_EXPLICIT_PROFILE")

config = RunCreate(
    target=TargetReference(connection_id="agent"),
    cases=[Case(input={"query": "Can an opened item be refunded?"})],
    load=Load(concurrency=1, duration_seconds=10, max_requests=1, timeout_seconds=40),
)

# Review exact agent/model resources and traffic first; no inference by default.
ALLOW_REAL_INFERENCE = False
if not ALLOW_REAL_INFERENCE:
    raise RuntimeError("Approve this exact target and two possible agent invocations first")

with EvalSurge(artifact_dir="artifacts/approved-smoke", targets={"agent": agent}) as client:
    report = client.start(config).wait(timeout=300)
    print(format_summary(report))
```

This snippet generates traffic locally; choosing an App target does not move the
runner into that App. It is not evidence of cloud-runner process/authentication
support. Do not switch the guard until the exact target, resources and traffic
are approved.

## Agent sources and execution samples

- [real_framework_handler.py](../real_framework_handler.py) contains the canonical
  actual LangGraph, OpenAI Agents and CrewAI handlers, without EvalSurge imports.
  [real_framework_agent.py](../real_framework_agent.py) retains the optional
  EvalSurge serving bridge for compatible agent environments.
  [crewai_agent.py](../crewai_agent.py) is the standalone CrewAI HTTP endpoint;
  use its separately resolved agent environment rather than installing CrewAI
  into EvalSurge. None has a fixture/model fallback. CrewAI telemetry must be
  disabled; the runner's `[agents]` extra does not install CrewAI.
- [local_runner_http_target.py](local_runner_http_target.py) generates traffic
  locally against an already running real HTTP agent.
- [local_runner_databricks_app_target.py](local_runner_databricks_app_target.py)
  generates traffic locally against an already deployed real App agent.
- [serverless_runner_databricks_app_target.py](serverless_runner_databricks_app_target.py)
  is a retained, deferred notebook-to-App path with a portable OAuth prerequisite,
  not a demonstrated complete serverless journey or current milestone requirement.
- [app_runner/](app_runner/README.md) is a separately gated prepared source for
  installing EvalSurge in the dedicated `load-test` App, not a local setup step.
  Its disabled deployment failed during dependency installation; a stopped
  stdlib diagnostic observed denied registry access, not benchmark success.
  Native authentication and protected export remain unverified. Approved exact
  target/volume grants and `ram_artifacts.evalsurge_validation.runner_artifacts`
  are retained; existing catalog administration was preserved. This runner App
  is neither the agent App nor a benchmark-submission API server.

**Native agent-App preparation, not live coverage:** the
[public native projects](agent_apps/README.md) reuse the same customer handler
for LangGraph, OpenAI Agents and CrewAI. They require explicit source staging, reviewed
dependency artifacts, model/identity resources and actual deployment/inference
validation. CrewAI's supported deployment and managed Runtime Store provisioning
remain unresolved; prepared native source is not a successfully deployed App.
It is not relabeled as LangGraph/OpenAI. The
[standalone CrewAI endpoint](../crewai_agent.py) avoids incompatible runner
dependencies but does not establish native App support.
Historical private bundles do not establish current public-template coverage.
Neither the matrix CLI nor an App-runner sample deploys an agent App. A runner
App and an agent App are separate selected resources with different responsibilities.

Example files are repository sources, not files installed by the wheel. Install
the reviewed wheel with `[local]` (`[server]` remains compatible) in the local
runner environment; copy the selected
standalone example or import this matrix module from a reviewed checkout.
Framework dependencies belong in the agent's environment, not a framework
allowlist or plugin inside EvalSurge.

## Evidence required to mark a cell passed

Record the exact installed wheel/version/hash, runner environment, framework
version, real model, agent source/deployment revision, target, explicitly selected
auth identity, and approved traffic. Retain excluded preflight and measured
counts, phase outcomes, typed report, and cleanup receipts. Actual model calls
and actual deployed App invocation must be established independently of input
schema construction or dispatch-counter metadata.

Load-only completion does not establish answer quality. Follow with separately
approved explicit or automatic evaluation of captured answers, documenting judge
model/provider, selected scorers, coverage, and evidence gaps. Judging must not
reinvoke the agent. Fail-fast and cancellation/drain need separate bounded
scenarios; intentional pre-provider failures make no model call and are reported
separately. No stubbed provider responses are used by the pure matrix checks.
