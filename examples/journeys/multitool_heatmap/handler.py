"""Real serial LangGraph workflow over explicitly synthetic local tool data.

Three actual tool functions and a business-rule decision precede one real model
call. The model explains their evidence; it does not choose which tools to call.
Only the delayed case injects a two-second nonblocking wait inside the shipping
tool. The runner never imports this customer-owned module.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, TypedDict

from evalsurge.serving import AgentAnswer, AnswerUsage, InvocationContext
from examples.real_framework_handler import ModelSelection, completed_response


class State(TypedDict):
    """Raw request-isolated facts; no checkpointer, memory or shared session."""

    query: str
    order_id: str
    scenario: str
    order: dict[str, Any]
    policy: dict[str, Any]
    shipping: dict[str, Any]
    eligibility: dict[str, Any]
    outputs: str
    output_tokens: int | None


def validate_inputs(inputs: dict[str, Any]) -> None:
    """Reject undeclared demo inputs before tools or paid model dispatch.

    Args:
        inputs: Unmodified input object supplied by the HTTP helper.

    Raises:
        ValueError: An extra/missing field, unknown order/scenario or invalid query.
    """
    if (
        set(inputs) != {"query", "order_id", "scenario"}
        or inputs.get("order_id") != "DEMO-42"
        or not isinstance(inputs.get("scenario"), str)
        or inputs.get("scenario") not in {"normal", "delayed"}
        or not isinstance(inputs.get("query"), str)
        or not 1 <= len(inputs["query"]) <= 512
        or not inputs["query"].strip()
    ):
        raise ValueError("Unsupported demonstration input")


def build_handler(client: Any, selection: ModelSelection, directory: Path) -> Any:
    """Bind actual tools and an operator-owned native model client to a graph.

    Args:
        client: Actual AsyncOpenAI client with retries disabled by its owner.
        selection: Explicit model/profile/route and token/deadline settings.
        directory: This sample's directory containing synthetic JSON tool data.

    Returns:
        Async serving handler, executing three tools, one decision and one model
        dispatch for each successful request.

    Raises:
        ImportError: Actual LangGraph or MLflow is absent.
        ValueError: Invalid inputs or incomplete provider output.
        TimeoutError: The 35-second total handler budget expires.
        Exception: Actual tool/model failure, without fallback or retry.

    Side Effects:
        Construction imports native framework/tracing APIs but makes no calls.
        Invocation reads files off-loop, computes rules, writes native spans and
        makes one paid model call. Trace/export costs stay inside agent latency.
        No tracing destination, graph retries or model fixtures are installed here.
    """
    import mlflow
    from langgraph.graph import END, START, StateGraph

    def read_document(name: str) -> Any:
        return json.loads((directory / name).read_text(encoding="utf-8"))

    @mlflow.trace(name="lookup_order", span_type="TOOL")
    async def lookup_order(order_id: str) -> dict[str, Any]:
        """Read the sample's actual synthetic order document on an owned thread."""
        orders = await asyncio.to_thread(read_document, "orders.json")
        return orders[order_id]

    @mlflow.trace(name="lookup_return_policy", span_type="TOOL")
    async def lookup_return_policy(category: str) -> dict[str, Any]:
        """Read the actual synthetic category policy, not a canned tool answer."""
        policies = await asyncio.to_thread(read_document, "policies.json")
        return policies[category]

    @mlflow.trace(name="quote_return_shipping", span_type="TOOL")
    async def quote_return_shipping(weight_grams: int, scenario: str) -> dict[str, Any]:
        """Compute cents and inject a disclosed 2s wait only for delayed cases."""
        delay_ms = 2000 if scenario == "delayed" else 0
        span = mlflow.get_current_active_span()
        if span is not None:
            span.set_attribute("demo.injected_delay_ms", delay_ms)
        if delay_ms:
            await asyncio.sleep(delay_ms / 1000)
        return {
            "shipping_cents": 450 + ((weight_grams + 499) // 500) * 125,
            "currency": "USD",
            "controlled_delay_ms": delay_ms,
        }

    @mlflow.trace(name="check_return_eligibility", span_type="CHAIN")
    async def check_return_eligibility(
        order: dict[str, Any], policy: dict[str, Any], shipping: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply real deterministic rules before the model explains their result."""
        within_window = order["days_since_purchase"] <= policy["return_window_days"]
        condition_ok = not order["opened"] or policy["allow_opened"]
        eligible = within_window and condition_ok
        return {
            "eligible": eligible,
            "within_window": within_window,
            "condition_ok": condition_ok,
            "refund_cents_after_shipping": (
                max(0, order["price_cents"] - shipping["shipping_cents"]) if eligible else 0
            ),
        }

    async def order_node(state: State) -> dict[str, Any]:
        return {"order": await lookup_order(state["order_id"])}

    async def policy_node(state: State) -> dict[str, Any]:
        return {"policy": await lookup_return_policy(state["order"]["category"])}

    async def shipping_node(state: State) -> dict[str, Any]:
        return {
            "shipping": await quote_return_shipping(
                state["order"]["weight_grams"], state["scenario"]
            )
        }

    async def decision_node(state: State) -> dict[str, Any]:
        return {
            "eligibility": await check_return_eligibility(
                state["order"], state["policy"], state["shipping"]
            )
        }

    async def answer_node(state: State) -> dict[str, Any]:
        evidence = {key: state[key] for key in ("order", "policy", "shipping", "eligibility")}
        response = await client.responses.create(
            model=selection.model,
            instructions=(
                "You are a returns assistant using synthetic demonstration data. "
                "Answer using only the supplied tool evidence. Explain eligibility, "
                "return window, shipping fee and net refund in USD. Keep the answer concise."
            ),
            input=state["query"] + "\nTool evidence:\n" + json.dumps(evidence),
            max_output_tokens=selection.max_output_tokens,
            **(
                {"reasoning": {"effort": "low"}}
                if selection.model == "system.ai.gpt-oss-120b"
                else {}
            ),
            store=False,
        )
        output, tokens = completed_response(response)
        return {"outputs": output, "output_tokens": tokens}

    graph = (
        StateGraph(State)
        .add_node("order", order_node)
        .add_node("policy", policy_node)
        .add_node("shipping", shipping_node)
        .add_node("decision", decision_node)
        .add_node("answer", answer_node)
        .add_edge(START, "order")
        .add_edge("order", "policy")
        .add_edge("policy", "shipping")
        .add_edge("shipping", "decision")
        .add_edge("decision", "answer")
        .add_edge("answer", END)
        .compile()
    )

    async def invoke(inputs: dict[str, Any], context: InvocationContext) -> AgentAnswer:
        """Validate and execute one actual graph with a 35-second handler deadline."""
        validate_inputs(inputs)
        async with asyncio.timeout(35):
            result = await graph.ainvoke(inputs)
        return AgentAnswer(
            outputs=result["outputs"],
            usage=(
                AnswerUsage(output_tokens=result["output_tokens"])
                if result["output_tokens"] is not None
                else None
            ),
        )

    return invoke
