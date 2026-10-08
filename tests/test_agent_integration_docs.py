"""Hosted-agent documentation/schema checks; no agent or provider calls."""

import ast
import re
from pathlib import Path

from evalsurge import Agent, RunCreate

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "AGENT_INTEGRATION.md"


def test_agent_integration_python_snippets_compile_without_execution() -> None:
    """Compile recipes without importing customer graphs/crews or starting servers."""
    snippets = re.findall(r"```python\n(.*?)```", GUIDE.read_text(), re.DOTALL)
    assert len(snippets) == 6
    for snippet in snippets:
        compile(snippet, str(GUIDE), "exec")
    bridges = [ast.parse(snippet) for snippet in snippets[1:4]]
    for tree in bridges:
        bridge = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef))
        assert bridge.name == "answer_case"
        assert [argument.arg for argument in bridge.args.args] == ["query"]
        assert [argument.arg for argument in bridge.args.kwonlyargs] == ["request_id"]


def test_agent_integration_request_and_bindings_match_public_contracts() -> None:
    """Construct only native models/bindings, without resolver, HTTP or inference."""
    snippets = re.findall(r"```python\n(.*?)```", GUIDE.read_text(), re.DOTALL)
    source = snippets[4].split("with EvalSurge(", 1)[0]
    namespace: dict = {}
    exec(compile(source, str(GUIDE), "exec"), namespace)
    request = namespace["request"]
    assert isinstance(request, RunCreate)
    assert request.evaluation.mode == "off"
    assert request.load.concurrency == 2
    assert request.load.max_requests == request.load.duration_seconds == 10
    assert request.cases[0].input == {"query": "Give a short greeting."}
    http = Agent.http("http://127.0.0.1:9001/invoke", protocol="http-json")
    assert http.registration.protocols == ("http-json",)
    translated = request.translate(http.target, set())
    assert translated.evaluation.samples[0].inputs == request.cases[0].input
    app_source = snippets[5].split("with EvalSurge(", 1)[0]
    exec(compile(app_source, str(GUIDE), "exec"), namespace)
    app = namespace["target"]
    assert app.registration.kind == "databricks-app"
    assert app.registration.protocols == ("databricks-agent-runtime",)
    assert app.registration.profile == "YOUR_SELECTED_OAUTH_PROFILE"


def test_integration_and_design_navigation_resolves() -> None:
    """Verify local documentation links/anchors without fetching external resources."""
    paths = (GUIDE, ROOT / "docs/adr/0012-hosted-agent-integration-contract.md")
    for guide in paths:
        for destination in re.findall(r"\]\(([^)]+)\)", guide.read_text()):
            if destination.startswith(("https://", "http://")):
                continue
            filename, _, anchor = destination.partition("#")
            target = guide.parent / filename if filename else guide
            assert target.is_file(), (guide, destination)
            if anchor:
                headings = re.findall(r"^#{1,6}\s+(.+)$", target.read_text(), re.MULTILINE)
                slugs = {
                    re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-")
                    for heading in headings
                }
                assert anchor in slugs, (guide, destination)
