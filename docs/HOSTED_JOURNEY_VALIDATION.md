# Hosted journey validation: evidence and next authorization

Reviewed October 8, 2026. Fresh results below are scoped to their exact journey;
the remaining matrix is a validation plan, **not** a blanket live pass.
Use the same endpoint boundary for LangGraph, OpenAI Agents, CrewAI, or any other
customer-owned implementation. Framework names below are examples, not a runtime
allowlist. The load runner never imports their graphs, agents or crews.

## Current short-smoke scope and fresh evidence

The user approved `agent-bricks-es-lg-1008`, `agent-bricks-es-oai-1008` and
`agent-bricks-es-crew-1008` in the selected `e2-demo-field-eng` workspace.
Notebook checks are **serverless only**; classic compute is explicitly deferred.
Do not create/start a classic cluster or use one as a fallback. The retained
classic sample describes a different journey, not coverage for this checkpoint.

Tests start with one excluded probe and one measured request at concurrency one.
After a successful compatibility gate, short smokes use no more than five users
and five measured attempts, with evaluation off. Workstreams serialize live model
traffic. No planner/judge calls, larger capacity campaign, trace-aware judging,
memory or TTFT validation is included in this load-only checkpoint.

| Classification | Current evidence | Remaining boundary |
| --- | --- | --- |
| Laptop → real local HTTP, OpenAI Agents | Initial canary `d1a5f8a6-3aac-4b9b-a5d2-fa77ed125730` passed. The later five-user direct/API matrix and the separate unchanged synchronous sample `main()` below passed | Streaming, memory and judging were not exercised by these load-only checks |
| Laptop → real local HTTP, LangGraph | Initial canary `41f9b79c-3289-4e50-929f-7193364d7d5d` completed two real calls/retrieval but failed agent cleanup; retained as failed. The later five-user direct/API matrix below passed with cleanup | Original failure stays failed; the later runs are new evidence, not a rewrite or replay of that receipt |
| Laptop → real local HTTP, CrewAI | Exact `crewai==1.15.25` installation blocked: public PyPI connection refused and configured Databricks mirror lacks the release | Isolated environment remains empty; no downgrade, alternate source build or Crew inference claimed |
| Laptop → deployed native App | Original revisions crashed; corrected revisions are RUNNING with authenticated `/status` and exact identity proof | Readiness is established separately from the bounded inference matrix; failed revisions remain retained |
| Serverless notebook prerequisites | Corrected run `526298221857181` / task `972949342784427`: driver runtime-OAuth, loopback and POSIX lock/fsync passed; zero inference | Independent subprocess runtime-OAuth failed with `ValueError`; Job success is not a blanket auth pass |
| Serverless notebook runner → deployed App | Intended cloud-runner sample, not yet verified | Agent stays in its App; worker-portable authentication remains a gate; no copied notebook/laptop tokens or notebook-hosted agent substitute |
| Offline contract checks | Native construction, configuration/status metadata, deliberate pre-provider rejection and docs checks | No successful model inference; do not count these as live passes |

Both successful local inference paths used `system.ai.gpt-oss-120b`, explicit
`/ai-gateway/mlflow/v1/responses`, low reasoning, a 512-output-token ceiling,
30-second model transport, 35-second handler deadline and 40-second runner HTTP
timeout. OpenAI model retries were zero. Four physical model calls were consumed
at the initial canary checkpoint, with no fixture completions. Latencies from one measured
request (LangGraph 561.72 ms; OpenAI Agents 485.18 ms) are functional observations,
not tail-latency or sustainable-capacity estimates.

The SDK configuration correction uses `WorkspaceClient(config=Config(...))`.
Pinned SDK 0.146.0's native `_BaseClient` treats a zero retry window as its
300-second default. Metadata reads therefore use a positive one-second retry
window, not a claimed zero-retry setting. OAuth refresh has separate semantics;
neither this window nor client cancellation establishes upstream abortion.
Preserve the startup-only local receipt and serverless run `166927894022579`
/ task `585536860269` (zero inference) as failed prerequisite evidence.

### Completed local-runner → HTTP-target matrix — October 8, 2026

Fresh validation used `scripts/validation/local_runner_http_target_journeys.py`,
the actual `examples/real_framework_agent.py` handler and the exact public
`examples/journeys/local_runner_http_target.py:request()` object. The target was
a separately owned real HTTP agent on the local machine; the notebook was not
an agent-hosting substitute. Direct execution used the native-async SDK. Optional
API execution used the synchronous typed remote SDK against an authenticated,
owned local EvalSurge REST server, with the same request object and sole Locust
engine. That first matrix did not execute the public sample's synchronous
`main()` wrapper; the separate entrypoint checks below now establish it.

All four normal and four cancellation runs used five users, at most five measured
attempts plus one excluded probe, a ten-second dispatch ceiling and 40-second
attempt timeout. The cap ended each dispatch window early; these were functional
smokes, not ten seconds of sustained load. Each had exactly six actual outbound
GPT-OSS model requests and six guarded completed Responses. This matrix adds
**48 physical model attempts / 48 completed Responses**, separately from the
earlier four canary calls. There were no model retries, tools, planner/judge calls,
fixture completions or model/API fallback. Evaluation stayed off; token-usage
coverage was 1.0, and nonstreaming JSON correctly supplied no TTFT.

| Framework / execution | Normal load run | Measured successes/errors | p50 / p95 latency (ms) | Protected report |
| --- | --- | --- | --- | --- |
| LangGraph / native-async direct | `f1dc050b-ce10-4cf5-8695-d1ed2ed7dcf3` | 5 / 0 | 670.85 / 816.57 | [JSON](/private/tmp/evalsurge-local-http-lg-load-direct-20261008.Afigzl/typed-report.json) |
| OpenAI Agents / native-async direct | `e28ebff0-b27c-4529-8962-635d31be8a4b` | 5 / 0 | 547.65 / 746.56 | [JSON](/private/tmp/evalsurge-local-http-oai-load-direct-20261008.ilClNi/typed-report.json) |
| LangGraph / typed remote → local API | `cded6670-af5d-455b-ba69-4fe0c62c3a72` | 5 / 0 | 559.45 / 584.19 | [JSON](/private/tmp/evalsurge-local-http-lg-load-api-20261008.gDQhQg/typed-report.json) |
| OpenAI Agents / typed remote → local API | `86e7d920-6b5f-4d66-bf21-b6cf69f8a6f8` | 5 / 0 | 593.41 / 690.98 | [JSON](/private/tmp/evalsurge-local-http-oai-load-api-20261008.8c4Mmv/typed-report.json) |

Every normal run observed five measured requests in flight, zero errors and a
terminal `completed` result. Five samples do not establish reliable tail latency,
a throughput comparison, capacity or a quality verdict.

| Framework / execution | Active-cancel/drain run | Terminal outcome | Protected report |
| --- | --- | --- | --- |
| LangGraph / native-async direct | `8204f883-cf83-45f5-ae6b-594351e75e69` | `cancelled`, 5 measured completions, 0 errors | [JSON](/private/tmp/evalsurge-local-http-lg-cancel-direct-20261008.pVfQe8/typed-report.json) |
| OpenAI Agents / native-async direct | `41cd0727-d52a-454b-ae63-f611e968a0f7` | `cancelled`, 5 measured completions, 0 errors | [JSON](/private/tmp/evalsurge-local-http-oai-cancel-direct-20261008.JzDwYk/typed-report.json) |
| LangGraph / typed remote → local API | `461c9bb3-8b11-4a06-907d-11b0ac95d339` | `cancelled`, 5 measured completions, 0 errors | [JSON](/private/tmp/evalsurge-local-http-lg-cancel-api-20261008.leY60l/typed-report.json) |
| OpenAI Agents / typed remote → local API | `99e2bea1-9d47-4294-879d-f8b91d8ec1dd` | `cancelled`, 5 measured completions, 0 errors | [JSON](/private/tmp/evalsurge-local-http-oai-cancel-api-20261008.rAbn7G/typed-report.json) |

Each cancellation was acknowledged as `cancellation_requested` while five measured
ASGI handlers were active, followed by completed drain and a terminal `cancelled`
report. All five requests had already been dispatched at the small attempt cap.
This verifies active lifecycle cancellation/drain, **not** suppression of an
unissued backlog, abortion of provider work, rollback of tools or cancelled model
costs. No provider request was replayed to expand this claim.

Four additional negative checks supplied an unsupported field to the real handler;
input validation rejected it before provider dispatch. These are **zero-inference
fail-fast checks**, not successful model runs. Every run had one failed probe,
`target_http_error`, measured load skipped, zero measured rows and zero outbound/
completed model requests, with inspectable typed failure reports.

| Framework / execution | Intentional fail-fast run | Protected report |
| --- | --- | --- |
| LangGraph / native-async direct | `1d8df9c7-4adf-4d10-afd9-c42fe98ca4e2` | [JSON](/private/tmp/evalsurge-local-http-lg-failfast-direct-20261008.HkuEmE/typed-report.json) |
| LangGraph / typed remote → local API | `faf73da9-b3e6-4e73-880f-5e5c36252526` | [JSON](/private/tmp/evalsurge-local-http-lg-failfast-api-20261008.Fk5CSt/typed-report.json) |
| OpenAI Agents / native-async direct | `6950bf7e-e59a-4ebf-b839-4a4f0fa4caf9` | [JSON](/private/tmp/evalsurge-local-http-oai-failfast-direct-20261008.CPI66G/typed-report.json) |
| OpenAI Agents / typed remote → local API | `b03ad02e-3c64-4c99-869b-46bf6517ef98` | [JSON](/private/tmp/evalsurge-local-http-oai-failfast-api-20261008.P8tykh/typed-report.json) |

All 12 scenarios had terminal status/result/waited-report/retrieved-report equality,
closed SDK contexts, drained native agent lifespans and closed listeners. API
scenarios also checked missing-key HTTP 401, authenticated typed retrieval, HTTP
200 for the static report shell and API shutdown. Retrieving the shell is not a
browser-rendering test. Protected report/receipt files are mode 0600 in private
validation-machine directories; the artifacts themselves are not committed.
The loopback servers are closed, so retained JSON—not a stale loopback URL—is the
handoff evidence. [The protected matrix inventory](/private/tmp/evalsurge-local-http-matrix-summary-20261008.ueOqkq/summary.json)
lists every receipt/report path and counter. All 12 passed the current metadata
classifier without any further model calls or changes to earlier receipts.

Source SHA256 identities for all 12: real helper
`300f9771e145156f3ba36385f31878a26e9fa34b3a43e2c897fa16fa2d236dc0`;
public request
`806adbf0fb9d4959202ba596308bd5c30374c8090770fef63520dd22d7569a85`.
Installed versions were LangGraph 1.2.12, OpenAI Agents 0.22.3, OpenAI 3.22.1,
Databricks SDK 0.146.0, MLflow 3.16.1 and Locust 2.46.6. No new dependencies or
external resources were introduced by this local matrix. It does not establish
deployed-App/notebook, CrewAI, streaming, trace, memory or judge coverage.

Focused pure configuration/status/constructor checks passed **59 tests in 0.95
seconds**; Ruff lint and formatting passed. No controlled provider-completion
suite or new CI was run by this workstream. See [the exact validation record](../VALIDATION.md#fresh-local-http-helper-matrix--october-8-2026).

### Actual synchronous HTTP sample entrypoints — October 8, 2026

The unchanged `examples/journeys/local_runner_http_target.py` was subsequently
executed as an actual child script for each real framework, not merely imported
for its request object. Each sample exited zero and printed JSON validated as
the public typed `Report`: passed excluded probe, five measured successes, zero
errors, peak concurrency five and token-usage coverage 1.0. Selection and bounds
remained the approved GPT-OSS/MLflow Responses route, 512 output tokens, zero
model retries, evaluation off and the public five-attempt/ten-second request.

| Framework | Run ID | p50 / p95 latency (ms) | Protected report |
| --- | --- | --- | --- |
| LangGraph | `bea314c3-fc3f-4830-8ce6-29e6b2a3381c` | 588.81 / 597.09 | [JSON](/private/tmp/evalsurge-local-http-main-20261008.1EGljR/langgraph/typed-report.json) |
| OpenAI Agents | `699fb8bc-b737-4339-a2d5-b32fad798ef8` | 556.50 / 602.17 | [JSON](/private/tmp/evalsurge-local-http-main-20261008.1EGljR/openai-agents/typed-report.json) |

Each made six physical model calls and six completed Responses: **12 / 12** in
this separate entrypoint batch; **60 / 60** across the local matrix and entrypoint
batches, excluding the earlier four canary calls. Agent lifespans/listeners,
SDK storage locks and preflight/load workers closed. Fixed relative artifacts
were kept under a private temporary working directory, not committed. Sample,
helper and coordinator/runner/SDK source hashes were unchanged throughout.
These are functional smokes, not stable tail latency, capacity, App, notebook,
streaming, memory or judging evidence. No failed paid preflight was replayed.

### App creation is not readiness

The native deployment commands exited zero and created the approved LangGraph
and OpenAI Apps with one MEDIUM instance each. Both subsequently crashed during
startup with a retained `RuntimeError`; no App inference was attempted at this
checkpoint. Deployment IDs are `01f1c388f0e01036acba9db2dd850a9b` (LangGraph) and
`01f1c38911271428a8019f96eeab4e78` (OpenAI). These links identify created resources,
**not successful load-test evidence**:

- [LangGraph App](https://agent-bricks-es-lg-1008-1444828305810485.aws.databricksapps.com)
- [OpenAI Agents App](https://agent-bricks-es-oai-1008-1444828305810485.aws.databricksapps.com)

The deployed handler hash is
`300f9771e145156f3ba36385f31878a26e9fa34b3a43e2c897fa16fa2d236dc0`; wrapper hash
`52f02e9146647af636d64b6775ecfcc2de70afed9601d4097b50d57cfcced04b`; wheel hash
`6adc059ef3b3ae2aa868f20a4470a4b52da16a6cdeb1a8b849ad390e97f016a3`.
Native CLI resource wiring changed `app.yaml`, and its post-deploy hashes are
retained separately. No App or store was deleted. Any corrected deployment must
retain this failure and receive its own source/readiness/inference record.

### Corrected native App readiness — October 8, 2026 (EDT)

The exact model-only `MODEL_SERVICE`/`EXECUTE` resource was attached to both owned
Apps using a resources-only update, preserving other settings. The model name
is injected through `valueFrom: model` and checked against the approved selection.
Current [official App Unity Gateway guidance](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/unity-gateway)
documents that resource; the installed Apps enum does not list the newer model
service, so raw native resource metadata was retained rather than trusting its
typed projection. No catalog-wide inference grant was introduced.

The original host mismatch is now established as bare-host platform spelling.
The guard accepts only the exact selected origin in bare-host or HTTPS form,
validates workspace/App/model selectors, and verifies actual selected-origin SCIM
response org and App principal. It does not accept arbitrary aliases or use an
inferred SDK workspace ID as API evidence. A subsequent wrapper revision failed
on an unsupported `Config.custom_headers` getter before inference; failed IDs
`01f1c38cdcbb1c7fbc6a424889829ef8` and `01f1c38cdd241d9ab50ae3d8fc502f1d`
remain preserved. Removing that getter and using the supported actual metadata
call corrected startup without weakening the identity checks.

| App | Ready deployment | Actual readiness |
| --- | --- | --- |
| LangGraph | `01f1c38db3f5165b98332e7c16cb1108` | RUNNING, authenticated `/status` 200, exact selected-origin/owner proof |
| OpenAI Agents | `01f1c38db4281b698aaac4c5aa8e6761` | RUNNING, authenticated `/status` 200, exact selected-origin/owner proof |

The native Runtime Stores opened; no memory, session history, tools, tracing or
automatic recovery is configured. At this readiness checkpoint all handler and
model counters were zero: no model call was used merely to obtain readiness.
The protected `*-readiness-identity-v3.json` files under
`/private/tmp/evalsurge-native-apps-20261008.ZdVXL2` retain the exact proof.
Shared handler SHA256 remains `300f9771e145156f3ba36385f31878a26e9fa34b3a43e2c897fa16fa2d236dc0`;
wrapper SHA256 is `ab2301d623a3f7d855a58bc6f41dc1f83114d0fdfff03ec0a949e65180cf9c31`;
identity guard SHA256 is `56987a31432bf778ccc5d7047f096ef3ef92a903b7a4175225ca7f1942e1b4d7`.
Five pure parser/native-SDK-interface checks and copied-runtime lint passed,
without stubbed authentication or model responses. Resources remain available;
runtime readiness alone is not successful inference or a capacity test.

### User-requested App traffic pause — October 8, 2026

The App workstream stopped before starting its newly allotted 52-call inference
matrix. It confirmed **0/52 additional physical model calls**, no scenario
executed and no live subprocess or invocation in flight. The ready Apps and
Runtime Stores were retained, not stopped or deleted. The zero handler/model
counters above are the latest recorded readiness observation, not a new read
at the pause. Retained resources may continue incurring charges while testing
is paused. Resume only after the user directs it; do not schedule an automatic
run or silently replay failed evidence. The saved
[handoff](SESSION_HANDOFF.md) and [serverless diagnosis](SERVERLESS_RUNNER_STATUS.md)
record the remaining gates.

## Retained discovery and preparation checkpoint (before live checks)

The explicitly approved laptop profile is `e2-demo-field-eng`, workspace
`https://e2-demo-field-eng.cloud.databricks.com`, workspace ID `1444828305810485`.
No other profile was selected, modified or used by this workstream.

Initial read-only CLI discovery on October 8 found 235 Apps and no `eval`-named
App. A later secure elevated refresh found 233 Apps and no EvalSurge/test-eval-ram
matches or collisions for `agent-bricks-es-lg-1008`, `agent-bricks-es-oai-1008`
and `agent-bricks-es-crew-1008`. Counts are point-in-time observations. The
agent-related Apps in that workspace were not selected, inspected as deployed
source, invoked or treated as substitutes. A current Databricks App journey needs
an exact user-selected existing App, or separately approved deployment names and
resource creation. Historical App evidence from another workspace is not evidence
that these resources exist here.

`databricks-gpt-oss-120b` and `databricks-gpt-5-4-mini` were both
`READY` / `NOT_UPDATING`. These are control-plane observations, not inference or
framework compatibility checks. Model-service metadata for
`model-services/system.ai.gpt-oss-120b` lists `mlflow/v1/chat/completions` and
`mlflow/v1/responses`; it does not advertise a native `openai/v1` API. No model
query was sent during this review.

The same metadata check for `system.ai.gpt-5-4-mini` also advertises native
`openai/v1/responses`, unlike GPT-OSS. A different model/route remains an explicit
operator decision, never an automatic fallback after failed GPT-OSS inference.

Sandboxed App/cluster reads initially reported a CLI credential-cache error.
Secure elevated reads with the same selected profile subsequently succeeded;
no reauthentication, profile switch or plaintext auth-storage workaround was
needed. The selected identity is active. No eligible current-user-owned or
EvalSurge-named classic cluster was found, running or stopped. An unrelated
cluster has not been selected, created or started.

The existing source environment contains OpenAI Agents 0.22.3, OpenAI 3.22.1,
LangGraph 1.2.12, MLflow 3.16.1 and Databricks SDK 0.146.0. CrewAI is not installed.
No dependencies, profile files, credentials, Apps, Jobs, clusters or Lakebase
resources were changed in this workstream.

## OpenAI Agents failure: root cause and safe next action

Retain failed run `965459df-81da-454e-9624-889d23aede1c`. Its real GPT-OSS streamed
preflight failed and measured load was skipped. Installed source establishes the
boundary:

- `agents/models/chatcmpl_stream_handler.py` forwards `delta.content` into
  `ResponseTextDeltaEvent(delta=...)`, then concatenates that value with text.
- OpenAI's `ChoiceDelta.content` and `ResponseTextDeltaEvent.delta` are string
  fields. The recorded provider response supplied structured reasoning/text blocks.
- The non-streaming converter also passes `message.content` to
  `ResponseOutputText(text=...)`. Merely changing to non-streaming is not a proven
  repair for the same Chat Completions response.
- `examples/framework_agent.py` explicitly selects the Chat Completions model and
  transport. Do not strip reasoning blocks, stringify lists, monkeypatch the SDK,
  retry another route, or silently replace the model.

The selected compatibility path is an **explicitly selected** native
`OpenAIResponsesModel` through the advertised MLflow Responses route, with its own
correct SDK client/base URL/model identifier and existing trace ownership. The
older App record in `VALIDATION.md` exercised this route successfully, but it does
not establish new-workspace evidence. The explicit Responses canary and fresh
local direct/API matrix above now supply that separate evidence for
`system.ai.gpt-oss-120b` in the selected workspace. No model/route fallback or
installed converter patch was used. A different model remains a separately
declared operator choice, not a relabeled fix or replay of failed GPT-OSS evidence.

The recorded failed Chat Completions run has not been rerun successfully.
It stays failed; success of the separately selected Responses path does not make
the old Chat Completions transport compatible.

`examples/real_framework_agent.py` contains native LangGraph, OpenAI Agents and
prepared CrewAI handlers for the JSON helper. The first two were executed in the
fresh local matrix; CrewAI remains uninstalled/unexecuted. OpenAI Agents uses
`OpenAIResponsesModel` and the native Runner, not the failed Chat Completions
converter. A customer-owned HTTPX response hook requires raw top-level
`status == "completed"` before Agents drops that field; completed message items
alone do not establish terminal provider status. The handler requires the same
guarded transport as the native client. No installed converter was patched.
Actual usage is retained only when supplied; Agents' normalized missing-usage
zeros are not presented as observed tokens.

The initial canary plan selected `system.ai.gpt-oss-120b` through
`/ai-gateway/mlflow/v1/responses` explicitly, low reasoning, 512 output tokens,
30-second model transports and zero provider/framework retries. One excluded
probe plus one measured attempt per framework at concurrency one admits six
target attempts and at most eight underlying model attempts (CrewAI at most two
per invocation): at most 4,096 output tokens. This was a planning ceiling, not a
claim that all three frameworks ran: LangGraph/OpenAI Agents each subsequently
executed two model calls; CrewAI executed none. The separately approved five-user
local matrix adds the 48 calls recorded above. Truncation remains a failed receipt;
no fallback or automatic token-limit increase is allowed.

The model transport is 30 seconds, customer-handler deadline 35 seconds and the
latest local benchmark attempt timeout 40 seconds. Disconnect/timeout/cancel
does not prove upstream abortion. OAuth
refresh lacks a hard overall deadline; the raw-response size check occurs after
buffering, not as a hard memory quota. No tool loop, memory, trace evidence,
streaming or TTFT is claimed by this stateless example.

The loopback factory requires the selected laptop profile. It is not an unchanged
App deployment entrypoint. A native App wrapper must reuse `build_handler` with
its own operator-configured App identity/model client and the same guarded
transport, never upload or try to resolve a laptop profile inside the App.

## Current server contract and Runtime Store ownership

Current official Databricks documentation recommends `DurableAgentServer` from
`databricks_agentkit`, in `databricks-agentbricks`, with `/api/invocations` for new
agents. MLflow AgentServer and LongRunningAgentServer `/responses` are documented
as legacy, with no removal date established here. This is not permission to delete
the compatibility adapters.

The synchronous invocation contract is the immediate App test. Streaming,
background/recovery behavior and shared session ordering are separate semantics.
The App's internal model API is independent of its public invocation API.

The documented `agentbricks deploy` flow provisions a dedicated Runtime Store
database in a Databricks-managed Lakebase project and reuses it on redeployment.
The documentation says customers cannot bind their own Lakebase project as that
Runtime Store. Do not apply the old legacy LongRunningAgentServer Lakebase setup
to a new DurableAgentServer deployment. Runtime invocation persistence is not
automatically agent conversation memory, custom checkpoints or trace export.
Provisioning any new App/store still requires separate resource authorization.

CrewAI's current docs distinguish native async `akickoff()` from thread-based
`kickoff_async()` (`asyncio.to_thread`). The prepared handler calls the real crew
and uses completed `CrewOutput.raw`, with request-local state/counters and a
two-model-call ceiling. CrewAI is still uninstalled and unexecuted. Official
metadata advertises 1.15.25 for Python >=3.10,<3.14; an isolated Python 3.12
environment with `crewai==1.15.25` and `openai==3.22.1` is proposed, not a resolved
compatible transitive lock. Public main-branch source is not pinned-version
runtime evidence. Require `CREWAI_DISABLE_TELEMETRY=true` before import and keep
tracing off for this basic sample. Do not install CrewAI/LiteLLM and their
transitive stack into the project just to claim framework coverage; the reviewed
isolated dependency setup is a separate consent and compatibility gate.

## Executable, bounded endpoint harness

`scripts/validation/hosted_journeys.py` supports direct generic `http-json`, direct
existing DurableAgentServer Apps and optional typed remote registered-target
execution. It defaults to a **no-network dry run** and never installs a framework,
deploys an App or imports customer agent code. Actual target inference is required
and operator-attested for live execution; source/model labels are declarations,
not automatic verification. A successful endpoint response alone cannot prove
which framework/model is deployed.

One invocation runs one scenario: `load`, `fail-fast` or `cancel`. A fail-fast
selection additionally requires `--intentional-rejection` and the exact expected
safe category via `--expected-preflight-code`, such as `target_http_error` for an
authorized deliberately rejected route. A negative scenario pass still means the
operational run failed as expected; it is never successful model inference.
Defaults are
concurrency 5, 30 seconds of dispatch, 30 seconds per attempt, at most five measured
attempts and one excluded probe: **at most six top-level target attempts**. Hard
harness ceilings are five users, 20 measured attempts, 180 dispatch seconds and
60 seconds per attempt. Evaluation is off, with zero planner/judge calls.
Provider/tool calls and native retries inside an agent invocation are not a dollar
quota; separately review target limits. Failed preflight should have zero measured
attempts. An incorrectly selected fail-fast endpoint may work, so its admitted
maximum remains six rather than claiming a one-attempt hard cap.

Dry direct HTTP plan, after starting your real handler with the optional serving
helper or bringing an already compatible endpoint:

```bash
uv run --frozen --no-sync python -m scripts.validation.hosted_journeys \
  --target http --framework langgraph --model YOUR_SELECTED_REAL_MODEL \
  --url http://127.0.0.1:9001/invoke
```

Dry App plan, using an exact existing App explicitly selected in this workspace:

```bash
uv run --frozen --no-sync python -m scripts.validation.hosted_journeys \
  --target app --framework openai-agents --model YOUR_SELECTED_REAL_MODEL \
  --profile e2-demo-field-eng --app-name YOUR_SELECTED_EXISTING_APP
```

Dry remote plan, using an already authorized EvalSurge service/registered target:

```bash
uv run --frozen --no-sync python -m scripts.validation.hosted_journeys \
  --target remote --framework crewai --model YOUR_SELECTED_REAL_MODEL \
  --service-url https://YOUR_AUTHORIZED_EVALSURGE_SERVICE \
  --connection-id YOUR_REGISTERED_TARGET --api-key-env EVALSURGE_SERVICE_KEY
```

Only after fresh explicit authorization, append `--live --accept-paid-traffic
--real-inference-attested --source-revision YOUR_DEPLOYED_SOURCE_ID --artifact-dir
/tmp/NEW_PRIVATE_DIRECTORY`. The artifact path must not already exist. No command
above selects or authorizes an actual App/model by placeholder substitution.
HTTP mode binds an unauthenticated endpoint; for authenticated custom HTTP targets,
use the ordinary SDK's exact operator-owned connection binding instead of putting
tokens into URLs/cases. Remote keys are read only from the selected environment
variable and never written to the receipt.

The receipt records independent phases, safe preflight codes, metrics and failures.
Matching IDs are recorded separately from parity: terminal statuses/phases, the
complete result payloads and report pages must agree before retrieval is counted
as verified. A nonterminal/inconsistent response cannot clear the remote-work
warning. Safe preflight evidence is persisted before subsequent retrieval, so a
transport failure cannot erase the earlier failure category. Cancellation records the acknowledgment
and terminal cancellation but deliberately leaves `inflight_cancellation_confirmed`
false: a `running` lifecycle alone is not evidence of an active model request. Use
the existing owned `DispatchObserver` in `unified_sdk_journeys.py` for that stronger
HTTP test; an external App needs equivalent target-side evidence. Cancel stops new
benchmark dispatch and drains; it does not promise cancellation of durable agent
background work. Remote failures/timeouts can leave service-owned work active and
the incomplete receipt says so; closing the SDK client does not cancel that work.

This generic existing-endpoint harness has **not** been run live or against controlled provider
responses. Its 23 pure parser/budget/pre-provider/native-DTO tests passed on October 8. They
do not establish successful endpoint integration, inference, cancellation or hosting.
The separate owned-real-helper harness and public HTTP request exercised in the
fresh local matrix are not a claim that this other script was executed.

## Remaining journey matrix and staged bounds

| Framework implementation | Laptop → generic HTTP | Laptop → actual App | Optional server → registered target | Notebook → actual App |
| --- | --- | --- | --- | --- |
| LangGraph | Fresh five-user native-async direct load, active-cancel/drain and zero-inference fail-fast passed; older cleanup failure retained | Created; runtime startup failed, no inference yet | Owned local API → registered HTTP target load/cancel/fail-fast passed; shared hosting and remote App targets are separate | Worker auth gate |
| OpenAI Agents | Fresh explicit Responses five-user native-async direct matrix passed; historical Chat Completions failure retained | Created; runtime startup failed, no inference yet | Owned local API → registered HTTP target load/cancel/fail-fast passed; shared hosting and remote App targets are separate | Worker auth gate |
| CrewAI | Exact 1.15.25 dependency unavailable; isolated environment empty, no inference | Approved name; source/deployment/live check pending | Real crew/provider environment needed | Unverified |

For each selected row, retain source revision, framework/provider versions, actual
model, hosting and runner location. Validate preserved nontrivial case inputs,
completion/failure, auth, case/request state isolation, and optional exact trace
correlation. Record real and controlled results separately. Do not treat the
generic HTTP endpoint as a deployed App substitute.

Start with one approved model/route compatibility check, then one load-only run
per selected journey. A proposed first bounded load batch across three frameworks,
two endpoint hostings and direct/optional-server paths is 12 runs × six target
attempts = **72 top-level attempts maximum**, not preapproved spend. Separate
fail-fast and cancellation scenarios would add at most six attempts each per
selected cell. This is the remaining broader proposal, not the separately
approved/executed 48-model-call local matrix above. Propose captured-answer quality validation separately with exact
scorer/model/dataset/reference IDs, one readiness assessment per selected judge
and explicit sampled-assessment caps. Trace-required scorers need verified
correlated probe evidence before measured load. No judging reinvokes the target.

Additional scope beyond the short smokes still needs exact selections:

1. Exact model/API route, source revisions and any CrewAI example dependency setup.
2. Existing App names or new App deployment names and managed Runtime Store creation.
3. Existing optional API host/registered targets and operator authentication.
4. Which cells/scenarios to run, per-run/overall request limits, model/tool token
   limits and acceptable spend; stop the batch after a failed model preflight.
5. Classic compute is deferred by the user's latest instruction. Only serverless
notebook checks are in scope; lack of serverless support is a blocker, not
permission for classic fallback.

The three names above are now approved for new native deployments; approval is
not evidence of creation. The reviewed shape is one MEDIUM instance and
one native-managed Runtime Store per App, with the same request-isolated real
handler reused locally and in the App. Keep resource revisions and source hashes
in protected receipts; cleanup requires an exact owned-resource decision.
The 72-attempt successful-load batch is a top-level target limit: a bounded CrewAI
executor may make two model calls for one target attempt. Count those separately
in the model-call budget, including probes, cancellation and mistakenly accepted
negative scenarios. Evaluation/model compatibility needs separate explicit
model selections and call limits rather than borrowing the load-only budget.

The existing serverless prerequisite notebook established driver runtime OAuth,
but independent worker runtime OAuth failed. Parent Job `584248337638691` / task
`1003312814916440` failed with kernel exit 3 and `No Experiment with id=1 exists`,
with no final receipt. A fresh read of that retained task output shows the missing
experiment during ASGI lifespan startup, `Application startup failed`, then exit
3. Installed Uvicorn source calls `sys.exit(STARTUP_FAILURE)` on failed startup,
with `STARTUP_FAILURE = 3`; this explains the recorded exit sequence, but does not
establish a successful live correction. The host-lifecycle/experiment harness
corrections were tested locally, not re-uploaded or rerun live. Do not claim notebook→App support,
cleanup, measured counts or inference from that failure. Reuse
`serverless_prerequisites.py` and `serverless_sdk_journeys.py`; the latter tests
notebook-driver HTTP/direct/loopback API, not an App. Never upload a laptop token
or silently switch profiles/compute to work around runtime auth.

The latest notebook harness additionally requires terminal status/phase, complete
typed result and report-content agreement for normal, fail-fast and cancellation
scenarios in direct and remote modes. Current SDK prerequisite source uses an
explicit 20-second HTTP timeout and a positive one-second metadata retry window,
not zero (which SDK 0.146.0 interprets as its 300-second default). OAuth refresh
has separate timing semantics. Driver runtime OAuth alone is not
proof of worker-portable OAuth: a regular subprocess lacks the injected notebook
context needed by SDK `runtime-oauth`. Direct notebook→App needs an approved
operator-owned portable credential mechanism before any such journey is claimed.
Strengthening that existing harness does not establish use of the new real
Responses/helper sample or CrewAI notebook coverage; those still require explicit
source/environment integration and live execution.

### Current runner-only serverless sample — prepared, authentication-blocked

The explicitly named
[`serverless_runner_databricks_app_target.py`](../examples/journeys/serverless_runner_databricks_app_target.py)
and [`serverless_runner_app_target.py`](../scripts/validation/serverless_runner_app_target.py)
keep all agent/model execution in an already deployed App. The notebook hosts
only EvalSurge/Locust. They are **not live-validated or ready for Job submission**
in the current selected authentication configuration. The corrected environment-5
prerequisite run `526298221857181` / task `972949342784427` established driver
OAuth, loopback and POSIX lock/fsync, but independent worker runtime-OAuth failed.
That probe made zero inference calls and did not test a deployed App.

The public App binding is profile-only and rejects ambient notebook destination/
identity overrides. Driver-native OAuth is not an independent worker credential.
A supported operator-owned portable OAuth design, ADR/maintainer review and
verified deployed readiness are required before an initial one-probe plus
one-measured-invocation smoke, concurrency one and evaluation off. No new live
notebook-to-App Job, token bridge, identity or classic compute was created.
Notebook API execution, fail-fast, cancellation, report retrieval and runner
cleanup remain unvalidated for this topology. Historical notebook-hosted HTTP
helpers remain diagnostic-only and must not substitute for the intended journey.

## Primary sources checked

- [Databricks Agent Server](https://docs.databricks.com/aws/en/agents/deploy/agent-server)
  and [agent query contracts](https://docs.databricks.com/aws/en/agents/query-llms).
- [OpenAI Agents model guide](https://openai.github.io/openai-agents-python/models/)
  plus installed SDK stream/converter and OpenAI event type source, versions above.
- [CrewAI async execution](https://docs.crewai.com/en/learn/kickoff-async).
- Repository `VALIDATION.md`, `examples/framework_agent.py` and existing validation
  harnesses. Fresh discovery/metadata is distinguished from retained inference.
