"""Execute report JavaScript with a bounded DOM fixture, without a model or browser."""

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from evalsurge.remote import RemoteClient

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


def test_report_shows_safe_mlflow_experiment_links(evidence) -> None:
    evidence["mlflow_experiments"] = [
        {
            "experiment_id": "123",
            "url": "https://workspace.example/ml/experiments/123",
            "scopes": ["traces", "evaluation"],
        },
        {
            "experiment_id": "456",
            "url": "http://127.0.0.1:5000/#/experiments/456",
            "scopes": ["evaluation"],
        },
    ]
    output = render(evidence)
    links = output["nodes"]["mlflow-links"]["children"]
    assert len(links) == 2
    assert "123" in links[0]["text"]
    assert "traces" in links[0]["text"].lower()
    assert "evaluation" in links[0]["text"].lower()
    assert links[0]["attributes"] == {
        "href": "https://workspace.example/ml/experiments/123",
        "target": "_blank",
        "rel": "noopener noreferrer",
        "referrerpolicy": "no-referrer",
    }
    assert len(output["calls"]) == 1
    assert "private-test-key" not in json.dumps(links)


def test_remote_report_url_autoloads_the_shipped_renderer(evidence: dict[str, Any]) -> None:
    """SDK/browser links must use the real renderer's query and prefix contract."""
    with RemoteClient("https://api.example/prefix", api_key="private-test-key") as client:
        url = client.report_url(evidence["run"]["id"])
    output = render(evidence, origin=url, autoload=True)
    assert len(output["calls"]) == 1
    assert output["calls"][0]["url"] == (
        f"/prefix/v1/runs/{evidence['run']['id']}/report?offset=0&limit=25"
    )
    assert output["calls"][0]["options"]["headers"] == {}
    assert not output["nodes"]["report"]["hidden"]
    assert evidence["run"]["id"] in output["nodes"]["message"]["text"]
    assert "private-test-key" not in url + json.dumps(output["history"])


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,secret",
        "//tracking.example",
        "https://user:secret@tracking.example",
        "http://remote.example/#/experiments/1",
        "https://tracking.example?token=secret",
        "https://tracking.example\\@other.example",
    ],
)
def test_report_never_links_unsafe_mlflow_destinations(evidence, url) -> None:
    evidence["mlflow_experiments"] = [{"experiment_id": "123", "url": url, "scopes": ["traces"]}]
    output = render(evidence)
    links = output["nodes"]["mlflow-links"]
    assert all(child["tag"] != "a" for child in links["children"])
    assert "not configured" in links["text"].lower()


def test_historical_report_without_mlflow_links_remains_renderable(evidence) -> None:
    output = render(evidence)
    assert "not configured" in output["nodes"]["mlflow-links"]["text"].lower()
    assert "1.20req/s" in output["nodes"]["metrics"]["text"]


def test_historical_report_does_not_assume_generator_health(evidence) -> None:
    """Rendering-only evidence; no agent, provider or target invocation."""
    text = render(evidence)["nodes"]["generator-health"]["text"]
    assert "historical or missing" in text
    assert "Do not assume an unsaturated runner" in text


def test_report_generator_observations_are_not_an_accuracy_badge(evidence) -> None:
    """Only fixed labels and numeric timing data are rendered, not raw diagnostics."""
    from tests.test_generator_presentation import observations

    health = observations(degraded=True)
    health["limitations"] = ["private-provider-message"]
    health["journal"]["path"] = "private-path"
    evidence["run"]["metrics"]["generator_health"] = health
    text = render(evidence)["nodes"]["generator-health"]["text"]
    assert "Generator health: degraded" in text
    assert "not verified accuracy" in text
    assert "mean 1.25 ms" in text
    assert "Journal drained: no" in text
    assert "do not sum" in text
    assert "Journal backpressure observed" in text
    assert "may be generator-limited" in text
    assert "private" not in text


def test_report_does_not_hide_successful_only_timing_coverage(evidence) -> None:
    """Displayed tails retain observation counts and disclose omitted failures."""
    timing = evidence["run"]["metrics"]["timing_successful_only"]
    timing["latency_ms"]["count"] = 3
    timing["ttft_ms"] = {"count": 2, "p50": 20, "p95": 40, "p99": 40}
    evidence["run"]["metrics"]["requests"] = 4
    text = render(evidence)["nodes"]["metrics"]["text"]
    assert "3 successful observations / 4 attempts" in text
    assert "2 successful observations / 4 attempts" in text
    assert "Failures and timeouts excluded" in text
    assert "not first response byte" in text


def test_report_shows_each_failed_quality_reason_and_safe_execution_error(evidence) -> None:
    result = evidence["run"]["evaluation"]["results"][0]
    result["assessments"] = [
        {
            "request_id": "failed-request",
            "case_id": 2,
            "status": "failed",
            "value": False,
            "rationale": "<img src=x onerror=alert(1)> Missed the deadline.",
            "rationale_truncated": False,
            "error": None,
        },
        {
            "request_id": "errored-request",
            "case_id": 3,
            "status": "error",
            "value": None,
            "rationale": None,
            "error": {
                "code": "judge_rate_limited",
                "message": "The judge provider rate-limited the assessment.",
                "guidance": "Check provider quotas.",
            },
        },
        {
            "request_id": "passed-request",
            "status": "passed",
            "rationale": "Accurate.",
        },
    ]
    output = render(evidence)
    text = output["nodes"]["assessment-details"]["text"]
    assert "failed-request" in text
    assert "Case 2" in text
    assert "Quality failed" in text
    assert "<img src=x onerror=alert(1)> Missed the deadline." in text
    assert "Judge error" in text
    assert "errored-request" in text
    assert "judge_rate_limited" in text
    assert "passed-request" not in text


def test_report_explains_missing_and_truncated_rationales(evidence) -> None:
    result = evidence["run"]["evaluation"]["results"][0]
    result["assessments"] = [
        {"request_id": "first", "status": "failed", "rationale": None},
        {
            "request_id": "second",
            "status": "failed",
            "rationale": "Bounded reason",
            "rationale_truncated": True,
        },
    ]
    text = render(evidence)["nodes"]["assessment-details"]["text"]
    assert "did not record a rationale" in text
    assert "truncated" in text


def test_historical_report_does_not_invent_per_request_reasons(evidence) -> None:
    text = render(evidence)["nodes"]["assessment-details"]["text"]
    assert "not recorded" in text


def test_failed_preflight_report_shows_error_instead_of_benchmark_success(evidence) -> None:
    evidence["run"].update(
        status="failed",
        load_status="skipped",
        profiling_status="skipped",
        evaluation_status="skipped",
        metrics={},
        evaluation={},
        preflight={
            "status": "failed",
            "request_id": "probe",
            "http_status": 401,
            "error": {
                "code": "target_http_error",
                "message": "Inference preflight failed. Load test did not start. Check target access.",
            },
        },
    )
    evidence["requests"] = []
    evidence["total"] = 0
    evidence["profiling"].update(
        total_requests=0,
        traced_requests=0,
        coverage=0,
        hotspots=[],
        gaps={},
    )
    output = render(evidence)
    assert "Load test did not start" in output["nodes"]["message"]["text"]
    assert "Inference check failed" in output["nodes"]["context"]["text"]
    assert "target_http_error" in output["nodes"]["context"]["text"]
    assert "HTTP 401" in output["nodes"]["context"]["text"]
    assert "Skipped" in output["nodes"]["judges"]["text"]
    assert "No internal hotspot evidence" in output["nodes"]["hotspots"]["text"]


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


@pytest.mark.parametrize(
    "status",
    ["not_run", "skipped", "pending", "running", "passed", "failed", "cancelled", "interrupted"],
)
def test_evaluation_preflight_checks_are_excluded_from_quality_scores(
    evidence: dict[str, Any], status: str
) -> None:
    evidence["run"]["evaluation_preflight"] = {
        "status": status,
        "checked_scorers": ["relevance", "registered:grounding"],
    }
    evidence["run"]["evaluation"] = {"status": "pending", "results": []}
    evidence["run"]["evaluation_status"] = "pending"
    output = render(evidence)
    context = output["nodes"]["context"]["text"]
    assert f"Evaluation preflight{status.replace('_', ' ').capitalize()}" in context
    assert "Checked scorers: relevance, registered:grounding" in context
    assert "readiness checks, excluded from quality scores" in context
    assert "Criteria with assessments0 / 2" in output["nodes"]["evaluation-summary"]["text"]
    assert "Distinct answers selected—" in output["nodes"]["evaluation-summary"]["text"]
    assert "No assessments" in output["nodes"]["judges"]["text"]
    assert "boolean pass rate" not in output["nodes"]["judges"]["text"]
    assert "1.20req/s" in output["nodes"]["metrics"]["text"]


@pytest.mark.parametrize("metrics", [{}, {"requests": 0, "successful_requests": 0}])
def test_failed_evaluation_preflight_report_preserves_zero_load(
    evidence: dict[str, Any], metrics: dict[str, Any]
) -> None:
    diagnostic = {
        "code": "judge_access_denied",
        "message": "The configured judge could not be accessed.",
        "guidance": "Ask the operator to grant access to the frozen judge endpoint.",
        "scorer": "relevance",
        "http_status": 403,
    }
    evidence["run"].update(
        status="failed",
        load_status="skipped",
        profiling_status="skipped",
        evaluation_status="skipped",
        metrics=metrics,
        evaluation={},
        evaluation_preflight={
            "status": "failed",
            "error": diagnostic,
            "checked_scorers": ["relevance"],
        },
    )
    evidence["requests"] = []
    evidence["total"] = 0
    evidence["profiling"].update(
        total_requests=0, traced_requests=0, coverage=0, hotspots=[], gaps={}
    )
    output = render(evidence)
    assert not output["nodes"]["report"]["hidden"]
    assert "Evaluation preflight failed — load never started" in output["nodes"]["message"]["text"]
    context = output["nodes"]["context"]["text"]
    assert "Evaluation preflight failed — load never started" in context
    for field in ("code", "message", "guidance"):
        assert diagnostic[field] in context
    assert "Scorer: relevance" in context and "HTTP 403" in context
    assert "Inference check failed" not in context
    assert "Criteria with assessments0 / 2" in output["nodes"]["evaluation-summary"]["text"]
    assert "Skipped" in output["nodes"]["judges"]["text"]
    assert "boolean pass rate" not in output["nodes"]["judges"]["text"]
    assert "0 successful / 0 attempts" in output["nodes"]["metrics"]["text"]
    assert "Successful throughput—req/s" in output["nodes"]["metrics"]["text"]
    assert output["nodes"]["page"]["text"] == "0–0 of 0 attempts"
    assert not output["nodes"]["waterfall"]["children"]
    assert "No internal hotspot evidence" in output["nodes"]["hotspots"]["text"]


def test_runtime_evaluation_failure_keeps_load_metrics(evidence: dict[str, Any]) -> None:
    diagnostic = {
        "code": "judge_unavailable",
        "message": "The configured judge is unavailable.",
        "guidance": "Ask the operator to check judge availability before a new run.",
        "http_status": 503,
    }
    evidence["run"]["evaluation_status"] = "failed"
    evidence["run"]["evaluation"] = {"status": "failed", "error": diagnostic, "results": []}
    output = render(evidence)
    assert "Evaluation failed" in output["nodes"]["message"]["text"]
    context = output["nodes"]["context"]["text"]
    assert "Evaluation failed" in context and "HTTP 503" in context
    for field in ("code", "message", "guidance"):
        assert diagnostic[field] in context
    assert "load did not start" not in context.lower()
    assert "1.20req/s" in output["nodes"]["metrics"]["text"]
    assert "100ms" in output["nodes"]["metrics"]["text"]
    assert "2 successful / 2 attempts" in output["nodes"]["metrics"]["text"]
    assert "Criteria with assessments0 / 2" in output["nodes"]["evaluation-summary"]["text"]
    assert "boolean pass rate" not in output["nodes"]["judges"]["text"]


@pytest.mark.parametrize(
    "code,status,title",
    [
        ("worker_start_failed", "failed", "Load worker could not start"),
        ("worker_failed", "failed", "Load worker failed"),
        ("worker_timeout", "interrupted", "Load worker timed out"),
    ],
)
def test_load_worker_failure_is_actionable_without_changing_measurements(
    evidence: dict[str, Any], code: str, status: str, title: str
) -> None:
    diagnostic = {
        "code": code,
        "message": "The load worker could not complete this run.",
        "guidance": "Check the runner environment and protected worker logs before retrying.",
    }
    evidence["run"].update(
        status=status,
        load_status=status,
        load_error=diagnostic,
        preflight={"status": "passed"},
        evaluation_preflight={"status": "passed", "checked_scorers": ["relevance"]},
        evaluation_status="skipped",
        evaluation={"status": "skipped", "results": []},
    )
    if code == "worker_start_failed":
        evidence["run"].update(metrics={}, profiling_status="skipped")
        evidence["requests"] = []
        evidence["total"] = 0
        evidence["profiling"].update(
            total_requests=0, traced_requests=0, coverage=0, hotspots=[], gaps={}
        )
    output = render(evidence)
    assert not output["nodes"]["report"]["hidden"]
    assert title in output["nodes"]["message"]["text"]
    context = output["nodes"]["context"]["text"]
    assert f"{title}{status.capitalize()}" in context
    for field in ("code", "message", "guidance"):
        assert diagnostic[field] in context
    assert "Inference preflightPassed" in context and "Evaluation preflightPassed" in context
    assert "Inference check failed" not in context and "Evaluation failed" not in context
    assert "Criteria with assessments0 / 2" in output["nodes"]["evaluation-summary"]["text"]
    assert "Skipped" in output["nodes"]["judges"]["text"]
    assert "boolean pass rate" not in output["nodes"]["judges"]["text"]
    metrics = output["nodes"]["metrics"]["text"]
    if code == "worker_start_failed":
        assert "Successful throughput—req/s" in metrics
        assert "0 successful / 0 attempts" in metrics
        assert output["nodes"]["page"]["text"] == "0–0 of 0 attempts"
        assert not output["nodes"]["waterfall"]["children"]
    else:
        assert "1.20req/s" in metrics and "100ms" in metrics
        assert "2 successful / 2 attempts" in metrics
        assert output["nodes"]["page"]["text"] == "1–2 of 2 attempts"
        assert "Generation" in output["nodes"]["waterfall"]["text"]


def test_load_worker_diagnostics_are_text_only(evidence: dict[str, Any]) -> None:
    diagnostic = {
        "code": "worker_failed",
        "message": "<img src=x onerror=alert('worker')>",
        "guidance": "<a href=javascript:alert('guidance')>fix</a>",
    }
    evidence["run"].update(status="failed", load_status="failed", load_error=diagnostic)
    output = render(evidence)
    context = output["nodes"]["context"]
    assert "Load worker failed" in output["nodes"]["message"]["text"]
    for field in ("code", "message", "guidance"):
        assert diagnostic[field] in context["text"]
    pending = [context]
    while pending:
        node = pending.pop()
        assert node["tag"] not in {"script", "img", "a", "svg"}
        assert not node["attributes"]
        pending.extend(node["children"])
    assert len(output["calls"]) == 1
    assert "private-test-key" not in json.dumps(output["history"])


def test_incomplete_load_worker_diagnostic_uses_safe_fallback(evidence: dict[str, Any]) -> None:
    evidence["run"].update(
        status="failed",
        load_status="failed",
        load_error={"code": "worker_failed", "message": "private exception details"},
    )
    output = render(evidence)
    context = output["nodes"]["context"]["text"]
    assert "Load worker failed" in context
    assert "Safe load diagnostic details were not recorded." in context
    assert "Ask the operator to review load-worker configuration and protected logs" in context
    assert "private exception details" not in json.dumps(output["nodes"])


@pytest.mark.parametrize("status,scored", [("failed", 0), ("partial", 1)])
def test_criterion_diagnostics_preserve_recorded_outcomes(
    evidence: dict[str, Any], status: str, scored: int
) -> None:
    diagnostic = {
        "code": "judge_timeout",
        "message": "A judge assessment did not finish within its deadline.",
        "guidance": "Review the frozen judge timeout and endpoint health.",
        "scorer": "relevance",
    }
    result = evidence["run"]["evaluation"]["results"][0]
    result.update(
        status=status,
        attempted=2,
        scored=scored,
        judge_errors=2 - scored,
        pass_rate=0 if scored else None,
        metrics={"relevance/mean": 0} if scored else {},
        error=diagnostic,
    )
    output = render(evidence)
    context = output["nodes"]["context"]["text"]
    assert "Evaluation criterion error: Relevance" in context
    assert status.capitalize() in context
    text = output["nodes"]["judges"]["text"]
    for field in ("code", "message", "guidance"):
        assert diagnostic[field] in context and diagnostic[field] in text
    assert f"{scored} / 2 selected scored" in text
    assert f"{2 - scored} judge error" in text
    assert ("boolean pass rate" in text) == bool(scored)
    assert ("0.0%" if scored else "No assessments") in text
    assert "1.20req/s" in output["nodes"]["metrics"]["text"]


def test_legacy_evaluation_failure_uses_fixed_safe_fallback(evidence: dict[str, Any]) -> None:
    evidence["run"]["evaluation_status"] = "failed"
    evidence["run"]["evaluation"] = {
        "status": "failed",
        "error_type": "RuntimeError: private exception <script>alert(1)</script>",
        "message": "private exception message",
    }
    output = render(evidence)
    assert "Evaluation failed" in output["nodes"]["message"]["text"]
    context = output["nodes"]["context"]["text"]
    assert "diagnostic_unavailable" in context
    assert "Safe evaluation diagnostic details were not recorded." in context
    assert "Ask the operator to review judge configuration and protected logs" in context
    assert "private exception" not in json.dumps(output["nodes"])
    assert "Criteria with assessments0 / 2" in output["nodes"]["evaluation-summary"]["text"]
    assert "No assessments" in output["nodes"]["judges"]["text"]
    assert "Evaluation preflightNot run" in context


def test_evaluation_diagnostics_are_text_only(evidence: dict[str, Any]) -> None:
    diagnostic = {
        "code": "<script>alert('code')</script>",
        "message": "<img src=x onerror=alert('message')>",
        "guidance": "<a href=javascript:alert('guidance')>fix</a>",
        "scorer": "<svg onload=alert('scorer')>",
        "http_status": 403,
    }
    evidence["run"]["evaluation_preflight"] = {
        "status": "failed",
        "checked_scorers": [diagnostic["scorer"]],
        "error": diagnostic,
    }
    evidence["run"]["evaluation"].update(status="failed", error=diagnostic)
    evidence["run"]["evaluation"]["results"][0].update(status="partial", error=diagnostic)
    output = render(evidence)
    context = output["nodes"]["context"]
    judges = output["nodes"]["judges"]
    for field in ("code", "message", "guidance", "scorer"):
        assert diagnostic[field] in context["text"]
        assert diagnostic[field] in judges["text"]
    pending = [context, judges]
    while pending:
        node = pending.pop()
        assert node["tag"] not in {"script", "img", "a", "svg"}
        assert not node["attributes"]
        pending.extend(node["children"])
    assert len(output["calls"]) == 1
    assert "private-test-key" not in json.dumps(output["history"])


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
