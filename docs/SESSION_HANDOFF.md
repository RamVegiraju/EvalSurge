# EvalSurge session handoff — October 10, 2026

## Resumed checkpoint — October 10, 2026

Branch is `main`; pre-publication HEAD was
`a4e9408c6d642dd5e20d4545e638f08f167d3d49`. This checkpoint is being published
before further CrewAI work; inspect the latest commit and working-tree state on
resumption for the exact HEAD. Preserve unrelated changes. Native storage/process tests passed
**29/29**, one upstream warning, after the readiness diagnostic repair. Full
combined verification completed in 28.34 seconds. Prior failure
receipts remain. Tests with controlled inference were adapted but not run;
their explicit exception approval remains pending.

Independent review confirmed exact durable feedback and bounded catalog
dispatch accounting. Top-level worker errors now survive readiness; cancellation
has its own readiness status, and credential inheritance is accurately documented.
Cleanup failure with a still-live child and supported-store custom trace-scorer
semantics remain hardening/verification gates. The narrow recovery independently
requires reaping and both PID/group absence. The 16-check offline recovery audit
passes. After final source review/static/schema/build checks, root released the
previously approved one-use recovery. It finished with exit **0**, owner gate
**passed**, and independent read-only audit **45/45 passed**. Never rerun this
completed recovery or the original stopped lease.

Final results (real models, no fixtures):

| Evidence | LangGraph | OpenAI Agents |
| --- | --- | --- |
| Load | Historical 500/500 success, no new target calls | Fresh 500/500 success, one excluded probe |
| Successful p50 / p95 / p99 | 1154.21 / 1171.63 / 2161.67 ms | 1164.49 / 1675.44 / 2524.54 ms |
| Achieved whole-window rate | 4.173 requests/sec | 3.979 requests/sec |
| Relevance / correctness | 50 durable scores each; 100% / 88% | 50 durable scores each; 100% / 86% |
| Judge execution errors | 0 | 0 |

Both load runs used concurrency five. LangGraph supplemental judging retained the
exact original 50 selected captures; original failed run
`2b28bf04-bc4c-40f7-95f4-8a3beedebdc5` stays failed. Derived plan changes only
ID/store, with lineage. OpenAI new run is
`1bc6580c-bdc7-408b-a625-348934b72c54`; elapsed including drain 125.652 seconds.
The independent audit verified exact durable feedback/source-run metadata,
original hashes, sample membership, complete journals, metrics and PID/group
absence. SDK context closure is recorded by the owner's lifecycle receipt,
not a separate independent-audit predicate.
Parent environment unchanged. **703 new attempts: 501 agent + 202 confirmed judge**,
below approved 1,103; zero commit-unknown judge attempts. No model/deployment change.

Agent: `system.ai.gpt-oss-120b`, <=512 output tokens, zero retries. Judge:
`databricks-gpt-5-4-mini`, <=2048 output tokens, 60-second timeout. Explicit
relevance/correctness, no planner/fallback. Protocol remains synchronous
`/api/invocations`; no `/responses`, App TTFT/token usage, streaming/internal trace,
memory, notebook or capacity claim follows.

Protected evidence (never commit/export raw contents):

- Owner: `/private/tmp/evalsurge-app-quality-recovery-20261009.r4c3jk/gate-receipt.json`.
- Independent audit: `/private/tmp/evalsurge-measurement-accuracy-20261009.hhACtp/independent_recovery_extended_receipt.json`.
- LangGraph supplemental envelope: `/private/tmp/evalsurge-app-quality-recovery-20261009.r4c3jk/langgraph-rejudge/rejudged-report.json`.
- OpenAI report: `/private/tmp/evalsurge-app-quality-recovery-20261009.r4c3jk/openai/report.json`.
- Original failure: `/private/tmp/evalsurge-app-load-quality-20261009.0099be`.
- Readable aggregate index: `/private/tmp/evalsurge-app-quality-recovery-20261009.r4c3jk/reports.html`.
  Offline 0600 export, zero new calls; not browser/layout verified or deployed.

Read-only LangGraph correctness review classified one supported policy error and
five compound-reference completeness-sensitive verdicts. OpenAI had one supported
policy error and six completeness-sensitive negatives. Preserve 88%/86%; neither
rewrite frozen references nor rejudge merely to make them pass. Completion and
passing quality remain separate. See `VALIDATION.md` for details and limitations.

After validation, both retained Apps were stopped on selected `e2-demo-field-eng`
on October 10: `agent-bricks-es-lg-1008` and `agent-bricks-es-oai-1008` each
returned compute `STOPPED` and App `UNAVAILABLE`. Definitions, deployments,
coupled managed Runtime Stores and historical evidence were preserved. Stopping
compute is reversible; it is not deletion or proof of zero storage charges.
The recorded prerequisite submit-run `526298221857181` is already terminal.
No matching EvalSurge Job appeared in the 100-definition inventory; that is not
proof of workspace-wide absence. Do not delete a Job using a run ID.

Measurement work is complete; all diagnostic children are stopped. See
`docs/MEASUREMENT_ACCURACY.md` and `VALIDATION.md`: small native laptop costs,
confirmed cross-user delay under blocking journal stalls, auth timing includes
journaling and full snapshot polling costs CPU/disk. No zero-observer-effect,
capacity/cloud-disk claim or production timing change.

Official latest-release metadata rechecked October 10 advertises CrewAI 1.15.27,
published October 9 at 22:33:44 UTC. Neither 1.15.26 nor 1.15.27 is visible through
the approved development package source. This is an availability blocker, not
demonstrated incompatibility; do not bypass registry controls.
Alternative 1.15.23 resolved but is uninstalled; isolated environment is empty.
Version choice and the separate 76-attempt App/local lease remain pending.
Never upload the private preparation directory or commit private registry data.

Before publication review: **23 tracked files modified, 9 untracked additions**;
README and dependency-status updates were added during the review.
Implementation: modified `coordinator.py`, `evaluation_preflight.py`, `evaluator.py`;
new `evaluation_process.py`, `evaluation_worker.py`, `evaluation_attempts.py`.
Docs include architecture/security/code guide, validation/hosted/serverless/handoff
records, new diagnosis/measurement records and proposed ADR 0013. Validation
harnesses, wheel verification and controlled-test compatibility adaptations are
included in this checkpoint; new tests are `test_evaluation_process_storage.py`,
`evaluation_unit_boundary.py`, `test_local_helper_canary_setup.py`. Inspect actual
`git status --short` on resumption; preserve every tracked/untracked change.

Final evidence integration and publication review reran Ruff lint/format
(193 files), whitespace,
OpenAPI equality/schema and wheel/source build/archive checks successfully.
The protected HTML index passed active-content, local-link and permission checks;
not browser/layout validation. Dependencies/lock unchanged; no complete
controlled-provider suite or CI. Publication uses `[skip ci]` because the suite's
controlled-inference exception is not approved. Required next decisions are CrewAI
version/traffic approval and explicit controlled-suite exception approval, not
replaying finished traffic. Independent audits are complete, no live workstream
remains active. Latest native storage rerun: 29 passed, one upstream warning,
28.62 seconds; see `VALIDATION.md` for the publication checks/cleanup commands.

## Earlier implementation checkpoint — superseded by October 10 results

The following sections preserve historical failures, proposed gates and exact
resources. Their pending/running statements describe those earlier checkpoints,
not the finished recovery above. No historical unused traffic allowance may be
reused. Remaining gates: CrewAI version/lease choices; controlled-provider
suite/CI exception approval; designated ADR review; trace-scorer and genuinely
live-child cleanup-failure hardening; serverless worker OAuth.

The follow-up request is to fix and fully test evaluation, and validate CrewAI
both as a local HTTP agent and a deployed Databricks App. Three active workstreams
cover native evaluation process ownership, the protected recovery harness, and
isolated CrewAI preparation. Inspect the working tree before continuing; none of
this checkpoint establishes a finished fix, successful live recovery or CrewAI
deployment.

The user's subsequent “ok go ahead and fix and fully test” confirms proceeding
with the separately proposed **1,103-attempt** LangGraph/OpenAI recovery bounds
below. Execution remains held until child-side attempt accounting, native storage
regressions and independent review pass. This does not authorize replaying the
original failed lease or expanding its bounds. CrewAI is a separate lease: exact
App/resource selection and new traffic bounds still require confirmation before
deployment or model calls. The existing controlled-provider suite also requires
its own explicit exception approval; no such suite has been run in this resumed
implementation turn.

CrewAI preparation directory:
`/private/tmp/evalsurge-crewai-preparation-20261009.g9DGi2`.
Recovery candidate directory:
`/private/tmp/evalsurge-app-quality-recovery-20261009.r4c3jk`.
Neither directory is evidence of completed live validation.

Latest resumed checks: both retained Apps report running through the selected
`e2-demo-field-eng` profile; these metadata reads invoke no model. Ruff (192
files), OpenAPI equality/schema checks, build/archive verification and 33 setup/
authentication regressions pass. Revised native storage tests retained 50 exact
feedbacks and structurally transferred traces, but two cleanup checks failed
(14 passed); outside-sandbox retry leaves the timeout check failing. Core repair
and fresh regression verification remain in progress. The recovery harness passes
16 network-forbidden schema/storage checks and treats incomplete accounting as
unknown, not a verified attempt upper bound. No recovery traffic has been released.

CrewAI preparation verified the official **1.15.26** wheel (SHA256
`2abedcdc941d68940f48aa1a262e8ab036b9ecc05cb0cc44999d68f9832a0a58`)
and inspected its source, superseding the earlier 1.15.25 preparation only.
No dependencies were installed and no Crew/App inference ran. Public index
resolution remains connection-refused. Its OpenAI `>=2.30.0,<3` and Pydantic
`>=2.11.9,<2.13` constraints require a separate agent environment. Native
`BaseLLM` throttle retries are independent of `Agent.max_retry_limit`; the sample
two-call guard bounds dispatches but is not proof of retry-free execution.
The initial protected `/invoke` candidate does not fit the current App SDK
protocols. A follow-up now prepares a genuine native MLflow AgentServer
`/responses` compatibility recipe in the same private directory. It needs no
Lakebase, but current Databricks docs label this server legacy and recommend
DurableAgentServer for new agents; do not claim preferred-runtime coverage.
Native event-schema and intentional invalid-input checks passed without inference
using the runner's existing dependencies, not an installed CrewAI environment.
Official-index joint resolution still fails with connection refused, including the
required outside-sandbox retry. No CrewAI dependency install, actual Crew import,
model call or deployment has occurred. The proposed App is
`test-eval-crewai-1009` on explicit profile `e2-demo-field-eng`, using only
`MODEL_SERVICE system.ai.gpt-oss-120b` with `EXECUTE`; exact resource/protocol and
the separate 48-agent/28-judge (76 total) traffic lease remain pending approval.
Do not deploy before compatible dependency verification, fabricate Runtime
compatibility or silently provision Lakebase.

## Historical October 9 diagnosis and then-pending recovery gate

User wants successful load metrics and complete evaluations for both Apps.
Offline native-MLflow storage testing with the same 50 saved real captures
reproduced defaults retaining 19/50 with connection-pool/tag/assessment failures.
Actual process-owned serial settings retained 50/50. A final fresh check with
async/batch export disabled retained 50 exact durable current-run feedbacks per
check (two code checks), with 100 legitimate native scorer-owned span scopes, no
pool/tag/assessment/export/refresh failures and three other warnings. Independent
SQLite audit confirmed exact selection membership and source-run metadata.
Zero agent/judge/network calls; no provider/model substitution. This is storage
verification, not successful real-model judging.

Final receipt: `/private/tmp/evalsurge-eval-serial-verified-20261009.AdfokN/receipt.json`.
An intermediate stricter check failed its absent `Assessment.run_id` property
assertion despite retaining 50 scores/check; preserve its failed receipt. Final
verification uses exact `mlflow.assessment.sourceRunId` metadata.

Nested SQLite sessions reproduce pool exhaustion. ContextVars do not configure
native MLflow `os.environ` reads; async exporter state is cached at initialization.
Use a fresh owned process with real serial/synchronous/nonbatch flags before
native imports. Do not mutate parent global environment, patch packages, blindly
raise pool limits or fabricate target traces. Capture-trace staging alone leaves
judge-autotracing concurrency risks. Core isolation remains unimplemented and
designated review pending. See [diagnosis](EVALUATION_STORAGE_DIAGNOSIS.md) and
[proposed ADR 0013](adr/0013-native-evaluation-process-ownership.md).

The recovery proposal was subsequently approved as recorded above, but is
**not executed yet**. Its exact one-use bounds: LangGraph saved captures rejudged
(300 judge attempts, zero
target/readiness), then OpenAI App original concurrency-five/180-second/500-attempt
load + excluded probe (501 agent + 302 judge attempts). Total new ceiling 1,103,
separate from old 552; exact existing profile/Apps/real models/budgets below.
Preserve original failure; derive supplemental plan/store with explicit lineage.
Require exact durable coverage for both criteria and retain false verdicts.
Never replay original harness or consume its unused allowance automatically.

No dependency/core evaluator/deployment/commit/push/new paid-call changes occurred
during diagnosis. Prior dirty source/tests are preserved; diagnosis, ADR and doc
additions are uncommitted.

Post-documentation Ruff lint/format (187 files) and `git diff --check` passed.
No controlled-provider pytest suite or CI was run. Fresh recovery harness
preparation is offline-only; consult its pending-consent plan before execution.

## Historical October 9 larger App lease — stopped, do not replay

Repository still `main`, HEAD `a4e9408c6d642dd5e20d4545e638f08f167d3d49`.
The existing eight tracked modifications and untracked
`tests/test_local_helper_canary_setup.py` are preserved; this new validation
record is uncommitted/unpushed. No core fix or dependency update was made.

After the earlier four-call canaries, the user explicitly approved larger
sequential tests on exact profile `e2-demo-field-eng`, workspace
`1444828305810485`, unchanged Apps `agent-bricks-es-lg-1008` and
`agent-bricks-es-oai-1008`. Per App: local runner, concurrency five, <=180 dispatch
seconds or 500 measured attempts, one excluded probe, no extra warmups. Agent
`system.ai.gpt-oss-120b`, <=512 output tokens, zero target/model retries.
Ten synthetic refund-policy cases with authoritative references; explicit
relevance/correctness, <=50 captures per scorer. Judge `databricks-gpt-5-4-mini`,
<=2048 output tokens, 60-second timeout, two quality retries and zero readiness
retries. Total approved ceiling 1,606 model transport attempts; stop on failure.

LangGraph run `2b28bf04-bc4c-40f7-95f4-8a3beedebdc5` passed **500/500 load**,
zero load errors, configured/observed concurrency 5/5. Latency p50/p95/p99:
1154.21/1171.63/2161.67 ms; throughput 4.173 requests/second; dispatch/elapsed
including drain 118.61/119.82 seconds. Inference/both judge preflights passed.
Lifecycle `completed_with_gaps`, evaluation `completed_with_errors`:
**13 passing correlated relevance scores of 50 selected, 1 backend error,
36 missing assessments**. Correctness post-load judging was skipped by fail-fast.
The 13/13 available scores are not complete quality coverage.

App counters establish 501 agent model attempts / 501 completed Responses;
judge transport telemetry 51 HTTP attempts, all HTTP 200 (2 readiness + 49
quality). **552 total observed model transport attempts**, not billing receipts.
Typed status/result/waited/retrieved reports and all 500 journal rows/five pages
agreed; probe excluded. SDK closed, worker PIDs 75541/75414 absent, no App handlers
remained. OpenAI was **never started**. No model calls were made during diagnosis
or rendering, no fixtures/fallbacks or deployment/resource changes occurred.

Independent saved-evidence audit confirms incomplete native MLflow persistence/
correlation. It does not prove SQLite locking, an autotracing race, auth failure
or malformed judge body. Exact underlying exception class was not preserved;
private harness logging suppressed warnings. Native evaluation returned partial
evidence, not a confirmed evaluation-wide thrown exception.

Protected root: `/private/tmp/evalsurge-app-load-quality-20261009.0099be`.
`gate-receipt.json`, `langgraph/{status,result,report,waited-report}.json`, captures,
five report pages, native SQLite/artifacts and judge telemetry remain private.
Offline `reports.html` / `langgraph/report.html` were generated with zero external
calls, escaped content and 0600 permissions inside 0700 directories. Renderer
and repository Ruff lint/format (185 files), whitespace, offline HTML link/coverage/
no-active-content and recursive permission checks passed; browser/layout was not
verified. Never rerun the one-use
`run_load_quality.py --execute-approved-load-quality-lease` or overwrite evidence.

Next: separately scope diagnosis/fix with content-free exception-class/persistence
diagnostics, inspect native MLflow concurrency/local-store behavior, and obtain
any controlled-inference test exception approval. Then separately approve
quality-only judging of existing captures (no target reinvocation) and OpenAI
traffic. Do not reuse this stopped lease's remainder. App TTFT/token usage,
internal tracing/memory, notebook worker OAuth and CrewAI remain unresolved;
full-suite/CI and commit/push were not requested or performed by this lease.

## Historical October 9 resumption checkpoint

The following checkpoint predates the larger stopped lease above; its proposed
next budgets and absence of quality evidence describe that historical state.

Resumed from the published October 8 checkpoint on `main`, HEAD
`a4e9408c6d642dd5e20d4545e638f08f167d3d49`, initially clean and synchronized with
`origin/main`. This follow-up is **uncommitted and unpushed**; inspect `git status`
for the current state. The original publication and live evidence below remain
historical records, not permission to spend their unused lease.

Working-tree checkpoint: eight tracked files modified (`VALIDATION.md`, the four
handoff/code-guide/hosted/serverless documents, both validation harnesses and
`tests/test_serverless_app_target_contract.py`); one untracked new regression,
`tests/test_local_helper_canary_setup.py`. Live traffic has finished and no more
model calls are authorized. Preserve these changes.

Three parallel workstreams completed:

- `local_helper_canary.py` now retains a private failed receipt for optional
  distribution/source/app-construction failures, before any agent starts. Each
  receipt is 0600 inside a 0700 directory; existing evidence is never replaced.
  New `tests/test_local_helper_canary_setup.py` covers the reproduced failure.
- `serverless_runner_app_target.py` now checks the exact selected workspace
  before OAuth retrieval and App discovery, with fixed stage-specific blockers.
  SDK construction itself can initialize metadata/authentication. The unchanged
  core profile/override/OAuth guards and independent worker check remain in force.
  This does **not** resolve the actual serverless worker-authentication blocker.
- Fresh read-only checks verified both retained Apps' immutable deployments,
  exact selected workspace/active identity, authenticated `/status` 200, model
  resource and four deployed source/wheel hashes. Before/after process-local
  handler/model counters were all zero. No invocation, deployment or store change
  occurred. Receipt: `/private/tmp/evalsurge-app-ready-20261009.HLxSpg/readiness-receipt.json`.

Exact CrewAI 1.15.25 official wheel access is now verified, with SHA256
`aea1282a2b5bf966e1a52a2937cc27e83bbb7daa5eeeb8104cf563c8ac3a8be6`.
Its public-index dependency-resolution dry run still failed with connection
refused, including an outside-sandbox retry. No package was installed, no version
changed and no Crew inference ran. The isolated environment remains empty.
Receipt: `/private/tmp/evalsurge-crewai-wheel-20261009.CzZe3b/dependency_receipt.json`.

The four focused no-inference test files passed together: **92 passed**. Tests
control metadata/authentication or raise setup failures; no agent/model completion
is substituted. See `VALIDATION.md` for exact commands and final static checks.
Full controlled-provider suite/CI was not run. Dependencies/lock remain unchanged.
Ruff lint/format, OpenAPI equality/schema, wheel/source build and asset checks
also passed. These are static/non-inference checks, not a full release validation.

The user subsequently approved the four-call canaries. Root owned execution after
the App workstream relinquished the unused lease. Both unified native-async direct
App runs passed: LangGraph `86ab5671-d173-423e-932d-691f8570ee12`, OpenAI Agents
`04f77c8c-0bd2-4e77-9c60-dd44d4e0e33e`. Each passed its excluded preflight and
one measured call at concurrency one; native before/after counters establish
**4 actual model attempts / 4 completed Responses total**, zero errors and zero
active handlers. Typed status/result/waited/retrieved reports agreed and SDK
contexts closed. Measured latency was 1458.41 / 1467.40 ms: wiring evidence only.
Profile/model/output/retry/evaluation bounds were unchanged, no fixture response
was substituted, and no deployment/resource configuration changed. Private
gate/report root: `/private/tmp/evalsurge-app-canaries-20261009.wQEzfS`.

Subsequent parallel read-only audits verified saved reports/results/status and
all four successful probe/measured journals. None of the four recorded worker
PIDs existed at the local check; evidence directories were 0700 and captured
evidence/receipts 0600 (gate script 0644 inside the protected root). Harness review
found no blocking regression. Documentation now distinguishes the public App
`/api/invocations` boundary from the internal model `/responses` route, corrects
the App matrix and constrains proposed CrewAI OpenAI dependencies to `>=2.30.0,<3`.
Fresh Ruff lint/format and whitespace checks passed. No extra inference, suite/CI,
install, deployment, commit or push occurred; this is not maintainer approval.

The four-call approval is **exhausted**. Next authority gate: a separately approved
short public-sample/API/cancel matrix, proposed **48 additional model calls**
(52 including these completed canaries), serial traffic, at most five users and
five measured attempts per positive run. Negative fail-fast checks are separately
labeled zero-model tests. Stop on failure without replay/fallback. Do not rerun
successful canaries automatically. No App TTFT/token-usage, trace, memory, quality,
capacity, CrewAI or notebook coverage is implied.
No classic compute, copied credentials, forwarding proxy, silent fixtures or
unreviewed authentication changes are authorized. No push is requested by this
resumption. Retained Apps/stores can continue incurring hosting/storage charges.

## Historical October 8 resume boundary

The user paused App load tests and requested publication of the current code/docs
checkpoint, with resumption intended for **October 9, 2026**. No automatic resume
or scheduled traffic is authorized. Read this file and `AGENTS.md` first; inspect
the repository state instead of assuming earlier session state remains current.

## Historical October 8 repository and publication

- Repository: `RamVegiraju/EvalSurge`; branch `main`.
- Implementation baseline before this checkpoint:
  `2276c3b4d6fa9943544f988df4e5ed658ad79365`.
- Checkpoint HEAD: the commit containing this file; obtain its exact ID with
  `git log -1 --format=%H -- docs/SESSION_HANDOFF.md` and current HEAD with
  `git rev-parse HEAD`. The final publication receipt supplies the exact pushed
  SHA rather than embedding a self-referential commit hash here.
- Publication is a checkpoint, not an independent maintainer approval or
  production sign-off. ADR 0012 remains proposed for designated review.
- Task changes and the requested real-inference disclosure policy are included;
  ignored `.isaac/`, credentials, raw reports and private cloud receipts stay out
  of source control. Do not reset or discard later working-tree edits.
- Use `[skip ci]` for this push: full CI uses controlled provider completions and
  needs specific user disclosure/approval. Do not trigger it on resumption
  without that approval. Existing scheduled workflow settings are unchanged.

## Historical October 8 completed work

- Preserved the existing unified v2 direct/remote SDK and `/v1` compatibility.
- Added the optional framework-neutral `evalsurge.serving` helper: customer-owned
  async handler, bounded unchanged input, completed output and untrusted
  request/case/run correlation/state labels. It is not authentication or memory.
- Added typed configured-versus-observed evidence capabilities to v2/CLI without
  new evidence calls; answer judging still needs no traces unless the selected
  scorer specifically requires them.
- Improved fixed preflight guidance and safe required-probe-trace failure
  handling, preserving one Locust engine and no target reinvocation by judging.
- Classified samples explicitly by runner location and target hosting:
  `local_runner_http_target.py`, `local_runner_databricks_app_target.py`, and
  `serverless_runner_databricks_app_target.py`. Notebook is a runner, not a host.
- Updated onboarding, contracts, source/evidence documentation and regression
  tests. Dependencies and lockfile versions/provenance remain unchanged.

## Historical October 8 actual inference

LangGraph and OpenAI Agents locally hosted HTTP targets passed the new native-
async direct/typed remote API × load/cancel/fail-fast matrix. The unchanged public
synchronous HTTP sample `main()` then passed separately for both frameworks.

- **60 physical model attempts / 60 completed Responses** across the new positive
  matrix and entrypoints, separate from four older canary calls.
- Profile `e2-demo-field-eng`; workspace ID `1444828305810485`;
  `system.ai.gpt-oss-120b`, `/ai-gateway/mlflow/v1/responses`, low reasoning,
  `store=False`, <=512 output tokens and zero model retries.
- Per positive run: one excluded probe plus five measured calls, max concurrency
  five, ten-second dispatch ceiling; 30-second model / 35-second handler /
  40-second benchmark attempt deadlines. Evaluation off; no planner/judges.
- Four unsupported-input fail-fast scenarios: rejected probe, zero model calls,
  load skipped. Not successful inference coverage.
- Active cancellation acknowledged and drained five already-dispatched calls;
  no claim of upstream abortion, cost rollback or suppressing an unissued backlog.
- Authentication, typed status/result/report agreement, retrieval and local
  lifecycle cleanup passed. No App/notebook/trace/memory/TTFT/quality claim follows.

Full run IDs, latency observations and protected report locations are in
`VALIDATION.md` and `docs/HOSTED_JOURNEY_VALIDATION.md`. These are functional
five-attempt smokes, not stable tail latency or sustainable capacity.

## Apps retained; load testing paused — October 8 historical checkpoint

Selected profile: **`e2-demo-field-eng`**, exact workspace:
`https://e2-demo-field-eng.cloud.databricks.com`.

| Framework | App | Latest ready deployment |
| --- | --- | --- |
| LangGraph | `agent-bricks-es-lg-1008` | `01f1c38db3f5165b98332e7c16cb1108` |
| OpenAI Agents | `agent-bricks-es-oai-1008` | `01f1c38db4281b698aaac4c5aa8e6761` |

App links and exact source hashes are in the hosted-journey record. Both reached
RUNNING, authenticated `/status` 200 and exact workspace/principal proof. Native
managed Runtime Stores opened. Model-only `MODEL_SERVICE`/`EXECUTE` resource
updates preserved unrelated settings. Store persistence is not configured
conversation memory; no tools/history/tracing/recovery are configured.

The newly allotted **52-call App lease used zero calls**. The App agent confirmed
no scenarios started, no model calls and no in-flight invocation/subprocess.
The last recorded counters were zero at readiness; they were not refreshed at
the pause. Apps/stores remain retained and can continue incurring charges.

Failed startup revisions remain failed and preserved: exact bare-host spelling
and a later unsupported `Config.custom_headers` getter were corrected without
relaxing identity checks. Readiness alone is not deployed inference success.
Protected root: `/private/tmp/evalsurge-native-apps-20261008.ZdVXL2`.

## Blocked and deferred coverage — October 8 historical checkpoint

These are the blockers recorded at publication. The October 9 checkpoint above
records subsequent exact CrewAI wheel retrieval and successful App canaries;
dependency resolution and notebook worker OAuth remain blocked.

- **Serverless notebook runner→App:** driver runtime OAuth passed, independent
  worker runtime OAuth failed. Corrected prerequisite run `526298221857181`,
  task `972949342784427`, environment 5/Python 3.12.3/SDK 0.146.0; zero inference
  and no deployed App tested. See `docs/SERVERLESS_RUNNER_STATUS.md`.
- A notebook calling an external EvalSurge API generates load at the API host.
  Hosting FastAPI inside the notebook does not fix independent worker OAuth.
  Public App binding is profile-only and rejects ambient auth/destination
  overrides. Portable worker OAuth needs ADR/maintainer review before traffic.
- **CrewAI:** exact `crewai==1.15.25` unavailable through current installer access;
  public PyPI connection refused, mirror stops at 1.15.23. Empty isolated env;
  no alternate version/source, Crew inference or Crew App deployed. Approved
  future name: `agent-bricks-es-crew-1008`.
- Classic compute is explicitly excluded. Historical notebook-hosted helpers
  remain diagnostics, not the advertised App target or a third hosting option.
- Native App token usage/TTFT, quality/judge recommendations, trace correlation,
  memory and full capacity remain outside this load-only checkpoint.

## Historical October 8 verification boundary

The publication record in `VALIDATION.md` lists final commands/results. Use
`uv run --frozen --no-sync` for the existing environment; do not accidentally
rewrite `uv.lock` through an unfrozen command. No new full controlled-provider
suite, new dependency sync/update or live model calls are implied by static
checks. Full-suite/remote CI evidence for baseline `2276c3b` predates this code.

When separately approved, required full checks remain the commands in `AGENTS.md`:
locked agents/dev sync, Ruff lint/format, complete pytest, OpenAPI equality plus
schema validation, and wheel/source build. Preserve failed live receipts.

## Original October 8 resumption plan (superseded by October 9 checkpoint above)

1. Inspect branch, HEAD and working tree; read the validation/ADR records. No
   agent is currently running live traffic. Ask for resume direction, do not
   spend a historical lease automatically.
2. For Apps, recheck exact selected identity/workspace/source/readiness and old
   counters without inference. Confirm a new bounded lease and run one probe+
   one measured canary per framework before five-attempt direct/API/cancel runs.
   Preserve failures; no replay, fallback or silent fixtures.
3. Resolve CrewAI release access or obtain an explicit alternative-version
   decision before installation/deployment/inference.
4. Review worker-portable OAuth separately; verify both driver and worker without
   inference before any serverless→App smoke. No copied tokens/guard bypass,
   forwarding proxy, new identity/secret or classic-compute fallback by inference.
5. The October 9 follow-up hardened both dormant harness details: optional-distribution
   setup is inside safe receipt handling in `local_helper_canary.py`; serverless
   harness verifies profile workspace before App discovery and separates safe auth/discovery
   diagnostics. Focused no-inference checks passed. Later separately approved
   App canaries completed as recorded in the October 9 checkpoint above; local
   HTTP and notebook live execution was not repeated.
6. Integrate actual App/notebook/Crew receipts and retrieve protected reports.
   Later quality/trace/streaming/capacity work needs its own models, budgets,
   explicit measurement semantics and ADR/maintainer review.

Do not promise automatic conversation compaction or a timed restart. This file
is the durable repository context; local `/private/tmp` reports can expire and
must not be exported or committed as public source.
