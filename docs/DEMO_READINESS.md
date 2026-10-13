# Demo finish-and-validate checkpoint — October 12, 2026

## Current artifact: installed local multi-tool tracing sample

The current `0.2.1.dev2026101203` wheel includes independent load-only trace
readiness, CLI lifecycle progress and bounded retries for missing exact trace
correlation metadata. Its frozen artifact is:

```text
evalsurge-0.2.1.dev2026101203-py3-none-any.whl
SHA256 1b46d96185afc7225faf6254db1181b9e023525bb67c0cb714ce948ea5b1d20f
```

Fresh isolated uv **base/local/server installations** outside the checkout passed
on macOS against exact locked hashes using the approved source's artifact cache,
with zero model, target or authentication calls. This is not public publication,
Linux/App installation or fresh range-based dependency-resolution evidence.

Both public [multi-tool sample](../examples/journeys/multitool_heatmap/README.md)
entrypoints then ran from the installed wheel outside the checkout against a
separate local HTTP LangGraph agent. The fixed serial graph executed three actual
tools over synthetic documents/computation, an eligibility decision and actual
`system.ai.gpt-oss-120b` Responses inference using the explicitly selected
`e2-demo-field-eng` profile. No model completions were stubbed or substituted.

| Trace export | Run ID | Measured outcomes |
| --- | --- | --- |
| Synchronous | `fefaebd2-792f-4a36-9c42-5cd320e81edb` | 4/4 successes, zero errors, 100% trace coverage |
| Asynchronous | `e36199e5-b5c6-4717-a294-c33816012ce9` | 4/4 successes, zero errors, 100% trace coverage |

Each run added one excluded successful probe and retained six spans per request.
The delayed shipping tool was approximately 2,001 ms, making the injected delay
visible in content-free trace evidence. Five users were configured, but the
four-request measured cap permitted at most four concurrent measured attempts.
The ten-call model budget is exhausted; no judges, retries, fallback inference,
App deployment or App load were performed. Both agent processes exited cleanly.

These are functional local HTTP smokes, not capacity or accuracy certification,
fresh native App template deployment, governed UC trace collection, or browser
visual verification. The first earlier asynchronous probe remains recorded as
failed; later success does not erase it or prove its original mismatching field.
See [validation](../VALIDATION.md) for exact measurements, archived failures and
controlled-suite results. The earlier installation-alias checkpoint below remains
specific to its own `.1202` artifact and older App deployments.

## Historical installation-alias checkpoint: local installation and traffic generation

The installation-alias milestone covers a simple installed-package local SDK and
six intended target journeys: LangGraph, OpenAI Agents, and CrewAI, each hosted as a local
HTTP agent or a deployed Databricks App. No EvalSurge API server is required. The additive
`[local]` install name uses the existing execution stack; `[server]` stays compatible.
Four of those six basic real-model cells passed; CrewAI remains blocked as recorded below.
See [the local-runner quickstart](../examples/journeys/LOCAL_RUNNER_QUICKSTART.md).

The package change is a new `0.2.1.dev2026101202` artifact, not a replacement for
either frozen native-auth wheel. Installation, static samples, and real-model
validation are separate claims. Latest evidence is in [the live record](LIVE_MATRIX_RESULTS.md).
The runner-App registry 403 and ADR 0019 workspace-ID amendment remain preserved
historical/unresolved gates, not prerequisites for local traffic to an agent App.
CrewAI's dependency-security gate still applies to its agent environment.

The reviewed wheel is
`evalsurge-0.2.1.dev2026101202-py3-none-any.whl`, SHA256
`a1a58a4513c4659aee41f9c5570bbcca6da371b4b185b629e7842be4eac23285`.
Fresh pip base/local/server installations outside the checkout passed with exact
locked hashes through the approved source, with zero agent/model calls. This is
macOS installation evidence, not public-PyPI publication or Linux/App installation.

**4/6 basic real-model local-runner cells passed:** LangGraph and OpenAI Agents,
each over local HTTP and against the existing deployed agent App. Actual
`system.ai.gpt-oss-120b` inference used one excluded probe and one measured
request per cell, concurrency one, evaluation off and no fixture completions.
Typed status/result/report retrieval agreed, journals drained and SDK/worker
cleanup passed. Each App's two model attempts completed without model errors;
final read-only confirmation at **October 12, 17:23:32 UTC** found both target
Apps **STOPPED / UNAVAILABLE**, deployments/resources unchanged. Nothing was
deleted. CrewAI's two cells remain blocked; no advisory waiver or inference was
performed.

These smokes validate that exact `.1202` installed local runner against retained old
App deployments, not deployment of the current public templates, the unchanged
five-request quickstarts, quality, active cancellation, capacity or zero observer
effect. App-target generator health remains unknown; hub-lag maxima were
355.68/381.54 ms. Dedicated runner-App installation and traffic remain separate
unverified gates; notebook work is deferred. Consolidated protected evidence is
`/private/tmp/evalsurge-local-only-20261012.D2MG3y/milestone.safe.json`, with App
readiness/counters/cleanup in
`/private/tmp/evalsurge-target-readiness-20261012.RxUvhu/`.

## Historical local-plus-runner-App milestone

The product demo is Tuesday, October 13. On October 11 the user deferred notebook
validation and selected two installation/load-generation locations: local Python
and the dedicated `load-test` Databricks App. Agent hosting remains HTTP or a
separate deployed Databricks App. This milestone finishes the existing
contract; it does not introduce notebook-native authentication, another SDK or
another load engine. The workspace-ID repair is now versioned
`0.2.1.dev2026101201`; do not reuse either older wheel to claim it is installed.
See [installation](INSTALLATION.md) and [validation](../VALIDATION.md).

The preceding native-auth wheel is retained at
`/private/tmp/evalsurge-native-reviewed-20261011.HlxeuH/dist/evalsurge-0.2.1.dev2026101101-py3-none-any.whl`.
SHA256: `f81098aac24e2251955cb000bdb017b981ef64ad4474104183ef4f8c8f894d6e`.
Fresh base/server installs outside the checkout passed with zero agent/model/cloud
calls. Actual SDK construction and refresh have controlled HTTP coverage, not
live OAuth evidence. The final synchronized controlled suite passed **1,709 tests /
42 warnings**; the template/docs regression slice passed **151 tests**. Exact final gates
and retained failures are in the validation record.

At that historical checkpoint, **2/12** basic live cells had passed: local LangGraph/OpenAI Agents HTTP
smokes on the original wheel. They do not validate the new native-auth runtime.
The October 12 disabled `load-test` runtime deployment failed during dependency
installation, before startup or inference. A separate stdlib-only diagnostic
established Python 3.11.17/Linux and HTTP 403 from the approved package index;
its successful deployment did not install/run EvalSurge. Compute is confirmed
`STOPPED`, with source/logs and exact target/volume/parent grants preserved. Registry
access, ADR 0019's new workspace-ID amendment approval, repaired-artifact App
installation, live native OAuth/exports and CrewAI advisory resolution remain gates.
Three formerly requested notebook→App cells are deferred, not completed. Retain
their prepared samples and failure receipts; notebook credentials are no longer
an active milestone requirement.

## Historical original-wheel checkpoint

The corrected installation-verified wheel is retained at
`/private/tmp/evalsurge-reviewed-demo-20261011.Voze4Q/dist/evalsurge-0.2.1.dev20261011-py3-none-any.whl`.
SHA256: `4acba9feeb55dd724b0389ef84eaaf3cc623f4af42e14e9aa1ae8d8431b33b8f`.
Fresh base/server installs passed outside checkout on Darwin ARM64/Python 3.12.13,
using hash-pinned dependencies from an approved source, not public-index download
evidence. The final non-inference slice passed **323 tests / 3 deselected**;
installed worker checks used nine NON-agent timing requests. The two portable
sample `--help` checks establish imports/options, not successful model traffic.
With explicit user approval, the full controlled-provider suite subsequently
passed **1,252 tests with no skips or deselections**. The initial 1,249-pass/one-
failure run is retained; a narrow source-test correction handles notebook
top-level await without relaxing ordinary scripts. Packaged runtime and wheel
hash are unchanged. These are controlled regressions, not real-model evidence.
Linux-install, remote-CI, live validation and maintainer-review gates remain open.

The original [15-cell runner/target plan](RUNNER_TARGET_VALIDATION.md) adds an
explicit CrewAI/LangGraph/OpenAI Agents inventory, standalone serverless HTTP/App
notebooks and a [private direct runner App](../examples/journeys/app_runner/README.md).
Two original-wheel real-model HTTP smokes are recorded separately; ten local/App
cells remain pending and three notebook cells are now deferred. The earlier 1,252-test suite predates these additions
and native authentication. No deployed runner workload is claimed.

The subsequent customer-example isolation work separates the real handler from
EvalSurge's package dependencies, adds a standalone CrewAI HTTP endpoint and
prepared native LangGraph/OpenAI Agents/CrewAI App sources. This addresses a source
dependency conflict. The isolated CrewAI install subsequently passed, but its
ChromaDB advisory audit failed; no CrewAI inference or deployment followed. See
[proposed ADR 0018](adr/0018-customer-agent-example-dependency-isolation.md) and
[the exact live-resource/dependency gates](LIVE_MATRIX_PREREQUISITES.md).

## Artifact and execution boundaries

The base install is the lightweight remote SDK/CLI. The `[server]` install runs
the direct SDK and sole Locust engine on the caller's machine; an API server is
optional. Requests share `RunCreate`, operator-owned target bindings and typed
results. Evaluation is off by default, judging uses captured answers, and lifecycle
completion remains distinct from passing quality checks.

The two targets are a separately hosted HTTP agent and a deployed Databricks App.
A serverless notebook is a retained, deferred **runner location**, not a third
hosting choice or a requirement for the current demo. Submitting from a notebook
to another API host does not move load generation into the notebook. Native App
streaming, sweeps, comparisons and distributed workers
remain deferred.

| Capability/journey | Current artifact evidence | What is not established |
| --- | --- | --- |
| Base remote-client installation | Fresh installed-wheel import/schema/presentation checks, without the server stack | Live service submission, service auth or target behavior |
| Direct `[local]` / compatible `[server]` installation | Fresh pip installations outside checkout; installed imports/CLI/runtime checks; separate real-model local-runner smokes below | Public-index, Linux/App install, newest-dependency resolution or unsaturated capacity |
| Shared Python/CLI summary | Pure typed/dictionary presentation and dependency-isolation regressions | New quality or timing evidence; unknowns are not zero |
| Laptop → hosted HTTP agent | Fresh reviewed-wheel actual-model LangGraph/OpenAI Agents basic smokes, typed retrieval and cleanup | CrewAI advisory resolution; quality, active cancellation, tails and capacity |
| Laptop → deployed App | Fresh reviewed-wheel actual-model LangGraph/OpenAI Agents basic smokes against retained deployments, counters and compute cleanup | Current-template deployment, quality, active cancellation, trace/TTFT and accuracy certification |
| Serverless → deployed App | Deferred by user October 11; retained launcher, safe failures and portable-M2M checks | No live notebook-generated load established; not an active release gate |
| Serverless → reachable HTTP agent | Deferred optional prepared sample, never requested live coverage | Cloud install, network reachability and real inference not established |
| Dedicated runner App → separate HTTP/App target | Original private-contract approval; verified exact grants; disabled install failed; stdlib-only diagnostic found approved-index 403; compute stopped | Repaired-artifact installation after registry access and workspace-ID amendment approval, live OAuth/worker refresh, protected exports, model traffic and active shutdown coverage |
| Classic notebook | Retained example only | Deferred by user instruction; no fallback cluster |

## Completed implementation

- Repaired the packaged serverless dependency using the pure `evalsurge._retrieval`
  module; no dependency on a source-only validation script remains.
- Added public `format_summary(result_or_report)`, shared with the CLI. It emits
  bounded metrics, phase/quality/coverage and generator caveats without prompts,
  answers, rationales, credentials, paths or arbitrary provider messages.
- Strengthened native timing-server and worker ownership against repeated task
  cancellation. Calibration success requires observed cleanup, successful timing
  pairs and exact injected storage-fault evidence, not lifecycle labels alone.
- Split serverless metadata, observed client dispatch and successful-completion
  flags. A failed pre-invocation run no longer claims the App was tested.
- Aligned source/API version metadata, README and installation instructions to a
  uniquely versioned demo wheel. Static archive checks inspect internal imports;
  installation verification runs outside the checkout.

`print(format_summary(run.result()))` is the default human-readable presentation.
Explicit full JSON is a protected export and can include sensitive evidence.
Readiness retains separate configuration/planning, discovery/authentication,
protocol/inference and judge/evidence failures; successful preflight is not a
concurrency-capacity test. Static `doctor` performs no target or paid calls.

## Remaining gates

1. The explicitly approved full offline suite passed; remote CI and the supported
   interpreter/platform matrix are not established by this local run. Disclose
   controlled providers and obtain the appropriate approval before new CI runs.
2. Preserve the fresh four-cell receipts and two intentional pre-provider
   fail-fast checks. The original aggregate 36-target/48-model ceiling has
   consumed 16/12, leaving 20/36; it is not a new lease or quality/cancellation
   approval. Recheck target readiness and exact bounds before any additional
   authorized traffic. Never fall back to fixture completions.
3. For the dedicated runner App, use the user-approved managed volume
   `ram_artifacts.evalsurge_validation.runner_artifacts`, created on October 12.
   Direct grants are empty and existing catalog administration remains inherited;
   verify the narrow runner grants and exact target App permissions. Use explicit native App-runtime
   M2M binding with the runner service-principal identity; no manual notebook
   credential is required. Verify installation, worker OAuth and protected export
   before bounded real-model traffic. No deployment, grants or traffic are implied
   by the stopped shell or catalog selection.
4. Obtain designated maintainer review of the material ADRs before release.

NON-agent timing confirms a narrow storage/scheduling mechanism on the tested
machine. It neither proves zero observer effect nor validates cloud/serverless
disk behavior. Do not subtract it from real metrics or call smoke throughput
sustainable agent capacity. Fresh inference is limited to the four documented
basic cells; no current-template deployment or package publication is established.
