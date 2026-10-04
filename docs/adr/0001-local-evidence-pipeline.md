# ADR 0001: Local hosted-agent evidence pipeline

- Date: October 4, 2026
- Status: Accepted for the local alpha; not approval for shared hosting
- Review owner: repository maintainer

## Context and assumptions

The minimum integration is an owner-authorized hosted streaming agent, workload
cases, and bounded load settings. Initially support LangGraph and OpenAI Agents
examples on localhost; the wire adapters remain framework independent.

One API process owns persistent POSIX local storage and at most one active run.
Current maxima are 100 concurrent users, 10,000 attempts, 1,000 cases, and 8 MB
request bodies. Internal profiling defaults to 100 traces with 250 spans each;
the trace maximum is 200 and report pages are at most 100 requests.

These are admission limits, not demonstrated capacity. At 10,000 attempts, a
2 KB average journal event pair is roughly 20 MB/run before snapshots or MLflow
storage. The default 25,000 normalized spans at an assumed 0.5 KB/span is roughly
12.5 MB/run. Actual content sizes and retention determine disk growth. Four
simultaneous runs or multiple API processes are outside the ownership contract.

## Decision and data flow

1. Authenticate and validate caller input, exact target binding, admission, and
   idempotency; create or reuse a reviewed, persisted evaluation plan.
2. Run Locust in a separate subprocess. Journal each attempt and measure
   client latency, answer-text TTFT, errors, and throughput including drain.
3. Collect operator-scoped MLflow traces after load. Verify exact run/request
   correlation, experiment scope, a closed span tree, and collection bounds.
4. Normalize content-free waterfalls and overlap-safe wall occupancy. Preserve
   missing/rejected traces as explicit coverage gaps.
5. Select captured answers using frozen sampling and evidence requirements;
   invoke native MLflow evaluation without calling the target again.
6. Persist independent phase outcomes and serve authenticated, paginated reports.
   The public report shell contains no run data.

Endpoint-only requests receive client metrics, not invented internal timings.
Reviewed manifests inform judge suggestions but are not runtime proof. References
come from users. Brought judges are exact-version, operator-allowlisted MLflow
scorers, not caller-uploaded Python.

## Bottlenecks and failure modes

| Area | Bound/control | Residual limitation |
| --- | --- | --- |
| Load generator | Bounded requests/timeouts, one Locust process, observed concurrency | fsync, CPU, and sockets can saturate; no capacity claim without generator checks |
| Streaming | One parser, no target retries/redirects, explicit incomplete/error rows | Framework or remote exporter behavior may differ by version |
| Storage | Journal fsync, atomic snapshots, torn-line recovery, compact metadata | Local disk loss is unrecoverable; journal reads and metadata indexes grow with retention |
| Planning | Bounded preview and completion output, admission, sanitized upstream errors | Provider/authentication work needs isolated hard deadlines before hosting |
| Profiling | Trace/span limits, eventual-export retries, scope/tree validation | In-process flush cannot flush remote agents; stalled transport needs process isolation |
| Judging | Frozen catalog budgets and per-scorer sample limits; gaps/errors retained | Native brought-scorer provider budgets and code are operator responsibilities |
| Process crash | Durable attempt records and restart-aware reads/idempotency | Recovery marks interruption; it does not resume a durable queued job |

## Trade-offs

Single-owner disk avoids premature queues/databases and makes local runs inspectable,
but gives up horizontal availability and tenant isolation. Post-load collection
keeps profiling and judging out of measured latency, but extends report completion
and can lose traces to retention/export lag. Exclusive wall occupancy handles
overlap honestly, but is not a causal critical path. Trusted native scorers preserve
MLflow interoperability, but are not a secure untrusted plugin execution model.

## Compatibility and rollout

Keep `/v1` experimental and plan format 3 explicit. Regenerate and validate OpenAPI
for contract changes; document incompatible plan/lifecycle/schema changes in
`docs/API_REVIEW.md`. Verify actual frameworks, native MLflow evaluation, storage
recovery, concurrency, authentication, and error contracts in regression tests.

Keep production gates in `docs/PRODUCTION_READINESS.md`: tenant/egress isolation,
durable isolated workers, hard phase deadlines, quotas, retention, observability,
calibration, capacity methodology, and a portable audited dependency supply chain.
