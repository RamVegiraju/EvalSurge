# Code guide

EvalSurge has one production load engine and one post-load evaluation path. Function
docstrings describe arguments, results, side effects, and important failure behavior;
this guide explains how those functions fit together.

`v2.py` validates registered-target requests, translates through `v2_models.py`,
and admits a deferred-plan run in the same coordinator. `configuration.py` carries
private operator snapshots through request/task/thread scopes and worker environments
without global mutation. `settings.py` and `diagnostics.py` perform bounded static
inspection. `target_resolver.py` separates App identity/OAuth resolution from
`adapters.py` invocation semantics. `evalsurge/remote.py` and `cli.py` own HTTP
polling and command output; they do not create another load engine.
Both local HTTP agents and registered Databricks Apps are implemented targets;
[the target guide](TARGETS.md) maps their public/operator boundaries. A Runtime
session identifier is ordering state, not proof of transcript or long-term memory.
`evalsurge/facade.py` exposes remote access without server dependencies and defers
local execution imports until explicitly requested. Package-level `Agent`,
`Connection`, and `RunFailed` remain compatible lazy exports requiring the server
extra; the public Pydantic models and HTTP client need only the base installation.

`evalsurge/local.py` adds the v2 request vocabulary to direct execution. Its
operator snapshot binds opaque request aliases to `Agent.http()` or lazy
`Agent.databricks_app()` registrations. `EvalSurge(...)` and `.local()` use this
context; `.local_async()` uses the native-async equivalent. Legacy keyword calls
retain legacy reports. `.remote(..., typed=True)` wraps the existing transport
with the same v2 models; default remote dictionary calls remain available.
The factory inherits effective task-local configuration. Implicit target-registry
validation is deferred until unified admission; legacy exact-Agent submissions
retain submission-time configuration without validating that unused registry.
`run_views.py` shares pure presentation with REST. `validation.py` shares bounded
field-specific diagnostics without importing FastAPI. See [ADR 0011](adr/0011-unified-direct-and-remote-sdk.md).

## Request-to-report flow

1. `api.create_app()` installs HTTP authentication/error handling/metadata over
   `RunCoordinator`; `evalsurge.EvalSurge` provides local sync/async ownership without
   a web server. Both acquire the same exclusive local-storage lock.
2. `RunCoordinator.submit()` validates a target through `connections.resolve_connection()` and each
   workload envelope through `runner.payload()`. It checks idempotency and admission,
   then creates or reuses a persisted plan before scheduling background work for
   v1/local runs. V2 admission persists first; the owned task performs planning
   asynchronously, before preflights and measured load.
3. `planner.create_plan()` uses explicit scorer IDs or a constrained planner call.
   `validate_plan()` independently determines evidence readiness and freezes data
   hashes, installed rubric sources, judge configuration, and sampling settings.
4. `RunCoordinator._execute()` validates frozen evaluation setup before invoking the
   target, calls `locust_runner.run_preflight()` once, and reuses its answer in
   `run_evaluation_preflight()` before `run_load()`. Only completed readiness
   assessments permit load; performance-only skips judging. Workers share one
   Locust path; probes/readiness are excluded from measured/quality/report rows.
   The API process never imports `locustfile.py`.
5. Each `AgentUser.invoke()` journals its start, resolves authentication, sends one
   HTTP request, and records completion. Shared adapters interpret SSE or the bounded
   JSON contract; `runner.summarize()` aggregates client measurements.
6. `profiling.collect_profiles()` validates exact trace correlation and scope after
   load, persists bounded content-free profiles, and retains actual Trace objects
   transiently for native trace-aware judging.
7. Completed load calls synchronous `evaluator.evaluate(rows, plan, traces)` in a thread.
   `sampling.select_rows()` chooses evidence-qualified captured answers;
   `judges.direct_scorer()` uses the frozen plan for direct Databricks calls wrapped
   as MLflow assessments. The target is not reinvoked.
8. The API snapshots independent phase statuses and exposes the report and paginated
   request records. Missing evidence or judge failures are not passing assessments.

## Function ownership

| Module | Functions and responsibilities |
| --- | --- |
| `api.py` | `authorize()` enforces inbound service access; HTTP handlers delegate to the coordinator and translate domain errors to the existing envelope. |
| `coordinator.py` | `RunCoordinator.open()/close()` own storage and drain; `submit()` freezes and schedules; `_execute()` advances phases; reads, reports, wait, and cancellation share one lifecycle. |
| `evalsurge/` | `Agent.http()` separates protocol and connection; `EvalSurge.local()/local_async()` expose run handles without starting a server or nesting event loops. |
| `evalsurge/facade.py` | `EvalSurge.remote()` stays dependency-light; local factories and lazy exports verify the explicit server extra before loading the existing local implementation. |
| `evalsurge/local.py` | Direct v2 admission, operator snapshot ownership and typed handles over the existing local runtime; legacy overloads remain. |
| `evalsurge/serving.py` | Optional agent-side `create_app()` calls the customer async handler, preserves bounded JSON inputs, validates completed answers and propagates explicit correlation/state keys; no framework loading in the runner or automatic auth/tracing. |
| `run_views.py` | Shared status/result/report projections, including planless terminal failures; no target or judge execution. |
| `validation.py` | `validate_request()` detaches schema inputs and emits safe bounded `RequestValidationError`; no raw submitted values. |
| `v2_models.py` | Canonical request plus typed result/evaluation/coverage/evidence-gap variants; completion and quality remain independent. |
| `adapters.py` | Supported response decoders bound input and validate completion/answer/usage/trace IDs; JSON never fabricates TTFT. |
| `models.py` | Request and response contracts reject unknown model fields and bound load and assessment counts. Nested workload metadata remains flexible. |
| `connections.py` | `resolve_connection()` validates exact operator-owned destinations; `authentication()` returns a refreshable header source. Connection records contain credential references, not copied secrets. |
| `providers.py` | `workspace_client()` requires explicit workspace configuration; `planner_client()` and `judge_client()` create caller-owned clients; `judge_endpoint()` resolves the server endpoint name. |
| `planner.py` | `fingerprint()` binds canonical JSON; `has_reference()` checks candidate evidence; `validate_plan()` freezes deterministic readiness; `create_plan()` optionally performs paid planning. |
| `locust_runner.py` | `run_preflight()` reuses `run_load()` for one first-case invocation; `preflight_result()` reduces evidence to safe diagnostics. `run_load()` owns subprocess creation, cancellation markers, outer deadline, and recovery. |
| `locustfile.py` | `start()` starts the measured window; `finish()` writes the aggregate snapshot; `AgentUser.invoke()` owns sequential request lifecycle and active counters. |
| `streaming.py` | `consume()` mutates one measurement row from a supported single-line SSE data event. It does not open connections or measure its own clock. |
| `runner.py` | `payload()` builds adapter envelopes; `percentile()` computes nearest-rank statistics; `summarize()` reports descriptive performance, not capacity or a quality verdict. |
| `storage.py` | `atomic_json()` replaces snapshots; `append_event()` flushes journal progress; `recover_rows()` reconstructs latest per-attempt state without resuming work. |
| `sampling.py` | `select_rows()` balances shuffled case/time strata using the frozen seed and assessment budget; it preserves input rows. |
| `judges.py` | `rubric_hash()` detects prompt-source drift; `build_prompt()` renders installed rubrics; `direct_scorer()` requires a plan and returns a native MLflow scorer. |
| `evaluator.py` | `evaluate()` uses captured outputs and the plan as the sole evaluation configuration, retaining assessment IDs, coverage, and MLflow result references. |
| `evaluation_preflight.py` | `configuration_error()` validates frozen criteria/evidence before agent traffic; `run_evaluation_preflight()` checks one native assessment per criterion without reinvoking the target. |
| `evaluation_errors.py` | `evaluation_error()` maps exception type/status to fixed safe guidance, never provider messages or bodies. |
| `evaluation_details.py` | `assessment_details()` joins native result rows by exact request tags, bounds protected judge rationales, separates boolean quality failures from execution errors, and rejects ambiguous correlation. |
| `scorer_registry.py` | `catalog()` validates trusted references; `freeze()` binds exact versions and `definition_hash()` canonicalizes public serialization; `trace_source()` freezes operator scope. |
| `report_links.py` | `experiment_links()` builds bounded browser-only experiment links from frozen tracking stores and recorded IDs; operator UI overrides require exact store matching and no network or credential resolution. |
| `profiling.py` | `normalize_trace()` checks complete tree timing/ancestry; `union_duration()` avoids nested overlap; `collect_profiles()` validates correlation and persists profiles; `summarize_profiles()` reports coverage/hotspots. |
| `middleware.py` | `BodyLimitMiddleware` counts ASGI body chunks before parsing accepts excess data. |
| `static/` | Report UI uses text-only DOM updates, same-origin authenticated fetches, and bounded report pages; no keys enter URLs or persistent browser storage. |
| `static/report.js` | `drawSuggestions()` displays frozen rationale/readiness; `drawJudges()` preserves per-scorer assessment/selection/error counts; `focusedSpans()` reduces enclosing-span clutter without modifying evidence; `load()` owns in-memory authentication and serialized pagination. |
| `docs_ui/` | Public Swagger shell and external initializer use pinned local vendor assets. `api.legacy_docs()` redirects `/redoc` without inheriting API-operation authorization. |
| `openapi.py` | `install_schema()` installs a cached renderer that adds common header documentation and request examples. |
| `scripts/export_openapi.py` | `main()` exports the public schema or verifies the committed snapshot with `--check`. |
| `scripts/verify_remote_install.py` | Builds an isolated base-only dependency environment, installs the actual wheel, checks absent server distributions, and exercises remote SDK/CLI behavior plus missing-extra guidance without target traffic. |
| `scripts/verify_wheel.py` | Checks required wheel/source assets, including unified SDK modules, and rejects local assistant metadata in the sdist by member name; never extracts or executes archive contents. |

## Contracts worth preserving

- Legacy v1/local `evaluation.scorers=None` invokes planning; an explicit list
  bypasses it; `[]` disables catalog judging. V2 instead defaults to
  `evaluation.mode="off"`; automatic planning requires explicit opt-in.
  Registered aliases are independently selectable.
- Plan reuse binds evaluation input exactly. Target and load settings can change,
  but the scorer selection, references, seed, and budget cannot silently drift.
- Planner clients injected for tests remain caller-owned. Clients created by planning
  are closed there; each judge client is closed after its assessment.
- Cancellation stops new load dispatch and drains active requests. It does not cancel
  evaluation or promise immediate termination.
- Preflight uses identical target settings and one extra first-case invocation; it
  can execute tools/change agent state. Failure skips load; selected judges reuse
  its captured answer for excluded readiness only. Historical checks default to
  `not_run`; no target retries or model fallbacks are introduced.
- Catalog provider errors return native errored Feedback without a value, avoiding
  MLflow's hidden rate-limit retry layer. Readiness uses zero SDK retries; quality
  uses the frozen SDK cap. Only explicitly trace-required registered scorers
  receive a homogeneous native Trace column, never missing traces converted to NaN.
- Required probe trace collection is handled by `RunCoordinator._probe_readiness()`.
  Store/artifact exceptions become fixed `evaluation_trace_collection_failed`
  readiness errors; missing correlation remains `evaluation_missing_trace`.
  Both prevent judging/load and retain the failure independently of the passed
  inference probe. Ordinary answer judging does not perform probe trace reads.
- V2 `Result.evidence` projects configured and observed capabilities from existing
  phase outcomes, frozen plans and supplied coverage, without extra evidence reads.
  Probe success is not measured coverage, nor does observed judging imply a pass.
- TTFT and request latency begin after authentication, just before HTTP dispatch.
  The run window also includes ramp-up, authentication, journaling, and drain.
- Failed attempts affect error rates. Successful-only percentiles and partial
  provider token usage must be interpreted with their coverage counts.
- Journal rows are returned in attempt-start order, which includes attempts that fail
  before HTTP dispatch.
- Restart recovery marks abandoned phases interrupted and idempotency replay agrees
  with GET. It never retries target actions or automatically resumes jobs.
- History uses compact metadata and finished run state is evicted from memory.
  Request pagination still reconstructs journals; storage/index/retention scaling
  remains a deployment gate.

## Examples and retained history

- `examples/journeys/local_runner_http_target.py` and
  `local_runner_databricks_app_target.py` distinguish the load-generator machine
  from the separately hosted HTTP/App agent, sharing a five-attempt v2 workload.
  The classic notebook context is retained but deferred; notebook compute is a
  runner location, not agent hosting. Samples alone are not live evidence.
- [The serverless runner-only notebook](../examples/journeys/serverless_runner_databricks_app_target.py)
  and [its readiness harness](../scripts/validation/serverless_runner_app_target.py)
  are **prepared, authentication-blocked—not live-validated**. The notebook runs
  EvalSurge/Locust only and targets an already deployed App. The unchanged public
  binding is profile-only, rejects ambient identity/destination overrides, and
  requires independently refreshable worker OAuth. Native driver OAuth is not
  worker evidence. Gates cover exact driver/profile identity, worker auth and
  deployed readiness before separately approved traffic. Initial load is one
  excluded probe plus one measured invocation, concurrency one, evaluation off;
  the reviewed no-tool deployment must enforce <=512 output tokens. This does
  not establish notebook API execution, cancellation, fail-fast or capacity.
- `scripts/validation/serverless_sdk_journeys.py` and
  `serverless_helper_notebook.py` are retained historical notebook-hosted helper
  diagnostics. They are neither the advertised runner→App sample nor another
  agent-hosting option. `serverless_prerequisites.py` checks native driver and
  independent subprocess authentication without inference; inspect individual
  receipt checks rather than treating a Jobs `SUCCESS` as a passed journey.
- `examples/quality/` shows client-loaded datasets, explicit catalog/registered
  judges, automatic planning priorities, and deliberately rejected/not-ready
  edge cases. No uploaded scorer code or dataset-path request field is added.
- `scripts/validation/unified_sdk_journeys.py` is dry-run by default. Live HTTP
  mode reuses the actual framework demo with `live=True`; App mode requires an
  existing deployed agent. It verifies typed retrieval, the HTTP pre-provider
  fail-fast boundary, optional active-dispatch cancellation and context cleanup.
  No fixture fallback exists. Notebook and optional REST validation are separate.
- `scripts/validation/hosted_journeys.py` adds a no-network plan and explicit
  live-consent gate for already-running generic HTTP, existing native App and
  typed remote registered targets. Framework/model/source labels are operator
  attestations, not automatic deployed-source verification. It retains failed
  receipts, uses no model fallback and makes no deployment or notebook changes.
  The bounded matrix and unresolved source/auth gaps are documented in
  [the hosted-journey review](HOSTED_JOURNEY_VALIDATION.md).

- `examples/mock_agent.py` serves deterministic local SSE without model credentials.
- `examples/python_benchmark.py` is a minimal public Python request: five concurrent
  users, a three-minute bounded performance-only run, and printed report JSON
  against the credential-free mock agent.
- `examples/langgraph_benchmark.py` and `examples/openai_agents_benchmark.py` use
  the public facade against the corresponding `examples/framework_agent.py`
  endpoints. Both combine load, authoritative references, and explicit
  relevance/correctness evaluation. Provider/tracking setup remains operator-owned
  and opt-in; local integration tests control provider boundaries rather than
  establishing paid/live validation.
- `examples/requests/` contains four performance-only v2 requests for LangGraph
  and OpenAI Agents, each runner-local or hosted on Databricks Apps, plus a
  placeholder-only operator configuration. The [framework target examples](FRAMEWORK_TARGET_EXAMPLES.md)
  guide shows REST, CLI, and remote SDK submission. Static schema/encoder tests
  keep the guide and files aligned; real framework/Locust integration tests use
  reduced copies, not the published 500-request budgets. App-boundary tests use
  controlled SDK/OAuth and a local invocation envelope, not a deployed App or
  native DurableAgentServer/Runtime Store. Separate full-budget local and actual
  native App tests are recorded in [validation](../VALIDATION.md); their model,
  tracing, memory and quality boundaries are not interchangeable.
- `scripts/validation/python_benchmark.py` retains the advanced CLI and saves a
  report even on preflight failure; it is not the beginner tutorial.
- `scripts/validation/python_requests_benchmark.py` submits one REST request with Requests,
  polls independent phase outcomes, and prints the report URL without replaying
  uncertain submissions or cancelling on client timeout.
- The obsolete `smoke_test.py` and its request fixture were removed after checking
  callers: their missing correctness reference conflicts with fail-fast readiness.
  Actual REST/Locust tests and the framework harness retain integration coverage.
- `scripts/validation/databricks_validation.py` checks direct planning, inference, and judge
  discrimination with an intentionally incorrect answer; it is not a load test.
- `scripts/validation/locust_databricks_e2e.py` checks the full bounded hosted integration.
  Both Databricks examples require an explicitly configured workspace and are opt-in.
- `scripts/validation/databricks_app_smoke.py` is dry-run by default and resolves one
  explicitly selected App/profile only with live/paid consent. Its performance-only
  run retains failures and distinguishes the excluded probe from measured attempts.
- `scripts/validation/databricks_app_quality.py` separately gates two measured
  captures with authoritative refund facts, explicit relevance/correctness, a frozen
  mini judge, and native local MLflow. Use it as a CLI process: the backend's tracking
  selector is process-global even though operator configuration is task-local.
- `examples/framework_agent.py` owns real compiled LangGraph and OpenAI Agent streaming,
  traced memory, synthetic tools/retrieval, provider clients, and their lifecycles.
  `demo_chat_options()` scopes verified model settings to the provider/model pair;
  explicit overrides are demo-only. `demo_request_usage()` validates usage opt-out;
  `TracedChatModel.stream_response()` wraps the public SDK hook in one MLflow span
  without reconstructing provider IDs. `runner.payload()` never applies those presets.
- `scripts/validation/framework_e2e.py` validates both frameworks through actual REST, Locust,
  MLflow, judging, and report retrieval; `--live` and explicit profile opt in to paid calls.
  `configure_live_models()` selects independent target/planner/judge roles before
  startup, with no runtime fallback or capability-probing calls.
- `scripts/scan_agent.py` parses owner-selected Python with AST, never imports/executes
  agent source, and prints a conservative draft manifest for review.
- `docs/review/openapi-0.1.json` and its reports are intentional migration evidence,
  not executable legacy code. Keep them while the 0.1 migration notes refer to them.
- The `benchmark_agents` import namespace remains active and is not a second package
  implementation. Historical test filenames do not imply a second load engine.

The cleanup removes the unused `Evaluation` argument from `evaluate()` and the
unfrozen fallback from `direct_scorer()`. Internal Python callers must supply the
frozen plan. Profiling/report and optional manifest/registered-scorer contracts are
additions; old plans may need recreation because format 3 binds these new defaults.
