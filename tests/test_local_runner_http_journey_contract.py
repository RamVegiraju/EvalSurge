"""Pure local-journey plans/status classification; no agent/model calls or answers."""

import argparse
import ast
import inspect

import pytest

from examples.journeys.local_runner_http_target import request
from scripts.validation.local_runner_http_target_journeys import (
    benchmark_request,
    journey_passed,
    main,
    parse_options,
    plan_record,
    validate_api_environment,
)


def arguments(*extra: str) -> list[str]:
    """Return explicit constructor-only selections, never an actual SDK profile."""
    return [
        "--framework",
        "langgraph",
        "--profile",
        "not-resolved-constructor-only",
        "--workspace-host",
        "https://selected-workspace.cloud.databricks.com",
        "--model",
        "system.ai.gpt-oss-120b",
        "--api",
        "mlflow-responses",
        "--artifact-dir",
        "/private/tmp/not-created-by-construction",
        *extra,
    ]


@pytest.mark.parametrize("scenario", ["load", "cancel"])
def test_positive_journeys_use_the_unmodified_advertised_request(scenario: str) -> None:
    assert benchmark_request(scenario) == request()
    assert benchmark_request(scenario).evaluation.mode == "off"


def test_fail_fast_changes_only_case_input_and_has_no_model_budget() -> None:
    negative = benchmark_request("fail-fast")
    positive = request()
    assert negative.load == positive.load
    assert negative.target == positive.target
    assert set(negative.cases[0].input) == {"query", "unsupported"}
    options = parse_options(arguments("--scenario", "fail-fast"))
    assert plan_record(options)["max_physical_model_attempts"] == 0


@pytest.mark.parametrize("execution", ["direct", "api"])
def test_runner_target_classification_is_not_a_notebook_hosting_choice(execution: str) -> None:
    plan = plan_record(parse_options(arguments("--execution", execution)))
    assert plan["runner_location"] == "local machine"
    assert plan["target_hosting"] == "local HTTP agent"
    assert plan["max_physical_model_attempts"] == plan["max_target_attempts"] == 6
    assert plan["load"] == request().load.model_dump(mode="json")
    assert plan["inference_stubbed"] is False


@pytest.mark.parametrize("scenario", ["load", "cancel"])
def test_paid_consent_is_checked_before_native_resource_creation(scenario: str) -> None:
    with pytest.raises(SystemExit):
        parse_options(arguments("--live", "--scenario", scenario))


def test_negative_live_selection_requires_no_paid_consent_because_no_provider_call() -> None:
    options = parse_options(arguments("--live", "--scenario", "fail-fast"))
    assert options.live and not options.accept_paid_traffic


def test_dry_plan_has_no_resource_or_inference_claim(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(arguments()) == 0
    assert '"passed": false' in capsys.readouterr().out


def test_unknown_scenario_is_never_accepted() -> None:
    with pytest.raises(ValueError):
        benchmark_request("other")


def test_latest_real_helper_is_the_only_imported_agent_implementation() -> None:
    from scripts.validation import local_runner_http_target_journeys as harness

    tree = ast.parse(inspect.getsource(harness))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "examples.real_framework_agent" in modules
    assert "examples.framework_agent" not in modules
    assert "examples.mock_agent" not in modules


def metadata_receipt() -> dict:
    """Build only content-free status fields, not a model answer/completion fixture."""
    return {
        "retrieval_agrees": True,
        "sdk_context_closed": True,
        "agent_lifespan_closed": True,
        "agent_listener_closed": True,
        "report_json_path": "metadata-only-not-an-exported-report",
        "model_transport_evidence": {"outbound_attempts": 0, "completed_responses": 0},
    }


def test_load_cannot_pass_from_typed_retrieval_without_real_model_counts() -> None:
    options = parse_options(arguments())
    assert not journey_passed(options, metadata_receipt())


def test_natural_completion_is_not_active_cancellation() -> None:
    options = parse_options(arguments("--scenario", "cancel"))
    receipt = metadata_receipt()
    receipt.update(status="completed", measured_dispatch_observed_at_cancel=False)
    assert not journey_passed(options, receipt)


def test_failed_cleanup_never_passes_negative_check() -> None:
    options = parse_options(arguments("--scenario", "fail-fast"))
    receipt = metadata_receipt()
    receipt.update(
        status="failed",
        preflight="failed",
        preflight_code="target_http_error",
        phases={"load": "skipped"},
        target_receipts={"received": 1},
        agent_lifespan_closed=False,
    )
    assert not journey_passed(options, receipt)


def test_api_metadata_requires_actual_authentication_rejection() -> None:
    options = argparse.Namespace(execution="api", scenario="fail-fast")
    assert not journey_passed(options, metadata_receipt())


def test_failed_report_export_is_never_a_pass() -> None:
    options = parse_options(arguments("--scenario", "fail-fast"))
    receipt = metadata_receipt()
    receipt["failure_type"] = "OSError"
    assert not journey_passed(options, receipt)


def test_ambient_operator_settings_never_replace_owned_api_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BENCHMARK_CONNECTIONS", "not-read-or-exported")
    with pytest.raises(ValueError, match="ambient benchmark configuration"):
        validate_api_environment()
