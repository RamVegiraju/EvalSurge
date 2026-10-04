"""Opt-in static manifest extraction; parse a local file, never import or execute it."""

import argparse
import ast
import json
from pathlib import Path

from benchmark_agents.models import AgentManifest, Capability


def scan(path: Path, framework: str, name: str) -> AgentManifest:
    """Extract public tool names and known memory constructs from bounded Python source.

    Args:
        path: File the owner explicitly selects for disclosure.
        framework: LangGraph or OpenAI Agents label selected by the owner.
        name: Human-readable name; raw source, comments, and constants are not exported.

    Returns:
        A conservative draft manifest requiring owner review. Dynamic registration,
        external files, actual permissions, and runtime behavior cannot be inferred.

    Raises:
        ValueError: Source exceeds one megabyte or produces too many capabilities.
        SyntaxError: Source is not valid Python.
    """
    with path.open("rb") as stream:
        source = stream.read(1_000_001)
    if len(source) > 1_000_000:
        raise ValueError("Select a Python file under one megabyte")
    tree = ast.parse(source)
    capabilities = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                reference = decorator.func if isinstance(decorator, ast.Call) else decorator
                decorator_name = (
                    reference.id
                    if isinstance(reference, ast.Name)
                    else reference.attr
                    if isinstance(reference, ast.Attribute)
                    else ""
                )
                if decorator_name in {"tool", "function_tool"}:
                    capabilities[node.name] = Capability(name=node.name, kind="tool")
        if isinstance(node, ast.Call):
            reference = node.func
            constructor = (
                reference.id
                if isinstance(reference, ast.Name)
                else reference.attr
                if isinstance(reference, ast.Attribute)
                else ""
            )
            if constructor in {"InMemorySaver", "MemorySaver", "SQLiteSession", "PostgresSaver"}:
                capabilities[constructor] = Capability(name=constructor, kind="memory")
    return AgentManifest(
        name=name,
        framework=framework,
        source="static-scan",
        description="Static draft only; owner review required. No runtime evidence or ground truth.",
        capabilities=list(capabilities.values()),
    )


def main() -> None:
    """Print a draft manifest for explicit owner inspection before API submission."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--framework", choices=["langgraph", "openai-agents"], required=True)
    parser.add_argument("--name", default="Hosted agent")
    options = parser.parse_args()
    print(json.dumps(scan(options.path, options.framework, options.name).model_dump(), indent=2))


if __name__ == "__main__":
    main()
