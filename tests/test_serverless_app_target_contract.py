"""No-inference guards for a runner-only notebook -> deployed App sample.

These checks exercise parsing, real schemas, source boundaries and intentional
pre-provider authentication rejection. No agent, model or controlled completion
is invoked; they do not establish successful live notebook-to-App coverage.
"""

import ast
import asyncio
from pathlib import Path

import pytest

from scripts.validation.serverless_runner_app_target import (
    budget_record,
    execute,
    parse_options,
    readiness,
    request,
)

ROOT = Path(__file__).resolve().parents[1]


def _arguments() -> list[str]:
    return [
        "--workspace",
        "https://selected-workspace.cloud.databricks.com",
        "--app-name",
        "operator-selected-app",
        "--profile",
        "operator-selected-profile",
        "--target-model",
        "operator-selected-model",
        "--source-revision",
        "reviewed-source-hash",
    ]


def test_dry_run_declares_only_runner_app_topology() -> None:
    options = parse_options(_arguments())
    record = budget_record(options)
    assert not options.live
    assert record["runner"] == "serverless-notebook"
    assert record["target_hosting"] == "deployed-databricks-app"
    assert record["maximum_app_invocations"] == 2
    assert record["declared_deployed_max_output_tokens"] == 512
    assert record["evaluation"] == "off"
    assert not record["deployed_app_tested"]
    assert not record["api_execution_tested"]
    assert not record["paid_traffic_authorized_by_this_record"]


def test_request_is_one_measured_attempt_and_no_judging() -> None:
    config = request()
    assert config.load.concurrency == 1
    assert config.load.max_requests == 1
    assert config.load.duration_seconds == 5
    assert config.load.timeout_seconds == 30
    assert config.target.connection_id == "agent"
    assert config.evaluation.mode == "off"
    assert set(config.cases[0].input) == {"query"}
    assert "profile" not in config.model_dump_json()


@pytest.mark.parametrize(
    "extra",
    [
        ["--workspace", "https://selected-workspace.cloud.databricks.com/path"],
        ["--workspace", "https://user:secret@selected-workspace.cloud.databricks.com"],
        ["--app-name", "bad_app_name"],
        ["--profile", ""],
        ["--source-revision", " "],
        ["--target-model", ""],
        ["--deployed-max-output-tokens", "513"],
        ["--deployed-max-output-tokens", "0"],
        ["--live"],
    ],
)
def test_selectors_and_paid_gate_reject_before_calls(extra: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_options([*_arguments(), *extra])


def test_execute_without_consent_makes_no_authentication_or_inference_calls() -> None:
    options = parse_options(_arguments())
    with pytest.raises(PermissionError, match="before auth or traffic"):
        asyncio.run(execute(options))


def test_actual_ambient_profile_guard_blocks_before_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABRICKS_HOST", "https://notebook-injected-host.cloud.databricks.com")
    result = readiness(parse_options(_arguments()))
    assert not result["driver_profile_ready"]
    assert not result["worker_oauth_ready"]
    assert result["inference_invocations"] == 0
    assert len(result["blockers"]) == 1
    assert "rejects ambient" in result["blockers"][0]
    assert "notebook-injected-host" not in str(result)


def test_notebook_never_imports_agent_or_serving_helper() -> None:
    path = ROOT / "examples/journeys/serverless_runner_databricks_app_target.py"
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported = {
        alias.name if isinstance(node, ast.Import) else node.module
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = {"langgraph", "agents", "crewai", "uvicorn", "evalsurge.serving"}
    assert not any(
        name and any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)
        for name in imported
    )
    assert "serverless_sdk_journeys" not in imported
    assert '"allow_paid_inference", "false"' in text
    assert "not proven live" in text
    assert "deployed Databricks App" in text


def test_retained_helper_sources_are_diagnostic_not_app_coverage() -> None:
    harness = (ROOT / "scripts/validation/serverless_sdk_journeys.py").read_text(encoding="utf-8")
    notebook = (ROOT / "scripts/validation/serverless_helper_notebook.py").read_text(
        encoding="utf-8"
    )
    assert "Historical diagnostic" in harness
    assert "not the intended hosted-agent journey" in harness
    assert "Historical diagnostic" in notebook
    assert "not deployed-App coverage" in notebook
