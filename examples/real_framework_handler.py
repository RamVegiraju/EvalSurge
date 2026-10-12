"""Customer-owned real framework handlers, isolated from EvalSurge dependencies.

Importing this module uses the standard library only: optional frameworks and
Pydantic are loaded solely when the operator calls build_handler(). No package
installation, profile resolution, network request or inference occurs at import.
Deploy or copy this module explicitly alongside its hosting entrypoint; it is not
a dynamic decoder/plugin and the load runner never imports customer agent code.
"""

import asyncio
import json
import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, TypedDict
from urllib.parse import urlsplit


@dataclass(frozen=True)
class CompletedAnswer:
    """Completed text and optional provider-present output tokens, without dependencies.

    Values are validated without normalization before any serving conversion.
    The two-million-byte answer bound matches the generic HTTP response contract;
    it is not a token estimate, model-call proof, trace or hard allocation quota.
    """

    outputs: str
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        """Reject blank/invalid Unicode/oversized output or invalid token evidence."""
        if not isinstance(self.outputs, str) or not self.outputs.strip():
            raise ValueError("The real agent returned no completed answer")
        try:
            encoded = self.outputs.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Completed answer must be valid UTF-8") from None
        if len(encoded) > 2_000_000:
            raise ValueError("Completed answer exceeds the response byte limit")
        if self.output_tokens is not None and (
            type(self.output_tokens) is not int or self.output_tokens < 0
        ):
            raise ValueError("The provider returned invalid output-token usage")


class ProviderInvocationFailed(RuntimeError):
    """Safe terminal provider failure; never an answer or retryable provider chain."""


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
        if (
            not isinstance(self.profile, str)
            or not isinstance(self.model, str)
            or not self.profile.strip()
            or not self.model.strip()
        ):
            raise ValueError("Select an exact profile and model")
        if not isinstance(self.api, str) or self.api not in {
            "mlflow-responses",
            "openai-responses",
        }:
            raise ValueError("Select the advertised Responses API route explicitly")
        valid_host = False
        if isinstance(self.expected_host, str) and not any(
            character.isspace() or ord(character) < 32 or ord(character) == 127 or character == "\\"
            for character in self.expected_host
        ):
            try:
                parsed = urlsplit(self.expected_host)
                valid_host = (
                    parsed.scheme == "https"
                    and parsed.hostname is not None
                    and parsed.username is None
                    and parsed.password is None
                    and parsed.netloc == parsed.hostname
                    and not parsed.path
                    and not parsed.query
                    and not parsed.fragment
                    and self.expected_host == f"https://{parsed.hostname}"
                )
            except ValueError:
                valid_host = False
        if not valid_host:
            raise ValueError("Select the exact HTTPS workspace origin without a port or path")
        if type(self.max_output_tokens) is not int or not 1 <= self.max_output_tokens <= 512:
            raise ValueError("The example output-token cap is 1..512")
        if (
            type(self.timeout_seconds) not in {int, float}
            or not math.isfinite(self.timeout_seconds)
            or not 0.1 <= self.timeout_seconds <= 30
        ):
            raise ValueError("The example timeout is 0.1..30 seconds")

    @property
    def base_url(self) -> str:
        """Return the fixed selected gateway prefix; never infer native support."""
        suffix = "mlflow/v1" if self.api == "mlflow-responses" else "openai/v1"
        return f"{self.expected_host}/ai-gateway/{suffix}"


def validate_model_request(request: Any, selection: ModelSelection) -> None:
    """Bind SDK authentication to the exact selected nonstreaming Responses route.

    Args:
        request: Native transport request, inspected before obtaining credential headers.
        selection: Exact operator-owned workspace origin and Responses API prefix.

    Raises:
        ValueError: Method/URL differs, including a query, alternate route or origin.

    This performs no authentication, network request or model invocation. Native
    HTTP clients do not follow redirects, and endpoints accept no target URL.
    """
    if request.method != "POST" or str(request.url) != f"{selection.base_url}/responses":
        raise ValueError("SDK credentials require the exact selected Responses destination")


async def owned_thread(function: Callable[..., Any], *args: Any) -> Any:
    """Offload SDK setup/refresh without abandoning work or losing cancellation.

    Args:
        function: Customer-owned synchronous operation; it may perform network I/O.
        args: Arguments for that exact operation, never persisted or logged here.

    Returns:
        Operation result after ownership ends, when cancellation was not requested.

    Raises:
        asyncio.CancelledError: Requested cancellation, after observing native work.
        Exception: The native failure when cancellation was not requested.

    Side Effects:
        Uses an owned native thread and keeps the event loop available. SDK OIDC
        discovery has separate transport/retry defaults: this is not a hard auth
        deadline. Repeated cancellation is retained and takes precedence over a
        later native failure, which is observed without exposing its contents.
        Cleanup can wait for native work; no zero-observer-overhead claim is made.
    """
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except BaseException:
            if not cancelled:
                raise
            break
    if cancelled:
        if not task.cancelled():
            task.exception()
        raise asyncio.CancelledError
    return task.result()


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
    try:
        query.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("The sample query must be valid UTF-8") from None
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
        Async customer handler returning CompletedAnswer, with request-local framework state.

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
    # Read-only native client provenance check; verify the exact installed version.
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
                """Bound actual calls and preserve terminal provider failure.

                Inspected CrewAI source wraps custom async calls in native throttle
                retries independently of executor max_retry_limit. Raise a safe
                terminal exception outside the catch block so no retryable cause
                or context survives; no error text becomes a completed answer.
                Exact selected CrewAI versions still need installed/live validation.
                """
                self.calls += 1
                if self.calls > 2:
                    raise RuntimeError("The request-local CrewAI model-call budget is exhausted")
                # Native CrewAI can retry throttling exceptions even when executor
                # retries are disabled. Retain failure without a retryable chain.
                failed = False
                try:
                    output, tokens = await complete(messages)
                except Exception:  # noqa: BLE001 - preserve failure, omit provider content
                    failed = True
                if failed:
                    raise ProviderInvocationFailed("Selected provider invocation failed")
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

    async def handler(inputs: dict[str, Any], context: Any = None) -> CompletedAnswer:
        """Preserve this declared input contract and execute one request-local real agent.

        Correlation labels are available to customer-owned tracing but never used as
        identity. The sample has no persistent state: a session key is not memory.
        """
        del context
        query = validate_inputs(inputs)
        # Include native executor/transport work in one explicit customer deadline.
        async with asyncio.timeout(selection.timeout_seconds + 5):
            output, tokens = await invoke(query)
        return CompletedAnswer(outputs=output, output_tokens=tokens)

    return handler
