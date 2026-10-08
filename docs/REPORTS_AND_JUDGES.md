# What generated reports contain

A unified Python `run.wait()` or `run.report()` returns a typed `Report`:

```text
Report
  run: Result
    id, name, status, phases, links
    summary: performance, quality, evidence_gaps
    metrics: client timing, throughput, errors, usage coverage
    preflight, evaluation_preflight, load_error, planning_error
    evaluation: per-judge outcomes, request/selection coverage, assessments
  profiling: trace coverage, gaps, wall occupancy, hotspots
  requests: one bounded page of content-free request profiles
  offset, limit, total
```

This is a field guide, not a fabricated successful run. Use
`report.model_dump_json(indent=2)` for actual JSON. `run.result()` provides the
typed `Result` without the profile page. `/v2/runs/{id}/result` and `/report`
expose the corresponding protected server data.

## Completion, quality, and gaps are separate

- `status` describes the lifecycle. `completed` does not mean every judge passed.
- `summary.performance` distinguishes complete/incomplete/not-run measurements.
- `summary.quality` distinguishes off/pending/available/unavailable evidence.
- `evaluation.results` holds each judge's execution, coverage, and verdicts.
- `summary.evidence_gaps` and profiling gaps show missing observations explicitly.

Boolean judge outcomes have `pass_rate` where available; a failed verdict is a
real quality observation, not a transport failure. Registered judges can return
numeric or categorical values instead; those do not automatically have a pass
rate. Missing evidence and execution errors never count as passing assessments.
Review selected/eligible/scored counts beside any score, including failed load
attempts and judge errors. No CI threshold is silently applied by this milestone.

Successful-only timing percentiles can omit timeout/failure latency. Native
DurableAgentServer JSON has no answer-text TTFT or token usage. No correlated
agent-side traces means no internal tool/model/memory timeline. Unknowns are
displayed as unavailable, not zero. Throughput includes drain in its denominator;
warmup is not yet excluded. Single-level smoke throughput is not sustainable capacity.

## Browser report

Close the direct artifact owner and follow [optional report serving](OPTIONAL_SERVER.md#open-a-retained-report).
The browser shell at `/reports/?run=YOUR_RUN_ID` displays:

1. Run identity, workload/load level, readiness and independent phase outcomes.
2. Suggested judges: frozen selection source, rationale, evidence requirements,
   readiness counts, and exact brought-scorer version when available.
3. Evaluation results: per-judge scores/pass rates, sampled coverage, execution
   errors, and bounded failed-assessment details with rationale.
4. Performance: client latency/TTFT, throughput, errors, completeness and usage.
5. Latency anatomy/hotspots, then request heatmap and selected span waterfall
   when real correlated traces exist; missing trace evidence stays visible.
6. Evidence and measurement notes.

The section is named "Suggested judges" even for an explicit plan, but its badge
distinguishes "Explicit selection" from "LLM-suggested". A suggestion is not a
calibrated quality verdict. In automatic mode the frozen ready selection is used
for actual judging; in explicit mode no planner selected the IDs.

The browser reads legacy v1 report data for runs with a frozen plan and uses a
same-origin v2 fallback for failures before a plan exists. V2 `Result`/`Report`
does not include the frozen plan/suggestion rationale; do not assume those fields
exist in the Python v2 model. There is no standalone HTML export. The initial
profile page is bounded (25 by default, 100 maximum), not the whole run.

Protected report data can include judge rationales quoting prompts, references,
and answers. The browser shell is data-free until authenticated fetch; service
keys stay in memory, never URL/persistent storage. Protect exports and artifacts.

## Which judges did the actual App tests use?

The retained October 8, 2026 LangGraph/OpenAI Agents App load runs used real
`system.ai.gpt-oss-120b` inference, concurrency five, and 500/500 measured successes
each, plus their excluded successful probes. Evaluation was off: **no planner or
judge was recommended or called**. Those runs do not establish model quality,
trace coverage, or capacity. Earlier explicit quality checks used relevance and
correctness; explicit selection must not be relabeled as an automatic recommendation.
See [the actual validation record](../VALIDATION.md) for their different boundaries.

Two retained real-inference examples show the distinction:

| Historical run | Frozen selection | Actual quality evidence |
| --- | --- | --- |
| October 4 LangGraph integration, two measured calls | LLM recommended `relevance` and `correctness`, both ready | One captured answer judged per criterion, both true; planner/judge `databricks-gpt-5-4-mini` |
| October 5 three-minute run, 896 measured successes | Explicit `relevance` and `correctness`; not automatic recommendations | Relevance 5/5 (1.0), correctness 3/5 (0.6), lifecycle completed; judge `databricks-gpt-5-4-mini` |

These are actual historical records, not scores generated for the new examples.
One or five scored answers do not calibrate a judge or establish a population
pass rate. The October 4 record is framework integration, not the new notebook
journey or October 8 App quality. Associated earlier failures remain retained;
later successful runs do not erase them.

The new direct/notebook/quality samples are not new live test results. Current
workspace validation requires profile reauthentication before fresh App checks;
previous checks found the test Apps absent. Classic notebook compute still needs
explicit selection and separate real-model validation; serverless is another gate.
See [the SDK milestone and live gates](SDK_MILESTONE.md) for the pending journey matrix.

## Choose your judges and dataset

Use [the quality examples](../examples/quality/README.md) for three clear choices:
fixed catalog judges, your reviewed registered judge alias, or automatic selection.
Load authoritative dataset records into `cases`. The planner cannot invent them.
Target agent model, automatic planner model, and catalog judge model are separate
operator configuration roles; a registered judge owns its own model definition.
