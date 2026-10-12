# Native agent-App templates: hosting the target, not the load generator

These prepared projects host the same actual LangGraph, OpenAI Agents or CrewAI refund
handler used by the local HTTP sample, behind `DurableAgentServer` and its
`/api/invocations` contract. They are **not deployed or live-validated templates**.
Source/configuration tests do not demonstrate model inference, App authentication,
Lakebase readiness or dependency installation. A separate October 11, 2026
CrewAI/macOS dependency installation passed compatibility checks, but failed its
advisory gate; that prerequisite is not native App deployment or live validation.

| Project | Agent framework | Agent serving contract | Current evidence |
| --- | --- | --- | --- |
| `langgraph/` | Actual LangGraph graph | Native `/api/invocations` | Prepared; live validation not run |
| `openai_agents/` | Actual OpenAI Agents Runner | Native `/api/invocations` | Prepared; live validation not run |
| `crewai/` | Actual CrewAI handler | Native `/api/invocations`; supported deployment route unresolved | macOS install compatible; advisory blocked; native deployment/live validation not run |

EvalSurge itself belongs in a separate runner environment: local Python,
serverless notebook or an EvalSurge runner App. These agent projects do not
install EvalSurge, Locust or the runner stack. Binding an agent App from that
runner uses `Agent.databricks_app(..., protocol="databricks-agent-runtime")`.
The framework is an example implementation, not an EvalSurge target allowlist.

## Prepare the reviewed source

From a reviewed repository checkout, choose one template and a new staging
directory. For example:

```bash
uv run --frozen --no-sync python examples/journeys/agent_apps/stage_shared_sources.py \
  --template langgraph \
  --repository-root /absolute/path/to/EvalSurge \
  --destination /absolute/path/to/new-langgraph-agent-app
```

Use `--template openai_agents` or `--template crewai` for the other projects.
CrewAI has no false framework-label `agent.toml`; its supported native deployment
route is unresolved with the inspected CLI. See [its prerequisite review](crewai/README.md).
The preparation step copies
only public source/configuration files, checks the reviewed shared handler/wrapper
SHA-256 values, and writes `staged_source_manifest.json`. Existing destinations,
changed shared source and symlinks are rejected. It makes no network or model call.
The real handler is staged as `real_framework_handler.py`; no historical/private
App bundle, Runtime Store identifiers, wheel or credentials are copied.

Before deploying the staged project:

1. For the two managed-CLI projects, replace the `agent.toml` App-name placeholder
   with an explicitly selected name. CrewAI remains source preparation only until
   a supported framework-neutral deployment manifest/CLI is verified; do not label
   its implementation LangGraph or OpenAI merely to pass schema validation.
   Replace the `app.yaml` workspace-origin placeholder with the exact approved
   `https://...cloud.databricks.com` origin. It must match App-injected
   `DATABRICKS_HOST`; a local profile or notebook token is not used by the agent.
2. Resolve/audit this separate Python 3.11 environment through the approved package
   registry, freeze its lockfile and record the resulting dependency/artifact hashes.
   Pins describe source-reviewed selections, not an audited release lockfile
   or a claim of newest compatible dependencies. CrewAI's isolated macOS closure
   installed compatibly but failed its advisory gate; Linux/App installation and
   native deployment remain unverified. Runtime 0.4.0 declares
   `databricks-sdk>=0.124.0`; the selected SDK candidate is 0.148.0, matching the
   inspected native environment rather than the separate runner's SDK version.
   Do not install the current EvalSurge runner extra into this agent environment.
3. For LangGraph/OpenAI Agents, review the `agentbricks deploy` route against the
   selected installed CLI. It provisions and wires the native Runtime Store;
   do not independently create, bind or change that store, copy Lakebase identifiers
   from another deployment, or substitute process-local storage. Review generated
   App configuration and the managed resource's permissions/lifecycle before testing.
   CrewAI cannot bypass its unresolved CLI gate with generic `apps deploy` plus
   hand-entered store references.
   All three templates require the managed branch/database/username configuration
   before native construction; local, incomplete and placeholder store selections
   are rejected. This configuration check does not establish store readiness.
4. Bind the explicitly selected model service as App resource `model` using
   `MODEL_SERVICE` and `EXECUTE`. `MODEL_SERVICE_NAME` uses that resource's `valueFrom`.
   Databricks injects this App's own OAuth client credentials; never paste tokens,
   client secrets or a laptop profile into `app.yaml` or benchmark requests.
5. Verify App ingress permissions and a bounded real invocation with the exact
   approved caller profile. Then run the selected EvalSurge journey against this
   actual deployed App. Record failures and provider evidence before claiming the
   matrix cell passed; prepare-only/import/config checks are not live tests.

No deployment or package install is performed by the staging helper. The files
deliberately fail validation while operator selections remain placeholders.
For the managed `system.ai` model-service route, the **single-resource shape** is:

```json
{
  "name": "model",
  "uc_securable": {
    "securable_full_name": "system.ai.REPLACE_WITH_EXPLICIT_MODEL_SERVICE",
    "securable_type": "MODEL_SERVICE",
    "permission": "EXECUTE"
  }
}
```

This is an operator-review example, not a command to create/update resources.
Merge it using the reviewed deployment route; do not replace an App's complete
resource list or remove the managed Runtime Store resources. A differently hosted
model endpoint needs separately reviewed identity/resource/API semantics.
The inspected SDK 0.146/0.148 typed enums do not expose `MODEL_SERVICE`; use the
reviewed raw CLI/API resource contract rather than an invented typed constructor.

Consult the official [native agent server guide](https://docs.databricks.com/aws/en/agents/deploy/agent-server),
[agent invocation guide](https://docs.databricks.com/aws/en/agents/query-llms)
and [agent CLI reference](https://developers.databricks.com/docs/agents/cli)
before a live deployment; the inspected native namespace is `databricks_agentkit`
from `databricks-agentbricks==0.4.0`, not the deprecated runtime namespace.

## What these small agents do

Each first attempt accepts exactly one user message with nonblank text of at most
512 characters. Agent-specific extras, recovery attempts and unsupported messages
fail before inference. The handler executes the selected real framework and actual
model, permits one LangGraph/OpenAI call or at most two CrewAI calls, caps output
at 512 tokens per call, disables provider retries, uses a 30-second
per-call deadline and a 35-second whole-handler deadline, and accepts only a
completed nonstreaming Responses answer. No canned answer or fallback exists.

The synthetic policy is the local handler's policy: opened items cannot be
refunded; unopened items can be refunded within 30 days. Use its authoritative
reference only when exercising this sample, never for an arbitrary production
agent. EvalSurge evaluation remains off by default; explicit captured-answer
judging is configured separately in the runner, with its own judge provider.

Authentication/discovery, HTTP transport and native completion parsing are part
of observed invocation latency; costs are not subtracted. App OAuth refresh uses
the SDK on an owned thread off the asyncio event loop. Requested cancellation,
including repeated cancellation, propagates only after that work settles and takes
precedence over a later worker failure. SDK discovery/refresh can delay cleanup
beyond a requested handler deadline; this is not a hard authentication timeout.
Threads/CPU/network can still contend.
These prepared sources do not certify generator accuracy, zero observer effect,
sustainable capacity, native streaming/TTFT or a trace-aware evaluation path.
Returning provider-present usage from the agent is not evidence that the current
native EvalSurge adapter extracts App output tokens into the report.

The native invocation/session IDs remain correlation labels. This example reads
no session history, creates no conversational memory and registers no recovery
handler, so automatic crash recovery/reinvocation is disabled. The managed
Runtime Store can still retain invocation payloads/results/events: inspect its
permissions, retention and cleanup separately. Native storage is not evidence
that MLflow traces are exported. OpenAI Agents' own sensitive-data tracing is
disabled; this is not a claim about all platform/provider logs or retention.

The intentional `__evalsurge_fail_preflight__` message raises before a model call.
Record such fail-fast tests as **intentional pre-provider failure**, separately
from successful real-model tests. Long-running sessions, tools, recovery,
delegation, browser interaction and conversational memory are outside this sample.
