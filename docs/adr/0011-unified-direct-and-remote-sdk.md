# ADR 0011: One request vocabulary, direct execution by default

- Date: October 8, 2026
- Status: Implemented locally; proposed for designated maintainer review; live journey validation partial
- Review owner: repository maintainer

## Context and assumptions

The local Python SDK, remote SDK and REST API currently express the same run with
different request/response shapes. Users should be able to run from a laptop or
notebook without starting an API server, then move execution to an optional API
host without rewriting cases or evaluation policy. Hosting must not dictate the
invocation protocol or require another client implementation.

Retain one active run per artifact owner, one Locust engine, 100 closed-loop users,
10,000 measured attempts, 1,000 cases and the eight-million-byte body bound.
Tutorials use small bounded runs, not capacity claims. At the existing illustrative
2 KB per journal event pair, 10,000 attempts consume roughly 20 MB before snapshots,
profiles and traces; actual payload size can be substantially greater. Every run
can add one excluded first-case inference probe. Explicit/automatic evaluation
adds one readiness assessment per selected judge plus bounded sampled judging;
automatic also calls the planner. These are assumptions, not new spend approval.

## Contract decisions, before implementation

1. `EvalSurge(artifact_dir=..., targets=..., settings=...)` is the direct synchronous
   context factory. `EvalSurge.local(...)` is its explicit equivalent; native async
   local execution remains available. Neither starts an HTTP server. Both reuse
   the existing coordinator and its dedicated loop/thread or caller-owned loop.
   An explicit artifact directory wins; omission honors supplied
   `Settings.artifact_dir`, or settings loaded once from operator file/environment.
   Without configuration the legacy `artifacts` default remains.
   Coordinator ownership and the private worker snapshot use the same directory.
2. `start(RunCreate)` uses the v2 vocabulary: `target.connection_id`, `cases` with
   `input`/`reference`, `load`, and `EvaluationPolicy`. JSON-compatible mappings are
   accepted through the same validation. The request contains no profile, host,
   App URL, token, scorer source, or tracking-store selector.
   Both modes share finite UTF-8 encoding and the same body bound without ASCII
   escaping. Raw mappings must already be JSON-compatible; validated typed models
   may use public Pydantic JSON serialization, retaining unset-field omission for
   legacy remote bodies. The encoded document also detaches nested caller values.
3. Direct callers are operators: `targets={"agent": Agent.http(...)}` or
   `targets={"agent": Agent.databricks_app(name, profile=...)}` binds that alias
   outside the request. App construction stores configuration without discovery
   or authentication; admission uses the existing target resolver. Its default
   is the current DurableAgentServer `/api/invocations` contract; legacy
   `mlflow-agent-server` `/responses` is an explicit protocol choice. Auth refresh,
   exact-origin validation and invocation decoding stay separate.
4. New direct run handles and `EvalSurge.remote(url, typed=True)` share typed
   `status() -> RunStatus`, `result() -> Result`, `report() -> Report`,
   `wait(timeout=None) -> Report`, and `cancel() -> Acknowledgment`. The remote
   adapter uses the existing HTTP client; it does not create a load engine.
   Shared presentation is FastAPI-independent. Public request/result models are
   exported from `evalsurge` without importing the optional execution stack.
5. Preserve `/v1`, legacy local keyword `start(agent=..., cases=..., ...)` and its
   `RunReport`, direct `RemoteClient` dictionary methods, and default
   `EvalSurge.remote(...)` dictionary behavior. `typed=True` is deliberate opt-in
   for existing remote callers. New tutorials always use the unified contract.
   Direct execution still requires the existing `server` extra; changing the
   execution default does not force the load stack on lightweight remote installs.
6. Preserve safe field-specific validation. Catch Pydantic validation errors
   separately from JSON-encoding errors and share a bounded sanitizer with REST,
   SDK and CLI. Never include submitted values, unknown input keys, raw validator
   context, private provider messages or credentials in error guidance.
7. Type evaluation outcomes, scorer/assessment variants, sampling coverage and
   existing evidence-gap codes without changing their wire meaning. False judge
   verdicts are valid assessments, not execution errors. `completed` and
   `completed_with_gaps` do not assert quality passing. Evaluation remains off by
   default; automatic planning is explicit, catalog/allowlist constrained and
   cannot invent references or executable judge code.
8. CLI summaries show available latency/TTFT percentiles, throughput, error rate,
   completeness, token coverage and per-judge coverage/pass rates. Missing values
   remain unavailable. `--json` explicitly opts into protected structured output.
   Configured-target discovery is static and secret-free, not App enumeration or
   inference. Local CLI execution uses operator settings outside the request.

## Data flow, ownership and failure modes

`direct Python/notebook -> operator binding -> RunCreate validation -> existing
target resolver -> coordinator admission/deferred frozen plan -> excluded
preflights -> one Locust subprocess -> protected journal/correlated traces ->
captured-answer judging -> shared typed report`.

`optional remote SDK/REST -> API authentication -> server-owned registered
binding -> same pipeline`.

Requests originate from the machine running the direct context (a notebook's
driver for notebook use), or from the API host for remote submission. Moving the
submission client does not move a remote run's load generator. Context exit stops
new dispatch, drains owned work and releases the exclusive artifact lock. Waiter
timeout does not cancel work; cancellation cannot roll back tools, stop already
dispatched requests immediately, or forcibly terminate trusted scorer code.

Private task-local operator snapshots must propagate into coordinator tasks and
workers without mutating process-global environment configuration. Copies freeze
target bindings and requests before scheduling. App auth still requires an exact
explicit profile and refreshable OAuth; a laptop profile is not automatically
installed or usable on a notebook driver. Missing deployment/authentication or
evidence fails closed with inspectable phase results, including planless failures.
Reports retain protected rationales and may quote workload/reference data.

Factories inherit the effective task-local scope, not just `os.environ`. An
implicit environment target registry is retained privately and validated when a
unified request selects it; legacy calls supply their own exact `Agent` and do not
validate that unused registry. Legacy calls without explicit context settings or
bindings preserve submission-time environment selection, including an experiment
created after context entry. Explicit context configuration and unified requests
remain frozen. Invalid registries fail before unified target discovery/admission;
this compatibility rule does not authorize any new destination or credential.

Local artifacts need private persistent POSIX storage with exclusive ownership.
Opening a separate browser-report server over those artifacts requires closing the
direct owner first; no hidden server or standalone HTML export is promised.
Crash recovery/idempotency, no target retries, no judging reinvocation and
independent load/profiling/evaluation outcomes remain unchanged.

Fresh serverless prerequisites establish driver runtime-OAuth, local subprocess,
socket and POSIX-storage availability, but independent worker OAuth failed. The
validation-only notebook harness therefore keeps native model clients in the
driver and exercises real framework HTTP through direct execution and a keyed
loopback API. It does not copy laptop tokens, extend App profile authentication,
deploy a shared API, or substitute a local server as App deployment evidence.
Driver artifacts are ephemeral, not durable run-retention support. Actual App
audience/worker credentials and classic notebook validation remain open gates.
The first mini-model serverless HTTP/API validation failed without a final receipt.
Its output included an experiment ID from another tracking store. Harness-owned
tracking scopes now clear and restore `MLFLOW_EXPERIMENT_ID`, which native MLflow
sets during experiment selection. A real local two-store regression covers this
configuration leak. Native Uvicorn lifespan startup failure separately reproduced
host exit code 3. Both validation harnesses now contain SystemExit inside their
owned server task, allowing normal failure receipts and cleanup. This is harness
ownership, not a new engine or live journey success; no remote rerun is claimed.

Validation cancellation must observe a real measured HTTP handler in flight,
not just `running` status before users spawn. A validation-only receipt observer
retains opaque run IDs/counters without request bodies or model delays. It does
not change load-engine timings, stop semantics, or capacity claims. Original
cancel-before-dispatch receipts remain explicitly qualified in `VALIDATION.md`.

## Trade-offs and deferred work

Additive wrappers and typed opt-in preserve compatibility but retain a clearly
labeled legacy surface. Direct execution is easier to start, not dependency-free
or shared-hosting ready. No new durable workers, capacity campaigns, tenant ACLs,
run thresholds or judge calibration are implied. Runner CPU/network, synchronous
journal fsync, repeated snapshot reads and duplicate App lookup remain potential
bottlenecks. Measure them before redesigning persistence or timing.

Excluded warmup, concurrency stages, comparisons, CI thresholds and native App
streaming are later work with explicit measurement semantics and their own design
review. Do not invent TTFT for the synchronous Runtime JSON contract. Shared
hosting remains gated by `docs/PRODUCTION_READINESS.md`.

## Verification and release gates

Static request/typed response/validation/serialization tests and import/build
checks establish contracts, not live inference. Real LangGraph and OpenAI Agents
journeys need separately recorded, bounded actual model calls: laptop-to-HTTP,
laptop-to-deployed-App, classic-notebook-to-App, and optional REST-to-registered
targets. Verify auth, fail-fast, cancellation, report retrieval and cleanup.
Serverless notebook validation is separate and must not inherit classic results.

Use an explicitly user-selected profile and authorized target/compute. Missing
resources/permissions/traffic bounds are validation gaps, never permission to use
fixture completions. Disclose and obtain approval before running existing tests
or CI containing stubbed inference. Record exact commands/results and remaining
gaps in `VALIDATION.md`. The ADR and public API additions need designated maintainer
review; local checks do not provide that review or prove remote CI passed.
