# Generate a benchmark inside a private Databricks App

**Status: prepared example; no successful runtime installation or live validation.**
The October 12 disabled deployment failed before startup. A separate stdlib-only
App diagnostic found Python 3.11.17 and HTTP 403 from the approved package index;
its successful deployment is not an EvalSurge installation or benchmark. Resolve
registry/platform access before retrying the pinned installation. It does not yet
establish that installing EvalSurge on an App produces successful benchmarks.
The exact wheel, cloud export/replay gate, worker authentication and shutdown must
be verified on the selected resources before advertising this journey.

This App is the **load generator**, not the agent and not an EvalSurge benchmark
API server. It installs EvalSurge and uses the direct Python SDK/one Locust engine
against a **separate** hosted HTTP agent or Databricks App. No agent framework code
is installed in this runner. CrewAI, LangGraph and OpenAI Agents are examples of
the target implementations, not runner configuration options.

The only web routes are read-only `/healthz` and content-free `/status`.
There is no HTTP run submission, caller-chosen target, credential upload or report
endpoint. Do not install or start the optional EvalSurge REST server.

## Prerequisites

- A user-selected workspace/profile and explicitly approved runner App name.
- A separately running actual agent using a real model, with reviewed model,
  output-token/tool-turn bounds and source revision. Never substitute canned
  answers or a local fake for App hosting validation.
- An exact reviewed wheel under this directory's `wheel/`, matching the version
  and SHA256 in the operator configuration. The wheel is supplied separately and
  is not committed. This sample does not claim public PyPI publication.
- An existing protected Unity Catalog volume explicitly bound as the App
  resource `result-artifacts`, with **read/write** permissions for the runner
  App's assigned principal. `valueFrom` supplies its volume name/root; the example
  converts a simple three-part name into its Files API path. No Lakebase store is
  required or provisioned by this sample.
- For an App target, explicitly select `app_auth: "app-runtime"` with the expected
  workspace, runner App name and runner **service-principal client UUID**. Declare
  the exact numeric `workspace_id` as private operator configuration too: Apps
  injects `DATABRICKS_WORKSPACE_ID`, which must match the selected workspace in
  both the owner and its detached worker environment. The October 12 ADR 0019
  amendment and repaired artifact remain review gates; the older reviewed wheel
  rejects this platform selector and must not be live-armed on Apps.
  Declare the separate target App resource with `CAN_USE`. Databricks injects the runner's
  own M2M credentials; each owner/worker authenticates and refreshes independently.
  No user/notebook token or credential file is copied. This implemented binding
  has controlled SDK-boundary coverage, not a deployed/live validation receipt.
  A separately provisioned protected portable profile remains an explicit
  compatibility alternative, not a fallback from native authentication.
- Permissions on the exact target App for that selected principal, and workspace
  egress access to the selected HTTP/App origin and approved package registry.

Dependencies use the local wheel's `server` extra in `requirements.txt`—the extra
contains the direct coordinator/Locust dependencies; it does **not** start a REST
server. Select a registry authorized for the deployment environment. Do not copy
internal registry addresses into customer examples, relabel lock provenance, or
bypass organization registry restrictions. Dependency installation on Apps remains
unvalidated for this artifact; the registry-only diagnostic did establish the
selected App's Python 3.11.17 interpreter. The short requirements file resolves
compatible dependency ranges, while the recorded private deployment used an exact
hash-locked export. Do not describe those two installs as equivalent evidence.

`databricks.yml` and `app.yaml` contain the same runtime command/resource wiring.
Their environment schemas use different spellings: bundle `config.env` requires
`value_from`, while runtime `app.yaml` requires `valueFrom`. Do not copy one key
verbatim into the other file; CLI `1.17.0` warns and ignores the wrong bundle key.
Inspect the resolved `config.env` during bundle validation, not just its exit code.
For a native App target, stage the standalone `databricks.native.yml` template as
the deployment's `databricks.yml`; it adds the exact `benchmark-target` App resource
without relying on bundle list merging. Select `target_app_name` explicitly.
The bundle has no default App or volume name: explicitly select approved
`runner_app_name` and `result_volume` variables and the chosen CLI profile before
validation/deployment. Its native `uc_securable` bindings request `READ_VOLUME`
and `WRITE_VOLUME` on that existing volume; they do not provision a volume or
select an App access policy. Review that the App's access permissions are private
to the intended operator. Local `.gitignore` excludes the copied wheel, private
operator config, credentials and generated evidence. Bundle sync includes only
the reviewed wheel and nonsecret `operator.json` when deliberately supplied;
never put a credential file in the deployment source.

## Configure one bounded execution

Start with `operator.native.example.json` for native App targets, or
`operator.example.json` for portable-profile/HTTP compatibility. Both are disabled
and expired, and the native template's artifact/identity fields are placeholders.
Deploying that configuration causes **zero SDK, target, judge or volume calls**.
The health route confirms only that the process is up, not target readiness.

Review the exact wheel/version/hash and target selections. For an HTTP target,
set `target_kind` to `http`, set `http_url` to the exact reachable `http-json`
endpoint over **HTTPS**, and set `app_name`, `profile`, `oauth_config_file`, `oauth_client_id` to
`null`. Omit `bearer_token_env` for explicitly authorized unauthenticated HTTP.
HTTP also requires `runner_app: null` and default `app_auth: "profile"`.
For a protected endpoint, optionally set `bearer_token_env` to the name of an
existing operator-owned environment variable, for example `AGENT_BEARER_TOKEN`.
This is a **reference**, never its secret value. Provision that variable through
the approved existing secret/environment mechanism before launch; the example
does not create a secret, copy credentials or put a token into `operator.json`,
`RunCreate`, status or receipts. Normal Locust workers resolve it at dispatch
using the existing exact-URL `Connection` boundary. HTTPS is required for bearer
authentication, including loopback; no redirects or target retries are added.
A runner App cannot call a laptop's `127.0.0.1`; use an independently reachable
endpoint. Token availability and actual authentication remain separate live gates.

For an App target, keep `target_kind: "databricks-app"` and explicitly select its
name, workspace and identity mode. Omit `bearer_token_env` or
set it to `null`: App targets reject HTTP bearer settings. Credentials stay outside
`RunCreate`. Do not put secrets in the JSON, source tree, notebook, report or chat.
Native mode uses the direct SDK with no launcher/profile file. Explicit portable
mode reuses `evalsurge.serverless` only as the installed portable-process launcher;
the exported receipt identifies the actual runner as `databricks-app`, not a notebook.

### Native App-target binding

Outside the benchmark request, the direct binding is:

```python
from evalsurge import Agent

agent = Agent.databricks_app(
    "your-agent-app",
    auth="app-runtime",
    workspace="https://your-workspace.cloud.databricks.com",
    workspace_id="1234567890123456",  # Replace with the selected numeric workspace ID.
    runner_app="your-runner-app",
    client_id="00000000-0000-0000-0000-000000000000",  # Replace with its actual SP client UUID.
)
```

Use the runner App metadata's `service_principal_client_id`; **not** its numeric
`service_principal_id` or `oauth2_app_client_id`. Keep `profile` and
`oauth_config_file` absent in native mode. The runtime validates actual and detached
environment agreement before SDK calls, explicitly selects M2M OAuth, verifies
that the runner App owns that client identity and declares the target App resource,
and binds credentials to the workspace-discovered invocation endpoint. Missing
credentials, mismatches or alternate token/profile/config selectors fail closed.
This is configuration agreement, not cryptographic platform attestation. SDK
discovery/refresh ownership and transport budgets are not hard process deadlines.
See [ADR 0019](../../../docs/adr/0019-explicit-native-app-runner-authentication.md).
Serverless notebook authentication remains a separate portable-source gate; this
native App mode neither forwards notebook tokens nor repairs notebook workers.

Only after fresh paid-traffic/resource approval, choose a unique `approval_id`,
an ISO UTC expiry within ten minutes of launch, and set all three live fields to
`true`: `enabled`, `accept_paid_traffic`, `real_inference_attested`. Enabling this
one-shot configuration is an explicit execution action; ordinary installation or
deployment of the disabled template must not be described as consent to traffic.
Run a single Uvicorn process; do not enable reload or multiple workers.
Point `EVALSURGE_OPERATOR_CONFIG` to the reviewed nonsecret `operator.json` in
both runtime configurations for that intentional launch; otherwise the default
remains `operator.example.json` and disabled. Merely copying a config does not arm it.

The immutable smoke request is concurrency **one**, **one** measured attempt,
five seconds of dispatch and a 30-second target timeout, plus the normal excluded
first-case preflight. Evaluation is **off**; no planner or judge calls occur.
Two target invocations do not imply two model/tool turns or a monetary quota.
This is a functional smoke, not capacity discovery, quality validation or proof
of zero generator-induced latency. Larger load and evaluation need a separate
reviewed request/lease, not a silent change to this sample.
Approval expiry is checked initially, immediately before the external claim and
again before the target branch starts, after potentially slow SDK setup. It is an
admission/start gate, not a hard deadline for already dispatched discovery,
storage, preflight or inference calls. Expiry does not revoke active traffic.

## Restart, cancellation and reports

Before target dispatch, the assigned App principal consumes a unique claim under
the protected result volume with `overwrite=False`. An existing claim or
ambiguous claim error stops before inference. Failed runs still consume their
approval. Automatic restart cannot reuse that claim; the sample never deletes it,
creates another approval or retries a run. Volume ACLs must prevent unauthorized
claim deletion. This is not a distributed lease or production scheduler.
The exporter checks native `DATABRICKS_HOST` agreement with the reviewed workspace
and native client-ID/secret presence **before SDK construction**. Construction and
OAuth/OIDC discovery run in an owned native thread outside the event loop, not in
measured load. SDK `oauth-m2m`, workspace and client-ID agreement are then required
before resource operations. Native values are never logged or placed in a request/report.
Configured metadata/storage SDK calls have a small **positive** retry-timeout
setting (one second) and a five-second transport timeout; zero would select the
installed SDK's 300-second default. SDK 0.146.0's OIDC endpoint discovery uses a
separate default client with a **300-second retry / 60-second HTTP timeout**;
the configured 1/5-second settings do not bound that discovery. Resource SDK
retries never retry the model target. None of these settings is a hard process
deadline or proof of successful cleanup; cancellation owns the native operation
until it finishes, and platform shutdown can interrupt it.

Stop the runner App to cancel its single execution. Context ownership stops new
dispatch and waits for active work/child cleanup. The platform can forcibly kill
an App before drain/export completes; such outcomes remain unverified, not a
successful cancellation. Stopping/restarting does not roll back agent side effects.

After cleanup, the sample uploads `<approval_id>.artifacts.zip` and
`<approval_id>.receipt.json` under `<volume>/evalsurge-app-runner/`, without
overwriting previous evidence. Retrieve them with the selected volume's ordinary
permissions. The ZIP contains protected prompts/answers/metadata; do not publish
it as a sanitized report. Nothing is served through the health/status routes.
An export failure is visible as a gap. Local evidence is ephemeral and can be lost
on forced kill/container recycling; the external claim remains consumed.
The safe receipt preserves benchmark outcome separately; missing/failed artifact
export cannot mark the complete sample journey as passed. An empty artifact
directory after an authentication block is not a delivered report.
`benchmark_passed` remains distinct from journey `passed`, which stays false
until both artifact and receipt uploads finish. Cancellation during export sets
the content-free `export_interrupted` / `export_status: "interrupted"` outcome;
an upload completing during cancellation does not certify delivery of the whole journey.

Do not provision, deploy, grant permissions or delete resources merely by copying
these files. Select/approve the exact runner App, target and volume first. The
prepared sample is covered by non-inference source/schema/storage checks and
controlled SDK/OAuth transport regressions;
those checks are not actual App installation or live-model evidence. See proposed
[ADR 0017](../../../docs/adr/0017-private-app-direct-runner.md).

Initial preparation verification on October 11, 2026: focused Ruff checks and **29** source,
schema, pure approval-expiry, inert-thread ownership, bounded local archive/export
and native SDK resource-data contract tests passed. These tests make no SDK
client/authentication, agent, model, deployment or cloud file call. Inert local
storage/thread fixtures verify export/cancellation projection only, never agent behavior.
Subsequent native-auth verification exercises the actual SDK configuration,
Apps decoding and refreshable M2M provider against controlled HTTP replies, with
independent coordinator/worker credential sources. It makes no live OAuth or
agent/model call; see [ADR 0019](../../../docs/adr/0019-explicit-native-app-runner-authentication.md)
and [the current validation checkpoint](../../../VALIDATION.md).
Both disabled operator templates require an explicitly reviewed wheel SHA256;
their zero hashes are placeholders, not hashes of an executable release artifact.
The example has not passed live App
installation, OAuth, cloud claim/export, cancellation or inference validation.
