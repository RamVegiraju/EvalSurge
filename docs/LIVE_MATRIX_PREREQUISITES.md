# Live matrix execution checklist

Updated October 12, 2026. This supplements [runner/target validation](RUNNER_TARGET_VALIDATION.md)
with exact dependency gates and the bounded smoke approval. Fresh October 12
installed-wheel evidence covers four basic local-runner cells out of six target
journeys. Runner-App installation/execution has not passed; notebook work is
deferred. Historical broader inventories, failed checks and prepared sources
remain below. The initial inspection made no model calls; subsequent successful
installs and actual-model smokes are recorded in
[the current live evidence](LIVE_MATRIX_RESULTS.md). See the fresh checkpoint
before using historical two-cell or twelve-cell counts.

## Fresh readiness and completed cleanup — October 12

The reviewed `0.2.1.dev2026101202` wheel (SHA256
`a1a58a4513c4659aee41f9c5570bbcca6da371b4b185b629e7842be4eac23285`)
passed isolated pip base/local/server installs and four actual-model basic
smokes: LangGraph/OpenAI Agents, each local HTTP or existing deployed App,
with a local installed-wheel runner. Each smoke used one excluded probe and one
measured request, concurrency one, evaluation off and actual
`system.ai.gpt-oss-120b`; no fixture substitution occurred.

The two exact existing Apps were started only for the authorized validation.
Verified source/deployment/resources remained unchanged; post-traffic counters
per App were two handler/model attempts, two completed model responses, no model
errors and no active handlers. Both starts were stopped and final confirmation
at **2026-10-12 17:23:32 UTC** found **STOPPED / UNAVAILABLE**. Resources, grants,
profiles and managed stores were retained. Restart and fresh readiness are
necessary before any subsequently authorized traffic; successful historical
deployment status is not current readiness.

Aggregate consumption is **16 target attempts / 12 model calls**, including
prior retained traffic and the two fresh intentional pre-provider failed probes
that made zero model calls. **20 target attempts / 36 model calls remain**
under the original 36/48 ceiling; there is no new lease. Quality, cancellation,
current-template deployment, capacity and zero-overhead claims remain unverified.
CrewAI's two basic cells remain blocked. Protected receipt roots are
`/private/tmp/evalsurge-local-only-20261012.D2MG3y/` and
`/private/tmp/evalsurge-target-readiness-20261012.RxUvhu/`.

The dedicated `load-test` runner App is not validated by these local-to-App
passes. Its denied registry access, reviewed native identity, installation and
protected-export gates remain separate. Notebook work is deferred. Any renewed
runner-App milestone must preserve these gates and the already consumed lease,
not treat the historical twelve-cell proposal as additional authorized traffic.

## Validated installation scope: local runners — October 12

The six local-runner cells cover LangGraph/OpenAI Agents/CrewAI, each served over
local HTTP or on a deployed Databricks App. Install the reviewed `[local]` wheel
in the runner environment; agent framework dependencies belong to the separate
agent environment. The simple SDK needs no benchmark-submission API server.

Retain the selected `e2-demo-field-eng` profile and aggregate ceiling of 36 target
attempts / 48 model calls; this narrowed scope is not a fresh lease. Each ready
basic cell uses one excluded probe plus one measured request, concurrency one,
evaluation off, zero retries and at most 512 output tokens per model call. Failed
or uncertain attempts consume the same allowance. Public five-measured-request
tutorials must not be run unchanged under this reduced validation allocation.
App targets still need verified source, model bounds, credentials and running
compute. No newly created App, grants, Lakebase, or public endpoint is authorized
merely by installing the runner package. CrewAI retains its advisory gate.

The October 12 read-only upstream recheck found CrewAI 1.15.27 now requires
`chromadb~=1.5.9`. The approved registry did not list that CrewAI release, and
the current ChromaDB 1.5.9 release still matches four active high/critical GitHub
advisories with no first patched version listed. A newer CrewAI version therefore
does not clear the dependency gate. Keep the failed 1.15.23 audit; no installation,
security exception or incompatible override was approved by this recheck. See
[the CrewAI prerequisite details](../examples/journeys/agent_apps/crewai/README.md).

The runner-App registry denial, volume/export setup, and ADR 0019 amendment review
are separate historical/unresolved work, not local-runner installation gates. Preserve the
following records rather than deleting resources or relabeling earlier failures.

## Historical local/App-runner approved scope

The user selected workspace/profile `e2-demo-field-eng`, runner App `load-test`
and exact CrewAI `1.15.23`, and approved at most **36 target attempts / 48 model
calls**, concurrency one, evaluation off and at most 512 output tokens per model
call. This is one aggregate smoke lease, not permission to repeat earlier leases,
restore deferred notebook scope, ignore failed security/authentication gates or activate
judges. Failed and commit-unknown attempts consume the same allowance. The full
controlled-inference regression-suite exception was disclosed and approved
separately; fixture completions never establish a live matrix cell.

The twelve combinations in that historical scope were four per framework: local→HTTP,
local→App, runner App→HTTP and runner App→App. Notebook→App is deferred by the user;
notebook→HTTP remains an optional retained sample outside this scope. Runner App→HTTP requires an
explicitly approved reachable HTTPS origin; no tunnel or public exposure is
authorized. Only the two local→HTTP LangGraph/OpenAI Agents basic smokes passed;
the other ten active cells and separately budgeted quality/cancellation scenarios
remain pending their gates.

## What can be reused

The already selected workspace/profile is `e2-demo-field-eng`; do not select
another profile. Historical agent Apps are `agent-bricks-es-lg-1008` and
`agent-bricks-es-oai-1008`. Their initial stopped/unavailable observations are
recorded in the validation guide; old successful deployments do not establish
current inference readiness. The target model service `system.ai.gpt-oss-120b`
was used under the current approved smoke lease. The historical judge
`databricks-gpt-5-4-mini` is not activated by the evaluation-off approval and
requires its own allowance.

A historical October 11 exact-profile read confirmed both historical target Apps were
still `STOPPED` / `UNAVAILABLE`, despite retained `SUCCEEDED` deployment records.
At that checkpoint the runner shell had no active deployment or declared resources. No target/model
call, compute start, deployment or grant accompanied this metadata check; all
three Apps still need their applicable readiness gates before traffic.

The selected `load-test` App has its service-principal client UUID resolved and
exact target `CAN_USE`, volume `READ_VOLUME` / `WRITE_VOLUME`, and catalog/schema
traversal verified. The October 12 disabled runtime deployment failed during
dependency installation, before startup. A separate stdlib diagnostic found
Python 3.11.17/Linux and approved-index HTTP 403; it is not a benchmark or installed
EvalSurge runtime. Compute is confirmed `STOPPED`; registry/platform access must
be resolved before another full installation attempt. Live native OAuth,
protected export and runner-App cells remain unverified. This does
not supply serverless notebook credentials; none are needed for the current
local/App milestone. Native runner-App mode uses the App's injected service
principal, not an exported notebook or user token. On October 12 the user-approved
managed volume `ram_artifacts.evalsurge_validation.runner_artifacts` was created.
Its runner-specific read/write grants are now verified; existing catalog administration retains inherited
`ALL_PRIVILEGES` and `MANAGE`. No broad data-reader grants were added, but this is
not owner-only storage. Live protected export remains unverified. The original
private contract was approved, but ADR 0019's October 12 workspace-ID amendment
still requires explicit designated maintainer acceptance before deploying the
new `0.2.1.dev2026101201` artifact. No Lakebase store is required for
this one-shot runner.

The inspected checkout environment contains Locust 2.46.6, Databricks SDK 0.146.0,
MLflow 3.16.1, LangGraph 1.2.12, OpenAI Agents 0.22.3 and OpenAI 3.22.1.
Retained October 8 framework environments use Python 3.11, SDK 0.148.0 and
MLflow 3.17.0. They are different artifacts, not evidence for installing the
current reviewed wheel. The initial CrewAI inspection was uninstalled. The
subsequent approved isolated CrewAI `1.15.23` install now contains 162 hash-checked
distributions and passes its dependency check, but ChromaDB `1.1.1` failed the
retained advisory audit. Inference is blocked, not established by imports. See
[the exact CrewAI prerequisite record](../examples/journeys/agent_apps/crewai/README.md).

| Prepared source | Reusable boundary | Remaining work |
| --- | --- | --- |
| `examples/real_framework_handler.py` | Standard-library-only import, canonical actual stateless framework handlers and validated completed-answer DTO | Install each exact framework environment and validate actual inference; source preparation alone establishes neither |
| `examples/real_framework_agent.py` | Backward-compatible optional EvalSurge serving bridge for LangGraph/OpenAI Agents | Start with exact approved model/profile; run against reviewed wheel |
| `examples/crewai_agent.py` | Independent customer-process `/invoke` endpoint without EvalSurge imports | Isolated install passed; resolve the failed advisory gate before actual model calls |
| `scripts/validation/local_runner_http_target_journeys.py` | Local direct HTTP load, pre-provider rejection and active cancellation | Existing fixed request uses five measured attempts; do not count it as the one-attempt matrix budget below |
| `scripts/validation/hosted_journeys.py` | Existing native agent App, direct execution, fail-fast/cancel and typed retrieval | Exact deployed contract/source and its scenario budget must agree |
| `examples/journeys/serverless_runner_databricks_app_target.py` | Retained installed-package notebook runner targeting deployed Apps | Deferred by user October 11; earlier install/authentication failures remain evidence, not active release gates |
| `examples/journeys/app_runner/` | Private one-shot direct runner App, no benchmark submission API | Approved dedicated App, explicit native App-runtime M2M or selected portable-profile compatibility, and protected export permissions |
| `scripts/validation/databricks_app_quality.py` | Native captured-answer relevance/correctness judging | Existing legacy/current protocol selection, judge profile/access and separate quality lease |

Private historical native App bundles and CrewAI drafts can inform a review but
are not public deployment examples. Newly prepared native target projects must
be deployed and tested against their exact dependency artifacts before any live
compatibility claim. Stage the explicitly reviewed hosting entrypoint and
canonical handler together; never upload a private preparation directory,
credential source, environment/cache or raw evidence as App source.

Prepared native source now exists for all three frameworks. CrewAI's deployment
route remains **unresolved**, not a manual Runtime Store provisioning recipe.
The inspected `databricks-agentbricks==0.4.0` and `0.5.0` project parsers require
a framework and accept only `langgraph`/`openai`; actual parser checks reject CrewAI and an
omitted framework. Current Agent Server guidance assigns Runtime Store provisioning
to `agentbricks deploy`, not to a caller creating or binding a store independently.
Verify a supported framework-neutral manifest/tooling version or platform guidance
before deploying this native CrewAI source. Do not relabel the framework or treat
a generic App upload as evidence of a supported durable native deployment.

## CrewAI dependency decision

Read-only inspection of the approved registry on October 11 exposed **1.15.23**
as its highest observed stable CrewAI version. The previously selected 1.15.26
was not exposed; prereleases are not substitutes. Candidate wheel metadata
requires `crewai-core==1.15.23`, `crewai-cli==1.15.23`, Python `>=3.10,<3.14`,
OpenAI `>=2.30.0,<3` and Pydantic `>=2.11.9,<2.13`. This is approved-registry
metadata provenance, not a claim that it is the latest public release.

EvalSurge requires Pydantic `>=2.13.5`; its direct-runtime extra requires OpenAI
3.x. Accordingly **do not install CrewAI into the runner environment**, or
silently downgrade it. `real_framework_handler.py` now isolates customer framework
code from EvalSurge; `crewai_agent.py` serves its declared HTTP contract without
EvalSurge or runner imports. The old helper remains a compatibility bridge, not
the standalone CrewAI installation path. Pure import/DTO/pre-provider checks
verify only this boundary. The approved isolated `1.15.23` closure subsequently
installed and passed `uv pip check`, but its ChromaDB `1.1.1` audit failed with
four distinct advisory IDs. No native CrewAI or real-inference success is
established by source/imports. Obtain a reviewed compatible fixed dependency route
or an explicit security exception before inference; do not suppress findings,
force an out-of-range dependency, bypass the registry or relabel its provenance.
The [CrewAI record](../examples/journeys/agent_apps/crewai/README.md) retains exact
versions, API signatures and failed advisory evidence.

## One approval manifest to unblock execution

Record these selections privately, without putting secrets into the manifest:

- Exact current reviewed EvalSurge version/SHA256; target source revisions,
  protocols and framework dependency artifacts, including the CrewAI decision.
- Existing selected workspace/profile; approved target model/judge resources;
  start/deploy permission for each exact target App and the dedicated runner App.
- Three approved reachable HTTPS origins for separately hosted HTTP agents when
  cloud runners are used. Laptop loopback is not reachable; no tunnel or public
  exposure is implied by this request. Select explicitly authorized unauthenticated
  ingress or the operator-owned bearer environment-variable reference supported
  by the runner samples. Provision the secret separately in each eventual worker;
  do not paste its value into the manifest, request, source or chat. Current pure
  binding checks establish neither token availability nor authenticated ingress.
- Dedicated runner App→App may explicitly
  use `app_auth="app-runtime"` with the selected workspace, runner App
  service-principal client UUID and declared target App resource (`CAN_USE`);
  a portable profile remains an explicit compatibility alternative. Select the
  approved export volume `ram_artifacts.evalsurge_validation.runner_artifacts`
  and recheck its access policy before launch. It was created only after exact
  user approval; runner grants and deployment are not established by creation.
  Provision secrets through approved
  operator channels, never request fields.
- A unique expiring lease, scenario/cell list and invocation/model/output/judge
  bounds. Keep successful, failed and commit-unknown attempts in the same ledger.

## Current basic smoke and separately unapproved scenario proposal

Each basic cell uses one excluded inference probe and one measured attempt,
concurrency one, evaluation off, no provider retry or tool/delegation/memory calls,
and at most 512 output tokens **per model call**. The twelve active cells exclude
notebook execution and require approved HTTPS for runner App→HTTP. They need at
most 24 target attempts / 32 model calls before accounting for already consumed
allowance; the aggregate approved ceiling remains 36/48, not a fresh lease.
LangGraph/OpenAI Agents
permit one model call per invocation; the CrewAI custom handler permits at most
two. Verify those bounds in the actual deployed source and disable recovery/replay
before counting an App invocation as a bounded model attempt.

The table below retains the earlier fifteen-cell scenario proposal as historical
budget arithmetic. Its three notebook cells are now deferred; it does not authorize
notebook execution or additional quality/cancellation traffic.

| Historical scenario | Target attempts | Model attempts | Target output-token ceiling | Judge attempts | Approval |
| --- | ---: | ---: | ---: | ---: | --- |
| Basic load across 15 cells | 30 | 40 | 20,480 | 0 | Within aggregate approved 36/48 smoke ceiling; unresolved gates still apply |
| Separate active cancel/drain across 15 cells | 30 | 40 | 20,480 | 0 | Additional traffic not approved by the basic smoke lease |
| Intentional pre-provider rejection across 15 cells | 15 | 0 | 0 | 0 | Separate scenario record; no model calls |
| Explicit quality in six representative local-runner cells | 18 | 24 | 12,288 | 84 | Judge/quality traffic not approved |
| Total of current basic plus unapproved proposals | 93 | 104 | 53,248 | 84 | Not a combined execution authorization |

The earlier eighteen-cell proposal is historical and superseded by the narrower
requested inventory. Its 36/48 arithmetic is not a requirement to spend the
entire currently approved ceiling or permission to restore excluded cells.

The six quality cells cover each framework/target-host pair with one probe and
two measured captures. Relevance and correctness use authoritative synthetic
refund facts: two zero-retry readiness assessments and four capture assessments,
each allowing two additional retries, yield at most fourteen judge attempts per
cell. At 2,048 output tokens/attempt, their combined judge ceiling is 172,032
tokens. Judging never reinvokes the target. Automatic planning is excluded from
this budget; it needs its own frozen model, scorer set, retry/token allowance and
readiness evidence.

These are output/attempt bounds, **not input-token or dollar quotas**. Use the
published five-/ten-second dispatch windows and explicit target timeouts; short
dispatch does not cancel upstream work or limit cleanup/metadata wall time.
Serialize paid traffic until gates pass. If cancellation loses a race to natural
completion, keep it unverified and seek a new lease instead of repeating it.
Stop at the first failed install/auth/protocol/inference/judge/evidence gate.

Primary serving references: [current Databricks Agent Server](https://docs.databricks.com/aws/en/agents/deploy/agent-server),
[CrewAI custom LLMs](https://docs.crewai.com/en/learn/custom-llm) and
[serverless dependencies](https://docs.databricks.com/aws/en/compute/serverless/dependencies).
The load-testing skill's legacy endpoint/Locust pin and fixture suggestions are
not adopted: preserve the repository's one Locust engine and real-inference policy.
