# Validation — 0.2.0

Validated locally on macOS/Python 3.12 on October 4, 2026. CI is configured for
Linux/Python 3.11–3.14; remote CI and branch-protection settings have not been
verified/enabled by this local work.

## Current verification — October 4, 2026

| Check | Actual result |
| --- | --- |
| `uv sync --locked --extra agents --group dev` | Locked environment synchronized |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 64 files already formatted |
| `MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync pytest -q --tb=short` | 98 passed, no skips; 38.40 seconds |
| `uv run --no-sync python scripts/export_openapi.py --check` | Snapshot matches |
| `uv run --no-sync openapi-spec-validator docs/openapi.json` | Valid OpenAPI |
| API review tools | 0 errors, 70 warnings, 28 informational findings; 77.28/100 (C), not a B sign-off |
| Breaking-change review | 9 intentional breaks + 1 potential break versus archived 0.1; no explicit breaks versus earlier local 0.2 snapshot |
| Distribution build and `scripts/verify_wheel.py` | sdist/wheel built; API, report, and self-hosted docs assets verified |
| OSV audit of hashed lock export | 181 applicable dependencies; zero known vulnerabilities |
| `git diff --check` | Passed |

The suite has one SQLAlchemy loader-strategy warning and three MLflow/pandas
positional-argument warnings. These are recorded, not suppressed. Native registered
`RetrievalGroundedness` evaluation receives a real correlated Trace; only its model
judge boundary is controlled. No paid calls are required by the suite.

New model regressions check actual SDK-emitted JSON through real LangGraph and
OpenAI Runner streams: exact Databricks-mini presets, portable unknown-model
settings, bounded token parameters, omitted optional reasoning/parallel/store
settings, no retries/model switching after provider 400, and isolated memory/tools.
The hosted payload's usage extension is optional. Tests also validate the README
curl body and preserve legacy default-on idempotency hashes while rejecting an
explicit usage opt-out under the same key. The portable-wire and legacy-replay
regressions were observed failing before their fixes.

### Docs and quality-first report — October 4, 2026

The initial docs regression failed on inline JavaScript under `script-src 'self'`;
report regressions also failed on omitted rationale, indistinct missing/zero
outcomes, absent coverage details, and stale evidence after invalid input. The
first focused post-fix run passed 12 tests; expanded docs/rendering/profiling/wheel
verification passed 27 tests before the final operation-hotspot regression.
The final full suite passes 75 tests with the same four upstream warnings.

Swagger UI v5.33.1 is self-hosted from a verified immutable upstream commit,
with its Apache-2.0 license, SHA-256 hashes, and official Git blob identifiers.
The global CSP is unchanged. Tests check public docs/assets versus authenticated
operations, local asset integrity, external initialization, no remote validator,
no persistent authorization, and prefix-relative URLs. No Python dependency
versions changed for this UI work.

Report tests execute shipped JavaScript using Node.js v26.0.0 and a controlled DOM.
They cover rationale, pre-load readiness, registered judge versions, Boolean zero
rates versus unknown results, numeric/unaggregated scores, partial assessments,
selected/eligible/scored counts, judge errors, missing traces, safe text,
pagination/stale-data handling, operation hotspots, and reversible enclosing-span
filtering. Node is a development prerequisite; CI explicitly configures Node.js 24.
This does not establish browser layout or accessibility conformance.

The owned preview was restarted on loopback port 8000 using
`artifacts/framework-upgraded-live-fixed/`. HTTP checks confirm `/docs` and `/redoc`
redirect to `/docs/`; the docs shell, JS/CSS, Swagger assets, OpenAPI, report shell,
and report assets all return 200 with the same CSP. The served saved live report
`5a8e4b7c-35bc-46ba-a97e-9bad3cd4338b` was also rendered through the shipped script:
two request profiles, two actual judge outcomes, rationale, 1/2 eligible-answer
selection per judge, 100% Boolean rates on the scored answers, and tool
waterfall/hotspots are present. This reuses saved evidence, not new paid calls.

Additional full offline smoke:

```bash
MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync python -m examples.framework_e2e \
  --artifact-dir artifacts/report-ui-offline-20261004 --agent-port 0 --api-port 0
```

| Framework | Run ID | Successful requests / correlated traces | Spans |
| --- | --- | --- | --- |
| LangGraph | `0e9746a7-4068-41f7-84f3-8b5c3b265b0a` | 2/2 and 2/2 | 26 |
| OpenAI Agents | `bc2342d4-83dd-4923-bf9b-b87c42201393` | 2/2 and 2/2 | 32 |

Both new report JSON files render through current JS, including the
performance-only state and focused tool spans. Provider responses are fixtures and
judging is deliberately disabled. Native outer-tool missing-input/output hints
remain; inner custom spans retain tool evidence. These smoke rates do not establish
capacity or model quality. The demo subprocesses exited; only the saved-evidence
preview remains running. Manual browser/desktop/mobile review is still pending.

### Full offline API smoke after compatibility changes

```bash
MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync python -m examples.framework_e2e \
  --artifact-dir artifacts/framework-compatible-offline --agent-port 0 --api-port 0
```

| Framework | Run ID | Successful requests / correlated traces | Spans |
| --- | --- | --- | --- |
| LangGraph | `5cd2c06d-e0c1-44d5-a7c1-16c344651bb3` | 2/2 and 2/2 | 26 |
| OpenAI Agents | `0f8c38b2-b8fb-4ced-a074-dcbe2cd532cd` | 2/2 and 2/2 | 32 |

Real REST, Locust subprocess, streaming, frameworks, memory, MLflow correlation,
profiling, and paginated report retrieval pass. All four inspected native traces
are OK, contain the synthetic policy tool output, and answer “Opened items cannot
be refunded.” Model responses are fixtures; quality scoring is explicitly disabled.
The processes exited normally and no demo servers are left running.

### Bounded live evidence on the selected workspace

Workspace: `https://dbc-a5d4177a-49dc.cloud.databricks.com`.
User-selected profile:
`ug-oauth-dbc-a5d4177a-49dc.cloud.databricks.com-4f7af981-8977-4042-b90e-a5dea5b62e19`.
SDK/keyring authentication is used; no plaintext auth storage. The verified
`databricks-gpt-5-4-mini` endpoint was READY/NOT_UPDATING. Pricing-catalog fetching
was disabled with `MLFLOW_MODEL_CATALOG_URI=''`; cost was not benchmarked.

October 4 live runs before the final compatibility-boundary refactor:

| Framework | Run ID | Targets / traces | Relevance and correctness |
| --- | --- | --- | --- |
| LangGraph | `cf412d30-01e1-4781-9f69-de3470070ece` | 2/2 and 2/2, 26 spans | One answer per criterion, both true, no judge errors |
| OpenAI Agents, corrected setting | `5a8e4b7c-35bc-46ba-a97e-9bad3cd4338b` | 2/2 and 2/2, 32 spans | One answer per criterion, both true, no judge errors |

Observed LangGraph successful TPS was 1.9311, latency p95 999.57 ms, and answer TTFT
p95 918.06 ms. OpenAI Agents TPS was 1.1832, latency p95 1645.79 ms, and TTFT p95
1501.37 ms. Two requests per framework establish wiring, not capacity, stable
percentiles, or judge calibration.

The preceding Agents attempt `fa0b1f78-2653-4d19-b986-f631250e5233` failed 2/2.
Recorded trace errors identified function tools plus `reasoning_effort="low"` as
unsupported for this model/API combination. The successful bounded retest used
`none`, without repeating the successful paid LangGraph run. Its retained artifacts
are in `artifacts/framework-upgraded-live-fixed/`; the failure remains in
`artifacts/framework-upgraded-live/`.

The final exact-pair preset preserves these known wire settings and is verified
with controlled real-framework HTTP tests plus the full offline smoke. No additional
paid runs were repeated for that refactor. The earlier October 2 framework run in
`artifacts/framework-live/` retained successful target/trace calls but judging
failures/timeouts and a `completed_with_gaps` outcome; later success does not
establish that earlier transport failure's cause.

### Remaining gaps

- Browser/visual interaction was not verified: Computer Use permission is unavailable.
  Static assets, report JSON, and CSP contracts are tested, not visual rendering.
- Duplicate/misparented integration spans can inflate the `parallel` bucket. Occupancy
  is not proof of independent concurrency or a causal critical path. Inner custom
  tool spans contain evidence when outer native tool spans have empty outputs.
- Direct catalog judging is Databricks-specific; hosted-target provider independence
  does not imply universal planner/judge/native-provider transport support.
- Dependencies were upgraded to the newest compatible versions reachable from the
  configured mirror, not all upstream-latest versions. Public PyPI installer access
  failed even outside the sandbox; see `docs/DEPENDENCIES.md` for release gates.
- Audit evidence applies to the local Python 3.12 graph; the supported-interpreter
  audit matrix, remote CI, portable clean installs, and production gates remain open.

## Multi-model smoke — October 4, 2026

The operator authorized the same previously selected workspace/profile. Runtime
discovery found READY / NOT_UPDATING Foundation Model chat endpoints for
`databricks-claude-haiku-4-5` and `databricks-gemini-2-5-flash`.
No endpoint configuration, permission, or hosting resource was changed.
The earlier GPT-5.4 mini paid evidence is retained, not repeated.

Each full case uses two synthetic target requests at concurrency two, a reviewed
planner response, at most one captured answer per selected scorer, and scoped
local MLflow traces. Target calls have a 1,024-token cap, 30-second provider timeout,
zero provider retries, and at most three Agents turns. Planner/judge retry budgets
remain independent and frozen. These tests are wiring checks, not model rankings,
sustainable capacity measurements, stable percentiles, or judge calibration.

Commands below redact only the operator's profile identifier; the exact selected
profile/workspace are retained in ignored frozen plans:

```bash
MLFLOW_MODEL_CATALOG_URI='' uv run --no-sync python -m examples.framework_e2e \
  --live --profile YOUR_CONFIRMED_PROFILE --model databricks-claude-haiku-4-5 \
  --planner-model databricks-gpt-5-4-mini --judge-model databricks-gpt-5-4-mini \
  --artifact-dir artifacts/model-matrix-live-20261004/haiku \
  --agent-port 0 --api-port 0

MLFLOW_MODEL_CATALOG_URI='' EVALSURGE_DEMO_REQUEST_USAGE=false \
  uv run --no-sync python -m examples.framework_e2e \
  --live --profile YOUR_CONFIRMED_PROFILE --model databricks-gemini-2-5-flash \
  --planner-model databricks-gpt-5-4-mini \
  --artifact-dir artifacts/model-matrix-live-20261004/gemini-fixed-gpt-planner \
  --agent-port 0 --api-port 0
```

| Target / framework | Run ID | Successful / correlated requests | Spans | Quality |
| --- | --- | --- | --- | --- |
| Claude / LangGraph | `695a53f7-9b08-4d6c-b826-6ad0e5d43ccb` | 2/2 and 2/2 | 26 | Relevance and correctness: one true assessment each, zero judge errors |
| Claude / OpenAI Agents | `2762605e-f1ed-46df-b96e-97f5f03c1845` | 2/2 and 2/2 | 32 | Same; GPT planner and judges |
| Gemini / LangGraph | `cc2b42dc-b54a-4b4b-8bda-6e014edfdece` | 2/2 and 2/2 | 24 | Same; Gemini judges, GPT planner; groundedness suggestion remains needs_data |
| Gemini / OpenAI Agents | `f16553eb-19e8-4998-a1bf-695fb9a9041d` | 2/2 and 2/2 | 16 | Same; Gemini judges, GPT planner |

All four report JSON files were retrieved by the live helper and rendered through
the shipped JavaScript. The original missing-trace report also renders its gap.
Local native Trace inspection verifies exact run/request correlation, actual
policy tool output, and isolated initial memory reads. This is not browser layout
validation. Cached Claude/Gemini report previews are served on loopback ports
8001/8002; they make no new inference calls when reading reports.

### Retained failures and fixes

- Six bounded canary/diagnostic calls used a 256-token cap, 30-second timeout, and
  zero retries. Claude rejected JSON-object mode with HTTP 400 but accepted tool
  streaming. Gemini accepted JSON-object mode, rejected `stream_options` with
  HTTP 400 twice (the second call captured its exact reason), then accepted the
  explicit no-extension tool stream. Results are in ignored `canaries.json`.
- The first Gemini LangGraph run, `7e621f61-03a2-45de-8163-d37ed783afba`, passed
  2/2 target requests and both Gemini judge assessments, but had zero correlated
  profiles. MLflow OpenAI autologging could not reconstruct a completion with a
  null ID, leaving spans unfinished. Its snapshots/report remain under `gemini/`.
- A controlled null-ID stream reproduced that trace loss in both real frameworks:
  two regressions failed with coverage zero before the fix. The demo now uses
  LangChain autologging and explicit public Agents model-stream spans, with
  duplicate OpenAI autologging and the SDK's external trace exporter disabled.
  It neither fabricates completion IDs nor patches an installed dependency.
- The intermediate same-model Gemini retest in `gemini-fixed/` failed with a
  planner HTTP 502 before any target requests. Its provider-response details
  were not retained, so the cause is unresolved. The final run selected GPT
  planning explicitly before startup; no runtime model fallback was added.
- The first usage/role regressions failed 13 cases before implementation.
  Missing/partial provider usage is now null rather than SDK-normalized zero.
  The final focused framework suite passed 39 tests; the full suite passed 98
  with the same four upstream warnings. Ruff's three formatting changes were
  applied before the final passing release checks.

The Gemini LangGraph evaluation finishes `completed_with_gaps` because the
planner also suggests the unimplemented catalog groundedness wrapper. Available
relevance/correctness assessments complete; the missing criterion is not a pass.
Both new models still reported token usage even without an explicit Gemini usage
request. This observed behavior does not guarantee coverage on other endpoints.
Claude's successful paid work was not repeated after the generic tracing fix;
normal-ID and verified-mini paths were revalidated through controlled real SDK
streams. General planner/judge provider coverage and shared-hosting gates remain
unchanged.

## Automated coverage

The suite covers constrained planning, deterministic evidence readiness, native MLflow scoring with a controlled model response, and actual Locust subprocess traffic over localhost. It covers observed concurrency, answer-text TTFT, UTF-8, timeout, truncation, cancellation/drain, authentication failure, worker SIGKILL, torn journals, frozen plans, idempotency, independent phase outcomes, history, authentication, and restart reads.

The old asyncio-only load tests were removed with the duplicate load implementation.
Counts are not directly comparable to the original 17-test snapshot. Ruff, OpenAPI
snapshot verification, and wheel/source-distribution builds are checked separately.

## Retained real LLM validation — October 2, 2026

`uv run python examples/locust_databricks_e2e.py` exercised REST API → real local Locust → Databricks streamed inference → MLflow post-run judging. Planner, target, and judge used `databricks-gpt-5-4-mini`.

Run at that checkpoint: `7323c770-bd26-4e50-81b3-06e7608521d2` (2026-10-02 UTC).

| Observation | Result |
| --- | --- |
| Configured / observed HTTP concurrency | 2 / 2 |
| Successful target requests | 4 / 4 |
| Incomplete measurements | 0 |
| Answer-text TTFT coverage | 4 / 4 |
| Output-token usage coverage | 100% |
| Planner selections | Relevance and correctness |
| Assessments | 4 per scorer, zero judge errors |
| Relevance / correctness mean | 1.0 / 1.0 on these answers |
| Load / evaluation status | completed / completed |

Observed successful TPS was 1.67, TTFT p50 about 517 ms, p95 about 922 ms. Four requests validate wiring, not capacity or stable latency statistics. The run window includes auth, ramp-up, journaling, and drain. Raw artifacts and the local MLflow database remain ignored.

A prior run (`e4187993-da9c-4a49-b24e-da35f0c822c5`) also passed 4/4. An earlier development run (`75be9a64-e23d-480c-b105-609996172b96`) had 3/4 successes and a connection/read-timeout failure; the three successful responses were judged. That failure remains recorded. Subsequent success does not establish its root cause.

A separate direct judge check used one correct and one deliberately incorrect response; correctness mean was 0.5. That confirms discrimination for the simple fixture, not general calibration.

The local mock example generates 20 requests at concurrency 3 without paid calls. Missing references or judge configuration are explicit evaluation gaps.
