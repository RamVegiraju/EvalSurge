# Three tools, one deliberately slow step

This sample uses a local EvalSurge/Locust runner against a separately hosted
loopback HTTP agent. The agent is an actual, fixed serial LangGraph workflow:

`lookup_order → lookup_return_policy → quote_return_shipping → check_return_eligibility → real model answer`

The three tools read the included synthetic documents and compute a shipping
quote. The eligibility step applies business rules. A real Responses model then
explains those facts; the model does **not** select the tools. No model responses
are stubbed and there is no fallback, memory, session store or tool retry.
`scenario="delayed"` adds two seconds of nonblocking `asyncio.sleep` **inside the
agent's shipping tool span**, not in the load generator.

## Run from a reviewed source checkout

Install the reviewed package/agents environment as described in
[installation](../../../docs/INSTALLATION.md). These source examples are not
installed into the wheel. Use separate terminals for the agent and the runner;
no EvalSurge API server or Databricks App deployment is needed.

First choose a private output directory and initialize your own local trace
experiment. This setup makes no inference call:

```bash
umask 077
mkdir -p /absolute/private/demo/traces
uv run --frozen --no-sync python -c '
import mlflow
mlflow.set_tracking_uri("sqlite:////absolute/private/demo/traces/traces.sqlite")
experiment_id = mlflow.MlflowClient().create_experiment(
    "multitool-heatmap", artifact_location="/absolute/private/demo/traces/artifacts"
)
print(experiment_id)
'
```

Save the printed experiment ID. Select your exact OAuth profile, HTTPS workspace
origin, model and Responses API route. Do not use a default profile or copy tokens
into requests. The native transport refreshes SDK authentication only for that
exact selected model route. Confirm that your selected model accepts it.

```bash
uv run --frozen --no-sync python -m examples.journeys.multitool_heatmap.agent \
  --profile YOUR_SELECTED_PROFILE \
  --workspace-host https://YOUR_WORKSPACE.cloud.databricks.com \
  --model system.ai.gpt-oss-120b --api mlflow-responses \
  --tracking-uri sqlite:////absolute/private/demo/traces/traces.sqlite \
  --experiment-id YOUR_PRINTED_EXPERIMENT_ID --trace-export sync \
  --port 9002 --allow-paid-inference
```

In the second terminal:

```bash
uv run --frozen --no-sync python -m examples.journeys.multitool_heatmap.runner \
  http://127.0.0.1:9002/invoke \
  --tracking-uri sqlite:////absolute/private/demo/traces/traces.sqlite \
  --experiment-id YOUR_PRINTED_EXPERIMENT_ID \
  --artifact-dir /absolute/private/demo/benchmark --allow-paid-inference
```

The workload is capped at four measured attempts plus one excluded readiness
probe, with five configured users and a ten-second dispatch ceiling. Four requests
cannot occupy all five users; this is a functional smoke, **not a capacity test**.
Each successful invocation has one actual model call, a 512-output-token ceiling,
30-second model deadline, 35-second handler deadline and 40-second HTTP deadline.
The agent rejects a sixth model transport attempt over its lifetime. Stop the
agent with Ctrl-C after the run; its lifespan owns and closes its native clients.
Re-running this sample requires separately approving another bounded workload.
No planner or judge is called: evaluation remains off while trace readiness must
pass on the captured probe before measured load starts.

The runner prints the shared metric/evidence summary, run ID and an optional
viewer URL, and retains report/request artifacts in the private directory.
Failed readiness also prints its retained report information and exits nonzero
after cleanup; it does not reinvoke the agent or overwrite the failed evidence.
The URL is not yet running: **after the runner exits and releases exclusive
storage ownership**, start the existing optional loopback API/report viewer over
the same retained directory:

```bash
BENCHMARK_ARTIFACT_DIR=/absolute/private/demo/benchmark \
  uv run --frozen --no-sync uvicorn benchmark_agents.api:app \
  --host 127.0.0.1 --port 9003 --no-proxy-headers
```

Open the printed `http://127.0.0.1:9003/reports/?run=YOUR_RUN_ID` URL. This API
server is **only for viewing after direct execution**; it did not generate the
load and starting/viewing it makes no target or model call. Do not start it while
the runner owns the directory or start multiple workers for that directory.
Ensure any existing `BENCHMARK_CONFIG` selects this same artifact directory;
otherwise it overrides the environment-based directory. Keep the server bound
to loopback with proxy headers disabled. If no API key is configured, loopback
reads work without a key; if `BENCHMARK_API_KEY` is configured (including through
operator configuration), enter it in the report's API-key field. A configured
key remains required even locally. Never place keys in the URL or publish them.
Stop the viewer with Ctrl-C when finished. This is the existing full API, not a
new read-only viewer implementation: use only its report reads for this sample.

Do not publish raw trace databases, answers, credentials or benchmark artifacts
with the sample sources.

## What the report should reveal

The category heatmap has one **Tools** column, not one column per tool. Delayed
cases should show roughly two seconds of Tools occupancy and substantially darker
cells than normal cases. Inspect named waterfalls and hotspot rows for the
individual `lookup_order`, `lookup_return_policy` and `quote_return_shipping`
spans. Enable “Show enclosing/framework spans” to inspect the separately traced
`check_return_eligibility` decision. Native OpenAI autologging adds the actual
`CHAT_MODEL`/`LLM` operation; `traced_handler` adds the correlated agent boundary.

Inclusive span durations overlap. Use the report's overlap-aware exclusive
category occupancy; do not sum all inclusive spans into wall time or subtract
tracing overhead from client latency. Synchronous export, auth, parsing, network
and scheduling can affect the observation. Generator health is not an accuracy
certificate, and a successful preflight does not establish concurrency capacity.

## Validation and asynchronous export limitation

The public agent and runner entrypoints were exercised outside the checkout on
October 12, 2026 using the installed `0.2.1.dev2026101203` wheel, actual LangGraph
and real `system.ai.gpt-oss-120b` Responses inference. Separate sync and async
trace-export runs each passed one excluded probe plus four measured attempts:

| Export mode | Measured successes | Correlated traces | Delayed shipping spans |
| --- | --- | --- | --- |
| Sync | 4/4 | 4/4 | 2001.253 / 2003.961 ms |
| Async | 4/4 | 4/4 | 2001.353 / 2001.354 ms |

Both had zero errors, six actual spans per measured request, complete measurements,
and clean agent/worker shutdown. Configured concurrency was five, but only four
requests were measured and peak HTTP concurrency was four. Evaluation was off;
no judge, retry, fallback or App deployment was used. The successful async smoke
validates this local SQLite journey, not arbitrary remote-export latency or
governed Databricks UC collection. **Actual browser visual verification remains
unperformed.** See [validation](../../../VALIDATION.md) for artifact hash, run IDs,
installation checks and preserved earlier failures.

The earlier private source workflow was exercised on October 12,
2026 with actual LangGraph, actual `system.ai.gpt-oss-120b` inference, local HTTP
hosting and local SQLite MLflow. Its successful run had four successful measured
answers, no errors, full correlated trace coverage and two delayed shipping spans
of approximately 2001 ms. Light/dark JavaScript checks used the real generated
report. **Actual browser visual verification has not been performed.** See the
[validation record](../../../VALIDATION.md) for exact runs, limits and failure
evidence; copying that implementation is not a new paid validation run.

The preceding asynchronous-export probe passed inference but failed trace
readiness with `scope_mismatch`; measured load was correctly skipped. A later
read-only check found matching experiment/run/request metadata. This suggests a
metadata-visibility race, but the original read did not retain which field was
provisional. It remains a recorded failure, not a silently retried model call.
The agent entrypoint defaults to **synchronous trace export in this sample
only** to reproduce the demonstrated report. `--trace-export sync` states that
choice explicitly; neither mode flushes every request or changes EvalSurge's
defaults. For fresh approved validation, `--trace-export async` selects native
asynchronous export before the local exporter initializes. Restart the agent
with a fresh private trace experiment and approve another five-call workload;
changing the flag is not itself live-validation evidence. The bounded sync/async
public-entrypoint results above used separate fresh trace stores and the same
installed wheel; they did not overwrite the original failed probe.

The collector now boundedly re-reads missing correlation metadata, only after
the trace ID and authorized experiment match. Present conflicting run/request
values still fail closed immediately; exhausted visibility remains a missing
gap. A native local MLflow/SQLite non-LLM reproduction passed for this fix,
without provider stubs, target reinvocation or broad trace discovery. The
original paid asynchronous probe remains failed; it did not preserve its
initially mismatching field, so this reproduction does not prove that exact
probe's cause. Fresh asynchronous real-model validation and actual browser
visual validation remain unperformed. See
[ADR 0020](../../../docs/adr/0020-load-only-correlated-trace-readiness.md).

The new public files have offline request/input/data/source-contract checks;
those checks make no model calls and are not additional real-inference evidence.
