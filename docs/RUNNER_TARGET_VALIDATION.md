# Runner and agent validation matrix

## Fresh local-runner milestone — October 12

Traffic in the fresh validated cells originated on the local Python machine. Agent hosting choices
remain local HTTP or deployed Databricks Apps. LangGraph, OpenAI Agents and CrewAI
are example implementations of the endpoint contract, not target types. Use
`evalsurge[local]` (compatible `[server]` remains available), one shared request,
and the two [local runner scripts](../examples/journeys/LOCAL_RUNNER_QUICKSTART.md).
No EvalSurge API server, runner App, or notebook is needed.

Four of the six local-runner basic cells passed against the exact reviewed
`0.2.1.dev2026101202` pip-installed wheel (SHA256
`a1a58a4513c4659aee41f9c5570bbcca6da371b4b185b629e7842be4eac23285`):

| Actual agent | HTTP target, local runner | Existing Databricks agent App, local runner |
| --- | --- | --- |
| LangGraph | Passed real-model basic smoke; 666.392 ms single measured latency | Passed real-model basic smoke; 1371.096 ms single measured latency |
| OpenAI Agents | Passed real-model basic smoke; 435.451 ms single measured latency | Passed real-model basic smoke; 1441.589 ms single measured latency |
| CrewAI | Blocked by dependency-security gate; no inference | Blocked by dependency-security/native deployment gates; no inference |

Each positive cell used actual `system.ai.gpt-oss-120b`, one excluded probe plus
one measured request, concurrency one, evaluation off and no provider fixtures.
Typed retrieval, drained journals, SDK/worker and HTTP-server cleanup passed.
Existing App identity/source/model/deployment checks passed, with two completed
model responses and no errors per App. Both Apps were stopped afterward; final
confirmation at **2026-10-12 17:23:32 UTC** found STOPPED/UNAVAILABLE, with
resources and deployment IDs unchanged.

Two separate HTTP intentional pre-provider failure checks made one failed probe
each, zero measured requests and zero model calls. They are not successful live
inference cells. Remaining aggregate allowance is 20 target attempts/36 model
calls under the original 36/48 ceiling, not a new lease. These reduced smokes do
not establish quality, active cancellation, tails, capacity, current-template
deployment or zero-overhead accuracy. The App-target health remains unknown.
Prepared cloud samples and the evidence below remain separate; runner-App
installation, native worker authentication/export and cloud traffic have not
passed, and notebook validation is deferred.
See [latest exact-artifact outcomes](LIVE_MATRIX_RESULTS.md) before claiming
real-model coverage. In particular, a prepared CrewAI sample is not a passed
journey while its dependency-security gate is unresolved.

## Retained broader runner validation

This is the historical October 11, 2026 validation inventory and execution plan.
Two of fifteen reduced basic-load cells passed with actual model calls; the other
thirteen are pending. See [the exact current live evidence](LIVE_MATRIX_RESULTS.md).
Listed samples are not automatically successful live runs or complete scenarios.
The examples use direct Python execution. There is no separately deployed
EvalSurge benchmark-submission API in these journeys.

Choose the **agent target** independently from the **load-generator location**:

| Agent target | What runs there |
| --- | --- |
| Separately hosted HTTP endpoint | The customer's real agent and model calls; localhost works only for a runner on that same host |
| Databricks App | The deployed real agent and model calls, selected by exact App name and operator-owned authentication |

| Runner location | What runs there |
| --- | --- |
| Local Python/laptop | Installed EvalSurge, its owned Locust worker, captured-answer evaluation and protected reports |
| Databricks serverless notebook | The same installed package/engine in the notebook environment; the agent runs elsewhere |
| Dedicated Databricks runner App | Direct EvalSurge execution in a separate App, not inside the agent App; private, bounded demo only |

Moving the runner changes the network and scheduling vantage point. It does not
make a local endpoint remotely reachable, prove equivalent latency, or provide
zero observer effect. The runner does not import the customer's agent framework.

## Historical broader live coverage proposal

The three framework names classify example implementations, not a framework
allowlist or separate EvalSurge adapters. All cells require fresh real-model
validation of the exact reviewed artifact; historical receipts remain separate.

| Agent implementation and hosting | Local runner | Serverless notebook runner | Dedicated App runner |
| --- | --- | --- | --- |
| CrewAI, separately hosted HTTP | Pending; installed dependency advisory gate failed | Outside requested scope; optional sample retained | Pending; approved reachable HTTPS required |
| CrewAI, deployed App | Pending; advisory and native deployment gates | Pending worker authentication and live run | Pending runner and target deployment/authentication |
| LangGraph, separately hosted HTTP | Passed reduced basic-load smoke; other scenarios pending | Outside requested scope; optional sample retained | Pending; approved reachable HTTPS required |
| LangGraph, deployed App | Historical live evidence only; fresh run pending | Pending worker authentication and live run | Pending runner and target deployment/authentication |
| OpenAI Agents, separately hosted HTTP | Passed reduced basic-load smoke; other scenarios pending | Outside requested scope; optional sample retained | Pending; approved reachable HTTPS required |
| OpenAI Agents, deployed App | Historical live evidence only; fresh run pending | Pending worker authentication and live run | Pending runner and target deployment/authentication |

The [logical inventory](../examples/journeys/FRAMEWORK_MATRIX.md) enumerates the
15 requested cells and can print a schema-valid workload without making any
network call. Serverless notebook validation targets deployed Apps only; the
retained serverless→HTTP sample is optional and outside this requested scope.
Runner-App→HTTP cells additionally require approved reachable HTTPS, not laptop
loopback or an automatically created tunnel.
A listed cell or successful source check is **not** a successful benchmark.

The current smoke approval selects workspace/profile `e2-demo-field-eng`,
dedicated runner App `load-test` and CrewAI `1.15.23`, with aggregate ceilings of
36 target attempts / 48 model calls, concurrency one, evaluation off and at most
512 output tokens per model call. These are ceilings, not permission to bypass
failed installation/security/authentication gates or expand the 15-cell scope.
Successful and failed calls share the same private lease ledger. The disclosed
controlled-inference regression-suite exception is approved separately; its
fixture responses are not live matrix evidence. Quality and additional active
cancellation traffic require their own scenario allowance.

## Source examples

- [Local runner, HTTP target](../examples/journeys/local_runner_http_target.py).
- [Local runner, App target](../examples/journeys/local_runner_databricks_app_target.py).
- [Serverless notebook, HTTP target](../examples/journeys/serverless_runner_http_target.py):
  optional prepared sample outside the requested validation inventory.
- [Serverless notebook, App target](../examples/journeys/serverless_runner_databricks_app_target.py).
- [Dedicated App direct runner](../examples/journeys/app_runner/README.md):
  disabled one-shot template, fixed target and protected artifacts; no inbound
  benchmark-submission API. Prepared; the October 12 disabled runtime install
  failed and a registry-only App diagnostic found HTTP 403. No live benchmark is
  established. See
  [proposed ADR 0017](adr/0017-private-app-direct-runner.md).
- [Real framework implementations](../examples/real_framework_agent.py): separate
  customer-process agents; no fixture fallback. CrewAI needs its own reviewed
  environment, not EvalSurge's runner environment.
- [Shared customer handler](../examples/real_framework_handler.py) and
  [standalone CrewAI HTTP endpoint](../examples/crewai_agent.py): separate agent
  dependencies, without a load engine in the CrewAI process. Its isolated
  162-distribution install/check passed, but the retained ChromaDB advisory audit
  failed; actual CrewAI inference was not run. See [the prerequisite record](../examples/journeys/agent_apps/crewai/README.md).
- [Native agent-App source projects](../examples/journeys/agent_apps/README.md):
  prepared LangGraph/OpenAI Agents/CrewAI projects reusing that handler; not deployed
  or live validated. CrewAI's supported deployment/managed-store route is still a gap, not silently
  relabeled as another framework. See
  [proposed ADR 0018](adr/0018-customer-agent-example-dependency-isolation.md).
- [Cases, references and judge policies](../examples/quality/README.md): evaluation
  off by default; explicit/automatic policies require separate provider approval.

Install the [reviewed wheel with its historical `server` extra](INSTALLATION.md).
That extra installs direct-execution dependencies; it does **not** require
starting an EvalSurge API server. The wheel does not contain the example source
files: copy the applicable standalone sample separately. Verify the artifact hash
and installed version in each environment, not just an editable source checkout.

HTTP runner samples share optional operator-owned bearer references, outside
`RunCreate`; HTTPS is required for bearer even on loopback. App target samples
reject HTTP bearer configuration. This is configuration parity, not successful
live authentication or a credential-provisioning mechanism. Keep each worker's
credential availability and the actual ingress checks in the private live record.

## Live prerequisites and stopping conditions

1. Select the exact workspace/profile, agent origins/App names, actual agent model
   and source revision. Do not reuse completed historical traffic leases.
2. For CrewAI, select a compatible stable version available through the approved
   registry and validate its separate agent environment. Do not silently substitute
   a version or model to make a test pass.
3. For cloud runners targeting a laptop-hosted agent, obtain an explicitly
   authorized HTTPS origin and network path. `127.0.0.1`, `localhost` and
   notebook-local helper servers are not substitutes. Creating a tunnel, making
   an agent public or changing egress permissions needs separate authorization.
4. For the serverless App-target path, select an existing protected OAuth M2M
   profile source and service-principal client ID with workspace/App permissions.
   Authenticate the owner and independent worker before inference. A working
   driver token or profile listing is not independent worker readiness.
5. Select a dedicated runner App and approve its deployment/permissions. Protect
   artifacts in an explicitly selected existing protected Unity Catalog volume
   and retain evidence before ephemeral compute terminates. The sample consumes
   a non-overwriting approval claim before traffic and does not retry a run on
   restart. This is not
   a production/shared deployment approval; the
   [shared-hosting gates](PRODUCTION_READINESS.md) still apply.
6. Approve agent invocation/model-turn, output-token, duration and judge/planner
   budgets separately. A request cap does not bound customer tool/model turns.
   Start with one excluded preflight and one measured invocation at concurrency
   one; evaluation stays off unless explicitly opted in.
7. Stop on failed configuration, discovery/authentication, protocol/inference or
   selected-judge readiness. Keep failed evidence. No target retry, alternate
   profile, local App stand-in or canned completion is allowed.

The following observations are the historical October 11 initial inventory,
not a current deployment/inference receipt. That inventory encountered a selected-profile
credential-cache refresh error. The initial piped listing is not reliable
evidence of empty/current App inventory. OAuth was subsequently refreshed for
the previously selected `e2-demo-field-eng` profile. Exact read-only App checks
then observed `agent-bricks-es-lg-1008` and `agent-bricks-es-oai-1008` with
`compute_status: STOPPED` and `app_status: UNAVAILABLE`, despite their retained
successful deployment records. `test-eval-crewai-1009` was reported nonexistent
or deleted. This confirms current metadata access, not inference readiness or
independent worker authentication. No App was started, deployed or invoked.

Prepared public native agent-App sources now cover all three frameworks,
but do not verify CrewAI's supported deployment/Runtime Store provisioning route.
They do not count as deployed
Apps or successful inference. The HTTP agent source and matrix generator do not
deploy agents; historical private App bundles are not public deployment examples.
Each target must be verified against its actual native serving contract. See
[the resource/dependency checklist](LIVE_MATRIX_PREREQUISITES.md) before traffic.

## What counts as passing a cell

Retain private evidence identifying the exact wheel hash/version, runner
environment/resources, target hosting/source/model, authorized identity and
approved traffic lease. Record at least:

- Actual inference preflight and successful measured responses, without fixture
  substitutions; load metrics and completeness/generator warnings.
- Typed status/result/report agreement and report retrieval after completion.
- Separate explicit-judge readiness, scored coverage, execution errors and
  quality verdict when evaluation is enabled. Judge calls use captured answers,
  never target reinvocation; a quality failure is not an execution failure.
- Intentional fail-fast checks with expected request/model counts, and separately
  budgeted active cancellation/drain with observed owner/worker cleanup. An empty
  context closure is not active-cancellation coverage.
- Notebook/App lifecycle cleanup and private evidence export before termination.
  Cleanup cannot undo already-dispatched agent tools or model calls.

Answer evaluation does not require internal tracing. Trace correlation and
trace-aware judges are separate optional evidence gates; nonstreaming JSON cannot
establish answer TTFT. Small smokes do not establish sustainable capacity,
calibrated judge quality or cloud-disk measurement accuracy. See
[measurement accuracy](MEASUREMENT_ACCURACY.md) and
[actual command/result records](../VALIDATION.md).

Pure schema/source checks and controlled-provider regression tests must be
reported separately from this live matrix. Existing full-suite/CI tests use
controlled inference and require the explicit exception in [AGENTS.md](../AGENTS.md)
before execution or push-triggered CI. No remote CI result is inferred from a
local test pass.
