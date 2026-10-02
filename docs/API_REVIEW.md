# API and implementation review — 0.2.0

This is a private alpha checkpoint, not a shared-service production sign-off. The six supplied implementation findings are addressed for the local single-run milestone:

| Finding | Resolution | Validation |
| --- | --- | --- |
| Performance versus capacity | Explicit single-concurrency closed-loop measurement including ramp-up and drain | Documented metric contract and real concurrency test |
| Early-response quality bias | Seeded case × elapsed-time strata; coverage and selected IDs retained | Late-run coverage and order-independent sampling test |
| Lost partial results | Per-request fsync journal; durable run directory; interrupted-attempt recovery | SIGKILL worker test and torn-line recovery test |
| Evaluation config resolved too late | Persisted model/workspace, rubric hashes, data hash, seed, budgets; reusable plan ID; separate statuses | Frozen-model/plan reuse and evaluation-failure tests |
| Authentication leaks active slots | Auth in protected lifecycle; failures recorded and slots released | Production subprocess test with unavailable credential |
| Divergent load implementations | Removed old asyncio engine; shared event parser and production Locust coverage | Cancellation, truncation, timeout, Unicode, concurrency, auth, crash tests |

Target credentials are bound to exact server-owned connections. Unknown connections, destination mismatches, arbitrary remote targets, and caller-specified `auth_env` are rejected. This mitigates the specific credential-forwarding issue; it is not multi-tenant authorization or complete network isolation.

## Automated schema review

Raw reports: [lint](review/lint.json), [scorecard](review/scorecard.json), and [breaking changes](review/breaking-changes.json). The [unpublished 0.1 schema](review/openapi-0.1.json) is retained for reproducibility.

The linter reports zero errors. Warnings/information remain for intentional snake_case names and HTTP conventions: 202 for asynchronous submission, 422 for input validation, and a bodyless POST cancellation action. These are documented decisions; the report is not warning-free.

The generic scorecard is 77.12/100 (C), below its suggested B threshold. It reports B for documentation/security/consistency and penalizes absent bulk operations, field projection, and heuristic discoverability. Its analysis also mistakes `judge_max_completion_tokens` for a sensitive token credential and does not fully resolve response-schema references. We have not added unrelated features or changed valid Python-style names solely to raise the score. The local implementation fixes are validated; production API review remains open. This heuristic contract check is not a security audit.

## Migration from the unpublished 0.1 template

Package version is bumped to 0.2.0. `/v1` is the initial experimental wire namespace, not a stable 1.x compatibility promise.

- Replace target `auth` / `auth_env` with `connection_id`; configure exact destination bindings on the server.
- Plan creation now persists a plan and returns 201 with Location.
- Inspect `load_status` and `evaluation_status` independently. Evaluation gaps produce `completed_with_gaps`.
- Read captured records through paginated `/requests`, rather than the run snapshot.
- Invalid UUID paths return structured 422 errors. HTTP errors use a consistent envelope.
- Excess concurrent submissions return 429 + Retry-After. Idempotency-Key supports safe submission retries.
- Configure X-API-Key for remote access and use TLS. Disable forwarded client-address trust for the local deployment.

The breaking-change detector correctly fails against 0.1 for removed credential fields, security requirements, and changed plan creation status. These breaks are intentional in this pre-release version bump.

## Open production work

Distributed ownership, tenant isolation, egress enforcement, gateway body limits, retention, and provider quotas precede shared hosting. Capacity discovery needs staged/repeated windows and thresholds. Internal latency attribution needs target-side instrumentation. Judge calibration needs representative labeled data; the refund smoke test does not establish general evaluation accuracy.
