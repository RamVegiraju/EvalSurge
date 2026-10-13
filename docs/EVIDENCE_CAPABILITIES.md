# Load, answer evaluation and optional internal evidence

EvalSurge can measure an endpoint without importing its agent framework. Choose
an HTTP endpoint or a Databricks App, provide cases, choose load, run, and inspect
the typed report. These capabilities are independent:

| Capability | Evidence used | Requires agent tracing? |
| --- | --- | --- |
| Load measurements | Captured successful client latency and all-attempt errors at one chosen concurrency level | No |
| Answer evaluation | Captured inputs, completed answers and authoritative references | No |
| Internal profiling | Actual correlated agent-side MLflow spans | Yes, optional |
| Trace-aware evaluation | Captured answers and verified native traces required by the selected registered judge | Yes, only for those judges |

Evaluation is **off by default**. Explicit evaluation selects reviewed judges;
automatic evaluation explicitly opts into planning and judging. The planner can
select criteria, but cannot invent references, change evidence requirements or
upload scorer code. Judge-provider configuration belongs to the operator and is
independent of the agent's inference model. Judging never invokes the target again.

## Read configured and observed separately

Typed v2 results and reports include `result.evidence` (or
`report.run.evidence`), with `load_measurements`, `answer_evaluation`,
`internal_profiling` and `trace_aware_evaluation`. Each entry contains:

- `configured`: frozen feature selection, not verified credentials or provider
  compatibility. `null` means historical configuration was not recorded.
- `state`: `pending`, `observed`, `unavailable` or `off`. Successful configuration
  or preflight alone cannot make evidence observed. A failed phase may still retain
  observed partial measurements or assessments.
- `observed_count`, `total_count` and `coverage`: observed evidence and its
  recorded denominator. Missing denominators and zero-denominator coverage are
  `null`, not fabricated zero coverage. Load counts cover all recorded measured
  attempts, including failures: record coverage can be one with a 100% error rate
  or incomplete timing. Read `metrics.timing_successful_only` for successful
  latency coverage and `summary.performance` for measurement completeness.
  Profile counts cover validated traces over measured attempts;
  evaluation counts are scorer/attempt pairs over eligible captured outputs, not
  unique requests or pass rates. Aggregate assessment denominators are known only
  when every selected scorer is represented exactly once with recorded eligibility;
  an omitted scorer after early failure leaves total/coverage `null` while preserving
  scored observations. Sampling budgets can limit assessment coverage.
- `guidance`: fixed content-free explanation. Operator profiles, trace destinations,
  private experiment scopes, credentials, raw prompts and answers are not included.

`observed` means evidence exists, **not** that quality passed, all cases succeeded,
the measurement is complete or sustainable capacity was established. A false
boolean judge verdict is an observed completed assessment. Inspect the existing
per-scorer verdicts, errors, pass rates and sampling coverage. The unchanged
`summary.quality` describes whether the whole evaluation is available; partial
assessments can remain observed even when that summary is unavailable.

Historical results without frozen scorer requirements keep configuration unknown.
Recorded catalog provenance can still identify observed answer-judging outcomes.
Registered outcomes remain in `evaluation.results`, with explicit unknown-requirement
guidance rather than an invented answer-only/trace-required classification.

Leaving optional profiling off is not an internal-trace failure and does not
disable answer-only judging. Enabled but missing/correlation-invalid/budget-limited
profiling remains visible as unavailable or partial evidence and existing gaps.
Trace coverage says nothing about which internal operation caused a bottleneck.

## What readiness establishes

Static `/v2/capabilities` and `evalsurge doctor` inspect configuration only. They
do not authenticate, look up Apps, retrieve traces, execute trusted scorer code,
invoke the target or call a paid model. `runtime_verified` remains `false`.

A submitted run performs one excluded inference probe through the same invocation
protocol. It can execute tools, mutate state, warm caches and incur spend. Probe
failure prevents measured load; its capture is not a measured attempt or a quality
sample. Successful preflight establishes first-case readiness only, not readiness
of every case or concurrency capacity.

When the operator enables tracing, the same captured probe must also establish
profiling readiness even when evaluation is off. The returned trace ID,
authorized experiment and exact run/request correlation must agree, with a valid
complete span tree. Missing correlation keys can be retried within the existing
bounded collection budget; any present conflicting value fails immediately.
No target is reinvoked to obtain evidence. Failed trace readiness leaves inference
success intact but prevents measured load. See
[the profiling guide](PROFILING_AND_EVALUATION.md) for configuration and limits.

Selected judges reuse the captured probe for excluded readiness assessments.
Answer-only judges require no trace. A selected trace-required judge additionally
requires an actual trace with the exact returned trace ID, benchmark run ID,
request ID, authorized experiment and valid span tree. Missing evidence stops
before that judge or load executes. No unrelated or synthetic trace substitutes
for it. Export/collection failures receive safe evidence guidance.

After load, judges evaluate eligible captured answers without reinvocation.
Trace-required assessment eligibility uses verified measured traces; a successful
probe does not guarantee later export or measured trace coverage. Missing optional
spans, judge execution failures and failed/incomplete requests remain independent
outcomes. Neither completed load nor completed judging implies a passing quality
gate. Warmup stages, CI thresholds and native App streaming require separate
measurement contracts and are not introduced by this capability presentation.

## Verification boundary

`tests/test_hosted_evidence_contract.py` checks DTO schemas, pure presentation and
an intentional missing-trace rejection that never reaches the evaluator. Those
checks make no target or judge calls and are not live agent/LLM validation. Actual
framework/App journeys require separately approved profiles, exact resources and
bounded real-model traffic; retained failures remain failures until verified.
