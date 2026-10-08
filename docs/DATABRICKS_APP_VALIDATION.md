# Bounded Databricks App smoke validation

This workstream validates an **existing, authorized deployed sample**, with EvalSurge
running separately on the operator's machine. It does not deploy, reconfigure, or
restart an App. A new sample deployment needs separate approval and selected resources.

For normal end-user setup, see [local HTTP and App targets](TARGETS.md) and the
[four framework request examples](FRAMEWORK_TARGET_EXAMPLES.md). Separate October 8
deployments validated both LangGraph and OpenAI Agents native Apps through actual
loopback HTTP v2 submission and the remote SDK, with 500/500 successes each at five
users and intentional failed probes that stopped measured load. Those samples were
stateless, tool-free, quality-off and untraced; exact revisions, results and limits
are in [VALIDATION.md](../VALIDATION.md). These tests do not deploy EvalSurge itself.

The separately authorized October 7 redeployment passed intentional fail-fast, 500/500 measured
requests at concurrency five, and a two-capture explicit quality check; retained
failures and exact metrics are in [VALIDATION.md](../VALIDATION.md). Those checks used
the local facade/resolver, not live `/v2` HTTP submission or hosted EvalSurge.

## Current deployment and protocol guidance

Official guidance checked October 7, 2026, with Agent Server guidance rechecked
October 8 (the original pages were last updated October 6):

- [Develop agents](https://docs.databricks.com/aws/en/agents/) recommends Agent Runtime
  and AgentKit `DurableAgentServer`.
- [Query agents](https://docs.databricks.com/aws/en/agents/query-llms) maps current CLI
  templates to synchronous `POST /api/invocations`, with a generated invocation UUID
  and a session ID. It explicitly labels MLflow `AgentServer`/`LongRunningAgentServer`
  and their `/responses` endpoint as legacy.
- [Agent Server](https://docs.databricks.com/aws/en/agents/deploy/agent-server) explains
  the current server and legacy interfaces. Hosting on Apps alone does not identify
  the installed server. Choose the protocol from the actual sample's implementation.

Consequently, EvalSurge retains `databricks-agent-runtime` as the default App protocol.
An existing MLflow AgentServer registration must explicitly configure:

```toml
[connections.sample]
kind = "databricks-app"
app_name = "your-selected-app"
profile = "your-selected-profile"
protocols = ["mlflow-agent-server"]
```

This selects `/responses` without caller URL/profile overrides or speculative
fallback requests. Runtime registration can omit protocols or explicitly use
`["databricks-agent-runtime"]`.

### Source and skill boundaries

The older local deployment/load-testing skills describe MLflow AgentServer and
`/invocations`; they are not the invocation contract for this native Runtime sample.
Cross-check current official docs with the installed package's runtime guide and
[OpenAI integration contract](https://github.com/databricks/databricks-ai-bridge/blob/c2046018d6fa3f382bf18f89a44ea5b7943776ba/integrations/agentbricks/src/databricks_agentbricks/templates/agent-openai/AGENTKIT_CONTRACT.md).
The official [migration skill](https://github.com/databricks/databricks-ai-bridge/blob/c2046018d6fa3f382bf18f89a44ea5b7943776ba/integrations/agentbricks/src/databricks_agentbricks/templates/agent-bricks-migrate/SKILL.md)
is a useful integration reference, not authorization to migrate stores or deploy.
That October 7 source snapshot is `0.5.0.dev0`; it is not a stable upgrade to the
sample's pinned `databricks-agentbricks==0.4.0`. Its migration skill, OpenAI contract,
and deployment implementation match the installed stable package. Its newer server
event-reader changes are not exercised by this synchronous JSON check.

The native package/templates require Python 3.11+, even though the overview docs
still say 3.10+. Use the installed metadata and CLI help for version-specific
requirements and flags. Native deployment omits the developer's `uv.lock` and
resolves dependencies on the App; local transitive versions do not prove deployed
version parity.

Model API compatibility must also be verified independently of the App's public
protocol. The [Unity Gateway quickstart](https://docs.databricks.com/aws/en/unity-gateway/quickstart)
documents querying fully qualified model names through the MLflow Responses route.
In this workspace, the `system.ai.gpt-oss-120b` model-service metadata
advertises only `mlflow/v1/chat/completions` and `mlflow/v1/responses`, not the
native `openai/v1` route supported by the Databricks OpenAI client. Do not infer
model support from an SDK flag or change routes as an automatic fallback. The
MLflow chat route can return structured reasoning/text content blocks; the
non-streaming Agents chat converter expects a text string. For this sample, use
the supported MLflow Responses route with the actual `OpenAIResponsesModel`,
keeping reasoning separate from final answer text and rejecting incomplete/failed
provider responses before reporting success. The App remains synchronous
`POST /api/invocations`; the internal model API is a separate boundary.

The managed Lakebase **Runtime Store** holds invocation requests, status,
heartbeats, events, and results. It is provisioned by native deployment, separately
from a **Session Store** for agent conversation history and a **Memory Store** for
cross-session facts. A Runtime session ID orders invocations; it does not make the
agent remember prior messages. This sample binds neither history nor memory.

## Resources and consent required

Before any workspace access or paid inference, provide:

1. The exact OAuth CLI profile selected by the user, not just a workspace URL. Never
   auto-select even a unique matching profile. PAT authentication does not work for Apps.
2. Existing App resource name, permission to invoke it, and its actual server protocol.
3. A harmless synthetic prompt and confirmation that tool/model actions are safe.
4. Consent to one extra excluded probe plus a chosen measured cap (default two;
   maximum 500), concurrency (default one; maximum five), dispatch window (default
   ten seconds; maximum 180), and request timeout (maximum 60 seconds). These limits bound
   top-level traffic, **not dollars or internal agent model/tool calls**; the App
   operator must supply those spend/action controls. Current DurableAgentServer
   recovery can reexecute handlers after a crash without a built-in attempt cap:
   confirm recovery is disabled or explicitly bounded for this sample. State any
   acceptable cost ceiling. EvalSurge's no-retry policy cannot disable server recovery.
5. A new protected artifact directory and retention decision. Prompts, answers,
   profiles, and resolved configuration in raw evidence are sensitive; do not commit them.

No scoring reference, judge endpoint, or trace experiment is needed for this initial
performance-only check. Add judging/profiling only after separate explicit selection
and consent. A production-like agent using `custom_inputs`, actor identity, model
routing, or resume state is not supported by the fixed message adapters: those
top-level fields now fail validation rather than being silently discarded. This
smoke uses only `query` converted to one user message. A pass therefore validates
that contract, not every production behavior.

## Prepare without traffic

Install the checkout's server/development environment (see README for current extras),
then run the harness without `--live`. This default performs no App lookup, profile
credential resolution, storage creation, target traffic, or planner/judge calls:

```bash
uv run --no-sync python -m scripts.validation.databricks_app_smoke \
  --profile YOUR_SELECTED_PROFILE --app-name YOUR_SELECTED_APP \
  --protocol databricks-agent-runtime --prompt 'Reply with a short greeting.'
```

The printed budget omits the profile, App name, and prompt. Select
`--protocol mlflow-agent-server` for an already deployed MLflow sample.
Do not put sensitive prompts into command-line arguments or shell history.
To prepare the requested five-user, three-minute workload without making any calls,
add `--concurrency 5 --duration 180 --max-requests 500`. Duration and request cap are
competing dispatch stopping conditions: 500 fast responses may end before three
minutes. The excluded probe and active-request drain add time outside that window.

## Execute only after consent

Use a new/empty evidence directory; a nonempty directory is rejected before discovery.
The following is an example of the bounded consent envelope, not authorization to run:

```bash
uv run --no-sync python -m scripts.validation.databricks_app_smoke \
  --profile YOUR_SELECTED_PROFILE --app-name YOUR_SELECTED_APP \
  --protocol databricks-agent-runtime --prompt 'Reply with a short greeting.' \
  --concurrency 1 --max-requests 2 --duration 10 --timeout 30 \
  --artifact-dir artifacts/app-smoke-UNIQUE_RECORD \
  --live --accept-paid-traffic
```

The harness uses server-owned resolution with the selected SDK profile, refreshable
OAuth, exact origin binding, per-attempt isolated Runtime sessions, the public local
Python façade, and one Locust engine. It rejects ambient SDK credential/destination
overrides rather than changing global environment values. Evaluation and tracing
are explicitly off. There is one inference probe; only its success permits measured
load. There are no EvalSurge target retries, redirects, deployment changes, background polling,
resume operations, or judging reinvocations. Runtime JSON has no fabricated TTFT;
legacy SSE measures first answer-text delta, not first event/byte or browser paint.

Exit codes: `0` requires passed inference preflight and at least one measured success
with zero measured errors; `1` retains a usable failed report; `2` means no usable
report was returned. Parser errors also return `2`. The content-free `validation.json`
records the run ID, bounds, phase outcomes, and selected metrics; raw protected
evidence stays alongside it. Do not repeat a failed/uncertain invocation to hide it.
The local owner drains on exit; SDK credential sources are not hard wall-clock bounded.
The nominal wait budget includes dispatch, probe/drain deadlines and startup margin
(at least 300 seconds; at most 360 with these configured limits), not a hard wall-clock
authentication/process termination guarantee.

After separately consenting to the larger workload, choose
`--concurrency 5 --duration 180 --max-requests 500` explicitly. That allows at most
501 top-level invocations including the probe, not 501 model calls or a fixed
dollar amount. Before that run, exercise the sample's explicitly designed safe
failure input in a **separate new directory**. A failed preflight must retain a
safe error code/message, `load_status=skipped`, measured requests zero, and
`fail_fast_confirmed=true`; the harness exits `1` because the run intentionally
failed. Its observation counters distinguish the excluded probe from measured
attempts. No attempt is repeated to turn the failure into a pass. Do not invent a
failure input for an arbitrary production agent or mutate its resource configuration.

## Record and interpret the result

Keep a private validation record of the selected workspace/profile, App/revision,
protocol, consent/cost bounds, safe workload, runner/network placement, package versions,
run ID, observed calls, phase outcomes, and any trace gaps. Record failed attempts,
including discovery/auth failures. A tiny passing check establishes connectivity,
OAuth, supported envelope, preflight, and measured-load integration—not calibrated
quality, full production input equivalence, sustainable capacity, or shared-hosting
readiness. Follow [the production gates](PRODUCTION_READINESS.md) for those claims.

## Separate captured-answer quality integration

The [quality helper](../scripts/validation/databricks_app_quality.py) runs a **new**
bounded native Runtime benchmark, not post-hoc grading of a prior performance run.
It fixes one harmless synthetic refund-policy question and an authoritative
`expected_facts` reference, explicitly selects relevance and correctness (no
automatic planner), and freezes `databricks-gpt-5-4-mini` as the judge. The case
contains the policy: opened items cannot be refunded; unopened items may be returned
within 30 days. It does not invent a reference from the target's answer.

Prepare without discovery, credentials, storage, or traffic:

```bash
uv run --no-sync python -m scripts.validation.databricks_app_quality \
  --profile YOUR_SELECTED_PROFILE --app-name YOUR_SELECTED_APP --concurrency 5
```

After **separate consent to the target and judge budgets**, use a new directory:

```bash
uv run --no-sync python -m scripts.validation.databricks_app_quality \
  --profile YOUR_SELECTED_PROFILE --app-name YOUR_SELECTED_APP --concurrency 5 \
  --max-requests 2 --duration 10 --timeout 60 \
  --artifact-dir artifacts/app-quality-UNIQUE_RECORD --live --accept-paid-traffic
```

The bounded budget is one excluded target probe plus at most two measured target
attempts; up to two selected captures per scorer; two zero-retry judge-readiness
assessments on the **same captured probe**, then up to four quality assessments on
measured captures. Judging never reinvokes the target. The current frozen SDK quality
retry cap is two, so the maximum is **14 judge-provider attempts** (2 + 4 × 3), each
with a 2048 output-token cap and 60-second transport timeout. These are request/token
bounds, not a monetary ceiling or a hard authentication deadline. Native server
recovery and the target's internal calls remain operator controlled. The nominal
quality waiter is 1200 seconds to allow those separate phases; it does not make
trusted SDK/native code forcibly terminable.

The operator profile and fail-closed App resolver use the same gates as the smoke
helper. Native MLflow tracking uses `quality-mlflow.db` and `mlflow-artifacts/` under
the owned, protected directory, not an ambient remote tracking destination. Raw
answers, references, assessment rationales and MLflow traces are protected evidence.
`validation.json` and the summary expose only phase outcomes, counters and boolean
verdicts. Exit zero requires complete execution and all observed relevance/correctness
verdicts true. A valid negative verdict exits one with `quality_outcome=failed`, not
a transport failure; missing/errored assessments remain `unavailable`. This tiny
integration check does not establish judge calibration or general agent quality.
Use the helper as a separate CLI process: its operator configuration is task-local,
but the existing native evaluation backend changes MLflow's process-global tracking
selector. Tests explicitly restore that state; this helper is not an isolated
embedded-library execution API.
