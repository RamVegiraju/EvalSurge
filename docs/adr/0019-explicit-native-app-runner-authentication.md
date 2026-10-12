# ADR 0019: Explicit native App-runner authentication

- Status: Accepted by designated maintainer for private validation on October 12, 2026; live validation and production gates remain
- Date: October 11, 2026
- Scope: Operator-owned authentication for direct App runners; no new load engine

The designated maintainer confirmed approval in response to the explicit ADR
0017/0019 private-deployment review request on October 12. This permits the
disabled-first selected-workspace validation, not independent security sign-off,
public/shared hosting, notebook credentials or additional traffic allowance.

## Context and evidence

The `load-test` runner App should install EvalSurge and invoke a separate agent
App through direct Python. It must not need a second benchmark-submission API or
an exported laptop profile. Existing `Agent.databricks_app()` is profile-only:
`target_resolver._reject_profile_overrides()` deliberately rejects ambient SDK
identity selectors. Removing that guard would make a selected profile ambiguous.

Current official Apps guidance supports declaring the target App as a resource,
granting the runner's service principal `CAN_USE`. Apps inject its own
`DATABRICKS_CLIENT_ID`/`DATABRICKS_CLIENT_SECRET`; the inspected Databricks SDK
`oauth_service_principal()` creates refreshable client credentials. Independent
workers can authenticate with inherited App credentials. This is platform/source
evidence, not a successful deployed EvalSurge benchmark.

References reviewed October 11:

- `https://docs.databricks.com/aws/en/dev-tools/databricks-apps/apps-resource`
- `https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth`
- Installed SDK 0.146.0 credential strategy/configuration source and Apps types
- ADRs 0011, 0015 and 0017; existing exact-origin/credential conflict tests

## Proposed contract before implementation

Add an explicit **native App service-principal mode** to operator-owned App target
configuration. Default profile mode remains unchanged and continues rejecting
ambient destination, credential and authentication overrides. Selection of native
mode must be deliberate; it cannot fall back from failed profile authentication.

The binding owns the exact workspace origin, runner App identity and expected
OAuth client identity outside `RunCreate`. Native mode requires the platform App
environment, matches those identities before credential use, permits only the
expected M2M inputs, and rejects conflicting token/profile/config-file/account or
alternate-cloud/auth-routing selectors. The SDK must explicitly select
`oauth-m2m`, not generic default credential discovery. Verify any runtime-to-App
principal mapping against the installed SDK/API schema before implementing it.

Hosting/discovery remains separate from invocation protocols. Resolve the target
App URL through the exact selected workspace; credentials may reach only its
verified `/api/invocations` or `/responses` endpoint. Both coordinator and Locust
worker validate the binding. SDK OAuth refresh happens independently in each
process; never serialize access tokens, copy injected secrets into files, put
credentials in a request/receipt, or send them to caller-chosen origins.

Native mode does **not** solve notebook authentication. The serverless launcher
continues requiring a separately provisioned protected refreshable source. A
driver-token exchange is not proof of independent worker refresh. No notebook
token forwarding, profile auto-selection or native-auth fallback is introduced.

## Load, data flow and failure semantics

### October 12 proposed amendment: explicit native workspace identifier

Pre-live source inspection reproduced a deployment blocker without constructing
any credential provider: SDK 0.146.0 declares `DATABRICKS_WORKSPACE_ID`, Apps
injects that metadata, and the existing native guard rejects it as an alternate
routing selector. Blindly permitting it is unsafe: SDK host metadata fills only
missing IDs and does not verify an ambient ID before services use it in routing
headers. Do not unset/drop the platform variable or weaken named-profile guards.

Proposed focused repair: carry an optional private `workspace_id` through native
operator bindings, outside `RunCreate`. When the platform variable is present,
require a pinned numeric identifier and exact agreement between the actual and
detached environments before SDK construction. A configured ID also requires
matching runtime metadata; pass it explicitly to Config and verify the resulting
configuration. Legacy native callers without configured/injected IDs retain their
existing behavior, while real Apps must supply the selected workspace identifier.
Profile mode continues rejecting these native-only fields and ambient selectors.

Tests must cover matching, missing, mismatching and split-environment IDs,
operator-only serialization, worker reconstruction and unchanged profile rejection.
This is a new runtime artifact: preserve the previously reviewed wheel, assign a
new version, and obtain designated maintainer acceptance of this amendment before
deploying or live-arming the repaired runtime. The prior private deployment approval
does not constitute independent review or this amendment's acceptance.

### Implemented operator binding

`Agent.databricks_app(name, auth="app-runtime", workspace=..., workspace_id=...,
runner_app=..., client_id=...)` deliberately selects native mode without a profile. Registered
operator settings/worker connections carry `app_auth`, `workspace`, `runner_app`
and `client_id`, with optional private `workspace_id`; ordinary settings serialization/repr keeps identity metadata
private. No new public `RunCreate` or REST credential/destination field is added.
`auth="profile"` remains the default and requires the selected profile.

The installed SDK's `App.service_principal_client_id` is the runner mapping used;
numeric `service_principal_id` and App OAuth `oauth2_app_client_id` are not accepted
as substitutes. The runner must declare the target `AppResourceApp` with `CAN_USE`.
Both actual/scoped environments reject token/config/profile/alternate-auth routing
before Config construction. Explicit host/client/secret and
`credentials_strategy=oauth_service_principal`, `auth_type="oauth-m2m"` prevent
default-provider fallback. SDK source skips profile loading with those explicit
credentials. Each worker repeats metadata and independent OAuth-provider creation,
then refreshes tokens at dispatch without repeating App discovery per request.
Native environment agreement is not cryptographic App-runtime attestation.

The private runner's native branch calls the public direct SDK and reuses these
checks for claim/export setup; it does not route through the portable notebook
launcher. `operator.native.example.json` is disabled with placeholder identity/
artifact fields. `databricks.native.yml` is a separate complete bundle template,
staged as `databricks.yml` rather than assuming list-merging semantics. Native
metadata/OAuth fixtures exercise this boundary without model calls. A controlled
HTTP test also exercises the real Config, WorkspaceClient, OAuth M2M strategy and
ClientCredentials: independent coordinator/worker token sources and expiry-driven
refresh are verified without replacing SDK constructors. This is not live OAuth.
Configured and SDK-discovered origins share strict HTTPS parsing, rejecting
backslashes, whitespace, controls/DEL, credentials, routing components and non-TLS
ports before target credentials can be bound. New-version wheel installation and
actual deployment/authentication remain gates.

Initial native App validation remains one excluded probe plus one measured
invocation, concurrency one, evaluation off, no target retry, at most 512 output
tokens per approved model call. The runner App also requires a selected protected
export volume and consumed one-use claim; authentication does not grant execution
or create resources. Keep the selected `load-test` name and fixed target.

`operator native binding → exact identity checks → target App discovery → OAuth
refresh → sole Locust worker → separately hosted agent → protected journal/report`

Identity mismatch, missing credentials, unexpected SDK selectors, failed discovery
or unavailable OAuth fail before measured load, with fixed safe guidance. Retain
failed preflight/report evidence. Metadata/auth calls have SDK timeout limitations;
coroutine cancellation cannot claim hard termination of native SDK work. Public
cancellation still stops new dispatch and drains active work; agent side effects
are not rolled back. Existing journal completeness/generator observations apply.

## Compatibility and trade-offs

Optimized: installing/running EvalSurge inside a private App uses its platform
identity without generating credential files or weakening named profiles.
Sacrificed: generic ambient-credential convenience, automatic identity selection
and cross-workspace App discovery. Native binding metadata increases the private
operator surface; no credentials or destinations become public API request fields.

Preserve `/v1`, `/v2`, legacy SDK calls, explicit profiles, invocation adapters,
captured-answer judging and one Locust engine. No new SDK dependency is needed.
Do not assert that native OAuth proves generator capacity, zero overhead, worker
cleanup or durable report delivery. App CPU, scheduling, auth and disk still
affect measurements; protected export and platform shutdown remain separate gates.

Tests must independently cover unchanged profile rejection, native identity and
selector failures before credentials, exact endpoint binding, safe diagnostics,
worker refresh, disabled configurations and public-request credential exclusion.
SDK/OAuth controlled-boundary tests are not live authentication. A changed runtime
requires a new versioned reviewed wheel; do not overwrite the validated artifact.
Deployment, protected volume choice and designated maintainer review remain gates.
