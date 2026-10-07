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

EvalSurge 0.2 is a local, single-tenant prototype. Bind to loopback with proxy headers disabled. Set `BENCHMARK_API_KEY` when serving beyond loopback and terminate TLS before exposing any remote connection. A shared API key authenticates the service; it does not provide tenant authorization. Documentation endpoints and the OpenAPI schema are public metadata.

Configure destination credentials only through server-owned `BENCHMARK_CONNECTIONS`. Each connection binds an authentication method to one exact URL. Unauthenticated remote targets need an exact allowlist entry. Redirects, URL credentials, fragments, and query strings are rejected. Databricks credentials are restricted to the configured HTTPS workspace. The load worker disables environment proxy and netrc credential discovery.

For local Python, the caller is the operator and may pass an explicit `Connection`
bound to the exact authorized URL. This is not a new REST request field. Neither
client temporarily mutates global connection configuration or serializes tokens;
workers receive detached credential references. JSON response decoding is capped
at two million decoded bytes and does not infer tool timings or TTFT.

These controls do not make a general public load-testing service safe. Multi-tenant deployment additionally requires connection ACLs, network egress enforcement (including DNS rebinding controls), quotas, audit logging, request-body limits at the gateway, secret management, and durable job ownership. Only benchmark endpoints and agent actions you are authorized to exercise; load retries are intentionally disabled.

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

Send vulnerability details privately to the repository owner or through private vulnerability reporting when enabled. Do not post credentials or private prompts in issues. Security claims apply only to this documented deployment boundary; this repository has not undergone an independent security audit.
