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

The October 4, 2026 reports contain zero errors, 70 warnings, and 28 informational
findings. The generic scorecard is 77.28/100 (C), below its suggested B threshold.
It reports B for documentation/security/consistency and penalizes absent bulk
operations, field projection, and heuristic discoverability. Its analysis also
mistakes `judge_max_completion_tokens` for a sensitive token credential and does
not fully resolve response-schema references. We have not added unrelated features
or changed valid Python-style names solely to raise the score. The local
implementation fixes are validated; production API review remains open. This
heuristic contract check is not a security audit.

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

Distributed ownership, tenant isolation, egress enforcement, gateway limits,
retention, and provider quotas precede shared hosting. Incremental 8 MB API body
limits now exist but do not replace gateway controls. Capacity discovery needs
staged/repeated windows and thresholds. Correlated target-side profiling is
implemented; duplicate/misparented integration spans still require verification
before causal interpretation. Judge calibration needs representative labeled data;
the refund smoke test does not establish general evaluation accuracy.

## Follow-up review — October 2, 2026

This is retained historical evidence. At the October 2 checkpoint the following
findings were open. Their October 4 resolutions are recorded below.

| Priority | Finding | Impact and recommended follow-up |
| --- | --- | --- |
| P1 | `storage.recover_rows()` decodes the entire journal before parsing lines. | A torn final UTF-8 character raises `UnicodeDecodeError`, preventing recovery of earlier valid records. Read and decode complete lines independently, and add a regression test alongside the existing torn-JSON test. |
| P2 | History and idempotency use payload-heavy snapshots. | Completed runs and responses remain in memory; idempotency scans deserialize every run snapshot, and history reads inspect all runs. Separate compact metadata from request journals, index keys, and bound retained state. |
| P2 | The HTTP error contract is not universal. | Router-generated 404/405 responses use `detail` rather than the error envelope; unexpected 500 responses lack the common response headers. Handle Starlette HTTP exceptions and attach metadata on outer error responses; test these paths explicitly. |
| P2 | Invalid planner output is translated into a caller validation error. | A provider-side model validation failure becomes 422 with raw validation text. Classify invalid provider output as a sanitized upstream failure rather than invalid client input. |
| P2 | Idempotency replay bypasses restart-aware resource reads. | A replay can return persisted `running` while GET reports `interrupted`, and its 202 response omits the documented Retry-After header. Resolve the existing resource through the recovery-aware path and align replay headers. |

The existing 22 tests passed before cleanup, including real local Locust subprocesses.
Those tests do not cover all findings above. Schema tools reproduced zero errors,
40 warnings, and 17 informational lint findings; the scorecard remains 77.12/100 (C).
The 0.1 comparison reports nine intentional breaking changes and one potentially
breaking change. These checks are not production or security sign-off.

## Resolutions — October 4, 2026

| Historical finding | Current resolution and evidence |
| --- | --- |
| Torn UTF-8 prevents journal recovery | Decode complete lines independently, skip malformed shapes, and ignore a torn final multibyte fragment; regression in `tests/test_foundations.py` |
| Payload-heavy history/idempotency | Compact persisted summaries/indexes, finished-state eviction, and paginated journals; indexed storage and retention remain hosting gates |
| Inconsistent HTTP errors/headers | Starlette 404/405, unexpected 500, and recognized planner 502 use safe envelopes plus common headers; controlled path regressions |
| Invalid planner output becomes caller 422 | `PlannerResponseError` becomes sanitized upstream 502; caller data validation stays 422 |
| Restart replay differs from GET | Replay uses recovery-aware reads, consistent interrupted status, and Retry-After; regression also covers legacy default-on usage hashes |

Phase lifecycles and report/profiling shapes now have typed models. Metrics and
assessment dictionaries, timestamps, and stable history cursors remain contract
maturity work. Frozen plan format 3 adds trusted exact-version scorer references,
definition hashes, tracking URI, and trace scope; older plans may need recreation.

The optional `target.request_usage` preserves previous behavior by default and
allows incompatible Chat endpoints to omit usage extensions. Model settings remain
agent-owned; verified presets are not applied globally. Provider 400s are not
retried with changed settings. See [ADR 0002](adr/0002-model-compatibility-boundaries.md).

The 0.1 comparison still identifies nine intentional breaking changes and one
potentially breaking change. The earlier local 0.2 snapshot comparison reports no
explicit breaking changes; both detectors are heuristic, not compatibility proof.
Native OpenAPI validation, wire-level framework tests, recovery regressions, and
the full test/build results are recorded in [VALIDATION.md](../VALIDATION.md).
