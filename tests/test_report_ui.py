"""Execute report JavaScript with a bounded DOM fixture, without a model or browser."""

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

STATIC = Path(__file__).resolve().parents[1] / "benchmark_agents" / "static"


class Elements(HTMLParser):
    """Collect real shell element IDs so the fixture cannot hide missing UI nodes."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "id" and value:
                self.ids.append(value)


def render(report: dict[str, Any], **actions: Any) -> dict[str, Any]:
    """Run the shipped script and serialize its DOM updates and HTTP calls.

    Args:
        report: Controlled API report evidence; no model/provider is contacted.
        actions: Optional pagination, invalid-input, or framework-toggle actions.

    Returns:
        Rendered element trees, fetch calls, and URL history changes.

    Raises:
        AssertionError: Node is unavailable or JavaScript fails.

    This is a rendering/interaction contract test, not browser layout verification.
    """
    node = shutil.which("node")
    assert node, "Install Node.js >=22 to run report JavaScript contract tests."
    shell = Elements()
    shell.feed((STATIC / "index.html").read_text())
    assert len(shell.ids) == len(set(shell.ids))
    payload = {"ids": shell.ids, "script": str(STATIC / "report.js"), "report": report, **actions}
    result = subprocess.run(
        [node, str(Path(__file__).with_name("report_harness.cjs"))],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture
def evidence() -> dict[str, Any]:
    return {
        "run": {
            "id": "12345678-1234-4321-8123-123456789abc",
            "status": "completed_with_gaps",
            "load_status": "completed",
            "profiling_status": "completed",
            "evaluation_status": "completed_with_gaps",
            "config": {
                "target": {"framework": "langgraph", "url": "http://127.0.0.1:9001/chat"},
                "load": {"concurrency": 2},
                "evaluation": {"description": "Refund policy", "samples": [{}]},
            },
            "metrics": {
                "successful_tps": 1.2,
                "requests": 2,
                "successful_requests": 2,
                "error_rate": 0,
                "timing_successful_only": {"latency_ms": {"p95": 100}},
            },
            "plan": {
                "id": "frozen-plan",
                "source": "llm",
                "rubric_version": "rubric-v1",
                "judge_model": "configured-model",
                "sampling_policy": "case-time-stratified-v1",
                "max_scored_requests": 1,
                "notes": ["Uncalibrated suggestions; review first."],
                "registered_scorers": [],
                "recommendations": [
                    {
                        "scorer": "relevance",
                        "reason": "<img src=x onerror=alert(1)>Matches the question.",
                        "status": "ready",
                        "required_fields": ["inputs", "outputs"],
                        "eligible_samples": 1,
                        "total_samples": 1,
                    },
                    {
                        "scorer": "correctness",
                        "reason": "Compare with supplied references.",
                        "status": "needs_data",
                        "required_fields": ["inputs", "outputs", "expectations"],
                        "eligible_samples": 0,
                        "total_samples": 1,
                    },
                ],
            },
            "evaluation": {
                "status": "completed_with_gaps",
                "results": [
                    {
                        "scorer": "relevance",
                        "status": "completed",
                        "eligible": 2,
                        "coverage": {"selected": 1, "fraction_of_eligible": 0.5},
                        "attempted": 1,
                        "scored": 1,
                        "judge_errors": 0,
                        "request_ids": ["request"],
                        "pass_rate": 0,
                        "metrics": {"relevance/mean": 0},
                        "source": "catalog",
                        "version": "rubric-v1",
                    }
                ],
            },
        },
        "profiling": {
            "coverage": 0.5,
            "traced_requests": 1,
            "total_requests": 2,
            "hotspots": [],
            "notes": ["Not a critical path."],
            "gaps": {"missing": 1},
        },
        "requests": [
            {
                "request_id": "request",
                "success": True,
                "status": "available",
                "latency_ms": 100,
                "agent_duration_ms": 80,
                "client_minus_agent_ms": 20,
                "occupancy_ms": {"model": 60, "orchestration": 20},
                "spans": [
                    {
                        "span_id": "root",
                        "parent_id": None,
                        "depth": 0,
                        "name": "Agent workflow",
                        "category": "orchestration",
                        "status": "OK",
                        "start_ms": 0,
                        "duration_ms": 80,
                        "self_ms": 20,
                    },
                    {
                        "span_id": "child",
                        "parent_id": "root",
                        "depth": 1,
                        "name": "Generation",
                        "category": "model",
                        "status": "OK",
                        "start_ms": 10,
                        "duration_ms": 60,
                        "self_ms": 60,
                    },
                ],
            },
            {
                "request_id": "missing",
                "success": True,
                "status": "missing",
                "latency_ms": 90,
                "agent_duration_ms": None,
                "client_minus_agent_ms": None,
                "occupancy_ms": {},
                "spans": [],
            },
        ],
        "total": 2,
        "offset": 0,
        "limit": 25,
    }


def test_suggestions_keep_rationale_and_preload_readiness(evidence: dict[str, Any]) -> None:
    output = render(evidence)
    text = output["nodes"]["suggestions"]["text"]
    assert "<img src=x onerror=alert(1)>Matches the question." in text
    assert "1 / 1 input cases ready" in text and "0 / 1 input cases ready" in text
    assert "expectations" in text and "Needs data" in text
    assert "LLM-suggested" in output["nodes"]["plan-source"]["text"]
    assert "private-test-key" not in json.dumps(output["history"])


def test_zero_quality_and_missing_evidence_are_distinct(evidence: dict[str, Any]) -> None:
    output = render(evidence)
    text = output["nodes"]["judges"]["text"]
    assert "0.0%" in text
    assert "1 / 1 selected scored" in text
    assert "1 / 2 eligible selected" in text
    assert "Needs data" in text
    assert "0 judge errors" in text
    assert "overall pass" not in text.lower()
    assert output["nodes"]["waterfall"]["text"].count("Generation") == 1
    assert "Agent workflow" not in output["nodes"]["waterfall"]["text"]
    assert "1 enclosing/framework span hidden" in output["nodes"]["waterfall-note"]["text"]
    expanded = render(evidence, toggle=True)
    assert "Agent workflow" in expanded["nodes"]["waterfall"]["text"]


def test_registered_numeric_and_partial_results(evidence: dict[str, Any]) -> None:
    plan = evidence["run"]["plan"]
    plan["source"] = "explicit"
    plan["recommendations"][0]["scorer"] = "registered:grounding"
    plan["registered_scorers"] = [{"alias": "grounding", "name": "Grounding", "version": 7}]
    result = evidence["run"]["evaluation"]["results"][0]
    result.update(
        scorer="registered:grounding",
        status="partial",
        attempted=2,
        scored=1,
        judge_errors=1,
        pass_rate=None,
        metrics={"Grounding/mean": 0.75},
        source="registered-mlflow",
        version=7,
        coverage={"selected": 2},
    )
    output = render(evidence)
    assert "Registered MLflow · v7" in output["nodes"]["suggestions"]["text"]
    assert "Explicit selection" in output["nodes"]["plan-source"]["text"]
    text = output["nodes"]["judges"]["text"]
    assert "Grounding/mean" in text and "0.75" in text and "Partial" in text
    assert "1 / 2 selected scored" in text and "1 judge error" in text
    assert "boolean pass rate" not in text


@pytest.mark.parametrize(
    "status",
    ["pending", "no_ready_scorers", "needs_configuration", "configuration_changed", "failed"],
)
def test_no_assessment_statuses_are_not_passes(evidence: dict[str, Any], status: str) -> None:
    evidence["run"]["evaluation"] = {"status": status, "results": []}
    evidence["run"]["evaluation_status"] = status
    output = render(evidence)
    assert "—" in output["nodes"]["judges"]["text"]
    assert "0.0% boolean pass rate" not in output["nodes"]["judges"]["text"]
    assert status.replace("_", " ").capitalize() in output["nodes"]["evaluation-status"]["text"]


def test_empty_report_clears_evidence(evidence: dict[str, Any]) -> None:
    evidence["run"]["plan"]["recommendations"] = []
    evidence["run"]["evaluation"] = {"status": "no_ready_scorers", "results": []}
    evidence["requests"] = []
    evidence["total"] = 0
    output = render(evidence)
    assert "Performance-only run" in output["nodes"]["suggestions"]["text"]
    assert "No request profiles" in output["nodes"]["waterfall-note"]["text"]
    assert output["nodes"]["next"]["disabled"]


def test_pagination_and_failed_refresh_clear_stale_data(evidence: dict[str, Any]) -> None:
    evidence["total"] = 26
    output = render(
        evidence,
        next=True,
        responses=[
            {"ok": True, "body": evidence},
            {"ok": False, "status": 401, "body": {"error": {"message": "Not authorized"}}},
        ],
    )
    assert output["calls"][1]["url"].endswith("offset=25&limit=25")
    assert output["nodes"]["report"]["hidden"]
    assert output["nodes"]["message"]["text"] == "Not authorized"
    invalid = render(evidence, invalid=True)
    assert invalid["nodes"]["report"]["hidden"]
    assert len(invalid["calls"]) == 1


def test_unaggregated_assessments_and_unknown_counts(evidence: dict[str, Any]) -> None:
    result = evidence["run"]["evaluation"]["results"][0]
    result["metrics"] = {}
    result["pass_rate"] = None
    output = render(evidence)
    assert "No numeric summary" in output["nodes"]["judges"]["text"]
    assert "No assessments" in output["nodes"]["judges"]["text"]
    result.clear()
    result.update(scorer="relevance", status="configuration_changed")
    output = render(evidence)
    assert "Distinct answers selected—" in output["nodes"]["evaluation-summary"]["text"]
    assert "Reported judge errors—" in output["nodes"]["evaluation-summary"]["text"]


def test_enclosing_spans_are_reversible_and_gaps_clear_waterfall(evidence: dict[str, Any]) -> None:
    profile = evidence["requests"][0]
    profile["spans"].append(
        {
            **profile["spans"][1],
            "span_id": "model-leaf",
            "parent_id": "child",
            "depth": 2,
            "name": "AsyncCompletions",
            "duration_ms": 50,
        }
    )
    output = render(evidence)
    assert "Generation" not in output["nodes"]["waterfall"]["text"]
    assert "AsyncCompletions" in output["nodes"]["waterfall"]["text"]
    assert "Generation" in render(evidence, toggle=True)["nodes"]["waterfall"]["text"]
    gap = render(evidence, select_missing=True)
    assert not gap["nodes"]["waterfall"]["children"]
    assert "trace gap: missing" in gap["nodes"]["waterfall-note"]["text"]
    assert gap["nodes"]["show-framework"]["disabled"]


def test_same_origin_fetch_supports_prefix_and_no_secret_history(evidence: dict[str, Any]) -> None:
    output = render(evidence, origin="http://localhost/bench/reports/")
    request = output["calls"][0]
    assert request["url"].startswith("/bench/v1/runs/")
    assert request["options"]["headers"] == {"X-API-Key": "private-test-key"}
    assert request["options"]["cache"] == "no-store"
    assert request["options"]["credentials"] == "same-origin"
    assert "private-test-key" not in json.dumps(output["history"])


def test_hotspots_prioritize_operations_without_altering_evidence(evidence: dict[str, Any]) -> None:
    hotspots = [
        {"name": "AgentRunner", "category": "orchestration", "p95_ms": 100, "observations": 2},
        {"name": "policy_db", "category": "tool", "p95_ms": 90, "observations": 2},
        {"name": "Model API", "category": "model", "p95_ms": 60, "observations": 2},
    ]
    evidence["profiling"]["hotspots"] = hotspots
    output = render(evidence)
    assert "policy_db" in output["nodes"]["hotspots"]["text"]
    assert "AgentRunner" not in output["nodes"]["hotspots"]["text"]
    assert evidence["profiling"]["hotspots"] == hotspots
    evidence["profiling"]["hotspots"] = hotspots[:1]
    output = render(evidence)
    assert "AgentRunner" in output["nodes"]["hotspots"]["text"]
    assert "All observed categories" in output["nodes"]["hotspot-note"]["text"]
