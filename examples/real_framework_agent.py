"""Real-model, request-isolated HTTP helper examples; no fixture path exists.

This is customer-process code, not a framework adapter in the EvalSurge runner.
Select one framework, exact Databricks profile/model/API route and bounded model
settings explicitly. CrewAI belongs in a separately reviewed example environment;
an absent installation fails rather than substituting another framework.
"""

import argparse
import asyncio
import json
import math
import os
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from evalsurge.serving import AgentAnswer, AnswerUsage, InvocationContext, create_app

Framework = Literal["langgraph", "openai-agents", "crewai"]
ModelAPI = Literal["mlflow-responses", "openai-responses"]
POLICY = "Opened items cannot be refunded. Unopened items can be refunded within 30 days."
INSTRUCTIONS = f"Answer only using this synthetic refund policy: {POLICY}"


def validate_completion_metadata(document: Any) -> None:
    """Reject nonterminal provider metadata before a framework discards its status.

    Args:
        document: Parsed provider response; only its top-level status is inspected.

    Raises:
        ValueError: The response is not an object with status exactly completed.

    This is customer-owned validation, not a converter patch or an answer parser.
    A valid status alone is not evidence of a real model call or a valid answer.
    """
    if not isinstance(document, dict) or document.get("status") != "completed":
        raise ValueError("The selected provider did not complete the response")


async def response_completion_guard(response: Any) -> None:
    """Require terminal raw metadata on the owned nonstreaming Responses transport.

    Args:
        response: Actual HTTPX response delivered to the customer's async hook.

    Raises:
        ValueError: A successful response is malformed, oversized, streaming or
            not completed. Provider HTTP errors remain native SDK errors.

    Side Effects:
        Reads the provider JSON body before OpenAI Agents normalizes it; reading,
        parsing and validation remain inside model/handler/HTTP latency. No request,
        retry, answer, token count or trace is invented. This hook is only for the
        explicitly nonstreaming Responses route, not a streaming/TTFT adapter.
        The body-size check follows buffering and is not a hard memory quota.
    """
    if not 200 <= response.status_code < 300:
        return
    if "text/event-stream" in response.headers.get("content-type", "").lower():
        raise ValueError("The sample accepts nonstreaming Responses only")
    body = await response.aread()
    if len(body) > 2_000_000:
        raise ValueError("The provider response exceeds the sample body limit")
    try:
        document = json.loads(body)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise ValueError("The provider returned invalid completion metadata") from None
    validate_completion_metadata(document)


@dataclass(frozen=True)
class ModelSelection:
    """Operator-owned source selections and per-call bounds, outside workload JSON."""

    profile: str
    model: str
    api: ModelAPI
    expected_host: str
    max_output_tokens: int = 512
    timeout_seconds: float = 30

    def __post_init__(self) -> None:
        """Reject absent/unsafe selections before credentials, network or frameworks."""
        if not self.profile.strip() or not self.model.strip():
            raise ValueError("Select an exact profile and model")
        if self.api not in {"mlflow-responses", "openai-responses"}:
            raise ValueError("Select the advertised Responses API route explicitly")
        if (
            not self.expected_host.startswith("https://")
            or self.expected_host.endswith("/")
            or any(character in self.expected_host[8:] for character in "/?#@")
        ):
            raise ValueError("Select the exact HTTPS workspace origin")
        if not 1 <= self.max_output_tokens <= 512:
            raise ValueError("The example output-token cap is 1..512")
        if not math.isfinite(self.timeout_seconds) or not 0.1 <= self.timeout_seconds <= 30:
            raise ValueError("The example timeout is 0.1..30 seconds")

    @property
    def base_url(self) -> str:
        """Return the fixed selected gateway prefix; never infer native support."""
        suffix = "mlflow/v1" if self.api == "mlflow-responses" else "openai/v1"
        return f"{self.expected_host}/ai-gateway/{suffix}"


def validate_inputs(inputs: dict[str, Any]) -> str:
    """Accept this sample's declared input, rejecting extras before paid inference.

    Args:
        inputs: Unmodified helper input object; this sample supports query only.

    Returns:
        The original nonblank query of at most 512 characters.

    Raises:
        ValueError: Unsupported fields or an invalid query. This is an intentional
            pre-provider failure, not a successful agent/model test.
    """
    query = inputs.get("query")
    if set(inputs) != {"query"} or not isinstance(query, str) or not query.strip():
        raise ValueError("This sample requires exactly one nonblank query field")
    if len(query) > 512:
        raise ValueError("The sample query limit is 512 characters")
    return query


def completed_response(response: Any) -> tuple[str, int | None]:
    """Validate native Responses completion without flattening reasoning into text.

    Args:
        response: Actual OpenAI SDK response, not an arbitrary provider dictionary.

    Returns:
        Completed answer text and actual output tokens when supplied by the provider.

    Raises:
        ValueError: Failed/incomplete response, unfinished message, refusal, missing
            text or invalid usage. No retries, estimates or success-shaped fallback.
    """
    if response.status != "completed":
        raise ValueError("The selected provider did not complete the response")
    text = []
    for item in response.output:
        if item.type == "message":
            if item.status != "completed":
                raise ValueError("The provider returned an unfinished message")
            for content in item.content:
                if content.type != "output_text":
                    raise ValueError("The provider did not return an answer-text item")
                text.append(content.text)
        elif item.type != "reasoning":
            raise ValueError("The sample does not accept outstanding tool calls")
    answer = "".join(text)
    if not answer.strip():
        raise ValueError("The provider returned no completed answer")
    tokens = response.usage.output_tokens if response.usage is not None else None
    if tokens is not None and (type(tokens) is not int or tokens < 0):
        raise ValueError("The provider returned invalid output-token usage")
    return answer, tokens


class _GraphState(TypedDict):
    """One invocation's immutable prompt and completed answer; no persistent memory."""

    query: str
    answer: str
    output_tokens: int | None


def build_handler(
    framework: Framework, client: Any, selection: ModelSelection, *, http_client: Any
) -> Any:
    """Bind an actual framework to an existing real authenticated model client.

    Args:
        framework: Explicit example framework; no compatibility allowlist in EvalSurge.
        client: Caller-owned native AsyncOpenAI using SDK-refreshable authentication.
        selection: Frozen profile/model/route/output/deadline settings.
        http_client: Caller-owned native HTTPX transport with response_completion_guard
            installed. Local and App entrypoints must pass the same transport used
            by their native OpenAI client; a caller-supplied App client is not exempt.

    Returns:
        Async customer handler for create_app(), with request-local framework state.

    Raises:
        ImportError: Selected optional framework is absent; no installation/fallback.
        ValueError: Unknown framework or absent/mismatched raw completion guard.
            Runtime provider/framework failures propagate.

    Side Effects:
        Successful invocation performs actual model calls: one for LangGraph/OpenAI
        Agents, at most two for CrewAI's bounded native executor. No provider retries,
        tools, sessions, store, delegation or planner. These are real-model graph/agent
        examples, not tool-loop, conversational-memory or sustainable-capacity tests.
    """
    # Read-only client provenance check for the pinned OpenAI 3.x native client.
    # No framework/client converter is patched. Reverify this attribute on upgrades.
    if getattr(
        client, "_client", None
    ) is not http_client or response_completion_guard not in http_client.event_hooks.get(
        "response", []
    ):
        raise ValueError("Supply the native OpenAI client's guarded HTTPX transport")
    if framework not in {"langgraph", "openai-agents", "crewai"}:
        raise ValueError("Select one explicitly supported example framework")

    async def complete(messages: Any) -> tuple[str, int | None]:
        response = await client.responses.create(
            model=selection.model,
            input=messages,
            instructions=INSTRUCTIONS,
            max_output_tokens=selection.max_output_tokens,
            reasoning={"effort": "low"},
            store=False,
        )
        return completed_response(response)

    if framework == "langgraph":
        from langgraph.graph import END, START, StateGraph

        async def answer(state: _GraphState) -> dict[str, Any]:
            output, tokens = await complete(state["query"])
            return {"answer": output, "output_tokens": tokens}

        graph = (
            StateGraph(_GraphState)
            .add_node("answer", answer)
            .add_edge(START, "answer")
            .add_edge("answer", END)
            .compile()
        )

        async def invoke(query: str) -> tuple[str, int | None]:
            result = await graph.ainvoke({"query": query})
            return result["answer"], result["output_tokens"]

    elif framework == "openai-agents":
        from agents import (
            Agent,
            ModelRetrySettings,
            ModelSettings,
            OpenAIResponsesModel,
            RunConfig,
            Runner,
        )
        from openai.types.shared import Reasoning

        agent = Agent(
            name="Synthetic refund assistant",
            instructions=INSTRUCTIONS,
            model=OpenAIResponsesModel(model=selection.model, openai_client=client),
            model_settings=ModelSettings(
                max_tokens=selection.max_output_tokens,
                reasoning=Reasoning(effort="low"),
                store=False,
                preserve_raw_usage=True,
                retry=ModelRetrySettings(max_retries=0),
            ),
        )

        async def invoke(query: str) -> tuple[str, int | None]:
            result = await Runner.run(
                agent,
                input=query,
                max_turns=1,
                run_config=RunConfig(tracing_disabled=True, trace_include_sensitive_data=False),
            )
            output = result.final_output
            if not isinstance(output, str) or not output.strip():
                raise ValueError("The real agent returned no completed answer")
            # The native model rejects failed/incomplete Responses. Inspect retained
            # completed message items too, without treating reasoning as answer text.
            for response in result.raw_responses:
                for item in response.output:
                    if item.type == "message":
                        if item.status != "completed" or any(
                            content.type != "output_text" for content in item.content
                        ):
                            raise ValueError("The real agent returned an unfinished/refused answer")
                    elif item.type != "reasoning":
                        raise ValueError("The sample does not accept outstanding tool calls")
            usages = [
                response.raw_usage.get("output_tokens") if response.raw_usage else None
                for response in result.raw_responses
            ]
            if any(value is not None and (type(value) is not int or value < 0) for value in usages):
                raise ValueError("The provider returned invalid output-token usage")
            # Agents normalizes omitted usage to zero. Only provider-present raw
            # counts are evidence; absence stays absent, never a synthetic zero.
            return output, sum(usages) if usages and all(t is not None for t in usages) else None

    else:
        if os.getenv("CREWAI_DISABLE_TELEMETRY") != "true":
            raise ValueError(
                "Set CREWAI_DISABLE_TELEMETRY=true before importing the real CrewAI sample"
            )
        from crewai import Agent, BaseLLM, Crew, Task
        from pydantic import Field

        class ResponsesLLM(BaseLLM):
            """Native CrewAI custom LLM with bounded real Responses calls, no LiteLLM."""

            calls: int = 0
            output_tokens: list[int | None] = Field(default_factory=list)

            def __init__(self) -> None:
                super().__init__(model=selection.model)
                self.calls = 0
                self.output_tokens = []

            def call(self, *args: Any, **kwargs: Any) -> str:
                """Refuse thread-based/synchronous substitution for native async execution."""
                raise RuntimeError("This example requires native Crew.akickoff()")

            async def acall(self, messages: Any, **kwargs: Any) -> str:
                """Bound real calls even if the framework retries output-format parsing."""
                self.calls += 1
                if self.calls > 2:
                    raise RuntimeError("The request-local CrewAI model-call budget is exhausted")
                output, tokens = await complete(messages)
                self.output_tokens.append(tokens)
                return output

            def supports_function_calling(self) -> bool:
                """This sample has no tools; outstanding provider tool calls are invalid."""
                return False

            def supports_stop_words(self) -> bool:
                """The selected Responses transport does not send a stop-word parameter."""
                return False

        async def invoke(query: str) -> tuple[str, int | None]:
            model = ResponsesLLM()
            agent = Agent(
                role="Refund assistant",
                goal="Answer the synthetic refund question accurately",
                backstory=INSTRUCTIONS,
                llm=model,
                max_iter=1,
                max_retry_limit=0,
                allow_delegation=False,
                verbose=False,
            )
            task = Task(
                description=query,
                expected_output="One short answer using only the supplied policy",
                agent=agent,
            )
            result = await Crew(
                agents=[agent], tasks=[task], memory=False, planning=False, tracing=False
            ).akickoff()
            output = result.raw
            if not isinstance(output, str) or not output.strip():
                raise ValueError("The real crew returned no completed answer")
            tokens = model.output_tokens
            return output, sum(tokens) if tokens and all(t is not None for t in tokens) else None

    async def handler(inputs: dict[str, Any], context: InvocationContext) -> AgentAnswer:
        """Preserve this declared input contract and execute one request-local real agent.

        Correlation labels are available to customer-owned tracing but never used as
        identity. The sample has no persistent state: a session key is not memory.
        """
        del context
        query = validate_inputs(inputs)
        # Include native executor/transport work in one explicit customer deadline.
        async with asyncio.timeout(selection.timeout_seconds + 5):
            output, tokens = await invoke(query)
        return AgentAnswer(
            outputs=output,
            usage=AnswerUsage(output_tokens=tokens) if tokens is not None else None,
        )

    return handler


def create_real_app(framework: Framework, selection: ModelSelection) -> Any:
    """Own actual clients/frameworks in a loopback app lifespan, with no startup inference.

    Args:
        framework: Chosen real optional framework.
        selection: Exact caller-selected profile/workspace/model/route and bounds.

    Returns:
        FastAPI app serving the generic completed-answer contract at /invoke.

    Raises:
        RuntimeError: Resolved SDK host differs from the explicitly selected origin.
        ImportError: Selected framework or native client is missing.

    Side Effects:
        Startup resolves SDK authentication; requests incur bounded actual inference.
        Shutdown closes every owned client. No token is copied into requests/artifacts.
        Authentication is absent at the helper endpoint: bind loopback only unless the
        customer supplies their own authenticated gateway. No deployment occurs.
    """
    resources: dict[str, Any] = {}

    async def handler(inputs: dict[str, Any], context: InvocationContext) -> AgentAnswer:
        return await resources["handler"](inputs, context)

    app = create_app(handler, isolation="request")
    # Content-free live validation counters: a dispatch hook is an attempted
    # transport request, not proof of provider receipt or sustainable capacity.
    app.state.inference_evidence = {"outbound_attempts": 0, "completed_responses": 0}

    async def record_dispatch(request: Any) -> None:
        """Count actual client dispatches without retaining URLs, headers or content."""
        app.state.inference_evidence["outbound_attempts"] += 1

    async def record_completion(response: Any) -> None:
        """Count only successful responses already accepted by the raw status guard."""
        if 200 <= response.status_code < 300:
            app.state.inference_evidence["completed_responses"] += 1

    @asynccontextmanager
    async def lifespan(app: Any) -> AsyncIterator[None]:
        import httpx
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.core import Config
        from openai import AsyncOpenAI

        from benchmark_agents.providers import DatabricksAuth

        workspace = WorkspaceClient(
            config=Config(
                profile=selection.profile, http_timeout_seconds=20, retry_timeout_seconds=1
            )
        )
        if workspace.config.host.rstrip("/") != selection.expected_host:
            raise RuntimeError("The selected profile does not resolve to the approved workspace")
        async with (
            httpx.AsyncClient(
                auth=DatabricksAuth(workspace),
                trust_env=False,
                follow_redirects=False,
                timeout=selection.timeout_seconds,
                event_hooks={
                    "request": [record_dispatch],
                    "response": [response_completion_guard, record_completion],
                },
            ) as http,
            AsyncOpenAI(
                base_url=selection.base_url,
                api_key="sdk-auth",
                http_client=http,
                max_retries=0,
                timeout=selection.timeout_seconds,
            ) as client,
        ):
            resources["handler"] = build_handler(framework, client, selection, http_client=http)
            try:
                yield
            finally:
                resources.clear()

    app.router.lifespan_context = lifespan
    return app


def main(arguments: Sequence[str] | None = None) -> None:
    """Validate a no-network plan by default; require consent before starting real clients."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--framework", required=True, choices=("langgraph", "openai-agents", "crewai")
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--workspace-host", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api", required=True, choices=("mlflow-responses", "openai-responses"))
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--accept-paid-traffic", action="store_true")
    options = parser.parse_args(arguments)
    selection = ModelSelection(options.profile, options.model, options.api, options.workspace_host)
    if not 1024 <= options.port <= 65535:
        parser.error("--port must be 1024..65535")
    if not options.live:
        print(
            f"Dry run: {options.framework}, {options.api}, no inference; request-isolated /invoke"
        )
        return
    if not options.accept_paid_traffic:
        parser.error(
            "--live requires --accept-paid-traffic and separately bounded benchmark traffic"
        )
    import uvicorn

    uvicorn.run(create_real_app(options.framework, selection), host="127.0.0.1", port=options.port)


if __name__ == "__main__":
    main()
