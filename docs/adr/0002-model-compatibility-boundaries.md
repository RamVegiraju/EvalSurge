# ADR 0002: Explicit model compatibility at the owning boundary

- Date: October 4, 2026
- Status: Proposed for maintainer review; implemented for the local alpha
- Review owner: repository maintainer

## Context

A real Databricks GPT-5.4 mini Chat Completions call rejected function tools with
`reasoning_effort="low"`. The recorded error required Responses or effort `none`.
Applying `none` to every model would replace one incompatibility with another.
Framework identity, model-name prefixes, and an OpenAI-compatible URL do not prove
reasoning, JSON, tool, token-cap, or usage support.

Load assumptions remain ADR 0001's one local owner, bounded Locust workload, and
post-load profiling/judging. No paid discovery calls are introduced.

## Decision and data flow

- Hosted agent configuration stays inside the agent. Locust sends only the selected
  streaming envelope and correlation headers; it does not inject model reasoning,
  tools, temperature, or execution settings from evaluation metadata.
- Add optional `target.request_usage`, default true to preserve existing behavior.
  False omits `stream_options` on `openai-chat`. MLflow agent-server is unchanged.
  Missing usage remains null with explicit coverage; it is never estimated as zero.
- Synthetic framework demos resolve settings by exact provider and endpoint.
  The verified Databricks mini preset uses `max_completion_tokens=1024`, `none`
  with function tools, and `low` for the graph's non-tool model call.
- Unknown demo models omit reasoning, parallel-tool and store options. Their token
  cap uses `max_tokens` by default. The operator can explicitly choose the token
  parameter and reasoning effort; invalid or known-incompatible settings fail
  locally. This is not a universal model capability detector.
- Keep Chat Completions explicit in these demos. Do not silently switch to
  Responses, change models, remove tools, or retry 400s with altered parameters.
- The demo's explicit streamed-usage setting controls the two synthetic model
  clients independently of the hosted-target adapter. Unknown or partial model
  usage remains null, not the Agents SDK's normalized zero.
- Keep demo model tracing at stable public boundaries: LangChain autologging for
  LangGraph and an MLflow span around the Agents SDK's public stream hook. Disable
  duplicate OpenAI SDK autologging and the SDK's external trace exporter. An
  observed null completion ID prevents MLflow's OpenAI stream reconstruction from
  closing its span, losing the correlated root trace. Do not fabricate provider
  IDs or monkey-patch installed dependencies to hide this incompatibility.
- Allow separately selected planner/judge endpoints in the live helper before
  startup. A target model's tool support does not establish JSON-object support.
  Existing public plans already bind these independent roles; no plan migration
  or catalog transport expansion is introduced.
- Planning supports the documented Databricks/OpenAI clients. Direct catalog
  judging remains Databricks-specific. Operator-allowlisted native MLflow scorers
  may use their configured providers, under the operator's transport/spend budget.

## Trade-offs and failure modes

Explicit configuration preserves reproducible measurements and avoids replaying
tool actions, but makes the operator responsible for an endpoint's actual contract.
Default-on usage preserves token metrics for current clients; endpoints without
the extension must opt out. Unknown optional features stay omitted rather than
inventing compatibility. Presets require review when hosted endpoint revisions
change; a readiness check alone cannot prove feature compatibility.
Explicit demo model spans trade native Agents orchestration detail for stable
stream lifecycle, captured model outputs, tool/memory evidence, and reproducible
correlation across OpenAI-compatible providers. Upstream autologging fixes require
another reviewed integration change, not an automatic runtime switch.

No routing service, new dependency, arbitrary caller-selected credential reference,
or credential-bearing base URL is added. Existing admission, timeout, exact target
authorization, retry, trace scope, and evidence rules stay unchanged.

## Verification and compatibility

Use actual LangGraph and OpenAI Runner streams with controlled HTTP boundaries for
both the portable settings and verified preset. Assert emitted JSON, captured
outputs, isolated memory, and correlated traces. Test preset provider/model scope,
invalid configuration, target usage opt-out, unknown token usage, and no fallback
after provider rejection. Run full tests and regenerate/validate OpenAPI.

The API field is additive with its old behavior as default. Persisted requests
without it still parse. Default-on idempotency replay accepts the old hash without
this field; an explicit opt-out conflicts with that key. The evaluation-plan
contract/version does not change.
Generalizing catalog judge transports is a separate frozen-plan/migration decision,
not a claim of native Anthropic/Gemini support from this change.
