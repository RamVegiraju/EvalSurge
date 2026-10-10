"""Explicit in-process native boundary for existing controlled-provider unit tests.

This is test code, not a shipped scorer/plugin or worker bypass. Provider fixtures
do not cross processes. These tests deliberately exercise native scoring/error
mapping in the parent; independent storage tests exercise production ownership.
Running controlled inference tests still requires user disclosure and approval.
"""

from typing import Any

import pytest

from benchmark_agents import coordinator, evaluation_preflight
from benchmark_agents.evaluator import _evaluate_native


def evaluate_inline_native(*args: Any, cancellation: Any = None, **kwargs: Any) -> dict[str, Any]:
    """Keep controlled provider fixtures in the native scorer's test process.

    Args:
        args: Captured rows, frozen plan and optional native traces.
        cancellation: Accepted for caller compatibility, intentionally not acted on.
            Actual cancellation/process ownership is tested in the storage suite.
        kwargs: Native evaluation options such as phase and fail-fast behavior.

    Returns:
        The actual native evaluator's result with the test's explicit provider hooks.

    The caller must install a controlled provider or fail-if-called sentinel first.
    This test-only boundary does not exercise worker isolation, durable verification
    or real inference; it must not be installed by live validation harnesses.
    """
    return _evaluate_native(*args, **kwargs)


def install_inline_native(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bind controlled unit tests to native scoring without creating paid children."""
    monkeypatch.setattr(coordinator, "evaluate", evaluate_inline_native)
    monkeypatch.setattr(evaluation_preflight, "evaluate", evaluate_inline_native)
