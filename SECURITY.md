# Security and deployment boundary

EvalSurge 0.2 is a local, single-tenant prototype. Bind to loopback with proxy headers disabled. Set `BENCHMARK_API_KEY` when serving beyond loopback and terminate TLS before exposing any remote connection. A shared API key authenticates the service; it does not provide tenant authorization. Documentation endpoints and the OpenAPI schema are public metadata.

Configure destination credentials only through server-owned `BENCHMARK_CONNECTIONS`. Each connection binds an authentication method to one exact URL. Unauthenticated remote targets need an exact allowlist entry. Redirects, URL credentials, fragments, and query strings are rejected. Databricks credentials are restricted to the configured HTTPS workspace. The load worker disables environment proxy and netrc credential discovery.

These controls do not make a general public load-testing service safe. Multi-tenant deployment additionally requires connection ACLs, network egress enforcement (including DNS rebinding controls), quotas, audit logging, request-body limits at the gateway, secret management, and durable job ownership. Only benchmark endpoints and agent actions you are authorized to exercise; load retries are intentionally disabled.

The API limits decoded request bodies to 8 MB, including chunked bodies. Admission
limits concurrent planning and runs. It is not a distributed rate limiter or a spend
quota. The static report shell is public and data-free; report JSON is authenticated,
uses no-store, and is subject to the same single-tenant boundary. Keys stay in the
page's memory, not query strings or persistent browser storage. Dynamic report text
uses textContent rather than HTML injection and a same-origin CSP restricts scripts.

Runs perform one extra first-case inference preflight through the same authorized
connection before load. It can execute agent tools, mutate memory, warm caches, and
incur spend; there is no retry or rollback. Failed checks skip load/judging and expose
only fixed safe guidance, HTTP status, and correlation IDs. Raw probe captures remain
protected artifacts, excluded from measured request pages, report profiles, and
judging. Replays/restarts never automatically repeat that agent action.

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
