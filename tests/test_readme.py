"""Check published examples against the real local Python and report contracts."""

import asyncio
import json
import re
import shlex
import tomllib
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from benchmark_agents.evaluation_details import assessment_details
from benchmark_agents.models import Evaluation, RunReport, Target
from benchmark_agents.runner import payload
from benchmark_agents.settings import Settings
from benchmark_agents.v2_models import RunCreate
from evalsurge import EvalSurge, Sample

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


async def test_readme_python_request_runs_without_judging(
    endpoint, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Run the documented request against a local SSE fixture, not a paid provider."""
    base_url, server = endpoint
    blocks = re.findall(r"```python\n(.*?)```", README.read_text(), re.DOTALL)
    assert len(blocks) == 2
    source = blocks[0].replace("http://127.0.0.1:9001/chat", base_url + "/normal")
    source = source.replace('"artifacts/python"', repr(str(tmp_path / "python")))

    def execute() -> dict[str, Any]:
        """Keep synchronous client waits off the fixture server's event loop."""
        namespace: dict[str, Any] = {}
        exec(compile(source, str(README), "exec"), namespace)
        return namespace

    namespace = await asyncio.to_thread(execute)
    report = namespace["report"]
    printed = RunReport.model_validate_json(capsys.readouterr().out)
    assert printed == report
    assert report.run.status == "completed"
    assert report.run.preflight.status == "passed"
    assert report.run.metrics["requests"] == report.run.metrics["successful_requests"] == 20
    assert report.run.metrics["error_rate"] == 0
    assert report.run.evaluation == {
        "status": "no_ready_scorers",
        "results": [],
        "needs_data": [],
    }
    assert report.run.config.evaluation.scorers == []
    assert report.run.config.evaluation.registered_scorers == []
    assert server["received"] == 21
    assert all(
        body["messages"][0]["content"] == "Can I refund an opened item?"
        for body in server["bodies"]
    )
    with EvalSurge.local(artifact_dir=tmp_path / "python") as client:
        persisted = client.report(report.run.id)
    assert persisted.run.metrics == report.run.metrics
    assert persisted.run.evaluation == report.run.evaluation


def test_readme_quality_policy_and_output_match_current_contracts() -> None:
    """Validate optional policy and report projections without invoking judges."""
    readme = README.read_text()
    install = re.search(r"^uv sync .+$", readme, re.MULTILINE)
    assert install is not None
    arguments = shlex.split(install.group())
    assert "--locked" in arguments
    assert arguments[arguments.index("--default-index") + 1] == "https://pypi.org/simple"
    blocks = re.findall(r"```python\n(.*?)```", readme, re.DOTALL)
    namespace: dict[str, Any] = {}
    exec(compile(blocks[1], str(README), "exec"), namespace)
    policy: Evaluation = namespace["evaluation"]
    assert policy.scorers == ["relevance", "correctness"]
    assert policy.registered_scorers == []
    assert policy.max_scored_requests == 20
    sample = Sample(
        inputs={"query": "Can I refund an opened item?"},
        expectations={"expected_response": "Opened items are not refundable."},
    )
    assert sample.expectations["expected_response"]
    blocks = re.findall(r"```json\n(.*?)```", readme, re.DOTALL)
    documents = [json.loads(block) for block in blocks]
    reports = [document for document in documents if "run" in document]
    assert len(reports) == 1
    excerpt = reports[0]
    assert set(excerpt) <= RunReport.model_fields.keys()
    run = excerpt["run"]
    assert run["status"] == "completed"
    assert run["metrics"]["requests"] == policy.max_scored_requests == 20
    assert run["metrics"]["timing_successful_only"]["latency_ms"]["count"] == 20
    assert run["metrics"]["timing_successful_only"]["ttft_ms"]["count"] == 20
    criterion = run["evaluation"]["results"][0]
    assert criterion["scored"] == criterion["attempted"] == policy.max_scored_requests
    assert criterion["judge_errors"] == 0
    assert criterion["pass_rate"] == 16 / 20
    assessment = criterion["assessments"][0]
    native = pd.DataFrame(
        [
            {
                "tags": {"evalsurge.request_id": assessment["request_id"]},
                "correctness/value": False,
                "correctness/rationale": "The answer allowed a refund for an opened item.",
            }
        ]
    )
    normalized = assessment_details(
        native,
        [{"request_id": assessment["request_id"], "case_id": 0}],
        "correctness",
        "correctness",
        catalog=True,
    )
    assert criterion["assessments"] == normalized


def test_readme_automatic_request_matches_v2_contract() -> None:
    """Validate opt-in automatic judging and authoritative evidence without traffic."""
    documents = [
        json.loads(block)
        for block in re.findall(r"```json\n(.*?)```", README.read_text(), re.DOTALL)
    ]
    requests = [
        document
        for document in documents
        if document.get("evaluation", {}).get("mode") == "automatic"
    ]
    assert len(requests) == 1
    request = RunCreate.model_validate(requests[0])
    assert request.target.connection_id == "refund-agent"
    assert request.evaluation.mode == "automatic"
    assert request.evaluation.scorers == []
    assert request.evaluation.max_scored_requests == 20
    assert request.cases[0].reference["expected_response"]
    assert request.load.max_requests == 20
    assert "url" not in requests[0]["target"]
    assert "profile" not in requests[0]["target"]


def test_readme_recommended_request_defaults_to_performance_only() -> None:
    """Validate the first v2 example without resolving credentials or invoking targets."""
    readme = README.read_text()
    documents = [json.loads(block) for block in re.findall(r"```json\n(.*?)```", readme, re.DOTALL)]
    body = documents[0]
    request = RunCreate.model_validate(body)
    assert request.target.connection_id == "refund-agent"
    assert "evaluation" not in body
    assert request.evaluation.mode == "off"
    assert set(body["target"]) == {"connection_id"}
    assert request.load.concurrency == 3
    assert request.load.max_requests == 20
    assert readme.index("Recommended request") < readme.index("legacy v1")


def test_target_guide_examples_validate_without_discovery_or_traffic() -> None:
    """Validate both operator bindings and their shared public request natively."""
    guide = (ROOT / "docs" / "TARGETS.md").read_text()
    operator_blocks = re.findall(r"```toml\n(.*?)```", guide, re.DOTALL)
    request_blocks = re.findall(r"```json\n(.*?)```", guide, re.DOTALL)
    assert len(operator_blocks) == len(request_blocks) == 1
    settings = Settings.model_validate(tomllib.loads(operator_blocks[0]))
    request_body = json.loads(request_blocks[0])
    local = settings.connections["local-agent"]
    app = settings.connections["app-agent"]
    assert local.kind == "http"
    assert app.kind == "databricks-app"
    assert app.protocols == ("databricks-agent-runtime",)
    assert app.profile == "YOUR_SELECTED_OAUTH_PROFILE"
    for connection_id, url in (
        ("local-agent", local.url),
        ("app-agent", "https://your-app.aws.databricksapps.com/api/invocations"),
    ):
        binding = settings.connections[connection_id]
        request = RunCreate.model_validate(
            {**request_body, "target": {"connection_id": connection_id}}
        )
        target = Target(url=url, adapter=binding.protocols[0], connection_id=connection_id)
        translated = request.translate(target, set())
        assert request.evaluation.mode == "off"
        assert translated.evaluation.scorers == []
        assert translated.evaluation.registered_scorers == []
        assert translated.load.concurrency == 5
        assert translated.load.duration_seconds == 180
        assert translated.load.max_requests == 500
        wire = payload(translated, translated.evaluation.samples[0])
        messages = wire["messages"] if binding.kind == "http" else wire["input"]
        assert messages == [{"role": "user", "content": "Reply with a short greeting."}]
        if binding.kind == "databricks-app":
            assert wire["stream"] is wire["background"] is False


def test_readme_relative_documentation_links_and_anchors_resolve() -> None:
    """Check local README navigation without assuming remote pages are reachable."""
    for target in re.findall(r"\]\(([^)]+)\)", README.read_text()):
        if target.startswith(("https://", "http://")):
            continue
        destination, _, anchor = target.partition("#")
        path = ROOT / destination if destination else README
        assert path.is_file(), f"Missing README destination: {target}"
        if anchor:
            headings = re.findall(r"^#{1,6}\s+(.+)$", path.read_text(), re.MULTILINE)
            slugs = {
                re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-") for heading in headings
            }
            assert anchor in slugs, f"Missing README anchor: {target}"
