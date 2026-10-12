# Fresh runner/agent evidence — October 12, 2026

## Fresh installed local-runner evidence: four of six basic cells passed

The reviewed **0.2.1.dev2026101202** wheel passed four fresh real-model basic
smokes on October 12. Load originated in a separate **local pip-installed
environment**, not a notebook, runner App or benchmark-submission API server.
The six-cell local-runner inventory contains three example frameworks, each
hosted over HTTP or on a Databricks App; the two CrewAI cells remain blocked.
`[local]` selects the unchanged direct-execution dependencies; `[server]` remains
a compatible extra name.

```text
evalsurge-0.2.1.dev2026101202-py3-none-any.whl
SHA256 a1a58a4513c4659aee41f9c5570bbcca6da371b4b185b629e7842be4eac23285
```

Fresh pip **base, local and server** installations passed outside the checkout,
using the approved package source and exact locked artifact hashes. Installed
imports, request construction, CLI/sample help and dependency checks made zero
agent/model calls. This is macOS installation evidence, not public-PyPI
publication, latest-dependency resolution or a Linux/runner-App installation.
Private provenance remains under
`/private/tmp/evalsurge-local-only-20261012.D2MG3y/pip-reviewed-install/` and
`pip-runner-evidence/`. See [installation](INSTALLATION.md).

All four positive cells used the explicitly selected `e2-demo-field-eng` profile,
actual **`system.ai.gpt-oss-120b`** inference through
`/ai-gateway/mlflow/v1/responses`, zero provider retries and at most 512 output
tokens per call. Each used one excluded inference probe plus **one measured
request**, concurrency **1**, a **10-second** dispatch ceiling and evaluation
**off**. No fixture completions, mocked inference transport, fake agents,
planner, judge, tool or memory calls were used.

| Actual framework | Target hosting | Probe / measured requests | Model attempts / completed responses | Single measured latency | Run ID |
| --- | --- | ---: | ---: | ---: | --- |
| LangGraph | Local HTTP | 1 / 1 | 2 / 2 | 666.392 ms | `8177940b-259d-4516-aac3-22eaed70af92` |
| OpenAI Agents | Local HTTP | 1 / 1 | 2 / 2 | 435.451 ms | `9c58618b-4382-46e0-9fc9-23e26b431676` |
| LangGraph | Existing Databricks agent App | 1 / 1 | 2 / 2 | 1371.096 ms | `f4ea3175-34f0-404d-94af-96556a3363ac` |
| OpenAI Agents | Existing Databricks agent App | 1 / 1 | 2 / 2 | 1441.589 ms | `e0c5e19f-e081-44af-9a1a-361a49b70987` |

Every measured request succeeded, with zero load errors, typed
status/result/report agreement, content-free summary retrieval and observed SDK
and worker cleanup. HTTP agent lifespans/listeners closed. Journals drained,
with zero writer failures/backpressure and `measurement_complete=true`.
The protected reports and safe consolidated receipt remain under
`/private/tmp/evalsurge-local-only-20261012.D2MG3y/`; see
`milestone.safe.json`, `ledger.0002.safe.json`, `app-langgraph/receipt.safe.json`
and `app-openai/receipt.safe.json`. Full reports are protected artifacts, not
committed example data.

### Existing App identity and cleanup

The App targets were the real retained managed deployments:

- [LangGraph: agent-bricks-es-lg-1008](https://agent-bricks-es-lg-1008-1444828305810485.aws.databricksapps.com), deployment `01f1c38db3f5165b98332e7c16cb1108`.
- [OpenAI Agents: agent-bricks-es-oai-1008](https://agent-bricks-es-oai-1008-1444828305810485.aws.databricksapps.com), deployment `01f1c38db4281b698aaac4c5aa8e6761`.

Readiness and post-traffic checks verified unchanged immutable runtime/handler
bytes, source, deployment, declared resources, identity, model bounds and package
versions. Each App's observed counters increased by **2 handler attempts / 2
model HTTP attempts / 2 completed model responses**, with **0 model errors / 0
active handlers**. Counters are corroborating execution evidence, not billing
receipts. Both authorized compute starts were stopped afterward. Final
confirmation at **October 12, 2026, 17:23:32 UTC** found both **STOPPED /
UNAVAILABLE**, with deployment IDs and resources unchanged. No App, source,
grant, profile, managed store or historical evidence was deleted.

The agent Apps still run source version
`20261008-shared-real-framework-identity-v2`, EvalSurge 0.2.0 and the compatibility
`/api/invocations` contract. These passes establish current installed-runner
interoperability with those existing deployments, **not deployment validation of
the current public agent-App templates**.

### Separate fail-fast checks and unchanged aggregate allowance

Two intentional local-HTTP pre-provider failures, one per framework, each made
one failed excluded probe and **zero measured requests / zero model calls**.
They retained `target_http_error`, a failed lifecycle, skipped load, consistent
typed retrieval and cleanup. `fail-fast.ledger.0002.safe.json` records them
separately: successful failure-path checks are not successful inference cells.

The original ceiling remains **36 target attempts / 48 model calls**. Including
earlier retained traffic, the four new smokes and two new failed probes consumed
**16 target attempts / 12 model calls** in aggregate, leaving **20 / 36**.
This is not a new lease or permission to bypass remaining gates or activate
judges. CrewAI's two cells retain their failed advisory/deployment gates; no
CrewAI inference, dependency override or security waiver was performed.

### What these smokes do not prove

Public quickstart defaults are five users/five measured invocations and were
**not exercised unchanged**. One successful latency sample per cell cannot
establish latency tails or sustainable throughput. Evaluation was off; no new
quality, planner/judge calibration, trace, active cancellation or TTFT coverage
is claimed. Generator health remains **unknown**. App-target hub-lag maxima
were **355.68 / 381.54 ms**; complete journals do not establish an unsaturated
runner, accurate server-only timing or zero observer effect. Do not subtract
journal waits or timing baselines from request latency. Runner-App installation,
native worker OAuth, protected cloud export and cloud-generated traffic remain
separate unresolved evidence gates. Notebook validation is deferred.

## Historical App-install checkpoint: blocked, no additional live cell

The October 12 disabled `load-test` runtime deployment failed during dependency
installation, before startup or inference. The unchanged `0.2.1.dev2026101101`
wheel never ran. A separate stdlib-only diagnostic deployment established
Python 3.11.17/Linux and HTTP 403 from the approved package index; pip likewise
found no matching distribution. That diagnostic installed no dependencies and
ran no EvalSurge benchmark. Its compute is confirmed stopped, with source/logs,
App/resource grants and the volume preserved. See [the handoff](SESSION_HANDOFF.md)
for exact deployments and private evidence locations.

The runner's target/volume grants and catalog/schema traversal are verified.
App-side approved-registry access, the October 12 ADR 0019 workspace-ID amendment
approval, new `0.2.1.dev2026101201` wheel installation, target/source readiness,
live OAuth, protected exports and real-model App-runner traffic remain gates.
No new target/model/judge calls or claims occurred; the aggregate lease is unchanged.
At that historical installation checkpoint, live coverage was **2/12**, on the original wheel as recorded below—not
coverage of either newer native-auth artifact. Notebook work remains deferred;
CrewAI retains its failed advisory and managed-deployment tooling gates.

## Historical October 11 scope and older-wheel smokes

The following records actual-model validation against the older reviewed EvalSurge wheel, not
source-only tests or historical App successes. On October 11, 2026, the user
deferred notebook validation: the then-active inventory had twelve local/App-runner
cells, with three earlier notebook→App cells retained as deferred historical scope.
There is no separate
EvalSurge benchmark-submission API server in these journeys.

## Local runner → local HTTP agent: two cells passed

| Actual agent | Probe / measured attempts | Actual model dispatches / successful responses | Measured request latency | Result |
| --- | ---: | ---: | ---: | --- |
| LangGraph | 1 / 1 | 2 / 2 | 580.37 ms | Completed, one successful measured request |
| OpenAI Agents | 1 / 1 | 2 / 2 | 570.38 ms | Completed, one successful measured request |

Both agents used `examples/real_framework_agent.py` and the canonical
`real_framework_handler.py`, executing their actual graph/Runner. The selected
profile was `e2-demo-field-eng`, target model `system.ai.gpt-oss-120b`, and native
gateway route `/ai-gateway/mlflow/v1/responses`. No fake agent, provider fixture,
model fallback, tool, memory, deployment, planner or judge was used. Provider
retries were zero and each call allowed at most 512 output tokens. Four actual
model requests were observed in total; each returned a successful provider response.

The runner used a fresh installed wheel outside the checkout, under Python
3.12.13/macOS ARM64. It checked installed module paths and ran with Python `-I`:

```text
evalsurge-0.2.1.dev20261011-py3-none-any.whl
SHA256 4acba9feeb55dd724b0389ef84eaaf3cc623f4af42e14e9aa1ae8d8431b33b8f
```

All 117 runner dependencies were installed from the retained hash-locked server
export through the approved registry, without changing the repository lock or
relabeling registry provenance. All sixty wheel runtime members matched the
checkout at that validation checkpoint. The separately rebuilt `dist/` wheel had
a different archive hash and was not the artifact tested here, although its sixty
runtime members also matched then. Subsequent native App authentication changes
belong to `0.2.1.dev2026101101` and the later workspace-ID repair to
`0.2.1.dev2026101201`; these smokes validate neither newer runtime.

Each `RunCreate` used concurrency one, at most one measured request, a ten-second
dispatch ceiling and forty-second request timeout. Evaluation was off. An excluded
first-case inference probe preceded measured load. Typed status/result/report
receipts agreed, repeated report retrieval agreed, and SDK/agent lifespan/listener
cleanup completed. Protected reports and the content-free execution ledger were
retained privately rather than committed:

```text
/private/tmp/evalsurge-matrix-smoke-20261011.2mWD9R/
  ledger.safe.json
  langgraph/report.private.json
  openai-agents/report.private.json
```

The owned harness ran with:

```text
.venv/bin/python /private/tmp/evalsurge-matrix-smoke-20261011.2mWD9R/owned_local_cells.py
```

It hosted actual agent HTTP processes and invoked the independent installed runner
with `python -I installed_cell.py`; it did not import the agent into Locust. This
validated the published request vocabulary with a reduced, separately approved
smoke workload, not the five-user/five-attempt tutorial unchanged.

## Measurement boundaries

Each row has one measured observation: equal p50/p95/p99 values do not establish a
tail-latency distribution. Nonstreaming HTTP has no TTFT or first-event measurement.
Token-usage coverage was 100% for these two captures. Both measurements were complete
and journals drained with no writer failure or backpressure; generator-health state
remained **unknown**, not certified healthy. Maximum observed hub lag was 16.70 ms
and 22.32 ms respectively. These successful real-agent runs do not prove zero
observer overhead, cloud-disk accuracy, steady-state throughput or sustainable
capacity. Quality, active cancellation, internal trace correlation and cloud runners
are not established by these load-only cells.

## Separate fail-fast checks: passed with zero model calls

Both actual local framework HTTP handlers received exactly one intentionally
unsupported input. Each returned a failed inference preflight with safe code
`target_http_error`; measured load was skipped, metrics were absent and report
pagination contained no measured rows. Native transport counters were zero,
typed retrieval agreed, and SDK/agent/listener cleanup completed. These expected
failure-path tests made no substituted provider completion or model call.

The harness was `python -m scripts.validation.local_runner_http_target_journeys`
with `--framework langgraph` / `openai-agents`, `--execution direct`,
`--scenario fail-fast`, the same explicitly selected profile/model/route and
`--live`. It ran against checkout runtime members that matched the reviewed wheel;
these negative tests themselves are not separate installed-wheel validations.
Receipts/reports remain in `negative-langgraph/` and `negative-openai/` beneath
the same private evidence directory. The published five-user/five-attempt request
was reused, but its one excluded failed probe prevented all measured dispatch.

## CrewAI prerequisite: installation passed, advisory gate failed

The separately approved CrewAI 1.15.23 environment installed 162 hash-checked
distributions and passed `uv pip check`; actual async Crew/LLM API signatures were
inspected. Its ChromaDB 1.1.1 dependency failed the retained advisory audit, so
CrewAI inference was **not run**. No out-of-range dependency override or security
exception was assumed. Agent Bricks 0.4.0 and inspected 0.5.0 also retained a
required framework enum limited to LangGraph/OpenAI: the truthful native CrewAI
deployment/managed-store route remains unresolved, not a prohibition on generic
CrewAI HTTP hosting on Apps. See [the CrewAI prerequisite record](../examples/journeys/agent_apps/crewai/README.md).

## Remaining evidence

Fresh read-only metadata in the explicitly selected `e2-demo-field-eng` profile
on October 11 confirmed:

| App | Compute / App state | Deployment/resource observation |
| --- | --- | --- |
| `load-test` | `STOPPED` / `UNAVAILABLE` | No active deployment or declared resources |
| `agent-bricks-es-lg-1008` | `STOPPED` / `UNAVAILABLE` | Retained deployment status `SUCCEEDED`; not current readiness |
| `agent-bricks-es-oai-1008` | `STOPPED` / `UNAVAILABLE` | Retained deployment status `SUCCEEDED`; not current readiness |

The runner URL is `https://load-test-1444828305810485.aws.databricksapps.com`;
its service-principal client UUID is
`c6a6a61f-14d4-4123-9146-225e6aac6ec6`. The retained target deployment IDs are
`01f1c38db3f5165b98332e7c16cb1108` (LangGraph) and
`01f1c38db4281b698aaac4c5aa8e6761` (OpenAI Agents). These metadata reads made zero
target/model calls and did not start, deploy or grant access to any resource.

The selected `load-test` shell was created with `--no-compute`. A subsequent
exact-profile metadata read confirmed compute `STOPPED` and resolved its
service-principal client UUID. No source, resource grant or workload was deployed.
This is provisioning evidence, not a benchmark cell, runtime OAuth proof or
successful protected report delivery.

At that historical checkpoint, only two of twelve basic cells had passed, on the older artifact
identified above. The other ten are pending their exact
installation/authentication/deployment/ingress/export gates. The three former
notebook→App cells are deferred, not relabeled as passing or discarded. Historical
App and serverless receipts are separate evidence and cannot fill those cells.
Cloud tests must retain the selected `load-test` runner App name. Catalog
`ram_artifacts.evalsurge_validation.runner_artifacts` was subsequently selected
and provisioned on October 12 as recorded below; runner grants remain pending. No notebook
credential is needed for this milestone. See [the live prerequisite checklist](LIVE_MATRIX_PREREQUISITES.md)
and [runner/target validation](RUNNER_TARGET_VALIDATION.md).

## October 12 artifact provisioning, not a live matrix success

Using `e2-demo-field-eng`, the approved `evalsurge_validation` schema and managed
`runner_artifacts` volume were created in `ram_artifacts`. Both are owned by the
selected operator and have no direct grants. An effective-permission check found
only the preserved existing catalog-administration `ALL_PRIVILEGES` / `MANAGE`
grant; no broad data-reader grant was added. Ownership/administration remains
privileged access, not owner-only storage.

The unchanged reviewed wheel and a disabled native runner configuration were
staged locally. Non-networked configuration construction, exact wheel hash and
runtime-environment wiring passed. No runner access was granted; no App or target
was started/deployed; no report was uploaded and no inference/judging occurred.
The matrix pass count is unchanged. The native deployment still requires
designated maintainer review, disabled cloud installation verification and
target/authentication/export readiness before bounded traffic.
