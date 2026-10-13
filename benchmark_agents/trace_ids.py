"""Bounded trace wire identifiers; no lookup, auth, or tracing dependency."""

import re
from typing import Any

MAX_TRACE_ID_CHARS = 1024
LEGACY_TRACE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
UC_TRACE_ID = re.compile(r"trace:/([A-Za-z0-9_.-]+)/([A-Za-z0-9_-]{1,128})")


def uc_namespace(value: Any) -> str | None:
    """Recognize one bounded native UC table identifier, not an authorized scope.

    Args:
        value: Target-provided identifier; never interpreted as a URL or SQL.

    Returns:
        The namespace in a syntactically valid native ID, otherwise None. Actual
        authorization still requires operator experiment resolution and scoped
        membership verification before trace content retrieval.
    """
    if not isinstance(value, str) or len(value) > MAX_TRACE_ID_CHARS:
        return None
    match = UC_TRACE_ID.fullmatch(value)
    return match[1] if match else None


def valid_wire_trace_id(value: Any) -> bool:
    """Preserve legacy UTF-8 IDs and allow only bounded native long UC IDs.

    Args:
        value: Untrusted header/body/SSE metadata value.

    Returns:
        Whether the unchanged identifier meets the existing 128-character legacy
        contract or the native UC extension. This is not tracing authorization.
    """
    if not isinstance(value, str) or not value.strip():
        return False
    if value.startswith("trace:/"):
        return uc_namespace(value) is not None
    if len(value) > 128:
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True
