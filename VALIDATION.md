# Validation — 0.2.0

Validated locally on macOS/Python 3.12 on October 4–8, 2026. Baseline commit
`2276c3b4d6fa9943544f988df4e5ed658ad79365` passed GitHub run `37840928318` on
October 8: every test and security job succeeded on Linux/Python 3.11–3.14.
That approved controlled-inference CI does not validate the follow-up checkpoint
or establish live model/deployment success. Earlier mirror-install failures remain
historical evidence. Repository review enforcement remains a maintainer gate.

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
