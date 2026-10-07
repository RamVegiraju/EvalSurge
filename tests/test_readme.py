"""Check published examples against the real local Python and report contracts."""

import asyncio
import json
import re
import shlex
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from benchmark_agents.evaluation_details import assessment_details
from benchmark_agents.models import Evaluation, RunReport
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
    requests = [document for document in documents if "cases" in document]
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
