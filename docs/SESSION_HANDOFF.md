# EvalSurge session handoff — October 8, 2026

## Resume boundary

The user paused App load tests and requested publication of the current code/docs
checkpoint, with resumption intended for **October 9, 2026**. No automatic resume
or scheduled traffic is authorized. Read this file and `AGENTS.md` first; inspect
the repository state instead of assuming earlier session state remains current.

## Repository and publication

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

## What was completed

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

## Completed actual inference

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

## Apps retained; load testing paused

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

## Blocked and deferred coverage

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

## Verification boundary

The publication record in `VALIDATION.md` lists final commands/results. Use
`uv run --frozen --no-sync` for the existing environment; do not accidentally
rewrite `uv.lock` through an unfrozen command. No new full controlled-provider
suite, new dependency sync/update or live model calls are implied by static
checks. Full-suite/remote CI evidence for baseline `2276c3b` predates this code.

When separately approved, required full checks remain the commands in `AGENTS.md`:
locked agents/dev sync, Ruff lint/format, complete pytest, OpenAPI equality plus
schema validation, and wheel/source build. Preserve failed live receipts.

## Safe order for the next session

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
5. Harden two dormant harness details: optional-distribution setup must be inside
   safe receipt handling in `local_helper_canary.py`; serverless harness must
   verify profile workspace before App discovery and separate safe auth/discovery
   diagnostics. These have not been implemented in this checkpoint.
6. Integrate actual App/notebook/Crew receipts and retrieve protected reports.
   Later quality/trace/streaming/capacity work needs its own models, budgets,
   explicit measurement semantics and ADR/maintainer review.

Do not promise automatic conversation compaction or a timed restart. This file
is the durable repository context; local `/private/tmp` reports can expire and
must not be exported or committed as public source.
