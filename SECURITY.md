# Security and deployment boundary

EvalSurge 0.2 is a local, single-tenant prototype. Bind to loopback with proxy headers disabled. Set `BENCHMARK_API_KEY` when serving beyond loopback and terminate TLS before exposing any remote connection. A shared API key authenticates the service; it does not provide tenant authorization. Documentation endpoints and the OpenAPI schema are public metadata.

Configure destination credentials only through server-owned `BENCHMARK_CONNECTIONS`. Each connection binds an authentication method to one exact URL. Unauthenticated remote targets need an exact allowlist entry. Redirects, URL credentials, fragments, and query strings are rejected. Databricks credentials are restricted to the configured HTTPS workspace. The load worker disables environment proxy and netrc credential discovery.

These controls do not make a general public load-testing service safe. Multi-tenant deployment additionally requires connection ACLs, network egress enforcement (including DNS rebinding controls), quotas, audit logging, request-body limits at the gateway, secret management, and durable job ownership. Only benchmark endpoints and agent actions you are authorized to exercise; load retries are intentionally disabled.

Artifacts contain input prompts, responses, reference data, model/profile identifiers, and request metadata. Protect the artifact directory and MLflow store with filesystem permissions and a retention policy. Do not commit live artifacts. Deleting artifacts also deletes local idempotency history. Journal flushing protects against worker-process interruption, not disk failure or filesystem loss.

Send vulnerability details privately to the repository owner or through private vulnerability reporting when enabled. Do not post credentials or private prompts in issues. Security claims apply only to this documented deployment boundary; this repository has not undergone an independent security audit.
