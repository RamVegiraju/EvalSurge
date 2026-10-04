# Code guide

EvalSurge has one production load engine and one post-load evaluation path. Function
docstrings describe arguments, results, side effects, and important failure behavior;
this guide explains how those functions fit together.

## Request-to-report flow

1. `api.create_app()` creates per-process state and installs authentication, error
   handling, response metadata, and the local-storage lifespan.
2. `submit()` validates a target through `connections.resolve_connection()` and each
   workload envelope through `runner.payload()`. It checks idempotency and admission,
   then creates or reuses a persisted plan before scheduling background work.
3. `planner.create_plan()` uses explicit scorer IDs or a constrained planner call.
   `validate_plan()` independently determines evidence readiness and freezes data
   hashes, installed rubric sources, judge configuration, and sampling settings.
4. `execute()` calls `locust_runner.run_load()`, which persists configuration and starts
   a separate Locust process. The API process never imports `locustfile.py`.
5. Each `AgentUser.invoke()` journals its start, resolves authentication, sends one
   streaming request, and records completion. `streaming.consume()` interprets the
   answer events; `runner.summarize()` aggregates client measurements.
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
| `api.py` | `authorize()` enforces inbound service access; `plan_or_error()` translates recognized planner failures; factory-local handlers own admission, phase transitions, persistence, reads, and cancellation. |
| `models.py` | Request and response contracts reject unknown model fields and bound load and assessment counts. Nested workload metadata remains flexible. |
| `connections.py` | `resolve_connection()` validates exact operator-owned destinations; `authentication()` returns a refreshable header source. Connection records contain credential references, not copied secrets. |
| `providers.py` | `workspace_client()` requires explicit workspace configuration; `planner_client()` and `judge_client()` create caller-owned clients; `judge_endpoint()` resolves the server endpoint name. |
| `planner.py` | `fingerprint()` binds canonical JSON; `has_reference()` checks candidate evidence; `validate_plan()` freezes deterministic readiness; `create_plan()` optionally performs paid planning. |
| `locust_runner.py` | `run_load()` owns subprocess creation, cancellation markers, the outer deadline, and result recovery. |
| `locustfile.py` | `start()` starts the measured window; `finish()` writes the aggregate snapshot; `AgentUser.invoke()` owns sequential request lifecycle and active counters. |
| `streaming.py` | `consume()` mutates one measurement row from a supported single-line SSE data event. It does not open connections or measure its own clock. |
| `runner.py` | `payload()` builds adapter envelopes; `percentile()` computes nearest-rank statistics; `summarize()` reports descriptive performance, not capacity or a quality verdict. |
| `storage.py` | `atomic_json()` replaces snapshots; `append_event()` flushes journal progress; `recover_rows()` reconstructs latest per-attempt state without resuming work. |
| `sampling.py` | `select_rows()` balances shuffled case/time strata using the frozen seed and assessment budget; it preserves input rows. |
| `judges.py` | `rubric_hash()` detects prompt-source drift; `build_prompt()` renders installed rubrics; `direct_scorer()` requires a plan and returns a native MLflow scorer. |
| `evaluator.py` | `evaluate()` uses captured outputs and the plan as the sole evaluation configuration, retaining assessment IDs, coverage, and MLflow result references. |
| `scorer_registry.py` | `catalog()` validates trusted references; `freeze()` binds exact versions and `definition_hash()` canonicalizes public serialization; `trace_source()` freezes operator scope. |
| `profiling.py` | `normalize_trace()` checks complete tree timing/ancestry; `union_duration()` avoids nested overlap; `collect_profiles()` validates correlation and persists profiles; `summarize_profiles()` reports coverage/hotspots. |
| `middleware.py` | `BodyLimitMiddleware` counts ASGI body chunks before parsing accepts excess data. |
| `static/` | Report UI uses text-only DOM updates, same-origin authenticated fetches, and bounded report pages; no keys enter URLs or persistent browser storage. |
| `static/report.js` | `drawSuggestions()` displays frozen rationale/readiness; `drawJudges()` preserves per-scorer assessment/selection/error counts; `focusedSpans()` reduces enclosing-span clutter without modifying evidence; `load()` owns in-memory authentication and serialized pagination. |
| `docs_ui/` | Public Swagger shell and external initializer use pinned local vendor assets. `api.legacy_docs()` redirects `/redoc` without inheriting API-operation authorization. |
| `openapi.py` | `install_schema()` installs a cached renderer that adds common header documentation and request examples. |
| `scripts/export_openapi.py` | `main()` exports the public schema or verifies the committed snapshot with `--check`. |

## Contracts worth preserving

- `evaluation.scorers=None` invokes planning; an explicit list bypasses it; `[]`
  disables catalog judging. Registered aliases are independently selectable.
- Plan reuse binds evaluation input exactly. Target and load settings can change,
  but the scorer selection, references, seed, and budget cannot silently drift.
- Planner clients injected for tests remain caller-owned. Clients created by planning
  are closed there; each judge client is closed after its assessment.
- Cancellation stops new load dispatch and drains active requests. It does not cancel
  evaluation or promise immediate termination.
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

- `examples/mock_agent.py` serves deterministic local SSE without model credentials.
- `examples/smoke_test.py` exercises the actual REST and Locust path with that mock
  target. It can still use a paid judge when judge credentials are configured.
- `examples/databricks_validation.py` checks direct planning, inference, and judge
  discrimination with an intentionally incorrect answer; it is not a load test.
- `examples/locust_databricks_e2e.py` checks the full bounded hosted integration.
  Both Databricks examples require an explicitly configured workspace and are opt-in.
- `examples/framework_agent.py` owns real compiled LangGraph and OpenAI Agent streaming,
  traced memory, synthetic tools/retrieval, provider clients, and their lifecycles.
  `demo_chat_options()` scopes verified model settings to the provider/model pair;
  explicit overrides are demo-only. `demo_request_usage()` validates usage opt-out;
  `TracedChatModel.stream_response()` wraps the public SDK hook in one MLflow span
  without reconstructing provider IDs. `runner.payload()` never applies those presets.
- `examples/framework_e2e.py` validates both frameworks through actual REST, Locust,
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
