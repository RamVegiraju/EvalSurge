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
| [serverless_prerequisites.py](serverless_prerequisites.py) | Importable source notebook: zero-inference driver/worker OAuth, socket, process and POSIX-storage checks; requires an explicit workspace widget. |
| [serverless_sdk_journeys.py](serverless_sdk_journeys.py) | Real model/framework HTTP checks on a notebook driver, using direct execution and an authenticated loopback API; not a deployed-App stand-in. |

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
`scripts.validation.*`. `examples.python_benchmark` is now the minimal tutorial,
without command-line flags. The obsolete smoke script and its `run.json` were
removed: their missing correctness reference conflicts with fail-fast readiness.
Actual REST/Locust regression coverage and the framework harness remain.

## Serverless notebook validation

Use a dedicated, explicitly authorized serverless notebook/task. Install the built
`evalsurge[agents]` wheel with the reviewed frozen requirements. The wheel does not
package `examples` or `scripts`: upload those selected source packages to a private
Workspace directory and add that directory to the notebook import path. Select a
supported environment version through the Jobs environment spec; disable task
retries and serverless auto-optimization, set a finite task timeout and keep the
explicit CLI profile on every launch/read. These are test resources, not a shared
EvalSurge deployment. Never upload a laptop token or OAuth-cache/profile file.

First run the prerequisites notebook with the approved workspace origin in its
`workspace` widget. Examine individual booleans, not just Jobs `SUCCESS`. The fresh
check found driver runtime-OAuth available but independent-worker OAuth unavailable.
That is a notebook-to-App authentication gap; do not strip auth-routing overrides
or fall back to classic without user selection.

For the separately scoped notebook-driver HTTP/API journey:

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
