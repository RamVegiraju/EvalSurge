"""Fixed hosted-agent wire contracts, independent of model providers and load engines."""

import json
import time
from dataclasses import dataclass
from typing import Any, Literal, NoReturn, Protocol
from uuid import UUID, uuid4

from requests import Response
from requests.exceptions import ContentDecodingError

from .models import Sample, Target
from .streaming import consume

JSON_RESPONSE_LIMIT = 2_000_000


class InvalidResponse(ValueError):
    """A JSON contract failure carrying fixed guidance, never target response content."""


class ResponseAdapter(Protocol):
    """Encode cases and decode caller-owned responses without opening connections."""

    def encode(self, target: Target, sample: Sample) -> dict[str, Any]:
        """Return the wire body without mutating the target or workload case."""
        ...

    def decode(self, response: Response, row: dict[str, Any], sent: float) -> None:
        """Read a successful response into its attempt row; sent is a monotonic clock."""
        ...


@dataclass(frozen=True)
class SSEAdapter:
    """Existing OpenAI Chat and MLflow agent-server single-line SSE contracts."""

    name: Literal["openai-chat", "mlflow-agent-server"]

    def encode(self, target: Target, sample: Sample) -> dict[str, Any]:
        """Build the existing streaming envelope without provider feature injection.

        Args:
            target: Model name, SSE protocol, and optional usage request setting.
            sample: Workload inputs with query or messages; messages take precedence.

        Returns:
            A fresh OpenAI Chat or MLflow agent-server streaming request body.
            Additional inputs remain evaluation metadata, not target fields.

        Raises:
            ValueError: Query is absent or messages are not nonempty role-bearing objects.
        """
        messages = sample.inputs.get("messages")
        if messages is None:
            query = sample.inputs.get("query")
            if not isinstance(query, str) or not query:
                raise ValueError("Each sample needs inputs.query or inputs.messages.")
            messages = [{"role": "user", "content": query}]
        if (
            not isinstance(messages, list)
            or not messages
            or any(
                not isinstance(message, dict) or not isinstance(message.get("role"), str)
                for message in messages
            )
        ):
            raise ValueError("inputs.messages must be a nonempty array of objects with a role")
        if self.name == "mlflow-agent-server":
            return {"input": messages, "stream": True}
        body = {"model": target.model, "messages": messages, "stream": True}
        if target.request_usage:
            body["stream_options"] = {"include_usage": True}
        return body

    def decode(self, response: Response, row: dict[str, Any], sent: float) -> None:
        """Consume the existing SSE semantics while preserving answer-text timing.

        Args:
            response: Caller-owned streamed 2xx response; this method does not close it.
            row: Mutable attempt evidence, including initially unknown timing fields.
            sent: Monotonic HTTP dispatch time in seconds.

        Raises:
            ValueError: Content type, events, answer size, or completion is invalid.
            requests.RequestException: The underlying response transport fails.

        Timing fields use milliseconds since dispatch. Partial SSE evidence is retained
        on failure, as before; no redirects, retries, or new HTTP calls are performed.
        """
        header_id = response.headers.get("X-MLflow-Trace-ID")
        row["trace_id"] = _trace_id(header_id) if header_id is not None else None
        if "text/event-stream" not in response.headers.get("content-type", ""):
            raise ValueError("Expected text/event-stream response")
        response.encoding = "utf-8"
        terminal = False
        # Requests' default line buffer can delay small SSE deltas.
        for line in response.iter_lines(chunk_size=1, decode_unicode=True):
            if not line.startswith("data:") or not line[5:].strip():
                continue
            data = line[5:].strip()
            completed = consume(row, data, (time.perf_counter() - sent) * 1000)
            terminal = terminal or completed
            if len(row["outputs"]) > 2_000_000:
                raise ValueError("Response exceeded the two-million-character limit")
            # Native MLflow emits its trace-id event after the agent's completion
            # event, then [DONE]. Retain that evidence without reconnecting/polling.
            if completed and (self.name != "mlflow-agent-server" or data == "[DONE]"):
                break
        if not terminal and row.get("completion_reason") != "stop":
            raise ValueError("Stream ended without a terminal event")
        if not row["outputs"].strip():
            raise ValueError("Agent produced no answer text")


def _trace_id(value: Any) -> str:
    """Validate a present trace identifier without exposing its value in errors.

    Args:
        value: Header or JSON trace identifier, not a tracing destination.

    Returns:
        The unchanged nonblank string, bounded to 128 characters.

    Raises:
        InvalidResponse: The identifier is absent, blank, wrong-type, or oversized.
    """
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise InvalidResponse("Invalid trace identifier in JSON response")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise InvalidResponse("Invalid trace identifier in JSON response") from None
    return value


def _reject_constant(value: str) -> NoReturn:
    """Reject non-JSON numeric literals without echoing target content."""
    raise InvalidResponse("Nonstandard numeric literal in JSON response")


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Decode an object while rejecting ambiguous duplicate evidence fields."""
    document = dict(pairs)
    if len(document) != len(pairs):
        raise InvalidResponse("Duplicate field in JSON response")
    return document


def _read_json(response: Response) -> dict[str, Any]:
    """Read a bounded native Requests JSON stream without publishing partial output.

    Args:
        response: Caller-owned response; the caller owns closure and its deadline.

    Returns:
        A UTF-8 JSON object with unambiguous keys and standard numeric literals.

    Raises:
        InvalidResponse: Wrong media type, oversized decoded bytes or invalid JSON.
        requests.RequestException: Reading fails; no HTTP calls or retries occur.
    """
    media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise InvalidResponse("Expected application/json response")
    body = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=8192):
            if len(body) + len(chunk) > JSON_RESPONSE_LIMIT:
                raise InvalidResponse("JSON response exceeded the decoded-byte limit")
            body.extend(chunk)
    except ContentDecodingError:
        raise InvalidResponse("Invalid JSON response content encoding") from None
    try:
        document = json.loads(
            body.decode("utf-8"), parse_constant=_reject_constant, object_pairs_hook=_json_object
        )
    except (ValueError, RecursionError):
        raise InvalidResponse("Target returned malformed JSON") from None
    if not isinstance(document, dict) or "error" in document:
        raise InvalidResponse("Expected a JSON answer object without an error")
    return document


class JSONAdapter:
    """Bounded non-streaming JSON answers with no answer-text TTFT observation."""

    def encode(self, target: Target, sample: Sample) -> dict[str, Any]:
        """Copy the raw workload object without adding model or streaming settings.

        Args:
            target: Target configuration; model and request_usage do not affect JSON.
            sample: A nonempty provider-independent inputs object.

        Returns:
            A shallow copy of inputs; nested values remain unchanged and caller-owned.

        Raises:
            ValueError: Inputs are empty.
        """
        if not sample.inputs:
            raise ValueError("http-json requires a nonempty inputs object")
        return dict(sample.inputs)

    def decode(self, response: Response, row: dict[str, Any], sent: float) -> None:
        """Validate a complete JSON response before publishing any answer evidence.

        Args:
            response: Caller-owned streamed 2xx response; this method does not close it.
            row: Mutable attempt evidence. Timing fields are not modified.
            sent: Monotonic dispatch time in seconds, unused for non-streaming timing.

        Raises:
            InvalidResponse: Media type, decoded size, JSON, answer, usage, or trace
                correlation violates the fixed contract. Errors omit response content.
            requests.RequestException: Reading the response fails or times out.

        The body is capped at two million bytes after transport decompression and is
        decoded as UTF-8. Only application/json is supported, including parameters;
        structured +json types require a separate review. The worker owns the deadline
        and full response latency, including this parsing. No HTTP calls are created.
        """
        document = _read_json(response)
        outputs = document.get("outputs")
        if not isinstance(outputs, str) or not outputs.strip():
            raise InvalidResponse("JSON response requires nonempty text outputs")
        try:
            outputs.encode("utf-8")
        except UnicodeEncodeError:
            raise InvalidResponse("JSON response contains invalid answer text") from None
        output_tokens = None
        if "usage" in document:
            usage = document["usage"]
            if not isinstance(usage, dict):
                raise InvalidResponse("Invalid JSON response token usage")
            output_tokens = usage.get("output_tokens")
            if type(output_tokens) is not int or output_tokens < 0:
                raise InvalidResponse("Invalid JSON response token usage")
        trace_id = None
        header_id = response.headers.get("X-MLflow-Trace-ID")
        if header_id is not None:
            trace_id = _trace_id(header_id)
        if "trace_id" in document:
            body_id = _trace_id(document["trace_id"])
            if trace_id is not None and trace_id != body_id:
                raise InvalidResponse("JSON response trace identifiers disagree")
            trace_id = body_id
        row.update(outputs=outputs, output_tokens=output_tokens, trace_id=trace_id)


def _runtime_text(output: Any) -> str:
    """Extract supported synchronous text from a handler or CLI-template result.

    Args:
        output: Invocation output, whose schema is owned by the hosted handler.

    Returns:
        Plain text from a string, documented answer handler, or assistant messages.

    Raises:
        InvalidResponse: Unsupported result, interrupted template, or absent text.

    This adapter intentionally supports a bounded subset of handler schemas. Tool
    results, reasoning, user messages and arbitrary JSON never become answer text.
    """
    if isinstance(output, dict) and output.get("status", "completed") != "completed":
        raise InvalidResponse("Agent Runtime handler did not complete")
    if isinstance(output, str):
        text = output
    elif isinstance(output, dict) and isinstance(output.get("answer"), str):
        text = output["answer"]
    elif isinstance(output, dict) and isinstance(output.get("output"), list):
        parts = []
        for message in output["output"]:
            if not isinstance(message, dict):
                raise InvalidResponse("Invalid Agent Runtime output message")
            if message.get("role") != "assistant" or message.get("type", "message") != "message":
                continue
            content = message.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        raise InvalidResponse("Invalid Agent Runtime message content")
                    if part.get("type") in {"output_text", "text"}:
                        if not isinstance(part.get("text"), str):
                            raise InvalidResponse("Invalid Agent Runtime answer text")
                        parts.append(part["text"])
            else:
                raise InvalidResponse("Invalid Agent Runtime message content")
        text = "".join(parts)
    else:
        raise InvalidResponse("Unsupported Agent Runtime handler output")
    try:
        if not text.strip():
            raise ValueError
        text.encode("utf-8")
    except (ValueError, UnicodeEncodeError):
        raise InvalidResponse("Agent Runtime produced no valid answer text") from None
    return text


class AgentRuntimeAdapter:
    """Synchronous DurableAgentServer invocations, independent of App discovery."""

    def encode(self, target: Target, sample: Sample) -> dict[str, Any]:
        """Build the documented fixed synchronous invocation envelope.

        Args:
            target: Operator session policy; model/usage settings are not injected.
            sample: Query or messages. Other case fields remain evaluation metadata.

        Returns:
            A new UUID invocation, input messages, explicit false stream/background,
            and optional fixed or independently generated per-attempt session ID.

        Raises:
            ValueError: Workload query/messages are invalid.

        No retries, resume tokens, actor identities or background operations are added.
        The Locust caller replaces id with its journaled request identifier.
        """
        messages = SSEAdapter("mlflow-agent-server").encode(target, sample)["input"]
        body = {"id": str(uuid4()), "input": messages, "stream": False, "background": False}
        session = target.session_id or (str(uuid4()) if target.session_per_request else None)
        if session is not None:
            body["session_id"] = session
        return body

    def decode(self, response: Response, row: dict[str, Any], sent: float) -> None:
        """Validate a completed invocation before retaining answer/correlation data.

        Args:
            response: Caller-owned response; JSON is bounded after decompression.
            row: Mutable journal row; timing remains unavailable for JSON answers.
            sent: Monotonic dispatch seconds, unused for non-streaming timings.

        Raises:
            InvalidResponse: Background, incomplete, mismatched or unsupported result.
            requests.RequestException: Response reading fails.

        Native invocation completion and handler completion must both hold. No status
        URLs are followed, and an error never exports response bodies or partial text.
        """
        if response.status_code != 200:
            raise InvalidResponse("Expected a synchronous Agent Runtime result")
        document = _read_json(response)
        if document.get("status") != "completed" or any(
            key in document for key in ("status_url", "events_url")
        ):
            raise InvalidResponse("Agent Runtime invocation did not complete synchronously")
        try:
            identifier = document["id"]
            UUID(identifier)
            if row.get("request_id") is not None and identifier != row["request_id"]:
                raise ValueError
        except (KeyError, ValueError, TypeError, AttributeError):
            raise InvalidResponse("Agent Runtime invocation identifier does not match") from None
        text = _runtime_text(document.get("output"))
        trace = response.headers.get("X-MLflow-Trace-ID")
        if trace is not None:
            trace = _trace_id(trace)
        row.update(outputs=text, trace_id=trace)


def get_adapter(
    name: Literal["openai-chat", "mlflow-agent-server", "http-json", "databricks-agent-runtime"],
) -> ResponseAdapter:
    """Select one built-in contract without loading arbitrary adapter code.

    Args:
        name: Validated public protocol identifier.

    Returns:
        A stateless adapter, or an immutable SSE adapter with its envelope name.

    Raises:
        ValueError: The name is unsupported; no imports or target calls are attempted.
    """
    if name == "http-json":
        return JSONAdapter()
    if name == "databricks-agent-runtime":
        return AgentRuntimeAdapter()
    if name in {"openai-chat", "mlflow-agent-server"}:
        return SSEAdapter(name)
    raise ValueError("Unsupported target adapter")
