"""Pure metadata presentation checks; no agent, inference, network or file output."""

import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from evalsurge import Report, Result, format_summary
from evalsurge.cli import _summary


def result_document() -> dict[str, Any]:
    """Describe numeric DTO observations only, not recorded agent/model evidence."""
    return {
        "id": "0c6ef53f-8aaf-440e-a6ef-971947e226da",
        "name": "private-display-name",
        "status": "completed_with_gaps",
        "phases": {
            "planning": "completed",
            "inference": "passed",
            "evaluation_readiness": "passed",
            "load": "completed",
            "profiling": "skipped",
            "evaluation": "completed_with_errors",
        },
        "links": {key: "private-link" for key in ("status", "result", "report", "cancel")},
        "summary": {
            "performance": "complete",
            "quality": "available",
            "evidence_gaps": ["evaluation_unavailable", "generator_health_unavailable"],
        },
        "metrics": {
            "requests": 4,
            "successful_requests": 3,
            "error_rate": 0.25,
            "successful_tps": 1.5,
            "completed_tps": 2.0,
            "elapsed_seconds_including_drain": 2,
            "dispatch_seconds": 1,
            "token_usage_coverage": 0,
            "reported_output_tokens_per_second": None,
            "timing_successful_only": {
                "latency_ms": {"count": 3, "p50": 40, "p95": 80, "p99": 80},
                "ttft_ms": {"count": 0, "p50": None, "p95": None, "p99": None},
            },
            "errors": {"private-error": 1},
            "measurement_complete": True,
        },
        "preflight": {},
        "evaluation_preflight": {},
        "evaluation": {
            "status": "completed_with_errors",
            "judge_model": "private-model",
            "request_coverage": {"total": 4, "successful": 3, "failed": 1},
            "results": [
                {
                    "scorer": "correctness",
                    "status": "partial",
                    "attempted": 3,
                    "scored": 2,
                    "judge_errors": 1,
                    "pass_rate": 0,
                    "assessments": [
                        {
                            "request_id": "private-request",
                            "status": "failed",
                            "value": False,
                            "rationale": "private-rationale",
                        }
                    ],
                    "coverage": {
                        "policy": "private-policy",
                        "seed": 42,
                        "time_bins": 1,
                        "observed_dispatch_window_ms": 1000,
                        "eligible": 3,
                        "selected": 3,
                        "fraction_of_eligible": 1,
                        "eligible_strata": 1,
                        "selected_strata": 1,
                        "strata": [],
                    },
                }
            ],
        },
    }


def test_typed_result_report_and_mapping_have_identical_summary(capsys) -> None:
    """One renderer serves the typed public API and legacy CLI presentation."""
    result = Result.model_validate(result_document())
    report = Report(
        run=result,
        profiling={"total_requests": 4, "traced_requests": 0, "coverage": 0},
        requests=[],
        offset=0,
        limit=25,
        total=4,
    )
    before = report.model_dump(mode="json")
    expected = format_summary(result)
    assert format_summary(report) == expected
    assert format_summary(result.model_dump(mode="json")) == expected
    assert format_summary(report.model_dump(mode="json")) == expected
    _summary(report.model_dump(mode="json"))
    assert capsys.readouterr().out == expected + "\n"
    assert report.model_dump(mode="json") == before
    assert "private" not in expected


def test_summary_preserves_quality_error_and_measurement_distinctions() -> None:
    """Lifecycle completion never means all attempts or quality passed."""
    output = format_summary(Result.model_validate(result_document()))
    assert "Lifecycle: completed_with_gaps." in output
    assert "Performance: complete." in output
    assert "Quality evidence: available." in output
    assert "Evaluation: completed_with_errors." in output
    assert "Judge execution: partial." in output
    assert "errors    pass rate" in output
    assert "0.0%" in output
    assert "3.00 successful observations / 4.00 total attempts" in output
    assert "1.00 failed attempts excluded from judging" in output
    assert "25.0%" in output
    assert "Throughput includes drain" in output
    assert "Failed and timed-out attempts are excluded" in output
    assert "separate from quality passing" in output
    assert "sustainable capacity" in output


def test_unknown_usage_and_ttft_are_not_known_zero() -> None:
    """Missing tokens/timing remain unknown; explicit zero remains observable."""
    result = result_document()
    unknown = format_summary(result)
    assert "Token-usage coverage: 0.0%." in unknown
    assert "Reported output tokens: unavailable tokens/s." in unknown
    assert "Answer-text TTFT             unavailable" in unknown
    result["metrics"]["reported_output_tokens_per_second"] = 0
    assert "Reported output tokens: 0.00 tokens/s." in format_summary(result)


@pytest.mark.parametrize(
    "unsafe", ["\x1b[31msecret", "secret\nforged", "secret\rforged", "secret\x00", "secret\u202e"]
)
def test_untrusted_labels_and_guidance_are_never_emitted(unsafe: str) -> None:
    """Control sequences and untrusted source fields cannot forge terminal lines."""
    result = result_document()
    result["status"] = unsafe
    result["phases"]["inference"] = unsafe
    result["summary"]["quality"] = unsafe
    result["summary"]["evidence_gaps"].append(unsafe)
    result["evaluation"]["results"][0]["scorer"] = unsafe
    result["evaluation"]["results"][0]["status"] = unsafe
    result["evaluation"]["results"][0]["error"] = {"message": unsafe}
    result["evidence"] = {
        "answer_evaluation": {"configured": True, "state": unsafe, "guidance": unsafe}
    }
    before = deepcopy(result)
    output = format_summary(result)
    assert "secret" not in output
    assert "private" not in output
    assert "\x1b" not in output
    assert "\r" not in output
    assert "\x00" not in output
    assert "\u202e" not in output
    assert "<unknown>" in output
    assert "Lifecycle: unknown." in output
    assert result == before


@pytest.mark.parametrize("bad", [None, [], "private-input", 3, object()])
def test_unsupported_top_level_input_raises_fixed_diagnostic(bad: Any) -> None:
    """Failure does not stringify a user's arbitrary object or source data."""
    with pytest.raises(TypeError, match="Summary requires a v2 Result, Report") as error:
        format_summary(bad)
    assert "private" not in str(error.value)


@pytest.mark.parametrize("bad", [True, "private-number", float("inf"), float("nan"), 10**400])
def test_malformed_legacy_observations_stay_unavailable(bad: Any) -> None:
    """Legacy documents cannot present booleans/secrets/nonfinite values as measurements."""
    output = format_summary({"metrics": {"successful_tps": bad}})
    assert "Successful throughput: unavailable requests/s." in output
    assert "private" not in output
    assert "nan" not in output
    assert " inf" not in output


def test_missing_fields_do_not_invent_evidence_or_generator_health() -> None:
    """Historical documents remain usable with unknown metadata."""
    assert format_summary({"run": {}}) == "Performance metrics: unavailable."
    output = format_summary({"metrics": {}})
    assert "Generator health: unavailable" in output
    assert "Coverage: unavailable successful observations / unavailable total attempts" in output


@pytest.mark.parametrize("large", [1e308, 10**307])
def test_percentage_overflow_is_unavailable(large: int | float) -> None:
    """Formatting a malformed finite legacy fraction cannot introduce infinity."""
    output = format_summary({"metrics": {"error_rate": large}})
    assert "Error rate: unavailable." in output
    assert "inf%" not in output


def test_legacy_scorer_count_is_bounded_and_disclosed() -> None:
    """Unexpected legacy criterion lists cannot make terminal output unbounded."""
    result = result_document()
    result["evaluation"]["results"] *= 3
    result["evaluation"]["results"] *= 4
    output = format_summary(result)
    assert output.count("Judge execution: partial.") == 10
    assert "Additional criteria omitted" in output


def test_summary_public_import_does_not_import_server_dependencies() -> None:
    """The public renderer remains usable when the execution stack is unavailable."""
    repository = Path(__file__).resolve().parents[1]
    code = """
import importlib.abc
import sys

class RejectServerImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'mlflow', 'fastapi', 'locust', 'gevent', 'openai', 'databricks', 'requests'}:
            raise AssertionError('Unexpected server dependency import: ' + fullname)

sys.meta_path.insert(0, RejectServerImports())
sys.path.insert(0, sys.argv[1])
from evalsurge import format_summary
assert format_summary({'run': {}}) == 'Performance metrics: unavailable.'
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", code, str(repository)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
