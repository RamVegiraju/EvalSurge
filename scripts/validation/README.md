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
