"""Dependency-light schema guidance shared by REST, direct/remote SDK and CLI.

Submitted values, arbitrary keys and custom validator text are protected. Only
bounded public locations, fixed diagnostics and validated numeric bounds leave
this boundary. This module never imports FastAPI or the execution stack.
"""

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from .limits import MAX_REQUEST_BYTES
from .models import Load
from .v2_models import Case, EvaluationPolicy, RunCreate, TargetReference, ValidationIssue


def sanitized_validation_issues(
    failures: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Reduce validation failures without disclosing their values or raw context.

    Args:
        failures: Pydantic/FastAPI ``errors()`` records, whose inputs stay private.

    Returns:
        At most 20 issues with at most 12 public path components each. Unknown
        keys become ``<extra>``. Custom guidance is an exact fixed allowlist.
        No code is executed and no network/filesystem operations are performed.
    """
    fields = {"body", "query", "path", "header", "run_id", "offset", "limit", "idempotency-key"}
    for model in (Load, Case, EvaluationPolicy, RunCreate, TargetReference):
        fields.update(model.model_fields)
    fixed_messages = {
        "Explicit evaluation requires scorer IDs",
        "Scorer IDs require explicit evaluation",
        "Scorer IDs must be unique",
        "Scorer IDs exceed the supported bounds",
    }
    messages = {
        "missing": ("required_field", "Field is required"),
        "extra_forbidden": ("unsupported_field", "Field is not supported"),
        "literal_error": ("invalid_choice", "Use one of the documented allowed values"),
        "string_pattern_mismatch": ("invalid_format", "Use the documented field format"),
        "uuid_parsing": ("invalid_format", "Must be a valid UUID"),
        "json_invalid": ("invalid_json", "Request body must be valid JSON"),
    }
    bounds = {
        "greater_than_equal": ("ge", "Must be greater than or equal to"),
        "less_than_equal": ("le", "Must be less than or equal to"),
        "greater_than": ("gt", "Must be greater than"),
        "less_than": ("lt", "Must be less than"),
        "string_too_short": ("min_length", "Must contain at least"),
        "string_too_long": ("max_length", "Must contain at most"),
        "too_short": ("min_length", "Must contain at least"),
        "too_long": ("max_length", "Must contain at most"),
    }
    issues = []
    for failure in failures[:20]:
        location = [
            part
            if (type(part) is int and 0 <= part <= 8_000_000)
            or (isinstance(part, str) and part in fields)
            else "<extra>"
            for part in failure.get("loc", ())[:12]
        ]
        kind = failure.get("type", "")
        code, message = messages.get(kind, ("invalid_value", "Field has an invalid value"))
        if kind.endswith(("_type", "_parsing")) and kind not in messages:
            code, message = "invalid_type", "Use the documented field type"
        if kind in bounds:
            key, prefix = bounds[kind]
            bound = failure.get("ctx", {}).get(key)
            if type(bound) in {int, float} and 0 <= bound <= 8_000_000:
                code, message = "out_of_bounds", f"{prefix} {bound}"
                if "length" in key:
                    message += " characters" if kind.startswith("string_") else " items"
        if kind == "value_error":
            for fixed in fixed_messages:
                if failure.get("msg") == f"Value error, {fixed}":
                    message = fixed
                    break
        issues.append({"location": location, "code": code, "message": message})
    return issues


class RequestValidationError(ValueError):
    """Safe field-specific request failure, without retaining submitted values."""

    def __init__(self, failures: Sequence[Mapping[str, Any]]) -> None:
        """Retain only bounded sanitized issues and construct safe textual guidance.

        Args:
            failures: Native validation records; discarded after sanitization.
        """
        self.issues = tuple(
            ValidationIssue.model_validate(issue) for issue in sanitized_validation_issues(failures)
        )
        lines = ["Invalid benchmark request fields:"]
        for issue in self.issues:
            location = ".".join(str(part) for part in issue.location) or "request"
            lines.append(f"  {location}: {issue.message}")
        super().__init__("\n".join(lines))

    def errors(self) -> list[dict[str, Any]]:
        """Return detached public diagnostics, never native Pydantic input records."""
        return [issue.model_dump() for issue in self.issues]


def validate_request(config: Mapping[str, Any] | RunCreate) -> RunCreate:
    """Validate the unified request while keeping native error inputs private.

    Args:
        config: Caller request model or JSON-like mapping, not operator settings.

    Returns:
        A validated detached model. This does not authorize a target or send traffic.

    Raises:
        RequestValidationError: Safe bounded field-specific schema guidance.
        ValueError: The input is not a nonempty request mapping.
    """
    if isinstance(config, RunCreate):
        # Assignment validation cannot protect in-place container mutations or
        # model_construct(). Revalidate through public Python values before any
        # target discovery; warnings must not echo a tampered private value.
        config = config.model_dump(mode="python", warnings=False)
    if not isinstance(config, Mapping) or not config:
        raise ValueError("Configuration must be a nonempty JSON object")
    try:
        return RunCreate.model_validate(dict(config))
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from None


def encode_request(config: Mapping[str, Any] | RunCreate) -> tuple[RunCreate, bytes]:
    """Validate and detach one finite UTF-8 request identically in both SDK modes.

    Args:
        config: Raw mappings must already be finite JSON-compatible values. A
            validated RunCreate may use its public Pydantic JSON serialization;
            unset fields stay omitted to preserve legacy remote submission bodies.

    Returns:
        Detached request rebuilt from the encoded JSON, plus exactly the bytes
        checked against the eight-million-byte limit. Unicode is not ASCII-escaped.

    Raises:
        RequestValidationError: Bounded field-specific schema guidance.
        ValueError: Python-only mapping values, nonfinite data, malformed Unicode,
            unsupported serialization, or an oversized UTF-8 request.

    Side Effects:
        None. No operator settings, auth, target discovery or model calls occur.
    """
    validated = validate_request(config)
    try:
        # Pydantic JSON serialization can normalize nonfinite Any values to null.
        # Reject them in Python form first, including in-place model mutations.
        _require_finite_values(validated.model_dump(mode="python", warnings=False))
        document = (
            config.model_dump(mode="json", exclude_unset=True)
            if isinstance(config, RunCreate)
            else dict(config)
        )
        encoded = json.dumps(document, allow_nan=False, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise ValueError("Configuration must contain finite JSON-compatible values") from None
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ValueError("Configuration exceeds the eight-million-byte limit")
    try:
        return RunCreate.model_validate_json(encoded), encoded
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from None


def _require_finite_values(document: Any) -> None:
    """Reject nonfinite floats before typed JSON normalization without retaining values.

    Args:
        document: Detached Python request data, potentially containing supported
            typed values such as datetimes; this check does not serialize them.

    Raises:
        ValueError: A nested float is NaN or infinite. The message is value-free.

    Side Effects:
        None. Containers are inspected once, not modified; cycles are left for
        the serializer's existing circular-reference rejection.
    """
    pending = [document]
    seen: set[int] = set()
    while pending:
        value = pending.pop()
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Configuration must contain finite JSON-compatible values")
        if isinstance(value, (Mapping, list, tuple, set, frozenset)):
            identity = id(value)
            if identity in seen:
                continue
            seen.add(identity)
            if isinstance(value, Mapping):
                pending.extend(value.keys())
                pending.extend(value.values())
            else:
                pending.extend(value)
