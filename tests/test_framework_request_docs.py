"""Validate the four published framework/hosting requests without target traffic."""

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

from benchmark_agents.models import Target
from benchmark_agents.runner import payload
from benchmark_agents.settings import Settings
from benchmark_agents.v2_models import RunCreate
from evalsurge.cli import _configuration

ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "examples" / "requests"
GUIDE = ROOT / "docs" / "FRAMEWORK_TARGET_EXAMPLES.md"
ALIASES = {
    "local-langgraph": ("http", "openai-chat", "/langgraph/chat"),
    "local-openai-agents": ("http", "openai-chat", "/openai-agents/chat"),
    "databricks-langgraph": ("databricks-app", "databricks-agent-runtime", "/api/invocations"),
    "databricks-openai-agents": (
        "databricks-app",
        "databricks-agent-runtime",
        "/api/invocations",
    ),
}


def test_framework_request_inventory_and_operator_bindings() -> None:
    """Every hosting/framework combination has a request and operator-owned binding."""
    assert {path.stem for path in REQUESTS.glob("*.json")} == set(ALIASES)
    settings = Settings.model_validate(tomllib.loads((REQUESTS / "operator.toml").read_text()))
    assert set(settings.connections) == set(ALIASES)
    for alias, (kind, protocol, path) in ALIASES.items():
        binding = settings.connections[alias]
        assert binding.kind == kind
        assert binding.protocols == (protocol,)
        if kind == "http":
            assert binding.url == f"http://127.0.0.1:9001{path}"
            assert binding.profile is None
        else:
            assert binding.url is None
            assert binding.profile == "YOUR_SELECTED_OAUTH_PROFILE"
            assert binding.app_name


@pytest.mark.parametrize("alias", ALIASES)
def test_published_framework_request_translates_without_provider_calls(
    alias: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test actual schemas/encoders, not SDK discovery, provisioning, or model health."""

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Static example validation must not initialize a provider")

    monkeypatch.setattr("benchmark_agents.target_resolver.workspace_client", forbidden)
    monkeypatch.setattr("benchmark_agents.planner.planner_client", forbidden)
    monkeypatch.setattr("benchmark_agents.judges.judge_client", forbidden)
    file = REQUESTS / f"{alias}.json"
    body = json.loads(file.read_text())
    assert _configuration(file) == body
    request = RunCreate.model_validate(body)
    assert body["target"] == {"connection_id": alias}
    assert "evaluation" not in body
    assert request.evaluation.mode == "off"
    assert request.load.concurrency == 5
    assert request.load.duration_seconds == 180
    assert request.load.max_requests == 500
    assert request.load.timeout_seconds == 60
    kind, protocol, path = ALIASES[alias]
    url = f"http://127.0.0.1:9001{path}" if kind == "http" else f"https://example.invalid{path}"
    target = Target(url=url, adapter=protocol, session_per_request=kind == "databricks-app")
    translated = request.translate(target, set())
    assert translated.evaluation.scorers == translated.evaluation.registered_scorers == []
    assert translated.load == request.load
    for case, sample in zip(request.cases, translated.evaluation.samples, strict=True):
        assert sample.inputs == case.input
        assert sample.expectations == case.reference
        wire = payload(translated, sample)
        messages = wire["messages"] if kind == "http" else wire["input"]
        assert messages == [{"role": "user", "content": case.input["query"]}]
        if kind == "databricks-app":
            assert wire["stream"] is wire["background"] is False
            assert wire["session_id"]
        else:
            assert wire["stream"] is True


def test_framework_guide_requests_and_navigation_match_files() -> None:
    """Keep copy/paste bodies and links consistent with the executable fixtures."""
    guide = GUIDE.read_text()
    bodies = [json.loads(block) for block in re.findall(r"```json\n(.*?)```", guide, re.DOTALL)]
    published = {alias: json.loads((REQUESTS / f"{alias}.json").read_text()) for alias in ALIASES}
    requests = [body for body in bodies if "target" in body and "cases" in body]
    assert len(requests) == 4
    assert {body["target"]["connection_id"] for body in requests} == set(ALIASES)
    for body in requests:
        assert body == published[body["target"]["connection_id"]]
    for destination in re.findall(r"\]\(([^)]+)\)", guide):
        if destination.startswith(("https://", "http://")):
            continue
        file, _, _ = destination.partition("#")
        assert (GUIDE.parent / file).is_file(), destination
    for relative in ("README.md", "examples/README.md", "docs/TARGETS.md", "docs/V2_API.md"):
        assert "FRAMEWORK_TARGET_EXAMPLES.md" in (ROOT / relative).read_text()
