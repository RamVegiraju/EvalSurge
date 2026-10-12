# Production release gates

This is a well-bounded local MVP, **not** a production-ready public benchmark service.
Do not replace this statement with a marketing label after a smoke test.

## Implemented local controls

- Strict input contracts, explicit lifecycle statuses, shared safe error envelopes,
  request IDs, no-store, CSP, and incremental body limits.
- Exact operator-owned target bindings, no target retries/redirects, explicit workspace
  profile selection, no caller-supplied credentials or tracking destinations.
- One active run/plan, POSIX ownership lock, fsync journals, atomic snapshots, torn
  UTF-8 recovery, restart-aware idempotency, compact history, completed-state eviction.
- Bounded cooperative/native journal owner with durable dispatch acknowledgments,
  explicit failure/drain recovery and content-free hub/journal observations. These
  observations are not calibrated generator saturation or accuracy gates.
- Frozen plans, exact registered scorer versions/hashes, evidence-qualified sampling,
  separate phase outcomes, preserved metrics when judging/profiling fails.
- Correlation/experiment validation, bounded trace/span/report collection, overlap-safe
  attribution, explicit gaps, and content-free report profiles.
- Real framework/runtime/memory/streaming and native MLflow tests, actual localhost
  Locust subprocesses, opt-in bounded live validation, OpenAPI snapshot/review tools.

## Required before shared hosting

| Gate | Required outcome |
| --- | --- |
| Tenant isolation | OIDC identities, per-run and per-connection ACLs, scoped MLflow credentials, authorization tests |
| Network isolation | Egress policy at the network layer, DNS rebinding protection, localhost/metadata-service isolation, reviewed endpoint ownership |
| Durable execution | Transactional database/queue, isolated workers, leases/fencing, heartbeats, cancel/recovery semantics and migration tests |
| Hard phase deadlines | Process isolation for App discovery/authentication and planner/trace/judge work; stop stalled credential subprocesses, transports, or native scorer code without leaving threads alive |
| Spend/resource quotas | Per-tenant/provider token/cost/concurrency quotas, registered scorer timeout/retry budgets, admission accounting |
| Storage lifecycle | Retention/deletion/export policies, indexed request/history access, bounded index memory, encrypted storage and backups |
| Operational observability | Structured safe audit logs, OTel/service metrics, readiness, SLOs, dashboards, alerting, run ownership diagnostics |
| Contract maturity | Fully typed metrics/assessment variants, timestamps/cursor history, stable SDK schema policy and migration compatibility |
| Judge validity | Labeled positive/negative and adversarial calibration sets, SME review, versioned provider/model revisions where possible |
| Trace semantics | Verify autolog/custom span parenting, duplicate operation spans, recorded tool/retrieval evidence, and category attribution for each supported framework/version |
| Capacity methodology | Warmup excluded, repeated load stages/windows, defined latency/error/quality thresholds, load-generator saturation checks |
| Runner topology | Dedicated workers separate from the API and target, recorded runner size/region/network vantage point, resource telemetry, and evidence that generator limits did not determine reported target capacity |
| Dependency/release supply chain | Portable public-index lockfile, clean Linux/macOS install matrix, supported-version CI, vulnerability/license scanning, provenance |
| Deployment verification | TLS/proxy configuration, secret manager, fault injection, recovery tests, independent security review, rollback/runbook |

## Deliberate trade-offs

Local disk and one owner avoid a premature distributed system, but cannot survive
filesystem loss or provide horizontal availability. An API key gives service access,
not tenant authorization. Thread-offloaded post-load work keeps it outside measured
latency, but is not a hard execution sandbox. Registered native scorers are trusted
operator code, not caller plugins. Static scanning is a conservative draft, not a
runtime capability/security audit. Immutable hosted model revisions are an operator
responsibility; endpoint names alone are mutable.

Keep the localhost MVP simple. Address these gates before offering shared hosting;
hosting adapters alone do not solve isolation, quotas, durability, or judge validity.
