# API and implementation review — 0.2.0

## Unified direct SDK milestone — October 8, 2026

[ADR 0011](adr/0011-unified-direct-and-remote-sdk.md) was recorded before
implementation and requires designated maintainer review. Direct execution now
accepts the existing v2 `RunCreate` and external operator target bindings. Optional
typed remote access shares the same result/status/report models and lifecycle
methods. Legacy local keyword calls, remote dictionary returns and `/v1` remain.
The change does not introduce a second engine, target replay or a new hosting
authorization mechanism.

V2 responses now declare evaluation/assessment variants, sampling coverage and
existing lifecycle/evidence-gap enums in OpenAPI. Partial historic evaluation
payloads retain their serialized field presence; unknown metrics/coverage do not
become fabricated observations. Response-schema narrowing can affect generated
clients even when runtime JSON is unchanged: regenerate those clients and review
exhaustive enums. No new endpoints or caller credential/model selectors are added.
Shared value-free validation distinguishes bad fields from nonfinite JSON.

CLI local mode, static target discovery, safe metric summaries and protected
opt-in JSON are additive. Completion remains separate from quality passing;
threshold exit gates are deferred. Current-run verification belongs in
`VALIDATION.md`; historical full-suite or App results do not validate this new SDK.
Do not claim maintainer approval, remote CI, live notebook auth, sustainable
capacity or judge calibration from the static checks.

## Registered-target v2 façade — October 7, 2026

The additive `/v2` API uses registered targets, defaults evaluation to off, admits
before deferred planning, and shares the existing coordinator and Locust engine.
Status, result/report, cancellation, and static capabilities have separate
contracts; v2 errors add fixed phase, retryability, and guidance fields while v1
error components and wire envelopes remain unchanged. App SDK resolution and
OAuth are operator-owned, and planning failures remain reportable through v2.
See [the guide](V2_API.md) and [ADR 0009](adr/0009-v2-databricks-app-boundaries.md).
Designated maintainer review is still required.

The schema tools evaluated 14 operations: [lint](review/v2-lint.json) reports
**0 errors, 130 warnings, 50 informational findings**; the
[compatibility comparison](review/v2-breaking-changes.json) against HEAD
`41311ac9b523e37ba7e4909fdbd1bd84f5d915bf` reports **0 breaking and 0 potentially
breaking changes**, with 28 additive/nonbreaking findings. The
[scorecard](review/v2-scorecard.json) is **71.76/100 (C)**, below its suggested B
threshold; this is not an API sign-off. Intentional snake_case fields, asynchronous
202 acknowledgments, 422 validation, and bodyless cancellation remain. Generic
cache/bulk/projection recommendations do not justify caching protected reports
or adding unrelated local-alpha features. Tools do not fully resolve schema
references or runtime headers. Controlled wire/integration tests establish
behavioral evidence separately from these heuristic scores.

Legacy v1 idempotency hashes remain recognized despite the new optional protocol/
session fields. The new `databricks-agent-runtime` adapter enum requires exhaustive
clients to update. V1 retrieval of a v2 run without a frozen plan returns safe
409; v2 JSON reports handle failed/interrupted planning. The browser report shell
now renders those planless runs through a same-origin v2 fallback. Results describe one
closed-loop load level, not sustainable capacity; assessment dictionaries remain
an explicit schema-maturity limitation at this October 7 checkpoint. ADR 0011's
October 8 change types v2 evaluation outcomes; v1 retains its compatibility shape.

## Client/input/failure follow-up — October 7, 2026

The follow-up patch fixes cancellation acknowledgments, mixed-version history
links, planless browser reports, safe field-specific v2 validation, and the remote
dependency surface. The App-default finding was checked against current official
guidance: DurableAgentServer `/api/invocations` remains the default; MLflow
AgentServer `/responses` is explicit legacy compatibility. See
[ADR 0010](adr/0010-client-input-and-failure-contracts.md), pending maintainer review.

Compatibility changes need attention beyond schema-diff tools:

- The optional v2 `error.errors` response field is additive; v1 envelopes remain.
- V1 history entries for v2 runs now link to v2 status, not an unusable v1 resource.
  V1-origin run links remain unchanged. Cancellation-request acknowledgment is not
  a new polling/terminal state.
- Fixed message adapters reject formerly ignored top-level inference fields and
  simultaneous `query`/`messages`. This is an intentional behavioral tightening
  across v1, v2, and local Python, despite no removed OpenAPI request field.
- Plain installation is now remote-only; local/server consumers must select the
  `server` extra. The `agents` extra includes it, preserving the checkout developer
  workflow. Lazy local APIs retain their signatures with the extra installed.
- Runtime responses reject explicitly unfinished assistant messages even when the
  outer invocation/handler reports completion. No partial answer is published;
  omitted message status remains compatible with current normalized output.

Controlled API/Locust/SDK, shipped-DOM, and isolated-wheel tests validate these
behaviors. Separate bounded live App evidence is recorded in `VALIDATION.md`; it
used the local facade/resolver, not live v2 HTTP submission or a deployed EvalSurge
service. Neither establishes remote CI success or production readiness.

Each evaluated criterion now includes an additive `assessments` array in run and
report responses, available identically through Python and REST. Exact request
tags associate bounded judge rationales with case/request IDs; quality failures,
execution errors, and unavailable evidence remain distinct. Rationales can quote
protected evaluation content; profiles and fixed execution diagnostics remain
content-free. Old reports are not re-judged or silently backfilled. This response/
disclosure change requires maintainer review of [ADR 0008](adr/0008-request-assessment-reasons.md).

New runs now include a mandatory first-case inference preflight. The 202 submission
contract and request/hash/plan formats are unchanged; poll the run's `preflight`
field for safe diagnostics. Failed checks terminate with skipped load, profiling,
and evaluation, and remain reportable. Enum-aware clients must accept the new
`preflighting` overall status and `skipped` load/profiling outcomes. Historical
snapshots use `preflight.status=not_run`. The extra invocation can execute tools
and incur cost but is excluded from measured metrics, profiles, and quality results.
Selected judges reuse its capture for separate readiness assessments. This material
lifecycle change requires maintainer review of [ADR 0004](adr/0004-fail-fast-inference-preflight.md).

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

## Shared Python/REST coordinator — October 5, 2026

REST routes, acknowledgment codes, authentication, pagination, error envelopes,
legacy usage hashes, and plan format 3 remain. Python uses the same coordinator
and Locust engine. New `http-json` request-adapter and `invalid_response`
preflight-error enum values require exhaustive enum clients to update; JSON TTFT
and first-event timing are unavailable, not zero.

The schema review versus `d83ef4a` reports zero explicit/potential breaking changes,
zero lint errors, 74 warnings, and 28 informational findings. The design score is
77.31/100 (C), not a B-grade or production sign-off. The installed tools require
`--output`; the skill quickstart's `-o` invocation failed before rerunning with the
supported option. Heuristic compatibility tools do not establish behavioral
compatibility; local REST/Python/Locust, recovery, and framework tests do.

Storage regressions tighten partial admission, repeated shutdown cancellation,
subprocess cleanup, safe configuration errors, and terminal reports. The shared
serialized input bound also protects local Python before planning. Snapshot/summary
writes are not transactional; truthful in-process terminal receipts may be lost on
restart after persistence failure. New admission fails closed until storage is
restored and the runner reopened. Startup rebuilds history from authoritative
snapshots once, trading cold-start I/O for correct recovery metadata.
See [ADR 0005](adr/0005-shared-coordinator-python-json.md); maintainer review is pending.
