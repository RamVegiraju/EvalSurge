# Validation — 0.2.1.dev2026101203 checkpoint

## Private-repository and CI follow-up — October 13, 2026

The repository was changed from public to private before adding the pending product
briefs and report preview. Authenticated GitHub metadata reports `private=true`;
an unauthenticated repository API request returns HTTP 404. Earlier public commits
contained operational identifiers and local evidence paths. Private visibility
prevents current anonymous repository access, but cannot revoke prior clones or
caches; do not make the existing history public again without a separate review.
The pending brief and preview were checked for exact workspace/App identifiers,
credential patterns, and local evidence paths. The HTML preview's historical run
ID was removed. No real model, deployment, or Databricks workspace call occurred.

The October 12 push at `10c34f9` triggered the previously approved controlled
provider-fixture CI. Security jobs and Python 3.11–3.13 test jobs passed. Python
3.14 had 1 failure and 1,876 passes: a localhost timeout regression applied a
50 ms read deadline to submission as well as polling, so a delayed creation
response could precede the expected report URL. The test now gives submission a
2-second read budget and delays the poll for 3 seconds; its 10-second overall
deadline remains bounded. This tests the intended post-admission network timeout
without changing production transport or server behavior.

Focused localhost regression: `uv run --frozen --no-sync pytest -q
'tests/test_requests_example.py::test_requests_cli_wait_and_network_timeouts_do_not_retry_or_cancel'`
passed **2 tests in 4.29 seconds**. This uses a deterministic local HTTP target,
not model inference. The first sandboxed attempt could not bind loopback; the
approved outside-sandbox rerun passed. A subsequent full controlled suite reported
**1,875 passed, 2 failed, 42 warnings in 282.69 seconds**. Both failures were
isolated `[local]`/`[server]` installation checks lacking artifacts in the local
offline uv cache. The same source's CI install checks had passed on Python
3.11–3.13; this local environment failure is retained rather than relabeled.
No new full-suite pass is claimed.

Locked sync passed offline with the lock's public index identity (190 resolved,
182 installed packages checked). Ruff lint, Ruff format, OpenAPI snapshot and
schema checks, JavaScript syntax, and `git diff --check` passed. An offline
wheel/source build and archive verification passed; post-push CI remains a separate
check. Controlled provider responses in the suite are regression fixtures,
not actual model inference.

## Pre-demo technical publication verification — October 12, 2026

The user approved parallel code/asset review, ten separately bounded real-model
calls, the disclosed controlled-regression/CI exception, and a technical-only
push. The ten calls below are exhausted. No further inference, deployment,
resource deletion or package publication was performed during final verification.

The first full controlled suite is preserved: **18 failed, 1,855 passed, 42
warnings in 293.15 seconds**. It exposed stale test/document expectations and
installation prerequisites, not a newly fixed inference failure:

- Ten probe-privacy checks matched the generic word `private`, including legitimate
  macOS tracking paths. Checks now reject exact provider/answer sentinels and
  include four assertion regressions; safe metadata does not waive payload privacy.
- One unsafe-file fixture depended on the shell umask. Explicit `chmod(0o644)`
  now establishes and checks its intentionally unsafe permissions before dispatch.
- Four framework phase assertions omitted additive `profiling_readiness=skipped`.
- One quickstart expectation still named the historical `.1202` wheel.
- Two isolated installation checks lacked a cached public-index cryptography
  artifact. They use the existing task-local supported-source override, without
  changing dependency versions, lock hashes or public index provenance.

The corrected framework/example subset passed **5 tests**; precise privacy and
permission regressions passed **15 tests, 38 deselected, in 9.82 seconds**. The
earlier focused native non-inference/schema/presentation set passed **389 tests**;
the final documentation/native trace subset passed **20 tests**. Those subsets
overlap and are not additive coverage counts.

Full verification then passed on Python **3.12.13/macOS**:

```bash
uv sync --locked --offline --extra agents --group dev \
  --python /Users/ram.vegiraju/Desktop/TestFolder/EvalSurge/.venv/bin/python \
  --default-index https://pypi.org/simple
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync pytest -q
uv run --frozen --no-sync python scripts/export_openapi.py --check
uv run --frozen --no-sync openapi-spec-validator docs/openapi.json
node --check benchmark_agents/static/report.js
git diff --check
git diff --cached --check
```

Locked sync resolved **190** records and checked **182** installed packages,
without downloading or rewriting the lock. Explicit public lock identity was
selected **offline**; it is not direct registry access or a proxy bypass. The
full test command used normal `umask 022` and the existing approved task-local
installation source setting for isolated package checks. Its private logs/source
URL are not published. Result: **1,877 passed, 42 warnings in 361.68 seconds**;
the warnings are one upstream MLflow/SQLAlchemy `noload` deprecation and 41
upstream MLflow/Pandas positional `.all(0)` notices. Ruff lint and format passed
for **260 files**; OpenAPI equality and schema validation, JS syntax and both
whitespace checks passed. Provider-fixture tests remain controlled inference,
not the real-model evidence in the next section.

The three exact previously failing Python 3.11 CI cases also passed locally in
a fresh CPython **3.11.14/macOS arm64** environment, with 181 existing locked,
hash-pinned dependencies and a successful native gevent build:

```bash
uv run --no-project --no-sync \
  /private/tmp/evalsurge-py311-ci-review.w2cgEg/venv/bin/python \
  -m pytest -q --tb=short \
  'tests/test_measurement_dispatch.py::test_authentication_initialization_single_flight_preserves_refresh[False]' \
  'tests/test_python_example.py::test_python_benchmark_cli_saves_success_or_preflight_failure[normal-0]' \
  'tests/test_requests_example.py::test_requests_cli_wait_and_network_timeouts_do_not_retry_or_cancel[True]' \
  --junitxml=/private/tmp/evalsurge-py311-ci-review.w2cgEg/prior-ci.xml
```

Result: **3 passed in 8.70 seconds**. These use localhost HTTP/Locust with
controlled responses; the authentication ownership check is non-agent/non-model.
No failures reproduced, so no speculative runtime/test changes were made.
This is not Linux verification or a claim that earlier CI failures were flakes.
Remote CI must be inspected after the actual push; configured jobs are not passes.

Independent code review found no actionable P1/P2 blocker in the changed collector,
readiness, CLI observer, safe trace headers or sample. It is not designated
maintainer approval: ADRs 0020/0021 remain proposed. The caller/asset audit found
no unused tracked assets safe to remove; report/docs assets and compatibility
snapshots retain callers. Private caches, failures and paid-run evidence remain
preserved. Product briefs, `docs/assets/` and their unrelated root README link
remain local and excluded from the staged technical source.

An offline build from that selectively staged source produced a wheel identical
to the real-model-tested artifact below. Required package/report/docs assets,
static internal imports, source-distribution exclusions and absence of the
unrelated README brief link were checked. No earlier artifact was overwritten.
The final build command uses a fresh technical-only index export, not the dirty
working tree:

```bash
git checkout-index --all \
  --prefix=/private/tmp/evalsurge-final-release-20261012.g90MFU/final-source/
uv build --offline --no-build-isolation --no-cache \
  --python /Users/ram.vegiraju/Desktop/TestFolder/EvalSurge/.venv/bin/python \
  /private/tmp/evalsurge-final-release-20261012.g90MFU/final-source \
  --out-dir /private/tmp/evalsurge-final-release-20261012.g90MFU/final-dist
```

The unchanged lock SHA256 is
`fc0080a3964731580738e5e528e45adc25419ffef318b1f023bc4e8c09c377ef`.
Report HTTP/JSON retrieval was rechecked: four actual profiles, full coverage,
no gaps, completed lifecycle and passed trace readiness. Browser control was
unavailable/not approved, so no actual visual inspection is claimed. Remaining
App/UC, CrewAI, judge-quality, capacity and overhead boundaries stay explicit.

## Installed-wheel multi-tool live validation — October 12, 2026

The user explicitly approved ten actual model calls and the separately disclosed
controlled regression/CI exception. This checkpoint uses a new version, never an
overwrite of the earlier `.dev2026101202` artifact:

```text
evalsurge-0.2.1.dev2026101203-py3-none-any.whl
SHA256 1b46d96185afc7225faf6254db1181b9e023525bb67c0cb714ce948ea5b1d20f
```

Source/project/runtime/OpenAPI and the root lock entry identify `.dev2026101203`;
all non-project dependency versions, hashes and index provenance remain unchanged.
The technical-only Git index supplied the build source, excluding the dirty root
README brief link and untracked product documents/assets. The wheel was installed
with required locked dependency hashes in a fresh Python 3.12.13 environment
outside the checkout. Runtime checks proved `evalsurge` and the Locust launcher
were ordinary wheel imports beneath that environment's `site-packages`.
Dependency validation passed for 150 packages including agent-framework dependencies.
The initial offline requirements export stopped on implicit interpreter/index
selection; explicitly selecting Python 3.12/public lock identity passed. An
offline cache miss then required the supported approved package source. No public
registry bypass, dependency upgrade or lock provenance rewrite occurred.

The real tests executed the public `examples.journeys.multitool_heatmap.agent`
and `.runner` entrypoints copied outside the checkout. Agent and runner used this
installed wheel; actual LangGraph called real `system.ai.gpt-oss-120b` through
`/ai-gateway/mlflow/v1/responses`, with exact selected `e2-demo-field-eng` profile
and workspace. Bounds were five physical calls per agent lifetime, 512 output
tokens and 30-second model timeout, zero retries/fallback; one excluded probe and
four measured attempts per run. Trace destinations were separate local SQLite
experiments. The disclosed synthetic tools/decision were actually executed; only
shipping's delayed scenario waited two seconds inside its span. No provider
completion, framework or agent was substituted, and no App was deployed.

| Observation | Synchronous export | Asynchronous export |
| --- | --- | --- |
| Run ID | `fefaebd2-792f-4a36-9c42-5cd320e81edb` | `e36199e5-b5c6-4717-a294-c33816012ce9` |
| Excluded probes / measured attempts | 1 / 4 | 1 / 4 |
| Inference / trace readiness | passed / passed | passed / passed |
| Successful measured answers / errors | 4 / 0 | 4 / 0 |
| Correlated measured profiles / gaps | 4/4 / none | 4/4 / none |
| Actual spans per measured trace | 6 | 6 |
| Configured / peak observed HTTP concurrency | 5 / 4 | 5 / 4 |
| Successful latency p50 / p95 (ms) | 1982.77 / 4128.81 | 2359.61 / 4254.58 |
| Successful throughput including drain (req/s) | 0.96 | 0.93 |
| Output-token usage coverage | 100% | 100% |
| Delayed shipping spans (ms) | 2001.253 / 2003.961 | 2001.353 / 2001.354 |
| Normal shipping spans (ms) | 0.078 / 0.128 | 0.080 / 0.106 |
| Delayed Tools occupancy (ms) | 2006.830 / 2019.989 | 2004.143 / 2004.821 |
| Normal Tools occupancy (ms) | 7.201 / 19.669 | 2.045 / 2.134 |
| Measurements / journal drain / worker exit | complete / yes / 0 | complete / yes / 0 |

The model, three named tools, eligibility decision and correlated boundary are
present. The heatmap's category-level Tools occupancy distinguishes delayed from
normal requests; waterfalls retain the individual spans. Both agent processes
exited cleanly after their owned shutdown (including async exporter exit flush).
Raw captures, traces and failure evidence remain private and uncommitted. Ten
approved model calls were consumed; no judging or additional canary was run.

These are local HTTP/local SQLite functional smokes, not App/UC tracing support,
quality calibration, sustainable capacity, zero instrumentation overhead or
browser visual verification. Nonstreaming HTTP reports TTFT as unavailable, not
zero. The first earlier asynchronous probe remains failed and its exact initially
mismatching field remains unknown. Native regression evidence establishes the
metadata-visibility failure mode; these fresh smokes establish the new public
entrypoints' success against this exact installed artifact.

Separate fresh `scripts/verify_install.py --surface all --offline` checks passed
for isolated **base/local/server** installations through the approved cached
source, using required hashes and unchanged lock metadata. These checks exercised
installed imports, public models, empty SDK ownership, CLI/sample help and native
Locust class listing, with zero inference, auth or target dispatch. They do not
establish public-index publication or a new dependency resolution. Private
installer diagnostics and source URLs were not copied into repository documents.

## Earlier preparation: reusable multi-tool sample and metadata visibility — October 12, 2026

Added `examples/journeys/multitool_heatmap/` with separate agent/runner entrypoints,
synthetic order/policy documents, three actually executed tool functions, a
business-rule decision and real Responses inference. It is a fixed serial
LangGraph workflow, not model-selected tool use. The sample owns the disclosed
two-second nonblocking shipping delay and explicit sync/async **local SQLite**
export selection (sync remains this sample's default); neither is injected by
the load generator. Evaluation stays off. Explicit
profile/host/model selection and consent are required; the agent lifetime caps
physical model attempts at five, matching one excluded probe plus four measured
attempts. The original private source workflow's live evidence below is distinct
from validation of these new public entrypoints. No fresh inference was run.

A native MLflow 3.16.1 reproduction persisted actual spans with the exporter’s
`TracingClient.log_spans()` before its `start_trace()` metadata write. A real
`MlflowClient.get_trace()` returned a non-null trace in the authorized experiment
with absent benchmark run/request keys. Before the fix, the regression failed
with `scope_mismatch`. The collector now rereads that same ID, within the existing
four-read and shared 60-second admission budgets, only for absent correlation
keys after matching the trace ID/experiment. Conflicting present keys still fail
immediately; exhausted absence remains `missing`, and no normalization/judging
or measured load is authorized. Tests cover either/both absent keys, permanent
absence, four conflicting scope components and deadline/backoff boundaries.
Production load-only planning also rejects incomplete enabled tracing; this
existing guard was regression-tested, not changed.

This reproduces and fixes a native storage-visibility failure mode. The first
paid asynchronous probe remains failed, and its originally mismatching field
was not captured. No claim of fresh live asynchronous/App/UC success or browser
visual verification follows. No target reinvocation, default export change,
per-request flush, timing subtraction or additional load engine was added.

Focused command:

```bash
uv run --frozen --no-sync pytest -q \
  tests/test_trace_visibility.py tests/test_load_only_tracing.py \
  tests/test_cli_progress.py tests/test_cli.py tests/test_remote_sdk.py \
  tests/test_unified_sdk_contract.py tests/test_unified_usability_contract.py \
  tests/test_summary.py tests/test_report_ui.py tests/test_wheel.py \
  tests/test_docs_ui.py tests/test_serving.py tests/test_streaming.py \
  tests/test_simple_examples.py::test_multitool_heatmap_request_bounds_and_non_inference_inputs \
  tests/test_simple_examples.py::test_multitool_heatmap_rejects_inputs_before_inference \
  tests/test_simple_examples.py::test_multitool_heatmap_declared_data_and_serial_source_contract \
  tests/test_simple_examples.py::test_journey_sources_have_named_non_inference_contract_coverage \
  tests/test_simple_examples.py::test_multitool_heatmap_documented_viewer_contract_and_links \
  tests/test_simple_examples.py::test_multitool_heatmap_export_configuration_without_lifespan \
  tests/test_simple_examples.py::test_multitool_heatmap_invalid_export_rejected_before_lifespan
```

Final sample follow-up: **389 passed in 17.21 seconds**, one upstream SQLAlchemy `noload` deprecation
warning. These are schema/lifecycle/rendering, native **non-LLM telemetry**,
input/data and source checks. No provider completion or agent was substituted;
they do not establish successful real inference. Separate read-only review found
no high-severity scope weakening in the collector fix. That agent review is not
designated maintainer approval for proposed ADRs 0020/0021.

The sample now prints retained report/run information after both success and
failed readiness, releases direct-run storage ownership before presenting the
optional existing viewer URL, and exits nonzero on `RunFailed` without a
traceback or another model call. Viewer documentation/source checks do not
establish actual browser visual verification. Sync/async factory tests do not
start the agent lifespan, authenticate, export or invoke a provider.

Final non-inference checks also passed: Ruff lint; Ruff format (260 files);
OpenAPI snapshot equality and schema validation; Node report JavaScript syntax;
working and staged diff whitespace checks. Dependencies/lockfile were unchanged;
no registry install, deployment or fresh model call was performed.

An offline diagnostic build from the reviewed Git index (not the dirty working
tree) passed wheel and source-distribution verification at
`0.2.1.dev2026101202`. Archive member checks excluded the product briefs,
`docs/assets/` and local assistant metadata; the archived root README was also
checked for absence of the unrelated product-brief link. The source copy and
build outputs stayed in a fresh private temporary directory. No existing
artifact was overwritten or new release published. The first build attempt
was denied access to the existing uv cache by the filesystem sandbox; its
explicitly approved offline rerun succeeded without downloading dependencies.

The full suite and push-triggered CI contain controlled provider responses and
were not run under this request; their explicit disclosure/approval gate remains.
The previous Python 3.11 CI failures below remain unresolved. Product briefs,
their assets and the unrelated README brief link remain preserved locally and
excluded from the proposed technical publication.

## Real multi-tool heatmap smoke — October 12, 2026

A private validation harness exercised the current working tree with an actual
serial LangGraph workflow and real `system.ai.gpt-oss-120b` Responses inference
under the previously selected profile. Three actual tool functions read synthetic
order/policy data and compute a shipping quote; a separate decision applies return
eligibility rules before model synthesis. This is a deterministic workflow, not
evidence of model-selected tool calls. Only the delayed case injects a disclosed
two-second nonblocking wait inside `quote_return_shipping`. No agent/framework or
provider completion was stubbed; evaluation was off.

The first run, `7d16f885-a05b-47d2-ba2d-73963945165e`, completed one real probe but
failed trace readiness with `scope_mismatch`; measured load was skipped. A later
read-only recheck of its retained trace passes all four exact scope checks and
normalization. This is consistent with asynchronous export/metadata visibility;
the mismatching field at the original read was not captured, so the precise race
is not proven. The original failure and artifacts remain unchanged. At the time
of that run, no collector retry behavior, trust boundary, default exporter or
load engine had changed; the subsequent native regression fix is recorded above.

With explicitly synchronous **local SQLite** trace export, run
`92f6c1b1-3be8-468b-97b9-1dd4e14cdb8e` passed inference and trace readiness,
then completed **4/4 measured requests**, **0 errors**, and **100% trace coverage**.
It used one excluded probe, a ten-second dispatch ceiling, five configured users
and four observed in-flight attempts. The request cap ends dispatch early; this
is a smoke, not a ten-second sustained window or capacity result. Actual model
attempts/completions total **6/6 across both runs**, with no retries, fallbacks or
judges and at most 512 output tokens/call. Target lifespans, provider clients and
CLI/load workers closed; only the read-only loopback report viewer remains.

Measured delayed shipping spans were **2001.264 / 2000.719 ms**, compared with
**0.088 / 0.109 ms** for normal quotes. The heatmap's aggregate Tools column
records **2007.875 / 2010.865 ms** versus **12.904 / 3.641 ms**. All four profiles
retain separate order, policy, shipping, eligibility and native `CHAT_MODEL`
spans with exact run/request correlation. Serial tool durations match exclusive
Tools occupancy. Synchronous export overhead is included in client latency;
these results do not certify zero overhead or server-only metric accuracy.

Commands used `uv run --frozen --no-sync python <private-harness>/live_check.py`
and a subsequent `verify_heatmap.py` over retained evidence only. The latter made
zero further model calls, checked native spans/profile arithmetic, and executed
the shipped report JavaScript against the actual generated report with the
bounded DOM harness. Light/dark Tools values and shading, per-tool waterfalls,
hotspots and theme roundtrips passed. This is **not browser visual verification**.
Protected records are retained under the private multi-tool heatmap validation
directories; no live artifacts or private tool data were added to Git. No App,
UC-tracing, release-wheel or remote-CI success is established by this check.

## Trace readiness and live CLI progress — October 12, 2026

Working-tree checks are based on `b5c915eff1b346188f8163e844a70ab647e2ca5f`.
This patch is uncommitted and unpushed, not a newly frozen release artifact.

Configured tracing now verifies the same excluded inference probe before load,
including when evaluation is off. Failed trace readiness retains successful
inference and has independent typed outcomes and safe report/summary guidance.
The optional local experiment helper creates real correlated boundary spans,
not model/tool spans. Databricks tracking URIs are rejected by that helper;
governed UC IDs survive transport but collection fails closed with
`unsupported_scope` before content fetch. No App/UC tracing success is claimed.

CLI `--progress` emits allowlisted phases and bounded heartbeats on stderr;
JSON stays on stdout. SDK observers reuse remote polls or lightweight direct
status projections, without changing the Locust hot path. Independent review
found a direct waiter deadline overrun; the fix checks before each callback and
clamps waits to remaining time. A controlled-clock regression verifies that
timeout does not cancel underlying work. Blocking callbacks remain nonpreemptible.

Final integrated command:

```bash
uv run --frozen --no-sync pytest -q \
  tests/test_cli_progress.py tests/test_cli.py tests/test_remote_sdk.py \
  tests/test_unified_sdk_contract.py tests/test_unified_usability_contract.py \
  tests/test_summary.py tests/test_report_ui.py tests/test_wheel.py \
  tests/test_docs_ui.py tests/test_load_only_tracing.py tests/test_serving.py \
  tests/test_streaming.py \
  tests/test_simple_examples.py::test_journey_sources_have_named_non_inference_contract_coverage
```

**363 passed in 10.05 seconds**, with one upstream SQLAlchemy `noload`
deprecation warning. These checks use lifecycle/report metadata, decoder wire
samples and real native local MLflow telemetry over non-LLM arithmetic handlers.
They make no agent/model calls and are not real-inference validation. Native
telemetry checks verify actual spans and correlation; no framework/model
completions are substituted as evidence of live success.

Additional checks passed:

- `uv run --frozen --no-sync ruff check .` and `ruff format --check .`
  (255 files formatted).
- `uv run --frozen --no-sync python scripts/export_openapi.py --check` and
  `uv run --frozen --no-sync openapi-spec-validator docs/openapi.json`.
  The initially stale additive snapshot was regenerated before these final checks.
- `node --check benchmark_agents/static/report.js` and `git diff --check`.
- `uv build --no-build-isolation --offline --out-dir <private-diagnostic-dir>`;
  direct `verify()` / `verify_sdist()` archive checks passed. This diagnostic
  build retains the existing development version and must not replace the
  previously frozen artifact or be published as a new release.

Archive member inspection found that untracked publication-excluded brief/report
files entered the initial source build. Exact sdist exclusions and regression
gates now reject them without reading their contents; the rebuilt archive passes.
Those user-owned files and the unrelated README link edit remain untouched and
outside any proposed publication. Dependencies and `uv.lock` are unchanged.

The previous pushed checkpoint's CI run `38303883690` still has an unresolved
Python 3.11 gate: **3 failed, 1797 passed**. Failures are
`test_authentication_initialization_single_flight_preserves_refresh[False]`,
`test_python_benchmark_cli_saves_success_or_preflight_failure[normal-0]`, and
`test_requests_cli_wait_and_network_timeouts_do_not_retry_or_cancel[True]`.
Python 3.12–3.14 tests and security jobs passed for that checkpoint, not this
uncommitted patch. Do not call the three failures confirmed flakes or infer
current remote CI success. Full inference/controlled-provider suites were not
rerun; their disclosure/consent gate still applies.

ADRs 0020/0021 require designated maintainer review. Governed UC scope support,
fresh bounded real-agent/App trace validation, full collection coverage and
instrumentation/generator overhead validation remain separate release gates.
No deployment, paid traffic, resource provisioning or cleanup was performed
for these changes.

## Report light/dark theme — October 12, 2026

### Presentation-only verification

The browser report now has a keyboard-accessible **Dark mode: on/off** header
button with an explicit pressed state. Initial selection follows the system
preference unless a valid `light`/`dark` choice was saved. Theme-aware panels,
badges, inputs, tables, heatmaps, anatomy bars and span waterfalls preserve all
underlying evidence. Stronger heatmap shading means greater occupancy in both
palettes. The preference uses only `evalsurge.report.theme`; blocked/missing
storage still allows in-page switching. No API key, run ID or report data is saved.

Checks against the working tree based on `dfd420416ec3d984fc0ba44b3bf6a6ff8be87d6a`:

- `uv run --frozen --no-sync pytest -q tests/test_report_ui.py tests/test_wheel.py tests/test_docs_ui.py`:
  **105 passed**. These are synthetic report-rendering, archive and static-docs
  checks, not stubbed inference or live agent validation. The theme regressions
  cover both directions, saved/invalid preferences, blocked storage, absent media
  API, failed report retrieval, stable request selection and no extra report fetch.
- `uv run --frozen --no-sync ruff check .`, `ruff format --check .`, and
  `git diff --check`: passed.
- `node --check benchmark_agents/static/report.js` and
  `node --check tests/report_harness.cjs`: passed.
- Frozen OpenAPI snapshot export check and schema validator: passed, unchanged.
- Offline wheel build and archive validation: passed; packaged HTML/CSS/JS bytes
  match the working tree. This diagnostic build is **not a new frozen release**;
  a distributable changed build needs a new version.

These presentation checks made no agent/model calls. Dependencies and `uv.lock`
remain unchanged. Full inference suites were not rerun locally for this
presentation-only patch. These DOM contracts do **not** establish browser layout
or visual contrast verification; a desktop/mobile browser check remains before
release. Private live-validation records and product-design material are excluded
from this change.

## Local installed-package milestone — October 12, 2026

The current milestone uses **local Python as the load generator**, with a hosted
HTTP agent or a separate Databricks agent App as the target. Notebook and
App-based load generators are deferred. Their source, failed installation
evidence, stopped resources and proposed contracts are retained; earlier sections
below describe historical checkpoints, not additional current successes.

Direct installation now has a `[local]` alias for the unchanged `[server]`
dependency surface. The customer quickstart uses ordinary `venv`, `pip` and
Python, two target bindings, the shared `RunCreate`, and `format_summary(report)`.
Agent-framework dependencies stay in a separate agent environment. The six
local-runner/framework/hosting combinations are an example inventory, not six
passed live tests. CrewAI remains blocked by its independent security/deployment
gates.

### Frozen artifact and installation evidence

The reviewed candidate is uniquely versioned **0.2.1.dev2026101202**. It was
frozen before the final documentation edits and was not overwritten afterward:

```text
/private/tmp/evalsurge-local-only-20261012.D2MG3y/reviewed-build/
  evalsurge-0.2.1.dev2026101202-py3-none-any.whl
  SHA256 a1a58a4513c4659aee41f9c5570bbcca6da371b4b185b629e7842be4eac23285
  evalsurge-0.2.1.dev2026101202.tar.gz
  SHA256 dcd50eca53f0fde1755643f5adbcd0795b5abe2eee744d0c46b3041a9bf04f3f
uv.lock SHA256 d550a74cb1a010c70a3480f10a88bdb98bc9935bbdd1e58baf104910f299d7ff
```

Both archive gates passed. The version/extra metadata changed, but all **189
non-editable lock records** retained their versions, hashes and recorded origins.
No fresh latest-compatible resolution or public package publication is claimed.
Earlier draft artifacts remain preserved and must not be substituted for this
reviewed wheel.

Fresh **pip** base, `[local]` and `[server]` installations of that exact wheel
passed outside the checkout. Installed-package imports, request construction,
sample `--help`, CLI checks and `pip check` made **zero agent/model dispatches**.
They used the explicitly approved package source with required artifact hashes;
`public_index_install_established=false`. Private provenance is retained under
`/private/tmp/evalsurge-local-only-20261012.D2MG3y/pip-reviewed-install/` in the
`base`, `local` and `server` subdirectories. The separately retained pip runner
is `.../runner`; its safe provenance is
`.../pip-runner-evidence/provenance.safe.json`, with environment manifest SHA256
`78fddb42a68c09a748deb3fa657a53680b63f8afe373f49143aef1106da40db4`.
This is macOS installation evidence, not public-index or Linux/App installation.

### Fresh real-model execution from the installed wheel

All four positive cells used the explicitly selected **`e2-demo-field-eng`**
profile/workspace and actual **`system.ai.gpt-oss-120b`** inference. The local
HTTP agents executed an actual LangGraph graph or OpenAI Agents Runner, using
MLflow Responses through `/ai-gateway/mlflow/v1/responses`. There was no fixture
completion, fake agent, mocked inference transport or retry fallback. The App
cells used the existing deployed managed agents, not local App stand-ins.

Each cell was bounded to one excluded readiness probe plus **one measured
request**, concurrency **1**, a **10 s** dispatch ceiling and **40 s** request
timeout. Agent/model bounds were **35 s / 30 s**, with at most **512** output
tokens per provider call and zero provider retries. Evaluation was **off**: zero
planner/judge calls, tools or memory. These smokes did not run the longer
five-request customer quickstart or establish sustainable capacity.

| Target hosting | Actual framework / target | Run ID | Measured latency |
| --- | --- | --- | ---: |
| Local HTTP | LangGraph | `8177940b-259d-4516-aac3-22eaed70af92` | 666.392 ms |
| Local HTTP | OpenAI Agents | `9c58618b-4382-46e0-9fc9-23e26b431676` | 435.451 ms |
| Existing agent App | `agent-bricks-es-lg-1008` | `f4ea3175-34f0-404d-94af-96556a3363ac` | 1371.096 ms |
| Existing agent App | `agent-bricks-es-oai-1008` | `e0c5e19f-e081-44af-9a1a-361a49b70987` | 1441.589 ms |

Each positive measured request succeeded, with error rate **0**, typed
status/result/report agreement and content-free public summary retrieval. The
SDK closed and runner was reaped; HTTP agent lifespans/listeners closed. Every
journal drained without writer failures or backpressure, and each report recorded
`measurement_complete=true`. Each HTTP cell recorded **2 outbound provider
attempts / 2 completed responses**, two target receipts and zero final in-flight
requests. Exact post-run App counters confirmed **2 handler/model attempts / 2
completed responses per App**, zero errors and unchanged deployed source. The
separate cleanup receipt confirmed both Apps **STOPPED / UNAVAILABLE** at
**October 12, 2026, 17:23:32 UTC**, with deployment IDs and resources unchanged.
It is retained at
`/private/tmp/evalsurge-target-readiness-20261012.RxUvhu/cleanup_complete.json`.
No App, source, grant, profile or historical evidence was deleted.

The four cells' safe consolidated receipt is
`/private/tmp/evalsurge-local-only-20261012.D2MG3y/milestone.safe.json`. Protected
reports and per-cell receipts are retained under that directory's `langgraph`,
`openai-agents`, `app-langgraph` and `app-openai` subdirectories. The App cells
establish latest installed-SDK interoperability with the **older existing
deployments**; they do not establish deployment or live validation of the current
public `examples/journeys/agent_apps/` templates.

### Intentional pre-provider fail-fast checks

Both real HTTP framework handlers rejected one unsupported-input readiness
probe each before calling the provider. Both runs recorded failed inference
preflight **`target_http_error`**, skipped measured load, absent metrics, empty
report rows, **0 provider attempts / 0 completions**, retrieval agreement and
closed SDK/agent lifecycle/listener with the runner reaped. This is successful
fail-fast behavior, **not successful model inference**, and involved no stubbed
completion. The safe incremental evidence is
`.../fail-fast.ledger.0002.safe.json`, with per-framework receipts under
`fail-fast-langgraph` and `fail-fast-openai-agents`. Earlier failed attempts and
the previous checkpoint's evidence were retained, not relabeled as passes.

The unchanged aggregate approval was **36 target attempts / 48 model calls**.
Including the conservatively retained October 11 attempts, accounted consumption
is **16 target attempts / 12 model calls**; the remainder is **20 / 36**. This is
one aggregate lease, not renewed consent or authorization to dispatch its remainder.
There were no judge or active-cancellation workloads in this checkpoint.

### Measurement limitations and remaining live gaps

One measured observation per cell is not a meaningful tail distribution or
capacity result. These nonstreaming contracts report no answer TTFT or
first-event timing. HTTP reported token coverage **100%**; native App token
coverage was **0%**, so App token throughput is unavailable. The public generator
health status remains **`unknown`**, not certified healthy. Maximum observed
hub lag was **19.479 ms / 27.667 ms** for HTTP LangGraph/OpenAI Agents and
**355.680 ms / 381.544 ms** for the corresponding App cells. The substantial App
scheduling observations preclude a zero-observer-effect or measurement-accuracy
certification. Client timing includes SDK/transport/authentication/scheduling;
no simultaneous server-only timing or target trace establishes their contribution.

Pending coverage: CrewAI HTTP/App real inference and its security/deployment
gates; current public native App-template deployments; current-artifact captured
answer judging and trace correlation; App fail-fast; active cancellation/drain;
the full advertised tutorial traffic; broader load/generator-overhead validation.
Notebook/App-based load generation, remote CI, public publication and other
platforms remain unverified/deferred. ChromaDB advisory `PYSEC-2026-311` was
confirmed in official OSV metadata through last-affected **1.5.9**; CrewAI's
`~=1.1.0` constraint cannot clear that advisory. No security/index bypass,
dependency downgrade or inference fixture was used to claim CrewAI success.

### Verification and preserved failures

Controlled inference regressions were explicitly disclosed/approved separately
from the live cells above. Their provider responses/native SDK replies were
controlled and their passes are not real-model evidence. The first full run
retained **1 failed / 1,777 passed / 42 warnings in 327.76 s**; a stale base-CLI
extra-guidance assertion failed and was corrected. The final full run passed
**1,782 tests / 42 warnings in 332.74 s**. Pure schema/docs/source checks passed
**100 tests in 0.14 s**; final scoped README checks passed **5 tests / 1 controlled
SSE test deselected in 0.05 s**. Ruff lint/format, diff checks, OpenAPI snapshot
equality/schema validation and archive checks passed. Fresh pip installation
verification and persistent installed-runner verification both exited **0**.

Relevant no-inference command for the 100-test documentation/schema/source slice:

```bash
uv run --frozen --no-sync pytest -q tests/test_runner_target_examples.py tests/test_unified_journey_examples.py tests/test_framework_runner_matrix.py
```

After the final documentation integration, the combined pure slice plus README
contracts initially returned **1 failed / 104 passed / 1 deselected in 0.31 s**:
the matrix guard still expected the older unverified/older-wheel wording. It now
checks four evidenced rows, two blocked CrewAI rows and explicit reduced-coverage
limits. The same command then passed **105 tests / 1 deselected in 0.77 s**:

```bash
uv run --frozen --no-sync pytest -q tests/test_runner_target_examples.py tests/test_unified_journey_examples.py tests/test_framework_runner_matrix.py tests/test_readme.py -k 'not test_readme_python_request_runs_without_judging'
```

The deselected README test uses controlled inference. This final slice made no
agent/model calls and does not replace the earlier full-suite or live receipts.
Final Ruff checks, OpenAPI equality/schema validation, diff checks and unchanged
reviewed wheel/sdist/lock hashes were also verified. The archived artifacts were
not rebuilt to incorporate documentation-only updates.

The full repository verification uses the commands in `AGENTS.md`, with frozen
no-sync invocations after the selected-source locked environment was prepared.
No remote CI result is inferred from local verification. The repository remains
dirty with preserved team/user work; no commit or push is claimed here.

## Historical App registry diagnosis and workspace-ID repair — October 12, 2026

The original ADR 0017/0019 private contract received designated maintainer
acceptance. The approved disabled deployment
`01f1c652cda714069d6c96824b266369` used the unchanged reviewed
`0.2.1.dev2026101101` wheel and failed at package installation:
`aiohappyeyeballs==2.7.1` had no available candidate. Startup, authentication,
claims, preflight and inference were not reached. Retained logs are
`/private/tmp/evalsurge-disabled-app-20261012.9raKwr/install-failure.log`.

The runner's exact `CAN_USE` target binding, `READ_VOLUME` / `WRITE_VOLUME`,
`USE_SCHEMA` and `USE_CATALOG` were verified. Existing inherited administration
was preserved; storage is not owner-only. After retaining logs the failed compute
was stopped. A temporary stdlib-only App-side registry diagnostic then ran in the
same selected `load-test` resource/profile, with no dependency installation,
EvalSurge execution, native credential forwarding or agent/model call. Starting
compute first automatically retried the same disabled install
(`01f1c6574977153cac57393c71c05ad9`), which failed identically. Diagnostic
deployment `01f1c65755671dada48e5ed6f32e9555` succeeded and observed:

- Python **3.11.17**, Linux.
- Approved package index **HTTP 403**, with redirects not followed by the stdlib probe.
- Pip candidate query exit **1**, no exact version/no matching distribution;
  no `CERTIFICATE_VERIFY_FAILED` marker.
- Zero dependency installs, EvalSurge executions, target/model/judge calls,
  approval claims or benchmark exports.

The protected diagnostic/failure receipt is in that same evidence directory.
Final exact-profile metadata confirmed compute **STOPPED**, App **UNAVAILABLE**.
The App, grants, volume and diagnostic/failure source snapshots remain preserved.
This is denied index access, not proof of the specific proxy/network policy layer,
interpreter incompatibility or successful EvalSurge cloud installation. The pinned
wheel is advertised to the laptop with the expected hash and requires Python >=3.10.
Do not use a public-index fallback, remove hashes or downgrade to hide this gate.

Before implementation, the October 12 ADR 0019 amendment recorded that SDK
0.146.0/App routing metadata needs an explicit private `workspace_id`. Runtime
and sample now preserve a canonical positive 1–20 digit ID through operator
bindings and independent workers, requiring exact actual/detached/SDK agreement.
Profile guards remain unchanged and legacy native callers with no configured or
injected ID remain compatible. The amendment's designated maintainer acceptance
is still required before deploying/live-arming the repaired runtime.

Source/project/OpenAPI/sample version is **0.2.1.dev2026101201**. This repair changed
only the editable project version in the retained lock; dependency versions,
hashes and registry provenance remain unchanged. Both earlier wheels are preserved.
The initial new wheel archive and isolated base/server installations passed
through the explicitly approved source, with required lock hashes and **zero**
agent/model/cloud/timing dispatches. Private provenance is retained under
`/private/tmp/evalsurge-workspace-id-20261012.LTOOfA/install/`. This is macOS
installation evidence, not a public-index download or Linux/App installation.
Final documentation/metadata wheel identity is recorded in the handoff. Its exact
fresh base/server installations also passed with zero agent/model/cloud/timing
dispatches; final provenance is under
`/private/tmp/evalsurge-final-workspace-id-20261012.5ObgZ5/install/`. All sixty
packaged runtime members match the initially verified new wheel, while distribution
README metadata differs. Final pure README checks passed **5 tests / 1 controlled
SSE test deselected in 0.05 s**. Old archives and their hashes remain unchanged.

Verification commands/results:

```bash
# First offline sync failed: isolated hatchling resolution lacked a cached artifact.
uv sync --locked --offline --default-index https://pypi.org/simple --extra agents --group dev
# Reuse the installed locked build backend; no public-index network access.
uv sync --locked --offline --no-build-isolation --default-index https://pypi.org/simple --extra agents --group dev
# 190 resolved; new editable version installed; lock dependency provenance unchanged.

uv run --frozen --no-sync pytest -q tests/test_native_app_runner_auth.py tests/test_app_direct_runner_example.py tests/test_source_version.py
# 192 passed in 0.78 s. Controlled SDK metadata/OAuth replies, no inference fixtures.

# The initial wider offline slice retained 228 passed / 1 failed: cryptography==50.0.1
# was absent from the isolated server install's cache, not a runtime regression.
# Explicit approved-source isolated-install rerun: 5 passed in 35.57 s.
# Its server timing check uses nine disclosed NON-agent loopback timing requests.

EVALSURGE_INSTALL_CHECK_INDEX="$APPROVED_PACKAGE_INDEX" uv run --frozen --no-sync pytest -q
# 1,765 passed / 42 upstream warnings in 299.81 s; no skips/deselections.
# Previously approved controlled-provider/framework/native-MLflow regressions,
# not real-model inference or new live journey coverage.

uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
# Passed; 245 Python files formatted.
uv run --frozen --no-sync python scripts/export_openapi.py --check
uv run --frozen --no-sync openapi-spec-validator docs/openapi.json
# Passed; schema change for this repair is the version, not public target credentials.
uv build --offline --no-build-isolation --out-dir <new-protected-artifact-directory>/dist
# Wheel/sdist built; required assets and internal imports passed archive verification.
```

The approved source selector is deliberately not embedded in public examples or
the lock. Failed results/logs are retained. The diagnostic provides no new live
matrix cell: **2/12** older-wheel successes remain separate. Notebook validation
is deferred and CrewAI retains its advisory/tooling gates. No target retries,
fallback model, new traffic allowance, commits or pushes were introduced.

## Native App predeployment review and bundle correction — October 12, 2026

Historical pre-approval/predeployment checkpoint; later state is recorded above.

Read-only CLI checks used only `--profile e2-demo-field-eng`. `load-test` is still
`STOPPED` / `UNAVAILABLE`, with no resources or active deployment. Its access list
contains the selected operator and inherited `admins` management. The separate
LangGraph target is also stopped; its October 9 successful deployment is historical,
not readiness evidence. Target permissions contain no runner principal yet, and
the selected volume retains only the previously recorded inherited administration
in its effective grant listing. No permissions or cloud resources were changed.

`databricks bundle validate --target reviewed --profile e2-demo-field-eng -o json`
on the disabled stage reproduced a real configuration error: CLI `1.17.0` warns
that bundle `valueFrom` is ignored and removes the resource reference from resolved
`EVALSURGE_EXPORT_VOLUME`. New static regressions failed twice before correction.
Both bundle templates and the private staged manifest now use `value_from`;
`app.yaml` retains the runtime contract's `valueFrom`. Corrected bundle validation
passed without that warning and resolved the approved exact target and volume.
A sandbox OAuth-cache error was retried outside the sandbox with the same profile;
no plaintext credential-storage setting or authentication fallback was used.

The staged wheel's SHA256 is unchanged:
`f81098aac24e2251955cb000bdb017b981ef64ad4474104183ef4f8c8f894d6e`.
This confirms artifact identity, not App/Linux dependency installation or OAuth.
Independent AI review is complete, but designated human maintainer review remains
unrecorded for ADRs 0017/0019 and still gates deployment. No App starts/deployments,
target/model/judge calls, credential files, protected exports, commits or pushes ran.
The traffic ledger is unchanged; older-wheel successes are not current live coverage.

Verification of this focused fix passed: **10 static tests in 0.49 seconds** across
bundle/runtime schema, source compilation/write guards, native resource data classes
and README request/link checks. The controlled README SSE test was not selected.
No inference/provider response was substituted or executed. Repository Ruff lint,
Ruff formatting (**245 files**) and `git diff --check` passed. The broader runtime
suite was not rerun for this YAML/documentation-only correction; its previous
checkpoint remains separate.

## Approved artifact storage provisioning — October 12, 2026

The user approved the exact managed volume
`ram_artifacts.evalsurge_validation.runner_artifacts`. CLI `1.17.0` and its
`schemas create`, `volumes create`, `grants get` and `grants get-effective` help
were checked before mutation. Selected-profile identity and catalog-owner checks
agreed. The schema was absent, so it and the managed volume were created using
`--json` and `--profile e2-demo-field-eng`; no existing object was overwritten.

Catalog permissions were checked before creation. The general account group has
only `BROWSE`. An existing infrastructure-administration principal has catalog
`ALL_PRIVILEGES` / `MANAGE`; it was identified with a filtered service-principal
metadata read, not assumed to be the runner. Parent grants were preserved.
Post-creation direct schema/volume grant reads returned empty sets, and the
effective volume read confirmed that existing administration remains inherited.
The selected operator owns both objects. No owner-only storage claim is made.

The reviewed wheel was copied unchanged into a fresh protected staging directory
with the standalone native App template and disabled nonsecret configuration:
`/private/tmp/evalsurge-app-stage-20261012.zJQDqB/`.
Actual `read_config()` / native binding construction, SHA256 equality and matching
`app.yaml` / bundle runtime environment declarations passed without network or
SDK construction. `EVALSURGE_OPERATOR_CONFIG` explicitly selects `operator.json`
in both manifests. Consent flags are false, approval is expired and deployed
source remains unverified; this stage must not be enabled as-is.

Safe resource/state evidence is in that directory's `provisioning.safe.json`.
No runner or target grants, cloud source uploads, App starts/deployments,
credential files, reports, target/model/judge calls or paid tests were performed.
Designated maintainer review still gates deployment of ADRs 0017/0019's changed
native runtime. Storage provisioning and local construction do not establish
Linux/App installation, live OAuth, protected export or benchmark success.

Post-update verification passed: Ruff lint, Ruff formatting (**245 files**),
`git diff --check`, and five focused static README request/policy/target-schema/
local-link tests (**5 passed in 0.05 s**). No inference fixture was selected.

## Local and App-runner scope checkpoint — October 11, 2026

The user deferred serverless notebook validation and credential provisioning.
The active installation/load-generation choices are local Python and the separate
`load-test` App in the selected `e2-demo-field-eng` workspace. Agent hosting remains
HTTP or a separate Databricks App. `ram_artifacts` is the selected artifact catalog;
an exact protected schema/volume and designated maintainer review remain required
before the changed native App runner is deployed. No notebook credential or
Lakebase instance is required by this narrowed runner path.

Fresh read-only metadata checks with `--profile e2-demo-field-eng` confirmed:

- `load-test`: compute `STOPPED`, App `UNAVAILABLE`, no resources or deployment.
- `agent-bricks-es-lg-1008` and `agent-bricks-es-oai-1008`: compute `STOPPED`,
  App `UNAVAILABLE`, with historical `SUCCEEDED` deployments retained. A retained
  deployment success is not current inference readiness.

The first sandboxed metadata check could not access the existing OAuth cache;
the same selected-profile check outside the sandbox succeeded. No authentication
storage setting was changed. No App was started, deployed, granted access or
invoked, and no model or judge calls were made.

Ruff lint passed, Ruff formatting passed for **245 files**, and `git diff --check`
passed. The existing reviewed native-auth wheel's required assets and internal
imports were rechecked without installation or execution of its contents:

```bash
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
git diff --check
```

After the current-facing documentation edits, five focused README request/policy,
target-schema and local-link checks passed in **0.06 seconds**, and
`git diff --check` passed again. The controlled SSE regression was explicitly not
selected; these checks made no endpoint, model, OAuth or cloud calls.

The archive check called `scripts.verify_wheel.verify(Path(...))` against the
retained wheel with SHA256
`f81098aac24e2251955cb000bdb017b981ef64ad4474104183ef4f8c8f894d6e`.
An initial positional-path invocation of the script failed because its CLI reads
the repository's `dist` directory rather than accepting a path; the direct verifier
call then passed. Existing isolated local installation receipts remain valid only
for their recorded artifact/environment. No new installed-package, Linux/App,
live OAuth, load, evaluation or measurement-accuracy validation is claimed.

## Native authentication integration checkpoint — October 11, 2026

The new runtime has a distinct version, `0.2.1.dev2026101101`, rather than
overwriting the original frozen wheel. README/installation/App-runner wheel
references and OpenAPI use the same new version. Public-origin offline lock
consistency passed (190 resolved). The sample inventory/version regressions
passed in a fresh process: **3 passed in 0.26 s**. The intentionally unsafe
journal-permission regression also passed with normal `022` umask: **1 passed
in 0.04 s**.

The intermediate full controlled suite was run against an evolving checkout:
**4 failed / 1,600 passed / 42 warnings in 306.42 s**. Its protected console log
is `/private/tmp/evalsurge-full-controlled-20261011.TbqAGJ/pytest.private.log`.
This is not final release validation. The failures were:

- The wrapper's `077` umask changed an intentionally unsafe `0644` journal into a
  safe `0600` file. A fresh test with ordinary permission semantics passed above.
- The installed-wheel integrity check detected the root's concurrent version/lock
  edit; this was not the earlier missing public-origin cryptography cache entry.
- The version test imported the old constant before the root changed metadata.
- The journey inventory still expected the historical eighteen-cell/no-live-result
  wording. Its assertions now match the requested fifteen-cell plan and distinguish
  listed samples from actual live successes.

Independent native-auth review also found and requested fixes for false profile
conflicts in static native diagnostics and malformed configured/SDK-returned
origins. The first focused native tests passed alone (**229**) but a combined
SDK regression slice reproduced **8 failed / 171 passed**: patching the real
`Config.__new__` contaminated later native SDK construction. That test boundary
was replaced without changing the real Config class. The corrected combined
native-auth/profile/settings/direct-SDK/diagnostics slice passed **270 tests**;
an independent SDK/settings/diagnostics slice passed **185 tests**. Strict configured
and discovered HTTPS origins, exact runner service-principal/resource mapping,
independent native M2M providers and expiry-driven refresh are covered.
All these auth tests use disclosed controlled SDK/OAuth boundaries, not live
credentials, deployed agents or actual inference. Native live App authentication,
protected export, notebook authentication and designated maintainer review remain
separate gates. These failed checkpoints remain retained below the final result.

### Stable final controlled suite

The stable suite first retained **1 failed / 1,706 passed / 42 warnings in
299.37 s**: the App sample's AST ownership assertion still looked inside
`_http_run` after SDK/context ownership moved to `_direct_run`. The correction
checks delegation, context ownership and that only `RunFailed` is caught,
without weakening cancellation propagation. Its focused rerun passed **66 tests**.

The subsequent full rerun finished **1,707 passed / 42 warnings in 304.60 s**:

```bash
EVALSURGE_INSTALL_CHECK_INDEX="$APPROVED_PACKAGE_INDEX" \
  uv run --frozen --no-sync pytest -q
```

The source selector was the separately approved internal registry, supplied
privately. Locked versions/hashes and public index provenance were preserved.
The disclosed controlled suite includes provider fixture responses, inert timing
endpoints and SDK/OAuth HTTP fixtures. It establishes no new real-model, deployed
App, notebook, cloud-authentication or measurement-accuracy success. Warnings
were one MLflow/SQLAlchemy `noload` deprecation and 41 MLflow/pandas positional
`all` warnings.

Ruff lint/format passed (**245 files**), OpenAPI export equality/schema validation
passed, and `git diff --check` passed. A plain offline lock check failed under
the ambient index selector; the explicit public-identity check passed without
rewriting the lock:

```bash
uv lock --check --offline --default-index https://pypi.org/simple
```

Final documentation review also reproduced a stale older-wheel hash in the
disabled portable runner template (**1 failed / 1 passed** pure template checks).
It now uses the same zero-hash placeholder as the native template, requiring
selection of the actual reviewed artifact before launch. The focused
template/matrix/bearer/source-version slice passed **151 tests in 1.27 s** after
correction. The full-suite result above precedes this documentation/template and
test-only correction.

The locked agent/dev environment synchronized successfully, including updating
editable installation metadata to `0.2.1.dev2026101101`, without network resolution
or rewriting public lock provenance:

```bash
uv sync --locked --extra agents --group dev --offline --no-build-isolation \
  --default-index https://pypi.org/simple
```

After that sync and the two new template regressions, the final full command
with the same explicit approved source selector passed **1,709 tests / 42
warnings in 301.79 s**. No tests skipped or were deselected. No version, lock or
runtime code changed during this final run. The controlled-inference boundary
and warning categories remain those disclosed above; live coverage did not grow.

### Stopped runner-App provisioning, not live workload validation

The approved `load-test` App was absent in the selected workspace. An initial
sandboxed read could not use cached authentication; the outside-sandbox retry
with the same profile succeeded. No authentication-storage fallback was used.
Only the stopped shell was created:

```bash
databricks apps create load-test --no-compute --no-wait \
  --description 'Private EvalSurge direct load-generator validation; stopped shell, no deployed workload' \
  --profile e2-demo-field-eng -o json
databricks apps get load-test --profile e2-demo-field-eng -o json
```

CLI 1.17.0 help confirmed `--no-compute` before creation. The immediate response
reported dependency provisioning; a subsequent metadata read confirmed compute
`STOPPED` and resolved its service-principal client UUID. App status `UNAVAILABLE`
is an undeployed shell, not a serving success. No source, credential export,
resource grant, compute start, model call or new benchmark occurred. Protected
volume choice, notebook M2M source and designated review remain gates.
The content-free provisioning receipt is retained privately at
`/private/tmp/evalsurge-final-checkpoint-20261011.SG59x1/load-test.provisioning.safe.json`.

### Final artifacts

The reviewed wheel remains unchanged and passed packaged-asset/internal-import
verification. Its fresh base/server install evidence remains under
`/private/tmp/evalsurge-native-reviewed-20261011.HlxeuH/install/`:

```text
evalsurge-0.2.1.dev2026101101-py3-none-any.whl
SHA256 f81098aac24e2251955cb000bdb017b981ef64ad4474104183ef4f8c8f894d6e
```

The source archive was refreshed after the final tests, templates and documentation
corrections, without overwriting the reviewed wheel or prior source evidence:

```bash
uv build --sdist --no-build-isolation \
  --out-dir /private/tmp/evalsurge-final-checkpoint-20261011.SG59x1/dist
```

Archive asset/metadata verification passed. The archive is
`evalsurge-0.2.1.dev2026101101.tar.gz`, SHA256
`f7f3786630f0d54e0f006f604c83b61e518a8b29fb8674e02bab4385c2d7fdcc`.
This build receipt itself postdates the archive. No claim is made of a public
package release, Linux install, remote CI, designated maintainer approval or
new real-model coverage. Final Ruff lint/format, OpenAPI equality/schema and diff
checks were repeated after the documentation corrections. A bounded search of
README, docs, examples and dependency/lock files found no internal registry host
after generalizing one historical mirror-failure record; this is not a full secret
audit. Branch/HEAD remain `main` / `1089553d58c69f368e31447e4ec1e1d0cc1848fd`;
tracked and untracked work is preserved, uncommitted and unpushed.

## Fresh installed-wheel live matrix and install recovery — October 11, 2026

The selected workspace/profile remains `e2-demo-field-eng`; the dedicated runner
App name is `load-test`. Notebook-generated load targets deployed agent Apps only.
The requested basic matrix has fifteen cells. **Two passed with actual inference**:
local Python → LangGraph HTTP and local Python → OpenAI Agents HTTP. The other
thirteen remain pending installation/security/authentication/deployment/ingress
and protected-export gates. No benchmark-submission API server was used.

The fresh independent runner installed all 117 hash-locked server dependencies
through the approved registry outside the checkout, using Python 3.12.13/macOS
ARM64 and `python -I`. It tested this frozen wheel:

```text
evalsurge-0.2.1.dev20261011-py3-none-any.whl
SHA256 4acba9feeb55dd724b0389ef84eaaf3cc623f4af42e14e9aa1ae8d8431b33b8f
```

Each actual framework ran one excluded probe and one measured request through
`system.ai.gpt-oss-120b` on `/ai-gateway/mlflow/v1/responses`. All four model calls
succeeded; there were no fixtures, retries, model fallback, tools, memory, planner
or judge. Concurrency was one and each model call allowed at most 512 output
tokens. Measured latency was 580.37 ms (LangGraph) and 570.38 ms (OpenAI Agents).
Typed status/result/report retrieval agreed and the runner/agent/listener cleanup
completed. These are reduced functional smokes, not unchanged tutorial workloads,
tail distributions, sustainable capacity or proof of zero observer overhead.
Journals drained completely; generator state remained `unknown`, with maximum
hub lag 16.70 ms and 22.32 ms. Nonstreaming HTTP cannot supply answer-text TTFT.

Two separate actual-handler fail-fast checks rejected unsupported inputs before
provider dispatch: one failed probe per framework, `target_http_error`, no measured
rows, no model calls, consistent typed retrieval and completed cleanup. They used
checkout runtime matching the frozen wheel, not separate installed-wheel runs.
Protected reports and the ledger remain under
`/private/tmp/evalsurge-matrix-smoke-20261011.2mWD9R/`; details and actual harness
commands are in [the live matrix record](docs/LIVE_MATRIX_RESULTS.md).

CrewAI 1.15.23 installed 162 hash-checked distributions in its isolated Python
3.11 environment and passed `uv pip check`, but ChromaDB 1.1.1 failed the retained
advisory gate (`PYSEC-2026-311`, `PYSEC-2026-3813`, `PYSEC-2026-3814`,
`PYSEC-2026-3815`). CrewAI inference remains held: no forced incompatible upgrade,
suppressed advisory or security exception was assumed. Inspected Agent Bricks
0.4.0/0.5.0 parsers also do not establish a native CrewAI/managed-store deployment
route. This does not preclude independently served CrewAI HTTP on Apps.

The approved controlled-provider full regression run retained **1 failed / 1,601
passed / 42 warnings in 270.68 s**. The failure was the server installed-wheel
test: public-origin `cryptography==50.0.1` was not cached. Protected retained
diagnostics reproduced that failure without changing lock provenance. The
installation regression now retains failure logs after environment cleanup.
Explicit approved-source reruns passed:

```bash
EVALSURGE_INSTALL_CHECK_INDEX="$EVALSURGE_APPROVED_PACKAGE_INDEX" \
  uv run --frozen --no-sync pytest -q tests/test_install_contract.py
# 5 passed in 34.16 s

EVALSURGE_INSTALL_CHECK_INDEX="$EVALSURGE_APPROVED_PACKAGE_INDEX" \
  uv run --frozen --no-sync pytest -q \
  tests/test_install_contract.py tests/test_http_bearer_samples.py \
  tests/test_framework_runner_matrix.py tests/test_app_direct_runner_example.py \
  tests/test_runner_target_examples.py
# 152 passed in 37.35 s

uv lock --check --offline --default-index https://pypi.org/simple
uv sync --locked --extra agents --group dev --offline \
  --default-index https://pypi.org/simple --no-build-isolation
```

The exact approved internal index was supplied privately; the commands above
represent its value with `EVALSURGE_APPROVED_PACKAGE_INDEX`, not a public registry
URL or customer installation recommendation. This does not relabel the
public-index lock. Those focused checks made no
model/cloud calls; installed timing checks used the explicitly disclosed inert
loopback endpoint. They do not replace the failed historical full run. Native
App-runner authentication is being implemented under proposed ADR 0019 and must
receive its own focused, integrated and live validation against a newly versioned
wheel. Earlier real-model results do not validate that new runtime. Designated
maintainer review, protected cloud resources and fresh cloud traffic remain gates;
no commit, push or deployment is established by these records.

## Earlier post-review runner/target sample checks — October 11, 2026

Branch `main`, HEAD `1089553d58c69f368e31447e4ec1e1d0cc1848fd`; earlier
tracked/untracked edits remain preserved and uncommitted/unpushed. This continuation
finishes source preparation/review, **not the requested live matrix**. No fresh
real-model cell passed; no SDK authentication, dependency installation, deployment,
cloud mutation, model call, full controlled-provider suite, CI, commit or push ran.
An exact public-doc retrieval and local `databricks version`/help checks are not
workspace or inference validation.

Parallel implementation and independent review reproduced/fixed:

- Strict model/workspace origins and scalar bounds before SDK setup; the native
  origin check now matches the canonical handler, including scheme spelling.
- Off-loop SDK setup/refresh using owned threads. Cancellation remains owned
  until workers settle, takes precedence over later worker failures, and is not
  a hard auth deadline or guarantee of zero event-loop/generator overhead.
- Independent customer agent environments and standard-library-importable shared
  handlers. Both HTTP entrypoints use the native OpenAI async HTTP client.
- Sample-only optional HTTP bearer environment references across the matrix,
  local HTTP runner and private App runner, matching the existing notebook option.
  Existing exact-URL `Connection` handling remains unchanged; references stay
  outside requests/receipts, HTTPS is required, and App targets reject HTTP auth.
- Fixed matrix CLI error disclosure: broad `ValueError` handling included native
  Pydantic error text containing a submitted credential-bearing malformed URL.
  Fixed guidance now omits all supplied values. Two matrix CLI regressions
  reproduced disclosure; four matrix/local CLI rejection cases now pass without
  authentication, workers, provider calls or fixture completions.

Canonical handler regressions initially reproduced **16 failures / 1 pass**;
sample bearer regressions initially reproduced **23 failures / 7 passes**.
These failures and corrected checks concern source/schema/configuration/lifecycle
and intentional pre-provider rejection, not substituted successful model answers.

Prepared native source covers LangGraph, OpenAI Agents and CrewAI. Source review
and actual local parser checks of retained `databricks-agentbricks==0.4.0`
established that its project loader requires a framework and rejects CrewAI/an
omitted framework. Current official Agent Server guidance assigns managed Runtime
Store provisioning to `agentbricks deploy`, not to independent store creation or
binding. Removed the misleading manual-store recipe. CrewAI staging now includes
its prerequisite guide and records `deployment_route: unresolved`; no false
framework label or process-local store substitutes for a native deployment.
This is a tooling/provisioning gate, not a claim that Apps cannot host CrewAI.

Final combined non-inference command:

```bash
uv run --frozen --no-sync pytest -q \
  tests/test_framework_runner_matrix.py \
  tests/test_serverless_notebook_examples.py \
  tests/test_app_direct_runner_example.py \
  tests/test_runner_target_examples.py \
  tests/test_unified_journey_examples.py \
  tests/test_readme.py \
  -k 'not test_readme_python_request_runs_without_judging' \
  tests/test_standalone_framework_handler.py \
  tests/test_real_framework_contract.py \
  tests/test_native_agent_app_examples.py \
  tests/test_http_bearer_samples.py \
  tests/test_simple_examples.py::test_example_index_links_resolve \
  tests/test_simple_examples.py::test_every_user_example_has_an_explicit_integration_contract \
  tests/test_simple_examples.py::test_journey_sources_have_named_non_inference_contract_coverage
```

Result: **430 passed / 1 deselected in 1.59 seconds**. The deselected README
regression uses controlled SSE answers; it was not run. Native checks also passed
separately: **107 in 0.13 seconds**. No successful provider completions were
fabricated in these checks. This supersedes only the earlier sample slices below,
not full-suite or live validation evidence.
The earlier **426 / 1 deselected in 1.72 seconds** snapshot predates the four
malformed-URL disclosure regressions and is superseded by this final sample slice.
Independent final re-review confirmed the native origin fix (**107 checks**) and
closed the original inert malformed-URL disclosure reproduction (**36 bearer/CLI
checks**). All previously confirmed findings in that sample-review scope are
resolved. This peer review is not designated maintainer approval or a full-repository
security sign-off.

Final static commands also passed:

```bash
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync python scripts/export_openapi.py --check
uv run --frozen --no-sync openapi-spec-validator docs/openapi.json
git diff --check
```

Formatting covered **242 files**; schema validation returned
`docs/openapi.json: OK`. A bounded search of public installation/sample files and
the root dependency/lockfiles found no internal registry-proxy URLs. That search
is not a comprehensive secret audit. No dependency sync/build occurred here.

Rechecked the reviewed wheel SHA256:
`4acba9feeb55dd724b0389ef84eaaf3cc623f4af42e14e9aa1ae8d8431b33b8f`.
A second read-only ZIP/checkout comparison found **60 runtime files / zero
mismatches**. No wheel was rebuilt or overwritten; examples are separate source.
Current staging hashes are:

```text
b2e1d72acd0da1e141ec2eb0f9708d2d581d73011bcdac993b08b1fa8735c96a  real_framework_handler.py
ba981526d2b2255474ea5a2d614828cb6be62e5ffe83e5ff3260bf552967e320  shared/native_agent.py
```

Fresh bounded traffic/resource approval, reachable HTTPS HTTP origins, protected
portable cloud-worker OAuth and evidence export resources, compatible CrewAI
installation, supported native deployment and designated ADR review remain gates.
Full controlled-inference suite/CI needs its disclosed exception before publication;
do not suppress CI to evade that gate. All eighteen cells remain `not_run`.

## Pre-review integrated customer-agent example checks — October 11, 2026

Continued the runner/target checkpoint below without discarding any earlier
tracked or untracked work. The shared real-framework handler now imports without
EvalSurge, and the standalone CrewAI HTTP endpoint owns its separate customer
environment. Prepared LangGraph/OpenAI agent-only App projects include strict
native inputs, App-owned OAuth, explicit candidate dependencies and checksum-based
public-source staging. CrewAI's inspected managed-CLI route remains a gap, not a
platform prohibition. No deployment, installation, real inference, model fixture,
cloud mutation, commit or push occurred in this integration check.

Reproduced `StopIteration` in the source-grounding regression after extracting
the authoritative refund policy. Updated only its AST source lookup to the new
canonical `examples/real_framework_handler.py`; the policy-grounding assertion
is preserved. Independent source/trust reviews remain separate from maintainer
approval and live validation.

Combined command:

```bash
uv run --frozen --no-sync pytest -q \
  tests/test_framework_runner_matrix.py \
  tests/test_serverless_notebook_examples.py \
  tests/test_app_direct_runner_example.py \
  tests/test_runner_target_examples.py \
  tests/test_unified_journey_examples.py \
  tests/test_readme.py \
  -k 'not test_readme_python_request_runs_without_judging' \
  tests/test_standalone_framework_handler.py \
  tests/test_real_framework_contract.py \
  tests/test_native_agent_app_examples.py \
  tests/test_simple_examples.py::test_example_index_links_resolve \
  tests/test_simple_examples.py::test_every_user_example_has_an_explicit_integration_contract \
  tests/test_simple_examples.py::test_journey_sources_have_named_non_inference_contract_coverage
```

Result: **342 passed / 1 deselected in 1.59 seconds**. Checks cover pure
source/schema/configuration/staging/lifecycle contracts and intentional
pre-provider failures, including construction of actual framework objects.
The deselected README test supplies controlled SSE answers and was not executed.
No successful agent/model response was substituted. This result does not
supersede the historical full controlled-provider suite or pass any live cell.

Full Ruff lint, formatting (**240 files**), OpenAPI snapshot equality, OpenAPI
schema validation (`docs/openapi.json: OK`) and `git diff --check` passed.
A read-only byte comparison of all **60** packaged `evalsurge`/`benchmark_agents`
files found no mismatches against the reviewed wheel. Its SHA256 is unchanged:
`4acba9feeb55dd724b0389ef84eaaf3cc623f4af42e14e9aa1ae8d8431b33b8f`.
This is artifact identity, not a fresh installation or provider result. The
examples remain separate from the installed wheel. Fresh bounded traffic,
reachable HTTP origins, cloud-worker authentication, target/runner deployments,
protected evidence export and the disclosed CI exception remain pending.

## Runner/target sample expansion — October 11, 2026

Branch `main`, HEAD `1089553d58c69f368e31447e4ec1e1d0cc1848fd`; all earlier
tracked/untracked work is preserved. No commit or push occurred. The current
request is 18 real-inference cells: CrewAI/LangGraph/OpenAI Agents, separately
hosted HTTP/deployed Apps, and local/serverless-notebook/separate-App runners.
None gained fresh live inference coverage in this checkpoint. See
[the explicit matrix](docs/RUNNER_TARGET_VALIDATION.md).

Three parallel workstreams added a pure inventory/request generator, standalone
installed-package serverless HTTP/App notebooks, and a disabled private one-shot
direct runner App with proposed ADR 0017. No separate benchmark-submission API
is required. Public native agent-App deployment projects for all three frameworks
remain a deliverable; historical private bundles are not public sample coverage.
The reviewed runtime wheel below is unchanged; these example sources are separate.

Independent review reproduced premature App journey success before evidence
export and found synchronous SDK initialization could block the event loop.
The sample now holds journey success false until artifact/receipt upload returns,
records export cancellation/failure separately, and owns SDK initialization in
an off-loop thread. Native App workspace/client selectors are checked before
credential-provider construction. Installed Databricks SDK 0.146.0 source shows
that its OIDC discovery uses an independent client with default 300-second retry
and 60-second transport settings; the sample's resource-client settings do not
bound that phase or guarantee platform shutdown. No SDK source was patched.

The preliminary review's remote-HTTP acceptance finding was retracted after
pure construction reproduced the existing `Agent.http` HTTPS rejection. Added
helper-specific HTTPS checks improve deterministic guidance, not a previously
accepted insecure binding. Six new matrix guidance tests initially failed and
three local-HTTP checks passed; the helper correction passed the complete pure
matrix suite (97 tests). No remote HTTP connection was made.

The initial combined four-module sample slice passed **141 tests in 0.57s**.
README-only schema/navigation checks passed **5 / 1 deselected in 0.04s**; the
excluded case invokes a controlled SSE agent fixture and was not run. Three
selected example-index/inventory tests passed in **0.08s**, without fixtures.
Full Ruff lint/format (228 files), OpenAPI equality/schema and whitespace checks
passed at this preparation snapshot. uv-cache sandbox denial was rerun through
explicit escalation; it was not treated as a behavioral failure. These are
non-inference checks, not actual agent/framework/provider or cloud validation.

The final combined sample slice then passed **166 tests / 1 deselected in 0.61s**:
the four sample-contract modules, README schema/navigation tests, and three named
example-index/inventory tests. The deselected README case uses a controlled SSE
fixture and was not executed. No agent or provider transport was invoked or
substituted in this slice. The final static-check command completed with exit
zero: Ruff lint, formatting (228 files), OpenAPI export equality, OpenAPI schema
validation (`docs/openapi.json: OK`), and `git diff --check`. This final result
supersedes the initial sample slice only, not the historical full-suite result
or any pending live matrix cell.

Cloud access was checked separately. The exact selected `e2-demo-field-eng`
profile initially failed with the older-CLI credential-cache error. Explicit
OAuth login with the same profile/host succeeded; no alternate profile or
plaintext credential-storage fallback was selected. Read-only App inventory and
exact `apps get` calls then observed:

| Exact App | October 11 observation |
| --- | --- |
| `agent-bricks-es-lg-1008` | Compute STOPPED; App UNAVAILABLE; retained deployment SUCCEEDED |
| `agent-bricks-es-oai-1008` | Compute STOPPED; App UNAVAILABLE; retained deployment SUCCEEDED |
| `test-eval-crewai-1009` | Nonexistent or deleted (CLI exit 1) |

Metadata access does not prove notebook/worker auth, current inference readiness
or a tested App. No target/judge/planner/model calls, App start/deployment,
notebook Jobs, cloud artifact writes or resource creation/deletion occurred.
The earlier completed traffic leases and 1,252-test controlled-provider pass below
are historical. Fresh bounded traffic/resource selections, protected portable
credentials/volume, CrewAI installation, designated maintainer review and the
explicit controlled-inference exception before full-suite/push-triggered CI
remain gates. No classic compute fallback or public package publication is claimed.

## Finish-and-validate integration — October 11, 2026

Branch `main`, baseline HEAD `1089553d58c69f368e31447e4ec1e1d0cc1848fd`;
working-tree changes remain uncommitted/unpushed. This is a development demo build,
not public-index publication or release approval. See [demo readiness](docs/DEMO_READINESS.md).
Older real-model/CI results below retain their original boundaries and dates.

Root and three parallel agents repaired packaged serverless retrieval imports,
shared content-free Python/CLI summaries, version/install guidance, cancellation
ownership and evidence labeling. No new model, agent, OAuth, cloud, deployment,
publication or paid calls occurred. Native timing endpoints are explicitly NOT
agents or inference substitutes. The user subsequently approved the full offline
controlled-provider suite below; no new remote CI result is claimed.

### Approved full offline suite — October 11, 2026

The user explicitly approved this controlled-inference exception after disclosure.
Fixtures include deterministic localhost HTTP/SSE answers, stubbed phase-unit
preflight outcomes, and canned provider responses for actual framework/native
MLflow integrations. These passes are not actual model inference, deployed-App
success, notebook-generated load, timing calibration or judge-quality validation.
No paid traffic, authentication, deployment, notebook Job, remote CI, publication,
commit or push was requested or performed by this verification.

Commands, with the approved dependency-source selector redacted:

```bash
uv sync --locked --extra agents --group dev --offline \
  --default-index https://pypi.org/simple --no-build-isolation
EVALSURGE_INSTALL_CHECK_INDEX=<explicit-approved-source> \
  uv run --frozen --no-sync pytest -q
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync python scripts/export_openapi.py --check
uv run --frozen --no-sync openapi-spec-validator docs/openapi.json
```

Locked sync resolved **190 packages / checked 182**. The first full run ended
**1 failed / 1,249 passed / 42 warnings in 310.54 seconds**. The failure in
`test_journey_sources_compile_and_notebook_has_an_explicit_consent_gate` used
ordinary module compilation for the source notebook's intentional top-level
`await`. Only the source-check test changed: explicitly marked Databricks notebooks
use `ast.PyCF_ALLOW_TOP_LEVEL_AWAIT`; ordinary scripts remain strict. Two new
regressions reject ordinary-script top-level await and invalid notebook syntax.
Focused source contracts: **12 passed in 0.10 seconds**. No notebook or packaged
runtime code was changed or executed for this correction.

The complete rerun passed **1,252 tests, no skips or deselections, 42 warnings in
301.37 seconds** and exited zero. Warnings come from MLflow's SQLAlchemy `noload`
and positional pandas `all` use; no dependency changes were made to silence them.
The full run includes the fresh-install tests previously handled separately,
using unchanged lock hashes through the explicitly approved source. This is not
a public-index download or Linux/all-interpreter install result.

Final Ruff lint/format (**217 files**), OpenAPI equality/schema and whitespace
checks passed. Public-origin verification still found 189 locked registry
packages. uv-cache sandbox denials were rerun with explicit escalation, not
misreported as test failures. The lock SHA256 remains
`16f879c970e85ba8070843dac75e1338723136ec369acbb0a61cecb3509816f3`.

A fresh offline build retained in
`/private/tmp/evalsurge-full-checks-20261011.hOdiVh/dist` reproduced the reviewed
wheel SHA256 `4acba9feeb55dd724b0389ef84eaaf3cc623f4af42e14e9aa1ae8d8431b33b8f`.
The archive CLI ignores positional paths; the first attempted explicit-path call
therefore checked an older default-directory wheel and failed for missing assets.
Calling the existing `verify()` / `verify_sdist()` helpers with the exact new
paths passed. No archive or runtime repair was required. Earlier archives remain
preserved; source snapshots have distinct hashes after retrospective docs/tests.

After the test correction and result notes, the offline build was repeated into
the separate `post-test-dist` directory under the same verification root. Both
archives passed the explicit-path verification helpers. Its wheel hash is still
identical to the reviewed demo wheel; source SHA256 is
`05d15b480c7939070e79525dea6461b7c93968a6d504346051abd052258107bc`.
This source snapshot contains the corrected test and suite record; this later
checksum note is retrospective. No previous archive was replaced.

The exception approval applies to these disclosed offline runs, not unbounded
real-model traffic or an automatic push/remote-CI run. Fresh live HTTP/App coverage,
portable serverless credentials, supported-platform CI and maintainer review remain
separate gates.

### Reproductions and focused corrections

- Missing `evalsurge.hosted_journeys` reproduced directly and through the previously
  untested packaged `execute()` branch. Pure `_retrieval` now supplies it and the
  historical harness re-exports the same implementation. Native SDK/storage
  pre-provider rejection verifies context closure and storage reopening.
- New daemon-handler and repeated-server-close cancellation regressions initially
  **2 failed**, then passed after owned non-daemon handlers and shielded, awaited
  native close. Cancellation retains the protected receipt before re-raising.
- Native inert-child TERM-grace regression first exposed **1 failure**, then
  passed after one shielded TERM/grace/KILL/reap task. An earlier construction
  attempt failed because the test omitted required description; that was a test
  setup error, not the reproduced process-ownership failure.
- Calibration acceptance now needs successful correlated timing pairs, exact
  injected storage-fault counts and observed cleanup. Empty observations and
  arbitrary interrupted workers cannot become calibration passes.
- Serverless receipts now separate metadata, client dispatch and completed
  responses. Planning/authentication/launch failures do not claim App invocation.
  Planless result/report evidence disagreement reproduced **1 failed / 1 passed**;
  both then passed after empty display profiling stopped masquerading as collected
  evidence. Unknown planless totals remain unknown, not zero.
- Independent source review confirmed the three lifecycle/evidence findings were
  addressed without an additional P1. It inspected the installed CPython transport
  cancellation boundary; this is not alternate-runtime/abrupt-loss certification
  or designated maintainer approval.

### Integrated non-inference checks

```bash
uv run --frozen --no-sync pytest -q \
  tests/test_calibration.py tests/test_measurement_math.py \
  tests/test_measurement_journal.py tests/test_measurement_dispatch.py \
  tests/test_measurement_recovery.py tests/test_runner_cleanup.py \
  tests/test_summary.py tests/test_generator_presentation.py tests/test_evidence_cli.py \
  tests/test_retrieval_consistency.py tests/test_serverless_app_target_contract.py \
  tests/test_serverless_portable_oauth.py tests/test_source_version.py \
  tests/test_report_ui.py tests/test_hosted_evidence_contract.py \
  tests/test_readme.py tests/test_wheel.py tests/test_install_contract.py \
  -k 'not test_readme_python_request_runs_without_judging and not test_installed_wheel_is_portable_without_checkout_or_development_group'
```

Initial integrated run: **307 passed / 1 failed / 3 deliberately deselected**.
The failure was `test_remaining_descendant_is_not_mistaken_for_owner_cleanup`:
production retained a negative descendant-cleanup observation, then the host
reaped the process group before the test's final best-effort SIGKILL. Only
test-owned cleanup now tolerates ProcessLookupError; its negative-evidence
assertions remain unchanged. Focused rerun: **1 passed / 53 deselected**. Complete
rerun: **308 passed / 3 deselected in 20.20 seconds**. A workstream's earlier broad
run also recorded **153 passed / 1 intermittent native-process failure** before
passing alone and **154 passed** on rerun; that failure is retained, not erased.
The three deliberate exclusions are one controlled-inference README test and
two fresh-install tests handled by the separate installation verifier.

Adding the two pure primary-journey construction/source checks exposed a separate
native cleanup failure: **309 passed / 1 failed / 3 deselected in 20.46 seconds**
in `test_native_deadline_terminates_owned_group_without_success`. It is not hidden
by the earlier rerun. Twenty inert-process probes initially returned two
cleanup-unverified results despite owner reaping, with `killpg(group, 0)` returning
`EPERM`. The subsequent thirty-round investigation observed eleven unverified
results inside the sandbox and fifteen outside it. A later read-only probe after
reaping returned `ESRCH`; no surviving live child was observed.

The new regression first failed, then passed after cleanup required explicit
post-reap group absence. Persistent permission errors, surviving descendants and
failed reaping still cannot certify cleanup; no terminating group signal follows
unknown visibility. Focused cleanup checks: **7 passed**. Thirty post-fix native
probes: seven observed permission transitions, **zero unverified cleanups**.
Six serverless/retrieval modules: **156 passed in 5.12 seconds**. These checks use
actual inert processes and injected OS permission errors only, never agent/model
responses. Independent read-only review found no ownership/evidence relaxation.

Final integrated command included the earlier module list plus
`tests/test_serverless_invocation_evidence.py` and
`tests/test_runner_target_examples.py`, with the same explicit exclusions:
**323 passed / 3 deselected in 21.45 seconds**. This is a non-inference slice,
not full-suite completion. The independent fresh base/server wheel installations
remain separate checks. No controlled provider completion, actual LLM inference
or live notebook/App behavior was established by this run.

Static checks passed: repository Ruff lint, Ruff format (**217 files**),
`scripts/export_openapi.py --check`, `openapi-spec-validator docs/openapi.json`
and `git diff --check`. OpenAPI includes the source version and the existing
generator-health schema additions. Shared summary checks are pure DTO/presentation;
serverless readiness checks use lexical/private configuration, controlled SDK
metadata and native process/storage operations, never model responses.

The official App programmatic-access page was retrieved October 11. It documents
notebook-token exchange for an audience-scoped App API call; installed SDK
0.146.0 still obtains runtime exchange subjects through injected notebook
authentication context. Neither source observation establishes independent
Locust-worker refresh or a live serverless benchmark. ADR 0015 and the runner
status now explicitly separate those claims; no authentication call was made.

Final doc review also corrected wheel-only example invocation: wheel installs do
not include the `examples` source package. The portable scripts can be copied and
run separately; `[agents]` adds framework dependencies, not example files. The
Python golden path explicitly selects raw `http-json` (`query` in, `outputs` out),
and human-readable optional-remote/integration output shares `format_summary`.

### Lock and artifact failure evidence

The first ordinary offline locked sync rejected the configured-index mismatch;
an explicit public-identity offline sync then lacked isolated Hatchling cache.
The successful consistency command used the already-installed locked backend:

```bash
uv sync --locked --extra agents --group dev --offline \
  --default-index https://pypi.org/simple --no-build-isolation
```

It resolved 190 packages and changed only the editable project version. No public
registry request occurred. A packaging workstream subsequently ran verification
commands with `uv run --no-sync` but omitted `--frozen`. That allows resolution;
the lock then changed to proxy sources and some dependency versions. Locked
installation export correctly failed, and artifact freeze stopped. The individual
causing command was not established; build/export timestamps were later than the
lock mutation, so export is not blamed.

Rejected/intermediate archives and both private installation failures remain at
`/private/tmp/evalsurge-final-demo-20261011.p27YUv`. The unintended lock is retained
as `unintended-proxy-uv.lock`. Root restored the exact known HEAD lock plus the
single deliberate project-version change using `apply_patch`; it did not rewrite
proxy origins/hashes to relabel artifacts. `uv lock --check --offline
--default-index https://pypi.org/simple` then passed, 190 packages; `git diff --
uv.lock` shows only that version line. All subsequent verification uses frozen
runs and separately retained approved-source installation provenance.

### Installation-verified demo snapshot

The corrected version is `0.2.1.dev20261011`. Frozen build/installation archives
and the content-free `artifact.safe.json` are retained at
`/private/tmp/evalsurge-reviewed-demo-20261011.Voze4Q/`. Root independently
rechecked the archive and lock hashes:

| Artifact | SHA256 |
| --- | --- |
| `evalsurge-0.2.1.dev20261011-py3-none-any.whl` | `4acba9feeb55dd724b0389ef84eaaf3cc623f4af42e14e9aa1ae8d8431b33b8f` |
| `evalsurge-0.2.1.dev20261011.tar.gz` | `26a21f254dd08400b415cef0e961366280419a33f3249b0a4b34dc8ebc9daf34` |
| `uv.lock` | `16f879c970e85ba8070843dac75e1338723136ec369acbb0a61cecb3509816f3` |

Passed on **Darwin ARM64 / Python 3.12.13**: wheel/source assets and internal
imports, fresh base/server installs outside checkout, installed typed retrieval,
summary/serverless declarations, empty SDK lifecycle, report/docs assets and
native Locust discovery. Four installed storage/timing modes verified accounting
and cleanup with **9 NON-agent timing requests**, zero agent/model/auth/cloud
calls. Both standalone journey scripts passed **2 `--help` checks** using the
installed server interpreter with `-I` outside checkout; this checks CLI/import
portability, not actual target execution.

```bash
uv --no-config build --no-build-isolation \
  --out-dir /private/tmp/evalsurge-reviewed-demo-20261011.Voze4Q/dist
uv run --frozen --no-sync python scripts/verify_install.py \
  --wheel /private/tmp/evalsurge-reviewed-demo-20261011.Voze4Q/dist/evalsurge-0.2.1.dev20261011-py3-none-any.whl \
  --dependency-index '<approved-index>' \
  --evidence-dir /private/tmp/evalsurge-reviewed-demo-20261011.Voze4Q/installation-evidence \
  --timing-only
uv run --frozen --no-sync pytest -q tests/test_wheel.py tests/test_readme.py \
  tests/test_install_contract.py \
  -k 'not installed_wheel and not test_readme_python_request_runs_without_judging'
```

The final artifact/static slice passed **39 / 3 deliberately deselected in
0.26 seconds**; these overlap the integrated tests, not an additive unique count.
Hash-pinned installs used the explicitly approved source. Base/server provenance
receipts record unchanged lock and do **not** claim a public-index clean install.
Earlier failed and provisional candidates remain unchanged. The source archive
hash identifies that frozen snapshot; these later retrospective validation and
handoff notes are recorded separately, not relabeled into its archive hash.

Final root lint/format and OpenAPI equality/schema checks passed again. The first
sandboxed retry failed uv cache initialization with `Operation not permitted`;
the approved escalated rerun passed. Whitespace checks passed; public-lock origin
verification found 189 registry packages, and offline lock consistency resolved
190 packages. The lock diff remains solely the deliberate project-version change.

This is an installation-verified development snapshot, not release approval.
Linux clean installs, supported-platform remote CI, fresh real-model
HTTP/App revalidation of this journal build, portable serverless credentials and
designated maintainer review remain gates. No publication, commit, push or cloud
mutation occurred.

Validated locally on macOS/Python 3.12 on October 4–10, 2026. Baseline commit
`2276c3b4d6fa9943544f988df4e5ed658ad79365` passed GitHub run `37840928318` on
October 8: every test and security job succeeded on Linux/Python 3.11–3.14.
That approved controlled-inference CI does not validate the follow-up checkpoint
or establish live model/deployment success. Earlier mirror-install failures remain
historical evidence. Repository review enforcement remains a maintainer gate.

## Measurement integrity and serverless preparation — October 10, 2026

Branch `main`, baseline `1089553d58c69f368e31447e4ec1e1d0cc1848fd`.
The current patch is uncommitted/unpushed; dependencies/lockfile are unchanged.
It implements proposed ADRs 0014/0015, not approved shared-hosting or capacity
support. Three parallel agents handled native measurement ownership, serverless
launcher preparation and independent review/CrewAI eligibility. No new cloud
mutations or agent/LLM inference occurred in this patch.

### Measurement and public-contract verification

The journal now uses one bounded cooperative FIFO/persistent native writer,
retaining per-event fsync and durable START-before-dispatch. Response clocks freeze
before completion writes, and lifecycle ownership includes acknowledgment/drain.
Stop boundaries are rechecked after persistence/authentication and immediately
before HTTP dispatch. Parent recovery compares issued/acknowledged/durable counts
and recomputes partial metrics from durable captures. New typed generator
observations are `unknown`/`degraded`, not a healthy/capacity/accuracy badge.

Root's final focused commands so far:

```bash
uv run --frozen --no-sync pytest -q tests/test_measurement_journal.py tests/test_measurement_recovery.py tests/test_measurement_dispatch.py tests/test_runner_cleanup.py
uv run --frozen --no-sync pytest -q tests/test_generator_presentation.py tests/test_evidence_cli.py tests/test_report_ui.py tests/test_hosted_evidence_contract.py
uv run --frozen --no-sync pytest -q tests/test_readme.py -k 'not runs_without_judging'
```

Results: **35 passed in 3.99 seconds**, **80 passed in 3.91 seconds**, and
**5 passed / 1 deliberately deselected**. These use native storage/process/clock
operations, inert child receipts, pure schema/presentation or intentional
pre-provider failures. The README inference test was excluded because its
controlled-provider exception is not approved. No model completion or framework
behavior is certified by these passes. Independent read-only review found no
additional measurement blocker; it is not designated maintainer ADR approval.

Final non-agent calibration used the production invocation/parent-recovery path
at concurrency five, 200 requests per successful mode, ten maximum dispatch
seconds and one-second request deadline. Native mode observed paired client-minus-
endpoint mean/p95 **0.471/0.710 ms**, **160.80 requests/sec**. Injected native
5 ms fsync delay observed **0.464/0.625 ms**, **76.89 requests/sec**. Each
durably recovered 200 successes and 200 acknowledged starts/completions, with
clean drain. START failure received zero timing requests; completion failure
retained an interrupted row, not an in-memory success. Both failed modes remained
incomplete/degraded. Endpoint and all children were stopped/reaped. This is timing
calibration only, not substituted agent inference, cloud storage or capacity.

Protected receipt:
`/private/tmp/evalsurge-measurement-integrity-final-20261010.Z2pHN3/calibration_receipt.json`.
The exact executed calibration command was:

```bash
uv run --frozen --no-sync python /private/tmp/evalsurge-measurement-integrity-final-20261010.Z2pHN3/calibrate.py
```

Earlier diagnostic receipts remain unchanged. Small paired differences support
removal of the demonstrated hub-blocking disk mechanism, not zero observer effect.
Durable waits still constrain generation rate. Do not subtract a baseline or
interpret successful-only tails as all-attempt latency. No calibrated saturation
threshold, warmup exclusion or steady-state throughput definition was added.

### Serverless and CrewAI gates

The serverless sample is a **load-generator location**, not another agent host.
It prepares an isolated owner plus the existing Locust worker with independently
refreshable OAuth M2M, using an existing bounded/private/exact profile file.
No driver tokens/caches are forwarded, notebook-global selectors changed, target
guards relaxed, identity/secret provisioned or App started. Credential source,
explicit service-principal client ID, workspace assignment and App permissions
remain absent. Driver/worker no-inference readiness must pass before separately
approved one-probe/one-measured real-model traffic. The historical failed runtime-
OAuth subprocess prerequisite remains failed, even though its Jobs task succeeded.

Independent review caught unbounded capture in the inner auth diagnostic; the
launcher now bounds output, discards stderr and preserves outer owner-group
cleanup. The root integration explicitly requires complete measurements in the
smoke-pass predicate. Native auth/configuration regressions passed with:

```bash
uv run --frozen --no-sync pytest -q tests/test_serverless_portable_oauth.py tests/test_serverless_app_target_contract.py tests/test_serverless_journey_contract.py
```

Result: **102 passed in 4.23 seconds**. These check synthetic private configuration,
native processes/storage and controlled SDK authentication/App metadata only; no
real profile, OAuth exchange, deployed App or model completion is substituted or
claimed. Independent source review found no remaining diagnostic-cleanup blocker.
An earlier root checkpoint had **71 passed / 3 failed** because three older tests
intercepted `subprocess.run` after the production code moved to bounded `Popen`.
They were repaired to emit inert diagnostic bytes from native children through
the actual bounded reader; a new overflow regression verifies child-only reaping
inside the parent's group. Neither failed nor passing checkpoint made inference
calls. Initial formatting/test startup hit the sandbox's uv-cache access error;
the no-install/no-inference commands were retried outside the sandbox.

CrewAI remains blocked before install/deployment/inference. Selected 1.15.27
failed exact resolution twice at the canonical approved source; 1.15.23 was visible
but not selected or installed. Isolated Python 3.12.13 environment remains empty.
The earlier noncanonical listing is invalid availability evidence. No registry
bypass, fallback wheel or stubbed model was used. User selection of an alternative
version and the separate proposed **76-attempt** local/App lease are required.

### Release checks and outstanding scope

At the current checkpoint OpenAPI equality and schema validation returned pass/
**OK**. The OpenAPI diff is additive v2 generator types/gaps/nullable telemetry;
no v1 schema is edited. Wheel and source distribution built successfully with
`uv build --no-build-isolation`; `scripts/verify_wheel.py` passed archive member/
asset checks after retrying the sandbox's uv-cache read error outside the sandbox.
No package installation or inference was performed by archive checks. Cached
offline locked sync in this turn resolved 190/checked 182 packages without
dependency/lock changes. Full controlled-provider suite/CI and live journeys remain
explicit unfulfilled gates. Nothing has been committed or pushed. Final combined
non-inference and release-check results are recorded below.

## Publication checkpoint before CrewAI — October 10, 2026

The user requested publication before further CrewAI work and cleanup of unneeded
resources. Source/doc review preserved the evaluation process implementation,
original failures and completed real-model recovery; old handoff/short-smoke
sections are now explicitly historical. README links the observer-effect audit.
ADR 0013 remains proposed, not independently approved. Final source self-review
found no new blocker for this bounded catalog checkpoint, but retained the
serialization-before-deadline, descendant supervision, registered-scorer and
full-suite gaps. This is not a broad production or all-journeys sign-off.

Fresh publication checks:

- `uv run --frozen --no-sync ruff check .`: passed.
- `uv run --frozen --no-sync ruff format --check .`: **193 files already formatted**.
- `git diff --check`: passed.
- `uv run --frozen --no-sync python scripts/export_openapi.py --check`: passed.
- `uv run --frozen --no-sync openapi-spec-validator docs/openapi.json`: **OK**.
- `uv build --no-build-isolation`: wheel and source distribution built.
- `uv run --frozen --no-sync python scripts/verify_wheel.py`: passed after the
  sandbox's uv cache access failure was retried outside the sandbox. Required
  modules/assets present; local assistant metadata excluded. No install/inference.
- Earlier in this publication session,
  `uv run --frozen --no-sync pytest -q tests/test_evaluation_process_storage.py`:
  **29 passed, one upstream SQLAlchemy warning, 28.62 seconds**. Actual native
  SQLite/process regressions, no LLM/agent inference or substitute completions.
- Narrow path/pattern inspection found no newly added private registry URLs,
  token-shaped literals or private-key markers. Historical examples/fixtures
  are not a comprehensive secret scan; protected live artifacts remain excluded.

GitHub authentication matched personal repository `RamVegiraju/EvalSurge` to
`RamVegiraju`; neither identity was removed. Remote fetch showed baseline HEAD
and origin/main aligned. Publication uses `[skip ci]`: the full controlled-provider
suite and new CI are not approved or claimed passed. Normal hooks remain enabled.
Final commit SHA/remote state are reported after push, not guessed in this file.

### Reversible cloud cleanup

Using only the selected `e2-demo-field-eng` profile:

- `databricks apps stop agent-bricks-es-lg-1008 --profile e2-demo-field-eng --timeout 1m -o json`
- `databricks apps stop agent-bricks-es-oai-1008 --profile e2-demo-field-eng --timeout 1m -o json`

Both commands completed and returned compute **STOPPED**, App **UNAVAILABLE**.
Definitions/deployments, coupled managed Runtime Stores and original runs/evidence
were preserved; restart is required before further authorized traffic. This
removes active App compute, not remaining storage charges. The recorded prerequisite
submit-run `526298221857181` was already TERMINATED/SUCCESS; its worker-auth failure
still stands. A 100-definition Job inventory showed no matching EvalSurge Jobs,
not exhaustive proof of workspace absence. No Job/store/historical evidence was
deleted, and cleanup sent no inference calls.

Fresh official release metadata and approved-source observations are documented
in `docs/DEPENDENCIES.md`: latest CrewAI 1.15.27/earlier 1.15.26 unavailable there;
1.15.23 resolution only, no installation/deployment/inference. No dependency or
lock changes, registry-policy bypass or new live lease occurred. CrewAI version/
traffic choices, serverless worker OAuth, designated review and full-regression
approval remain next gates.

## Resumed verification — October 10, 2026

Branch `main`, baseline HEAD `a4e9408c6d642dd5e20d4545e638f08f167d3d49`.
This section records the pre-publication verification; prior failed evaluation/
test receipts are retained. See the publication checkpoint below for later checks.
No controlled-provider suite or CI was run. Tests with canned judge/provider
responses or substituted phase receipts were adapted for the process boundary,
but remain unexecuted pending explicit exception approval.

Completed checks before the follow-up readiness repair:

- `uv run --frozen --no-sync pytest -q tests/test_evaluation_process_storage.py`:
  **26 passed, 1 warning in 28.51 seconds**. Native SQLite persistence,
  protected transfers, parent-state isolation, repeated timeout, cancellation
  during writes, descendant cleanup, exact source-run membership, finite means
  and the no-ready fast path passed. Deterministic storage predicates, no
  provider/agent substitutions or LLM calls. The warning is upstream
  SQLAlchemy's deprecated `noload` loader. Trace transfer is covered, not a
  trace-consuming scorer's semantics.
- `uv run --frozen --no-sync python /private/tmp/evalsurge-app-quality-recovery-20261009.r4c3jk/check_offline.py`:
  **16 checks passed**, network forbidden, zero model/App calls; exact original
  capture/sample and accounting checks passed, source hashes refreshed. The
  execution release remained absent; this is not live recovery.
- Ruff lint/format: passed, **192 files formatted**; `git diff --check`: passed.
- OpenAPI export equality and `openapi-spec-validator`: passed.
- `uv build --no-build-isolation` and
  `uv run --frozen --no-sync python scripts/verify_wheel.py`: passed. Rebuild
  after later edits; this is not a fresh-install validation.
- `uv sync --locked --extra agents --group dev --offline --default-index https://pypi.org/simple`:
  **190 packages resolved, 182 checked**, cached artifacts only. No network
  registry access, dependency/lock changes or provenance relabeling.

Independent review found readiness masking top-level worker errors and an
overstated credential-separation docstring. Both were repaired: safe worker
errors retain their codes/scorer, cancellation yields cancelled readiness, and
the docstring accurately states detached environment/auth inheritance. The
agent's follow-up `-k readiness_preserves_worker_failure` run passed **3 tests,
26 deselected, 1 warning in 1.62 seconds**; these test native no-network timeout,
pre-start cancellation and controlled OS startup denial, not stubbed inference.

Root's final combined command
`uv run --frozen --no-sync pytest -q tests/test_evaluation_process_storage.py`
passed **29 tests, 1 upstream warning in 28.34 seconds**. The independent
read-only recheck confirmed the readiness/docstring repair and found no blocker
for the narrowly bounded catalog-only recovery. Final Ruff lint/format (**193
files**), diff whitespace, OpenAPI equality/schema, build and archive-asset
verification passed after those source/test changes. A second network-forbidden
offline audit passed the same 16 checks with the final source hashes.

The root released the already-approved one-use recovery only after those gates:
`uv run --frozen --no-sync python /private/tmp/evalsurge-app-quality-recovery-20261009.r4c3jk/run_recovery.py --execute-approved-recovery-lease`.
It requires authorized outside-sandbox credentials/network, retains the original
failed lease unchanged and prohibits replay. Bounds: zero LangGraph target calls,
at most 300 supplemental judge attempts, followed only after durable completeness
and worker cleanup by at most 501 OpenAI agent and 302 judge attempts, concurrency
five, at most 180 load dispatch seconds. Execution finished with exit **0** and
the owner receipt reports **passed**. CrewAI and controlled-provider tests were
excluded. Never replay this completed recovery or the original stopped lease.
Designated ADR review and general registered trace-scorer/cleanup-failure
supervision remain separate.

### Finished real-model recovery and independent audit

The approved recovery used the exact `e2-demo-field-eng` profile and retained
Apps in workspace `1444828305810485`. Real agent inference used
`system.ai.gpt-oss-120b` (<=512 output tokens, one call per invocation, zero
retries); real judging used `databricks-gpt-5-4-mini` (<=2048 output tokens,
60-second timeout). Explicit relevance/correctness were frozen; no planner,
fallback, generated references or fixture completions were used. The runner
remained local; no deployment, resource or notebook changes occurred.

| Evidence | LangGraph historical load + supplemental judging | OpenAI fresh App run |
| --- | ---: | ---: |
| Measured successes / attempts | 500 / 500 (unchanged historical load) | 500 / 500 |
| Load error rate | 0% | 0% |
| Configured / observed concurrency | 5 / 5 | 5 / 5 |
| Successful latency p50 / p95 / p99 | 1154.21 / 1171.63 / 2161.67 ms | 1164.49 / 1675.44 / 2524.54 ms |
| Whole-window throughput, including drain | 4.173 requests/sec | 3.979 requests/sec |
| Durable relevance / correctness assessments | 50 / 50 each | 50 / 50 each |
| Judge execution errors | 0 | 0 |
| Sampled relevance / correctness pass rate | 100% / 88% | 100% / 86% |

LangGraph made **zero new target calls**. Supplemental judging reused exactly
the original 50 selected captures from run
`2b28bf04-bc4c-40f7-95f4-8a3beedebdc5`. Its new plan differs only in ID and
tracking destination, with explicit lineage. The original failed report remains
`completed_with_gaps`; the supplemental result does not replace it. OpenAI run
`1bc6580c-bdc7-408b-a625-348934b72c54` completed all phases, including one
excluded inference probe and two judge-readiness checks. Its measured elapsed
time including drain was **125.652 seconds**, last dispatch **124.450 seconds**.
Typed result/status/waited/retrieved reports and all five request pages agree.

Total new attempts: **501 agent + 202 judge = 703**, below the approved 1,103
ceiling. All 202 judge attempts were response-confirmed, with zero commit-unknown
attempts and complete reservation/context/outcome accounting. These are transport
attempts and server counters, not billing receipts. The SDK context closed;
one LangGraph and three OpenAI native worker receipts were verified, with both
PIDs and process groups absent. Parent environment was unchanged. Native worker
counts contained no pool/tag/assessment/export/refresh/SQLite-lock failures;
12 other warnings remain, so this is not warning-free execution.

Independent read-only audit command:

```bash
uv run --frozen --no-sync python /private/tmp/evalsurge-measurement-accuracy-20261009.hhACtp/audit_recovery.py
```

Exit **0**, **45/45 checks passed**, zero new target/model/cloud calls. It verified
original hashes, exact sample membership, one valid current-run assessment per
selected request/scorer, durable pass rates, SQLite `quick_check`, probe exclusion,
complete journals, recomputed OpenAI metrics, budget accounting and worker cleanup.
Receipt: `/private/tmp/evalsurge-measurement-accuracy-20261009.hhACtp/independent_recovery_extended_receipt.json`.
Owner receipt: `/private/tmp/evalsurge-app-quality-recovery-20261009.r4c3jk/gate-receipt.json`.

Protected reports:

- LangGraph supplemental envelope: `/private/tmp/evalsurge-app-quality-recovery-20261009.r4c3jk/langgraph-rejudge/rejudged-report.json`.
  Includes original report, recovery evaluation, lineage and preservation flags.
- OpenAI typed report: `/private/tmp/evalsurge-app-quality-recovery-20261009.r4c3jk/openai/report.json`.
- Original failed run remains under `/private/tmp/evalsurge-app-load-quality-20261009.0099be`.

Protected readable aggregate index:
`/private/tmp/evalsurge-app-quality-recovery-20261009.r4c3jk/reports.html`.
Generated on October 10 with
`uv run --frozen --no-sync python /private/tmp/evalsurge-app-quality-recovery-20261009.r4c3jk/render_summary.py`
(exit 0; initial sandboxed attempt failed uv-cache access, authorized retry
succeeded). This is a one-shot 0600 offline HTML summary inside the existing
0700 root, with escaped aggregate values, same-directory relative JSON links,
no scripts/remote assets and zero model/network calls. It is not the interactive
API report or evidence of browser/layout verification. Full linked JSON remains
protected and contains captured answers/references/rationales.

False correctness verdicts are quality findings, not failed execution. Read-only
LangGraph review found one supported policy-application error and five
reference-completeness-sensitive verdicts: the latter made policy-consistent
negative decisions but omitted a time-window qualification in a compound expected
fact. Preserve the **88%** result; changes to references/rubrics require a new
reviewed dataset/plan, not retroactive editing or rerunning to obtain passing scores.
The ten synthetic cases and 50 sampled answers do not establish general calibration
or unbiased population quality. Matching OpenAI review classified its seven false
verdicts as one supported policy-window error and six completeness-sensitive
verdicts (five on the same compound fact, one on a second implicit policy fact).
Other phrasings passed that latter case; they were not identical answers, so this
does not establish inconsistent judging of identical text. Preserve **86%**.
Successful synchronous `/api/invocations` coverage
does not establish `/responses`, App TTFT/token usage, streaming, internal traces,
memory, notebook authentication or sustainable capacity.

Both retained Apps reported `RUNNING`, compute `ACTIVE`, deployment `SUCCEEDED`
on explicit profile `e2-demo-field-eng`. Initial sandboxed checks failed
credential-cache access; authorized outside-sandbox retries succeeded without
cache/profile/fallback changes. These are metadata checks, not fresh inference.
Three sub-agent backends initially failed an unrelated workspace IP ACL;
one retry recovered.

### Measurement diagnostic, not agent inference

[The measurement record](docs/MEASUREMENT_ACCURACY.md) covers four completed
200-request localhost timing modes through production Locust, concurrency five,
at most ten dispatch seconds each. No new cloud, model or paid calls. Native
write means were 0.118/0.127 ms; paired client-minus-server mean/p95
0.676/1.595 ms. A diagnostic blocking 5 ms/write control raised the difference
to 22.692/34.527 ms and lowered achieved rate from 165.43 to 69.20 requests/sec.
This establishes sensitivity to journal stalls, not cloud-disk cost, zero
observer effect or a precise native throughput tax. The no-journal control
was noisier/slower. No production timing/journal definitions changed.

Historical real-App audit found tiny completion rows (mean 776 bytes) and five
cold `auth_ms` samples above 100 ms; that field includes initial journaling.
A 21 MB snapshot read/parse and deepcopy averaged 17.50/13.48 ms separately.
The oversized SSE parser probe was interrupted/reaped, not passed. All timing
children and the endpoint are stopped; no overlap with paid recovery occurred.
Protected evidence: `/private/tmp/evalsurge-measurement-accuracy-20261009.hhACtp`;
`FINDINGS.md` records exact commands and calibration/storage/historical receipts.
Generator-health and cloud/serverless overhead remain unverified.

### CrewAI preparation only

The approved development package source did not expose selected CrewAI 1.15.26
(resolver exit 1). An isolated alternative resolved CrewAI 1.15.23/OpenAI
2.54.0/Pydantic 2.12.5/MLflow skinny 3.16.1 with 150 packages, but was **not
installed** and has no generated hashes. The isolated environment is empty:
no actual Crew import/startup, model call or deployment. No registry bypass,
saved-wheel install, global-settings change or repository dependency/lock edit.
Changing the selected version and separate 76-attempt lease require explicit
choices. Private registry provenance must stay out of public docs, deployments
and the committed lockfile. Protected receipt:
`/private/tmp/evalsurge-crewai-preparation-20261009.g9DGi2/proxy-access-checkpoint-20261010.private.json`.

### Final evidence/documentation integration — October 10

The continuation retrieved both independent agents' completed read-only audits,
recorded OpenAI's verified 86% correctness, updated the handoff/hosted matrix/
diagnosis/ADR status and retained original failures. No extra App, agent, judge,
install, deployment, GitHub, commit or push operations were performed.

Fresh checks after integration:

- `uv run --frozen --no-sync ruff check .`: passed.
- `uv run --frozen --no-sync ruff format --check .`: **193 files already formatted**.
- `git diff --check`: passed.
- `uv run --frozen --no-sync python scripts/export_openapi.py --check`: passed.
- `uv run --frozen --no-sync openapi-spec-validator docs/openapi.json`: **OK**.
- `uv build --no-build-isolation`: wheel and source distribution built.
- `uv run --frozen --no-sync python scripts/verify_wheel.py`: packaged Python/
  REST/report/docs assets verified; local assistant metadata excluded.
- Private renderer Ruff/format, offline HTML active-content/relative-link checks
  and root/file modes (0700/0600): passed. Browser/layout was not verified.

No dependency/lock edits, clean-install test, complete controlled-provider pytest
suite, new CI or designated maintainer approval. Those remain release gates,
alongside registered trace-consuming scorer semantics and unreaped-live-child
cleanup-failure supervision. The no-inference native storage suite's **29 passes**
and the independent audit's **45 passes** remain separate from live inference.

## Evaluation-process implementation checks — October 9, 2026 (historical)

The evaluator process change is under implementation and review; this entry does
not establish completed native-storage regressions or real-model recovery.
No controlled-provider suite, CI, CrewAI inference or deployment has been run
in this resumed implementation turn.

Completed non-inference checks:

- First `uv run --frozen --no-sync pytest -q tests/test_evaluation_process_storage.py`:
  **4 failed, 3 passed, 1 warning**. All four failures occurred before worker
  execution: installed MLflow 3.16.1 explicitly prohibits decorator-scorer
  registration against SQLite. Its security gate was not bypassed. This attempt
  does not establish registered-scorer transfer or native worker completeness;
  revise the test boundary and retain registered-scorer coverage as a separate
  supported-store gate. Protected test state remains under pytest run 324.
- Follow-up of the revised native built-in registration tests: **2 failed,
  14 passed, 1 warning** in 19.77 seconds (pytest run 331). The 50-feedback
  persistence and structural trace-transfer checks passed; timeout and
  cancellation-during-writes returned the wrong safe failure code. The focused
  outside-sandbox retry (`-k 'owner_timeout or cancellation_during_actual'`)
  produced **1 failed, 1 passed, 14 deselected, 1 warning** in 3.97 seconds
  (pytest run 332): timeout still failed, so sandbox signalling alone does not
  explain it. Recovery remains held pending repair and passing regressions.
  These are deterministic native storage/ownership checks; no inference was
  stubbed and no agent/model calls occurred.
- `uv run --frozen --no-sync pytest -q tests/test_local_helper_canary_setup.py tests/test_serverless_app_target_contract.py`:
  **33 passed**. These exercise setup failures and controlled authentication/
  metadata boundaries before provider dispatch, not substituted successful
  model responses.
- `uv run --frozen --no-sync python scripts/export_openapi.py --check`: passed.
- `uv run --frozen --no-sync openapi-spec-validator docs/openapi.json`: passed.
- `uv build --no-build-isolation`: wheel and source archive built; subsequent
  `uv run --frozen --no-sync python scripts/verify_wheel.py` passed, including
  the new evaluation-process/worker/attempt modules. Rebuild after final edits.
- Bare `uv sync --locked --extra agents --group dev` rejected the unchanged
  lock under ambient index settings, as already documented in
  `docs/DEPENDENCIES.md`. Explicit public-index cached verification,
  `uv sync --locked --extra agents --group dev --offline --default-index https://pypi.org/simple`,
  passed: 190 packages resolved, 182 checked. No lock/source/hash was rewritten;
  this is not a fresh network install or dependency upgrade.

Official public PyPI metadata retrieval still failed with connection refused,
including the outside-sandbox retry. Latest-compatible release/install validation
therefore remains an explicit dependency gate, not a claimed success.

CrewAI preparation follow-up (no live test): the protected candidate now uses
actual MLflow AgentServer `/responses` models/decorators. Three native event-schema
checks and two intentional invalid-input HTTP checks passed, plus Ruff; no model
response was substituted. These ran against the existing runner dependencies
(MLflow 3.16.1/OpenAI 3.22.1/Pydantic 2.13.5), **not** a compatible CrewAI install.
Joint official-index dependency resolution failed inside and outside the sandbox
(`https://pypi.org/simple/openai/`, connection refused). There is no installed-Crew
or deployment/inference success. The recipe is explicitly legacy AgentServer
compatibility, not current DurableAgentServer coverage; its resource/traffic lease
is separate and pending. Protected receipt:
`/private/tmp/evalsurge-crewai-preparation-20261009.g9DGi2/compatibility-checkpoint.json`.

## Evaluation storage diagnosis — October 9, 2026

Using the same 50 saved real captures, native MLflow 3.16.1 storage testing
reproduced **19/50 retained scores**, 41 connection-pool warnings, 31 tag-write
failures and 31 assessment-write failures. Actual process-owned serial evaluation
retained 50/50. The final stricter fresh-process check disabled async/batch export
and retained **50 unique exact durable current-run assessments for each of two
checks**, with 100 legitimate scorer-owned native span scopes, no pool/tag/
assessment/export/refresh failures and three other warnings. Independent raw
SQLite audit confirmed exact selection membership, valid feedback and source-run
metadata. An intermediate failed property-based assertion is preserved; final
verification checks exact `mlflow.assessment.sourceRunId` metadata.

All diagnostics made zero agent/judge/network calls. These deterministic storage
presence checks are not relevance/correctness judging, fixture inference or
successful real-model evaluations. LangGraph's real load below stays successful,
its historical quality run stays incomplete, and OpenAI's larger run stays not
started. Original native exception details are unavailable; the reproduced shared
store mechanism does not prove the cause of every original gap.

Final command exited zero (historical command; do not replay into existing store):

```bash
uv run --frozen --no-sync python /private/tmp/evalsurge-eval-serial-verified-20261009.AdfokN/run_probe.py
```

Official MLflow docs were retrieved through `llms.txt`; installed source verifies
nested SQLite sessions, workers and exporter initialization. Native MLflow does
not read EvalSurge ContextVars. No core evaluator fix, dependency change, new paid
call, deployment, commit or push occurred. A proposed process-ownership ADR needs
designated maintainer review. See [the diagnosis record](docs/EVALUATION_STORAGE_DIAGNOSIS.md)
for commands, artifacts and proposed new bounds.

Post-documentation static checks passed: `uv run --frozen --no-sync ruff check .`,
`uv run --frozen --no-sync ruff format --check .` (187 files already formatted),
and `git diff --check`. No pytest/controlled-provider suite or CI was triggered;
its provider-substitution exception still requires explicit approval. No claim
of general core-fix regression coverage follows from these storage diagnostics.

At this diagnosis checkpoint the proposed recovery gate was not yet authorized
or executed; the subsequent user approval is recorded in `docs/SESSION_HANDOFF.md`,
and execution remains held for implementation verification. Its bounds: rejudge saved
LangGraph captures (300 judge attempts, zero agent calls), then OpenAI App load
and both judges (501 agent + 302 judge attempts). New ceiling 1,103, separate from
the stopped lease and earlier 552 attempts. Preserve the original failed reports;
LangGraph recovery is supplemental judging, not fresh load or forced passing
verdicts. Both App and local-hosted paths share the affected evaluator.

## Approved App load with captured-answer evaluation — October 9, 2026

The user separately approved a larger, sequential two-App lease on the exact
`e2-demo-field-eng` profile/workspace `1444828305810485`. Per App: concurrency
five; stop at 180 dispatch seconds or 500 measured attempts; one excluded
inference probe; no additional warmup/healthcheck inference. Existing deployments
and their synchronous `/api/invocations` contract were unchanged. Agent inference
used `system.ai.gpt-oss-120b`, <=512 output tokens, zero model/target retries and
a 40-second benchmark-attempt deadline. The local unified SDK/Locust runner used
ten shared synthetic refund-policy cases with authoritative references.

Evaluation explicitly selected `relevance` and `correctness`, at most 50 captured
answers per scorer, seed 42. The frozen judge was `databricks-gpt-5-4-mini`, <=2048
output tokens, 60-second timeout, two quality retries and zero readiness retries.
No automatic planning, dataset-generation model, fallback or target reinvocation
was used. The maximum lease was 1,002 agent attempts plus 604 judge attempts
(1,606 physical model transport attempts), with stop-on-execution-failure.

One-use live command (exit **1**, preserving the partial quality result):

```bash
uv run --frozen --no-sync python /private/tmp/evalsurge-app-load-quality-20261009.0099be/run_load_quality.py --execute-approved-load-quality-lease
```

**Do not rerun that command.** LangGraph load completed, native evaluation
returned partial evidence, and the harness stopped. OpenAI Agents was **not
started** under this lease; earlier successful one-measured-call canaries below
remain separate evidence. Unused allowance is not permission for replay/fallback.

| Observation | LangGraph App result |
| --- | --- |
| App / run ID | `agent-bricks-es-lg-1008` / `2b28bf04-bc4c-40f7-95f4-8a3beedebdc5` |
| Measured successful requests / load errors | 500 of 500 / 0 |
| Configured / observed peak HTTP concurrency | 5 / 5 |
| Dispatch / elapsed including drain | 118.61 / 119.82 seconds |
| Successful-only latency p50 / p95 / p99 | 1154.21 / 1171.63 / 2161.67 ms |
| Successful throughput, including drain | 4.173 requests/second |
| Inference / both judge readiness checks | passed / passed |
| Lifecycle / evaluation execution | `completed_with_gaps` / `completed_with_errors` |
| Relevance selected / correlated scores | 50 / 13, all 13 available verdicts true |
| Relevance gaps | 1 `evaluation_backend_error`, 36 `assessment_missing` |
| Post-load correctness | skipped by fail-fast after partial relevance |

The 13/13 available passing scores **are not complete quality coverage** or a
50/50 pass. The source path in `benchmark_agents/evaluator.py` marks a scorer
partial when scored != selected, then breaks on `fail_fast=True`. This was not
a confirmed evaluation-wide thrown exception. The generic errored assessment
does not preserve the exact underlying exception class; private harness logging
suppressed warnings. The retained evidence cannot establish a specific locking,
autotracing, authentication or judge-response cause.

App before/after counters establish **501 actual model HTTP attempts / 501
completed Responses**, including the excluded probe, zero model HTTP errors and
no remaining active handlers. Judge transport telemetry records **51 real HTTP
attempts**, all HTTP 200: two readiness and 49 quality. Total observed model
transport attempts were **552**, within the approved bound. These observations
are not billing receipts; HTTP 200 does not establish a parsed, persisted verdict.

Independent read-only saved-evidence review confirmed incomplete native MLflow
retention/materialization: 19 trace records, 16 request-correlation tags, 15
relevance assessments including readiness and an error, and one correctness
readiness assessment. Native evaluation persistence/correlation is the area to
investigate, not a proven SQLite-locking root cause. No additional model calls
were made during diagnosis. Do not modify original evidence or invent missing
assessments; diagnosis/fix and any quality-only rerun require separate scope.

Typed status/result/waited/retrieved reports agreed; all 500 measured captures,
ten cases and five request pages were correlated, with the probe excluded. SDK
context cleanup completed; recorded worker PIDs 75541 and 75414 were absent.
No deployment, sizing, store, credential, dependency or Git mutation was made
by live execution. Apps/stores remain retained and may incur hosting charges.

Protected evidence root: `/private/tmp/evalsurge-app-load-quality-20261009.0099be`.
[Readable index](/private/tmp/evalsurge-app-load-quality-20261009.0099be/reports.html),
[LangGraph report](/private/tmp/evalsurge-app-load-quality-20261009.0099be/langgraph/report.html)
and [typed JSON](/private/tmp/evalsurge-app-load-quality-20261009.0099be/langgraph/report.json)
are private offline exports, not hosted reports. The index labels OpenAI not run;
HTML displays selected/scored/error/missing coverage and escaped answers/rationales.
Directories are 0700 and report exports 0600; do not publish or commit them.

Offline-only report preparation used the following commands, all exit **0**:

```bash
uv run --frozen --no-sync ruff format /private/tmp/evalsurge-app-load-quality-20261009.0099be/render_reports.py
uv run --frozen --no-sync ruff check /private/tmp/evalsurge-app-load-quality-20261009.0099be/render_reports.py
uv run --frozen --no-sync python /private/tmp/evalsurge-app-load-quality-20261009.0099be/render_reports.py
```

The renderer used only saved files and made zero network/model calls. This is not
browser/layout validation. An offline standard-library HTML parser verified both
exports: no scripts, event handlers, remote assets or external links; all five
local links resolved; all 50 selected assessment details were present; incomplete
coverage/correctness-skipped/OpenAI-not-run labels matched the saved evidence.
Recursive permission validation passed (directories 0700, files 0600).
`uv run --frozen --no-sync ruff check .`,
`uv run --frozen --no-sync ruff format --check .` (185 files) and
`git diff --check` passed after the documentation changes. These static/offline
checks used no controlled or real inference and did not trigger CI.
One closed-loop concurrency level does not establish
sustainable capacity. App TTFT/token usage, internal target profiling, memory,
notebook execution and judge calibration remain unverified. The full controlled-
provider suite/CI was not run or triggered by this lease; no inference was stubbed.

## Renewed deployed-App real-model canaries — October 9, 2026

The user explicitly approved **four physical model calls total**, not the larger
52-call matrix. The App workstream relinquished ownership with zero calls used;
root then owned the gate exclusively. The preliminary wrapper preparation was
interrupted before any inference; no failed/live run was replayed. A no-network
dry run confirmed the bound before execution.

Command (outside the sandbox for the selected profile's secure OAuth access):

```bash
uv run --frozen --no-sync python /private/tmp/evalsurge-app-canaries-20261009.wQEzfS/run_gate.py --execute-approved-four-call-gate
```

Exit **0**. The current unified native-async direct SDK bound
`Agent.databricks_app(..., profile="e2-demo-field-eng")` outside `RunCreate`; the
local machine generated load against each existing native DurableAgentServer
App in workspace `1444828305810485`. Framework/model execution remained inside
the deployed App. Both used `system.ai.gpt-oss-120b`, explicit
`/ai-gateway/mlflow/v1/responses`, <=512 output tokens, low reasoning,
`store=False`, 30-second model transport, 35-second handler and 40-second
benchmark attempt limits, zero model/target retries. Each run had one excluded
probe and one measured invocation, concurrency one, ten-second dispatch ceiling,
120-second wait ceiling and evaluation off. There was no additional model
healthcheck, warmup, fallback, fixture completion, planner or judge call.

The public App boundary was `databricks-agentbricks==0.4.0`
DurableAgentServer compatibility through synchronous `/api/invocations`.
The internal model's `/ai-gateway/mlflow/v1/responses` is a different boundary;
these canaries do not establish public App `/responses` coverage.

| Framework / deployed App | Run ID | Preflight / measured completion | Measured latency | Protected report |
| --- | --- | --- | --- | --- |
| LangGraph / `agent-bricks-es-lg-1008` | `86ab5671-d173-423e-932d-691f8570ee12` | passed / 1 of 1, zero errors | 1458.41 ms | [JSON](/private/tmp/evalsurge-app-canaries-20261009.wQEzfS/langgraph/report.json) |
| OpenAI Agents / `agent-bricks-es-oai-1008` | `04f77c8c-0bd2-4e77-9c60-dd44d4e0e33e` | passed / 1 of 1, zero errors | 1467.40 ms | [JSON](/private/tmp/evalsurge-app-canaries-20261009.wQEzfS/openai/report.json) |

Both terminal results were `completed`, `performance=complete`, `quality=off`,
with complete measurements, configured/observed concurrency one and exactly one
measured row per report. Excluded probe latencies were 2787.58 / 2821.81 ms.
These single measured latencies are wiring observations, not a framework ranking,
stable percentiles, sustainable capacity or a passing quality verdict.

Selected-origin active identity and the previously source-verified immutable
deployments matched before traffic; `/status` verified exact runtime controls
and identity before and after each run. Each App's process-local counters changed
from zero to **2 handler attempts / 2 model HTTP attempts / 2 guarded completed
Responses**, zero errors and zero active handlers. Thus this gate consumed exactly
**4 actual model attempts / 4 completed Responses**. Those counters are transport/
completion evidence, not provider billing receipts. No deployment or resource
configuration changed; native Runtime invocation persistence is an expected target
side effect, not configured conversation memory. Durable store contents/recovery
were not independently validated by this gate.

Typed status/result IDs and lifecycle agreed; full waited/retrieved report run
models equaled the separate typed result. Both SDK contexts closed. Full status,
result, waited/retrieved reports and per-App/gate receipts are retained privately
under `/private/tmp/evalsurge-app-canaries-20261009.wQEzfS`; captures were not
printed or committed. Nonstreaming App decoding reported **no TTFT/first-event
timing and zero token-usage coverage**; provider-present usage was not promoted
into benchmark metrics. Tracing/profiling and answer/trace-aware evaluation were
off. No cancellation, negative fail-fast, remote-API, unchanged sample `main()`,
CrewAI or serverless notebook coverage is established by these canaries.

### Independent local evidence and handoff audit — October 9, 2026

Three parallel read-only reviews checked saved canary evidence, changed harness
source/regressions and checkpoint documentation. No new cloud/model calls, tests,
deployment, dependency resolution or GitHub actions were performed. This agent
review is not designated maintainer approval.

For each framework, the separate result matched both waited and retrieved report
`run` models; full waited/retrieved reports matched, and status IDs/phases agreed.
All four attempt journals (two probes and two measured attempts) contained exactly
one start and one successful completion each. Retained App counter deltas confirm
four physical model attempts/completed Responses, with no errors or active handlers.
The SDK contexts closed. The exact local worker check was:

```bash
ps -p 27225,27122,27274,27236 -o pid=,comm=
```

After approved local `ps` escalation, it returned exit **1** with no rows: none
of the four recorded workers existed at the audit. Every evidence directory was
0700 and captured evidence/receipt files were 0600. The gate script was 0644 inside
the protected 0700 root; no captures or credentials were printed or committed.

Documentation corrections distinguish the completed App canaries from the
pending sample/API/cancel/fail-fast matrix, scope earlier pause/readiness records
historically and constrain the proposed CrewAI environment to its verified
`openai>=2.30.0,<3` metadata. No package was installed. Source review found no
blocking regression in the two diagnostic harness changes; worker OAuth remains
unresolved. Fresh `uv run --frozen --no-sync ruff check .`,
`uv run --frozen --no-sync ruff format --check .` (**185 files**) and
`git diff --check` passed. The earlier **92** focused no-inference test result
was not rerun; the full controlled-provider suite and CI remain unrun for this
checkpoint. Dependencies/lockfile and HEAD remain unchanged; no commit or push.

The four-call approval is exhausted. No larger matrix was started; its proposed
48 additional positive calls and separately labeled zero-model failure checks
require new explicit consent. The actual serverless worker-OAuth blocker and
CrewAI dependency-index blocker remain unchanged. No full suite, CI, dependency
update, commit or push was performed for this gate.

## Read-only resumption and harness fixes — October 9, 2026

This section records the checkpoint before the separately approved canaries above.

Resumed from clean published HEAD `a4e9408c6d642dd5e20d4545e638f08f167d3d49`.
Two focused diagnostic-harness fixes are implemented; no core SDK/API/auth,
Locust engine, evaluation, dependency or lockfile change was made. No commit,
push, new full controlled-provider suite or remote CI was performed.

- Local canary optional distribution/source/app setup now occurs after the
  initial protected receipt and inside safe failure handling. Setup exceptions
  retain class/phase, zero-call evidence and no fabricated run, at mode 0600 in
  a 0700 directory. Existing receipts stay unchanged; storage failures propagate
  when evidence cannot safely be persisted. New regression before implementation:
  **5 failed / 1 passed**; after implementation: **6 passed**.
- The prepared serverless harness checks the exact profile workspace before
  OAuth retrieval or App discovery. SDK construction itself may initialize
  metadata/authentication. Fixed safe blocker codes distinguish profile conflicts,
  driver auth/OAuth, discovery, deployment origin and independent worker OAuth.
  The unchanged core guards and profile-only binding remain. Six new regressions
  failed before implementation; focused final file: **27 passed**. A separate
  read-only agent review found no blocking issue; designated maintainer review is
  not implied. Worker-portable OAuth and live notebook coverage remain blocked.

Combined regression command:

```bash
uv run --frozen --no-sync pytest -q tests/test_local_helper_canary_setup.py tests/test_local_runner_http_journey_contract.py tests/test_real_framework_contract.py tests/test_serverless_app_target_contract.py
```

**92 passed in 1.44 seconds.** Exact boundary: native schemas/construction/source
contracts, actual receipt persistence, exception-only setup failures, controlled
SDK metadata/authentication, and deliberate pre-provider rejection. The SDK tests
block outbound Requests HTTP. No real profile, cloud request, framework response,
model completion or successful agent inference was substituted by these tests.
Earlier real local-model results were not repeated.

Fresh read-only App evidence is separate: CLI 1.17.0, explicitly selected
`e2-demo-field-eng`, exact workspace ID `1444828305810485` and active identity
verified. Both retained Apps were RUNNING/ACTIVE with authenticated `/status` 200
on the previously recorded immutable deployments. Downloaded source snapshots
matched all four retained handler/wrapper/guard/wheel hashes; exact model resource
and <=512-output-token/zero-model-retry controls matched. Before/after process-local
handler/model counters were all zero. No model calls, redeployment, store changes
or fresh live benchmark occurred. Process counters are not billing receipts.
Receipt: `/private/tmp/evalsurge-app-ready-20261009.HLxSpg/readiness-receipt.json`.
At this read-only checkpoint, renewed bounded consent was required. The separately
approved four-call gate subsequently completed above, and its approval is exhausted.

The official CrewAI 1.15.25 wheel is reachable and SHA256-verified:
`aea1282a2b5bf966e1a52a2937cc27e83bbb7daa5eeeb8104cf563c8ac3a8be6`.
Its metadata requires Python >=3.10,<3.14, exact `crewai-core`/`crewai-cli` 1.15.25
and OpenAI >=2.30.0,<3. An isolated public-index `uv pip install --dry-run
--no-build` failed to fetch `opentelemetry-api` metadata with connection refused,
both sandboxed and after escalation. No install, source build, version substitution
or lock rewrite followed. Wheel access is not dependency/inference success.
Receipt: `/private/tmp/evalsurge-crewai-wheel-20261009.CzZe3b/dependency_receipt.json`.

Final integration checks (installed environment; no dependency sync):

```bash
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync python scripts/export_openapi.py --check
uv run --frozen --no-sync openapi-spec-validator docs/openapi.json
uv build --no-build-isolation
uv run --frozen --no-sync python scripts/verify_wheel.py
git diff --check
```

All passed: Ruff lint, **185 files already formatted**, unchanged OpenAPI snapshot,
independent schema validation, wheel/source build, packaged assets/private-metadata
exclusion and whitespace checks. OpenAPI export emitted the installed MLflow skill
hint only; no tracing behavior changed. No full-suite, fresh dependency audit,
remote CI, browser or live inference claim follows from these checks.

## Endpoint-first helper and evidence follow-up — October 8, 2026

Implemented against pushed baseline `2276c3b4d6fa9943544f988df4e5ed658ad79365`;
this is an implementation checkpoint, not a fully live-validated release. Proposed ADR 0012 records the contract
before behavior changes; designated maintainer approval remains outstanding.
The unified SDK, `/v1`, existing protocol choices and sole Locust engine remain.

### Paused publication checkpoint — October 8, 2026

The user requested that App load tests stop and that the implementation and its
documentation be preserved for resumption on October 9, 2026. The App workstream
confirmed **zero of its 52 additional physical model calls were used**, no new
scenario started and no invocation/subprocess remained in flight. No App or
Runtime Store was stopped or deleted; retained resources can continue incurring
hosting/storage charges. This checkpoint does not authorize a scheduled resume.

The LangGraph and OpenAI Agents Apps reached RUNNING with authenticated `/status`
200 and exact workspace/principal checks. Their ready deployment IDs are
`01f1c38db3f5165b98332e7c16cb1108` and
`01f1c38db4281b698aaac4c5aa8e6761`. Handler/model counters were zero at that
readiness read; they were not refreshed after the pause. Resources-only model
permission updates, failed startup revisions and corrected source hashes are
recorded in [the hosted-journey record](docs/HOSTED_JOURNEY_VALIDATION.md#corrected-native-app-readiness--october-8-2026-edt).
Readiness is not a successful inference/load test. CrewAI remains dependency-
blocked and undeployed; no downgrade or stand-in was used.

The corrected environment-5 serverless prerequisite run was
`526298221857181`, task `972949342784427`: Python 3.12.3, Databricks SDK 0.146.0.
Notebook-driver runtime OAuth, exact selected workspace/active identity,
loopback sockets and POSIX locking/fsync passed. Independent subprocess runtime
OAuth failed with `ValueError`; **zero inference calls** occurred and no deployed
App was tested. Jobs `SUCCESS` does not override the failed worker-auth check.
The earlier failed/prerequisite receipts below remain historical evidence.

[The serverless runner status](docs/SERVERLESS_RUNNER_STATUS.md) distinguishes
calling an externally hosted API from hosting the API/Locust in the notebook.
The latter still needs reviewed independently refreshable worker authentication;
starting FastAPI does not fix that boundary. No token copying, trust-guard bypass,
new credential identity or classic-compute fallback was implemented.

Read-only helper/evidence/serverless reviews found no blocker for preserving this
checkpoint. They do not replace designated maintainer review. Two dormant harness
follow-ups remain before future execution: save a safe local canary receipt when
an optional framework is missing, and check the notebook profile's exact workspace
before App discovery while separating safe auth/discovery diagnostics.

Publication checks use the installed environment with `--frozen --no-sync`.
`pyproject.toml` and `uv.lock` are unchanged; no dependency sync/update or new
upstream-latest claim is made. An incidental mirror-URL rewrite with unchanged
package versions was separately preserved and reversed before building. The
full controlled-provider suite and new remote CI were not authorized here;
the checkpoint commit uses `[skip ci]` for its push-triggered workflow. No
remote repository/workflow settings were changed. The scheduled CI definition
remains present and was not changed by this pause.

See [the session handoff](docs/SESSION_HANDOFF.md) for scope, retained evidence,
safe resumption order and publication verification. The following historical
subsections retain their original traffic and verification boundaries.

Final no-inference publication checks:

```bash
uv run --frozen --no-sync pytest -q tests/test_runner_target_examples.py tests/test_local_runner_http_journey_contract.py tests/test_real_framework_contract.py tests/test_serverless_journey_contract.py tests/test_serverless_app_target_contract.py tests/test_hosted_journey_harness.py tests/test_agent_integration_docs.py tests/test_simple_examples.py::test_every_user_example_has_an_explicit_integration_contract
uv run --frozen --no-sync pytest -q tests/test_hosted_evidence_contract.py tests/test_evidence_cli.py tests/test_probe_evidence_failure.py
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync python scripts/export_openapi.py --check
uv run --frozen --no-sync openapi-spec-validator docs/openapi.json
uv build --no-build-isolation
uv run --frozen --no-sync python scripts/verify_wheel.py
uv run --frozen --no-sync python scripts/verify_remote_install.py --offline
git diff --check
```

- Focused source/schema/native-construction/storage and deliberate pre-provider
  rejection checks: **130 passed in 3.30 seconds**. Independent presentation/schema
  and deliberate pre-judge evidence-failure checks: **22 passed in 0.07 seconds**.
  No model completion, target traffic or judge call was substituted or executed.
- Ruff lint passed; format check reported **184 files already formatted**.
- OpenAPI equality and independent schema validation passed. A read-only Python
  comparison against `git show 2276c3b:docs/openapi.json` confirmed **all seven
  `/v1` paths and 28 reachable schemas unchanged**. Additive v2 strict-client
  compatibility limits remain documented in `docs/API_REVIEW.md`.
- Wheel/source builds and archive assets/private-metadata checks passed. Offline
  isolated base-wheel installation checked its 11 dependency packages, compatible
  installation, public evidence DTOs, lazy server imports, CLI and remote lifecycle
  metadata. That lifecycle metadata is simulated; it is not model inference or
  a real hosted service. The expected `VIRTUAL_ENV` mismatch warning describes the
  deliberate isolated environment. No main lockfile/dependency changes occurred.
- Whitespace checks passed. No new full-suite/remote-CI result, fresh upstream
  dependency audit, live calls or successful serverless/App inference is claimed.
  Build/asset checks were repeated after these documentation edits so the source
  distribution includes the final record.

### Fresh local HTTP helper matrix — October 8, 2026

The latest real helper and public HTTP request were exercised in **12 new local
scenarios**: LangGraph/OpenAI Agents × native-async direct SDK/authenticated local
REST × normal load/active cancellation/intentional fail-fast. Local machine was
the load-generator location and the real agent's HTTP hosting location. A
serverless notebook was not used to host an agent, and these local results do
not establish deployed-App or notebook-runner coverage. The exact public
`examples/journeys/local_runner_http_target.py:request()` object was imported for
both SDK modes; that first matrix did not execute its synchronous CLI/`main()`
wrapper. The separate entrypoint checks below now establish that path.

The eight positive runs used the explicitly approved `e2-demo-field-eng` profile,
`https://e2-demo-field-eng.cloud.databricks.com`, `system.ai.gpt-oss-120b`, the
explicit `/ai-gateway/mlflow/v1/responses` route, low reasoning and `store=False`.
Each used five closed-loop users, five measured attempts plus one excluded probe,
a ten-second dispatch ceiling, 512 maximum output tokens per model call, a
30-second model transport timeout, 35-second handler deadline and 40-second
benchmark attempt timeout. Model retries were zero; the actual native compiled
LangGraph or OpenAI Responses Agent/Runner executed, without canned responses,
tools, fallback, planner or judge calls. Evaluation was off. Each positive run
made exactly six outbound model requests and retained six guarded completed
Responses: **48 model attempts / 48 completed Responses** in this new batch,
separately from the earlier four local canary calls. Paid traffic was serialized,
the allotted 48-call ceiling was reached exactly, and the lease was released.

Normal load completed before the ten-second ceiling because the five-attempt cap
was reached. All normal runs had observed peak concurrency five, five successes,
zero errors and token-usage coverage 1.0. These are functional smokes, not
continuous ten-second loads, stable tail-latency comparisons or sustainable
capacity. Nonstreaming JSON supplied no TTFT/first-event timing; none was invented.

| Framework / execution | Run ID | Successful measured / errors | p50 / p95 latency (ms) | Protected JSON report |
| --- | --- | --- | --- | --- |
| LangGraph / native-async direct | `f1dc050b-ce10-4cf5-8695-d1ed2ed7dcf3` | 5 / 0 | 670.85 / 816.57 | [Report](/private/tmp/evalsurge-local-http-lg-load-direct-20261008.Afigzl/typed-report.json) |
| OpenAI Agents / native-async direct | `e28ebff0-b27c-4529-8962-635d31be8a4b` | 5 / 0 | 547.65 / 746.56 | [Report](/private/tmp/evalsurge-local-http-oai-load-direct-20261008.ilClNi/typed-report.json) |
| LangGraph / typed remote → local API | `cded6670-af5d-455b-ba69-4fe0c62c3a72` | 5 / 0 | 559.45 / 584.19 | [Report](/private/tmp/evalsurge-local-http-lg-load-api-20261008.gDQhQg/typed-report.json) |
| OpenAI Agents / typed remote → local API | `86e7d920-6b5f-4d66-bf21-b6cf69f8a6f8` | 5 / 0 | 593.41 / 690.98 | [Report](/private/tmp/evalsurge-local-http-oai-load-api-20261008.8c4Mmv/typed-report.json) |

Each of the four separately bounded cancellation checks observed `running` plus
five active measured ASGI handlers before receiving `cancellation_requested`.
All five measured calls subsequently completed and drained with zero errors,
while lifecycle/report status remained `cancelled`. All five had already been
dispatched at the small attempt cap. This is verified active lifecycle
cancellation/drain, **not** evidence of suppressing an unissued backlog or aborting
upstream model work/costs. Cancellation cannot roll back tools; these samples
had no tools. No call was replayed or budget increased to improve that claim.

| Framework / execution | Active-cancel/drain run ID | Terminal status | p50 / p95 measured latency (ms) | Protected JSON report |
| --- | --- | --- | --- | --- |
| LangGraph / native-async direct | `8204f883-cf83-45f5-ae6b-594351e75e69` | `cancelled` | 561.22 / 627.09 | [Report](/private/tmp/evalsurge-local-http-lg-cancel-direct-20261008.pVfQe8/typed-report.json) |
| OpenAI Agents / native-async direct | `41cd0727-d52a-454b-ae63-f611e968a0f7` | `cancelled` | 588.71 / 616.33 | [Report](/private/tmp/evalsurge-local-http-oai-cancel-direct-20261008.JzDwYk/typed-report.json) |
| LangGraph / typed remote → local API | `461c9bb3-8b11-4a06-907d-11b0ac95d339` | `cancelled` | 588.22 / 694.73 | [Report](/private/tmp/evalsurge-local-http-lg-cancel-api-20261008.leY60l/typed-report.json) |
| OpenAI Agents / typed remote → local API | `99e2bea1-9d47-4294-879d-f8b91d8ec1dd` | `cancelled` | 569.14 / 576.49 | [Report](/private/tmp/evalsurge-local-http-oai-cancel-api-20261008.rAbn7G/typed-report.json) |

Four negative checks deliberately added an unsupported input field to the real
handler. Its native input validation rejected before any provider request.
Each retained one failed probe with `target_http_error`, terminal `failed`, load
`skipped`, zero measured rows and **zero outbound/completed model calls**. These
are separately reported no-inference fail-fast checks, not model success.

| Framework / execution | Intentional fail-fast run ID | Protected typed failure report |
| --- | --- | --- |
| LangGraph / native-async direct | `1d8df9c7-4adf-4d10-afd9-c42fe98ca4e2` | [Report](/private/tmp/evalsurge-local-http-lg-failfast-direct-20261008.HkuEmE/typed-report.json) |
| LangGraph / typed remote → local API | `faf73da9-b3e6-4e73-880f-5e5c36252526` | [Report](/private/tmp/evalsurge-local-http-lg-failfast-api-20261008.Fk5CSt/typed-report.json) |
| OpenAI Agents / native-async direct | `6950bf7e-e59a-4ebf-b839-4a4f0fa4caf9` | [Report](/private/tmp/evalsurge-local-http-oai-failfast-direct-20261008.CPI66G/typed-report.json) |
| OpenAI Agents / typed remote → local API | `b03ad02e-3c64-4c99-869b-46bf6517ef98` | [Report](/private/tmp/evalsurge-local-http-oai-failfast-api-20261008.P8tykh/typed-report.json) |

All 12 scenarios verified terminal identifiers, independent phases and full typed
status/result/waited-report/retrieved-report parity. Five-row normal/cancellation
report pages excluded the preflight; failure pages had zero measured rows. Every
SDK context, native agent lifespan and listener closed. API modes additionally
verified missing-key HTTP 401, authenticated typed retrieval, HTTP 200 for the
static report shell, and API lifespan/listener cleanup. The shell fetch is not
browser-rendering evidence. Full typed reports and content-free receipts remain
mode 0600 in private validation-machine directories, not committed artifacts;
the loopback servers have closed, so no dead loopback report URL is advertised.

[The protected matrix summary](/private/tmp/evalsurge-local-http-matrix-summary-20261008.ueOqkq/summary.json)
lists all 12 receipt/report paths, counters, source identities and file modes.
The current metadata classifier confirmed all 12 retained passes without
further inference or rewriting original receipts. The original failed LangGraph
cleanup canary and zero-inference startup failure remain unchanged. New local
success does not relabel either old failure or establish current App readiness.

Exact tested source SHA256:

- `examples/real_framework_agent.py`:
  `300f9771e145156f3ba36385f31878a26e9fa34b3a43e2c897fa16fa2d236dc0`.
- `examples/journeys/local_runner_http_target.py`:
  `806adbf0fb9d4959202ba596308bd5c30374c8090770fef63520dd22d7569a85`.

Installed environment: Python 3.12.13, LangGraph 1.2.12, OpenAI Agents 0.22.3,
OpenAI 3.22.1, Databricks SDK 0.146.0, MLflow 3.16.1 and Locust 2.46.6.
No new dependency, deployment, notebook upload, credential/profile change,
commit or push occurred in this local workstream. CrewAI's exact dependency
blocker and App/serverless gates remain separate. Evaluation, trace correlation,
memory, streaming and synchronous CLI wrapper coverage are not claimed here.

Actual live commands used the module
`scripts.validation.local_runner_http_target_journeys` with the framework,
execution, scenario and fresh `--artifact-dir` corresponding to each row above.
All selected `--profile e2-demo-field-eng --workspace-host
https://e2-demo-field-eng.cloud.databricks.com --model system.ai.gpt-oss-120b
--api mlflow-responses --live`; only `load`/`cancel` commands added
`--accept-paid-traffic`. They were executed individually with
`uv run --frozen --no-sync python -m`, not as an unbounded/retrying matrix script.
The exact per-run selections and safe outcomes are retained in each `receipt.json`.

Focused no-inference verification (configuration/status metadata, native
constructors and intentional pre-provider rejection; no provider completions):

```bash
uv run --frozen --no-sync pytest -q tests/test_local_runner_http_journey_contract.py tests/test_real_framework_contract.py
uv run --frozen --no-sync ruff check scripts/validation/local_runner_http_target_journeys.py tests/test_local_runner_http_journey_contract.py examples/real_framework_agent.py tests/test_real_framework_contract.py
uv run --frozen --no-sync ruff format scripts/validation/local_runner_http_target_journeys.py tests/test_local_runner_http_journey_contract.py
```

Result: **59 passed in 0.95 seconds**; Ruff lint/format passed. No controlled
provider-completion full suite or new CI ran as part of this fresh local matrix.
See [the hosted-journey record](docs/HOSTED_JOURNEY_VALIDATION.md#completed-local-runner--http-target-matrix--october-8-2026)
for the same hosting/runner and evidence boundaries.

### Public synchronous HTTP entrypoints — October 8, 2026

Executed the unchanged public `examples/journeys/local_runner_http_target.py`
child script against the actual latest LangGraph and OpenAI Agents helper,
using private working directories for its fixed relative artifact path. Both
exited zero, printed native typed `Report` JSON, completed one excluded probe
and five measured successes with zero errors, reached peak concurrency five,
and closed agent lifespans/listeners, SDK storage locks and worker processes.
The same approved profile/workspace, GPT-OSS model, MLflow Responses route,
512-output-token ceiling and zero retry controls remained in force. Evaluation
was off: no planner, judges, tools, memory, fixtures or fallback.

- LangGraph run `bea314c3-fc3f-4830-8ce6-29e6b2a3381c`: p50/p95 588.81/597.09 ms;
  [protected report](/private/tmp/evalsurge-local-http-main-20261008.1EGljR/langgraph/typed-report.json).
- OpenAI Agents run `699fb8bc-b737-4339-a2d5-b32fad798ef8`: p50/p95 556.50/602.17 ms;
  [protected report](/private/tmp/evalsurge-local-http-main-20261008.1EGljR/openai-agents/typed-report.json).

Each made exactly six outbound/completed Responses, **12 / 12** in this new
batch, **60 / 60** with the preceding local matrix, separately from four earlier
canary calls. Source identities stayed unchanged. These five-attempt smokes are
not sustained capacity, robust tail-latency, App or notebook validation. No
failed paid preflight was replayed and no source code was changed to obtain a pass.

### Fresh journey preparation checkpoint — October 8, 2026

This section retains the pre-execution preparation state. The user subsequently
approved the three proposed App names and explicitly narrowed notebook execution
to **serverless only**, deferring classic compute. New local receipts are recorded
in [the short-smoke checkpoint](docs/HOSTED_JOURNEY_VALIDATION.md#current-short-smoke-scope-and-fresh-evidence):
OpenAI Responses canary passed with two real completed calls and cleanup;
LangGraph's two real calls/retrieval passed but its initial agent cleanup failed.
No claim of new App or notebook inference follows from those local passes.
The first new zero-inference serverless prerequisite retained a constructor
`TypeError` (run `166927894022579` / task `585536860269`); corrected source uses
native `Config` and a positive metadata retry window. No planner/judge calls
are authorized in this short load-only pass.

Three parallel workstreams prepared local real-framework handlers, native App
resources and notebook checks. This checkpoint includes **zero new target/model,
planner or judge calls**. No App/Runtime Store/cluster/Job was created, started,
deployed or deleted; no notebook was uploaded. No profile, credential-storage
policy, dependency lockfile or Git publication was changed.

Secure elevated metadata reads with the existing `e2-demo-field-eng` profile
succeeded after sandboxed reads reported a credential-cache error. Reauthentication
and plaintext auth storage were not needed. The refreshed workspace had 233 Apps;
none matched EvalSurge/test-eval-ram or the three proposed new native names:
`agent-bricks-es-lg-1008`, `agent-bricks-es-oai-1008`,
`agent-bricks-es-crew-1008`. No eligible current-user-owned or EvalSurge-named
classic compute was found. These are resource-discovery observations, not live
deployment evidence or authorization to select unrelated resources.

Added `examples/real_framework_agent.py` with actual LangGraph, native OpenAI
Responses/Runner and prepared native CrewAI handlers. The failed GPT-OSS Chat
Completions receipt remains failed. A customer-owned HTTPX response hook checks
raw `completed` status before Agents discards it; native framework converters
are unchanged. Missing native usage remains absent. Target retries are zero,
request state is isolated, and the example supplies no traces, memory or TTFT.
Model transport is 30 seconds; total handler deadline is 35 seconds, so a
30-second runner timeout does not prove upstream abortion. The local profile
factory is not a native App deployment entrypoint.

CrewAI is uninstalled and unexecuted. Stable 1.15.25 with OpenAI 3.22.1 in a
separate Python 3.12 environment is a proposed dependency combination, not a
resolved/tested lock. Real model canaries, new App/store creation, exact overall
traffic budgets, classic compute and portable notebook-worker OAuth still need
concrete confirmation. See [the retained matrix](docs/HOSTED_JOURNEY_VALIDATION.md).

Fresh read-only task output for run `584248337638691` / task `1003312814916440`
shows `No Experiment with id=1 exists` during ASGI startup, then startup failure
and kernel exit 3. Installed Uvicorn source uses exit 3 for startup failure; this
explains the retained failure sequence, not a successful live notebook fix.
The notebook harness now checks terminal phases and full result/report parity
for six direct/remote scenarios, with bounded prerequisite HTTP/retry settings.
It still does not establish the latest helper, CrewAI or notebook→App coverage;
driver runtime OAuth is not worker-portable merely by inheriting environment.

Final focused command:

```bash
uv run --frozen --no-sync pytest -q tests/test_real_framework_contract.py tests/test_serverless_journey_contract.py tests/test_hosted_journey_harness.py tests/test_agent_integration_docs.py tests/test_simple_examples.py::test_every_user_example_has_an_explicit_integration_contract
```

**87 passed in 3.66 seconds.** These are pure configuration/status metadata,
native client/framework construction, deliberate pre-provider rejection,
local storage/startup and documentation checks. The guard checks use status-only
HTTPX objects and headers, not fabricated model answers/provider completions.
They are not successful inference. Earlier isolated notebook/harness checks
also passed: **44 in 2.52 seconds**. Repository-wide Ruff lint/format and
`git diff --check` passed (172 formatted Python files).

No new full-suite run, OpenAPI regeneration or package rebuild is claimed for
this subsequent preparation checkpoint; the earlier 921-test/full release-gate
results below predate the new example and these notebook checks. Working-tree
changes remain uncommitted and unpushed, with unrelated user changes preserved.

### Earlier milestone implementation and verification

- Added the optional customer-process `evalsurge.serving.create_app` helper:
  unchanged bounded JSON input, completed `AgentAnswer`, immutable correlation
  context and explicit request/case/run-shared state keys. No built-in auth,
  tracing, memory, retry, streaming or TTFT is implied.
- Added defaulted typed evidence capabilities to v2 results/reports and safe CLI
  summaries. Configuration, measured observations, coverage and quality verdicts
  stay distinct. Omitted/duplicate selected-scorer outcomes leave aggregate
  denominators unknown; false verdicts remain observed assessments, not passes.
- Required probe trace-collection failures now produce a safe readiness error
  and prevent measured load. Answer-only readiness does not collect optional
  probe traces. Fixed guidance distinguishes auth/input/completion failures.
- Added a dry-run-first hosted-journey harness, integration/evidence guides and a
  bounded validation matrix. Terminal lifecycle/phase/result/report agreement is
  required for retrieval parity. Inconsistent remote evidence preserves an
  active-work warning. Intentional fail-fast tests require an expected safe code;
  they cannot turn an unrelated failure into successful inference.

Before the readiness correction, the smallest no-inference regression produced
one failure and one pass: a trace collector exception escaped instead of returning
an evaluation-readiness failure. Retained coverage tests exercise that exception,
missing required traces and answer-only readiness with pre-provider sentinels.
No synthetic model completion was used for these checks.

Final focused command (pure schemas, presentation, packaging, helper routing and
intentional pre-provider failures; no target or judge inference):

```bash
uv run --frozen --no-sync pytest -q tests/test_probe_evidence_failure.py tests/test_serving.py tests/test_hosted_evidence_contract.py tests/test_evidence_cli.py tests/test_hosted_journey_harness.py tests/test_wheel.py tests/test_diagnostics.py tests/test_unified_usability_contract.py tests/test_unified_journey_examples.py tests/test_agent_integration_docs.py tests/test_readme.py -k 'not runs_without_judging'
```

Final result: **173 passed, one controlled-inference test deselected** in 0.31 seconds.
The existing controlled-inference README case was deliberately deselected.
The helper tests do not execute a real agent; routing/validation checks and
deliberate handler failures are separate from successful real-model integration.
The journey harness's pure DTO tests make no inference/deployment calls either.

Other local commands:

```bash
uv sync --locked --offline --no-build-isolation --default-index https://pypi.org/simple --extra agents --group dev
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync python scripts/export_openapi.py --check
uv run --frozen --no-sync openapi-spec-validator docs/openapi.json
uv build --no-build-isolation
uv run --frozen --no-sync python scripts/verify_wheel.py
uv run --frozen --no-sync python scripts/verify_remote_install.py --offline
git diff --check
```

Local gates: locked offline sync against the public index (190 resolved,
182 installed checked), Ruff lint/format, regenerated OpenAPI equality and
independent schema validation, wheel/source build and archive verification.
Comparison against the pushed snapshot preserved all seven `/v1` paths and 28
reachable schemas. Isolated base-client installation checked 11 locked dependencies
and public evidence-model imports without the server/load/model stack; its simulated
API metadata is not simulated inference. No dependency or lockfile update occurred.
Older typed SDKs forbid unknown fields and may reject the additive v2 evidence or
capability responses; historical-document defaults are not bidirectional SDK/server
compatibility. This release caveat is recorded in ADR 0012 and the API review.

The hosted-journey guide records primary-source checks and selected-profile
read-only resource findings. No new live inference, judging, App/store/Job/compute
creation, notebook upload or cleanup is claimed. The recorded OpenAI Agents/GPT-OSS
preflight and serverless Job failure remain unresolved; CrewAI and new deployed-App
journeys remain unverified. The user approved the local controlled-inference
regression suite on October 8; the results are recorded below. No new CI was
triggered. Live validation needs exact model/route/source/App and
compute selections with bounded consent. The proposed 72-attempt matrix is not
preapproved traffic or a capacity result. See
[the retained findings and matrix](docs/HOSTED_JOURNEY_VALIDATION.md).

### Approved full-regression follow-up — October 8, 2026

The user explicitly approved the existing canned provider-response exception
before execution. Full-suite framework/native MLflow tests use controlled model
transports and deterministic localhost endpoints; real SDK/Locust execution is
not actual LLM inference or proof of a deployed App. Pure/no-inference checks and
intentional pre-provider failures are included in the aggregate count.

Environment: macOS, Python 3.12.13, pytest 9.1.1, MLflow 3.16.1, Locust 2.46.6,
LangGraph 1.2.12, OpenAI Agents 0.22.3, OpenAI 3.22.1, Databricks SDK 0.146.0 and
Pydantic 2.13.5. Locked public-index offline agents/dev sync checked 182 installed
packages after resolving 190; dependency metadata and lockfile were unchanged.

Initial `uv run --frozen --no-sync pytest -q`: **919 passed, two failed,
42 warnings in 221.69 seconds**. Both failures reproduced together in isolation
in 3.87 seconds. The assertions were stale against this milestone's documented
behavior, not replaced with skips:

- The denied HTTP 401 CLI probe expected generic `target_http_error`; it now
  asserts exact `authentication_failed` in the persisted preflight and CLI. The
  zero-measurement, skipped-load/judging and single-probe assertions remain.
- The default-off v2 journey expected missing internal-trace coverage despite
  disabled optional profiling. It now asserts no such gap and typed profiling
  configuration `false`, state `off` and zero observed profiles. All request,
  idempotency, measurement, secrecy and phase assertions remain.

Focused rerun command:

```bash
uv run --frozen --no-sync pytest -q 'tests/test_requests_example.py::test_requests_cli_real_api_locust_and_safe_preflight[denied-1]' tests/test_v2.py::test_sdk_v2_runs_actual_locust_without_planner_or_judge
```

Focused rerun: **two passed in 3.92 seconds**. Final
`uv run --frozen --no-sync pytest -q`: **921 passed, 42 warnings in 243.46 seconds**
(exit 0). No tests were skipped to remove the failures. Initial failures remain
recorded above. Independent review confirmed the updated assertions preserve the
existing fail-fast, request-count, idempotency, secrecy and measurement checks.
Warnings originate from MLflow: one SQLAlchemy `SADeprecationWarning` for `noload`
and 41 `Pandas4Warning` instances for positional `.all(0)`. Installed upstream
packages were not patched and these warnings were not suppressed.

Ruff lint and format checks passed again after the assertion updates (170 files
formatted), as did whitespace checks. OpenAPI equality/validation and read-only
comparison with the pushed baseline passed: all seven `/v1` paths and 28 reachable
request/response schemas remain equal. Wheel/source builds, archive verification
and isolated base-client installation also passed; the expected `VIRTUAL_ENV`
mismatch warning identifies the deliberate independent 11-dependency environment.
Its service lifecycle metadata is simulated, not model/provider inference.
The updated validation record is included in the rebuilt source distribution;
wheel and source package assets were verified separately.

No live LLM traffic, deployments, notebook/resource changes, new CI, commits or
pushes were performed in this follow-up. User-owned working-tree edits remain
preserved. Maintainer review, old strict-client/new-server compatibility decisions
and the separately authorized real-model journey matrix remain release gates.

## Hosted-agent onboarding documentation — October 8, 2026

Clarified chosen concurrency versus known capacity, made the minimal `http-json`
endpoint the README HTTP example, and kept DurableAgentServer as the recommended
App path. Moved MLflow `/responses` to advanced compatibility; no public protocol,
API enum, runtime or dependency was removed. Added
[the integration recipe](docs/AGENT_INTEGRATION.md) and
[proposed ADR 0012](docs/adr/0012-hosted-agent-integration-contract.md), separating
hosting/authentication, invocation and optional trace evidence.

Retrieved official Databricks Agent Server/query documentation and official
LangGraph/OpenAI Agents/CrewAI execution documentation. Databricks labels MLflow
AgentServer **legacy** and recommends DurableAgentServer; the Agent Server page
does not specify a removal date. Cross-checked installed LangGraph `ainvoke`,
LangChain message `text` and OpenAI Agents `final_output` source. CrewAI is not
installed or a newly live-validated integration; its bridge is a docs-only recipe.

Commands/results:

```bash
uv run --frozen --no-sync pytest -q tests/test_agent_integration_docs.py tests/test_readme.py tests/test_unified_journey_examples.py -k 'not runs_without_judging'
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync python scripts/export_openapi.py --check
uv run --frozen --no-sync openapi-spec-validator docs/openapi.json
git diff --check
```

The selected **18 tests passed; one controlled-inference test was deselected**.
New tests compile snippets and construct request/target schemas only; they do not
import customer agents, start an endpoint, resolve an App, invoke a model, or run
judges. Ruff lint passed. Formatting initially caught two Markdown Python blocks;
they were corrected and the check passed (**161 files already formatted**).
OpenAPI snapshot equality and independent schema validation passed; the exporter
printed MLflow's informational tracing-skill hint. Whitespace checks passed.

No fresh end-to-end inference, CrewAI/App/tracing parity, deployment, full
regression suite, dependency sync/update, package build, commit, push or CI run is
claimed. Documentation checks do not establish concurrency capacity. Material
future serving/protocol/evidence changes remain subject to ADR/maintainer review
and the explicit live/controlled-inference approvals in `AGENTS.md`.

The framework-agnostic wording follow-up makes the endpoint contract, not a list
of named frameworks, the integration boundary. Named bridge recipes are optional
examples; compatible custom agents reuse the same request and captured-answer
evaluation. Reran the selected schema/documentation command above: **18 passed,
one controlled-inference test deselected**. README/integration-guide formatting
and `git diff --check` passed. No runtime or live-validation claim was added.

## Unified direct SDK milestone — October 8, 2026

Implemented the proposed [ADR 0011](docs/adr/0011-unified-direct-and-remote-sdk.md)
contract locally on branch `main`, based on HEAD
`ce1f205c4153bb393aa6ec638cc1a88f67b90a71`. Direct Python is the onboarding
default; optional typed remote execution uses the same v2 request and typed
lifecycle/result/report models. Legacy local calls, dictionary remote calls and
`/v1` remain compatibility interfaces. Added safe field-specific validation,
typed quality/coverage/gaps, CLI summaries/JSON/static target discovery, dataset
and judge examples, and consent-gated HTTP/App/classic-notebook journey samples.
Evaluation remains off by default; lifecycle completion is not quality passing.

Independent source review also reproduced and fixed request-encoding parity,
Unicode byte-limit differences, ignored operator artifact-directory settings,
typed nonfinite values normalizing to null, conflicting ambient SDK credentials
in the HTTP live harness, and partially initialized framework-client cleanup.
Harness shutdown now closes its socket and persists content-free failure evidence
even if server shutdown raises. These fixes do not change the Locust engine or
measured timing definitions. Duplicate App discovery, snapshot-read overhead,
journal/generator measurements and capacity features remain deferred as described
in [the milestone follow-up](docs/SDK_MILESTONE.md).

Initial static checkpoint commands/results (superseded by the review below):

```bash
uv run --frozen --no-sync pytest -q \
  tests/test_unified_sdk_contract.py tests/test_unified_usability_contract.py \
  tests/test_unified_journey_examples.py tests/test_unified_journey_budget.py \
  tests/test_framework_client_ownership.py tests/test_cli.py \
  tests/test_remote_sdk.py tests/test_settings.py tests/test_diagnostics.py \
  tests/test_framework_request_docs.py \
  tests/test_v2.py::test_v2_validation_reports_safe_fields_and_bounds_without_submitted_values \
  tests/test_v2.py::test_v2_validation_preserves_only_fixed_model_validator_guidance \
  tests/test_v2.py::test_v2_validation_never_serializes_custom_exception_or_arbitrary_context \
  tests/test_readme.py::test_readme_quality_policy_and_output_match_current_contracts \
  tests/test_readme.py::test_readme_automatic_request_matches_v2_contract \
  tests/test_readme.py::test_readme_recommended_request_defaults_to_performance_only \
  tests/test_readme.py::test_target_guide_examples_validate_without_discovery_or_traffic \
  tests/test_readme.py::test_readme_relative_documentation_links_and_anchors_resolve \
  tests/test_simple_examples.py::test_example_index_links_resolve \
  tests/test_simple_examples.py::test_every_user_example_has_an_explicit_integration_contract
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync python scripts/export_openapi.py --check
uv run --frozen --no-sync openapi-spec-validator docs/openapi.json
uv build --no-build-isolation
uv run --frozen --no-sync python scripts/verify_wheel.py
uv run --frozen --no-sync python scripts/verify_remote_install.py --offline --wheel dist/evalsurge-0.2.0-py3-none-any.whl
uv run --frozen --no-sync python scripts/check_ci_prerequisites.py
git diff --check
git diff --numstat -- uv.lock
```

The focused suite passed **219 tests in 1.25 seconds**, with no skips or warnings.
It checks schemas, configuration, source ownership, lifecycle documents, transport
policy and documentation, not agent inference. Simulated HTTP responses represent
EvalSurge resource metadata only, never LLM/provider completions. Initial static
checks caught two incorrect terminal-cancellation assertions and dataset NaN
normalization; both were corrected and rerun. Later encoding regressions reproduced
typed NaN normalization before its fix. No successful live run is inferred from
these checks.

Ruff passed (**153 files formatted**); OpenAPI snapshot equality and independent
validation passed. A source comparison to HEAD verified all **7 `/v1` paths and
28 reachable schemas unchanged**; this is schema compatibility, not a complete
runtime compatibility sign-off. Fresh wheel/sdist build and packaged assets passed.
An isolated installation passed with the wheel plus **11 locked base dependencies**,
without the server/load/model SDK stack, including public v2 models, legacy/typed
remote lifecycle, safe errors and missing-server guidance. Its intentional separate
environment produced one `VIRTUAL_ENV` mismatch warning. The exporter printed
MLflow's informational tracing-skill hint; no new tracing code or calls were added.

No dependency update was requested. An earlier unfrozen `uv run` rewrote lock
provenance under the ambient mirror; only those tool-generated edits were restored.
Final checks use frozen execution. The final lock diff is empty, and provenance
checks verified **189 public registry/artifact package sources**. No new vulnerability
audit, supported-interpreter install matrix or dependency-upgrade approval is claimed.

At the initial static checkpoint, live validation had not run. A sandboxed CLI
authentication check reported an older credential-cache error. The fresh checks
below supersede that diagnosis: secure-keyring access outside the sandbox works
with the explicitly approved `e2-demo-field-eng` profile; no reauthentication,
auth-storage downgrade, profile change or laptop-token copy was needed. Classic
compute still requires explicit selection. Historical App records below are not
verification of current deployments in the newly selected workspace.

At that checkpoint, the full regression suite and inference-fixture CI were not run: they contain
controlled provider completions and require the user's explicit exception approval
under `AGENTS.md`. Framework startup cleanup currently has structural regression
coverage, not a new live runtime result. Designated maintainer review, full approved
regressions and fresh bounded real-agent journeys remain required. No commit, push,
GitHub operation or CI trigger was performed; pre-existing `AGENTS.md` and `.isaac/`
changes were preserved.

### Fresh live evidence in the selected workspace

User-approved workspace: `https://e2-demo-field-eng.cloud.databricks.com`, ID
`1444828305810485`; explicit CLI/laptop profile: `e2-demo-field-eng`. The selected
identity is active. Read-only discovery found no App with an `eval` name; other
workspace Apps were not selected or invoked. Model discovery reported
`databricks-gpt-oss-120b` and `databricks-gpt-5-4-mini` READY. Readiness is not
inference evidence. No App/Lakebase deployment or classic cluster was created.

One zero-inference, no-retry serverless prerequisite notebook completed: parent
run `364550198059215`, task run `211631498695137`. It used environment version 5,
Python 3.12.3 and Databricks SDK 0.146.0. Driver runtime auth can read the selected
workspace; explicit runtime-OAuth can obtain a token with exact-host verification.
The independent subprocess's runtime-OAuth initialization failed with `ValueError`.
Loopback sockets, process launch and POSIX lock/fsync checks passed. No credential
value was exported. This establishes a driver-to-worker auth gap, not notebook-to-App
support. `scripts/validation/serverless_prerequisites.py` provides the reusable
workspace-parameterized form of this diagnostic. Its task completion must not be
mistaken for all prerequisites passing.

Laptop real-inference commands:

```bash
uv run --frozen --no-sync python -m scripts.validation.unified_sdk_journeys \
  --journey http --framework langgraph --profile e2-demo-field-eng \
  --target-model databricks-gpt-oss-120b --exercise-cancel \
  --live --accept-paid-traffic --artifact-dir /tmp/evalsurge-lg-20261008.Lbs8io
uv run --frozen --no-sync python -m scripts.validation.unified_sdk_journeys \
  --journey http --framework openai-agents --profile e2-demo-field-eng \
  --target-model databricks-gpt-oss-120b \
  --live --accept-paid-traffic --artifact-dir /tmp/evalsurge-openai-20261008.drofEP
```

Both used the actual native framework and model, concurrency five, at most five
measured requests per run, 30-second dispatch/attempt limits, zero provider retries
and evaluation off. Synthetic read-only tools/FAQ data are disclosed demo inputs;
model responses were not stubbed. No planner/judge call occurred.

LangGraph normal run `8f5db20a-9b0c-4ea5-9400-2c65e376b63e` passed five of five
measured requests with zero errors, typed retrieval agreement and owned cleanup.
Its successful-only observed p95 latency was 943.44 ms and answer-text TTFT
871.50 ms. These are small-run client observations, not sustainable capacity.
The unknown-route probe failed and skipped measured load. Cancellation returned
`cancellation_requested` and terminated as cancelled, but had **zero measured
attempts**: cancellation before user dispatch is not in-flight cancellation
coverage. The earlier harness receipt's `dispatch_cancellation_exercised=true`
overstates this evidence; the harness is being tightened to observe actual HTTP
dispatch. Preserve that original receipt and this correction.

LangGraph also emitted upstream Pydantic serialization warnings around structured
reasoning content. Independent installed-source/artifact review found five
nonempty captured answer strings and positive provider usage values; across seven
traces, concatenated string model fragments matched the corresponding hosted
answers. MLflow stored raw `LLMResult` rather than normalized chat output. That is
degraded chat-trace rendering, not clean tracing/judging parity. Usage can include
reasoning tokens; future text-object chunks are not established support.
OpenAI Agents run `965459df-81da-454e-9624-889d23aede1c`
**failed** its real model-bearing preflight: the Chat Completions stream handler
passed structured reasoning blocks to `ResponseTextDeltaEvent.delta`, whose type
is string. Measured load was skipped and no additional run was attempted by that
harness. The failed result remains failed. It does not contradict older native
Responses-protocol App evidence, which exercises a different transport.

Remaining notebook journey tests explicitly select `databricks-gpt-5-4-mini` under
the user's smaller-model approval. This is a separate configured test, never an
automatic fallback, provider retry or replacement of failed evidence. Serverless
notebook-to-App, current deployed source, classic notebook, judge calibration,
designated maintainer review and approved full regression/CI remain open gates.

### Serverless live outcome and pre-push review — October 8, 2026

Read-only CLI inspection confirmed parent run `584248337638691` and task
`1003312814916440` terminated with `INTERNAL_ERROR` / `FAILED`, after five seconds
of setup and 214 seconds of execution. The selected profile was
`e2-demo-field-eng`; the selected model was `databricks-gpt-5-4-mini`, evaluation
off, concurrency five, with the previously recorded maximum of 26 top-level
attempts per framework (52 across both). These are approved bounds, not observed
attempt counts. The task had no retries; no new paid run was submitted.

`get-run-output` returned no `notebook_output.result`. It reported an unresponsive
Python kernel / exit code 3 and a framework-server startup exception:
`MlflowException: No Experiment with id=1 exists`. Without a final receipt,
successful inference, framework-by-framework counts, cancellation, report
retrieval and cleanup cannot be claimed. The startup exception does not establish
the cause of the kernel exit. No fresh App/Lakebase/classic resource was deployed.

Installed native MLflow source (`tracking/fluent.py`, `set_experiment`) sets
`MLFLOW_EXPERIMENT_ID` in the environment. The dedicated notebook harness restored
only its originally supplied keys, allowing that ID to leak into another fresh
SQLite store. A new subprocess-isolated test using two actual MLflow stores failed
before the fix and passed afterward (**1 passed in 1.94 seconds**). The harness now
clears and restores this ID inside its existing owned configuration scope, including
the exceptional path, after owned resources drain. No framework, provider, agent
or completion is mocked by this regression; it makes no inference calls. The fix
has not been uploaded or rerun live, and the original failed run remains failed.

README, Python/notebook guidance, milestone status, ADR 0011 and harness guidance
now surface this failure and retain the worker-OAuth/deployed-App validation gaps.
GitHub authentication outside the sandbox confirmed the correct personal
`RamVegiraju` identity; `git fetch origin` found no branch divergence (`0 0`).
The repository workflow runs the full controlled-inference suite on every push.
At this checkpoint its exception approval was still required; no workflow was
disabled or skipped. The subsequent user-approved release checks are recorded below.

Further installed-source inspection found native Uvicorn calls
`sys.exit(STARTUP_FAILURE)` after lifespan startup failure. An isolated regression
using real Uvicorn/FastAPI, with an intentionally failed ASGI lifespan and no agent
route or provider fixture, reproduced **process exit code 3** before the fix.
Both harnesses now catch SystemExit inside the server task and propagate a fixed
RuntimeError through existing cleanup/receipt paths. The same regression then
passed (**1 passed in 0.40 seconds**) and returned control to its host coroutine.
This establishes the local termination path matching the remote symptom, not a
definitive remote root cause or successful live rerun. Invocation/measurement
semantics, target retries, profile/auth boundaries and paid bounds are unchanged.

Source-archive inspection also found `.isaac/config.json` in the first local
sdist. It was not uploaded and its contents were not read. The directory remains
untouched; `.gitignore` and the Hatch sdist exclusion now keep it out of commits
and packaging. The package verifier now requires the new `local`, `run_views`
and `validation` modules and checks source member names without extraction.
The strengthened verifier rejected the old archive as expected; three no-inference
archive regressions cover clean, missing-module and private-metadata cases.
`pyproject.toml` changed only its build exclusion; dependency declarations and
`uv.lock` did not change. `uv lock --check --offline --default-index
https://pypi.org/simple` accepted the locked metadata. Cached locked sync aligned
Ruff from the previously installed 0.16.9 to locked 0.16.10, not a lock upgrade.

Final consolidated pre-push checks on macOS/Python 3.12.13:

```bash
uv sync --locked --offline --default-index https://pypi.org/simple --extra agents --group dev
uv run --frozen --no-sync pytest -q \
  tests/test_unified_sdk_contract.py tests/test_unified_usability_contract.py \
  tests/test_unified_journey_examples.py tests/test_unified_journey_budget.py \
  tests/test_framework_client_ownership.py tests/test_dispatch_observer.py \
  tests/test_serverless_journey_contract.py tests/test_wheel.py \
  tests/test_cli.py tests/test_remote_sdk.py tests/test_settings.py \
  tests/test_diagnostics.py tests/test_framework_request_docs.py \
  tests/test_v2.py::test_v2_validation_reports_safe_fields_and_bounds_without_submitted_values \
  tests/test_v2.py::test_v2_validation_preserves_only_fixed_model_validator_guidance \
  tests/test_v2.py::test_v2_validation_never_serializes_custom_exception_or_arbitrary_context \
  tests/test_readme.py::test_readme_quality_policy_and_output_match_current_contracts \
  tests/test_readme.py::test_readme_automatic_request_matches_v2_contract \
  tests/test_readme.py::test_readme_recommended_request_defaults_to_performance_only \
  tests/test_readme.py::test_target_guide_examples_validate_without_discovery_or_traffic \
  tests/test_readme.py::test_readme_relative_documentation_links_and_anchors_resolve \
  tests/test_simple_examples.py::test_example_index_links_resolve \
  tests/test_simple_examples.py::test_every_user_example_has_an_explicit_integration_contract
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync python scripts/export_openapi.py --check
uv run --frozen --no-sync openapi-spec-validator docs/openapi.json
uv run --frozen --no-sync python scripts/check_ci_prerequisites.py
uv lock --check --offline --default-index https://pypi.org/simple
uv build --no-build-isolation
uv run --frozen --no-sync python scripts/verify_wheel.py
uv run --frozen --no-sync python scripts/verify_remote_install.py --offline --wheel dist/evalsurge-0.2.0-py3-none-any.whl
git diff --check
git diff --numstat -- pyproject.toml uv.lock
```

The consolidated suite passed **262 tests in 3.49 seconds**, with no warnings or
skips. Checks exercised only schema/resource metadata, operator configuration,
source/docs contracts, archives and native local storage/failed ASGI startup.
No agent/model completion was stubbed or called. Ruff lint/format passed (158
files); OpenAPI snapshot equality and independent schema validation passed.
Recursive comparison against baseline `ce1f205` found all **7 v1 paths and 28
reachable schemas unchanged**, not a runtime compatibility sign-off. Public
registry/artifact provenance passed for **189 locked packages**. Rebuilt wheel
and sdist passed required-asset/private-metadata checks. Isolated installation of
the actual wheel plus **11 locked base dependencies** passed legacy/typed remote,
CLI and missing-server checks without the server/load/model stack. It emitted the
expected separate-environment `VIRTUAL_ENV` warning. Secret-pattern scanning found
no matches in the reviewed source/docs directories; this is not a security audit.

At this static checkpoint, full regression, push-triggered controlled-inference CI,
designated maintainer review and the remaining live journeys were still open. The offline full suite
uses deterministic SSE/JSON target responses (`tests/conftest.py`), controlled
preflight/readiness/load boundaries, real LangGraph/OpenAI frameworks with fixture
provider completions (`tests/test_frameworks.py` and App-boundary integrations),
and native MLflow with controlled planner/judge responses (evaluation/preflight
suites, including `tests/test_mlflow_backend.py`). These check reproducible failure,
wire, lifecycle and evaluation regressions without paid traffic; they do not
establish real inference. Approval for that explicit exception was required before
the full suite or a push triggering it. No commit or push had been performed at
that checkpoint; the approved full checks below supersede its regression status.

### Approved full release checks — October 8, 2026

After disclosure of the controlled target/provider/planner/judge boundaries above,
the user explicitly approved the offline full suite and push-triggered CI exception.
That approval does not convert fixtures into live-model evidence or authorize new
paid calls. No workflow or regression was disabled to obtain passing results.

The first `uv run --frozen --no-sync pytest -q` completed with **7 failed,
811 passed, 30 warnings in 218.19 seconds**. Five App-quality regressions exposed
direct factory configuration bypassing the effective task-local scope and legacy
submission losing an experiment selected after context entry. A legacy sync test
also reproduced eager validation of an unused invalid target registry; the last
failure was a README assertion still looking for the removed v1 curl quickstart.

Factories now inherit the effective private scope. Unified requests freeze and
validate their registry before discovery/admission. Legacy exact-Agent calls without
explicit context bindings/settings retain submission-time configuration and ignore
that unused registry. Both preserve the actual artifact owner without global
environment mutation. Seven new no-inference regressions cover scoped construction,
frozen valid registries, fail-closed invalid registries and native async/sync legacy
submission. The new sync guard caught a missing artifact-directory propagation in
the first focused rerun; it was corrected before the final full run. The README
regression now validates the direct v2 golden-path request. ADR 0011 and the Python
and code guides document these compatibility boundaries.

Final focused/full and release-gate commands:

```bash
uv sync --locked --offline --no-build-isolation --default-index https://pypi.org/simple --extra agents --group dev
uv run --frozen --no-sync pytest -q --tb=short tests/test_unified_sdk_contract.py tests/test_databricks_app_quality.py tests/test_foundations.py::test_should_accept_readme_sample_as_performance_only_request tests/test_python_api.py::test_sync_client_does_not_nest_event_loop
uv run --frozen --no-sync pytest -q
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync python scripts/export_openapi.py --check
uv run --frozen --no-sync openapi-spec-validator docs/openapi.json
uv run --frozen --no-sync python scripts/check_ci_prerequisites.py
uv lock --check --offline --default-index https://pypi.org/simple
uv build --no-build-isolation
uv run --frozen --no-sync python scripts/verify_wheel.py
uv run --frozen --no-sync python scripts/verify_remote_install.py --offline --wheel dist/evalsurge-0.2.0-py3-none-any.whl
git diff --check
git diff --numstat -- uv.lock
```

The focused rerun passed **71 tests, 13 warnings in 15.47 seconds**. The full
rerun passed **828 tests, 42 warnings in 232.58 seconds**, with no skips. Warnings
come from native MLflow's SQLAlchemy deprecated `noload` loader and positional
Pandas `all(0)` calls. These are controlled integration/regression results, including
real frameworks, Locust and native MLflow at the disclosed fixture boundaries;
they are not actual LLM inference, App deployment or notebook journey validation.
The new framework bridge documentation has syntax/schema coverage only, not CrewAI
runtime or hosting parity.

The initial offline isolated build could not resolve uncached Hatch metadata.
The explicit public-PyPI sync then failed with connection refused after three
retries. Offline locked sync with already-installed compatible **Hatchling 1.32.4**
and `--no-build-isolation` passed. The dependency lock remains unchanged; no registry
URLs, artifact hashes or dependency versions were rewritten. This is not a fresh
public-index clean installation or a latest-compatible dependency upgrade.

Lint/format passed (**161 files**); OpenAPI equality/independent schema validation
and public provenance checks passed (**189 locked registry packages**). Final
wheel/sdist checks verify required assets and private-metadata exclusion; isolated
installation verifies the client with **11 locked base dependencies**, without
the server/load/model stack. The isolated environment emits the expected
`VIRTUAL_ENV` mismatch warning. The
earlier 7-path/28-component v1 schema comparison remains separate from the full
runtime regressions and from any supported-interpreter CI result.

This record is prepared before commit/push. Remote CI must be inspected after
the actual push; configured jobs alone are not a pass. The user-owned `AGENTS.md`
edit and local `.isaac/` directory remain outside the commit. Designated maintainer
review, current deployed-App/notebook-to-App/classic-notebook evidence and the
failed serverless live journey remain open. No new paid traffic or deployment
was performed for these release checks.

## Publication verification — October 8, 2026

Reviewed the pending four framework/hosting request examples, controlled real
framework/Locust/API tests, README and operator guides before publication. README
now leads with a performance-only v2 request and keeps the supported v1 mock
tutorial clearly labeled. Updated App evidence/navigation, distinguished local
fixture and native live coverage, repaired the renamed quickstart anchor and
recorded fresh upstream dependency observations in `docs/DEPENDENCIES.md`.
No production module, API contract, load engine or dependency lock changed.

Commands/results for this publication checkpoint:

```bash
uv sync --locked --extra agents --group dev
uv sync --locked --offline --default-index https://pypi.org/simple --extra agents --group dev
uv run --no-sync pytest -q tests/test_readme.py tests/test_simple_examples.py tests/test_framework_app_requests.py tests/test_framework_request_docs.py --tb=short
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q --tb=short --junitxml=artifacts/prepush-20261008/final-junit.xml
uv run --no-sync python scripts/export_openapi.py --check
uv run --no-sync openapi-spec-validator docs/openapi.json
uv build --no-build-isolation
uv run --no-sync python scripts/verify_wheel.py
uv run --no-sync python scripts/verify_remote_install.py --offline
uv run --no-sync python scripts/check_ci_prerequisites.py
uv export --quiet --locked --offline --default-index https://pypi.org/simple --extra agents --group dev --no-emit-project --output-file artifacts/prepush-20261008-audit-requirements.txt
uv run --no-sync pip-audit --disable-pip --require-hashes --progress-spinner off --vulnerability-service osv --requirement artifacts/prepush-20261008-audit-requirements.txt --format json --output artifacts/prepush-20261008-audit.json
git diff --check
```

The bare sync rejected the authentic unchanged lock under the ambient index
configuration; explicit public-index cached sync succeeded (**190 resolved,
182 checked**). Focused tests passed **38 tests, 13 warnings in 56.10 seconds**.
One initial Ruff format check found the new README test's layout; formatting that
file resolved it. Final lint and format checks passed (**135 files**). Full pytest
passed **691 tests, no skips, 42 known upstream warnings in 226.53 seconds**.
OpenAPI snapshot equality and independent schema validation, wheel/sdist build,
packaged assets, isolated base-only remote SDK/CLI and missing-server guidance all
passed. Provenance checks verified **189 public registry/artifact package sources**.
The hashed lock export's OSV audit covered **181 applicable dependencies with zero
known advisories and no skipped packages** on local Python 3.12. OSV checks hash
presence, not artifact validity; this is not a license audit or security sign-off.

No paid traffic, App redeployment or resource mutation was repeated to prepare
this publication. Protected artifacts are ignored and excluded; unrelated `.isaac/`
content is preserved and not staged. The three reproduced runtime defects below
(swallowed client validation guidance, first-user App lookup race, repeated snapshot
reads) remain unresolved; these tests/docs do not implement those fixes. Newer
upstream dependency releases still need the reviewed compatibility workflow.
Remote CI results, maintainer approval and a clean install across all supported
interpreters are not established by these local checks.

## Native Databricks App deployments and live checks — October 8, 2026

Following separate authorization for the exact selected OAuth profile/workspace,
deployed **both** native framework samples on Databricks Apps, each with one MEDIUM
instance and a managed Lakebase Runtime Store. LangGraph active revision:
`01f1c3330cfe1a8caddb1e52caafad8f`; OpenAI Agents active revision:
`01f1c3333df91bb8a95241b11f68124d`. Both were RUNNING/ACTIVE; deployed source
hashes, runtime controls and store ownership matched before traffic. Real App names,
profile, URLs, store bindings and protected source/evidence remain uncommitted.
The earlier October 7 App is no longer listed; its historical results do not prove
present deployment health.

Samples execute a compiled LangGraph or the native OpenAI Agents Runner with
`system.ai.gpt-oss-120b` over the provider Responses API. They use 512 output-token
limits, low reasoning effort, 30-second model deadlines and zero model retries.
There are no tools, transcript history, long-term memory, automatic recovery or
trace exporter in these live samples. The required Runtime Store persists
invocation execution, not an enabled agent Session/Memory Store. The synthetic
refund policy is embedded in their instructions; the published questions/load
requests were unchanged. Native controlled tests verified completion, idempotency,
pre-provider failure and rejection of unfinished output. Final policy-source
controlled runs passed once per framework (5.92 / 5.93 seconds).

Real loopback HTTP remote SDK → Uvicorn v2 API → server-owned SDK App
resolution/OAuth → sole Locust subprocess → App HTTPS `/api/invocations` → real
model. No ASGI/TestClient replacement, controlled provider or synthetic App-origin
mapping was used for these live runs. Ran the two performance tests sequentially
with concurrency five, 180-second dispatch ceiling, 500 measured-request cap and
60-second HTTP timeout, plus one separately excluded successful inference probe.
Evaluation was omitted/default off; no paid planner or judge calls occurred.

| Live observation | LangGraph | OpenAI Agents |
| --- | ---: | ---: |
| Measured successes / attempts | 500 / 500 | 500 / 500 |
| Errors | 0 | 0 |
| Configured users / observed peak HTTP in-flight | 5 / 5 | 5 / 5 |
| Dispatch window | 147.52 s | 135.15 s |
| Elapsed including drain | 148.80 s | 136.40 s |
| Successful requests/s including drain | 3.360 | 3.666 |
| Successful latency p50 / p95 / p99 | 1204.89 / 2386.61 / 5763.19 ms | 1225.17 / 2362.05 / 2638.67 ms |
| Native JSON TTFT / usage coverage | unavailable / 0% | unavailable / 0% |
| Internal trace coverage | 0 / 500 | 0 / 500 |

Performance run IDs: `0526ee83-0883-4588-8bc5-54be52aef4d8` and
`3399b567-8903-4319-8e4c-c8cee8522fb1`. These reached the request cap before
three minutes; they are bounded integration runs, not capacity studies or a
statistically controlled comparison of frameworks. Endpoint-only native JSON
does not provide TTFT/token usage, internal breakdowns or live memory/tool coverage.

Separate intentional failure runs used a reserved sample sentinel that fails
before the model call. Each produced exactly one excluded HTTP-500 probe,
`target_http_error`, terminal failed status, skipped load and **zero measured
requests**; no target retry or judge call followed. Failure IDs:
`ee57526f-a620-4f02-bebd-d21c261efe38` and
`45ade80a-d935-483b-992c-996d3141cfbe`. Failed reports remain preserved.
OpenAI's real CLI doctor and idempotent replay both exited zero, returning the
same accepted run without additional target calls.

Protected deployment/control/source, successful and failed run, complete journal,
CLI and timing evidence is under `artifacts/live-framework-apps-20261008/`.
Final read-only checks retained the same active revisions/source hashes, runtime
controls and managed-store ownership. Independent journal audit confirmed matched
start/completion counts, valid unique IDs, no interrupted attempts and no overlap
with probe IDs. Total observed App invocations were 1004: 1000 measured, two
successful excluded probes and two intentional non-model failed probes. The
single-turn/no-retry source implies 1002 model calls; billing was not independently
reconciled. Local harness/API/Locust/deployment processes stopped; an unrelated
older MLflow server was preserved.

Initial name-limit, sandbox authentication/startup, STARTING-instance-update and
read-only evidence-serialization failures are retained in the protected summary.
Secure credential access was used without enabling plaintext caching, deleting
resources or changing the selected profile. Isolated sample dependencies used the
existing mirror after public refresh failed; cloud deployment selected public
PyPI and excluded the local lock. Mirror provenance is retained and complete cloud
transitive-dependency parity is not claimed.

At this live-validation checkpoint, no core/API/engine fix or dependency upgrade
was implemented and no commit/push had been performed. Apps/stores remained
provisioned; local controlled
framework/tool/memory evidence is separate below. Sustainable capacity, judge
calibration, production durability/recovery, App streaming and remote CI are not
established by this record.

After all live/local benchmark processes stopped, final repository verification
passed:

```bash
uv sync --locked --extra agents --group dev --offline --default-index https://pypi.org/simple
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q --tb=short --junitxml=artifacts/review-feedback-20261008/final-junit.xml
uv run --no-sync python scripts/export_openapi.py --check
uv run --no-sync openapi-spec-validator docs/openapi.json
uv build --no-build-isolation
uv run --no-sync python scripts/verify_wheel.py
uv run --no-sync python scripts/verify_remote_install.py --offline
uv run --no-sync python scripts/check_ci_prerequisites.py
git diff --check
```

Cached locked sync resolved **190 packages** and checked **182**. The full suite
passed **690 tests, no skips, 42 known upstream warnings in 220.07 seconds**.
Ruff lint/format (**135 files**), unchanged OpenAPI snapshot and independent
validation, sdist/wheel build, packaged assets, isolated base-only remote SDK/CLI
and missing-server guidance all passed. Source/provenance checks verified **189
locked registry packages**. Offline verification is not fresh release/advisory
metadata retrieval, cloud dependency parity, remote CI or maintainer approval.

## Feedback review and full-budget local checks — October 8, 2026

Validated the colleague's API/CLI, SDK, persistence, measurement and App-parity
feedback against first-party source, installed dependency source and current
official documentation. This is a review, not implementation of the proposed
runtime fixes. Reproduced three defects without paid traffic:

- Schema `ValidationError` is caught as `ValueError` by the CLI/remote submission
  paths, hiding the field-specific guidance. A valid JSON request with concurrency
  zero reports the misleading finite-JSON error and sends no HTTP traffic.
- Five delayed concurrent first-user App resolutions perform five SDK discovery
  calls. Admission/preflight and measured workers have separate caches.
- A synthetic terminal snapshot with 10,000 captures / 21,691,019 bytes is read
  once for status and three times for result/report. Observed local elapsed times
  were 33.625 / 66.732 / 65.521 ms respectively; these are not remote estimates.

Confirmed that native `fsync` can block the gevent hub; the measured local
200-event test had 0.0725-ms median and 0.1141-ms p95 sync cost. Network-disk cost
and actual generator saturation remain unmeasured. Any writer optimization must
retain durable start acknowledgment before target dispatch and truthful incomplete
completion recovery. Successful-only latency and elapsed-including-drain TPS are
already explicitly labeled. Output tokens exist per request; aggregate token
distributions remain absent. Locust `constant_throughput` is pacing, not a genuine
independent arrival scheduler. Remote submission already accepts typed `RunCreate`,
and local Python already can invoke an App through the operator resolver without
an EvalSurge REST server.

Native `databricks-agentbricks==0.4.0` source and a controlled actual server verified
foreground streaming and runtime terminal failure events. A server that emitted
answer text before failing returned HTTP 200 plus `run.failed`, with failed final
state. Adding native streaming requires terminal-outcome validation, separate
first-event/answer-text timing and actual usage evidence, not just `stream:true`.

Read-only API/CLI/SDK/v2 suite: **68 passed in 2.70 seconds**. Focused four-example
rerun: **32 passed, 13 upstream warnings in 41.95 seconds**. Ruff lint/format
(135 files), whitespace, unchanged OpenAPI export and independent validation passed.
Protected review/reproduction evidence is under
`artifacts/review-feedback-20261008/`. Fresh public release metadata retrieval was
blocked even after an escalated retry; no newly verified latest-release claim or
dependency upgrade is made.

Both unchanged published **local** JSON requests were also run through actual
loopback HTTP Uvicorn target/API servers, remote SDK, the sole Locust engine,
compiled LangGraph/OpenAI Agents Runner and native MLflow. Only provider HTTP
responses were controlled; tools, request-isolated memory and instrumentation
executed. No paid model, planner or judge calls occurred.

| Full-budget observation | LangGraph | OpenAI Agents |
| --- | ---: | ---: |
| Measured successes / attempts | 500 / 500 | 500 / 500 |
| Errors | 0 | 0 |
| Excluded successful probe | 1 | 1 |
| Configured users / observed peak HTTP in-flight | 5 / 5 | 5 / 5 |
| Elapsed including drain | 22.929 s | 17.190 s |
| Successful requests/s including drain | 21.807 | 29.086 |
| Latency p50 / p95 / p99 | 220.49 / 308.35 / 359.87 ms | 161.32 / 218.41 / 264.65 ms |
| Answer-text TTFT p50 / p95 / p99 | 120.66 / 178.34 / 216.15 ms | 113.68 / 138.95 / 210.82 ms |
| TTFT / usage coverage | 500 / 500 | 500 / 500 |
| Profiled / budget gaps | 200 / 300 | 200 / 300 |

The 500-request cap ended both runs before the 180-second dispatch ceiling.
Quality was off; trace-budget gaps were explicit. Run IDs were
`baf46b35-0be2-4479-87c3-f22385022015` and
`87a5e2a4-5776-4be4-8c32-199eff9f8e23`. Complete journals, excluded probes,
unique invocation/trace IDs and per-request timing/usage were verified. Evidence
and the completed-run rerun guard are under
`artifacts/framework-local-full-20261008/`. These are controlled integration
observations, not live-model speed, calibrated quality or sustainable capacity.

## Four framework/hosting request examples — initial October 8, 2026 checkpoint

Added [the framework target guide](docs/FRAMEWORK_TARGET_EXAMPLES.md), four
copyable default-off v2 JSON requests under `examples/requests/`, and one
placeholder-only operator TOML. The matrix covers LangGraph and OpenAI Agents,
each runner-local HTTP or a registered Databricks App. REST, CLI, and remote SDK
submission share the same aliases. Published load bounds are concurrency five,
180 seconds of dispatch, 500 measured attempts and a 60-second request timeout;
automated tests use detached copies reduced to two users/two measured attempts,
five seconds of dispatch and ten-second HTTP deadlines. No public API, runtime
behavior, dependencies, lockfile, or live resources changed.

Official Databricks Agent Server documentation retrieved on October 8 confirms
recommended DurableAgentServer `/api/invocations`, explicit legacy MLflow
`/responses`, both framework templates, and a managed Runtime Store separate from
agent transcript history/memory. No obsolete deployment skill was used to change
the protocol. Operator profiles, App names, destinations and OAuth remain outside
public requests; committed bindings contain placeholders, not selected resources.

Static tests validate all four request files through actual v2 models, translation,
protocol encoders and the CLI configuration reader, compare guide JSON to files,
and check registry/inventory/navigation. Actual local framework tests execute SDK
and CLI submissions through the API and real Locust HTTP to compiled LangGraph
and OpenAI Agents Runner. They verify default-off behavior, streamed timing,
request-isolated memory, correlation, and exactly one excluded probe plus two
measured successes. Real framework provider denials stop after one probe, with
zero measured traffic and no retries or judging.

App tests exercise the real v2/remote SDK, native Databricks Config/WorkspaceClient/
AppsAPI and OAuth interfaces, original Locust workers, both frameworks and native
MLflow traces. Test-only bootstrap controls discovery/auth and maps one exact
synthetic HTTPS App origin to loopback HTTP after production destination checks.
The loopback invocation envelope wraps the real framework demo; it is **not**
DurableAgentServer, a deployed App, or a Lakebase-backed Runtime Store. Tests verify
fresh OAuth per dispatch, unique invocation/session identifiers, exact correlation,
probe exclusion and content-free profile coverage. An unfinished outer invocation
fails fast with one excluded probe, zero measured attempts and no hidden polling.
Process-local boundary patches and exact raw MLflow selectors are restored.

Focused verification:

- `uv run --no-sync pytest -q tests/test_simple_examples.py`: **22 passed**,
  13 existing upstream warnings, **30.23 seconds**.
- `uv run --no-sync pytest -q tests/test_framework_app_requests.py
  tests/test_frameworks.py tests/test_remote_integration.py`: **52 passed**,
  one upstream SQLAlchemy warning, **62.56 seconds**.
- `uv run --no-sync pytest -q tests/test_framework_request_docs.py
  tests/test_readme.py --tb=short`: **11 passed in 3.02 seconds**. After adding
  the actual CLI reader assertion, the six static request tests passed again.

Locked public-index agents/dev sync resolved **190 packages** and checked **182**.
Environment: Python **3.12.13**, LangGraph **1.2.12**, OpenAI Agents **0.22.3**,
MLflow **3.16.1**, Databricks SDK **0.146.0**, Locust **2.46.6**. Commands:

```bash
uv sync --locked --extra agents --group dev --default-index https://pypi.org/simple
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q --tb=short \
  --junitxml=artifacts/framework-target-examples-20261008/junit.xml
uv run --no-sync python scripts/export_openapi.py --check
uv run --no-sync openapi-spec-validator docs/openapi.json
uv build --no-build-isolation
uv run --no-sync python scripts/verify_wheel.py
uv run --no-sync python scripts/verify_remote_install.py --offline
uv run --no-sync python scripts/check_ci_prerequisites.py
git diff --check
```

Final full suite: **690 passed, no skips, 42 existing upstream warnings in
222.59 seconds**. Warnings remain MLflow's SQLAlchemy loader deprecation and
positional pandas API usage, not new framework/hosting failures. Ruff lint and
formatting (**135 files**), unchanged OpenAPI snapshot equality and independent
schema validation, sdist/wheel build, packaged assets, and actual isolated base-only
SDK/CLI/missing-server checks passed. Source-distribution inspection also verified
all four JSON requests, the operator TOML and new guide. Public provenance checks
still cover **189 registry packages**; no fresh upgrade or advisory audit is
claimed. Whitespace checks passed. Protected JUnit evidence is retained at the
path in the command above.

No new paid target/planner/judge calls, workspace reads, App deployments or store
provisioning were performed. Live retests require an exact confirmed profile,
deployed App and bounded consent; a new LangGraph deployment is not inferred from
the earlier OpenAI App authorization. The October 7 live OpenAI Agents record
below remains separate historical evidence. Controlled tests do not establish
live App health, native server/store durability, sustainable capacity or calibrated
quality. Remote CI and designated maintainer review are not claimed. Changes are
uncommitted on `main` at `78681fbe68d61c4ffc0c47126328244e25b76b44`; the unrelated
`.isaac/` directory is preserved. No commit, push or GitHub operation occurred.

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
  from the then-configured private package source; tests/audits never ran. The public-lock
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
