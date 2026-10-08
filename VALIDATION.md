# Validation — 0.2.0

Validated locally on macOS/Python 3.12 on October 4–8, 2026. CI is configured for
Linux/Python 3.11–3.14. Observed main jobs failed during private-mirror installation;
there is no remote CI result for these local changes. Branch-protection
settings have not been verified/enabled by this local work.

## Documentation and source publication review — October 7–8, 2026

Reviewed the first-party API/coordinator, models/settings/diagnostics, connection
and App resolution, protocol adapters, sole Locust engine, persistence/recovery,
planning/readiness/judging/profiling, local/remote SDK and CLI, report presentation,
examples, validation helpers, packaging, and release checks. Stale-contract scans
exclude vendored Swagger and historical schema-review fixtures. This is a focused
source/contract review, not proof that all code is defect-free or a security audit.
No additional live/paid agent or judge traffic was generated for this review.

The README and target/API guides now explicitly support both an already running
HTTP agent and an operator-registered Databricks App. They explain runner-relative
localhost, lightweight versus server installs, strict message input envelopes,
evaluation opt-in/model roles, current Runtime versus legacy MLflow protocols,
session ordering versus memory, and live-evidence limits. New `docs/TARGETS.md`
TOML/JSON examples validate through the actual settings, v2 translation, and
protocol encoders without discovery or traffic. Relative navigation checked **27
documents / 143 links**, with no missing destinations. Public documentation now
omits exact selected workspace/profile/App URL and temporary-source identifiers;
they remain in protected evidence. Historical failures, run IDs and metrics remain.

Source review found a Runtime response-completion bug: a completed outer invocation
and handler could hide an explicitly unfinished assistant message. Four new
regressions (`in_progress`, `incomplete`, `failed`, null) failed before the fix,
**4 failed in 0.13 seconds**. The decoder now rejects those states without publishing
any partial answer; missing status remains compatible with normalized output and
explicit completed messages have a positive control. Focused protocol verification
passed **25 tests in 1.02 seconds**. ADR 0010/API review document the behavioral
tightening. No polling, target retry, fallback, or altered timing is introduced.

The initial target-guide test had one incorrect test assumption about a nonexistent
`ConnectionSettings.invocation_path` property (**1 failed, 29 passed**). It was
corrected to inspect the real declared protocol; documentation/configuration was
not weakened. The corrected guide/protocol suite passed **30 tests in 4.31 seconds**.
Ruff also identified one nested-context style error in the new regression, corrected
before final lint. A stale report note now excludes probes/readiness from benchmark
quality results, rather than incorrectly claiming the probe is never judged.
Legacy manual model-serving helper docstrings now distinguish logical assessments
from retry/provider/spend budgets and consent-gated App checks.

The bare required sync command selected the ambient private index and refused to
update the authentic public lock under `--locked`. Explicit public-index sync
succeeded (**190 resolved, 182 checked**) without a graph upgrade. Subsequent
commands use `--no-sync` against that verified agents/dev environment:

```bash
uv sync --locked --extra agents --group dev
uv sync --locked --extra agents --group dev --default-index https://pypi.org/simple
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q \
  --junitxml=artifacts/prepush-20261007/final-review-junit.xml
uv run --no-sync python scripts/export_openapi.py --check
uv run --no-sync openapi-spec-validator docs/openapi.json
uv build --no-build-isolation
uv run --no-sync python scripts/verify_wheel.py
uv run --no-sync python scripts/verify_remote_install.py --offline
uv run --no-sync python scripts/check_ci_prerequisites.py
uv export --quiet --locked --default-index https://pypi.org/simple \
  --extra agents --group dev --no-emit-project \
  --output-file artifacts/prepush-20261007/final-review-audit-requirements.txt
uv run --no-sync pip-audit --disable-pip --require-hashes --progress-spinner off \
  --vulnerability-service osv \
  --requirement artifacts/prepush-20261007/final-review-audit-requirements.txt
git diff --check
```

Full suite checkpoint: **674 passed, no skips, 42 upstream warnings, 198.61 seconds**.
The final publication rerun, including the corrected report-note regression,
passed **674 tests, no skips, 42 warnings in 194.14 seconds** with
`uv run --no-sync pytest -q --junitxml=artifacts/prepush-20261007/publication-junit.xml`.
Final documentation also aligns the tracing guide with the shipped explicit Agents
model-span strategy rather than recommending duplicate autologging, and clarifies
the Runtime session boundary in ADR 0009. Lint/format, schema checks, rebuilt
distributions, wheel assets and isolated-client verification passed again.
After final documentation edits, `uv run --no-sync pytest -q tests/test_readme.py
tests/test_validation_tools.py --tb=short` passed **13 tests, one upstream warning
in 9.05 seconds**; final lint/format and staged whitespace checks also passed.
Warnings concern MLflow's deprecated SQLAlchemy loader and positional pandas API.
Ruff lint and formatting (**131 files**), OpenAPI equality/schema validation,
sdist/wheel build, packaged asset checks, and an actual isolated base-only wheel
SDK/CLI/missing-extra check passed. The isolated check installed eleven base
dependencies plus EvalSurge, verified compatible installed metadata and absence of
the server/load distributions; its expected VIRTUAL_ENV mismatch warning confirms
it used the separate environment. Static CI provenance checked **189 registry
packages**. The complete hashed agents/dev/build export had **no known OSV
advisories**; hash presence is checked by OSV, artifact integrity by uv.

This publishes the existing follow-up fixes plus the decoder regression and current
documentation, not a new production release or agent deployment. API compatibility
review preserves v1 envelopes, lazy local signatures with the server extra, and
versioned history; intentional input/response tightening and packaging migration
are documented. ADR/public-contract designated maintainer review remains pending.
The official upstream version gaps in `docs/DEPENDENCIES.md` remain: no fresh
latest-compatible resolution or dependency-version/provenance rewrite is claimed.
Local verification is not evidence of the post-push Linux CI matrix. Private
captures, JUnit/audit artifacts, profile configuration, and the temporary deployed
sample source are excluded from the commit. Publication starts from `main` at
`fc66f6a7dc4e6d3f74bcb3d26cf7453b1312fecd`, matching fetched `origin/main`;
normal commit/push results are reported in the thread, not predicted here.

## Native App redeployment and bounded live results — October 7, 2026

The user explicitly authorized redeployment and the previously selected OAuth
profile/workspace, one App instance with its required managed Runtime Store,
concurrency five, and a few-minute bounded test. Exact selected profile/workspace
identifiers remain in protected evidence; public examples below use placeholders.
This section supersedes the pending/live-unavailable checkpoint below, without
changing its historical results. No optional agent memory, transcript-history
store, tracing experiment, tools or automatic recovery were enabled.

### Deployment, retained failure and minimal correction

Recreating the missing original App produced a new identity, but deployment
correctly refused to reuse its earlier Runtime Store because the store did not
belong to that App identity. No ownership guard was bypassed; the old store was
not deleted or rebound. The newly created, undeployed original-name App
`agent-bricks-test-eval-ram` was stopped and retained. A fresh-name deployment,
`agent-bricks-test-eval-ram-v2`, succeeded with its own required Runtime Store.
Its first immutable revision was `01f1c28d4eaf13ca9242b6f990c5f0b8`.

The first intentional failure check confirmed one excluded failed probe and zero
measured requests. The first real-model attempt then failed inference preflight
with HTTP 500 before any measured load. Private App logs and an offline test
reproduced `ResponseOutputText` receiving a list instead of text: the MLflow
Chat Completions route returned structured reasoning/text content, while the
non-streaming Agents chat converter required a string. This failed paid attempt
is retained; it is not relabeled as a passing performance test.

Official Unity Gateway quickstart and installed Databricks/OpenAI/Agents source
were checked against actual model-service metadata retrieved with
`databricks api get /api/2.1/unity-catalog/model-services/system.ai.gpt-oss-120b
--profile <selected-profile>`. Supported API types were only
`mlflow/v1/chat/completions` and `mlflow/v1/responses`. The SDK's
`use_ai_gateway_native_api=True` option was therefore not used: SDK support alone
does not establish that this model supports the native `openai/v1` route.

The temporary native sample now uses the real `OpenAIResponsesModel` with
`Runner.run` through `/ai-gateway/mlflow/v1/responses`. The public App contract
remains synchronous `/api/invocations`. Model/prompt/load bounds are unchanged:
`system.ai.gpt-oss-120b`, low reasoning, 512 maximum output tokens, one turn,
30-second model HTTP timeout, zero model retries/redirects, no tools or session.
Explicit `store=false` prevents provider-side response storage; the required
Runtime Store still persists invocation requests/events/results. The supported
SDK rejects failed/incomplete responses; sample guards also reject unfinished
message items and empty/malformed final answers. Reasoning is not flattened into
answers; no SDK converters were patched and no model/route fallback was added.

The corrected sample was redeployed in place with:

```bash
uv tool run --from databricks-agentbricks==0.4.0 agentbricks \
  --profile <selected-profile> \
  deploy test-eval-ram-v2 \
  --source <protected-sample-source> --instances 1
uv run --no-sync python artifacts/native-app-redeploy-20261007/verify_deployment.py \
  --record deployment-responses.json
```

Final revision: `01f1c28f4d441ee9bf6a2d61891edf74`, `SUCCEEDED` with traffic switched.
App `RUNNING`, compute `ACTIVE`, one MEDIUM instance. The exact App URL remains
in the protected deployment record rather than public documentation.
Authenticated `/status` returned 200 with expected controls. Eleven checked
runtime/config/documentation/test files matched the immutable deployed snapshot
byte-for-byte. This verifies those files, not transitive deployed package versions:
native deployment resolves dependencies without the developer's lockfile.
The App was still running on the same revision after both successful checks.

### Live checks and measurement boundaries

All use the sole Locust engine from the operator's macOS machine, outside the App,
with fresh invocation/session IDs, synchronous foreground JSON, no target retries,
and new protected directories under `artifacts/native-app-redeploy-20261007/`.
Commands below abbreviate only the exact selected profile and the synthetic prompt
recorded in the protected configuration:

```bash
uv run --no-sync python -m scripts.validation.databricks_app_smoke \
  --profile <selected-profile> --app-name agent-bricks-test-eval-ram-v2 \
  --prompt '__evalsurge_fail_preflight__' --concurrency 5 \
  --max-requests 2 --duration 10 --timeout 60 \
  --artifact-dir artifacts/native-app-redeploy-20261007/fail-fast-responses \
  --live --accept-paid-traffic
uv run --no-sync python -m scripts.validation.databricks_app_smoke \
  --profile <selected-profile> --app-name agent-bricks-test-eval-ram-v2 \
  --prompt '<synthetic refund-policy question>' --concurrency 5 \
  --max-requests 500 --duration 180 --timeout 60 \
  --artifact-dir artifacts/native-app-redeploy-20261007/performance-responses \
  --live --accept-paid-traffic
uv run --no-sync python -m scripts.validation.databricks_app_quality \
  --profile <selected-profile> --app-name agent-bricks-test-eval-ram-v2 \
  --concurrency 5 --max-requests 2 --duration 10 --timeout 60 \
  --artifact-dir artifacts/native-app-redeploy-20261007/quality-responses \
  --live --accept-paid-traffic
```

| Check | Run ID | Result |
| --- | --- | --- |
| Initial intentional failure | `22b19f48-f023-48d4-979c-86d2da20f1cd` | Expected HTTP 500; one excluded probe, zero measured requests; fail-fast confirmed |
| Initial real-model failure | `7f742a19-c28c-4e20-979c-c976fd5211de` | HTTP 500 at inference preflight; one excluded probe, zero measured requests; later phases skipped |
| Corrected intentional failure | `5b76b597-2047-46ae-81c0-a67f3a871483` | Expected HTTP 500; one excluded probe, zero measured requests; later phases skipped; CLI exit 1 |
| Corrected performance | `10d6e4a6-f3a7-4c11-ae33-24ce45cc65e8` | Passed probe plus 500/500 measured successes; no failures/incomplete measurements; CLI exit 0 |
| Separate explicit quality | `0411fd38-3705-469a-8039-69d293f580af` | Passed inference and both judge-readiness checks; 2/2 measured successes; all four quality verdicts true; CLI exit 0 |

Performance configured/observed peak HTTP concurrency was **5/5**. The request
cap stopped dispatch after **129.208 seconds**, before the 180-second ceiling;
elapsed including drain was **130.369 seconds**. Observed successful throughput
was **3.835 requests/second**; successful latency p50 **1146.795 ms**, p95
**2173.947 ms**, p99 **2460.319 ms**. Exactly one excluded successful probe was
additional to the 500 measured attempts. Evaluation was off (`no_ready_scorers`).
Profiling bookkeeping completed, but remote trace coverage was zero because
tracing was disabled. JSON supplies no answer-text TTFT/first-event measurements
and no output-token usage, so those values remain unavailable rather than zero.

Quality used **`databricks-gpt-5-4-mini`**, explicit **relevance/correctness**, the
authoritative fact “Opened items cannot be refunded.”, and **no planner calls**.
One excluded target probe supported two zero-retry readiness assessments; two
measured captures supported two assessments per scorer, with zero judge errors
and boolean pass rates 1.0 for each. The captured synthetic answer was inspected:
“No, an opened item cannot be refunded.” Judging did not reinvoke the target.
Configured concurrency was five, but a two-request quality cap is not five-user
capacity evidence. The documented frozen budget allowed at most fourteen judge
provider attempts, 2048 output tokens per attempt, and two quality retries; actual
network retry counts/cost were not independently audited. Local native MLflow
stores protected captures/rationales separately from content-free summaries.

### Offline verification and handoff limits

The original content-block regression failed before changing the sample. The
expanded suite initially had one incorrect exception expectation for reasoning-only
output; the guard correctly rejected it with `ValueError`. The expectation was
corrected without weakening answer rejection or the one-call/cleanup assertions.
Final actual-framework/client/native-server sample suite: **29 passed** (parent
rerun 5.29 seconds; final agent rerun 5.41 seconds). Static native doctor: **7/7**.
Changed sample Python files pass root Ruff lint/format. Sample runtime, manifest
and dependency declarations were not changed by the Responses fix.

Root App-harness/documentation regression command
`uv run --no-sync pytest -q tests/test_databricks_app_smoke.py
tests/test_databricks_app_quality.py tests/test_validation_tools.py
tests/test_readme.py --tb=short` passed **43 tests, 13 upstream warnings, 23.04
seconds**. Root Ruff lint/format (130 files), OpenAPI snapshot equality/schema
validation, and whitespace checks passed. The last full root suite/build/isolated
wheel checks remain the 669-test checkpoint below; this continuation changed no
root production Python behavior or dependency graph.

After recording these live results, the final validation-tool/README rerun passed
**12 tests, one upstream warning, 8.97 seconds**. Root Ruff lint/format and
whitespace checks passed again.

The sample App and required Runtime Store remain available and incur ongoing
resource cost. The stopped unused original-name App and earlier store were retained;
no store was deleted/rebound. No benchmark process remains running. Prior failed
evidence was not overwritten. No sustainable capacity, judge calibration, model
token throughput/TTFT, remote tracing, transitive deployed version parity, hard
wall-clock/spend deadline, remote CI or independent maintainer approval is claimed.
All unrelated dirty-tree work is preserved; no commit or push occurred.

## Native App source review and local verification — October 7, 2026

Resumed the approved native sample provisioning and bounded validation workstream.
Read current official Agent Server, Query Agents, and Agent Bricks CLI documentation
directly (all pages updated October 6), and checked the installed stable
`databricks-agentbricks==0.4.0` implementation against official
`databricks/databricks-ai-bridge` source at
`c2046018d6fa3f382bf18f89a44ea5b7943776ba` (October 7). The snapshot identifies itself
as `0.5.0.dev0`, not a released stable replacement. Its migration skill, OpenAI
integration contract, and deployment implementation match the installed package;
its newer event-reader/stream polling changes are outside this sample's synchronous
`stream=false`, `background=false` check. No development package was installed.
The runbook now documents this source/skill boundary and the overview's stale
Python 3.10 requirement versus the package/templates' Python 3.11 minimum.

The source/docs confirm `/api/invocations` as the current default and `/responses`
as legacy compatibility. Lakebase's managed Runtime Store is invocation execution
state, not agent transcript history or long-term memory. The tailored sample uses
the actual OpenAI Agents Runner, `system.ai.gpt-oss-120b`, one model turn, 512 maximum
output tokens, a 30-second HTTP timeout, zero model retries, no tools, no session
history, no memory, and no automatic recovery handler. The intentional failure
prompt raises before model dispatch. HTTP/authentication budgets are not hard
overall deadlines; queued first attempts can outlive client disconnection.

The prior native deployment completed successfully with one MEDIUM instance, an
App named `agent-bricks-test-eval-ram`, and its required managed Runtime Store.
No optional Session/Memory Store or trace experiment was bound. The pending
authenticated `/status` read returned HTTP 200 and the intended content-free
controls. Subsequent read-only CLI and SDK lookups both returned App `NotFound`;
the selected profile still resolves to the approved workspace and active user.
The App was absent from the bounded App list. Deployed source hash comparison
therefore could not complete. No replacement deployment, inference, judge, or
planner traffic was sent at this checkpoint. Whether the App was intentionally
deleted/moved requires operator clarification; no cause is asserted. The Runtime
Store's current existence was not independently checked, and nothing was deleted.
Local sample docs/tests were updated after upload; deployed docs/test snapshot
parity is not claimed even though the runtime source was unchanged locally.

The full root run first reported **12 failed, 657 passed, 42 warnings in 202.66
seconds**. New quality tests leaked native MLflow's process-global tracking URI
into later safe-report tests. The smallest ordered pair reproduced the failure
(one failed/one passed). A test-only fixture now restores raw tracking/experiment
selectors and exact environment presence; the pair passed, and the ordered
quality/evaluation-preflight/preflight suite passed **48 tests in 45.51 seconds**.
No production error-redaction assertion was weakened. The helper's documentation
now discloses this existing backend's global MLflow side effect and recommends
separate CLI-process execution.

Final local commands/results:

```bash
uv sync --locked --extra agents --group dev \
  --default-index https://pypi.org/simple --offline --no-build-isolation
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q --tb=short \
  --junitxml=artifacts/native-app-20261007-local/junit-recheck.xml
uv run --no-sync python scripts/export_openapi.py --check
uv run --no-sync openapi-spec-validator docs/openapi.json
uv build --no-build-isolation
uv run --no-sync python scripts/verify_wheel.py
uv run --no-sync python scripts/verify_remote_install.py --offline
git diff --check
```

Locked offline sync resolved 190 and checked 182 installed packages. Full root
suite: **669 passed, no skips, 42 upstream warnings, 194.40 seconds**. Ruff lint
and formatting (130 files), OpenAPI equality/schema validation, sdist/wheel build,
packaged assets, and actual isolated base-only wheel SDK/CLI checks passed. The
isolated native sample suite separately passed **19 tests in 4.25 seconds**;
its prior static doctor passed 7/7. These use real framework/native MLflow/server
APIs with controlled provider boundaries, not live model calls.

After the final runbook/validation and helper-docstring edits,
`uv run --no-sync pytest -q tests/test_databricks_app_quality.py
tests/test_validation_tools.py tests/test_readme.py --tb=short` passed **27 tests,
13 upstream warnings, 19.21 seconds**. Ruff lint/format and whitespace checks passed;
the distributions were rebuilt and final wheel assets verified. The full 669-test
run preceded only those documentation/docstring edits.

Protected failure/success JUnit records are retained under
`artifacts/native-app-20261007-local/`. The pending live checks remain separate:
intentional fail-fast, concurrency five/180-second dispatch/500-attempt-cap
performance-only, and a new tiny explicit relevance/correctness run using the
mini judge and captured answers (no planner). No live pass, sustainable capacity,
TTFT for native JSON, quality calibration, fresh upstream-latest dependency
resolution, remote CI result, or independent maintainer approval is claimed.
The dirty implementation remains preserved; no commit or push occurred here.

## Selected-profile discovery and five-user preparation — October 7, 2026

The user explicitly selected the previously listed OAuth profile and proposed
`test-eval-ram`, concurrency five, and a few-minute workload. Initial CLI reads
failed because the older token cache was incompatible with CLI 1.17.0. An approved
`databricks auth login --host <selected-workspace> --profile <selected-profile>
--timeout 2m` refreshed only that profile. Reads inside the sandbox still could
not access the secure credential store; approved outside-sandbox retries of
`databricks current-user me` and `databricks apps list --limit 100`, both with the
exact selected profile, succeeded. The identity was active and the proposed App
was not among the 24 returned Apps. No raw credentials were printed or credential
storage security weakened. These were read-only workspace operations, not inference.

The existing harness now accepts explicit `--concurrency 5 --duration 180
--max-requests 500`, retaining its small dry-run defaults and live-consent gate.
It records safe probe diagnostics, independent phase outcomes, separate observed
probe/measured counts, and fail-fast confirmation. Native localhost tests exercise
five-user load and an intentional failed probe: exactly one excluded attempt,
zero measured requests, skipped load. A 500-request cap can stop dispatch before
three minutes; the probe and drain add time outside that dispatch window.

`uv run --no-sync pytest -q tests/test_databricks_app_smoke.py --tb=short` passed
**16 tests in 2.62 seconds**. The first local attempt was blocked by sandbox access
to uv's cache; the approved retry passed. Full framework-enabled
`uv run --no-sync pytest -q --tb=short` passed **654 tests, no skips, 30 upstream
warnings, in 181.28 seconds**. Locked offline agents/dev sync checked 182 installed
packages and resolved 190. Ruff lint and formatting (128 files), OpenAPI snapshot
check and independent schema validation, sdist/wheel build, required wheel assets,
and whitespace checks passed using the same commands/options as the prior section.

Current official Agent Server/Agent Bricks CLI documentation confirms that the
new deployment workflow provisions a managed Runtime Store in addition to the App.
The Agent Bricks CLI is not installed locally. Sample type, an exact endpoint if
LLM-backed, and consent/budget for deployment resources and bounded inference remain
pending. No App/runtime store, managed session/memory resource, model call, paid
judge/planner call, or deployment was created or executed. No commit/push or GitHub
operation occurred. Local fail-fast verification does not establish a passing live
App test. The earlier no-workspace-access statement below describes that earlier
checkpoint, before the user selected a profile.

## Client/input/failure fixes and App test preparation — October 7, 2026

Three user-requested workstreams addressed cancellation, history/report navigation,
safe v2 validation, silent input loss, and remote-client dependencies. Initial
regressions reproduced the defects before the fixes. The App-default review premise
was checked against official documentation (pages updated October 6): current
DurableAgentServer/Agent Bricks deployments use `/api/invocations`; MLflow
AgentServer `/responses` is explicit legacy compatibility. The Runtime default
therefore remains, with documented/tested legacy configuration. See
[ADR 0010](docs/adr/0010-client-input-and-failure-contracts.md), still requiring
designated maintainer review.

The shipped renderer now handles terminal planless reports without inventing a
plan or measurements; recovered v2 history links are usable. Cancellation
acknowledgments are accepted only on cancel responses. Fixed message adapters
reject extra top-level fields before planning/inference and preserve nested
messages. V2 schema failures disclose bounded safe locations/messages, not values,
arbitrary keys, validator context, or exception text. An independent cross-workstream
read-only review found no additional confirmed actionable regressions; this is not
an independent security audit or maintainer approval.

Focused workstream evidence:

- Lifecycle/error integration: **117 passed in 12.11 seconds**, including actual
  SDK/API cancellation, recovered mixed-version history, shipped-DOM planless
  report rendering, validation bounds, and raw-validator redaction.
- App/input/local integration: **245 passed in 31.69 seconds**. The final App
  harness-only rerun passed **13 tests in 2.61 seconds**, including failed probe
  stops with exactly one invocation and no measured load. No paid traffic occurred.
- Remote packaging/CLI/Python: **139 passed in 24.05 seconds**; final wheel-only
  tests passed **13 tests**. The real built wheel installs with only 11 base
  transitive packages plus EvalSurge, no server distributions, and passes SDK
  submit/wait, CLI run/doctor, installed entrypoint, lazy exports, and missing-extra
  checks through controlled HTTP transports.

Integrated root verification on macOS/Python 3.12.13:

```bash
uv sync --locked --extra agents --group dev \
  --default-index https://pypi.org/simple --offline --no-build-isolation
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q --tb=short
uv run --no-sync python scripts/export_openapi.py
uv run --no-sync python scripts/export_openapi.py --check
uv run --no-sync openapi-spec-validator docs/openapi.json
uv build --no-build-isolation
uv run --no-sync python scripts/verify_wheel.py
uv run --no-sync python scripts/verify_remote_install.py --offline
uv lock --check --offline --default-index https://pypi.org/simple
uv run --no-sync python scripts/check_ci_prerequisites.py
node --check benchmark_agents/static/report.js
git diff --check
```

Results: locked sync/check resolved **190 packages** and checked **182 installed
packages**; Ruff lint passed and **128 files** were already formatted. Full suite:
**651 passed, no skips, 30 upstream warnings, 183.51 seconds**. Warnings are existing
MLflow/pandas/SQLAlchemy notices. After the final case-schema description edit,
`uv run --no-sync pytest -q tests/test_v2.py tests/test_readme.py tests/test_docs_ui.py
--tb=short` passed **19 tests in 6.87 seconds**. Its first invocation referenced a
nonexistent `tests/test_docs.py` and ran no tests; the corrected invocation above
passed. Snapshot export/check and independent OpenAPI validation passed. Sdist/wheel
were rebuilt after that description edit; required-asset and isolated remote-install
verification passed. Independent archive reads confirmed byte-for-byte parity for
**47 packaged runtime/UI files**. JavaScript syntax and whitespace checks passed.

Manual public-contract review found only documentation changes to existing input
schemas, an optional v2 `error.errors` property, and its new bounded component in
the OpenAPI diff. Runtime compatibility still intentionally tightens formerly
ignored inputs, versions mixed history links, and requires the server extra for
local execution; schema equality alone would not detect those changes. Existing
v1 envelopes and the shared Locust/evaluation pipeline remain.

All **189 non-root lock records** compare equal to HEAD, including dependency graphs,
versions, sources, URLs, and hashes. Public provenance checks passed. Public PyPI
resolution remained blocked with TCP connection refused even outside the sandbox;
the migration edits only the editable root dependency/extra metadata and passes
locked/offline consistency checks. This is not a fresh dependency upgrade, new
advisory audit, or clean online supported-interpreter installation. The existing
`agents` install continues to include server plus framework dependencies.

Added [the App validation runbook](docs/DATABRICKS_APP_VALIDATION.md) and a
dry-run-by-default harness. Only local profile names/hosts were listed with
`databricks auth profiles --skip-validate -o json`; that is not authentication
validation. The requested workspace is known, but the exact profile, deployed App,
safe prompt, and bounded traffic/internal spend/recovery consent remain unselected.
No workspace lookup, live inference, paid planning/judging, App deployment, GitHub
access, commits, or pushes were performed. Remote CI and maintainer approval have
not been checked for this patch. Tiny local controlled tests do not establish
live App health, full production input equivalence, quality calibration, sustainable
capacity, or shared-hosting readiness.

## Pre-push repository review — October 7, 2026

The user authorized publishing the implementation after a repository and dependency
scan. Read-only review found three concrete issues, fixed before publication:

- The SDK/CLI report link used `?run_id=` while the shipped browser reads `?run=`.
  A regression executing the actual report renderer confirms the old URL made no
  report fetch and the corrected SDK URL loads the requested run. Focused
  SDK/CLI/report tests passed **105 tests in 4.56 seconds**.
- Cancellation before or during deferred planning left inference `pending` on a
  terminal run. Both regressions failed before the fix; `_skip_load` now marks
  unstarted inference `not_run`. Focused v2/coordinator/foundation tests passed
  **21 tests in 3.68 seconds**.
- App profile guards omitted several SDK identity/auth-routing fields not tagged
  as credentials in SDK metadata. The shared presence-only guard now includes
  those inputs; offline native Config precedence and pre-SDK/doctor regressions
  prevent the override without provider traffic or OAuth reproduction. The scoped
  App/runtime/settings/diagnostics suite passed **104 tests in 1.61 seconds**.

README and the v2 guide now include the complete automatic-evaluation request,
authoritative-reference requirements, default-off behavior, constrained LLM judge
selection, operator provider prerequisites, and per-judge sampling/cost semantics.
Credential-snapshot rotation guidance is explicit. README contract/link tests
passed **4 tests in 3.10 seconds**. Final full verification after these fixes:

- `uv sync --locked --extra agents --group dev --default-index
  https://pypi.org/simple --offline --no-build-isolation`: 190 resolved packages,
  182 installed packages checked; cached locked environment retained.
- `uv run --no-sync pytest -q --tb=short`: **601 passed, no skips, 30 upstream
  warnings, 186.12 seconds**.
- Ruff lint passed and formatting checked **120 files**. OpenAPI snapshot equality
  and independent schema validation passed; the public schema remains unchanged
  by the pre-push fixes.
- Sdist/wheel build and required-asset verification passed; **46 packaged runtime/UI
  files** matched the checkout byte-for-byte. Shipped renderer and test harness
  JavaScript syntax checks passed. Lock/provenance and whitespace checks passed.
- A narrow credential-signature/path check of the **53 changed/new candidate
  files** found no forbidden artifacts or common credential signatures. Ignored
  environments, profiles, stores, and run artifacts are excluded. This is not a
  comprehensive secret or security audit.

Dependency review used official upstream release metadata for all 22 declared
runtime/framework/dev/build dependencies, package-specific monorepo releases, and
CI/vendored asset releases. Seven packages have newer observed releases; MLflow
3.17 is intentionally excluded pending private rubric API/hash review. The exact
versions, sources, index limitation, and follow-up are recorded in
[the dependency policy](docs/DEPENDENCIES.md#pre-push-upstream-review--october-7-2026).
No dependency versions, ranges, artifact origins/hashes, or lockfile were changed.
Public PyPI metadata requests failed with TCP connection refused inside and outside
the sandbox; this is not a successful latest-compatible resolution or install.

```bash
uv export --quiet --locked --default-index https://pypi.org/simple \
  --extra agents --group dev --no-emit-project \
  --output-file artifacts/prepush-20261007/audit-requirements.txt
uv run --no-sync pip-audit --disable-pip --require-hashes \
  --progress-spinner off --vulnerability-service osv --timeout 10 \
  --requirement artifacts/prepush-20261007/audit-requirements.txt \
  --format json --output artifacts/prepush-20261007/audit.json
```

The OSV audit passed: **181 applicable dependencies, zero known advisories**.
Initial uv export/audit attempts hit sandbox cache permissions; the approved retry
succeeded. OSV enforces hash presence, not validity; uv verifies artifact hashes.
A narrow GitHub Advisory Database query found no matching `swagger-ui-dist@5.33.1`
advisories. This is not a comprehensive security/license audit or a supported-
interpreter clean-install matrix. Dependabot PR #4 was inspected read-only, not
merged, rebased, or otherwise modified. GitHub identity was verified as the personal
account authorized for `RamVegiraju/EvalSurge`; remote settings remain unchanged.

## Registered-target v2 API and Databricks Apps — October 7, 2026

Implemented additive v2 admission/status/result/report/cancel/capabilities, deferred
owned planning, the remote SDK and packaged CLI, immutable operator settings,
configuration-only diagnostics, and synchronous Databricks App resolution/OAuth/
invocation support. V1 continues to use the same coordinator and one Locust engine;
judging reuses captured answers. Evaluation is off by default. ADR 0009 and these
public/trust-boundary changes require designated maintainer review.

Local environment: macOS 26.6.2 arm64, Python 3.12.13, Databricks SDK 0.146.0,
MLflow 3.16.1, Locust 2.46.6, FastAPI 0.142.2, OpenAI 3.22.1, LangGraph 1.2.12,
and OpenAI Agents 0.22.3. No dependency version or lockfile changes were made.

`uv sync --locked --extra agents --group dev` initially rejected this machine's
different default index as requiring a lock update; the lock was not rewritten.
Selecting public PyPI explicitly then failed fetching Hatchling for an isolated
build with a connection-refused error, including the required retry outside the
sandbox. The cached, non-isolated install succeeded with:

```bash
uv sync --locked --extra agents --group dev \
  --default-index https://pypi.org/simple --offline --no-build-isolation
```

It resolved 190 packages and rebuilt/installed the editable project. Subsequent
checks use `uv run --no-sync` to preserve that locked installed environment rather
than implicitly resolving through the machine's different default registry.
This is not a successful clean online installation or updated dependency audit.

Tests cover actual remote SDK/CLI → REST → localhost Locust traffic, packaged CLI
entrypoint execution, native SDK configuration/discovery/OAuth with controlled
HTTP boundaries, strict synchronous invocation completion/correlation, legacy
Responses trace events, and native framework/MLflow integration. Static diagnostics
forbid SDK imports/calls and redact operator values. File snapshots survive source
edits/deletion; contexts propagate through tasks/threads/worker environments without
global mutation. App identity/config-file conflicts fail before SDK resolution.

Final review reproduced a planning-recovery defect: a terminal interrupted run
left its unstarted inference phase pending. The new regression failed with
`pending != not_run`, then passed after recovery explicitly marked it `not_run`.
Focused v2/coordinator/foundation tests passed **20 tests in 3.66 seconds**.
The README checks passed **3 tests in 2.81 seconds**. Intermediate full-suite
runs passed **568 tests in 177.28 seconds** and **571 tests in 176.68 seconds**,
each with 30 upstream MLflow/pandas/SQLAlchemy warnings. After all implementation
files were frozen, final `uv run --no-sync pytest -q --tb=short` passed
**578 tests, no skips, 30 upstream warnings, in 177.40 seconds**.

Final non-test gates passed:

- `uv run --no-sync ruff check .` and `uv run --no-sync ruff format --check .`:
  lint clean; **120 files already formatted**.
- `uv run --no-sync python scripts/export_openapi.py --check` and
  `uv run --no-sync openapi-spec-validator docs/openapi.json`: snapshot equality
  and independent OpenAPI validation passed.
- `uv build --no-build-isolation`: sdist and wheel built successfully.
  `uv run --no-sync python scripts/verify_wheel.py` verified required package/UI
  assets; independent archive reads confirmed byte-for-byte checkout parity for
  **46 packaged runtime/UI files**. The integration suite separately executes
  the built wheel's CLI entrypoint.
- `uv lock --check --offline --default-index https://pypi.org/simple`: 190 resolved
  packages; `uv run --no-sync python scripts/check_ci_prerequisites.py` verified
  public registry/artifact provenance for **189 locked dependency packages**.
  `uv.lock` remains unchanged; this does not relabel mirror artifacts.
- `node --check benchmark_agents/static/report.js` and `git diff --check` passed.

Final App/runtime/settings/diagnostics focused checks passed **84 tests in 1.53
seconds**, including the native config-file consistency regressions. Hard OAuth
deadlines remain a documented limitation rather than a passing local test claim.

Schema review against `41311ac9b523e37ba7e4909fdbd1bd84f5d915bf` reports zero
breaking/potentially breaking changes. Lint reports zero errors, 130 warnings,
and 50 informational findings; design score is **71.76/100 (C)**, not a sign-off.
Raw generated reports are retained in `docs/review/v2-*.json` and interpreted in
[the API review](docs/API_REVIEW.md). These tools do not replace behavior tests.

No live Databricks/App deployment, paid inference/planning/judging, GitHub access,
remote-service changes, commits, or pushes were performed. SDK HTTP/retry budgets
are not hard deadlines for OAuth/CLI credential work; thread offloading cannot
terminate a stalled credential source. Hard discovery/auth isolation, background/
resumable invocation, planless browser reports, lifecycle/retention/capacity
campaigns, distributed workers/stores, and shared hosting remain gaps or later
milestones. Local controlled tests do not establish sustainable capacity, judge
calibration, remote CI success, browser layout, or production readiness.

## Agent-oriented Python examples — October 6, 2026

The phase-named `quality_benchmark.py` tutorial was replaced before release with
separate `langgraph_benchmark.py` and `openai_agents_benchmark.py` scripts. Each
uses the public Python facade against the corresponding real framework demo and
combines bounded load, authoritative references, explicit relevance/correctness
judges, and one typed report. The credential-free `python_benchmark.py` remains
the first quickstart. Framework implementation and advanced orchestration remain
in `framework_agent.py` and `scripts/validation/` rather than being copied into
the public requests.

The example integration suite executes both scripts through the actual LangGraph
graph and OpenAI Agents runner, Locust subprocess, native MLflow tracking and
evaluation APIs, correlated tool/model/memory profiles, and controlled provider
boundaries. It also verifies both inference and judge-readiness fail-fast paths,
safe imports and argument rejection, durable report reopening, documentation
links, and strict example inventory. No paid model or Databricks workspace call
is part of this validation.

- `UV_OFFLINE=1 MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync pytest -q
  tests/test_simple_examples.py --tb=short`: **16 passed**, 13 upstream
  MLflow/pandas/SQLAlchemy warnings, **18.54 seconds**.
- Full suite: **422 passed, no skips**, 30 upstream warnings, **176.05 seconds**.
  The log is retained under `artifacts/agent-examples-20261006/pytest.log`.
- Ruff lint and formatting passed for 102 files. OpenAPI snapshot equality and
  independent schema validation, JavaScript syntax, and whitespace checks passed.
- Offline sdist/wheel builds passed. The fresh wheel's required Python/API/report
  assets were verified directly, and archive inspection confirmed all three public
  Python requests plus both supporting agents and the example index. The first
  verifier CLI invocation inspected an older wheel in `dist/` because that command
  does not accept a path; it failed on that stale artifact before the fresh wheel
  in this validation directory passed direct verification.

No runtime API, load-engine, evaluation semantics, dependencies, lockfile,
credentials, remote settings, commits, or pushes changed in this reorganization.

## Minimal Python examples and complete example coverage — October 6, 2026

The user-facing benchmark now has 23 lines and the opt-in quality example has
33 lines. Both use the public Python facade, without REST polling or API-server
orchestration. Advanced CLIs and framework/provider validation moved to
`scripts/validation/`, with updated imports, commands, and repository-relative
dotenv paths. Unsupported tutorial CLI flags fail before admission rather than
silently loading the default target. The obsolete smoke script and its request
fixture were removed after caller review: their missing correctness reference
conflicts with fail-fast evaluation readiness.

All four remaining example modules have integration coverage. The new checks
execute the published scripts against the actual mock agent over localhost
Uvicorn/Locust, exercise inference and judge-readiness failures, verify printed
typed reports and durable reopening, and perform native MLflow scoring with a
controlled provider boundary. Negative quality verdicts remain completed
evaluations, not execution failures. The moved framework harness runs actual
LangGraph and OpenAI Agents with isolated memory, tools, correlated MLflow spans,
and report retrieval. An inventory regression and contribution guidance require
new examples to extend the coverage. Live Databricks helpers receive import,
dotenv-path, and missing-configuration guard checks, not a new paid/live success
validation.

- Initial minimal-example regression failed against the old CLI as expected.
  Early checks also corrected test parsing for MLflow's console banner and the
  existing `evaluation_status="failed"` judge-readiness contract; production
  lifecycle semantics were not changed.
- Final `uv run --no-sync pytest -q tests/test_simple_examples.py
  tests/test_validation_tools.py`: **19 passed**, seven upstream warnings,
  **16.33 seconds**.
- First full `uv run --no-sync pytest -q`: **416 passed, one failed**,
  24 upstream warnings, **198.81 seconds**. The first LangGraph fixture hit its
  unchanged ten-second preflight deadline while native MLflow retried a
  GitHub model-catalog metadata download after DNS resolution failed.
- Installed MLflow 3.16.1 documents an empty `MLFLOW_MODEL_CATALOG_URI` as
  disabling remote fetch. The offline framework fixture now sets it explicitly;
  no runtime configuration or request deadline changed. The failing case passed
  alone in **3.89 seconds**, with one upstream warning.
- Full recheck: **417 passed, no skips**, 24 upstream warnings,
  **169.83 seconds**. Initial and successful logs remain separately under
  `artifacts/simpler-examples-20261006/`.
- Ruff lint/format passed for 101 files; OpenAPI snapshot equality and schema
  validation, JavaScript syntax, and whitespace checks passed.
- Offline sdist/wheel builds passed. Archive inspection verified all 38 packaged
  runtime/UI files against the checkout, the current README, all four example
  sources and their index, and the moved validation tools.

No benchmark-library behavior, dependencies, model/provider profiles, paid calls,
remote repository settings, commits, or pushes changed in this work. The full
suite uses controlled providers; it is not a live deployment, judge calibration,
latest-dependency, remote CI, or production-readiness claim.

## Remote documentation integration — October 6, 2026

The initial push of `fda02c4` was rejected because remote main had advanced to
`fb8ce89`, containing the runner-placement documentation. Both histories were
preserved in a merge, retaining public-PyPI setup and distinguishing REST-host
load generation from local Python execution. The integration changes only
documentation; runtime code and dependencies remain identical to `fda02c4`.
`uv run --no-sync pytest -q tests/test_readme.py` passed **3 tests** in
**3.11 seconds** after conflict resolution. Whitespace checks passed and no
conflict markers remained. The full 398-test suite was not repeated for this
documentation-only integration.

## README examples and commit preparation — October 6, 2026

The README now includes a minimal Python input with authoritative references,
an opt-in quality policy, and an explicitly illustrative report excerpt. It
separates the no-model performance-only quickstart from configured LLM judging,
explains per-judge sampling and total runtime, and distinguishes completed
lifecycle, negative quality verdicts, and execution errors. Local navigation
remains focused on setup, usage, contribution, license, and deeper documentation.

The new README regression runs the published synchronous Python request through
actual Locust against a local SSE fixture, verifies its 20 successful measured
requests plus one excluded probe, parses printed JSON as `RunReport`, and reopens
the persisted report. Other checks validate the optional policy, normalize the
documented failure through the shipped assessment helper, and resolve local
documentation links/anchors. No model or remote-agent calls are made.

- Focused README/foundations/Python/Requests checks: **29 passed**, 28.88 seconds.
- Full suite: **398 passed, no skips**, 18 upstream warnings, 161.71 seconds.
- Final `uv run --no-sync pytest -q tests/test_readme.py`, after the setup
  command assertion was added: **3 passed**, 3.00 seconds.
- Ruff lint/format: 96 files; OpenAPI equality/schema, JS syntax, and whitespace
  checks pass. Public registry/artifact checks verify 189 dependency packages.
- `uv lock --check --offline --default-index https://pypi.org/simple` passes
  with 190 resolved packages including the project. An initial check against this
  machine's different default registry reported a stale lock; selecting the
  lock's actual public index passed without rewriting it.
- `uv build --offline --no-build-isolation --out-dir
  artifacts/readme-commit-20261006/package` built the sdist and wheel. The
  wheel verifier passed, all 38 runtime/UI files matched the checkout byte for
  byte, and both distributions included the current README. No install or
  package-content execution was performed by this archive inspection.

The README/Python guide now select public PyPI explicitly during locked setup
and use `--no-sync` for subsequent example commands, avoiding an implicit
re-resolution through a machine-specific mirror. This is not a fresh
latest-compatible upgrade, a remote CI result, or a new clean-install matrix.

A narrow commit-candidate path/signature check found no forbidden artifact paths
or common credential signatures across 68 changed/new source, test, configuration,
and documentation files. It is not a comprehensive secret or security audit.
Ignored run artifacts, local stores, `.env`, and `.venv` remain excluded. Validation
evidence is retained under `artifacts/readme-commit-20261006/`; previous paid-test
failures and release limitations remain unchanged.

## Per-assessment failure reasons — October 5–6, 2026

Evaluated criteria now retain bounded request-correlated `assessments`, including
boolean quality outcomes, native judge rationales, and fixed safe execution
diagnostics. Native datasets carry explicit request IDs and tags; result rows
are never joined by query text or completion order. Numeric/categorical scores
receive no inferred threshold. Missing explanations remain null; duplicated or
missing correlation is unavailable evidence. Rationales are protected evaluation
content, not sanitized profiling. ADR 0008 requires maintainer review.

Installed MLflow 3.16.1 source was checked for dataset request IDs/tags, result
DataFrame value/rationale/error columns, raw assessment metadata, and native run
scope. Actual local native evaluations verify repeated inputs, negative/positive
verdicts, catalog rate limits, and registered scorer errors. Error bodies and
error-associated rationales are not exported. The same native assessment details
survive the Python facade and authenticated REST run/report retrieval with
`Cache-Control: no-store`. DOM tests verify each failed reason, inert hostile
text, missing/truncated rationale, and historical report behavior.

Validation commands use the already-installed environment, without synchronization
or dependency upgrades:

- `uv run --no-sync pytest -q`: first run **394 passed, one failed**, 18 upstream
  warnings, 190.45 seconds. The unchanged localhost concurrency/Unicode test
  recorded two streamed `ConnectionError` attempts after HTTP 200. Its focused
  rerun passed in 1.51 seconds; no unrelated runtime/test code was changed.
- Full `uv run --no-sync pytest -q` recheck: **395 passed, no skips**, 18 upstream
  warnings, 155.41 seconds. Initial failure/journals and both logs are retained.
- A final diagnostic-preservation tweak keeps the existing criterion-level HTTP
  status. Focused final native/detail/registry/report tests: **70 passed**,
  seven upstream warnings, 7.90 seconds.
- Ruff lint and format checks pass for 95 files; OpenAPI snapshot equality/schema
  validation, JavaScript syntax, and whitespace checks pass.
- Offline sdist/wheel build succeeds with installed dependencies. Required assets
  and all 38 packaged runtime/UI files are verified against the checkout.

Evidence lives under ignored `artifacts/evaluation-reasons-20261005/`. The existing
real three-minute run's five relevance and five correctness assessments were
read from a read-only backup of its local MLflow database, with no re-judging.
Historical native Feedback has a null `run_id` property but retains explicit
source-run metadata; the initial read-only preview attempt failed that check,
then was corrected to use the recorded metadata.

For this synthetic presentation copy only, unique exact input/output/reference
fingerprints verified all historical identities before adding details. This is
not a shipped fallback for missing request tags. The report preview now shows
both negative correctness verdicts and their actual stored rationales; all
benchmark metrics, score rates, and original run/report/plan-request file hashes
remain unchanged. Its live JSON, shell, and current assets return HTTP 200, and
the shipped DOM renderer verifies both reasons. Browser layout is not verified.

No new inference/planning/judge calls, paid benchmarks, dependency changes,
commits, pushes, or external-service mutations were performed for this feature.
Previous live failures and release limitations remain unchanged.

## MLflow experiment navigation — October 5, 2026

Reports now expose optional, bounded `mlflow_experiments` links for authorized
trace experiments and native evaluation experiments. Native evaluation records
its already-known experiment ID; report reads never query MLflow or resolve SDK
credentials. Operator UI overrides require exact frozen-store matching; the
model/judge workspace is never assumed to be the tracking workspace. Unsafe
destinations are omitted, and browser links forward neither API keys nor referrers.

The first regression collection failed because `report_links` did not exist.
After implementation, focused link/UI/profiling/native tests passed 68 tests
with three retained upstream warnings. The full offline suite passed **373 tests,
no skips**, with the existing **16 upstream warnings**, in **153.92 seconds**.
Its log remains at `artifacts/mlflow-report-links-20261005/pytest.log`.
Ruff lint/format (92 files), OpenAPI export equality/schema validation, JavaScript
syntax, and whitespace checks passed. Locked-backend offline sdist/wheel builds
passed; required modules/assets and changed-runtime source parity were verified.
No dependencies, paid model calls, remote settings, commits, or pushes changed.
Installed MLflow 3.16.1 experiment routing and native run metadata were checked;
this is not an all-upstream-latest or production-readiness claim.

The operator approved a local MLflow UI for the previous real three-minute run.
A read-only report preview uses a presentation copy of its run/plan/profiling
files; verified evaluation experiment IDs were read from the actual local SQLite
store and added only to that copy. The original benchmark run/plan/report files,
scores, and all existing viewers remain unchanged. MLflow serves the actual
existing database on loopback. Neither viewer starts an agent, planner, or judge.

The first preview verifier incorrectly expected separate experiments; actual
native metadata confirms both traces and evaluations are in experiment `1`.
That assertion failure stopped only its owned viewers. The corrected verifier
checks one merged trace/evaluation link, unchanged 896-request metrics and sampled
scores, native experiment HTTP access, and the shipped JavaScript/DOM rendering.
The initial presentation copy and UI log remain retained. Successful preview,
metadata, report, and renderer evidence live under the same ignored artifact
directory. Both the report shell and actual MLflow experiment UI returned HTTP
200, served report JavaScript matched the checkout, and this preview rejected
new benchmark submissions with HTTP 405. This is not browser layout verification.
Historical unknown experiment
IDs are otherwise omitted; original reports are never silently backfilled.
ADR 0007 and the additive public response field require maintainer review.

## Real three-minute Requests retest — October 5, 2026

The operator authorized another real-model test using the previously selected
Databricks workspace/profile and `databricks-gpt-5-4-mini`. Python Requests submitted
one REST run against the local LangGraph demo, with actual model inference,
request-isolated memory, synthetic read-only policy/retrieval tools, and MLflow
tracing. Explicit relevance/correctness criteria bypassed paid planning; this run
does not validate LLM judge suggestion or a deployed Databricks App.

Run `d6325334-bea8-47a7-bd28-444817dd9b65` completed:

| Observation | Actual result |
| --- | --- |
| Configured / observed HTTP concurrency | 5 / 5 |
| Dispatch limit / request cap | 180 seconds / 5,000 attempts |
| Last dispatch / elapsed including drain | 179.785 / 180.656 seconds |
| Measured successes / attempts | 896 / 896 |
| Error rate / incomplete measurements | 0 / 0 |
| Successful throughput | 4.960 requests/s |
| Successful latency p50 / p95 | 977.490 / 1,289.012 ms |
| Answer-text TTFT p50 / p95 | 790.648 / 1,072.264 ms; 896 observations |
| Reported output-token usage coverage | 100% |
| Excluded inference probe / judge readiness | Passed / both criteria passed |
| Post-load relevance / correctness | 5/5 / 3/5 sampled answers passed |
| Post-load assessment errors | Zero; five captured outputs scored per criterion |
| Verified internal profiles | 200/896 (22.32%); 696 excluded by the trace budget |
| Observed operation p95 | Model 1,275.105 ms; policy tool 26.374 ms; retrieval 11.336 ms |

The 60% sampled correctness result is a quality verdict, not an evaluation failure
or a population estimate. Judging reused captured outputs, never reinvoked the
agent, and followed measured load/profiling. Inclusive operation durations must
not be added, and this single closed-loop level does not establish sustainable
capacity or calibrated judges.

Exact request, acceptance, frozen plan, result, report, local MLflow database,
driver log, and verification evidence remain separately under ignored
`artifacts/real-three-minute-20261005/`; the earlier failed paid run is unchanged.
`verify_report.py` confirmed the live report JSON matches the saved result, the
report shell and shipped JavaScript return HTTP 200, all 896 journal attempts
completed, and the probe is excluded. The shipped JavaScript/DOM harness renders
the real metrics, 60% correctness, and internal hotspots; this is not browser
layout verification. The target stopped after completion; its new local report
viewer remains available. Existing viewers were untouched. No dependencies,
production code, commits, pushes, or external-service settings changed.

## Evaluation readiness and Requests — October 5, 2026

This change adds static evaluation checks, one excluded native readiness assessment
per selected criterion, safe evaluation/worker diagnostics, a Python Requests
example, and runtime documentation. Both clients retain the shared coordinator and
Locust engine. No paid retest, dependency upgrade, commit, push, or external-service
mutation was performed for this fix.

### Original paid failure retained

The earlier authorized Databricks-backed LangGraph run
`8c54a300-ad49-4269-aced-3e7049707ee0` used five users, a 300-second dispatch limit,
and a 5,000-request cap. It completed 1,448/1,448 measured requests, zero errors,
peak HTTP concurrency five, and 301.37 seconds including drain. Successful
throughput was 4.8047 requests/s; latency p95 was 1,307.77 ms and answer TTFT p95
was 1,066.81 ms. Trace coverage was 200/1,448, with 1,248 budget-excluded attempts.
It remains `completed_with_gaps` with failed evaluation (`AttributeError`).
Original ignored artifacts under `artifacts/real-five-minute-20261005/` were not
rewritten. These observations are not sustainable-capacity evidence.

The offline diagnostic reproduced native MLflow calling `trace.data` on a float:
mixed traced/untraced evaluation records became a nullable Pandas trace column,
with missing values represented as NaN. The native regression now scores both
captured answers without a Trace column for output-only catalog criteria.
Explicit trace-required registered criteria receive only verified actual Traces.
This fix does not relabel the original failed evaluation as successful.

### Native contracts and fail-fast behavior

Installed MLflow 3.16.1 source/signatures were checked for `Feedback`,
`AssessmentError`, `genai.evaluate`, trace-column processing, and rate-limit retries.
The first 429 readiness regression observed four provider calls despite zero SDK
retries: MLflow layered three retries on top. Returning content-free native
errored Feedback eliminates that extra layer; the regression now makes one call
and never starts measured load. Errors have no value, not a false passing verdict.

Controlled native tests cover 401/403/429/500, timeouts, invalid verdicts,
negative valid verdicts, missing provider/references/ready criteria, scoped
registered traces, missing/empty assessments, cancellation/recovery/idempotency,
post-load failure retaining metrics, and subprocess creation/exit/watchdog cleanup.
Initial focused verification passed 15 native/readiness tests in 16.37 seconds;
expanded worker/readiness/Python checks passed 59 in 33.40 seconds.
Requests tests use actual Requests/Uvicorn/Locust traffic and report retrieval,
including authenticated requests, failure diagnostics, and bounded caller waits.
They do not establish real-model quality or deployed Databricks App compatibility.

The first full-suite attempt failed collection on an incorrect native test import;
the test was corrected against the installed export, not an upstream package patched.
The retained failure log is `artifacts/fail-fast-readiness-20261005/pytest.log`.
A verifier command with unsupported `--help` inspected an older wheel in `dist`
and failed; explicit verification of the newly built wheel passed, including new
readiness modules, required assets, and changed-runtime source parity.

| Final check | Actual result |
| --- | --- |
| `MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync pytest -q --tb=short` | 347 passed, no skips; 16 upstream warnings; 381.19 seconds |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 89 files already formatted |
| `uv run --no-sync python scripts/export_openapi.py --check` | Updated snapshot matches |
| `uv run --no-sync openapi-spec-validator docs/openapi.json` | Valid OpenAPI |
| `node --check benchmark_agents/static/report.js` | Passed |
| `uv run --no-sync python scripts/check_ci_prerequisites.py` | 189 public registry/artifact sources verified |
| `uv build --no-build-isolation --offline --out-dir artifacts/fail-fast-readiness-20261005/final-package` | Source distribution and wheel built; required modules/assets and runtime source parity verified |
| `git diff --check` | Passed |

The final full-suite log is
`artifacts/fail-fast-readiness-20261005/final-pytest.log`. Its 16 warnings are the
existing SQLAlchemy loader-strategy deprecation and MLflow/Pandas positional-argument
warnings; none were suppressed. Independent Requests and report-UI focused suites
passed 18 and 35 tests, respectively. Native registered-readiness/recovery checks
passed seven tests in 13.50 seconds. The lock SHA-256 remains
`468ac9fe28395d9a61cc30c3248c92cf530615c24a8a06c4ff1d87aa91efc93a`.

The installed versions remain FastAPI 0.142.2, Uvicorn 0.54.0, Requests 2.34.2,
MLflow 3.16.1, Locust 2.46.6, OpenAI 3.22.1, Agents 0.22.3, LangGraph 1.2.12,
Pydantic 2.13.5, and Ruff 0.16.10. Public-index metadata access failed even outside
the sandbox; installed-contract verification is not an all-upstream-latest claim.
The dependency-update gate and observed newer releases in `docs/DEPENDENCIES.md`
remain explicit. Hard judge/trace phase deadlines, calibrated judgments, fresh
public-index installation, current remote CI, and shared production readiness are
not established. ADR 0006 requires maintainer review.

## Shared coordinator, Python API, and JSON — October 5, 2026

Four parallel workstreams implemented the shared coordinator/Python facade, bounded
JSON adapter, CI dependency-source recovery, and independent contract/failure review.
Both REST and local Python use the existing Locust engine. No Databricks workspace
operations, paid inference, commits, pushes, or remote setting changes were performed
for this milestone. The desktop documentation work was not pulled or overwritten.

The root lock is the authentic public-PyPI graph from Dependabot PR #1, commit
`d81e43531ffa1f1ee6e8890304f3fa3a5a3861b2`; its SHA-256 remains
`468ac9fe28395d9a61cc30c3248c92cf530615c24a8a06c4ff1d87aa91efc93a`.
No artifact URLs, version records, or hashes were relabeled. On macOS/Python 3.12.13,
uv 0.11.28 installed 181 applicable dependencies. Key versions are FastAPI 0.142.2,
OpenAI 3.22.1, Agents 0.22.3, LangGraph 1.2.12, Locust 2.46.6, MLflow 3.16.1,
and Ruff 0.16.10. This is a verified recovery graph, not an all-upstream-latest graph.

The synchronized root editable environment uses the same lock and installed backend:

```bash
env -u UV_INDEX -u UV_INDEX_URL -u UV_EXTRA_INDEX_URL uv sync \
  --no-config --locked --extra agents --group dev \
  --default-index https://pypi.org/simple \
  --cache-dir artifacts/ci-public-lock/cache --python 3.12 \
  --no-python-downloads --offline --no-build-isolation
```

Earlier current-code verification against the separate public candidate passed
272 tests without skips. The root environment then passed 275 tests in 108.06 seconds
before the independent review corrections. Two new REST regressions failed first
because plan-storage faults returned `http_500` instead of the previous
`internal_error`. The fix preserves the existing code, stops new planning/admission,
and states that no agent preflight/load started; prior planning may already incur
cost. Focused lifecycle/failure/cleanup verification subsequently passed 23 tests.

| Final check | Actual result |
| --- | --- |
| `uv run --no-sync python scripts/check_ci_prerequisites.py` | 189 registry/artifact sources verified public |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 80 files already formatted |
| `MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync pytest tests -q --tb=short` | 277 passed, no skips; four upstream warnings; 104.79 seconds |
| `uv run --no-sync python scripts/export_openapi.py --check` | Snapshot matches |
| `uv run --no-sync openapi-spec-validator docs/openapi.json` | Valid OpenAPI |
| `node --check benchmark_agents/static/report.js` | Passed |
| Locked-backend sdist/wheel build and package verification | Both namespaces, report/docs assets, wheel RECORD hashes, and source parity verified |
| Offline wheel import from outside the checkout | Installed package imported with network blocked and no agent/judge calls |
| `git diff --check` | Passed |

The four warnings are the retained SQLAlchemy loader-strategy deprecation and
three MLflow/pandas positional-argument warnings; none were suppressed.
The final suite includes actual framework streaming/tools/memory, native MLflow
evaluation/registered scorers, real Locust JSON/SSE traffic, first-case failure
exclusion, cancellation/drain, recovery/idempotency, detached Python inputs/results,
storage faults, workload bounds, OpenAPI/report contracts, and editable packaging.
The final pytest log is `artifacts/python-api-public-lock-20261005/final-pytest.log`.
Package evidence is `artifacts/final-package-20261005/`; third-party dependencies
for the installed-wheel import were supplied by the previously verified public
environment. This is not a clean online dependency installation from an empty cache.
API review versus `d83ef4a` reports zero explicit/potential breaks, zero lint errors,
74 warnings, and 28 informational findings; its score is 77.31/100 (C), not a B
sign-off. See `docs/API_REVIEW.md` for the accepted local-alpha limitations.

### Python request-to-report smoke

```bash
MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync python \
  artifacts/python-api-public-lock-20261005/run_smoke.py
```

| Protocol / client | Run ID | Preflight | Measured successes | Answer TTFT coverage |
| --- | --- | --- | --- | --- |
| OpenAI Chat SSE / sync | `0f5d979d-5a77-40ba-8e67-3b3f9c94089d` | Passed | 2/2 | 2/2 |
| HTTP JSON / native async | `56104d88-b25a-4767-b48a-bfdc3212d665` | Passed | 2/2 | 0/2; percentiles null |

Each run made exactly one excluded preflight plus two measured calls through actual
Locust subprocesses to an ephemeral loopback fixture. Both typed reports and the
shipped JavaScript/DOM harness expose exactly two attempt rows, passed preflight,
performance-only status, and explicit zero trace coverage. Neither case requested
judging or constructed a provider client. The server socket/task and four owned
Locust subprocesses stopped; saved-evidence preview servers were untouched.
Evidence and source/version hashes are in `artifacts/python-api-public-lock-20261005/`.
The smoke preceded the final storage-error wording correction; full/focused tests
cover that correction. Older facade evidence remains in
`artifacts/python-api-smoke-20261005/` with its original FastAPI 0.141.1 environment.

### Failures retained and release limits

- An initial unrestricted pytest invocation collected downloaded upstream gevent
  tests under the ignored artifact cache and exited during collection. The project
  now declares `testpaths = ["tests"]`; scoped full-suite verification is separate
  from that failed collection.
- The separate candidate initially omitted project installation, so the direct
  OpenAPI export script could not import the package. Module invocation passed;
  the documented direct command passes in the synchronized root editable install.
- Automatic Hatchling discovery of two import namespaces required uncached
  `editables` during offline editable installation. Explicit `dev-mode-dirs = ["."]`
  allows the locked non-isolated editable build to expose both namespaces without
  importing `editables`; a real editable-build regression verifies the wheel.
  Hatchling still declares a dynamic `editables~=0.3` requirement for isolated
  editable builds. That separate resolution was not validated from a clean index.
  Offline isolated build metadata was also unavailable, so the recorded root sync
  uses the locked, installed backend rather than claiming an isolated online build.
- The OSV audit checked 181 applicable agents/dev/build dependencies with zero known
  advisories. MLflow distribution hashes, private prompt signatures, and the rubric
  hash remain unchanged; the `<3.17` exception remains. Audit scope is local Python
  3.12, not an independent security review or supported-interpreter matrix.
- Current main runs `37311757111` and `37322866817` failed all eight jobs downloading
  from `pypi-proxy.cloud.databricks.com`; tests/audits never ran. The public-lock
  prerequisite check and CI index configuration address that observed cause locally.
  PR #1's older eight-job success is not current-code CI evidence.
- Fresh public-index latest-compatible resolution still fails with TCP connection
  refused. Observed newer OpenAI/Agents/Locust releases were not installed or claimed
  compatible. See `docs/DEPENDENCIES.md` for provenance and the remaining upgrade gate.

Endpoint-only smoke cannot establish internal tool timings, calibrated judges,
model quality, sustainable capacity, browser layout/accessibility, deployed
Databricks App compatibility, clean public-index release installation, current
remote CI, or shared production readiness. Databricks App onboarding/OAuth, tracing
helpers, optional-extras redesign, and staged capacity discovery remain separate
milestones. ADR 0005 and public contract changes require maintainer review.

## Three-minute Python example — October 5, 2026

The operator requested a multi-minute sample Python request. A temporary local
`examples.mock_agent` served on an ephemeral loopback port; no real models,
Databricks profiles/workspaces, or judge calls were used. The example uses the
public synchronous facade, two users, a 180-second dispatch window, a 10,000-request
cap, and a ten-second request deadline. The cap and duration are competing stopping
conditions; the actual run ended by duration, not the request cap.

```bash
uv run --no-sync uvicorn examples.mock_agent:app \
  --host 127.0.0.1 --port 0 --no-proxy-headers --no-access-log

MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync python -m examples.python_benchmark \
  --url http://127.0.0.1:65329/chat --duration 180 \
  --artifact-dir artifacts/python-three-minute-20261005
```

Run `70bc1751-5d1f-4fe9-a601-51ee7ae3806c` completed with passed preflight:

| Observation | Actual result |
| --- | --- |
| Measured successes / attempts | 6,634 / 6,634 |
| Excluded first-case preflight | 1 successful request |
| Dispatch / elapsed including drain | 179.949 / 180.035 seconds |
| Configured / observed HTTP concurrency | 2 / 2 |
| Error rate / incomplete measurements | 0 / 0 |
| Successful TPS | 36.848 |
| Successful latency p50 / p95 | 53.946 / 54.401 ms |
| Answer-text TTFT p50 / p95 | 27.317 / 28.025 ms; 6,634 observations |
| Model calls / judging | 0 / disabled |
| Internal trace coverage | 0%; the mock has no instrumentation |
| Saved report / rendered first page | 6,634 total attempts; 25 visible rows |

The journal confirms all completions and exactly one separate probe, whose ID never
appears among measured requests. The saved report renders through the shipped
JavaScript/DOM harness with completed status, passed preflight, performance-only
judging text, and correct page totals. Both owned Locust workers and the temporary
agent stopped. Existing preview servers were not touched. Raw reports, journal,
stdout/stderr, renderer output, versions, and hashes remain under
`artifacts/python-three-minute-20261005/`.

New CLI regressions failed before the example existed, then passed three tests:
bounded actual subprocess success, first-request failure with safe saved report
and nonzero exit, and defaults that do not silently retain the 100-request cap.
The full offline suite passed **280 tests, no skips**, with the same four upstream
warnings in **117.00 seconds**. Ruff lint/format passed with 82 formatted files;
OpenAPI snapshot/schema, report syntax, and whitespace checks passed.
The full suite ran concurrently with the longer smoke, so its timings are not an
isolated performance baseline or capacity evidence. Usage and report UI commands
are in `docs/PYTHON_API.md`; the example is checkout tooling, not a wheel CLI.

The report verifier's first attempt incorrectly passed a journal filename to
`recover_rows`, whose contract is a directory and a `(rows, incomplete)` tuple.
Correcting the helper yielded the successful independent journal/renderer checks;
the benchmark itself did not fail and was not repeated. Browser layout, model
quality, internal tool timings, remote capacity, and judge calibration are not
established by this synthetic run. No dependencies or remote state changed.

## Inference-preflight verification — October 5, 2026 (UTC)

Mandatory first-case inference preflight uses the existing Locust engine. Failed
checks skip measured load, profiling, and judging, with safe API/report errors.
The probe is one extra invocation; measured request pages, metrics, profiles, and
judge inputs exclude it. No dependencies changed and no paid models were called.

| Check | Actual result |
| --- | --- |
| `uv sync --locked --extra agents --group dev` | 190 resolved / 182 installed packages checked |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 66 files already formatted |
| `MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync pytest -q --tb=short` | 119 passed, no skips; 78.21 seconds |
| `uv run --no-sync python scripts/export_openapi.py --check` | Regenerated snapshot matches |
| `uv run --no-sync openapi-spec-validator docs/openapi.json` | Valid OpenAPI |
| `node --check benchmark_agents/static/report.js` | Passed |
| `uv build --no-build-isolation` and `scripts/verify_wheel.py` | sdist/wheel built; API/report/docs assets verified |
| `git diff --check` | Passed |

The same four upstream SQLAlchemy/MLflow/pandas warnings remain. New coverage checks
HTTP/auth errors, redirects, provider error events, empty/malformed/filtered/truncated
streams, wrong content type, deadlines and connection failures, worker startup/kill,
cancellation/drain, restart ownership/idempotency, safe failure reports, both wire
adapters, first-case payload/usage preservation, and probe exclusion from judging.
Existing real-framework regressions now also perform preflight before their measured
requests and confirm exactly one rejected provider call during a failed probe.

The first regression failed before implementation because load could start without
the check. Focused implementation verification passed 49 tests. The initial full
run caught an invalid union response annotation in the local fixture and a real
worker cleanup defect: Locust's no-response object has no raw stream, so closing it
lost the completed attempt and active counters. Explicit fixture response handling
and guarding raw-stream closure fix these. A subsequent connection test observed a
real ConnectTimeout on this platform's bound/unlistened port rather than refusal;
coverage accepts either real transport outcome and separately verifies exact safe
connection-versus-deadline classification. The final full result is recorded above.

Full offline HTTP smoke:

```bash
MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync python -m examples.framework_e2e \
  --artifact-dir artifacts/preflight-offline-20261005 --agent-port 0 --api-port 0
```

| Framework | Run ID | Preflight | Measured successes / correlated traces | Spans |
| --- | --- | --- | --- | --- |
| LangGraph | `195324fd-0d05-423a-af1a-2ae5b9eb986c` | Passed | 2/2 and 2/2 | 24 |
| OpenAI Agents | `18497bfa-fb64-45d5-ad50-15648ad905dc` | Passed | 2/2 and 2/2 | 16 |

Both report JSON files were fetched over the real local API and rendered through
the shipped JavaScript/DOM harness; the context shows passed preflight and exactly
two measured attempts. The framework/model/tool/memory implementations are real;
provider answers are fixtures and catalog judging is explicitly disabled. Separate
tests exercise native MLflow evaluation. Smoke servers exited normally; existing
saved-evidence previews were not stopped. Browser layout, paid inference, sustainable
capacity, judge calibration, remote CI, and independent maintainer review are not
established by this validation. ADR 0004 remains proposed for review.

## Previous verification — October 4, 2026

| Check | Actual result |
| --- | --- |
| `uv sync --locked --extra agents --group dev` | Locked environment synchronized |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 64 files already formatted |
| `MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync pytest -q --tb=short` | 98 passed, no skips; 38.40 seconds |
| `uv run --no-sync python scripts/export_openapi.py --check` | Snapshot matches |
| `uv run --no-sync openapi-spec-validator docs/openapi.json` | Valid OpenAPI |
| API review tools | 0 errors, 70 warnings, 28 informational findings; 77.28/100 (C), not a B sign-off |
| Breaking-change review | 9 intentional breaks + 1 potential break versus archived 0.1; no explicit breaks versus earlier local 0.2 snapshot |
| Distribution build and `scripts/verify_wheel.py` | sdist/wheel built; API, report, and self-hosted docs assets verified |
| OSV audit of hashed lock export | 181 applicable dependencies; zero known vulnerabilities |
| `git diff --check` | Passed |

The suite has one SQLAlchemy loader-strategy warning and three MLflow/pandas
positional-argument warnings. These are recorded, not suppressed. Native registered
`RetrievalGroundedness` evaluation receives a real correlated Trace; only its model
judge boundary is controlled. No paid calls are required by the suite.

New model regressions check actual SDK-emitted JSON through real LangGraph and
OpenAI Runner streams: exact Databricks-mini presets, portable unknown-model
settings, bounded token parameters, omitted optional reasoning/parallel/store
settings, no retries/model switching after provider 400, and isolated memory/tools.
The hosted payload's usage extension is optional. Tests also validate the README
curl body and preserve legacy default-on idempotency hashes while rejecting an
explicit usage opt-out under the same key. The portable-wire and legacy-replay
regressions were observed failing before their fixes.

### Docs and quality-first report — October 4, 2026

The initial docs regression failed on inline JavaScript under `script-src 'self'`;
report regressions also failed on omitted rationale, indistinct missing/zero
outcomes, absent coverage details, and stale evidence after invalid input. The
first focused post-fix run passed 12 tests; expanded docs/rendering/profiling/wheel
verification passed 27 tests before the final operation-hotspot regression.
The final full suite passes 75 tests with the same four upstream warnings.

Swagger UI v5.33.1 is self-hosted from a verified immutable upstream commit,
with its Apache-2.0 license, SHA-256 hashes, and official Git blob identifiers.
The global CSP is unchanged. Tests check public docs/assets versus authenticated
operations, local asset integrity, external initialization, no remote validator,
no persistent authorization, and prefix-relative URLs. No Python dependency
versions changed for this UI work.

Report tests execute shipped JavaScript using Node.js v26.0.0 and a controlled DOM.
They cover rationale, pre-load readiness, registered judge versions, Boolean zero
rates versus unknown results, numeric/unaggregated scores, partial assessments,
selected/eligible/scored counts, judge errors, missing traces, safe text,
pagination/stale-data handling, operation hotspots, and reversible enclosing-span
filtering. Node is a development prerequisite; CI explicitly configures Node.js 24.
This does not establish browser layout or accessibility conformance.

The owned preview was restarted on loopback port 8000 using
`artifacts/framework-upgraded-live-fixed/`. HTTP checks confirm `/docs` and `/redoc`
redirect to `/docs/`; the docs shell, JS/CSS, Swagger assets, OpenAPI, report shell,
and report assets all return 200 with the same CSP. The served saved live report
`5a8e4b7c-35bc-46ba-a97e-9bad3cd4338b` was also rendered through the shipped script:
two request profiles, two actual judge outcomes, rationale, 1/2 eligible-answer
selection per judge, 100% Boolean rates on the scored answers, and tool
waterfall/hotspots are present. This reuses saved evidence, not new paid calls.

Additional full offline smoke:

```bash
MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync python -m examples.framework_e2e \
  --artifact-dir artifacts/report-ui-offline-20261004 --agent-port 0 --api-port 0
```

| Framework | Run ID | Successful requests / correlated traces | Spans |
| --- | --- | --- | --- |
| LangGraph | `0e9746a7-4068-41f7-84f3-8b5c3b265b0a` | 2/2 and 2/2 | 26 |
| OpenAI Agents | `bc2342d4-83dd-4923-bf9b-b87c42201393` | 2/2 and 2/2 | 32 |

Both new report JSON files render through current JS, including the
performance-only state and focused tool spans. Provider responses are fixtures and
judging is deliberately disabled. Native outer-tool missing-input/output hints
remain; inner custom spans retain tool evidence. These smoke rates do not establish
capacity or model quality. The demo subprocesses exited; only the saved-evidence
preview remains running. Manual browser/desktop/mobile review is still pending.

### Full offline API smoke after compatibility changes

```bash
MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync python -m examples.framework_e2e \
  --artifact-dir artifacts/framework-compatible-offline --agent-port 0 --api-port 0
```

| Framework | Run ID | Successful requests / correlated traces | Spans |
| --- | --- | --- | --- |
| LangGraph | `5cd2c06d-e0c1-44d5-a7c1-16c344651bb3` | 2/2 and 2/2 | 26 |
| OpenAI Agents | `0f8c38b2-b8fb-4ced-a074-dcbe2cd532cd` | 2/2 and 2/2 | 32 |

Real REST, Locust subprocess, streaming, frameworks, memory, MLflow correlation,
profiling, and paginated report retrieval pass. All four inspected native traces
are OK, contain the synthetic policy tool output, and answer “Opened items cannot
be refunded.” Model responses are fixtures; quality scoring is explicitly disabled.
The processes exited normally and no demo servers are left running.

### Bounded live evidence on the selected workspace

Exact user-selected workspace/profile identifiers remain in protected evidence.
This public record omits them; no profile is auto-selected.
SDK/keyring authentication is used; no plaintext auth storage. The verified
`databricks-gpt-5-4-mini` endpoint was READY/NOT_UPDATING. Pricing-catalog fetching
was disabled with `MLFLOW_MODEL_CATALOG_URI=''`; cost was not benchmarked.

October 4 live runs before the final compatibility-boundary refactor:

| Framework | Run ID | Targets / traces | Relevance and correctness |
| --- | --- | --- | --- |
| LangGraph | `cf412d30-01e1-4781-9f69-de3470070ece` | 2/2 and 2/2, 26 spans | One answer per criterion, both true, no judge errors |
| OpenAI Agents, corrected setting | `5a8e4b7c-35bc-46ba-a97e-9bad3cd4338b` | 2/2 and 2/2, 32 spans | One answer per criterion, both true, no judge errors |

Observed LangGraph successful TPS was 1.9311, latency p95 999.57 ms, and answer TTFT
p95 918.06 ms. OpenAI Agents TPS was 1.1832, latency p95 1645.79 ms, and TTFT p95
1501.37 ms. Two requests per framework establish wiring, not capacity, stable
percentiles, or judge calibration.

The preceding Agents attempt `fa0b1f78-2653-4d19-b986-f631250e5233` failed 2/2.
Recorded trace errors identified function tools plus `reasoning_effort="low"` as
unsupported for this model/API combination. The successful bounded retest used
`none`, without repeating the successful paid LangGraph run. Its retained artifacts
are in `artifacts/framework-upgraded-live-fixed/`; the failure remains in
`artifacts/framework-upgraded-live/`.

The final exact-pair preset preserves these known wire settings and is verified
with controlled real-framework HTTP tests plus the full offline smoke. No additional
paid runs were repeated for that refactor. The earlier October 2 framework run in
`artifacts/framework-live/` retained successful target/trace calls but judging
failures/timeouts and a `completed_with_gaps` outcome; later success does not
establish that earlier transport failure's cause.

### Remaining gaps

- Browser/visual interaction was not verified: Computer Use permission is unavailable.
  Static assets, report JSON, and CSP contracts are tested, not visual rendering.
- Duplicate/misparented integration spans can inflate the `parallel` bucket. Occupancy
  is not proof of independent concurrency or a causal critical path. Inner custom
  tool spans contain evidence when outer native tool spans have empty outputs.
- Direct catalog judging is Databricks-specific; hosted-target provider independence
  does not imply universal planner/judge/native-provider transport support.
- Dependencies were upgraded to the newest compatible versions reachable from the
  configured mirror, not all upstream-latest versions. Public PyPI installer access
  failed even outside the sandbox; see `docs/DEPENDENCIES.md` for release gates.
- Audit evidence applies to the local Python 3.12 graph; the supported-interpreter
  audit matrix, remote CI, portable clean installs, and production gates remain open.

## Multi-model smoke — October 4, 2026

The operator authorized the same previously selected workspace/profile. Runtime
discovery found READY / NOT_UPDATING Foundation Model chat endpoints for
`databricks-claude-haiku-4-5` and `databricks-gemini-2-5-flash`.
No endpoint configuration, permission, or hosting resource was changed.
The earlier GPT-5.4 mini paid evidence is retained, not repeated.

Each full case uses two synthetic target requests at concurrency two, a reviewed
planner response, at most one captured answer per selected scorer, and scoped
local MLflow traces. Target calls have a 1,024-token cap, 30-second provider timeout,
zero provider retries, and at most three Agents turns. Planner/judge retry budgets
remain independent and frozen. These tests are wiring checks, not model rankings,
sustainable capacity measurements, stable percentiles, or judge calibration.

Commands below redact only the operator's profile identifier; the exact selected
profile/workspace are retained in ignored frozen plans:

```bash
MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync python -m examples.framework_e2e \
  --live --profile YOUR_CONFIRMED_PROFILE --model databricks-claude-haiku-4-5 \
  --planner-model databricks-gpt-5-4-mini --judge-model databricks-gpt-5-4-mini \
  --artifact-dir artifacts/model-matrix-live-20261004/haiku \
  --agent-port 0 --api-port 0

MLFLOW_MODEL_CATALOG_URI='' EVALSURGE_DEMO_REQUEST_USAGE=false \
  uv run --no-sync python -m examples.framework_e2e \
  --live --profile YOUR_CONFIRMED_PROFILE --model databricks-gemini-2-5-flash \
  --planner-model databricks-gpt-5-4-mini \
  --artifact-dir artifacts/model-matrix-live-20261004/gemini-fixed-gpt-planner \
  --agent-port 0 --api-port 0
```

| Target / framework | Run ID | Successful / correlated requests | Spans | Quality |
| --- | --- | --- | --- | --- |
| Claude / LangGraph | `695a53f7-9b08-4d6c-b826-6ad0e5d43ccb` | 2/2 and 2/2 | 26 | Relevance and correctness: one true assessment each, zero judge errors |
| Claude / OpenAI Agents | `2762605e-f1ed-46df-b96e-97f5f03c1845` | 2/2 and 2/2 | 32 | Same; GPT planner and judges |
| Gemini / LangGraph | `cc2b42dc-b54a-4b4b-8bda-6e014edfdece` | 2/2 and 2/2 | 24 | Same; Gemini judges, GPT planner; groundedness suggestion remains needs_data |
| Gemini / OpenAI Agents | `f16553eb-19e8-4998-a1bf-695fb9a9041d` | 2/2 and 2/2 | 16 | Same; Gemini judges, GPT planner |

All four report JSON files were retrieved by the live helper and rendered through
the shipped JavaScript. The original missing-trace report also renders its gap.
Local native Trace inspection verifies exact run/request correlation, actual
policy tool output, and isolated initial memory reads. This is not browser layout
validation. Cached Claude/Gemini report previews are served on loopback ports
8001/8002; they make no new inference calls when reading reports.

### Retained failures and fixes

- Six bounded canary/diagnostic calls used a 256-token cap, 30-second timeout, and
  zero retries. Claude rejected JSON-object mode with HTTP 400 but accepted tool
  streaming. Gemini accepted JSON-object mode, rejected `stream_options` with
  HTTP 400 twice (the second call captured its exact reason), then accepted the
  explicit no-extension tool stream. Results are in ignored `canaries.json`.
- The first Gemini LangGraph run, `7e621f61-03a2-45de-8163-d37ed783afba`, passed
  2/2 target requests and both Gemini judge assessments, but had zero correlated
  profiles. MLflow OpenAI autologging could not reconstruct a completion with a
  null ID, leaving spans unfinished. Its snapshots/report remain under `gemini/`.
- A controlled null-ID stream reproduced that trace loss in both real frameworks:
  two regressions failed with coverage zero before the fix. The demo now uses
  LangChain autologging and explicit public Agents model-stream spans, with
  duplicate OpenAI autologging and the SDK's external trace exporter disabled.
  It neither fabricates completion IDs nor patches an installed dependency.
- The intermediate same-model Gemini retest in `gemini-fixed/` failed with a
  planner HTTP 502 before any target requests. Its provider-response details
  were not retained, so the cause is unresolved. The final run selected GPT
  planning explicitly before startup; no runtime model fallback was added.
- The first usage/role regressions failed 13 cases before implementation.
  Missing/partial provider usage is now null rather than SDK-normalized zero.
  The final focused framework suite passed 39 tests; the full suite passed 98
  with the same four upstream warnings. Ruff's three formatting changes were
  applied before the final passing release checks.

The Gemini LangGraph evaluation finishes `completed_with_gaps` because the
planner also suggests the unimplemented catalog groundedness wrapper. Available
relevance/correctness assessments complete; the missing criterion is not a pass.
Both new models still reported token usage even without an explicit Gemini usage
request. This observed behavior does not guarantee coverage on other endpoints.
Claude's successful paid work was not repeated after the generic tracing fix;
normal-ID and verified-mini paths were revalidated through controlled real SDK
streams. General planner/judge provider coverage and shared-hosting gates remain
unchanged.

## Automated coverage

The suite covers constrained planning, deterministic evidence readiness, native MLflow scoring with a controlled model response, and actual Locust subprocess traffic over localhost. It covers observed concurrency, answer-text TTFT, UTF-8, timeout, truncation, cancellation/drain, authentication failure, worker SIGKILL, torn journals, frozen plans, idempotency, independent phase outcomes, history, authentication, and restart reads.

The old asyncio-only load tests were removed with the duplicate load implementation.
Counts are not directly comparable to the original 17-test snapshot. Ruff, OpenAPI
snapshot verification, and wheel/source-distribution builds are checked separately.

## Retained real LLM validation — October 2, 2026

`uv run python examples/locust_databricks_e2e.py` exercised REST API → real local Locust → Databricks streamed inference → MLflow post-run judging. Planner, target, and judge used `databricks-gpt-5-4-mini`.

Run at that checkpoint: `7323c770-bd26-4e50-81b3-06e7608521d2` (2026-10-02 UTC).

| Observation | Result |
| --- | --- |
| Configured / observed HTTP concurrency | 2 / 2 |
| Successful target requests | 4 / 4 |
| Incomplete measurements | 0 |
| Answer-text TTFT coverage | 4 / 4 |
| Output-token usage coverage | 100% |
| Planner selections | Relevance and correctness |
| Assessments | 4 per scorer, zero judge errors |
| Relevance / correctness mean | 1.0 / 1.0 on these answers |
| Load / evaluation status | completed / completed |

Observed successful TPS was 1.67, TTFT p50 about 517 ms, p95 about 922 ms. Four requests validate wiring, not capacity or stable latency statistics. The run window includes auth, ramp-up, journaling, and drain. Raw artifacts and the local MLflow database remain ignored.

A prior run (`e4187993-da9c-4a49-b24e-da35f0c822c5`) also passed 4/4. An earlier development run (`75be9a64-e23d-480c-b105-609996172b96`) had 3/4 successes and a connection/read-timeout failure; the three successful responses were judged. That failure remains recorded. Subsequent success does not establish its root cause.

A separate direct judge check used one correct and one deliberately incorrect response; correctness mean was 0.5. That confirms discrimination for the simple fixture, not general calibration.

The local mock example generates 20 requests at concurrency 3 without paid calls. Missing references or judge configuration are explicit evaluation gaps.
