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

The previous `examples.*` CLI and integration-runner module paths have moved to
`scripts.validation.*`. `examples.python_benchmark` is now the minimal tutorial,
without command-line flags. The obsolete smoke script and its `run.json` were
removed: their missing correctness reference conflicts with fail-fast readiness.
Actual REST/Locust regression coverage and the framework harness remain.
