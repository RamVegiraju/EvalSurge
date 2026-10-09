"""Pure selection/budget regressions; no framework, provider or target is invoked."""

import json
from pathlib import Path
from uuid import UUID

import pytest

from benchmark_agents.models import (
    EvaluationPreflight,
    PreflightError,
    PreflightResult,
    ProfilingSummary,
)
from benchmark_agents.v2_models import (
    DecisionSummary,
    Links,
    PhaseStates,
    Report,
    Result,
    RunStatus,
)
from scripts.validation.hosted_journeys import (
    execute,
    main,
    parse_options,
    plan_record,
    retrieval_evidence,
    scenario_passed,
)


def http_arguments() -> list[str]:
    """Return a declared endpoint selector, not a real agent or fixture completion."""
    return [
        "--target",
        "http",
        "--framework",
        "customer-owned-framework",
        "--model",
        "operator-selected-model",
        "--url",
        "http://127.0.0.1:9001/benchmark",
    ]


def test_plan_needs_no_framework_install_or_credentials() -> None:
    """Framework labels are evidence declarations, never SDK imports/allowlists."""
    record = plan_record(parse_options(http_arguments()))
    assert record["declared_framework"] == "customer-owned-framework"
    assert record["max_total_target_attempts"] == 6
    assert record["evaluation_mode"] == "off"
    assert record["actual_inference_operator_attested"] is False
    assert record["target_source_automatically_verified"] is False
    assert record["monetary_quota_enforced"] is False


@pytest.mark.parametrize("value", ["nan", "inf", "0", "181"])
def test_dispatch_duration_is_finite_and_bounded(value: str) -> None:
    """Reject unbounded duration before auth, model calls or artifact creation."""
    with pytest.raises(SystemExit):
        parse_options([*http_arguments(), "--duration", value])


@pytest.mark.parametrize("value", ["0", "6", "100"])
def test_concurrency_does_not_exceed_approved_harness_ceiling(value: str) -> None:
    with pytest.raises(SystemExit):
        parse_options([*http_arguments(), "--concurrency", value])


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/benchmark",
        "https://user:secret@example.com/benchmark",
        "https://example.com/benchmark?token=secret",
        "https://example.com/benchmark#secret",
    ],
)
def test_secret_bearing_or_nonlocal_plaintext_targets_are_rejected(url: str) -> None:
    arguments = http_arguments()
    arguments[-1] = url
    with pytest.raises(SystemExit):
        parse_options(arguments)


def test_app_profile_is_explicit_and_mixed_targets_are_rejected() -> None:
    arguments = [
        "--target",
        "app",
        "--framework",
        "langgraph",
        "--model",
        "selected-model",
        "--app-name",
        "test-eval-ram",
    ]
    with pytest.raises(SystemExit):
        parse_options(arguments)
    options = parse_options([*arguments, "--profile", "e2-demo-field-eng"])
    assert plan_record(options)["profile"] == "e2-demo-field-eng"
    with pytest.raises(SystemExit):
        parse_options([*http_arguments(), "--profile", "e2-demo-field-eng"])


def test_remote_request_selects_registered_target_not_profile() -> None:
    options = parse_options(
        [
            "--target",
            "remote",
            "--framework",
            "crewai",
            "--model",
            "selected-model",
            "--service-url",
            "https://example.com/",
            "--connection-id",
            "approved-agent",
            "--api-key-env",
            "EVALSURGE_SERVICE_KEY",
        ]
    )
    record = plan_record(options)
    assert record["runner_location"] == "service host"
    assert record["connection_id"] == "approved-agent"
    assert "api_key_env" not in record
    assert "service_url" not in record


def test_live_requires_consent_attestation_identity_and_fresh_storage(tmp_path: Path) -> None:
    """Intentional pre-provider rejection does not substitute model inference."""
    with pytest.raises(SystemExit):
        parse_options([*http_arguments(), "--live"])
    options = parse_options(
        [
            *http_arguments(),
            "--live",
            "--accept-paid-traffic",
            "--real-inference-attested",
            "--source-revision",
            "reviewed-target-commit",
            "--artifact-dir",
            str(tmp_path),
        ]
    )
    with pytest.raises(ValueError, match="new storage"):
        execute(options)
    assert not list(tmp_path.iterdir())


def test_execute_rejects_missing_consent_before_loading_sdk(tmp_path: Path) -> None:
    options = parse_options([*http_arguments(), "--artifact-dir", str(tmp_path / "unused")])
    with pytest.raises(ValueError, match="explicit consent"):
        execute(options)
    assert not (tmp_path / "unused").exists()


def test_dry_main_writes_only_content_free_bounds(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(http_arguments()) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["live_requested"] is False
    assert record["inflight_cancellation_confirmed"] is False
    assert "metrics" not in record


def report_metadata() -> tuple[RunStatus, Result, Report]:
    """Construct DTOs without captured answers, provider responses or agent execution."""
    identifier = UUID("d93398ed-8dc7-4b99-a262-9ab3fd3e3e72")
    phases = PhaseStates(
        planning="completed",
        inference="passed",
        evaluation_readiness="skipped",
        load="completed",
        profiling="skipped",
        evaluation="no_ready_scorers",
    )
    result = Result(
        id=identifier,
        status="completed",
        phases=phases,
        links=Links.for_run(str(identifier)),
        summary=DecisionSummary(performance="complete", quality="off"),
        preflight=PreflightResult(status="passed"),
        evaluation_preflight=EvaluationPreflight(status="skipped"),
    )
    status = RunStatus(id=identifier, status=result.status, phases=phases, links=result.links)
    report = Report(
        run=result,
        profiling=ProfilingSummary(total_requests=0, traced_requests=0, coverage=0),
        requests=[],
        offset=0,
        limit=25,
        total=0,
    )
    return status, result, report


def test_terminal_receipt_requires_full_result_and_report_parity() -> None:
    status, result, report = report_metadata()
    receipt = retrieval_evidence(
        result.id, status, result, report, report.model_copy(deep=True), remote=True
    )
    assert receipt["identifiers_agree"] is True
    assert receipt["retrieval_agrees"] is True
    assert receipt["remote_work_may_remain_active"] is False
    different = report.model_copy(deep=True)
    different.run.summary.performance = "incomplete"
    receipt = retrieval_evidence(result.id, status, result, report, different, remote=True)
    assert receipt["identifiers_agree"] is True
    assert receipt["retrieval_agrees"] is False
    assert receipt["result_payloads_agree"] is False
    assert receipt["remote_work_may_remain_active"] is True


@pytest.mark.parametrize("mismatch", ["phase", "report_page"])
def test_remote_warning_survives_terminal_phase_or_report_disagreement(mismatch: str) -> None:
    """Terminal metadata disagreement is not verified remote-work cessation."""
    status, result, report = report_metadata()
    retrieved = report.model_copy(deep=True)
    if mismatch == "phase":
        status.phases = status.phases.model_copy(update={"load": "skipped"})
    else:
        retrieved.limit = 10
    receipt = retrieval_evidence(result.id, status, result, report, retrieved, remote=True)
    assert receipt["identifiers_agree"] is True
    assert receipt["retrieval_agrees"] is False
    assert receipt["remote_work_may_remain_active"] is True


def test_matching_ids_do_not_prove_terminal_state_or_phases() -> None:
    status, result, report = report_metadata()
    status.status = "running"
    receipt = retrieval_evidence(result.id, status, result, report, report, remote=True)
    assert receipt["identifiers_agree"] is True
    assert receipt["retrieval_agrees"] is False
    assert receipt["remote_work_may_remain_active"] is True
    status.status = "completed"
    status.phases = status.phases.model_copy(update={"load": "skipped"})
    receipt = retrieval_evidence(result.id, status, result, report, report, remote=False)
    assert receipt["terminal_states_and_phases_agree"] is False
    assert receipt["retrieval_agrees"] is False


def test_preflight_receipt_exports_only_safe_code_not_message() -> None:
    status, result, report = report_metadata()
    report.run.preflight = PreflightResult(
        status="failed",
        error=PreflightError(code="target_http_error", message="private-provider-sentinel"),
    )
    receipt = retrieval_evidence(result.id, status, result, report, report, remote=False)
    assert receipt["preflight_code"] == "target_http_error"
    assert "private-provider-sentinel" not in json.dumps(receipt)


def test_fail_fast_requires_explicit_intent_and_expected_code() -> None:
    with pytest.raises(SystemExit):
        parse_options([*http_arguments(), "--scenario", "fail-fast"])
    options = parse_options(
        [
            *http_arguments(),
            "--scenario",
            "fail-fast",
            "--intentional-rejection",
            "--expected-preflight-code",
            "target_http_error",
        ]
    )
    assert plan_record(options)["negative_test_only"] is True
    receipt = {
        "retrieval_agrees": True,
        "status": "failed",
        "preflight": "failed",
        "preflight_code": "target_http_error",
        "phases": {"load": "skipped"},
        "metrics": None,
    }
    assert scenario_passed(options, receipt) is True
    receipt["preflight_code"] = "target_connection_error"
    assert scenario_passed(options, receipt) is False
    receipt["preflight_code"] = "target_http_error"
    receipt["status"] = "running"
    assert scenario_passed(options, receipt) is False
