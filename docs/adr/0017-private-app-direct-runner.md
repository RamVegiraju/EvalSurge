# ADR 0017: Private one-shot direct execution inside a Databricks App

- Status: Accepted by designated maintainer for private validation on October 12, 2026; live validation and production gates remain
- Date: October 11, 2026
- Scope: An operator-owned example, not an EvalSurge REST service or production host

The designated maintainer confirmed approval in response to the explicit ADR
0017/0019 private-deployment review request on October 12. This permits the
disabled-first `load-test` validation in `e2-demo-field-eng`; it is not independent
security review, a production approval or an expansion of the retained traffic budget.

## Context and source evidence

An agent's hosting location and a benchmark's runner location are independent.
The targets remain separately hosted HTTP agents and deployed Databricks Apps.
The requested additional runner is a Databricks App that installs EvalSurge and
uses its direct SDK and sole Locust engine. It must not accept public benchmark
requests, arbitrary targets, uploaded code, profiles, or credentials.

Official App documentation supports App-to-App programmatic OAuth with an App's
assigned service principal. That establishes the platform feature, not a tested
EvalSurge Locust authentication boundary. ADR 0019 adds explicitly selected
`auth="app-runtime"` with expected workspace/runner/principal metadata, a declared
target App resource and independent SDK M2M refresh in each worker. The native
branch uses the direct SDK without a profile file; existing explicit profile mode
can still reuse the packaged portable-M2M launcher. Neither branch relaxes profile
guards, forwards user/notebook tokens or copies runtime secrets into files.
Controlled metadata/OAuth checks are not deployed/live authentication evidence.

Source references reviewed October 11, 2026:

- Official App programmatic access and App-to-App authentication:
  `https://docs.databricks.com/aws/en/dev-tools/databricks-apps/connect-local`
- App environment, requirements and deployment configuration:
  `https://docs.databricks.com/aws/en/dev-tools/databricks-apps/app-runtime`
  and `https://docs.databricks.com/aws/en/dev-tools/databricks-apps/system-env`
- Installed Databricks SDK 0.146.0 `service/files.py`: `upload(path, contents,
  overwrite=False)` rejects an existing destination. `download()` returns a
  binary body. Upload without an explicit false overwrite flag is unsafe here.
- Installed SDK `oauth.py:get_endpoints_from_url()` uses its own `_BaseClient()`.
  `_base_client.py` defaults to 300-second retries and a 60-second HTTP timeout;
  a configured WorkspaceClient's 1/5-second settings do not bound that discovery.
- Existing ADRs 0011, 0014 and 0015 and `docs/PRODUCTION_READINESS.md`.

October 12 predeployment CLI validation corrected a configuration-schema mismatch:
bundle `config.env` uses `value_from`, while runtime `app.yaml` uses `valueFrom`.
CLI `1.17.0` ignored the former templates' camel-case bundle field with a warning;
the corrected disabled stage retains the export resource in resolved configuration.
Static regression/source checks and AI review do not satisfy the designated human
maintainer review or live validation gates. This correction changes no runtime wheel.

Platform guidance embedded in older skills is not evidence of current App-to-App
failure: browser-origin/CORS constraints do not prohibit an OAuth-authenticated
server-side call. Likewise default App resource sizes are not generator-capacity
evidence.

## Proposed decision

Provide `examples/journeys/app_runner/`, a private single-operator example with
only content-free read-only `/healthz` and `/status` routes. It runs one Uvicorn
process, without reload or additional workers. It does not import the EvalSurge
REST app and has no HTTP start, cancel, target-selection or report-data route.
Operators change a reviewed private configuration, not a browser request.

Default configuration is disabled. Deployment of the template makes no SDK,
OAuth, target, planner, judge or volume call. Explicit live enablement additionally
requires real-inference attestation, a fresh bounded approval identifier/expiry,
the exact installed wheel/version/hash, a reviewed fixed target, and a selected
protected result-volume resource. Changing configuration to enable this one-shot
is an explicit paid execution action, not ordinary installation.
Approval expiry is rechecked immediately before claim upload and target-branch
start, after potentially slow SDK initialization. It is an admission/start gate,
not a hard deadline for discovery, storage, preflight or inference calls already
dispatched. It does not revoke active traffic or replace SDK/Locust ownership.

Before inference, the App's assigned service principal reserves
`<volume>/evalsurge-app-runner/<approval-id>.claim.json` through the SDK Files API
with `overwrite=False`. A successful reservation consumes the approval even if
subsequent authentication, inference, cancellation or export fails. Existing
claims and ambiguous reservation errors fail closed before target dispatch.
No automatic new approval, claim deletion, retry run or restart recovery occurs.
An authorized operator must select a fresh approval for a deliberate new run.
This is a narrow replay gate, not distributed scheduling, leases or transactional
run recovery. An operator deleting the claim or changing identifiers can permit
another run; volume ACLs are part of the trust boundary.

The fixed smoke is concurrency one, one excluded first-case probe plus at most
one measured invocation, five seconds of dispatch and a 30-second target timeout.
Evaluation is off. This does not validate quality, automated scorer planning,
larger concurrency, streaming TTFT or sustainable capacity. Agent-side source
must enforce the declared model/output/tool limits; two invocations do not bound
arbitrary model/tool turns or dollar cost.

HTTP targets require HTTPS and use the public direct native-async SDK and explicit `http-json`.
The reviewed operator configuration may optionally name an existing bearer-token
environment variable through `bearer_token_env`; omission explicitly authorizes
unauthenticated HTTP. It uses the existing exact-URL operator `Connection`, not a
new authentication mechanism. Construction reads no credential value, and normal
workers resolve it at dispatch. The reference is private configuration outside
`RunCreate`; token values are never added to source, config, status or receipts.
The operator must separately provision the protected variable in the owner/worker
environment through an approved mechanism. HTTPS is mandatory for bearer targets,
including loopback, and an App target rejects this HTTP-only setting. Native App
targets use the direct SDK; portable-profile compatibility uses its existing
launcher. Both require independently refreshed worker OAuth.
No agent framework or customer handler is imported into the runner App.

## Data flow and protected export

`operator config → consent/artifact check → one-use volume claim → direct SDK /
portable owner → Locust → separately hosted agent → local protected artifacts →
post-load volume export`

The volume is an explicit existing protected export/claim destination, not a
newly provisioned Lakebase store. No target/judge work happens during export.
In native mode the App's service principal owns claim/export and target invocation;
its exact target App resource grants `CAN_USE`, while the selected volume grants
read/write evidence access. A compatibility App-target portable profile can belong
to a distinct selected principal, and credentials
remain outside `RunCreate`. Native workspace identity agreement and App client-ID/
secret presence are checked before SDK construction, not only before claim creation.
SDK construction/OAuth discovery run in an owned native thread outside the event
loop. SDK `oauth-m2m`, workspace and exact client-ID agreement are then required
before claim/export calls; no native value is serialized or logged.
Metadata/storage calls use a small positive one-second SDK retry timeout and a
five-second transport timeout. In the installed SDK, zero falls back to 300
seconds, so it cannot mean "disable retry". OIDC discovery has an independent
default SDK client (300-second retry / 60-second HTTP timeout); those 1/5-second
settings do not bound discovery. Configured calls may retry metadata or storage
operations, never the model target. Owned native calls cannot safely be killed
by coroutine cancellation; no SDK setting establishes a hard process deadline.

Artifacts remain private local temporary storage while running. A bounded ZIP
and aggregate receipt are uploaded after SDK/owner cleanup using unique paths
and `overwrite=False`. ZIP contents can include prompts, answers, references and
profile identifiers: the export is protected evidence, not sanitized telemetry.
No raw report/answer is logged or exposed by the App HTTP routes. Raw exceptions,
headers and credential values are never included in status. Export failure is a
visible gap, not successful report delivery. Report retrieval uses the selected
volume's normal permissions, not the runner's public routes.
The safe receipt retains benchmark success separately from complete journey
success; failed/missing export or an empty auth-blocked artifact directory cannot
claim that a protected report was delivered. Archival reads and SDK file calls
are owned through cancellation, rather than detaching their native threads.
Journey `passed` stays false until artifact and receipt exports both finish;
`benchmark_passed` separately preserves its captured execution outcome. Export
cancellation explicitly yields `export_interrupted` / `export_status: interrupted`,
and cannot retain a stale passing journey projection after a native upload finishes.

## Failure, ownership and restart

Configuration, expiry, artifact mismatch and claim failure stop before inference.
App readiness failure preserves the portable launcher's separate safe evidence.
Benchmark failure, cancellation and incomplete journal drain retain failure/partial
artifacts; lifecycle completion is not a quality pass or an accuracy certification.
Cancellation propagates to the owned direct context/portable launch, stops new
dispatch and waits for cleanup. The read-only web service cannot request another
run. Stopping the runner App is the operator's cancellation action.

The App filesystem is volatile. A platform kill, disk loss or interrupted export
can lose local evidence; the consumed external claim still prevents replay.
Platform shutdown grace may be shorter than target drain or an SDK network call.
The sample cannot guarantee artifact export or cleanup after forced SIGKILL and
must not report those unobserved outcomes as success. Retained claims require
operator retention/removal; the sample never deletes cloud resources or evidence.

## Trade-offs, bottlenecks and compatibility

Optimized: a small explicit install-and-run topology without a benchmark server,
public execution endpoint, new SDK, new runner or automatic credential copying.
Sacrificed: interactive multi-user execution, unattended retries, resumable runs,
automatic App-native auth convenience and production availability.

Admission is one task/one process. App CPU/RAM, journal/fsync, auth refresh, parser
work and scheduler pressure may limit load generation. The existing typed generator
observations remain unknown/degraded evidence, not zero observer-effect proof.
Keep the target in a different host/App; the runner cannot reach a laptop's
loopback address, and cohosting target and generator would confound measurements.

All public SDK, `/v1`, `/v2` and optional remote modes remain unchanged. No new
runtime package module or dependency pin is introduced. The exact reviewed wheel
is copied into the deployment separately; no internal registry URL or secret is
committed. Workspace-specific resource selection and live mutations require
fresh approval. This proposed example has not been deployed or used for actual
model inference. Static/source checks do not establish installation on Apps,
independent worker OAuth, claim/export behavior on cloud storage or timing accuracy.
Maintainer review and the production release gates remain outstanding.
