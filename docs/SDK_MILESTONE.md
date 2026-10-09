# Unified SDK milestone and verification gates

The contract is [ADR 0011](adr/0011-unified-direct-and-remote-sdk.md). The direct
Python SDK, typed optional-server adapter, typed evaluation evidence, CLI summaries
and onboarding examples are implemented. This is not a release sign-off: current
live journeys, full compatibility checks and designated maintainer review remain
required. Exact check results are recorded in [validation](../VALIDATION.md).

## Real-inference journey matrix

| Journey | Harness/example | Required evidence before claiming it passed |
| --- | --- | --- |
| Local runner → local HTTP agent | `examples/journeys/local_runner_http_target.py`; `scripts/validation/local_runner_http_target_journeys.py` | Actual compiled/native framework and actual selected model; typed status/result/report, failed pre-provider probe, active cancellation and cleanup |
| Local runner → deployed App | `examples/journeys/local_runner_databricks_app_target.py`; explicit native App harness | Existing authorized App, verified deployed framework/source and actual model; refreshed OAuth, correct native protocol, fail-fast, cancellation and reports |
| Classic notebook runner → App (deferred) | Retained `examples/journeys/classic_notebook.py` | Out of the current serverless-only scope; no cluster created/started or classic fallback |
| Optional REST/server → registered target | Existing live REST/framework harness plus new typed remote SDK | Service auth, operator-only aliases, same frozen request and measured/judged semantics, inspectable failure report |
| Serverless notebook runner → App | `examples/journeys/serverless_runner_databricks_app_target.py`; `scripts/validation/serverless_runner_app_target.py` | Prepared/authentication-blocked. Agent remains in its deployed App; notebook hosts EvalSurge/Locust only. Driver prerequisites checked; independent worker runtime-OAuth failed. Current profile-only App contract is not established on serverless |
| Retained notebook-local helper diagnostic | `scripts/validation/serverless_sdk_journeys.py` | Not an advertised agent-hosting option or a deployed-App substitute; any retained receipts are classified separately |

Dry-run prints only bounds, for example:

```bash
uv run --frozen --no-sync python -m scripts.validation.unified_sdk_journeys \
  --journey http --framework langgraph --profile YOUR_SELECTED_PROFILE \
  --target-model YOUR_VERIFIED_MODEL_ENDPOINT --exercise-cancel
```

Live mode additionally requires `--live --accept-paid-traffic --artifact-dir
artifacts/NEW_PRIVATE_DIRECTORY`. Defaults cap each of at most two runs at five
measured requests, concurrency five and 30 dispatch seconds; each adds one excluded
model-bearing probe. HTTP mode also sends one deliberate unknown-route probe with
no model dispatch. The limits are top-level invocation limits, not model/tool
spend quotas. No planner/judge is called. A failed normal run stops further traffic.
Natural completion before cancellation is reported as unexercised, not a pass.

The user confirmed `e2-demo-field-eng` for the new workspace. Secure CLI-keyring
access works outside the sandbox; no profile change or auth-storage downgrade was
needed. Serverless driver runtime-OAuth works, but an independent worker cannot
obtain that notebook context. Do not copy laptop tokens or weaken App profile
isolation to work around it. Current native App creation/readiness and latest
local checks are tracked separately in
[hosted journey validation](HOSTED_JOURNEY_VALIDATION.md). Classic compute is
explicitly deferred, not a fallback for the serverless authentication gap.
Live GPT-OSS Chat Completions validation exposed an OpenAI Agents structured-content
preflight failure; the separately selected mini-model journey does not erase it.
The mini-model serverless job `584248337638691` also failed: the Python kernel
exited unexpectedly, with an MLflow experiment/store startup error in its output.
There is no final receipt establishing counts, inference success or cleanup. The
harness experiment-ID leak and Uvicorn startup exit were reproduced and fixed
using native local storage/lifespan checks without inference. The latter reproduced
host exit code 3; no live rerun or definitive remote root cause is claimed.
See the exact outcomes and remaining gates in `VALIDATION.md`.

## Follow-up implementation order

1. **Runner read/auth overhead:** reproduce duplicate App lookups under concurrent
   first dispatch, then initialize one refreshable origin-bound credential source
   before users spawn. Preserve deployment identity checks and do not cache tokens
   or authorization failures. Separate status metadata from full snapshots/profile
   reads with recovery/consistency and privacy tests; no indefinite stale cache.
2. **Measure journal/generator cost:** use controlled storage microbenchmarks and
   actual bounded model runs, recording fsync duration, event-loop lag, CPU/network
   and dispatch timing. Compare disk/topology explicitly. Do not turn a guess about
   overhead into evidence or silently weaken journal durability by batching writes.
3. **CI thresholds:** define metric scope/units and insufficient-coverage behavior,
   then explicit latency/error/quality gates with nonzero exit codes. Keep lifecycle
   failure distinct from breached SLOs and require numeric/categorical judge policy.
4. **Excluded warmup and stages:** persist phase boundaries and exclude warmup rows
   consistently from metrics and quality sampling. Define per-stage dispatch/drain,
   arrival/concurrency accounting, admission/cancellation and comparison baselines
   before adding latency-throughput curves. Keep the one Locust engine.
5. **Comparisons and native streaming:** compare compatible workloads/models/evidence
   and show gaps. Verify actual Runtime streamed text/terminal/token events before
   adding App TTFT. First-event timing is not answer-text TTFT. Do not reuse legacy
   `/responses` streaming semantics without checking the native server contract.

Each material timing/persistence/transport change needs its own ADR, regression
coverage and maintainer review. Durable distributed infrastructure and capacity
campaigns remain deferred, subject to [production gates](PRODUCTION_READINESS.md).
