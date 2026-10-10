# Security and deployment boundary

The `/v2` API accepts registered target IDs only. File-backed operator configuration
is captured privately per application; task-local propagation avoids cross-request
process-environment mutation. Capabilities and doctor publish configuration states,
never destinations, profiles, credential references, source, or tokens, and make no
external checks. App origins come from the operator-selected SDK profile; OAuth is
refreshed and bound to that exact origin. Conflicting ambient SDK destinations,
credentials, identity selectors, and authentication-routing overrides are rejected
before App resolution. See [v2 configuration](docs/V2_API.md).
App configuration-file selectors must also agree between the API process and
private runtime snapshot; SDK CLI credential subprocesses inherit process values.

Fixed message adapters reject unsupported top-level inference fields instead of
silently dropping them. This includes identity/routing/resume/custom-input fields;
operator-governed mapping is deferred. V2 schema diagnostics expose only bounded
public locations and fixed guidance, never values, arbitrary input keys, or raw
validator context. Planless report fallback uses locally constructed same-origin
paths and does not forward service keys elsewhere. The lightweight client changes
installation/import boundaries, not API authorization or the runner trust model.

EvalSurge 0.2 is a local, single-tenant prototype. Bind to loopback with proxy headers disabled. Set `BENCHMARK_API_KEY` when serving beyond loopback and terminate TLS before exposing any remote connection. A shared API key authenticates the service; it does not provide tenant authorization. Documentation endpoints and the OpenAPI schema are public metadata.

Configure destination credentials only through server-owned `BENCHMARK_CONNECTIONS`. Each connection binds an authentication method to one exact URL. Unauthenticated remote targets need an exact allowlist entry. Redirects, URL credentials, fragments, and query strings are rejected. Databricks credentials are restricted to the configured HTTPS workspace. The load worker disables environment proxy and netrc credential discovery.

For local Python, the caller is the operator and may pass an explicit `Connection`
bound to the exact authorized URL. This is not a new REST request field. Neither
client temporarily mutates global connection configuration or serializes tokens;
workers receive detached credential references. JSON response decoding is capped
at two million decoded bytes and does not infer tool timings or TTFT.

The unified direct SDK binds target aliases in the operator context, not in
`RunCreate`. App target construction is non-networked; resolution still uses the
existing explicit-profile/exact-origin OAuth boundary. Private snapshots propagate
to owned tasks/workers without global environment changes. The optional API server
owns its own registered aliases; a remote client cannot upload a local binding.
CLI target discovery is static and secret-free. Ordinary summaries omit protected
assessment content; explicit `--json` output can contain rationales and must be
treated as a protected export. Direct context cleanup drains work and releases
exclusive artifacts, but cannot roll back agent tools or scorer side effects.

Native readiness/quality evaluation now uses an owned child process. Operator
credentials enter through its detached OS environment, never a persisted settings
snapshot; captured input/trace transfers are bounded files with mode 0600 inside
0700 temporary directories. Fixed native flags are established before MLflow
imports, leaving caller-global environment and cached exporters untouched. Owner
deadline/shutdown cleanup reaps the child; this is not a sandbox for trusted
registered scorers, a rollback of dispatched calls, or parent-crash recovery.
Public cancellation retains its documented load-phase contract. Optional private
judge-attempt and worker-receipt journals are operator-owned, content-free and
absent from public results. The attempt cap covers the built-in catalog transport,
not arbitrary registered scorer code. Planner/trace collection and parent-side
scorer setup still have their separate ownership limitations; see proposed
[ADR 0013](docs/adr/0013-native-evaluation-process-ownership.md).

The child's detached environment still inherits operator target/auth settings;
it is not a least-privilege credential allowlist. A cleanup-verification failure
cannot produce evaluation success, but the current tests do not establish ongoing
ownership of an unreaped live child after cleanup failure. Shared hosting requires
stronger failure/crash supervision. Bounded validation recovery independently
checks worker reaping and PID/process-group absence before proceeding.

These controls do not make a general public load-testing service safe. Multi-tenant deployment additionally requires connection ACLs, network egress enforcement (including DNS rebinding controls), quotas, audit logging, request-body limits at the gateway, secret management, and durable job ownership. Only benchmark endpoints and agent actions you are authorized to exercise; load retries are intentionally disabled.

The optional `evalsurge.serving` helper is an agent-side integration convenience,
not an authenticated hosting service. Customer middleware must protect nonlocal
endpoints. Benchmark run/request/case headers and resulting state keys are
untrusted correlation data, never an authorization boundary or user identity.
Explicit request/case/run-shared keys do not isolate customer globals, tools or
stores. The handler executes only in the customer's agent process; EvalSurge does
not accept uploaded handler/decoder code. Inputs and completed outputs are bounded,
and helper errors use fixed value-free responses. Failures or cancellation do not
roll back tools, memory writes or other side effects. Optional trace IDs still
require exact authorized store/experiment/run/request validation before judging.

V2 evidence capability states are projections over already-owned evidence, not
extra target/trace/provider queries. Required probe trace-collection failures
stop readiness with safe fixed guidance and no raw exception details; they never
permit measured load or substitute invented traces.

The API limits decoded request bodies to 8 MB, including chunked bodies. Admission
limits concurrent planning and runs. It is not a distributed rate limiter or a spend
quota. The static report shell is public and data-free; report JSON is authenticated,
uses no-store, and is subject to the same single-tenant boundary. Keys stay in the
page's memory, not query strings or persistent browser storage. Dynamic report text
uses textContent rather than HTML injection and a same-origin CSP restricts scripts.

MLflow experiment links use recorded experiment IDs and their frozen tracking
destinations, not the agent/model provider's host. Operator UI overrides apply
only to the exact currently configured store. Destinations reject credentials,
queries, unsafe schemes, and non-loopback plain HTTP. The browser checks links
again and opens them with no opener or referrer; API keys are never forwarded.
Links make no automatic tracking-store requests and grant no MLflow permissions.
The operator must bind a configured UI to the correct store. Full MLflow evidence
may contain protected content beyond the report's content-free profiling.

Per-assessment judge rationales are protected evaluation evidence, not sanitized
telemetry: they can quote prompts, answers, references, or sensitive source content.
Authenticated run/report JSON includes bounded rationales; protect exported reports
and the artifact directory accordingly. Rationales are text-only in the UI and are
not interpreted as links, HTML, or instructions. Native execution errors never
export raw messages, stack traces, or error-associated rationales. Only catalog-owned
error codes map to specific fixed guidance; registered scorer errors get a generic
safe diagnostic. Truncation is a size bound, not secret redaction.

Runs perform one extra first-case inference preflight through the same authorized
connection before load. It can execute agent tools, mutate memory, warm caches, and
incur spend; there is no retry or rollback. Failed checks skip load/judging and expose
only fixed safe guidance, HTTP status, and correlation IDs. Raw probe captures remain
protected artifacts, excluded from measured request pages, report profiles, and
quality samples. Selected judges reuse the captured probe for one readiness
assessment each before load; these extra calls can incur spend and disclose the
same inputs/outputs/references as quality judging to the configured provider.
Static setup failures avoid target traffic; catalog readiness has zero SDK retries
and no additional MLflow retry layer. Errors expose fixed guidance only. Trusted
registered scorer transports/retries remain operator-owned. Replays/restarts
never automatically repeat agent or readiness actions.

Interactive documentation uses pinned, self-hosted Swagger UI assets plus an external
same-origin initializer. No CDN/inline-script policy exception is needed. Remote
schema validation and persistent authorization are disabled. `/docs` redirects to
`/docs/`; `/redoc` redirects to the same supported UI. Documentation, its assets,
and the schema remain public metadata; interactive API operations still require
normal authorization. Vendored hashes/license/provenance live under
`benchmark_agents/docs_ui/vendor/`; review upstream security fixes on each update.

Setup scanning is explicit and local, AST-only, size-bounded, and never executes or
exports raw source/constants. Manifests are untrusted planning context, not proof of
runtime capabilities. Registered scorer aliases are operator-owned configuration.
MLflow can deserialize executable scorers in supported trusted environments; never
allow arbitrary uploaded Python, caller-selected registry destinations, or unreviewed
administrative scorer definitions. Native scorer transport/time/spend settings remain
the operator's responsibility.

Trace collection validates exact run/request IDs, configured experiment membership,
trace-ID equality, and complete span-tree timing. It never follows caller-supplied
tracking destinations. Report profiles strip inputs, outputs, and attributes, but
span/tool names can still be sensitive. Full source traces and captured request data
remain protected evidence, not sanitized public telemetry.

Artifacts contain input prompts, responses, reference data, model/profile identifiers, and request metadata. Protect the artifact directory and MLflow store with filesystem permissions and a retention policy. Do not commit live artifacts. Deleting artifacts also deletes local idempotency history. Journal flushing protects against worker-process interruption, not disk failure or filesystem loss.

Local assistant configuration under `.isaac/` is not project source. Keep it out
of commits and source distributions; release verification checks archive member
names without reading or exposing its contents. This check is not a comprehensive
secret scanner.

Send vulnerability details privately to the repository owner or through private vulnerability reporting when enabled. Do not post credentials or private prompts in issues. Security claims apply only to this documented deployment boundary; this repository has not undergone an independent security audit.
