# Live CLI progress

Run EvalSurge locally against your configured hosted agent. No separate EvalSurge
API server is required:

```bash
evalsurge run request.json --local --settings operator.toml --wait --progress --timeout 300
```

Interactive waiting sessions show progress automatically. `--progress` also enables
it for a redirected/noninteractive session; `--no-progress` suppresses it. Remote
submission requires `--wait` for progress; direct local execution already waits
before releasing its owned runner.

Progress includes elapsed waiting time and independent phase states. For example
(illustrative output, not live validation evidence):

```text
[1s] preflighting | planning=completed, inference=running, evaluation_readiness=skipped, profiling_readiness=pending, load=queued, profiling=pending, evaluation=pending
[3s] running | planning=completed, inference=passed, evaluation_readiness=skipped, profiling_readiness=passed, load=running, profiling=pending, evaluation=pending
```

Changes appear when observed; an unchanged state produces at most one heartbeat
every ten seconds. Elapsed time includes readiness and post-load phases, not just
the measured load window. Status does not currently include live completed-request
counts, latency or throughput. Final metrics come from the retained report and
the existing summary; a completed run is not necessarily a passing quality check.

Progress goes to stderr and never prints prompts, answers, references, rationales,
run names, credentials or tracking destinations. Structured output remains alone
on stdout:

```bash
evalsurge run request.json --local --settings operator.toml --wait --progress --json > report.json
```

`--json` explicitly exports protected report evidence; store that file securely
and do not commit it. Progress does not enable evaluation or tracing. Configure
agent instrumentation and an authorized trace scope separately as described in
[profiling and evaluation](PROFILING_AND_EVALUATION.md).

Remote observers reuse existing status polls, including server rate-limit/polling
hints. Direct observers read in-memory lifecycle metadata at one-second intervals
plus initial/terminal observations;
no request-level logging or extra trace fetching is added to Locust. This does not
establish zero observer overhead. Slow output still consumes caller resources.
Wait timeout leaves remote work active; direct context exit stops new dispatch
and drains owned work. See [ADR 0021](adr/0021-cli-live-lifecycle-progress.md) for
the callback and measurement boundaries.
