# Serverless notebook runner: current authentication blocker

Checkpoint: October 11, 2026. Live notebook→App validation remains blocked and
has not resumed.
This describes observed behavior with Databricks SDK 0.146.0, not a general claim
that serverless cannot run EvalSurge or a promise of a new authentication design.

The prepared harness now verifies the selected profile's exact workspace before
App discovery and distinguishes profile conflicts, driver authentication/OAuth,
App discovery/deployment and worker OAuth with fixed safe blocker codes. SDK
construction may initialize metadata/authentication before that check. Native
SDK metadata/auth-boundary and deliberate rejection tests passed without cloud
or model calls. The new portable-M2M launcher below does not supply a credential
source, submit a new notebook or establish live notebook-to-App coverage.

## What failed

In the selected `e2-demo-field-eng` workspace, prerequisite Job run
`526298221857181` / task `972949342784427` used serverless environment 5 and
Python 3.12.3. Driver-native runtime OAuth, exact workspace/active identity,
loopback HTTP and POSIX locking/fsync passed. An independent Python subprocess
failed runtime-OAuth initialization with `ValueError`. The check made **zero
model calls**, did not test a deployed App and retained the failed auth result
even though the diagnostic Job itself finished successfully.

EvalSurge's sole Locust engine runs in an independent worker process. The driver
being authenticated does not establish that worker authentication works. Installed
SDK runtime-OAuth source depends on notebook-injected runtime/REPL context and
token exchange; that context was not established in the subprocess. The saved
safe exception class does not prove a more specific hidden provider error.

There is also a public configuration boundary: `Agent.databricks_app(...)`
currently takes an explicitly selected **profile**, not a notebook-native
`WorkspaceClient`. The existing resolver rejects ambient destination/identity
overrides and requires the SDK's independently refreshable OAuth credential
provider. Neither naming a laptop profile in a notebook nor receiving a driver
bearer token makes it portable to a new worker.

## Three different API topologies

| Notebook's role | Where target load originates | Effect on this blocker |
| --- | --- | --- |
| HTTP client of a separately hosted EvalSurge API | API host's Locust worker | The API operator owns target authentication. Notebook runtime OAuth is not used by that target worker. This is remote submission, not notebook load generation. |
| Host of FastAPI and Locust | Notebook-owned Locust subprocess | Loopback was verified, but starting FastAPI does not repair the independent worker's App OAuth. Notebook lifetime/public ingress/durability are separate unverified concerns. |
| Direct Python EvalSurge runner | Notebook-owned Locust subprocess | This is the intended serverless sample, with the agent remaining in its deployed App. Worker-portable authentication is still a gate. |

Serverless is a **load-generator location**, never a third agent-hosting option
in this milestone. The two target choices remain a separately hosted HTTP agent
and an agent deployed in Databricks Apps.

## Implemented portable-auth path; resources still required

[Proposed ADR 0015](adr/0015-serverless-runner-oauth-boundary.md) records an
operator-owned OAuth M2M path. The notebook sample launches an isolated EvalSurge
owner process; it launches the normal Locust worker, with each process using the
SDK's independently refreshable provider. The unchanged public profile binding
and conflicting-selector guards remain active. Credentials stay outside
`RunCreate`; no notebook token/cache forwarding or credential proxy is added.

The launcher is now packaged as `evalsurge.serverless`; the notebook imports it
directly and uses `await launch_runner_async(options)`. The installed wheel's
package directory supplies the isolated owner/worker import path. No repository
checkout, source-root widget or `sys.path` edit is required. The old validation
script remains a thin alias/CLI entry point to the same implementation.

For a standard interactive serverless notebook, stage the exact reviewed wheel
at an authorized `/Workspace/...` or `/Volumes/...` artifact path. A wheel-picker
installation alone does not establish optional-extra installation. The prepared
samples instead describe a reviewed requirements file containing the exact wheel
path suffixed with `[server]`, referenced through the Environment side pane as
`-r /Workspace/.../evalsurge-requirements.txt`. Apply and rerun cells after Python
restarts. This installation recipe is not a successful serverless installation
receipt. A base-only package installation is the lightweight client, not the local
Locust load generator. Check native dependency
architecture compatibility; do not install PySpark. Use a new reviewed package
version for changed code rather than replacing a same-version artifact: serverless
environment caching is a separate staleness risk. Dependency-installation sources
must be set in the environment, not a later notebook cell.

The [standalone HTTP-target notebook](../examples/journeys/serverless_runner_http_target.py)
uses the same direct package/Locust engine but does not need App discovery/OAuth.
It requires an approved reachable HTTPS agent origin and actual inference; its
source/configuration checks are not live notebook coverage. Cloud localhost
cannot reach the user's laptop. See [the complete runner/target matrix](RUNNER_TARGET_VALIDATION.md).

The harness accepts an already provisioned private profile file with exactly
`host`, `auth_type=oauth-m2m`, `client_id` and `client_secret`. It validates bounded
regular owner-only storage, the selected workspace/profile/client ID, and rejects
alternate fields before network access. A fresh child environment inherits a
fixed OS/certificate allowlist, not notebook credentials or ambient routing.
The harness does not create, edit, copy or delete this operator credential source.

To run it live, the operator must explicitly select a service-principal application
ID and an approved protected credential source available to the notebook, with
workspace assignment and App permissions. Do not place secrets in chat or run
requests. These resources have **not** been provisioned or selected; no new
principal, secret, permissions, Job or model calls occurred in this implementation.
Designated review and a bounded live lease remain required. This is a prepared
portable-auth option, not a demonstrated fix for native notebook runtime OAuth.

Official App programmatic-access documentation also provides a notebook-token
exchange recipe for direct API calls (rechecked October 11). Invoking an App from
a notebook is not categorically unsupported. That recipe does not establish this
package's independent, refreshable Locust-worker authentication; this launcher
does not implement or forward notebook tokens. Keep the API-call recipe separate
from demonstrated notebook-generated load.

First verify both processes without inference; the prepared harness now verifies
the selected profile's workspace before App discovery. Then recheck deployed
readiness and obtain a resumed bounded traffic lease: initially one excluded
probe plus one measured call, concurrency one, evaluation off. Validate direct
and loopback-API lifecycle/cancellation/report cleanup separately before widening
coverage. Classic compute remains explicitly out of scope.

Do not copy notebook tokens, laptop OAuth caches or profiles, remove the override
guards, add a forwarding proxy, or create a new service principal/secret without
the corresponding reviewed design and user authorization. Merely submitting to
an external API is a valid different journey, not proof of notebook-generated load.

## Source and evidence pointers

- [`evalsurge/client.py`](../evalsurge/client.py): explicit-profile App binding
  used by this notebook sample. The separate proposed native App-runner mode in
  ADR 0019 does not authenticate a notebook or remove its portable-worker gate.
- [`benchmark_agents/target_resolver.py`](../benchmark_agents/target_resolver.py):
  conflicting-selector rejection and independently refreshable OAuth resolution.
- Installed SDK 0.146.0 `credentials_provider.py` and runtime authentication source:
  `runtime_oauth`, notebook runtime context and `PATOAuthTokenExchange` boundary.
- Official SDK 0.151.0 source retains the relevant runtime-context boundary;
  OAuth M2M uses `ClientCredentials`. See ADR 0015 for official source references.
- [`serverless_prerequisites.py`](../scripts/validation/serverless_prerequisites.py):
  separate driver/subprocess checks, with no model inference.
- [`serverless_runner_app_target.py`](../scripts/validation/serverless_runner_app_target.py):
  backward-compatible entry point for the prepared packaged helper.
- [`evalsurge/serverless.py`](../evalsurge/serverless.py): packaged, authentication-
  blocked launcher; local source/configuration passes are not live notebook coverage.
- Protected receipt:
  `/private/tmp/evalsurge-serverless-prereq2-20261008.vyqPKE/receipt.json`.
- [Hosted-journey evidence](HOSTED_JOURNEY_VALIDATION.md) and
  [session handoff](SESSION_HANDOFF.md) preserve completed and blocked coverage.
