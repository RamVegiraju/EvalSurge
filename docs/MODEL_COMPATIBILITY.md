# Model and provider compatibility

Provider independence is a boundary, not a promise that every API accepts the
same parameters. A hosted agent owns its model, tools, memory, and provider client.
EvalSurge observes that agent through a documented streaming or synchronous JSON contract.

## Current support

| Boundary | Supported contract | What this does not imply |
| --- | --- | --- |
| Hosted target | `openai-chat` and `mlflow-agent-server` streaming; synchronous `databricks-agent-runtime`; explicit `http-json`; any underlying model/provider | Native Anthropic/Gemini request APIs, arbitrary agent envelopes, or automatic remote instrumentation |
| Planner | Operator-configured Databricks or OpenAI Chat Completions with JSON-object output | Arbitrary providers, JSON-schema support, or universal model compatibility |
| Catalog judges | Direct SDK-authenticated Databricks Chat Completions; frozen model/profile/host and budgets | Provider-independent catalog judge transport |
| Brought MLflow judges | Operator-allowlisted, exact-version native scorers and their provider configuration | Uploaded Python, caller-selected stores/credentials, or uniform transport budgets |
| Synthetic demos | Fixture responses or explicitly selected Databricks endpoint; real frameworks | A general provider gateway or paid automatic capability probing |

Locust never adds reasoning, tools, temperature, or token caps to the hosted agent
request. Fixed message adapters require exactly one `query` or `messages` input;
extra top-level fields are rejected, not retained as evaluation metadata or silently
dropped. Evaluation evidence belongs in `expectations` (v1/Python) or `reference`
(v2). `http-json` sends its raw body under a separate explicit response contract.
The `openai-chat` adapter requests streamed usage by default. Set
`target.request_usage=false` to omit `stream_options` for incompatible endpoints.
Missing token usage remains null with a coverage fraction, not zero.

## Verified demo preset

The current native App sample has a different contract from the framework demos
below. Its October 7 check used `system.ai.gpt-oss-120b` via the MLflow Responses
route and the actual `OpenAIResponsesModel`/`Runner.run`. The first MLflow Chat
attempt failed because reasoning/text content blocks were incompatible with the
non-streaming chat converter. The failure is retained; no converter patch or
runtime fallback was added. Model-service metadata supported MLflow Chat/Responses,
not the native OpenAI gateway route. The App still exposes `/api/invocations`;
public agent protocol and internal model API are independent.

Performance-only needs just the target's own model. The separate tiny quality
check explicitly chose `databricks-gpt-5-4-mini` for relevance/correctness and used
authoritative references; it used no planner. Automatic mode additionally needs
an operator-configured compatible planner, which may share the judge endpoint
but remains a separately frozen role. No omitted scorer policy enables paid calls
by default on v2 or local Python. See [target setup](TARGETS.md) and
[App validation](DATABRICKS_APP_VALIDATION.md) for exact boundaries.

### Earlier framework demo preset — October 4

On October 4, 2026, the selected workspace's `databricks-gpt-5-4-mini` rejected
function tools with `reasoning_effort="low"` on Chat Completions. Its error required
Responses or effort `none`. This is a provider/model/API/tool combination, not a
global requirement for OpenAI Agents.

The demo resolver matches the exact Databricks provider and endpoint:

- Token cap: `max_completion_tokens=1024`.
- OpenAI Agents' tool-enabled call: effort `none`.
- LangGraph's non-tool model call: effort `low`.
- Unknown pairs: omit reasoning and optional parallel-tool/store settings; use
  `max_tokens=1024` unless the operator explicitly selects another token parameter.

Operator overrides for the demo are `EVALSURGE_DEMO_TOKEN_PARAMETER` (`max_tokens`
or `max_completion_tokens`), `EVALSURGE_DEMO_REASONING_EFFORT`, and
`EVALSURGE_DEMO_REQUEST_USAGE` (exact `true`/`false`, default `true`). They do not
configure the target adapter, planner, or judge. Invalid values and known-invalid
mini tool/reasoning combinations fail locally. Explicit overrides for unknown
models are the operator's compatibility responsibility.

The demo uses LangChain tracing for LangGraph and an explicit MLflow span around
the public Agents SDK model-stream hook. OpenAI SDK autologging and the native
Agents trace exporter are disabled in the demo. This avoids duplicate model
instrumentation and an observed MLflow reconstruction failure on null provider
completion IDs, without inventing IDs or patching an installed package.
Missing or partial Agents token usage remains unknown, not a fabricated zero.

No provider rejection triggers model switching, API switching, removing tools,
parameter negotiation, or target retries. Such fallbacks could replay tool actions,
distort latency, and change the behavior under evaluation.

## Additional model canaries — October 4, 2026

These are observations from the explicitly authorized workspace, not universal
provider capabilities or immutable model revisions:

- `databricks-claude-haiku-4-5`: streamed function tools accepted; JSON-object
  mode rejected with HTTP 400. Do not select it for the current JSON-object
  planner/catalog-judge transport. A Claude target can still use independently
  selected supported planner and judge models.
- `databricks-gemini-2-5-flash`: JSON-object mode accepted; tool streaming with
  `stream_options` rejected with HTTP 400. The explicit no-extension tool canary
  passed and still reported usage. Its first LangGraph run passed load/judging
  but lacked correlated traces because OpenAI autologging could not reconstruct
  a completion with a null ID. The failure remains recorded.

Final Claude and Gemini target smokes passed both framework load/profile paths
with explicit GPT planning; Claude used GPT judges and Gemini used Gemini judges.
Gemini's available relevance/correctness assessments completed, while the
LangGraph report preserves an unsupported groundedness suggestion as needs_data.
A separate Gemini-planner retest failed with HTTP 502 before target traffic;
its cause remains unresolved. Do not interpret JSON-mode acceptance as reliable
planner compliance or universal end-to-end support.

See [validation evidence](../VALIDATION.md) for full-run outcomes. The helper's
`--planner-model` and `--judge-model` flags select roles **before** a run; their
default remains `--model`. They are not fallbacks after a failed provider call.

## Adding a provider or model

1. Inspect the operator-authorized endpoint's documented schema/model revision.
   Record its API family, tool support, token-cap field, reasoning combinations,
   structured output, streamed terminal events, and usage support. Endpoint names
   and readiness alone do not establish these capabilities.
2. Keep model-specific settings inside that agent/provider boundary. Add a narrow
   tested preset only when needed; unknown optional settings remain omitted.
3. Validate the actual SDK-emitted request and streamed tool/answer flow against
   controlled HTTP boundaries. Include negative cases and assert no retries on 400.
4. Run a separately authorized, small live canary before any load test. Retain
   failures and provider revision evidence; do not infer capacity from the canary.
5. Generalizing catalog judging requires an ADR and frozen provider, destination,
   credential reference, token/JSON capabilities, transport budgets, and regression
   tests. Do not add a routing framework solely to claim broader support.

These recommendations follow the [Agents SDK's provider integration and feature
compatibility guidance](https://openai.github.io/openai-agents-python/models/).
The installed SDK and LangChain request builders are also checked by wire-level
regressions. Public upstream documentation can be newer than the compatible locked
versions in the lock; consult [dependency limitations](DEPENDENCIES.md).

See [ADR 0002](adr/0002-model-compatibility-boundaries.md) for the decision,
failure modes, compatibility impact, and review boundary.
