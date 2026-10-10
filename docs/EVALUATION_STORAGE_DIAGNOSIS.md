# Evaluation storage diagnosis — October 9, 2026

## Outcome and limits

The original LangGraph real App run completed **500/500 measured requests**, with zero
load errors, but retained only **13 of 50** selected relevance scores. Correctness
quality judging was skipped by fail-fast. The larger OpenAI App run never started.
Those results remain unchanged; a storage check does not repair the historical run.
The separately approved October 10 recovery subsequently completed supplemental
judging of those exact captures and a fresh OpenAI App benchmark. It does not
overwrite the original failure.

Offline native-MLflow tests reproduced connection-pool exhaustion independently
of target hosting. A fresh process with serial evaluation and synchronous
persistence retained exact assessment coverage. That diagnosis established a
**storage workaround**; the checkpoint core process-boundary implementation now
also has separately recorded real-LLM recovery evidence. Checkpoint publication
does not establish a release or designated maintainer approval. The shared evaluation backend can affect
both local agents and Databricks Apps.

### October 10 recovery outcome

LangGraph supplemental relevance/correctness each retained **50/50** unique
durable current-run scores, zero execution errors; sampled pass rates were
**100% / 88%**. Zero new LangGraph target calls occurred. OpenAI fresh run
`1bc6580c-bdc7-408b-a625-348934b72c54` passed **500/500** measured requests at
concurrency five, one excluded probe and both judge-readiness checks. Both
post-load scorers retained **50/50**, zero execution errors; pass rates were
**100% / 86%**. Quality verdicts remain unchanged, including false assessments.

The owner gate and independent **45/45-check** read-only audit passed exact
sample membership, source-run metadata, original hashes, durable values,
journals/metrics, complete attempt accounting and worker reaping. Total new
attempts: **703** (501 agent, 202 confirmed judge), under the approved 1,103
ceiling; no commit-unknown judge attempts. Parent environment remained unchanged.
See [validation](../VALIDATION.md) for commands, protected reports and limitations.
Never replay either completed/stopped lease. This is catalog-only local SQLite
recovery, not general trace-scorer, remote-store, capacity or judge-calibration
certification.

## Reproduction

All diagnostics used installed **MLflow 3.16.1**, actual native APIs, new private
SQLite stores and the same 50 saved real captures. Deterministic presence checks
tested storage only, not relevance/correctness. No provider was replaced, no
model response was stubbed and no target was invoked. A pre-import audit hook
rejected network connections: **zero agent, judge and network calls** per test.

| Storage test | Selected / retained | Additional evidence |
| --- | --- | --- |
| Native defaults | 50 / 19 | 41 connection-pool warnings, 31 tag-write failures, 31 assessment-write failures |
| Actual process `MLFLOW_GENAI_EVAL_MAX_WORKERS=1` | 50 / 50 | No pool/tag/assessment-write failures |
| Fresh serial process, synchronous export, batch processor disabled | 50 / 50 per check, two checks | 50 distinct durable request correlations and 50 exact current-run feedbacks per check; no pool/tag/assessment/export/refresh failures |

The final test executed 100 legitimate scorer-owned native CHAIN span scopes;
this does not establish 100 separately persisted named child spans. Three other
warnings remain. Independent read-only SQLite audit verified exact selection
membership, one feedback per request, valid values, no errors and exact source-run
metadata for all 100 assessments.

An intermediate test retained 50 scores/check but failed verification because
read-back `Assessment.run_id` was absent. Its failed receipt is preserved.
The final fresh test checks exact `mlflow.assessment.sourceRunId` metadata; neither
the absent property nor SQL `assessments.run_id` is used as a substitute.

Protected roots (not committed artifacts):

- Original real run: `/private/tmp/evalsurge-app-load-quality-20261009.0099be`
- Default reproduction: `/private/tmp/evalsurge-eval-diagnosis-20261009.vci7O6`
- Serial reproduction: `/private/tmp/evalsurge-eval-serial-20261009.BYEJkJ`
- Intermediate stricter check: `/private/tmp/evalsurge-eval-serial-spans-20261009.hCwWnj`
- Final strict check: `/private/tmp/evalsurge-eval-serial-verified-20261009.AdfokN`

Commands completed (historical record; do not replay into existing stores):

```bash
uv run --frozen --no-sync python /private/tmp/evalsurge-eval-diagnosis-20261009.vci7O6/storage_probe.py
uv run --frozen --no-sync python /private/tmp/evalsurge-eval-diagnosis-20261009.vci7O6/storage_probe_serial.py
uv run --frozen --no-sync python /private/tmp/evalsurge-eval-serial-spans-20261009.hCwWnj/storage_probe.py
uv run --frozen --no-sync python /private/tmp/evalsurge-eval-serial-verified-20261009.AdfokN/run_probe.py
```

First two exit codes: zero; intermediate: one; final: zero. Initial sandboxed
launch could not access the existing uv cache; approved offline execution then
completed. No dependency installation or paid calls occurred.

## Source-supported mechanism

Installed SQLite tracking code opens nested managed SQL sessions while retaining
outer connections. `mlflow/store/db/utils.py:152–157` checks out a connection for
PRAGMAs; `sqlalchemy_store.py:3736–3737` holds a session and calls
`get_experiment()`, which opens another at lines 853–858. `_log_spans_once()` has
the same pattern at lines 5397–5415. Concurrent workers retaining outer
connections can exhaust the pool while waiting for inner connections. Native
persistence catches some failures and continues, leaving incomplete evidence
even when judge HTTP calls succeed.

This establishes a reproducible shared-store failure mechanism, not the exact
unretained exception behind every original gap. Extra trace artifacts absent from
the DB are not alone corruption evidence: native evaluation cleans up extra
scorer/autolog traces.

EvalSurge's `configured_environment()` uses ContextVars; native MLflow reads actual
`os.environ`. Task-local flags do not configure native workers/exporters. Exporters
also cache async ownership during initialization. Do not patch `.venv`, blindly
increase pools or mutate another caller's global environment.

## Recovery boundary and historical live proposal

A fresh owned validation process must set actual environment before importing
MLflow-dependent modules:

```text
MLFLOW_GENAI_EVAL_MAX_WORKERS=1
MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=1
MLFLOW_ENABLE_ASYNC_TRACE_LOGGING=false
MLFLOW_USE_BATCH_SPAN_PROCESSOR=false
MLFLOW_ENABLE_ASYNC_LOGGING=false
MLFLOW_DISABLE_TELEMETRY=true
MLFLOW_MODEL_CATALOG_URI=
```

Pre-staging capture traces alone is not sufficient: real judge/autolog traces
can reintroduce concurrent writes. Such artifacts cannot stand in for actual
target instrumentation or satisfy trace-required scorers. Ordinary answer judging
continues to use captured pairs without requiring internal target tracing.

The following one-use lease was proposed October 9 and subsequently approved and
completed as recorded above. These are historical bounds, not new authority:

1. LangGraph: rejudge original saved captures, zero target/readiness calls, at most
   **300 judge attempts** including retries. Both scorers select the original 50
   IDs. Preserve original report/store; derive a new supplemental plan/store with
   explicit lineage, changing only ID/destination and retaining frozen settings.
2. OpenAI App: existing deployment, concurrency five, at most 180 dispatch seconds
   or 500 measured attempts, one excluded probe, 40-second attempt deadline, zero
   target/model retries. At most **501 agent + 302 judge attempts**.
3. Exact profile `e2-demo-field-eng`, workspace `1444828305810485`, Apps
   `agent-bricks-es-lg-1008` and `agent-bricks-es-oai-1008`. Agent
   `system.ai.gpt-oss-120b` (512 output tokens); judge `databricks-gpt-5-4-mini`
   (2048 output tokens, 60-second timeout, two quality retries, zero readiness
   retries). No planner, fallback, redeployment, resizing, new remote stores or
   classic compute.

New ceiling: **1,103 transport attempts** (501 agent + 602 judge), separate from
the earlier 552. Never automatically consume the stopped lease's unused allowance.
Stop on execution/persistence failure; count attempts before dispatch. Require
exact distinct selected IDs and one durable current-run feedback per request and
scorer, complete correlations/references, reports/journals and cleanup. Retain
false verdicts honestly; successful evaluation execution does not guarantee
passing answer quality. Supplemental judging is not a fresh LangGraph load test
or sustainable-capacity evidence.

See [proposed ADR 0013](adr/0013-native-evaluation-process-ownership.md) for general
core isolation; implementation is included in the publication checkpoint and designated review remains a
separate gate.

## Documentation verification

Official MLflow docs were retrieved October 9 through `llms.txt` and its referenced
evaluation-examples and production-tracing guides. The latter documents async
defaults and synchronous behavior when disabled. Installed source, not docs
alone, establishes nested sessions and batch-processor behavior. None certifies
this workaround as a general upstream fix:

- <https://mlflow.org/docs/latest/llms.txt>
- <https://mlflow.org/docs/latest/genai/eval-monitor/running-evaluation/eval-examples.md>
- <https://mlflow.org/docs/latest/genai/tracing/prod-tracing.md>
