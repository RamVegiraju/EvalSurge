# Your dataset, fixed judges, or automatic selection

These examples use the same `RunCreate` request in direct Python and optional
server execution. They are configurations, not recorded model-quality results.
No new model calls, custom judge registration, or deployments are performed by
loading them. Use an already running real agent and explicitly approved providers
before submitting a request.

| Sample | Purpose | Provider work when submitted |
| --- | --- | --- |
| [explicit.json](explicit.json) | Fixed `relevance` and `correctness` | Catalog judge readiness and sampled judging; no planner |
| [registered.json](registered.json) | Your reviewed `registered:policy` judge | Exact native MLflow scorer resolution, readiness and judging |
| [automatic.json](automatic.json) | Opt-in planner selects supported criteria | Planner, selected-judge readiness and sampled judging |
| [dataset.json](dataset.json) | Your input/reference records | None until submitted as `cases` |
| [operator.toml](operator.toml) | Private provider/approved judge placeholders | Loading settings does not call providers |

All three request examples initially contain one referenced case; the dataset
loader replaces that with four cases covering opened/sealed items, a date cutoff,
and a policy-override instruction. The agent must actually know the same policy.
An illustrative reference is not evidence your production policy is correct.

## Load your own JSON dataset

`dataset.json` is a list of `{ "input": {...}, "reference": {...} }` records.
There is no public `dataset_path`; read it on the client and put it in `cases`:

```python
from pathlib import Path
from examples.quality.load_dataset import build_request

request = build_request(
    Path("examples/quality/explicit.json"),
    Path("examples/quality/dataset.json"),
)
# Your existing direct client: run = client.start(request)
# Or optional server client: run = remote_client.start(request)
```

From a checkout you can inspect the validated request without inference:

```bash
uv run python -m examples.quality.load_dataset \
  examples/quality/explicit.json examples/quality/dataset.json
```

This prints inputs and references: protect the output for private datasets.
Keep reference facts/labels and scenario metadata in `reference`; fixed message
protocols reject arbitrary extra top-level inference fields. Up to 1,000 cases
are allowed. Select an evaluation budget that actually covers the scenario groups;
five sampled captures per judge does not guarantee coverage of every edge.

## Bring your own reviewed judge

Select an existing, reviewed MLflow scorer with `scorers=["registered:policy"]`.
The operator maps that alias to its authorized experiment, registered name,
exact version, and required fields in [operator.toml](operator.toml). Configure
`MLFLOW_TRACKING_URI` and its authentication separately. No scorer source,
registry URL, OAuth token, or executable code is accepted in a benchmark request.

For direct execution, load the private settings using
`benchmark_agents.settings.load_settings("your-private-operator.toml")` and pass
them as `settings=...` to `EvalSurge(...)`. This sample's settings already bind
`agent`; do not also register that same alias through `targets`. Alternatively,
omit its `[connections.agent]` block and supply `targets={"agent": Agent.http(...)}`
or `Agent.databricks_app(...)` outside the request. With a server,
use `BENCHMARK_CONFIG` for the same operator configuration. The
[integration guide](../../docs/PROFILING_AND_EVALUATION.md) describes trusted
native MLflow registration and trace scope.

The registered definition controls its provider/model and retry behavior. Catalog
`judge_model` does not override it. Native deserialization is trusted operator
code, not a caller sandbox. Exact version/definition hashes are frozen and checked.
Define and calibrate a new production rubric with domain-owner review rather than
treating this placeholder as a shipped policy judge.

## What automatic means

Automatic selects supported catalog criteria and potentially approved registered
aliases using your description, evidence availability, and up to three input
previews. Summarize every important edge-case priority in `description`; later
cases are not all previewed. The selected ready judges actually run: this is not
only a suggestion list.

Automatic cannot choose arbitrary model endpoints, upload judge code, invent
references, or guarantee particular judge IDs. Use explicit mode when fixed
criteria are required. V2 has no plan-approval pause; the legacy v1 plan workflow
supports reviewing/reusing a frozen plan before load. No supported selection or
missing required evidence fails readiness instead of silently disabling quality.

## Important edges: do not submit these as normal tutorials

| Case | Expected boundary |
| --- | --- |
| [automatic-with-scorers.json](edge-cases/automatic-with-scorers.json) | Schema rejects scorer IDs outside explicit mode; no inference |
| [unknown-judge.json](edge-cases/unknown-judge.json) | Approved-alias validation rejects it; no arbitrary judge loading |
| [missing-first-reference.json](edge-cases/missing-first-reference.json) | Schema-valid, but correctness readiness lacks first-case evidence and stops measured load |
| [unavailable-groundedness.json](edge-cases/unavailable-groundedness.json) | Catalog groundedness is currently unimplemented/`needs_data`; measured load is blocked |
| Later case lacks correctness facts | Its captures are ineligible for correctness; report reduced coverage, not fabricated truth |
| Registered judge requires `trace` but probe is uncorrelated/missing | Readiness fails; endpoint timing cannot replace a real authorized trace |
| Judge returns `false` | Valid assessment; quality can fail while lifecycle completes |
| Judge errors after successful load | Performance is retained, evaluation errors/gaps are explicit |

These schema/configuration checks are not real-inference coverage. Do not rerun
readiness failures as paid probes to conceal them. Correctness references use
`expected_response` or `expected_facts`, including the first case.

## Traffic and reports

Published positive examples use concurrency two, ten-second dispatch, and ten
measured agent invocations at most, plus one excluded inference probe. Each agent
invocation can perform multiple model/tool calls. Each selected judge
has one extra readiness assessment and at most five sampled assessments; automatic
adds planning. These bounds are not token/dollar caps and do not establish capacity.
Judges use captured answers, never reinvoke the target.

See [the report guide](../../docs/REPORTS_AND_JUDGES.md) for typed outcomes and
browser sections. Scalar custom scores need your interpretation/threshold;
only boolean assessments have an intrinsic pass rate. Lifecycle `completed`
does not assert quality passing. No pass rates have been invented for these examples.
