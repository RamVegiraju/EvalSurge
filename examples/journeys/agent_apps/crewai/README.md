# Prepared CrewAI native agent App: deployment route unresolved

This project hosts the canonical actual CrewAI handler behind
`databricks_agentkit.DurableAgentServer` and `/api/invocations`. It is a prepared
Databricks App source project, **not a deployed or live-validated example**.
Its isolated macOS dependency installation passed compatibility checks, but the
advisory gate failed; native deployment remains unresolved. It does not install
EvalSurge or Locust, import the customer's code into
the load generator, replace the agent with a fixture, or substitute generic HTTP
hosting for the native serving contract.

The inspected `databricks-agentbricks==0.4.0` `AgentProject.load()` requires
`agent.framework`, and its parser accepts only `langgraph` and `openai`. The
deployment code provisions the native Runtime Store only for a loaded project
with `server = "agentbricks"`. Omitting `agent.toml` therefore does not provide
an equivalent managed native deployment. That limitation is not proof that CrewAI
cannot be hosted on Databricks Apps: the native handler boundary is framework
neutral. This project deliberately has **no `agent.toml`**, so it never relabels
CrewAI as another framework. Current official guidance describes adapting an
existing agent with `DurableAgentServer`, but a supported framework-neutral
manifest/deployment path has not been verified for this installed version.
This discrepancy is an explicit prerequisite, not a proposed platform workaround.
The CLI-managed Runtime Store must not be independently created, bound or changed.

## Dependency gate: compatible macOS installation, advisory blocked

The approved-registry metadata inspected on October 11, 2026 exposed CrewAI
`1.15.23`, whose core/CLI distributions require OpenAI `>=2.30.0,<3` and Pydantic
`>=2.11.9,<2.13`. A separately approved isolated macOS/Python 3.11 installation
succeeded, but its advisory audit failed; no actual-framework inference or native
deployment was run. This is not a claim of the newest public stable release.
`pyproject.toml` records those explicit **macOS-compatible dependency constraints**,
not an audited release lockfile, a Linux/App installation result or an approved
replacement for an operator-selected version. Compatibility does not clear the
failed advisory gate or establish native deployment readiness.

The October 12 read-only release recheck found
[CrewAI 1.15.27](https://github.com/crewAIInc/crewAI/releases/tag/1.15.27),
whose tagged manifest requires `chromadb~=1.5.9`. The approved registry did not
advertise that release. ChromaDB 1.5.9 still matches active
[code-injection](https://github.com/advisories/GHSA-36p7-vc44-83pf),
[pre-authentication code-injection](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c),
[authorization-scope](https://github.com/advisories/GHSA-xph7-9rjv-w5fr) and
[cross-tenant authorization](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr)
advisories, with no first patched version listed. This is release/advisory metadata,
not a new installation, exploitability assessment or approved security exception.
Do not relabel the older failed audit as fixed or execute an unreviewed replacement.

The inspected native 0.4.0 base distribution declares SDK `>=0.124.0`, FastAPI
`>=0.129.0`, MLflow Skinny `>=3.10.1`, and `databricks-ai-bridge[memory]>=0.22.0`;
it does not directly require OpenAI 3 or Pydantic 2.13. Its complete transitive
closure was resolved separately through the supported registry, not in the runner
or repository lock. Those declared floors alone do not establish compatibility;
the isolated installation and `uv pip check` below establish only the selected
macOS closure's compatibility. This project does
not select the native `[openai]`/`[langgraph]` extras or install the EvalSurge
runner environment, whose current dependencies conflict with the CrewAI bounds.
Do not mix the environments, force incompatible versions or bypass the registry.

### October 11 isolated prerequisite result: advisory gate failed

The approved hashed closure installed **162 distributions** with CrewAI/core/CLI
`1.15.23`, OpenAI `2.54.0`, Pydantic `2.12.5`, Agent Bricks `0.4.0`, SDK `0.148.0`
and MLflow Skinny `3.17.0`. `uv pip check` reported all installed dependencies
compatible. Actual installed signatures confirmed native async `Crew.akickoff`
and `BaseLLM.acall`; the sample explicitly sets `max_retry_limit=0` rather than
accepting the installed Agent default of two. Telemetry was disabled before
imports. These checks made no model or workspace calls.

The complete hashed export's OSV audit returned eight rows representing four
distinct advisory IDs for ChromaDB `1.1.1`: `PYSEC-2026-311`, `PYSEC-2026-3813`,
`PYSEC-2026-3814`, and `PYSEC-2026-3815`. CrewAI declares `chromadb~=1.1.0`; the
retrieved advisory ranges include this selected version. Do not suppress those
findings, force an out-of-range dependency, or treat `memory=False` as an advisory
fix. An approved compatible fixed dependency route or an explicitly reviewed
security exception is required before live validation. OSV checks hash presence,
not artifact integrity; uv verified the install against export hashes. No Linux
installation, comprehensive license review or independent security sign-off is
established by this macOS prerequisite check.

The separately retrieved, hash-verified Agent Bricks `0.5.0` wheel retains the
same required `agent.framework` parser and LangGraph/OpenAI enum, with Runtime
Store provisioning conditional on the parsed managed-server project. It was
inspected, not installed, and does not resolve CrewAI's native deployment gate.
Retain the failed audit and selected artifact/source provenance; no fixture or
framework-label fallback follows from a successful package import.

## Prepare source; resolve the deployment prerequisite before creating an App

Stage the public project using `stage_shared_sources.py --template crewai` as
described in [the parent recipe](../README.md). It checksum-verifies the same
canonical handler/wrapper as the other frameworks. Then:

1. Choose the exact approved workspace, App name, model service and App caller
   identity. Replace the workspace placeholder in `app.yaml`. The agent uses
   only App-injected M2M credentials, not notebook credentials or a laptop profile.
2. Verify a supported framework-neutral `agentbricks deploy` manifest/version or
   obtain current platform guidance before proceeding. It must preserve the
   actual CrewAI implementation and provision the native Runtime Store through
   supported tooling. Do not invent a framework label, hand-provision or bind that
   store, reuse another App's branch/database/username, or fall back to in-memory
   persistence. Those fields are intentionally absent from this prepared YAML;
   supported tooling must supply them. The entrypoint rejects their absence before
   native construction. Configuration presence is not a store-readiness check.
3. Bind the model service as resource `model`, type `MODEL_SERVICE`, permission
   `EXECUTE`. The content of `model_resource.example.json` is a **single-resource
   raw JSON shape**, not a complete create/update payload and not an executed
   command. Inspected SDK 0.146/0.148 typed resource enums lack `MODEL_SERVICE`;
   use the current reviewed raw CLI/API contract, not an invented SDK enum.
   Preserve the managed resources generated by the verified deployment route.
   Never overwrite an existing App resource list with this one object.
4. Keep `CREWAI_DISABLE_TELEMETRY=true` before importing CrewAI. Configure ingress
   permissions and the selected App's injected port/identity through the platform.
   Only after step 2 resolves, deploy the complete reviewed source/lock through
   that supported native route. Generic Python App upload is not proof of a
   supported native durable deployment.
5. Verify a bounded real invocation, then bind the actual deployed target with
   `Agent.databricks_app(..., protocol="databricks-agent-runtime")` from the approved
   runner. Record the exact artifact/source/resource revision, provider evidence,
   separate quality outcomes, cancellation/drain, report retrieval and cleanup.

Each first attempt permits at most two actual model calls, 512 output tokens per
call, no provider retries/tools/delegation/memory, a 30-second per-call timeout
and a 35-second whole-handler deadline. Requested cancellation/deadlines can wait
for owned authentication work; they cannot undo already dispatched model calls.
No automatic recovery hook is registered. Durable invocation persistence is not
conversational memory or an MLflow trace-export guarantee. The native adapter's
current report path does not establish App output-token extraction or TTFT.

Isolated macOS dependency resolution/installation and source/API inspection were
run; the advisory gate **failed**. Runtime Store setup, deployment, model calls
and every fresh CrewAI live matrix cell are **not run**. Local CrewAI HTTP coverage
and this native App coverage remain distinct. See the [framework/runner matrix](../../FRAMEWORK_MATRIX.md)
and the current official [agent server guide](https://docs.databricks.com/aws/en/agents/deploy/agent-server)
and [agent invocation guide](https://docs.databricks.com/aws/en/agents/query-llms).
