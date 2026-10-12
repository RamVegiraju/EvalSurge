# EvalSurge session handoff — October 12, 2026

## Current checkpoint: reviewed local wheel and four real-model smoke cells

The current milestone is **local Python load generation** against either a hosted
HTTP agent or a separate Databricks agent App. Direct execution needs no separate
EvalSurge API server. Notebook and App-based load generators are deferred; retain
their sources, stopped resources, diagnostic deployments and failed evidence.
The older checkpoints below remain historical and must not be mistaken for the
current scope or current-artifact validation.

### Repository state and ownership

- Branch: `main`.
- Base commit for this checkpoint: `1089553d58c69f368e31447e4ec1e1d0cc1848fd`.
  Inspect `git rev-parse HEAD` for the final integration commit.
- Tracked and untracked changes are substantial and intentionally preserved;
  inspect `git status --short` before any integration. Do not reset, discard or
  blindly stage unrelated user/team work.
- Source/project/OpenAPI version: **`0.2.1.dev2026101202`**.
- This checkpoint records the pre-push evidence; confirm the final commit/push
  from Git and remote CI from its actual run status, not this document.
- The user subsequently requested repository cleanup and a push. GitHub identity
  `RamVegiraju` matches the personal `origin`. On October 12 the user explicitly
  approved the disclosed controlled-inference CI triggered by the push:
  `.github/workflows/ci.yml` runs the full provider-fixture suite. Keep those
  results separate from real-model validation; do not disable CI or add a skip
  marker. This approval authorizes no new live traffic or package publication.
- A newly appeared untracked `docs/PRODUCT_DESIGN_BRIEF.md` is outside the reviewed
  snapshot and deliberately excluded from the integration commit, not discarded.
  Its associated three-line README link is also left unstaged, preserving both
  local edits without publishing a dangling documentation link.
- Retain the real-inference/disclosure policy in `AGENTS.md`: controlled provider
  responses are not real-model coverage; new paid traffic needs exact selected
  resources and bounds, and must never silently fall back to fixtures.

Completed implementation/onboarding work preserves the unified `RunCreate`,
operator-owned target/authentication bindings, one Locust engine and evaluation
off by default. `[local]` is now an install alias for the unchanged `[server]`
dependency surface. The ordinary `venv`/`pip`/Python quickstart shows `Agent.http`
and `Agent.databricks_app`, the same workload and `format_summary(report)`.
Framework dependencies belong in a separate agent environment. Examples are not
installed by the wheel. The six local framework/hosting labels are an inventory,
not six successful live journeys; CrewAI remains blocked.

### Select this frozen artifact, never overwrite it

Reviewed artifact directory:

```text
/private/tmp/evalsurge-local-only-20261012.D2MG3y/reviewed-build/
evalsurge-0.2.1.dev2026101202-py3-none-any.whl
SHA256 a1a58a4513c4659aee41f9c5570bbcca6da371b4b185b629e7842be4eac23285
evalsurge-0.2.1.dev2026101202.tar.gz
SHA256 dcd50eca53f0fde1755643f5adbcd0795b5abe2eee744d0c46b3041a9bf04f3f
uv.lock SHA256 d550a74cb1a010c70a3480f10a88bdb98bc9935bbdd1e58baf104910f299d7ff
```

Both archive checks passed. All **189 non-editable lock records** are unchanged;
only project version/extra metadata changed. A new latest-compatible resolution
or public publication was not established. Earlier draft artifacts and final
dev1201 artifacts remain preserved, but are not this reviewed wheel. The frozen
candidate predates final documentation-only changes; do not rebuild under its
existing filename/version/hash to make the docs metadata appear newer.

Fresh **pip** installation verified base, `[local]` and `[server]` outside the
checkout, plus sample `--help` and installed import/request/CLI checks, with zero
agent/model dispatches. Required dependency hashes and the explicitly approved
package source were retained; `public_index_install_established=false`.
Provenance is under `.../pip-reviewed-install/{base,local,server}/provenance.safe.json`.
The separately verified persistent runner is
`/private/tmp/evalsurge-local-only-20261012.D2MG3y/runner`;
`.../pip-runner-evidence/provenance.safe.json` records manifest SHA256
`78fddb42a68c09a748deb3fa657a53680b63f8afe373f49143aef1106da40db4`.
`pip check` passed. These are macOS installed-package results, not Linux/App or
public-index installation claims. Do not put internal package-index URLs in
customer-facing docs or relabel their artifact provenance.

### Fresh live results from that exact installed wheel

Explicit selection: profile **`e2-demo-field-eng`**, workspace
`https://e2-demo-field-eng.cloud.databricks.com`, model
**`system.ai.gpt-oss-120b`**, MLflow Responses
`/ai-gateway/mlflow/v1/responses`. The local HTTP cells used the current helper
with an actual LangGraph graph and OpenAI Agents Runner. App cells invoked the
existing older managed deployments `agent-bricks-es-lg-1008` and
`agent-bricks-es-oai-1008`, not stand-ins. No inference was stubbed or retried.

Every positive cell used one excluded readiness probe plus one measured request,
concurrency **1**, **10 s** dispatch ceiling, **40 s** request timeout,
**35 s** handler / **30 s** model deadline and at most **512** output tokens per
call. Evaluation was **off**; no planners/judges/tools/memory ran. The four results:

| Hosting / actual framework | Run ID | Measured latency | Outcome |
| --- | --- | ---: | --- |
| HTTP / LangGraph | `8177940b-259d-4516-aac3-22eaed70af92` | 666.392 ms | Completed, 1 successful request |
| HTTP / OpenAI Agents | `9c58618b-4382-46e0-9fc9-23e26b431676` | 435.451 ms | Completed, 1 successful request |
| Existing App / LangGraph | `f4ea3175-34f0-404d-94af-96556a3363ac` | 1371.096 ms | Completed, 1 successful request |
| Existing App / OpenAI Agents | `e0c5e19f-e081-44af-9a1a-361a49b70987` | 1441.589 ms | Completed, 1 successful request |

Error rate was **0** for each. Typed status/result/report agreed, the content-free
summary rendered, the SDK closed and the runner was reaped. HTTP agent lifespans
and listeners closed. Journals drained without writer failures/backpressure and
reports recorded `measurement_complete=true`. Each HTTP cell recorded **2 actual
outbound attempts / 2 completions**, two target receipts and zero final in-flight
requests. Exact post-run App counters confirmed **2 handler/model attempts / 2
completions per App**, zero errors and unchanged deployed source. Final App
compute cleanup is pending confirmation; do not treat successful response
receipts as a compute-stop claim.

Safe consolidated evidence: `.../milestone.safe.json`, tied to the reviewed wheel
hash. HTTP live ledger: `.../ledger.0002.safe.json`. Safe receipts and protected
reports are in `langgraph`, `openai-agents`, `app-langgraph` and `app-openai`
subdirectories. Protect reports/prompts/answers; inspect safe projections instead
of printing their contents into a new thread.

Two additional **intentional pre-provider failure** checks passed: one unsupported
input probe per real HTTP framework, `target_http_error`, measured load skipped,
metrics absent, empty report rows, **0 provider attempts / 0 completions**,
consistent retrieval and complete SDK/agent/listener/runner cleanup. They used no
stubbed response and are not successful model inference. Evidence:
`.../fail-fast.ledger.0002.safe.json`, `fail-fast-langgraph/receipt.safe.json` and
`fail-fast-openai-agents/receipt.safe.json`. The native-App sentinel
`__evalsurge_fail_preflight__` is **not** a local-handler failure control; sending
it locally would invoke a model. Preserve all earlier negative/timeout evidence.

Traffic accounting is one unchanged approval: **36 targets / 48 model calls**.
Old conservative usage **6 / 4** plus fresh HTTP positives **4 / 4**, HTTP
fail-fast **2 / 0** and App positives **4 / 4** totals **16 / 12**. Remainder
**20 / 36** is not renewed or automatic dispatch consent. No judge or active
cancellation traffic occurred at this checkpoint.

### Measurement honesty and remaining work

One request per cell is a smoke, not a tail/capacity benchmark. Nonstreaming
contracts have no answer TTFT/first-event measurement. HTTP token coverage was
**100%**; native App token coverage **0%**. Generator health is **`unknown`**.
Observed maximum hub lag was HTTP **19.479 / 27.667 ms**, App
**355.680 / 381.544 ms** (LangGraph/OpenAI Agents). Those substantial App
scheduling observations prohibit a zero-overhead or measurement-accuracy
certification. There is no simultaneous server-only timing/trace establishing
transport/authentication/scheduling contributions.

Next focused work, requiring the relevant approval rather than automatic traffic:

1. Review/integrate preserved changes and run final no-inference documentation,
   Ruff, diff, OpenAPI and artifact-hash checks before any requested commit/push.
2. Clear CrewAI's security and truthful native deployment gates before HTTP/App
   real-inference validation. Official OSV metadata confirms ChromaDB
   `PYSEC-2026-311` through **1.5.9**; CrewAI's `~=1.1.0` constraint cannot clear it.
   Isolated compatibility installation is not security/live-inference approval.
3. Validate current public native `agent_apps/` templates separately. Existing
   older deployments prove SDK interoperability only, not their deployment.
4. Add current-artifact captured-answer judging/trace evidence, App fail-fast,
   active cancellation/drain, full tutorial traffic and broader generator-overhead
   measurements with explicitly approved bounds. Do not imply earlier journal
   implementations' live results validate this exact artifact.

Final App cleanup is confirmed in
`/private/tmp/evalsurge-target-readiness-20261012.RxUvhu/cleanup_complete.json`:
both targets were **STOPPED / UNAVAILABLE** at **2026-10-12 17:23:32 UTC**, with
deployment IDs and resources unchanged. Provider counters reconcile to two
actual completed calls per App. No source, resource, grant or profile was deleted.

Notebook/App-based load generation, remote CI/public publication/other platforms
remain deferred or unverified. `load-test`, volume/grants, diagnostic source and
the App-side registry **HTTP 403** evidence below stay preserved; no resource
deletion is implied by deferral. No Lakebase is needed for this runner milestone.

### Verification: live, controlled and no-inference boundaries remain separate

The first full controlled run retained **1 failed / 1,777 passed / 42 warnings
in 327.76 s**. Its stale base-CLI install-extra assertion was fixed. Final full
suite: **1,782 passed / 42 warnings in 332.74 s**. These approved controlled
provider/native SDK regressions are not real-model evidence. Pure schema/docs/
source checks: **100 passed in 0.14 s**. Scoped README checks: **5 passed /
1 controlled SSE test deselected in 0.05 s**. Ruff lint/format, diff checks,
OpenAPI equality/schema validation, both archive checks and fresh pip install
verification passed. See [VALIDATION.md](../VALIDATION.md) for boundaries.

Final integrated docs/README pure checks: **105 passed / 1 controlled test
deselected in 0.77 s**. The first final-doc attempt was **1 failed / 104 passed**;
a stale older-wheel wording guard was corrected to check the four evidenced and
two blocked rows. Ruff/OpenAPI/diff and unchanged artifact/lock hash checks passed.
No additional inference, commits, pushes, publication or artifact rebuilds ran.

Push-preparation recheck: public registry/artifact origins verified for all **189
locked packages**; **105 pure tests passed / 1 controlled test deselected in
0.16 s**; Ruff lint and `git diff --check` passed. No internal registry hostnames
were found in README, docs, examples, workflow, project metadata or lockfile.
Deferred cloud-runner sources and historical failure evidence are intentionally
preserved rather than deleted as cleanup. Official OSV metadata was rechecked:
`PYSEC-2026-311` is not withdrawn and its ChromaDB affected range ends at
`last_affected=1.5.9`; no package installation or inference was performed.

No-inference documentation/source slice to rerun after final edits:

```bash
uv run --frozen --no-sync pytest -q tests/test_runner_target_examples.py tests/test_unified_journey_examples.py tests/test_framework_runner_matrix.py
```

## Historical checkpoint: App registry access denied; workspace-ID repair isolated

The approved disabled runtime deployment did run on October 12 using only
`e2-demo-field-eng`, but failed during package installation before startup,
authentication, claims or inference. Deployment
`01f1c652cda714069d6c96824b266369` used the unchanged
`0.2.1.dev2026101101` wheel. Pip saw no candidate for
`aiohappyeyeballs==2.7.1`. A later compute start automatically retried that same
disabled install (`01f1c6574977153cac57393c71c05ad9`) and failed identically.
All consent flags remained false and the target source remained unverified.

A temporary stdlib-only registry diagnostic was separately uploaded/deployed to
the same `load-test` App, with no EvalSurge execution, dependency installation,
native credential forwarding, agent calls or model responses. Deployment
`01f1c65755671dada48e5ed6f32e9555` succeeded and recorded **Python 3.11.17/Linux**,
approved-index **HTTP 403**, pip exit 1/no matching distribution, and no pip TLS
verification error. This establishes denied App-side index access, not which
registry/network policy layer denied it. The package is advertised to the laptop
with the retained expected hash and requires Python >=3.10; do not downgrade or
change registries to hide the access problem. Registry/platform coordination is
required before retrying the complete hash-pinned runtime installation.

The diagnostic compute was stopped and a final exact-profile read confirmed
`STOPPED` / `UNAVAILABLE`; its App, source snapshots, grants and volume are
preserved. Logs and the safe failure receipt are retained privately under
`/private/tmp/evalsurge-disabled-app-20261012.9raKwr/`. Diagnostic source is
`/private/tmp/evalsurge-registry-probe-20261012.12DM4c/` and its unique workspace
upload is recorded in the safe receipt. Do not count the diagnostic deployment
as an installed EvalSurge runner, successful OAuth or a live matrix cell.

Deployment applied/verified the runner's exact target `CAN_USE`, volume
`READ_VOLUME` / `WRITE_VOLUME`, and parent `USE_SCHEMA` / `USE_CATALOG`. Existing
inherited catalog administration remains; storage is not owner-only. No Lakebase
is needed. Zero target/model/judge calls, approval claims and benchmark exports
occurred; the aggregate 36-target/48-model ceiling is unchanged. CrewAI remains
blocked by its advisory/tooling gates; notebooks remain deferred.

SDK source diagnosis also found that Apps injects `DATABRICKS_WORKSPACE_ID`,
which the old native guard rejects. The focused repair preserves a private,
canonical positive numeric `workspace_id` through operator settings and workers,
requiring exact actual/detached/SDK agreement rather than stripping metadata or
weakening profile guards. The sample now uses the same canonical 1–20 digit
validation and forwards the ID. ADR 0019's **October 12 amendment still requires
explicit designated maintainer acceptance before deployment/live arming**; the
original contract's approval is not this amendment's approval.

The changed runtime/source metadata is now `0.2.1.dev2026101201`; for this repair
only the editable project version changed in the lock, not dependency versions,
hashes or origins. Both older wheels and their evidence are preserved. The final
wheel is retained at
`/private/tmp/evalsurge-final-workspace-id-20261012.5ObgZ5/dist/evalsurge-0.2.1.dev2026101201-py3-none-any.whl`,
SHA256 `015d19b580d3e5338ce15f349175b194d67bf702d49f598e9a3f69bd457530dc`.
Archive checks and fresh isolated base/server installations passed with locked
hashes through the approved source, with zero agent/model/cloud/timing dispatches.
Private installation provenance is under that artifact directory's `install/`.
This verifies macOS installation, not the blocked Linux/App install or real-model
journey. The pre-documentation build/provenance under
`/private/tmp/evalsurge-workspace-id-20261012.LTOOfA/` is also preserved; all **60**
runtime members match the final wheel, but final distribution README metadata
differs. Select the final hash above, never interchange the two hashes. The final
source snapshot is under the final artifact directory's `source/`, with its hash
retained in the external build receipt rather than a self-referential archive.

Verification: full controlled suite **1,765 passed / 42 warnings in 299.81 s**;
focused auth/sample/version **192 passed in 0.78 s**; approved-source install
contract **5 passed in 35.57 s**; final pure README checks **5 passed / 1 controlled
SSE test deselected in 0.05 s**. Ruff, OpenAPI equality/schema, archive checks and
diff checking passed. Preserve the earlier **228 passed / 1 failed** cache-only
install slice and the initial offline build-backend cache miss. Controlled
provider completions/native SDK replies and NON-agent timing checks were disclosed
and approved; none establishes new live inference or latency accuracy. Exact
commands/boundaries are in `VALIDATION.md`.

Next: obtain amendment acceptance and
approved-index access from the App; recreate a disabled stage from the new wheel
with the exact workspace ID; verify target/source readiness; then arm only the
remaining approved bounded real-model smoke, retrieve both protected exports and
verify cleanup. Do not enable the old failed stage. No commits or pushes were
performed; preserve the substantial tracked/untracked working tree.

## Designated maintainer approval received; disabled deployment next

Historical checkpoint before the failed deployment recorded above.

After the explicit request for `@RamVegiraju`'s approval of ADRs 0017/0019 for
private `load-test` deployment, the user confirmed "yes go ahead". Record this
as designated maintainer acceptance of the private validation contract, not
independent security review or production approval. The retained aggregate traffic
ceiling is unchanged. Proceed disabled-first in the selected `e2-demo-field-eng`
profile; verify installation, exact grants and target source before live arming.
No new live result is established by this approval.

## Predeployment review: bundle environment bug fixed; human review still required

Historical checkpoint before original-contract approval and deployment.

The continuation's independent AI review found no new native runner source blocker,
but actual CLI `1.17.0` bundle validation reproduced a deployment wiring bug:
`config.env[].valueFrom` was ignored with a warning, dropping the export-volume
resource reference. Both App runner bundle templates and the disabled private stage
now use bundle `value_from`; runtime `app.yaml` correctly retains `valueFrom`.
Static regressions distinguish these contracts. The corrected selected-profile
bundle validation resolves the exact target and volume with no casing warning.
Ten focused static tests passed; Ruff lint/format and `git diff --check` passed.
No inference fixture was selected or substituted, and the full runtime suite was
not rerun for this template/documentation-only correction.
The runtime wheel is unchanged; no new artifact/version is implied by this YAML fix.

Fresh October 12 reads confirmed `load-test` remains stopped, without resources or
deployment. Runner access is the selected operator plus inherited `admins`
`CAN_MANAGE`; the target has no runner grant yet. Existing inherited catalog
administration remains unchanged. No deployment, grant, start, source upload,
target/model/judge call, report upload, commit or push occurred.

The user's general "review and go ahead" authorizes continuation, but is not a
record of designated human maintainer review. ADRs 0017/0019 remain proposed.
Obtain explicit review approval for those contracts from the designated maintainer
(`.github/CODEOWNERS`: `@RamVegiraju`) before deploying the changed native runner.
AI review does not establish independent human/security sign-off. Then proceed
disabled-first, retaining the existing live prerequisites and aggregate ceiling.

## Artifact volume provisioned; native runtime deployment still gated

Historical provisioning checkpoint; the later runner grants are recorded above.

The user explicitly approved
`ram_artifacts.evalsurge_validation.runner_artifacts`. On October 12, using only
the selected `e2-demo-field-eng` profile, the dedicated schema and managed volume
were created with the selected operator as owner. Direct schema/volume grants
are empty. Effective volume permissions preserve the existing catalog
administration principal's inherited `ALL_PRIVILEGES` and `MANAGE`. The general
account group has only catalog `BROWSE`, not report-reading access. Do not label
this storage owner-only, revoke parent administration or change unrelated grants.

A disabled standalone native runner is staged locally at
`/private/tmp/evalsurge-app-stage-20261012.zJQDqB/`, containing the unchanged
reviewed wheel, the approved volume and `load-test` binding, and an expired,
disabled LangGraph-target configuration. Both runtime configurations explicitly
select `operator.json`. The target source revision remains deliberately unverified;
all three live-consent flags are false. Native configuration construction, wheel
SHA256 and runtime-config agreement passed without SDK/network/model calls.
The safe provisioning receipt is `provisioning.safe.json` in that directory.

No runner permissions, source uploads, App deployments/starts, report uploads,
target attempts, model calls or judge calls occurred. The volume is not a passed
benchmark cell. Designated maintainer review of ADRs 0017/0019 remains required
before deploying the changed native runtime. Then verify the disabled installation,
exact runner/target permissions and ready target source before separately bounded
traffic. Notebook work remains deferred; CrewAI retains its independent gates.

## Historical scope change: local and dedicated App runners; notebooks deferred

The user deferred serverless notebook validation on October 11 because it was
delaying the milestone. Validate installing EvalSurge locally and on the dedicated
`load-test` Databricks App instead. The target agent remains separately hosted
at an HTTP endpoint or on an agent App; no separate benchmark-submission API
server is required. Preserve notebook source and historical installation/OAuth
failures, but do not require notebook credentials or run notebook workloads now.

The active matrix is **twelve** cells, four per CrewAI/LangGraph/OpenAI Agents:
local→HTTP, local→App, runner App→HTTP and runner App→App. Three former
notebook→App cells are deferred. Two older-wheel local→HTTP basic smokes passed;
ten active cells remain pending, and no current native-auth cloud success is
established. Keep all historical fifteen-/eighteen-cell accounting below intact.
The approved aggregate ceiling remains **36 target attempts / 48 model calls**,
not a new lease; consult the retained private ledger before dispatch.

Catalog **`ram_artifacts`** is user-selected. The October 12 checkpoint above
records the subsequently approved schema/volume and its inherited administration;
the October 11 documentation change itself created no schema/volume or grants.
The stopped `load-test` shell
can use its platform-injected service-principal OAuth for explicit native
App-runtime mode. This route does not need a notebook profile/token or Lakebase.
Deployment, live independent worker OAuth, protected export, the CrewAI advisory
gate and designated maintainer review remain pending. Do not delete resources,
deploy or expand traffic merely to implement this documentation scope change.

Fresh October 11 read-only metadata in `e2-demo-field-eng` confirmed `load-test`
is `STOPPED` / `UNAVAILABLE`, with no active deployment or declared resources.
URL: `https://load-test-1444828305810485.aws.databricksapps.com`.
Runner service-principal client UUID:
`c6a6a61f-14d4-4123-9146-225e6aac6ec6`.
Both targets `agent-bricks-es-lg-1008` and `agent-bricks-es-oai-1008` are also
`STOPPED` / `UNAVAILABLE`; retained `SUCCEEDED` deployment records are not current
App readiness. Zero target/model calls, starts, deployments or grants ran during
this read-only check. See [the exact metadata/evidence record](LIVE_MATRIX_RESULTS.md).

## Native App authentication implementation verified; cloud validation pending

The changed checkout is now uniquely versioned `0.2.1.dev2026101101`; metadata,
README/install/App-runner artifact references and OpenAPI were updated together.
The original frozen `0.2.1.dev20261011` wheel and its two real-model HTTP results
remain unchanged and do not validate the new runtime. Proposed ADR 0019 records
the explicit native App-runner authentication contract before implementation.
Named-profile guards and the retained, deferred notebook portable-M2M gate remain separate.

Independent review corrections are implemented: secret-free static diagnostics
recognize explicit native mode, and configured/SDK-discovered origins reject
controls/DEL/backslashes and other invalid routing before credential binding.
The `Config.__new__` fixture was replaced; combined SDK/configuration checks
passed **270 tests**, with **185** in the independent review slice. Actual SDK
construction, Apps decoding and native refresh exercise controlled HTTP replies,
not live OAuth or model calls. Designated maintainer review remains separate.

The stable full-suite rerun finished **1,707 passed / 42 warnings in 304.60 s**
using the explicitly approved dependency source and unchanged lock provenance.
It follows the retained **1 failed / 1,706 passed** checkpoint whose stale AST
assertion inspected `_http_run` instead of its `_direct_run` ownership delegate;
the focused correction passed **66 tests**. Ruff lint/format (**245 files**),
OpenAPI equality/schema and diff checks passed. Explicit public-identity offline
lock checking passed with **190 resolved**; a plain check under the ambient index
selector failed and did not rewrite the lock. Commands/results are in `VALIDATION.md`.

The new wheel was built and installed in separate fresh base/server environments
outside the checkout, with zero agent/model/cloud/timing dispatches:

```text
/private/tmp/evalsurge-native-reviewed-20261011.HlxeuH/dist/
evalsurge-0.2.1.dev2026101101-py3-none-any.whl
SHA256 f81098aac24e2251955cb000bdb017b981ef64ad4474104183ef4f8c8f894d6e
```

Protected installation evidence is under the same directory's `install/`.
Those installs verify the native constructor/import boundary, not cloud execution.
Keep this wheel and the older live-tested wheel unchanged. The final source
archive was refreshed after the test/template/docs corrections and verified at
`/private/tmp/evalsurge-final-checkpoint-20261011.SG59x1/dist/evalsurge-0.2.1.dev2026101101.tar.gz`.
SHA256 `f7f3786630f0d54e0f006f604c83b61e518a8b29fb8674e02bab4385c2d7fdcc`.
This build receipt itself postdates that archive; the prior sdist remains preserved.
The disabled portable runner template's stale older-wheel hash was corrected to
an explicit zero-hash placeholder, matching the native template. Two new pure
template regressions reproduce/prevent that mismatch; the focused
template/matrix/bearer/source-version slice passed **151 tests in 1.27 s**.
After explicit public-identity locked agent/dev sync, the final full controlled
suite passed **1,709 tests / 42 warnings in 301.79 s**, with no skips/deselections
or concurrent runtime/version/lock changes. Use this final result; the earlier
1,707-test pass predates the two new pure template regressions.

The selected `load-test` shell is now provisioned in `e2-demo-field-eng`.
`apps create --no-compute --no-wait` was followed by an exact-profile metadata
read confirming compute `STOPPED` and resolving the runner service-principal
client UUID. No source, credential export, target/volume grant or workload was
deployed; no new model traffic occurred. This resolves identity discovery only,
not live runtime OAuth or report export. The exact approved export volume was
subsequently created on October 12 as recorded above; runner grants remain pending. Notebook
portable M2M is deferred and no longer blocks this milestone. Keep CrewAI advisory
resolution and designated maintainer review gates.
Private provisioning receipt:
`/private/tmp/evalsurge-final-checkpoint-20261011.SG59x1/load-test.provisioning.safe.json`.

A full checkpoint suite against the evolving checkout retained **4 failed /
1,600 passed / 42 warnings in 306.42 s**. Its private log is
`/private/tmp/evalsurge-full-controlled-20261011.TbqAGJ/pytest.private.log`.
One failure came from the wrapper's restrictive umask changing an intentionally
unsafe test file to safe permissions; two came from the mid-run version/lock
change; one was the stale matrix assertion described above. Keep these failures;
the stable rerun above used ordinary pytest permission semantics.
This was disclosed controlled-provider testing, not new paid/live coverage.

## Historical fifteen-cell smoke continuation — before notebooks were deferred

Branch/HEAD remain `main` / `1089553d58c69f368e31447e4ec1e1d0cc1848fd`;
the shared tracked/untracked work is uncommitted/unpushed and must be preserved.
The earlier eighteen-cell proposals and approval blockers below are historical.
The current requested inventory is **fifteen** cells, five per CrewAI/LangGraph/
OpenAI Agents: local→HTTP, local→App, serverless notebook→App, runner App→HTTP,
and runner App→App. Notebook→HTTP remains an optional prepared sample outside
this scope. Cloud runners cannot reach laptop loopback; runner-App HTTP cells
need explicitly approved reachable HTTPS, never an automatic tunnel.

The current selections/approval are workspace/profile `e2-demo-field-eng`,
dedicated runner App `load-test`, exact CrewAI `1.15.23`, at most **36 target
attempts / 48 model calls**, concurrency one, evaluation off, zero provider
retries and at most 512 output tokens per model call. This is an aggregate smoke
ceiling, not authority to bypass failed security/authentication gates or add
judge/quality/cancellation scenarios. The disclosed controlled-inference
regression-suite exception is separately approved; fixture completions are not
actual inference or live cell coverage.

Two reduced basic-load cells passed with actual `system.ai.gpt-oss-120b` calls:
local→HTTP for LangGraph and OpenAI Agents, four successful model calls total.
See [the exact artifact, traffic and report evidence](LIVE_MATRIX_RESULTS.md).
These are not full tutorial, quality, active-cancellation or cloud-runner passes.
The other thirteen basic cells remain pending. The historical live-tested wheel is
`0.2.1.dev20261011`, SHA256
`4acba9feeb55dd724b0389ef84eaaf3cc623f4af42e14e9aa1ae8d8431b33b8f`;
no same-version overwrite or runtime repair was made by the sample-review branch.

CrewAI's approved isolated install passed for 162 hash-checked distributions,
but ChromaDB `1.1.1` failed four distinct advisory IDs. No CrewAI model call
followed that failure. Native deployment remains gated: inspected Agent Bricks
`0.4.0` and `0.5.0` require the LangGraph/OpenAI framework enum, not a truthful
CrewAI managed-store route. See [the retained CrewAI prerequisite record](../examples/journeys/agent_apps/crewai/README.md).

An earlier approved full controlled-inference suite retained **1 failed / 1,601
passed / 42 warnings in 270.68s**. Its server-wheel offline install failed before
the installed timing check: public-origin `cryptography==50.0.1` was not cached,
despite successful separate hash-checked proxy installation. No cache provenance
was relabeled. Explicit public-identity offline locked sync with the installed
build backend passed (190 resolved / 182 checked). The isolated installation
tests now explicitly retain owner-only logs outside the temporary venv; a native
child failure regression confirms cleanup cannot discard that evidence. All
**five focused installation tests passed in 34.16s** using the approved proxy
and unchanged lock hashes. The failed full run is not relabeled as a complete
suite pass; the subsequent stable full rerun above used the approved source
selector and passed without discarding this failed checkpoint.

Continue through [the current prerequisite checklist](LIVE_MATRIX_PREREQUISITES.md),
which now excludes notebook execution; the [original 15-cell runner/target plan](RUNNER_TARGET_VALIDATION.md)
remains historical scope. Keep exact artifact
hashes, failed evidence, separate live/controlled results, independent phase
outcomes and no zero-overhead/capacity claims. Root owns the combined validation
record, final artifact gate and commit/push decision. Maintainer review remains
separate from agent peer review.

## Historical final sample-review continuation — before current approvals

Branch/HEAD remain `main` / `1089553d58c69f368e31447e4ec1e1d0cc1848fd`.
All tracked/untracked edits below remain uncommitted/unpushed; preserve them.
The then-proposed live 18-cell matrix was **not complete**: every fresh cell was
`not_run`. No SDK authentication, installation, deployment, inference, cloud
mutation, full controlled-provider suite, CI, commit or push ran in this continuation.

Integrated parallel source work and independent review:

- Canonical handler/HTTP entrypoints validate strict origins and bounds before SDK
  setup, bind exact model destinations before auth, use native async OpenAI clients
  and keep SDK setup/refresh off-loop in cancellation-owned threads. Cancellation
  wins over a later worker error; cleanup may still exceed auth/handler deadlines.
- Native LangGraph/OpenAI Agents/CrewAI source projects and checksum staging are
  prepared. Closed native origin-validator inconsistency before SDK construction.
  Managed store validation precedes native construction, with no local fallback.
- CrewAI's supported native deployment route is explicitly **unresolved**. Retained
  `databricks-agentbricks==0.4.0` parser requires `langgraph`/`openai` framework
  labels; current docs say `agentbricks deploy` owns Runtime Store provisioning.
  Removed the unsupported manual-store setup recipe and CrewAI store placeholders.
  Do not relabel CrewAI, independently wire the managed store, or infer a platform
  hosting prohibition from this tooling gate. Its staged manifest records the gap.
- Sample-only HTTP bearer environment-reference parity now covers matrix/local/
  notebook/App runners. Existing exact-URL `Connection` is reused; secrets remain
  outside requests/receipts. HTTPS is required and App targets reject HTTP auth.
- Closed matrix CLI error disclosure: malformed credential-bearing URLs no longer
  reach stderr through Pydantic/ValueError text. Four real CLI/no-network rejection
  regressions cover matrix/local entrypoints; no client/auth/worker/model runs.
- Updated example inventory and global guides to include all three prepared native
  sources while keeping source, installed, deployed and actually tested distinct.

Final combined non-inference sample slice: **430 passed / 1 deselected in 1.59s**.
The excluded README regression uses controlled SSE answers. Native checks separately
passed **107 in 0.13s**. These are schema/source/staging/lifecycle and intentional
pre-provider checks, not live inference or fabricated provider success. See the
first `VALIDATION.md` section for the exact command/results and review findings.
The older 342-test snapshot below and intermediate 426-test slice predate the
final CLI disclosure fix/regressions.
Independent final re-review closed all previously confirmed findings in its scope;
native checks **107**, bearer/CLI checks **36**, original URL-disclosure reproduction
no longer leaks values. All three subagents completed. This is not maintainer approval.
Final Ruff lint/format (**242 files**), OpenAPI snapshot equality/schema and
`git diff --check` pass. No full-suite, dependency sync or fresh build is implied.

Reviewed wheel remains `0.2.1.dev20261011` with SHA256
`4acba9feeb55dd724b0389ef84eaaf3cc623f4af42e14e9aa1ae8d8431b33b8f`.
Rechecked all **60** runtime members against the checkout: zero mismatches.
Examples remain separate source; no same-version artifact overwrite occurred.
Canonical-handler SHA256 is `b2e1d72acd0da1e141ec2eb0f9708d2d581d73011bcdac993b08b1fa8735c96a`;
native-wrapper SHA256 is `ba981526d2b2255474ea5a2d614828cb6be62e5ffe83e5ff3260bf552967e320`.

Next action is the exact private manifest/resource/traffic gate in
[LIVE_MATRIX_PREREQUISITES.md](LIVE_MATRIX_PREREQUISITES.md): selected
`e2-demo-field-eng` only, exact model/CrewAI artifact choices, approved reachable
HTTPS HTTP origins, protected portable M2M reference, dedicated runner App and
protected export volume, and fresh bounded scenarios. Historical completed leases
cannot be replayed. Keep no classic compute, no automatic tunnel, no driver-token
copying, no registry bypass, no silent provider fixtures and no capacity/zero-
overhead claims. Full suite or CI-triggering push additionally requires explicit
controlled-inference disclosure/approval; **do not suppress CI to evade it**.
Maintainer/ADR approval is separate from agent peer review.

## Customer-agent example integration continuation

Current branch/HEAD remain `main` /
`1089553d58c69f368e31447e4ec1e1d0cc1848fd`; all earlier changes remain
uncommitted/unpushed. No fresh live matrix cell passed. Continue the existing
work rather than rebuilding examples or replaying historical traffic leases.

The customer-side source is now isolated from the runner:
`examples/real_framework_handler.py` is the canonical actual-framework handler,
`real_framework_agent.py` preserves the compatibility serving bridge, and
`crewai_agent.py` provides a standalone HTTP endpoint without EvalSurge imports.
Prepared LangGraph/OpenAI native projects and reviewed-source staging live under
`examples/journeys/agent_apps/`; native CrewAI's managed-CLI/dependency route
remains unverified. A generic Python App route must be assessed independently;
managed CLI selector absence is not an Apps platform prohibition.

Reproduced/fixed the policy AST lookup after extraction, without weakening its
authoritative-reference assertion. The final combined sample/non-inference slice
currently passes **342 / 1 deselected in 1.59 seconds**; the excluded README case
uses controlled SSE answers. Full Ruff lint/format (**240 files**), OpenAPI
equality/schema and whitespace checks pass. Independent source/trust reviews
are in progress. See the new first section of `VALIDATION.md` for exact commands.
These checks are not real inference or fresh installation evidence.

Read-only comparison found all **60** packaged runtime files byte-identical to
the reviewed wheel below; SHA256 remains
`4acba9feeb55dd724b0389ef84eaaf3cc623f4af42e14e9aa1ae8d8431b33b8f`.
New example sources are not packaged into that wheel. No build overwrite,
dependency installation, model call, deployment, resource mutation or push took
place in this continuation.

The live-resource/traffic and CI gates in the checkpoint below remain pending.
Start with [the staged execution checklist](LIVE_MATRIX_PREREQUISITES.md), not
with a full unbounded matrix run. The selected workspace remains
`e2-demo-field-eng`; owner reauthentication is not a current blocker.

## Historical runner/target sample checkpoint — October 11, 2026

Initial request: real CrewAI, LangGraph and OpenAI Agents under two independent
agent-hosting choices (separately hosted HTTP and deployed Databricks Apps),
with EvalSurge installed/generating traffic locally, in a serverless notebook,
and in a separate Databricks App. No benchmark-submission API service is wanted.
That initial cross-product proposed 18 logical cells; **none gained fresh live
validation in that checkpoint**. It is superseded by the current fifteen-cell
scope and exact two-cell live evidence above.

Branch `main`, HEAD `1089553d58c69f368e31447e4ec1e1d0cc1848fd`; substantial
previous tracked/untracked work plus these sample additions remains uncommitted
and unpushed. Preserve it. The reviewed runtime wheel/hash below is unchanged;
new example source is not inside that installed wheel.

Three parallel workstreams added the pure `framework_runner_matrix.py` inventory
and explicit-reference policy, standalone installed-package serverless HTTP/App
notebooks, and `examples/journeys/app_runner/` with proposed ADR 0017. The private
runner App is disabled by default, has health/status only, uses the direct SDK,
and requires a selected protected volume for one-use approval claims/evidence.
No fixture inference, model calls, App deployments, notebook Jobs, resources
created/deleted, commit or push occurred. Pure sample/source/configuration checks
are recorded separately in `VALIDATION.md`: the final combined slice passed
**166 tests / 1 deselected in 0.61s**, with no agent/provider invocation or
substitution. The deselected README case uses controlled SSE inference. Final
Ruff lint/format (228 files), OpenAPI equality/schema and whitespace checks
completed with exit zero. The earlier 1,252-test controlled pass predates these
additions; neither check establishes a fresh live matrix pass.

OAuth was refreshed for the already-selected `e2-demo-field-eng` profile after
the CLI rejected its old credential cache. Subsequent exact App metadata reads
confirmed LangGraph `agent-bricks-es-lg-1008` and OpenAI Agents
`agent-bricks-es-oai-1008` exist but are STOPPED/UNAVAILABLE. Their retained
deployment success is not current serving readiness. `test-eval-crewai-1009`
was reported nonexistent or deleted. No native worker authentication is established.

Next gates: fresh selected/bounded traffic and judge budgets; exact reachable
HTTP origins (cloud cannot reach laptop localhost); CrewAI approved-registry
environment and public native agent-App projects; protected portable OAuth M2M
source/client ID; selected runner App and protected volume; designated ADR review;
explicit controlled-inference exception before full-suite/CI-triggering push.
Do not bypass the registry, silently change versions/models, copy driver tokens,
resume historical traffic leases, or create classic compute. See
[the now-narrowed 15-cell plan](RUNNER_TARGET_VALIDATION.md) and
[examples](../examples/README.md). Earlier checkpoints remain historical.

## Finish-and-validate checkpoint — October 11, 2026

Objective: finish the current implementation for the Tuesday, October 13 demo,
not redesign the SDK. Branch `main`; baseline/current HEAD remains
`1089553d58c69f368e31447e4ec1e1d0cc1848fd`. All changes are **uncommitted and
unpushed**. Preserve the substantial tracked and untracked working tree; inspect
`git status --short` before resuming. Do not reset, discard or reuse completed live
leases. No external resources were created/deleted or deployments run here.

Completed across root and three parallel workstreams:

- Repaired the packaged serverless import via pure `evalsurge._retrieval`;
  historical validation callers re-export that same implementation. Installed
  execution no longer imports a nonexistent source-only helper.
- Added public content-free `format_summary(Result | Report | dict)`, exported
  from `evalsurge` and shared by CLI text output. Explicit JSON remains protected.
  ADR 0016 records presentation boundaries; maintainer review is still required.
- Frozen source/distribution/API version `0.2.1.dev20261011`; `_version.py`
  avoids stale installed metadata in source OpenAPI export. Dependency versions,
  hashes/index provenance remain unchanged. README/guides lead with reviewed wheel,
  not unverified public-index publication.
- Archive verification now AST-checks internal packaged import branches. Fresh
  installation verifier covers base/server exports, helper/summary branches,
  actual installed version and optional bounded NON-agent Locust timing.
- Calibration owns non-daemon native handlers, canonical bounded correlation
  IDs and cancellation-resistant native close. Completion needs actual successful
  timing pairs, exact injected-fault counts and observed worker/server cleanup.
- Reproduced and fixed repeated cancellation during TERM grace: one shielded,
  awaited TERM/grace/KILL/reap task retains ownership of the exact worker.
- Serverless receipts separate metadata checked, client dispatch observed and
  successful completion; a pre-invocation failure does not mark the App tested.
- Planless result/report retrieval now preserves unknown profiling evidence
  rather than turning the report's empty display shell into collected zero counts.

Verification is non-inference only. Intentional pre-provider failures, metadata
DTOs, native storage/process operations and inert timing endpoints do not validate
framework/model behavior. The controlled-provider full suite/CI requires the
explicit exception in AGENTS.md; the current full offline run was subsequently
approved and passed as recorded below. No new real-model, OAuth, cloud or paid calls
occurred, and no zero-overhead/capacity/serverless-live certification follows.
Exact final artifact/check evidence belongs to the latest `VALIDATION.md` section
and [demo matrix](DEMO_READINESS.md); earlier passes below remain historical.

Initial new regressions failed for daemon handler ownership, repeated cancellation
of native server close and repeated cancellation during worker TERM grace, then
passed after corrections. A broad final check exposed a test-owned killpg race:
the group vanished after a retained negative observation but before best-effort
test cleanup. Only that cleanup now tolerates ProcessLookupError; production's
negative evidence stays unchanged. Retain the original failed check in validation.

A later expanded slice failed native deadline cleanup (**309 passed, 1 failed,
3 deselected**). Thirty-round probes reproduced transient macOS group-probe
`EPERM` both sandboxed and escalated. The launcher now reaps only the known owner
and confirms cleanup solely from a subsequent read-only `ProcessLookupError`;
persistent permission errors and surviving groups remain false. Thirty post-fix
probes had zero unverified cleanups; six related modules passed 156 checks.
This source change required rebuilding the installation candidate; the corrected
artifact is recorded below. Earlier failed/provisional archives and their receipts
remain preserved rather than overwritten.

Final docs review corrected wheel-only example invocation (the wheel does not
package `examples`), explicitly selected `http-json` in the Python golden path,
and reused `format_summary` for optional remote and integration-guide output.

Final integrated non-inference command, adding invocation-evidence and primary-
sample contracts to the prior module list: **323 passed / 3 deselected in 21.45s**.
The omitted checks are one controlled-inference README case and two fresh-install
tests handled separately. Independent cleanup review found no additional P1.
No model inference or successful live notebook/App benchmark was run. Current
official docs support notebook App API token exchange; that is not this package's
independent-worker refresh validation, and no `auth="notebook"` is advertised.

The corrected candidate has now been rebuilt and clean-install verified:
`/private/tmp/evalsurge-reviewed-demo-20261011.Voze4Q/dist/evalsurge-0.2.1.dev20261011-py3-none-any.whl`,
SHA256 `4acba9feeb55dd724b0389ef84eaaf3cc623f4af42e14e9aa1ae8d8431b33b8f`.
Fresh base/server environments outside checkout passed on Darwin ARM64/Python
3.12.13, enforcing original lock hashes through the approved source. Installed
four-mode worker/storage/cleanup checks used nine NON-agent timing requests;
two standalone sample `--help` checks passed. Artifact/static slice: **39 passed /
3 deselected** (overlaps the 323-test slice). Exact source/lock hashes, commands
and protected receipt locations are in `VALIDATION.md`. Archives are retained
read-only. Later retrospective docs are separate from the source archive snapshot.
Final lint/format/OpenAPI/schema/whitespace and public-lock checks passed; uv-cache
sandbox denial was rerun with explicit escalation. Dependencies remain unchanged.
Do not rebuild or overwrite this demo wheel under the same version after code
changes; choose a new version. No publication, commit or push was performed.

The user approved the disclosed full offline controlled-provider suite. Initial
run: **1 failed / 1,249 passed / 42 warnings in 310.54s**. An ordinary-module
source compiler rejected the notebook's intentional top-level await. Only
`tests/test_unified_journey_examples.py` changed: notebook-only compiler flags
plus two strictness regressions, with **12 focused tests passed**. The complete
rerun then passed **1,252 tests, no skips/deselections, 42 upstream warnings in
301.37s**, exit zero. All static release checks passed; lock and reviewed wheel
hashes are unchanged. No packaged runtime or notebook execution code changed.
Exact approved-source commands, failure evidence and build snapshots are recorded
at the top of `VALIDATION.md`. No new real inference, notebook Job, remote CI,
publication, commit or push occurred. This approval is not a live traffic lease
or automatic CI/push authorization.

The final offline source snapshot containing the test correction is retained at
`/private/tmp/evalsurge-full-checks-20261011.hOdiVh/post-test-dist/`.
Explicit wheel/source archive checks passed. Wheel hash remains identical to the
reviewed demo; source hash and commands are recorded in `VALIDATION.md`. Earlier
archives were not replaced. Only the static source-check test and retrospective
documentation changed during this approved full-suite follow-up.

Remaining gates and decisions:

1. Fresh actual-model HTTP/App journeys against this artifact: exact selected
   target, model, approved attempt/token/retry bounds, fail-fast, active cancellation/
   drain, independent report retrieval and cleanup. Earlier App successes predate
   journal changes. LangGraph/OpenAI Agents/CrewAI live coverage is not inferred.
2. Serverless remains conditional. Public App construction still requires an exact
   profile; do not add/advertise `auth="notebook"`. Select an existing protected
   portable OAuth M2M source and service-principal client ID with workspace/App
   permissions; independently validate owner/worker auth before bounded inference.
   No classic fallback. Notebook is the runner, not agent hosting.
3. Current full offline verification is approved and passed. Future CI/controlled
   runs retain disclosure/approval requirements; distinguish them from real LLM
   calls. Remote CI/platform coverage and push remain unperformed.
4. Designated maintainer review of ADRs 0011/0014/0015/0016 and release gates.
   No public package publication or new cloud mutation is implied by this patch.

Prior active profile selection was `e2-demo-field-eng`; never auto-select another
profile. Historical leases completed/stopped and cannot authorize new traffic.
Sweep/CI-threshold/comparison/native-streaming/distributed features remain deferred.

## Historical checkpoint — October 10, 2026

### Measurement/serverless/CrewAI checkpoint — October 10, 2026

Branch `main`, baseline HEAD `1089553d58c69f368e31447e4ec1e1d0cc1848fd`.
This implementation is **uncommitted and unpushed**. The working tree contains
tracked load-engine/storage/public-schema/presentation/documentation changes and
untracked ADRs 0014/0015 plus native measurement and portable-OAuth tests. Inspect
`git status --short` before resuming; preserve these changes. `pyproject.toml` and
`uv.lock` are unchanged. The following publication/recovery sections are historical.

Three parallel workstreams:

1. Measurement integrity: implemented owned FIFO/native journal persistence,
   durable START acknowledgment, frozen response clocks, lifecycle drain,
   cancellation/window rechecks and parent recovery accounting. Public typed
   generator evidence has only `unknown`/`degraded` states; historical absence
   remains unavailable. CLI/UI display observations without declaring accuracy
   or capacity. Read proposed ADR 0014 and `docs/MEASUREMENT_ACCURACY.md`.
2. Serverless notebook runner: prepared private exact-profile OAuth M2M launcher
   and notebook sample. The notebook runs EvalSurge and the same Locust engine;
   it does not host the agent. Credentials stay outside requests. No credential
   source, identity, permissions or live notebook submission was provisioned.
   Read proposed ADR 0015 and `docs/SERVERLESS_RUNNER_STATUS.md`.
3. CrewAI local/App validation: **blocked before installation and inference**.
   Canonical approved package source exposes 1.15.23, not selected 1.15.27;
   two exact resolution attempts failed. The Python 3.12.13 environment remains
   empty. Earlier noncanonical-index availability was invalid evidence and was
   corrected. Do not bypass registry controls or silently install a fallback.

Native timing calibration after shutdown/dispatch repairs completed 200 requests
per mode at concurrency five, with at most ten dispatch seconds and a one-second
deadline. Native writer: paired client-minus-endpoint mean/p95 **0.471/0.710 ms**,
observed **160.80 requests/sec**. Injected native 5 ms fsync delay:
**0.464/0.625 ms**, **76.89 requests/sec**. This removes the demonstrated peer-disk
blocking mechanism but slow persistence still constrains generation rate. No
baseline subtraction, zero-overhead, capacity or cloud-disk claim follows.
START/completion failures remained interrupted/incomplete/degraded; server and
children were stopped/reaped. Calibration made zero agent/model/cloud calls.

Protected final calibration receipt:
`/private/tmp/evalsurge-measurement-integrity-final-20261010.Z2pHN3/calibration_receipt.json`.
Earlier calibration and all live failures remain unchanged. Never commit raw
artifacts or rerun completed live leases. Native/presentation checks, source
review, schema equality/validation and build evidence are in the latest section
of `VALIDATION.md`; no full controlled-inference suite/CI pass is claimed.
Independent agent review is not designated maintainer approval of ADRs 0014/0015.

Remaining resource/traffic gates:

- Explicitly choose CrewAI 1.15.23 or wait for 1.15.27 at the approved source.
  Proposed lease: selected `e2-demo-field-eng`, App `test-eval-crewai-1009`, real
  `system.ai.gpt-oss-120b` agent (<=512 output tokens, zero target retries),
  `databricks-gpt-5-4-mini` judge (2048 tokens/60-second timeout), explicit
  relevance/correctness and no planner. At most **76 model attempts: 48 agent +
  28 judge**, concurrency five, short local/App checks. No new memory/tools or
  Lakebase; prepared App contract is MLflow AgentServer `/responses` compatibility,
  not native DurableAgentServer. Exact alternative and lease approval are pending.
- Select the serverless service-principal client ID and protected credential
  source, with workspace assignment and App permissions, or separately authorize
  provisioning. Never send secrets in chat. Authenticate the owner and independent
  worker without inference first; then obtain the explicit initial smoke lease:
  one excluded probe plus one measured App invocation, concurrency one, evaluation
  off. No classic compute, driver-token forwarding, alternate profile or provider
  substitution.
- Obtain the explicit exception before running the existing controlled-provider
  full suite or triggering its CI. Actual inference validation stays live-only.
- Designated maintainer review and fresh real-agent/cloud-disk validation remain
  release gates; no new live inference occurred in this implementation checkpoint.

## Prior publication/recovery checkpoint — October 10, 2026

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
