# ADR 0018: Keep customer-agent examples separate from runner dependencies

- Status: Proposed; designated maintainer review and live validation required
- Date: October 11, 2026
- Scope: Example source/process boundaries; no public SDK or load-engine change

## Context

The requested journeys combine three customer-agent implementations, two target
hosting choices and three independent runner locations. EvalSurge should call a
declared endpoint contract without importing the customer's framework. Conversely,
a customer endpoint should not have to install the load engine merely to return
an answer.

The previous real-framework example imported `evalsurge.serving` at module load.
The CrewAI candidate observed through the approved registry requires OpenAI
`<3` and Pydantic `<2.13`, whereas the reviewed EvalSurge runtime requires newer
versions. Installing both into one environment is not a valid solution. The
candidate's isolated macOS installation was subsequently approved and succeeded,
but its ChromaDB advisory audit failed and native deployment/inference remain
unvalidated; see
[the dependency and live-resource checklist](../LIVE_MATRIX_PREREQUISITES.md).

Existing LangGraph/OpenAI Agents helper callers and retained validation scripts
must remain compatible. No test result from the old source establishes the
refactored example's actual-model behavior or deployment success.

## Proposed decision

Keep a single shared customer-owned real-framework handler implementation in
`examples/real_framework_handler.py`, with standard-library imports at module
load. Optional framework/model libraries are imported only when their handler is
constructed. Return a customer-owned completed-answer value, not an EvalSurge
request, result or run handle.

The existing `real_framework_agent.py` retains its public factory and imports for
compatibility. Its optional EvalSurge HTTP helper explicitly converts the
customer value into `evalsurge.serving.AgentAnswer`. A separate `crewai_agent.py`
serves the same `http-json` input/completed-answer contract without importing
EvalSurge or its server/load dependencies. Framework-specific package versions
and authenticated model resources remain operator selections in the agent's own
environment; the runner has its separate reviewed wheel/environment.

Prepared native LangGraph/OpenAI/CrewAI App projects reuse that same handler source,
`databricks_agentkit.DurableAgentServer` and `/api/invocations`. The inspected
0.4.0 deployment parser requires `agent.framework` and accepts LangGraph/OpenAI
selections, not CrewAI; native-store provisioning is conditional on a parsed
manifest with `server = "agentbricks"`. The current official guide also describes
adapting an existing agent, but a compatible framework-neutral manifest path has
not been verified. Do not relabel CrewAI or omit its manifest to imply equivalent
native provisioning. Preserve its prepared native handler with the deployment
route explicitly unresolved; generic App upload and manually bound Runtime Store
references are not supported substitutes. The CLI-managed Runtime Store must not
be independently created, bound or changed. Its isolated candidate OpenAI/Pydantic
constraints resolved compatibly on macOS/Python 3.11, but the complete advisory
audit blocks live validation. No native support claim follows from installation
or preparing source. Runtime Store/resources/permissions remain
operator-approved deployment prerequisites. Raw model-resource JSON is used in
the recipe because the inspected typed SDK enums lack `MODEL_SERVICE`; it is not
a complete resource-list replacement or an executed mutation.

## Data flow and measurement assumptions

`runner → declared endpoint → request-local framework → selected real model →
completed answer → captured-answer report/evaluation`

Each initial smoke plans one excluded probe and one measured invocation at
concurrency one. Each LangGraph/OpenAI invocation permits one model call; the
CrewAI handler permits at most two, with no provider retries or tools and at most
512 output tokens per model call. These source limits must be checked in the
actual installed/deployed revision before issuing traffic. They are not generic
monetary quotas, and dispatch windows are not rollback or upstream cancellation.

Framework execution, parsing, authentication and provider calls are target-side
work inside the endpoint's observed latency. EvalSurge remains a separate
process/environment with the sole Locust engine. There is no baseline subtraction,
zero-overhead claim or new capacity/TTFT meaning. Judging never reinvokes targets.
SDK initialization/refresh in the native wrapper runs on cancellation-resistant
owned threads. Caller cancellation, including repeated requests, propagates only
after those operations settle and takes precedence over a later worker failure.
This prevents abandonment during lifecycle teardown but can delay cancellation
beyond a requested handler deadline: SDK discovery defaults are not a hard auth
timeout. Thread/CPU/network contention remains inside observed endpoint latency.

## Failure and trust boundaries

Absent or incompatible framework dependencies fail; no fixture answer, alternate
framework, provider/model fallback or registry bypass is introduced. Input and
provider-completion validation remain explicit. Credentials, exact origins and
model selections are customer/operator-owned, outside benchmark requests.

The standalone HTTP endpoint is a loopback tutorial, not an authenticated public
service. A cloud runner requires separately approved HTTPS reachability and
customer-owned ingress authentication. Native App identity, model permissions and
Runtime Store setup remain deployment gates; a Runtime Store is not configured
conversation memory. No automatic recovery hook is supplied. Forced shutdown or
disconnect cannot guarantee rollback of already dispatched model work.
Native examples reject process-local, incomplete and placeholder managed-store
configuration before constructing the server. Configuration presence alone does
not prove durable-store reachability, initialization or permission correctness.
Exact host validation rejects controls/whitespace and backslashes before URL
parsing so normalization cannot silently change the selected credential origin.

## Compatibility and trade-offs

Optimized: independent installable agent and runner environments, one real
handler implementation, and explicit serving contracts without framework plugins
in EvalSurge. Sacrificed: a single environment for every example and a turnkey
unverified CrewAI native deployment. Shared source must be staged deliberately
with a recorded revision; import-time checks alone do not validate that staging
or live behavior.

Public `Agent.http`, `Agent.databricks_app`, v2 models, `/v1`, `/v2`, evaluation
defaults and package dependency constraints remain unchanged. The example files
are not added to the runtime wheel. Source/schema/pre-provider checks are separate
from actual-framework/model, installed-environment and deployment validation.
Required next evidence remains the explicitly approved live matrix and maintainer
review; no successful sample cell follows from this ADR.
