"""Structural client-ownership regression; no framework import or inference."""

import ast
from pathlib import Path


def test_framework_startup_is_inside_transport_ownership_guard() -> None:
    """Require startup and SDK close failures to retain native transport cleanup."""
    path = Path(__file__).resolve().parents[1] / "examples" / "framework_agent.py"
    tree = ast.parse(path.read_text())
    lifespan = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan"
    )
    ownership = next(
        node
        for node in lifespan.body
        if isinstance(node, ast.Try)
        and any(isinstance(child, ast.Yield) for child in ast.walk(node))
    )
    initialization_calls = {
        call.func.id
        for statement in ownership.body
        for call in ast.walk(statement)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    }
    assert {"AsyncOpenAI", "ChatOpenAI", "build_graph", "Agent"} <= initialization_calls
    cleanup = next(
        node
        for statement in ownership.finalbody
        for node in ast.walk(statement)
        if isinstance(node, ast.Try)
        and any(
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Await)
            and isinstance(statement.value.value, ast.Call)
            and isinstance(statement.value.value.func, ast.Attribute)
            and isinstance(statement.value.value.func.value, ast.Name)
            and statement.value.value.func.value.id == "http"
            and statement.value.value.func.attr == "aclose"
            for statement in node.finalbody
        )
    )
    assert any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "client"
        and len(node.test.ops) == 1
        and isinstance(node.test.ops[0], ast.IsNot)
        and len(node.test.comparators) == 1
        and isinstance(node.test.comparators[0], ast.Constant)
        and node.test.comparators[0].value is None
        for statement in cleanup.body
        for node in ast.walk(statement)
    )
    assert any(
        isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "client"
        and node.value.func.attr == "close"
        for statement in cleanup.body
        for node in ast.walk(statement)
    )
