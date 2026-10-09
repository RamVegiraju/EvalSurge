# Validation tools

These are advanced checkout tools and integration harnesses, not minimal API
tutorials. Start with the [Python examples](../../examples/README.md) for ordinary
benchmarks. Run these modules from the repository root.

| Tool | Purpose |
| --- | --- |
| [python_benchmark.py](python_benchmark.py) | Configurable local Python CLI; saves reports on success and preflight failure. |
| [python_requests_benchmark.py](python_requests_benchmark.py) | Remote REST client with idempotency, bounded polling, safe errors, and a report URL. |
| [framework_e2e.py](framework_e2e.py) | Actual LangGraph/OpenAI Agents, REST, Locust, MLflow, evaluation, and report integration. |
| [databricks_validation.py](databricks_validation.py) | Opt-in paid planning, inference, and positive/negative judging check. |
| [locust_databricks_e2e.py](locust_databricks_e2e.py) | Opt-in paid REST/Locust test against an authorized Databricks model. |
| [databricks_app_smoke.py](databricks_app_smoke.py) | Dry-run-by-default, consent-gated check of an existing authorized App; one probe plus at most 500 measured calls, up to five users/180 seconds, no judging. |
| [databricks_app_quality.py](databricks_app_quality.py) | Separate consent-gated native App quality integration; one synthetic policy/reference, up to two captured responses per relevance/correctness scorer, local native MLflow evidence. |
| [unified_sdk_journeys.py](unified_sdk_journeys.py) | Consent-gated direct SDK checks against a real local framework/model or an existing authorized App. |
| [local_runner_http_target_journeys.py](local_runner_http_target_journeys.py) | Local runner → real HTTP agent: current five-attempt public request, direct/optional API, intentional pre-provider fail-fast, active cancellation and typed report parity. |
| [serverless_prerequisites.py](serverless_prerequisites.py) | Importable source notebook: zero-inference driver/worker OAuth, socket, process and POSIX-storage checks; requires an explicit workspace widget. |
| [serverless_runner_app_target.py](serverless_runner_app_target.py) | Prepared/authentication-blocked readiness harness for the serverless runner → deployed App; one probe plus one measured invocation only after auth/deployment/traffic review. Not a live validation pass. |
| [serverless runner-only notebook](../../examples/journeys/serverless_runner_databricks_app_target.py) | Source notebook for that harness; paid traffic off by default, generator only, no agent-hosting substitute. |
| [serverless_sdk_journeys.py](serverless_sdk_journeys.py) | Retained notebook-local HTTP helper diagnostic; not the intended serverless-runner → App sample or an additional hosting option. |
| [serverless_helper_notebook.py](serverless_helper_notebook.py) | Historical notebook-hosted helper launcher; diagnostic only, not deployed-App coverage. |

For configurable local load against an already running authorized agent:

```bash
uv run --no-sync python -m scripts.validation.python_benchmark \
  --url http://127.0.0.1:9001/chat --duration 180 --concurrency 5
```

The REST client still requires an existing API server. See
[Requests usage](../../docs/USAGE.md#python-requests-client) for its command and
failure semantics. [Live integration guidance](../../docs/USAGE.md#bounded-live-validation)
explains explicit profile selection and traffic budgets. Live tools can execute
agent actions and incur model/judge costs; do not run them without authorization.
The two older Databricks model-serving helpers require manual consent and an
operator-selected environment profile; they do not have the App helpers' dry-run/
consent flags. Their nominal target counts do not cap planner, judge-readiness,
criteria selection, retries, or dollar spend. Review those separately frozen budgets.
For current DurableAgentServer `/api/invocations` versus legacy MLflow `/responses`,
required resources, and the App smoke budget, see
[Databricks App validation](../../docs/DATABRICKS_APP_VALIDATION.md).

The October 7 live App work passed an intentional fail-fast check, 500 measured
requests at concurrency five, and a separate tiny explicit quality check. Its
earlier real-model preflight failure is retained in [VALIDATION.md](../../VALIDATION.md).
These helpers invoke an existing App through the local facade; they do not
deploy EvalSurge or establish live `/v2` HTTP or sustainable-capacity evidence.

The previous `examples.*` CLI and integration-runner module paths have moved to
`scripts.validation.*`. `examples.python_benchmark` is a retained controlled
mock tutorial without command-line flags, not the primary real-agent journey.
The obsolete smoke script and its `run.json` were
removed: their missing correctness reference conflicts with fail-fast readiness.
Actual REST/Locust regression coverage and the framework harness remain.

## Serverless notebook validation

**Prepared, authentication-blocked—not live-validated.** The
[runner-only notebook](../../examples/journeys/serverless_runner_databricks_app_target.py)
and [App-target harness](serverless_runner_app_target.py) now exist. Keep the
paid-traffic widget false for review/dry-run planning. No model-bearing Job is
authorized by preparing the sample or obtaining a successful prerequisite task.

In the intended user journey, **only the load generator** runs on serverless
compute. The real agent stays in its deployed Databricks App. Authentication,
egress and subprocess prerequisites must pass before model-bearing load; do not
substitute a notebook-hosted agent for a failed App/authentication gate.

Use a dedicated, explicitly authorized serverless notebook/task. Install the built
current `evalsurge[server]` wheel and reviewed frozen execution requirements;
agent-framework dependencies are not needed in this runner-only notebook. The wheel does not
package `examples` or `scripts`: upload those selected source packages to a private
Workspace directory and add that directory to the notebook import path. Select a
supported environment version through the Jobs environment spec; disable task
retries and serverless auto-optimization, set a finite task timeout and keep the
explicit CLI profile on every launch/read. These are test resources, not a shared
EvalSurge deployment. Never upload a laptop token or OAuth-cache/profile file.

First run the prerequisites notebook with the approved workspace origin in its
`workspace` widget. Examine individual booleans, not just Jobs `SUCCESS`. The fresh
check found driver runtime-OAuth available but independent-worker OAuth unavailable.
That is a notebook-to-App authentication gap. The current public App binding is
also profile-only and rejects ambient destination/identity overrides before SDK
discovery; a laptop profile name is not a native notebook auth configuration.
Do not strip auth-routing overrides, copy notebook tokens/cache/profile files,
add a new principal, introduce a forwarding proxy or fall back to classic to
hide these blockers. A supported operator-auth change needs ADR/maintainer review.

Before any model-bearing submission, all of the following must be reviewed:

1. Exact user-selected workspace and supported operator-owned driver/profile
   identity, without bypassing ambient-override controls.
2. The independent Locust subprocess can acquire and refresh App OAuth itself;
   native driver-only success is insufficient.
3. One explicitly selected deployed App is ready, has the reviewed current source,
   and is a no-tool agent enforcing at most 512 output tokens per model response.
4. Current wheel/source and frozen requirements, environment version 5, zero Job
   retries, finite timeout, and an explicit initial traffic lease: **one excluded
   probe plus one measured App invocation**, concurrency one, evaluation off.

The harness returns fixed safe blockers before inference if profile/worker
readiness fails. The sample creates no deployment or model and exports no auth
messages, tokens or raw child output. Model/tool turns and dollars are not capped
by a generic App-invocation count; verify deployed behavior separately. A completed
run is not a quality verdict or capacity claim. Status/result/report agreement and
runner context cleanup belong in the final receipt; Apps/Lakebase are not deleted
by closing the runner. Optional notebook API execution, intentional fail-fast and
active cancellation remain separate, unvalidated gates.

The selected environment-5 prerequisite receipt records driver OAuth, loopback
and POSIX lock/fsync success but worker OAuth failure, with zero inference calls.
The runner-only sample has no fresh live notebook-to-App receipt. Keep the retained
historical helper failure separate; its local storage/lifespan regressions do not
establish successful deployed-App hosting. See
[the hosted-journey record](../../docs/HOSTED_JOURNEY_VALIDATION.md) and
[VALIDATION.md](../../VALIDATION.md) for actual resources and pass/failure evidence.

### Retained notebook-local helper diagnostic (not the advertised App journey)

This is retained for investigation/history, not the primary end-user sample:

```python
from scripts.validation.serverless_sdk_journeys import (
    budget_record,
    execute,
    parse_options,
    prerequisite_probe,
)

options = parse_options(
    [
        "--workspace",
        "https://YOUR_APPROVED_WORKSPACE.cloud.databricks.com",
        "--target-model",
        "YOUR_VERIFIED_COMPATIBLE_ENDPOINT",
        "--framework",
        "langgraph",  # or openai-agents
        "--model-api",
        "mlflow-responses",  # Explicit advertised route; never automatic fallback.
        "--artifact-dir",
        "/tmp/NEW_EMPTY_PRIVATE_DIRECTORY",
        "--exercise-cancel",
    ]
)
print(budget_record(options))  # Dry bounds only; no inference or discovery.

# Only after explicit paid-traffic authorization:
# options.live = options.accept_paid_traffic = True
# prerequisites = await prerequisite_probe(options.workspace)
# receipt = await execute(options)
```

The native framework and real model stay in the driver process, using its selected
runtime-OAuth credentials; the sole Locust worker calls only the exact local agent
route. A private API key is generated in memory for loopback REST; it is not a
request field, job parameter or persisted configuration. Defaults permit at most
26 top-level attempts per framework across direct/API normal and cancellation
runs, including four model-bearing probes and two intentional unknown-route probes
with no model dispatch. Evaluation is off. Model/tool calls and dollars are not
hard quotas; stop after any failed normal journey. Receipts omit prompts, answers,
keys and tokens. Raw artifacts are protected, ephemeral driver storage and are not
a durable report-retention guarantee.

Active-dispatch cancellation needs an observed measured HTTP request, not merely
`running` lifecycle status. It stops further dispatch and drains attempts; it cannot
undo tool actions. Actual source/hosting/model results and gaps belong in
[VALIDATION.md](../../VALIDATION.md), separate from static or controlled tests.

The October 8 serverless live job failed without a final receipt; it does not
establish inference success, request counts, cancellation or cleanup. A native
MLflow storage regression reproduced an experiment-ID environment leak between
fresh tracking stores. The harness now scopes and restores that ID as well as its
tracking URI. Native Uvicorn startup failure separately reproduced host exit code
3; both harnesses now contain its SystemExit within the server task. These fixes
have not been rerun live and do not establish a definitive remote root cause.
