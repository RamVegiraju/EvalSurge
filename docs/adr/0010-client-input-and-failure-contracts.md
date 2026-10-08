# ADR 0010: Lightweight clients and truthful input/failure contracts

- Status: Implemented; designated maintainer review required
- Date: 2026-10-07

## Context and load assumptions

Review of the v2 increment found cancellation acknowledgments rejected by the SDK,
unusable history links for runs without a frozen plan, unhelpful validation errors,
silently discarded inference fields, and mandatory server dependencies for remote
clients. A proposed App-default change also required checking current guidance.

The workload remains one local owner and one Locust engine, with at most 100
closed-loop users, 10,000 measured attempts, 1,000 cases, and an 8 MB request body.
Each run can add one excluded inference probe and, only when explicitly selected,
planning and judge-readiness calls. These fixes do not increase those budgets or
change timing, sampling, retries, or captured-answer judging.

## Decisions

1. Keep `databricks-agent-runtime` and `/api/invocations` as the default for App
   registrations. The official [agent overview](https://docs.databricks.com/aws/en/agents/)
   and [query guide](https://docs.databricks.com/aws/en/agents/query-llms), checked
   October 7 (pages updated October 6), recommend DurableAgentServer for Agent
   Bricks CLI deployments and label MLflow AgentServer/LongRunningAgentServer
   `/responses` as legacy. Existing MLflow Apps select
   `protocols = ["mlflow-agent-server"]` explicitly. No automatic protocol
   discovery, fallback, or trial invocation is introduced. This corrects the
   review premise rather than switching the default to a legacy contract.
2. Fixed message adapters accept exactly one top-level `query` or `messages` input.
   Extra fields, including `custom_inputs`, `actor`, per-case `model`, and `resume`,
   fail admission with fixed safe guidance instead of disappearing. Nested message
   objects retain their existing wire representation. Evaluation references remain
   separate from inference input. The explicit `http-json` contract still sends
   its arbitrary case body; it is not a generic AgentServer decoder. A future
   operator-governed input mapping needs its own identity/routing/lifecycle review.
3. Accept `cancellation_requested` only in SDK cancellation acknowledgments. It is
   not a terminal state or proof that in-flight agent actions stopped. Polling
   continues to use persisted lifecycle states; no mutation is retried.
4. Persist the existing v2 discriminator in compact history and construct v2 status
   links for v2 runs, including recovered snapshots. V1 links remain v1. The
   browser retains its rich v1 report and falls back to a locally constructed,
   same-origin v2 report after a v1 conflict. A planless report shows safe phase
   diagnostics without inventing a plan, measurements, or a quality verdict.
5. Add optional `error.errors` to v2 schema failures: at most 20 issues, each with
   bounded public field locations, a fixed code, and safe guidance. Unknown keys
   are replaced with `<extra>`; submitted values, raw exception text, and validator
   context are excluded. V1 error envelopes are unchanged.
6. Make HTTPX and Pydantic the only mandatory dependencies. The `server` extra owns
   the existing local execution stack; `agents` includes server and framework
   dependencies, preserving the documented developer install. Remote imports and
   CLI commands do not import that stack. Local public names and factories load
   lazily and report the required extra when it is missing. Registry versions,
   artifacts, hashes, and provenance remain unchanged.
7. A completed Runtime invocation must also contain completed handler/message
   output. Reject explicitly unfinished assistant messages without publishing any
   partial text. Missing message status remains compatible with the current
   normalized Runtime output; an explicit noncompleted or null status fails.
   This prevents a successful outer envelope from masking incomplete answers.

## Data flow and ownership

`remote SDK/CLI -> authenticated API -> registered target resolution -> input
validation/admission -> frozen plan -> preflights -> one Locust subprocess ->
journal/traces -> captured-answer evaluation -> version-aware history/report`.

Installing the lightweight client does not move load generation to that client.
The API host owns execution and artifacts. Operator profiles, credentials, tracking
destinations, and scorer implementations stay outside public requests. Rejected
input envelopes perform no inference or planning; App discovery/authentication
can still occur before admission. Report fallback never follows a returned URL
or sends credentials off origin.

## Failure modes and trade-offs

- Rejecting formerly ignored fields is a behavioral tightening for v1, v2, and
  local Python callers. It sacrifices permissiveness to prevent benchmarks from
  silently measuring a different request than production. Callers must remove
  extras or use a reviewed supported adapter, not hide required context in a prompt.
- Rejecting explicitly unfinished Runtime messages tightens response validation.
  A previously accepted partial answer now fails inference preflight or its measured
  attempt. No polling, replay, alternate decoder, or partial-success result is added.
- Lightweight installation requires an explicit extra for local execution. Public
  local APIs remain available with that extra; direct imports of server modules
  still require their dependencies. Wheel-level isolation checks catch accidental
  eager imports and mandatory dependency regressions.
- Safe validation diagnostics reveal schema constraints but not request content.
  Twenty issues may omit later failures; correcting the displayed errors and
  resubmitting is deliberate bounded behavior.
- Browser fallback adds one read for a planless report and keeps two presentation
  contracts. It does not backfill missing evidence or remove the v1 plan requirement.
- Cancellation drains existing requests; external side effects cannot be rolled
  back. Static doctor and controlled local tests are not live App health evidence.
- Journal fsync, runner CPU/network, target latency, and trace/judge work remain
  bottlenecks. Client packaging and these API fixes do not establish sustainable
  throughput, durable workers, tenant isolation, or shared-hosting readiness.

## Verification and live-test gate

Regressions use the real API/SDK cancellation flow, recovered mixed-version history,
the shipped DOM renderer, admission/input boundaries, sanitized schema failures,
and an isolated built-wheel environment without server distributions. Full results
and exact commands belong in `VALIDATION.md`.

The App smoke harness is dry-run by default and requires an explicitly chosen
profile, App, protocol, safe prompt, traffic/spend consent, and separate validation
record before live execution. Its performance-only workload excludes planning and
judging and counts the extra inference probe. It neither deploys an App nor claims
capacity or quality calibration. ADR and public-contract maintainer review remain
required; automated checks do not substitute for that review.
