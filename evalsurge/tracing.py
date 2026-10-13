"""Optional agent-side MLflow correlation, independent of benchmark evaluation.

Importing this module does not configure MLflow, resolve credentials, create an
experiment, or call a model. The operator owns instrumentation, trace storage,
sampling and export. The runner never imports or executes customer agent code.
"""

import re
from typing import Any

from .serving import AgentAnswer, AgentHandler, InvocationContext, _response_trace


def traced_handler(handler: AgentHandler, *, experiment_id: str) -> AgentHandler:
    """Correlate one actual handler invocation with its native MLflow trace.

    Args:
        handler: Customer-owned async handler, called exactly once per invocation.
        experiment_id: Exact existing local/explicit legacy experiment. Configure
            its tracking URI/auth before invoking this wrapper. No experiment is
            created or discovered here. Databricks governed instrumentation must
            use the agent's native setup; this helper refuses Databricks URIs.

    Returns:
        Async handler for ``evalsurge.serving.create_app``. Its real boundary span
        contains actual inputs/outputs and benchmark run/request metadata; the
        returned AgentAnswer carries that span's actual trace ID.

    Raises:
        ValueError: The handler or bounded experiment ID is invalid.
        RuntimeError: Tracing is disabled/dropped, the destination is Databricks,
            or the answer claims another trace ID. Customer exceptions propagate
            to the serving error boundary.

    Side Effects:
        Invocation records protected raw content in the configured tracking store,
        in addition to the customer's own model/tool work. Export and framework
        instrumentation overhead are part of observed agent response latency;
        this helper never flushes or subtracts them. It enables no autologging.
        A boundary-only span proves mapping/duration, not internal bottlenecks.
        An existing parent trace retains its destination; configure it in the same
        authorized experiment or readiness will reject it. Context propagation to
        additional threads is the customer's instrumentation responsibility.
    """
    if (
        not callable(handler)
        or not isinstance(experiment_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", experiment_id)
    ):
        raise ValueError("Supply an async handler and an exact existing experiment ID")

    async def invoke(inputs: dict[str, Any], context: InvocationContext) -> AgentAnswer:
        """Own one real boundary span; do not retry or substitute handler execution."""
        import mlflow
        from mlflow.entities.trace_location import MlflowExperimentLocation
        from mlflow.utils.uri import is_databricks_uri

        if is_databricks_uri(mlflow.get_tracking_uri()):
            raise RuntimeError(
                "Use native governed Databricks instrumentation; this experiment-only "
                "helper cannot verify UC scope and will not select legacy storage"
            )

        with mlflow.start_span(
            "hosted_agent",
            span_type="AGENT",
            trace_destination=MlflowExperimentLocation(experiment_id),
        ) as span:
            if not span.trace_id or span.span_id is None:
                raise RuntimeError("Tracing must be enabled and sampled for this invocation")
            if capture := _response_trace.get():
                capture.trace_id = span.trace_id
            metadata = {"evalsurge.request_id": context.request_id}
            if context.run_id is not None:
                metadata["evalsurge.run_id"] = context.run_id
            mlflow.update_current_trace(metadata=metadata)
            span.set_inputs(inputs)
            answer = await handler(inputs, context)
            if not isinstance(answer, AgentAnswer):
                raise TypeError("The traced handler must return AgentAnswer")
            if answer.trace_id is not None and answer.trace_id != span.trace_id:
                raise RuntimeError("The answer trace ID differs from its correlated boundary")
            span.set_outputs(answer.model_dump(exclude={"trace_id"}, exclude_none=True))
            return answer.model_copy(update={"trace_id": span.trace_id})

    return invoke
