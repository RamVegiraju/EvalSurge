"""Real framework runners with synthetic tools, isolated memory, and MLflow tracing.

Run with ``uv run --extra agents python -m examples.framework_agent``. By default
only the provider HTTP response is deterministic; LangGraph, OpenAI Agents,
streaming, memory, and tracing are real. Set EVALSURGE_DEMO_LIVE=true to call the
operator-selected Databricks model. Tools contain synthetic policy data only.
"""

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, TypedDict
from uuid import uuid4

import httpx
import mlflow
import uvicorn
from agents import (
    Agent,
    ModelSettings,
    OpenAIChatCompletionsModel,
    RunConfig,
    Runner,
    SQLiteSession,
    function_tool,
)
from agents.items import TResponseInputItem, TResponseStreamEvent
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from openai import AsyncOpenAI

from benchmark_agents.models import AgentManifest, Capability
from benchmark_agents.providers import DEFAULT_FM_ENDPOINT, DatabricksAuth, workspace_client

POLICY = "Opened items cannot be refunded. Unopened items can be refunded within 30 days."


class FixtureStream(httpx.AsyncByteStream):
    """A timed provider SSE fixture; real framework clients parse every chunk."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        """Retain synthetic Chat Completions chunks for one model call."""
        self.events = events

    async def __aiter__(self) -> AsyncIterator[bytes]:
        """Yield provider events with visible streaming gaps, then a terminal marker."""
        for event in self.events:
            await asyncio.sleep(0.002)
            yield f"data: {json.dumps(event)}\n\n".encode()
        yield b"data: [DONE]\n\n"


def fixture_provider(request: httpx.Request) -> httpx.Response:
    """Respond at the provider boundary without replacing either framework runtime."""
    body = json.loads(request.content)
    messages = body["messages"]
    tool_needed = bool(body.get("tools")) and not any(
        message.get("role") == "tool" for message in messages
    )
    identity = str(uuid4())
    base = {"id": identity, "object": "chat.completion.chunk", "created": 1, "model": "fixture"}
    deltas = (
        [
            {"role": "assistant"},
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call_" + identity,
                        "type": "function",
                        "function": {"name": "policy_db", "arguments": "{}"},
                    }
                ]
            },
        ]
        if tool_needed
        else [
            {"role": "assistant"},
            {"content": "Opened items "},
            {"content": "cannot be refunded."},
        ]
    )
    events = [{**base, "choices": [{"index": 0, "delta": delta}]} for delta in deltas]
    events.append(
        {
            **base,
            "choices": [
                {"index": 0, "delta": {}, "finish_reason": "tool_calls" if tool_needed else "stop"}
            ],
        }
    )
    if body.get("stream_options", {}).get("include_usage"):
        events.append(
            {
                **base,
                "choices": [],
                "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
            }
        )
    return httpx.Response(
        200, headers={"content-type": "text/event-stream"}, stream=FixtureStream(events)
    )


@mlflow.trace(span_type="TOOL")
async def policy_db() -> str:
    """Read a synthetic refund policy; the small delay represents a read-only dependency."""
    await asyncio.sleep(0.025)
    return POLICY


@mlflow.trace(span_type="RETRIEVER")
async def retrieve_faq() -> list[dict[str, Any]]:
    """Return synthetic retrieved content in MLflow's document-compatible shape."""
    await asyncio.sleep(0.01)
    return [
        {"page_content": "Contact support for help with returns.", "metadata": {"source": "demo"}}
    ]


class TracedCheckpointer(InMemorySaver):
    """Use real LangGraph checkpoints and expose memory I/O as dedicated spans."""

    async def aget_tuple(self, config: Any) -> Any:
        """Read one isolated thread checkpoint while recording memory occupancy."""
        with mlflow.start_span("memory.read", attributes={"evalsurge.category": "memory"}) as span:
            value = await super().aget_tuple(config)
            span.set_outputs(value.checkpoint["channel_values"] if value else {})
            return value

    async def aput(self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any) -> Any:
        """Persist actual graph state under this request's independent thread identifier."""
        with mlflow.start_span("memory.write", attributes={"evalsurge.category": "memory"}) as span:
            span.set_inputs(checkpoint["channel_values"])
            return await super().aput(config, checkpoint, metadata, new_versions)


class TracedSession(SQLiteSession):
    """Real OpenAI Agents SQLite memory scoped to one request, with traced reads/writes."""

    async def get_items(self, limit: int | None = None) -> Any:
        """Load prior conversation items from this isolated in-memory database."""
        with mlflow.start_span("memory.read", attributes={"evalsurge.category": "memory"}) as span:
            items = await super().get_items(limit)
            span.set_outputs(items)
            return items

    async def add_items(self, items: Any) -> None:
        """Write the actual conversation and tool results after the runner finishes."""
        with mlflow.start_span("memory.write", attributes={"evalsurge.category": "memory"}) as span:
            span.set_inputs(items)
            await super().add_items(items)


class TracedChatModel(OpenAIChatCompletionsModel):
    """Trace the public SDK stream hook without reconstructing provider completion IDs."""

    async def stream_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        *args: Any,
        **kwargs: Any,
    ) -> AsyncIterator[TResponseStreamEvent]:
        """Keep one model span open until the real SDK stream drains or fails.

        Args:
            system_instructions: Agent-owned instructions forwarded unchanged.
            input: Actual conversation and tool results sent to the model.
            *args: Remaining positional SDK stream parameters, forwarded unchanged.
            **kwargs: Remaining SDK stream parameters, not exported as trace inputs.

        Yields:
            Unmodified SDK stream events, including the actual completed response.

        Provider errors propagate unchanged; the span context records failure.
        Only captured output/usage are recorded, never an invented provider ID.
        Native SDK tracing is disabled by the demo Runner to avoid duplicate spans
        and the SDK's external trace exporter.
        """
        with mlflow.start_span("model.stream", span_type="CHAT_MODEL") as span:
            span.set_inputs({"instructions": system_instructions, "messages": input})
            span.set_attribute("model", str(self.model))
            async for event in super().stream_response(system_instructions, input, *args, **kwargs):
                if event.type == "response.completed":
                    span.set_outputs(
                        event.response.model_dump(mode="json", include={"output", "usage"})
                    )
                yield event


class GraphState(TypedDict):
    """Graph-owned messages and retrieved context, checkpointed during invocation."""

    messages: Annotated[list[BaseMessage], add_messages]
    context: str


def build_graph(model: Any, checkpointer: TracedCheckpointer) -> Any:
    """Compile a real checkpointed graph with tool/retrieval and streamed model nodes."""

    async def gather_context(state: GraphState) -> dict[str, Any]:
        """Read independent synthetic tool and retrieval dependencies in parallel."""
        policy, documents = await asyncio.gather(policy_db(), retrieve_faq())
        return {"context": policy + "\n" + documents[0]["page_content"]}

    async def answer(state: GraphState) -> dict[str, Any]:
        """Stream real LangChain model chunks through LangGraph's custom event channel."""
        writer = get_stream_writer()
        combined = None
        async for chunk in model.astream(
            [
                SystemMessage(content=f"Answer using only this policy: {state['context']}"),
                *state["messages"],
            ]
        ):
            combined = chunk if combined is None else combined + chunk
            if isinstance(chunk.content, str) and chunk.content:
                writer({"text": chunk.content})
        usage = combined.usage_metadata if combined is not None else None
        writer({"output_tokens": usage.get("output_tokens") if usage else None})
        return {"messages": [AIMessage(content=combined.content if combined is not None else "")]}

    graph = StateGraph(GraphState)
    graph.add_node("gather_context", gather_context)
    graph.add_node("answer", answer)
    graph.add_edge(START, "gather_context")
    graph.add_edge("gather_context", "answer")
    graph.add_edge("answer", END)
    return graph.compile(checkpointer=checkpointer)


def manifest(framework: str) -> AgentManifest:
    """Disclose demo capabilities without credentials, source code, or inferred references."""
    return AgentManifest(
        name=f"Refund assistant · {framework}",
        framework=framework,
        description="Answer synthetic refund questions using a read-only policy tool.",
        capabilities=[
            Capability(
                name="policy_db", kind="tool", description="Read authoritative refund policy"
            ),
            Capability(name="conversation", kind="memory", description="Request-isolated memory"),
            *(
                [
                    Capability(
                        name="retrieve_faq", kind="retrieval", description="Retrieve support FAQ"
                    )
                ]
                if framework == "langgraph"
                else []
            ),
        ],
    )


def demo_chat_options(
    provider: str,
    model: str,
    *,
    tools: bool,
    token_parameter: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    """Resolve bounded demo settings without inferring unknown model capabilities.

    Args:
        provider: Transport identity, not inferred from a model-name prefix.
        model: Exact endpoint name; the verified Databricks mini preset is narrow.
        tools: Whether function tools are sent in this Chat Completions request.
        token_parameter: Explicit max_tokens or max_completion_tokens override.
        reasoning_effort: Explicit reasoning override; None omits it for unknown models.

    Returns:
        An OpenAI SDK extra_body with one 1,024-token cap and, only for a known
        preset or explicit override, reasoning effort. No requests or retries occur.

    Raises:
        ValueError: Invalid overrides or a verified incompatible tool/reasoning setting.

    Presets describe the observed provider contract, not immutable hosted revisions.
    These settings belong to this synthetic agent, never the benchmark load payload.
    """
    known_mini = provider == "databricks" and model == DEFAULT_FM_ENDPOINT
    token_parameter = token_parameter or ("max_completion_tokens" if known_mini else "max_tokens")
    if token_parameter not in {"max_tokens", "max_completion_tokens"}:
        raise ValueError("Demo token parameter must be max_tokens or max_completion_tokens")
    if known_mini and token_parameter != "max_completion_tokens":
        raise ValueError("The verified Databricks mini preset requires max_completion_tokens")
    effort = reasoning_effort
    if effort is None and known_mini:
        effort = "none" if tools else "low"
    if effort is not None and effort not in {"none", "minimal", "low", "medium", "high", "xhigh"}:
        raise ValueError("Unsupported demo reasoning effort")
    if known_mini and tools and effort != "none":
        raise ValueError("Databricks mini function tools require reasoning_effort='none'")
    return {
        token_parameter: 1024,
        **({"reasoning_effort": effort} if effort is not None else {}),
    }


def demo_request_usage(value: str | None = None) -> bool:
    """Validate the operator's demo-only streamed-usage setting without inference.

    Args:
        value: Exact true/false environment value; None preserves default-on usage.

    Returns:
        Whether the synthetic model clients should request streamed token usage.
        Disabling this extension does not disable tracing or estimate missing tokens.

    Raises:
        ValueError: The explicit value is not true or false.
    """
    if value not in {None, "true", "false"}:
        raise ValueError("EVALSURGE_DEMO_REQUEST_USAGE must be true or false")
    return value != "false"


def create_app(live: bool = False) -> FastAPI:
    """Create localhost demo endpoints; initialize owned provider and tracing resources in lifespan."""
    resources: dict[str, Any] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Configure real OSS integrations and close clients after all requests drain."""
        uri = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///artifacts/demo-mlflow.db")
        Path("artifacts").mkdir(exist_ok=True)
        mlflow.set_tracking_uri(uri)
        experiment = (
            mlflow.set_experiment(experiment_id=os.getenv("MLFLOW_EXPERIMENT_ID"))
            if os.getenv("MLFLOW_EXPERIMENT_ID")
            else mlflow.set_experiment("evalsurge-framework-demo")
        )
        resources["experiment_id"] = experiment.experiment_id
        mlflow.langchain.autolog()
        mlflow.openai.autolog(disable=True)
        if live:
            workspace = workspace_client()
            base_url = workspace.config.host.rstrip("/") + "/serving-endpoints"
            model_name = os.getenv("EVALSURGE_DEMO_MODEL", DEFAULT_FM_ENDPOINT)
        else:
            base_url, model_name = "http://fixture", "fixture"
        options = {
            "provider": "databricks" if live else "fixture",
            "model": model_name,
            "token_parameter": os.getenv("EVALSURGE_DEMO_TOKEN_PARAMETER"),
            "reasoning_effort": os.getenv("EVALSURGE_DEMO_REASONING_EFFORT"),
        }
        graph_options = demo_chat_options(**options, tools=False)
        agent_options = demo_chat_options(**options, tools=True)
        request_usage = demo_request_usage(os.getenv("EVALSURGE_DEMO_REQUEST_USAGE"))
        http = (
            httpx.AsyncClient(auth=DatabricksAuth(workspace), trust_env=False, timeout=30)
            if live
            else httpx.AsyncClient(transport=httpx.MockTransport(fixture_provider))
        )
        client = AsyncOpenAI(
            base_url=base_url, api_key="sdk-auth", http_client=http, max_retries=0, timeout=30
        )
        langchain_model = ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key="sdk-auth",
            http_async_client=http,
            max_retries=0,
            timeout=30,
            extra_body=graph_options,
            use_responses_api=False,
            stream_usage=request_usage,
        )
        resources["checkpointer"] = TracedCheckpointer()
        resources["graph"] = build_graph(langchain_model, resources["checkpointer"])
        resources["agent"] = Agent(
            name="Refund assistant",
            instructions="Always call policy_db before answering. Answer only using its refund policy.",
            model=TracedChatModel(model=model_name, openai_client=client),
            tools=[function_tool(policy_db)],
            model_settings=ModelSettings(
                extra_body=agent_options, include_usage=True if request_usage else None
            ),
        )
        try:
            yield
        finally:
            try:
                await asyncio.to_thread(mlflow.flush_trace_async_logging)
            finally:
                await client.close()

    app = FastAPI(lifespan=lifespan, title="Synthetic instrumented framework demos")

    @app.get("/manifest/{framework}")
    async def get_manifest(framework: str) -> dict[str, Any]:
        """Return explicit opt-in setup context and the operator's trace experiment scope."""
        if framework not in {"langgraph", "openai-agents"}:
            raise HTTPException(404, "Unknown framework")
        return {
            "agent_manifest": manifest(framework).model_dump(),
            "trace_experiment_id": resources["experiment_id"],
        }

    @app.post("/{framework}/chat")
    async def chat(framework: str, request: Request) -> StreamingResponse:
        """Serve actual framework streaming with per-request correlation and isolated memory."""
        if framework not in {"langgraph", "openai-agents"}:
            raise HTTPException(404, "Unknown framework")
        body = await request.json()
        if not body.get("messages"):
            raise HTTPException(422, "messages are required")
        run_id = request.headers.get("X-Benchmark-Run-ID", "interactive")
        request_id = request.headers.get("X-Benchmark-Request-ID", str(uuid4()))
        if len(run_id) > 128 or len(request_id) > 128:
            raise HTTPException(422, "Correlation IDs are too long")

        async def stream() -> AsyncIterator[str]:
            """Keep the root trace alive through final output, tool execution, and memory writes."""
            output, tokens = "", None
            try:
                with mlflow.start_span("hosted_agent", span_type="AGENT") as root:
                    mlflow.update_current_trace(
                        metadata={"evalsurge.run_id": run_id, "evalsurge.request_id": request_id}
                    )
                    root.set_inputs({"messages": body["messages"]})
                    yield f"data: {json.dumps({'type': 'evalsurge.trace', 'trace_id': root.trace_id})}\n\n"
                    if framework == "langgraph":
                        try:
                            async for event in resources["graph"].astream(
                                {"messages": body["messages"]},
                                config={"configurable": {"thread_id": request_id}},
                                stream_mode="custom",
                            ):
                                if "text" in event:
                                    output += event["text"]
                                    yield text_event(event["text"])
                                if "output_tokens" in event:
                                    tokens = event["output_tokens"]
                        finally:
                            await resources["checkpointer"].adelete_thread(request_id)
                    else:
                        session = TracedSession(request_id)
                        result = None
                        reported_tokens: list[int | None] = []
                        try:
                            result = Runner.run_streamed(
                                resources["agent"],
                                input=body["messages"],
                                max_turns=3,
                                session=session,
                                run_config=RunConfig(
                                    tracing_disabled=True, trace_include_sensitive_data=False
                                ),
                            )
                            async for event in result.stream_events():
                                if (
                                    event.type == "raw_response_event"
                                    and getattr(event.data, "type", None) == "response.completed"
                                ):
                                    usage = event.data.response.usage
                                    reported_tokens.append(
                                        usage.output_tokens if usage is not None else None
                                    )
                                if (
                                    event.type == "raw_response_event"
                                    and getattr(event.data, "type", None)
                                    == "response.output_text.delta"
                                ):
                                    output += event.data.delta
                                    yield text_event(event.data.delta)
                            if reported_tokens and all(
                                count is not None for count in reported_tokens
                            ):
                                tokens = sum(
                                    count for count in reported_tokens if count is not None
                                )
                        finally:
                            if result is not None and not result.is_complete:
                                result.cancel()
                            session.close()
                    root.set_outputs(output)
                yield f"data: {json.dumps({'usage': {'completion_tokens': tokens}})}\n\n"
                yield 'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
                yield "data: [DONE]\n\n"
            except Exception:
                logging.exception("Synthetic framework demo failed")
                yield 'data: {"error":{"type":"agent_failed"}}\n\n'

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app


def text_event(text: str) -> str:
    """Encode an OpenAI-compatible answer delta, without confusing it with metadata TTFT."""
    return f"data: {json.dumps({'choices': [{'delta': {'content': text}}]})}\n\n"


if __name__ == "__main__":
    uvicorn.run(
        create_app(live=os.getenv("EVALSURGE_DEMO_LIVE", "false").lower() == "true"),
        host="127.0.0.1",
        port=9001,
        proxy_headers=False,
    )
