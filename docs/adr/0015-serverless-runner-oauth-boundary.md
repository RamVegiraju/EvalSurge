# ADR 0015: Serverless notebook runner OAuth boundary

- Status: Proposed; designated maintainer review and live validation required
- Date: October 10, 2026; package-portability review October 11, 2026
- Scope: The notebook validation harness, not a new public SDK or load engine

## Context and source evidence

The two target-hosting choices remain an independently hosted HTTP agent and a
deployed Databricks App. A serverless notebook is an optional **load-generator
location**. Its direct runner must still use the existing coordinator and sole
Locust subprocess. Running an API client in a notebook is a different topology:
target load then originates at that API host, not at the notebook.

The October 8 prerequisite run in `e2-demo-field-eng` established native driver
OAuth but not independent subprocess OAuth. It performed zero inference calls.
The independent subprocess returned the safe error class `ValueError`. A
successful Jobs task is not proof that its internal authentication checks passed.

Review of installed Databricks SDK 0.146.0 and official tag 0.151.0 finds the same
relevant contract. `runtime_oauth` calls `_runtime_native_auth` and obtains its
exchange subject from injected runtime credentials. Runtime providers inspect
notebook/REPL context; the SDK does not publish a mechanism to recreate that
context in an arbitrary independently launched Python process. This is not a
claim that every future serverless runtime lacks subprocess-native OAuth. It is
not a source-backed reason to assume a dependency upgrade fixes this receipt.

The official App programmatic-access guide, retrieved again October 11, documents
notebook-token exchange for an audience-scoped App token. That establishes a
notebook API-call recipe, not this launcher's independently refreshable Locust
subprocess boundary. The current milestone does not implement that exchange or
forward notebook tokens. It must not describe notebook-to-App invocation as
categorically unsupported, nor label the documented recipe a validated load path.

The official SDK `oauth-m2m` strategy instead uses the explicit workspace,
service-principal client ID and OAuth secret to construct a refreshable
`ClientCredentials` provider in each process. Official authentication guidance
supports this unattended-workload configuration. Federation is another upstream
option only when the operator has separately configured an appropriate trust
policy and independently refreshable external subject-token source; this harness
does not infer that a notebook's injected token is such a source.

Sources reviewed October 10–11, 2026:

- App programmatic access, including the notebook exchange recipe:
  `https://docs.databricks.com/aws/en/dev-tools/databricks-apps/connect-local`
- Databricks OAuth M2M documentation:
  `https://docs.databricks.com/aws/en/dev-tools/auth/oauth-m2m`
- Official SDK 0.151.0 `databricks/sdk/credentials_provider.py`,
  `databricks/sdk/runtime/__init__.py`, and `databricks/sdk/oauth.py`:
  `https://github.com/databricks/databricks-sdk-py/tree/v0.151.0/databricks/sdk`
- OAuth federation guidance:
  `https://docs.databricks.com/aws/en/dev-tools/auth/oauth-federation-provider`
- Serverless environment/dependency guidance:
  `https://docs.databricks.com/aws/en/compute/serverless/dependencies`

## Proposed decision

Provide a reviewed launcher in the serverless notebook sample. The notebook
launches an EvalSurge owner process using an explicit, operator-provisioned private
OAuth M2M profile file. That owner launches normal Locust workers. Each process
uses the SDK's own refreshable provider; no driver access token, notebook bearer
token, laptop OAuth cache, forwarding proxy or PAT is copied.

Before network access, validate the selected file as bounded, owner-only regular
storage in an owner-only directory with stable trusted ancestry, exactly the
selected named profile, exact selected HTTPS workspace,
`auth_type = oauth-m2m`, expected service-principal client ID, a nonempty secret,
and no alternate credential/routing fields. Do not create, populate, modify or
delete this operator file. Never return its values, contents or private path.
Reject symlink ancestry, untrusted owners and writable ancestor directories
except root-owned sticky temporary roots. Check file identity/mode/size/mtime
again after reading. The SDK later reopens the selected file; these checks narrow
but do not eliminate same-user mutation between validation and SDK reads. The
operator must not rotate or move the file/directory during a run; this is a
trusted-operator boundary, not a defense against arbitrary same-user code.

Create a fresh child environment from a small documented OS/certificate
allowlist, the reviewed source root, and the two explicit profile-file selectors.
Notebook credential/routing variables are not inherited. This is process
isolation, not removal of the resolver guard: the owner and worker must still
pass the unchanged conflicting-selector checks. Do not mutate the notebook's
global environment or permit extra supplied child environment values.

The readiness sequence is configuration → owner workspace/identity/OAuth → App
discovery → independent worker OAuth → existing excluded target preflight → one
measured request. Store only fixed, content-free blocker codes in receipts.
Credentials remain outside `RunCreate`, persisted run configuration and reports.
No new hosting/decoder abstraction or public authentication contract is added.

## Installation and package boundary

The reviewed launcher lives in `evalsurge.serverless`, included by the existing
wheel package configuration. Installed notebooks import `parse_options` and
`launch_runner_async` from that module; `await launch_runner_async(options)`
uses its installed package directory and launches `python -m evalsurge.serverless`.
No repository checkout, source-root widget, `sys.path` modification or customer
agent code is needed. The historical validation script is a thin compatibility
entry point/alias to that same implementation, including diagnostic globals;
there is no forked runner. An optional explicitly reviewed package-root argument
is retained only for source-checkout validation compatibility.

Install an exact reviewed wheel with its `server` extra in the standard serverless
notebook Environment side pane, using an authorized workspace/volume artifact.
Apply installs dependencies and restarts Python. Jobs notebook tasks inherit the
notebook environment unless separately overridden; Python wheel/script tasks
need an explicitly configured environment. Do not install PySpark or treat a
runtime notebook cell's proxy/environment settings as installation configuration.
Verify native dependencies for both supported runtime architectures, and change
the reviewed package version when code changes to avoid same-version caching.
The operator's protected OAuth file is separate from package/environment setup;
the helper never provisions a secret or claims installation authenticates a worker.

## Load, data flow and limits

The initial proposed lease is concurrency one, at most one excluded preflight
plus one measured App invocation, five seconds of measured dispatch, evaluation
off, no planner and no retries added by this harness. The deployed source must
independently enforce the declared model/tool/output-token bounds. Two App
invocations are not automatically two model turns or a monetary cap.

`notebook → isolated EvalSurge owner → Locust → exact discovered App origin`
remains the load path. Request journals and typed reports stay in protected local
runner artifacts. The source notebook returns an aggregate receipt, not answers,
references, raw SDK errors, child output or headers. SDK/token refresh and App
lookup are independently bounded diagnostics, not inference or capacity evidence.
The generator's disk and scheduling effects require separate measurement-health
verification; these auth changes do not establish zero observer overhead.

## Failure, cancellation and cleanup

Missing profile, wrong owner/mode, unsupported fields, wrong workspace/client ID,
ambient selector conflict, owner/worker OAuth failure and App discovery failure
stop before target inference. Child timeout must terminate and reap the owned
process group; it is not success. Stdout uses a bounded 64 KiB reader, not an
unbounded disk spool; output overflow terminates the owned group and blocks the
receipt. A notebook cancelling the async await signals the owned launcher and
waits for its cleanup instead of detaching an `asyncio.to_thread` worker. No
alternate profile, workspace, App, token
source or classic compute is selected. Runner context cleanup precedes a success
receipt; it does not stop the App, remove Runtime Stores or erase failure evidence.

Native October 11 diagnostics reproduced a transient macOS `EPERM` while checking
an exiting process group, both inside and outside the assistant sandbox. An OS
verification error is never group absence: reap only the known owner, then make
one read-only group probe. Cleanup is confirmed only if that probe explicitly
reports `ProcessLookupError`; surviving groups, persistent permission errors and
failed reaping stay unverified. No additional terminating group signal is sent
after group visibility is unknown. This corrects false-negative local cleanup
receipts without treating owner exit alone as descendant cleanup or extending the
claim to live notebooks, remote agent actions or abrupt parent loss.

The operator owns credential-file creation, rotation and eventual removal. A
secret store and service-principal permissions must be explicitly selected and
authorized; merely naming the laptop profile `e2-demo-field-eng` does not provide
these resources in serverless compute. App start/deployment, new identities,
secret creation, permission grants and live notebook submissions are separate
mutations requiring explicit authority and a bounded validation lease.

## Trade-offs and compatibility

- Optimizes independently refreshable worker auth and exact resource binding.
- Sacrifices zero-setup personal notebook auth until runtime-native worker support
  is demonstrated with a current runtime and a separately approved receipt.
- Introduces a long-lived operator secret source, requiring restricted storage,
  least-privilege grants and rotation. It is not a shared-hosting security sign-off.
- Preserves existing profile-only `Agent.databricks_app`, `/v1`, `/v2`, target
  adapters, invocation contracts and one Locust engine. Public requests gain no
  credential fields. Existing laptop profile use is unchanged.
- Defers credential federation, notebook-hosted public APIs, distributed workers,
  durable cloud artifacts and higher load. A remote API submission sample must
  be labelled remote submission, not notebook-origin load validation.

## Acceptance and current gate

Pure configuration tests must reject unsafe sources without auth/model calls and
prove that notebook credential variables cannot enter the child environment.
Native no-inference diagnostics must establish owner and independent worker
workspace/client identity, OAuth availability and App-origin binding. Only then
may the explicitly authorized two-invocation real-model smoke run proceed.
Afterward independently retrieve report/result/status and verify owner cleanup.

At proposal time no service principal, protected OAuth source, secret permission,
new notebook submission or live notebook-to-App pass is established. Maintainer
review and exact resource/traffic approval remain gates.
