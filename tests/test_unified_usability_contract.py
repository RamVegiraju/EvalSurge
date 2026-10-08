"""Static request/result/CLI presentation contracts, with no agent/model traffic.

Metric documents below are schema inputs, not model completions or live benchmark
evidence. No provider, target transport, coordinator run or native judge is used.
"""

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError

from benchmark_agents.api import sanitized_validation_issues as api_issues
from benchmark_agents.v2_models import (
    Acknowledgment,
    AssessmentOutcome,
    EvaluationOutcome,
    Links,
    Report,
    Result,
    RunCreate,
    ScorerOutcome,
)
from benchmark_agents.validation import (
    RequestValidationError,
    sanitized_validation_issues,
    validate_request,
)
from evalsurge.cli import _public_capabilities, _summary, main

RUN_ID = UUID("51d78660-11d8-486c-8399-fd9e74da19ce")
PRIVATE = "private-user-value"


def _result(evaluation: dict[str, Any]) -> dict[str, Any]:
    """Build a static envelope without creating run state or target answers."""
    return {
        "id": str(RUN_ID),
        "status": "completed",
        "phases": {
            "planning": "completed",
            "inference": "passed",
            "evaluation_readiness": "skipped",
            "load": "completed",
            "profiling": "completed",
            "evaluation": "completed",
        },
        "links": Links.for_run(str(RUN_ID)).model_dump(),
        "summary": {"performance": "complete", "quality": "available"},
        "preflight": {"status": "passed"},
        "evaluation_preflight": {"status": "skipped"},
        "evaluation": evaluation,
    }


def test_typed_evaluation_preserves_partial_wire_documents_and_false_verdicts() -> None:
    for document in ({}, {"status": "no_ready_scorers", "results": [], "needs_data": []}):
        result = Result.model_validate(_result(document))
        assert isinstance(result.evaluation, EvaluationOutcome)
        assert result.model_dump()["evaluation"] == document
    document = {
        "status": "completed",
        "results": [
            {
                "scorer": "correctness",
                "status": "completed",
                "attempted": 1,
                "scored": 1,
                "pass_rate": 0,
                "assessments": [{"request_id": "record", "status": "failed", "value": False}],
            }
        ],
    }
    result = Result.model_validate(_result(document))
    assert result.status == "completed"
    assert result.evaluation.results[0].pass_rate == 0
    assert result.evaluation.results[0].assessments[0].value is False
    assert result.model_dump()["evaluation"] == document


def test_typed_outcomes_accept_failures_without_fabricating_coverage() -> None:
    assert ScorerOutcome(scorer="relevance", status="failed").coverage is None
    assert AssessmentOutcome(request_id="record", status="unavailable").value is None
    assert EvaluationOutcome(status="failed").request_coverage is None
    receipt = Acknowledgment(
        id=RUN_ID, status="cancellation_requested", links=Links.for_run(str(RUN_ID))
    )
    assert receipt.status == "cancellation_requested"
    with pytest.raises(ValidationError):
        Result.model_validate(_result({"status": "quality_passed"}))


def test_result_serialization_schema_remains_typed_despite_partial_wire_fields() -> None:
    schema = Result.model_json_schema(mode="serialization")
    assert schema["properties"]["evaluation"] == {"$ref": "#/$defs/EvaluationOutcome"}
    assert "ScorerOutcome" in schema["$defs"]
    assert "SamplingCoverage" in schema["$defs"]
    assert "AssessmentOutcome" in schema["$defs"]


def test_safe_validation_preserves_field_guidance_without_values() -> None:
    request = {
        "target": {"connection_id": "support"},
        "cases": [{"input": {"query": "hi"}}],
        "load": {"concurrency": 0},
        PRIVATE: PRIVATE,
    }
    with pytest.raises(RequestValidationError) as failure:
        validate_request(request)
    assert "load.concurrency" in str(failure.value)
    assert "greater than or equal to 1" in str(failure.value)
    assert PRIVATE not in str(failure.value) + repr(failure.value.errors())
    assert {
        "location": ["<extra>"],
        "code": "unsupported_field",
        "message": "Field is not supported",
    } in failure.value.errors()
    assert (
        validate_request(
            {"target": {"connection_id": "support"}, "cases": [{"input": {"query": "hi"}}]}
        ).evaluation.mode
        == "off"
    )


def test_typed_request_is_revalidated_after_bypassed_assignment_or_container_mutation() -> None:
    request = RunCreate(target={"connection_id": "support"}, cases=[{"input": {"query": "hi"}}])
    request.load.__dict__["concurrency"] = 0
    with pytest.raises(RequestValidationError) as failure:
        validate_request(request)
    assert "load.concurrency" in str(failure.value)
    request.load.__dict__["concurrency"] = 1
    request.cases.clear()
    with pytest.raises(RequestValidationError) as failure:
        validate_request(request)
    assert "cases" in str(failure.value)


@pytest.mark.parametrize("value", [False, True, 0, 1, 0.0, 0.25, "false", "uncertain", None])
def test_assessment_scalar_variant_retains_native_type_without_truthiness_conversion(
    value: Any,
) -> None:
    item = AssessmentOutcome(request_id="record", status="scored", value=value)
    assert type(item.value) is type(value)
    assert item.value == value


def test_every_source_evaluator_return_variant_remains_readable_as_typed_evidence() -> None:
    diagnostic = {
        "code": "assessment_missing",
        "message": "The assessment is unavailable.",
        "guidance": "Check scorer configuration.",
        "scorer": "relevance",
    }
    coverage = {
        "policy": "case-time-stratified-v1",
        "seed": 42,
        "time_bins": 4,
        "observed_dispatch_window_ms": 0,
        "eligible": 0,
        "selected": 0,
        "fraction_of_eligible": 0,
        "eligible_strata": 0,
        "selected_strata": 0,
        "strata": [],
    }
    missing = {
        "scorer": "groundedness",
        "status": "needs_data",
        "reason": "Evidence missing.",
        "required_fields": ["trace"],
        "eligible_samples": 0,
        "total_samples": 1,
    }
    variants = [
        {"status": "no_ready_scorers", "results": [], "needs_data": [missing]},
        {"status": "needs_configuration", "required": ["DATABRICKS_CONFIG_PROFILE"], "results": []},
        {"status": "configuration_changed", "results": []},
        {
            "status": "completed_with_errors",
            "results": [{"scorer": "registered:policy", "status": "configuration_changed"}],
        },
        {
            "status": "completed_with_errors",
            "results": [{"scorer": "relevance", "status": "needs_configuration"}],
        },
        {
            "status": "completed_with_errors",
            "results": [
                {
                    "scorer": "relevance",
                    "status": "no_eligible_outputs",
                    "scored": 0,
                    "coverage": coverage,
                }
            ],
        },
        {"status": "failed", "error": diagnostic, "error_type": "RuntimeError"},
        {
            "status": "completed_with_errors",
            "results": [
                {
                    "scorer": "relevance",
                    "status": "failed",
                    "attempted": 1,
                    "scored": 0,
                    "judge_errors": 1,
                    "error": diagnostic,
                    "request_ids": ["record"],
                    "assessments": [
                        {
                            "request_id": "record",
                            "case_id": 0,
                            "status": "error",
                            "value": None,
                            "rationale": None,
                            "rationale_truncated": False,
                            "error": diagnostic,
                        }
                    ],
                    "coverage": coverage,
                }
            ],
        },
    ]
    for document in variants:
        result = Result.model_validate(_result(document))
        assert result.model_dump()["evaluation"] == document


def test_api_and_sdk_sanitizers_share_exact_bounded_policy() -> None:
    from fastapi.exceptions import RequestValidationError as APIValidationError

    errors = [
        {
            "loc": ("body", "cases", 0, "input", PRIVATE),
            "type": "value_error",
            "msg": PRIVATE,
            "input": PRIVATE,
            "ctx": {"error": ValueError(PRIVATE)},
        }
    ] * 30
    assert api_issues(APIValidationError(errors)) == sanitized_validation_issues(errors)
    assert len(sanitized_validation_issues(errors)) == 20
    assert PRIVATE not in repr(sanitized_validation_issues(errors))


def test_cli_validation_reports_invalid_field_before_any_client(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "run.json"
    path.write_text(
        json.dumps(
            {
                "target": {"connection_id": "support"},
                "cases": [{"input": {"query": "hi"}}],
                "load": {"concurrency": 0},
            }
        )
    )
    assert main(["run", str(path)]) == 2
    output = capsys.readouterr()
    assert "load.concurrency" in output.err
    assert "finite JSON" not in output.err


def test_cli_metric_summary_reports_unknowns_and_not_quality_pass(
    capsys: pytest.CaptureFixture[str],
) -> None:
    document = _result(
        {
            "status": "completed",
            "results": [
                {
                    "scorer": "correctness",
                    "status": "completed",
                    "scored": 1,
                    "pass_rate": 0,
                    "coverage": {"selected": 1},
                    "rationale": PRIVATE,
                }
            ],
        }
    )
    document["metrics"] = {
        "timing_successful_only": {"latency_ms": {"p50": 10, "p95": 20, "p99": 30}},
        "successful_tps": 2,
        "completed_tps": 2,
        "error_rate": 0,
        "token_usage_coverage": 0,
        "measurement_complete": True,
    }
    _summary({"run": document})
    output = capsys.readouterr().out
    assert "Latency" in output and "20.00" in output and "30.00" in output
    assert "Answer-text TTFT" in output and "unavailable" in output
    assert "0.0%" in output and "no CI threshold" in output
    assert PRIVATE not in output


def test_discovery_json_projects_only_public_configured_metadata() -> None:
    public = _public_capabilities(
        {
            "api_version": "v2",
            "secret": PRIVATE,
            "targets": [
                {"name": "support", "protocols": ["http-json", PRIVATE], "url": PRIVATE},
                {"name": "control\nsequence", "protocols": ["http-json"]},
            ],
            "evaluation": {"planner": "configured", "catalog_judges": PRIVATE},
            "tracing": {"readiness": "disabled", "profile": PRIVATE},
        }
    )
    assert public["targets"] == [{"name": "support", "protocols": ["http-json"]}]
    assert PRIVATE not in json.dumps(public)
    assert public["runtime_verified"] is False


def test_local_target_discovery_loads_operator_settings_without_traffic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("BENCHMARK_CONFIG", raising=False)
    path = tmp_path / "operator.toml"
    path.write_text(
        '[connections.support]\nurl = "http://127.0.0.1:9001/chat"\nprotocols = ["openai-chat"]\n'
    )
    assert main(["targets", "--local", "--settings", str(path), "--json"]) == 0
    public = json.loads(capsys.readouterr().out)
    assert public == {
        "targets": [{"name": "support", "protocols": ["openai-chat"]}],
        "runtime_verified": False,
    }


def test_local_browser_request_is_rejected_before_run_admission(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["run", str(tmp_path / "absent.json"), "--local", "--open-report"]) == 2
    assert "API report server" in capsys.readouterr().err


def test_cli_json_is_single_machine_readable_document_with_explicit_protected_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from evalsurge.remote import RemoteClient

    config = tmp_path / "run.json"
    config.write_text(
        json.dumps({"target": {"connection_id": "support"}, "cases": [{"input": {"query": "hi"}}]})
    )

    def transport(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"id": str(RUN_ID), "status": "queued"})
        if request.url.path.endswith("/report"):
            return httpx.Response(
                200,
                json={
                    "run": {"id": str(RUN_ID), "status": "completed", "protected_evidence": PRIVATE}
                },
            )
        return httpx.Response(200, json={"id": str(RUN_ID), "status": "completed"})

    def client(*args: Any, **kwargs: Any) -> RemoteClient:
        return RemoteClient(*args, **kwargs, transport=httpx.MockTransport(transport))

    assert main(["run", str(config), "--wait", "--json"], client_factory=client) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["run"]["protected_evidence"] == PRIVATE
    assert output.err == ""


def test_local_cli_json_failure_returns_report_without_starting_a_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercise only CLI exception presentation using static run metadata, not inference."""
    from evalsurge.client import RunFailed
    from evalsurge.local import Client

    config = tmp_path / "run.json"
    config.write_text(
        json.dumps({"target": {"connection_id": "support"}, "cases": [{"input": {"query": "hi"}}]})
    )
    run = _result({"status": "failed", "error_type": "RuntimeError"})
    run["status"] = "failed"
    report = Report.model_validate(
        {
            "run": run,
            "profiling": {"total_requests": 0, "traced_requests": 0, "coverage": 0},
            "requests": [],
            "offset": 0,
            "limit": 25,
            "total": 0,
        }
    )

    def unavailable(*args: Any, **kwargs: Any) -> Any:
        raise RunFailed(report)

    monkeypatch.setattr(Client, "start", unavailable)
    monkeypatch.delenv("BENCHMARK_CONFIG", raising=False)
    assert (
        main(
            ["run", str(config), "--local", "--json", "--artifact-dir", str(tmp_path / "artifacts")]
        )
        == 1
    )
    output = capsys.readouterr()
    assert json.loads(output.out)["run"]["status"] == "failed"
    assert "inspect retained local report" in output.err
