# ADR 0020: Correlated trace readiness independently of evaluation

Status: Proposed; designated maintainer review required before release.

## Context

Load-only benchmarking must be able to retain real agent traces for request
mapping and internal profiling without running an MLflow evaluation job. The
existing frozen trace scope and post-load collector already support this, but
readiness only checks the excluded probe's trace for trace-dependent judges.
Consequently, a configured load-only run can send its measured workload before
discovering that instrumentation, export, access, or correlation is absent.

Generic HTTP compatibility does not imply instrumentation. An uninstrumented
endpoint remains useful for client latency/error measurements but cannot expose
internal model, tool, retrieval, or memory bottlenecks.

## Decision and data flow

1. Preserve the same RunCreate, operator-owned tracking destination and exact
   authorized experiments, one Locust engine, and evaluation-off default.
2. When tracing is explicitly configured, collect and validate the *same excluded
   inference probe* before measured dispatch, independently of selected judges.
   Reuse its verified Trace for any trace-dependent judge readiness. Never invoke
   the target again or count this probe in measured profiles or quality results.
3. Missing, inaccessible, invalid, or mismatched trace evidence fails preflight
   with a safe `trace_readiness_failed` code and fixed corrective guidance. Judge
   execution is not attempted after this failure. Unconfigured tracing remains
   compatible and explicitly client-only.
4. Offer an optional agent-process `evalsurge.tracing.traced_handler` boundary
   over an existing async handler. The operator supplies an exact experiment;
   the helper attaches benchmark metadata, captures actual input/output, and
   returns the real trace ID. It does not configure credentials/destinations,
   create experiments, reinvoke handlers, or enable framework autologging.
   It rejects Databricks tracking URIs before handler execution because an
   explicit experiment-only native span destination can override governed UC
   storage. Databricks agents must keep their existing governed instrumentation;
   this helper never silently switches them to legacy workspace storage.
5. A boundary-only span proves request mapping and observed handler duration,
   not internal bottlenecks. Native framework/model/tool instrumentation remains
   agent-owned. Raw trace content stays in the protected tracking store; report
   artifacts continue to contain bounded timing and correlation metadata only.

## Load assumptions, limits, and bottlenecks

The shipped example uses concurrency five, at most five measured invocations plus
one excluded probe, and no judges. Tracing adds agent-side instrumentation/export
work: it is part of observed production-style response latency and is never
subtracted. Export should be asynchronous; do not flush on each HTTP request.
Readiness and collection stay outside the measured Locust window.

Every agent invocation may export its trace, but report collection remains capped
at 200 traces/run and 1,000 spans/trace. At the existing 10,000-request ceiling,
full report trace coverage is not guaranteed. Budget/sampling/export failures are
explicit gaps; no extrapolated durations or invented spans fill missing evidence.
The collector's 60-second admission deadline does not interrupt an already stalled
MLflow transport; operator HTTP timeouts and production hard deadlines remain
required. Added readiness can therefore extend total run latency, not measured
target latency.

## Failure, cancellation, and compatibility

Trace readiness may fail after successful actual inference. Reports retain probe
latency/HTTP evidence and name the trace failure; they do not call that model
inference a failure or permit measured traffic. Cancellation is checked before
load after evidence work. Frozen scope, bounded retries, and exact correlation
checks remain unchanged. No cross-experiment search or broad discovery is added.

### October 12: Incremental export visibility

Installed MLflow 3.16.1 can persist completed spans through `log_spans()` before
the full trace's `start_trace()` metadata write. A non-null fetched Trace can
therefore lack the benchmark run/request keys even in the correct experiment.
The collector previously stopped retrying at that first non-null object and
classified absence as a scope mismatch. Native local SQLite reproduction
confirmed this behavior without model/provider responses; the retained failed
real-model probe did not record its initially mismatching field, so its precise
original cause remains unproven.

The same existing four-fetch budget and 0.5/2/4-second backoff now also cover
absent correlation keys, but only after the fetched trace ID and experiment
match the admitted frozen scope. A present conflicting run/request key, wrong
experiment or wrong trace ID still fails immediately, even if another key is
missing. Missing keys never authorize normalization or evaluation; exhausted
visibility is an explicit `missing` gap and skips measured load in readiness.
Malformed metadata/trees remain invalid, not indefinitely retryable. Each retry
rechecks all scope fields and the shared 60-second admission deadline. There is
no broad search, target reinvocation, exporter setting change or per-request
flush. This bounded wait is outside measured load; it does not fix slow/stalled
remote exports or certify tracing overhead. Fresh approved local HTTP/SQLite
sync and async export validation subsequently passed for the exact installed
`0.2.1.dev2026101203` wheel; this does not prove that the race occurred in that
async run or establish the original failed probe's precise cause. Designated
maintainer review, deployed-App/governed-storage validation and overhead
calibration remain separate release gates.

Legacy and v2 results add defaulted `profiling_preflight`, and v2 PhaseStates adds
defaulted `profiling_readiness`. Missing historical records use `not_run`, not a
claim of successful tracing. Successful inference retains `preflight=passed` when
trace readiness fails; profiling fails and load is skipped. Request models, SDK
targets, legacy /v1 routes, and client-only defaults remain unchanged. Strict older
typed clients may reject the additive response fields; update client/server
together. Explicitly configured
tracing becomes fail-fast rather than silently degrading *before* load. Post-load
partial coverage still preserves successful load results and independent gaps.

For Databricks, operators provision/select governed Unity Catalog trace storage
and supply the exact experiment, catalog/schema, and SQL warehouse separately.
Native `trace:/<catalog.schema.table_prefix>/<id>` identifiers receive a bounded
wire exception to the legacy 128-character limit so actual identifiers are not
lost. Collection returns `unsupported_scope` without fetching their content:
location equality alone does not prove experiment membership, because experiments
can share a UC destination and native UC TraceInfo lacks experiment identity.
Experiment authorization therefore needs a separately reviewed verification
contract; the excluded probe fails fast with fixed corrective guidance today.
Schema-wide/table-wide tracing is not authorized by the experiment-only scope.
There is no broad search, inferred destination or legacy fallback. This patch does
not provision cloud resources or establish live UC export/access.

The optional helper preserves real error-span IDs in fixed safe HTTP error headers
using invocation-local context, without replacing the original exception or
inventing a completed answer. The load worker records a bounded error-response
trace header even when the HTTP status fails. A connection failure, server crash,
or cancellation before headers still cannot promise a returned trace ID; such
missing mapping remains an explicit evidence gap.
Live App/framework validation remains a separate consent,
profile, resource, and bounded-traffic gate.

## Alternatives and trade-offs

- Mandatory global tracing would break arbitrary compatible HTTP targets and
  invent an unauthorized tracking destination. Rejected.
- Requiring evaluation to obtain traces would couple load observability to judge
  cost and misrepresent existing architecture. Rejected.
- A runner-side client span would describe transport, not agent internals.
  Rejected as a substitute for instrumented agent evidence.
- Root correlation helper plus native instrumentation keeps the boundary small,
  but cannot guarantee every framework's parenting or export semantics. Those
  must be verified using actual traces in separately approved live journeys.

## Verification and release gates

Native local MLflow telemetry-contract tests validate real spans, correlation,
scope rejection, error capture, and load-only readiness without an LLM/provider
transport. They are not agent/model validation. Schema/OpenAPI checks cover the
defaulted independent trace-readiness response fields.

The exact installed `0.2.1.dev2026101203` wheel also passed separately approved
real-model runs of the public local multi-tool LangGraph HTTP agent/runner
entrypoints with both sync and async SQLite trace export. Each run used one
excluded successful probe and four successful measured requests, with evaluation
off, six spans per request and complete measured trace coverage. Three actual
tools used disclosed synthetic documents/computation; Responses inference used
the explicitly selected `system.ai.gpt-oss-120b` model without fixture completions.
The delayed shipping span was approximately 2,001 ms. The five-user configuration
could produce at most four concurrent measured attempts under that workload cap;
these are functional smokes, not capacity or zero-overhead certification. Exact
artifact hash, run IDs and retained original failure are in
[validation](../../VALIDATION.md).

Designated maintainer review, live deployed-App/governed UC tracing and permission
verification, browser visual inspection, and calibrated instrumentation-overhead
checks remain outstanding before claiming those additional boundaries verified.

## Public upstream references

- MLflow manual tracing: https://mlflow.org/docs/latest/genai/tracing/app-instrumentation/manual-tracing
- MLflow Python API: https://mlflow.org/docs/latest/api_reference/python_api/mlflow.html
- Governed Databricks trace storage: https://docs.databricks.com/aws/en/mlflow3/genai/tracing/trace-unity-catalog

Implementation signatures were also inspected in the installed MLflow 3.16.1
source. Package/schema checks and local telemetry tests do not establish live
export, permissions, span parenting, or collection on a Databricks App.
