"""Verify moved checkout tools without authorizing live provider traffic."""

import asyncio
import importlib
from pathlib import Path
from typing import Any

import mlflow
import pytest

from scripts.validation import framework_e2e

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "name",
    [
        "python_benchmark",
        "python_requests_benchmark",
        "framework_e2e",
        "databricks_validation",
        "locust_databricks_e2e",
    ],
)
def test_validation_modules_import_without_running(name: str) -> None:
    """Importing a helper must not start its CLI, resolve a profile, or invoke an agent."""
    module = importlib.import_module(f"scripts.validation.{name}")
    assert callable(module.main)
    assert Path(module.__file__).parent == ROOT / "scripts/validation"


@pytest.mark.parametrize("name", ["databricks_validation", "locust_databricks_e2e"])
async def test_paid_helpers_reject_missing_operator_configuration(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check repository-relative dotenv discovery and fail before paid provider access."""
    module = importlib.import_module(f"scripts.validation.{name}")
    dotenv_paths: list[Path] = []
    monkeypatch.setattr(module, "load_dotenv", lambda path: dotenv_paths.append(path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BENCHMARK_LLM_PROVIDER", "databricks")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/unused.db")
    monkeypatch.setenv("MLFLOW_MODEL_CATALOG_URI", "")
    for setting in ("DATABRICKS_CONFIG_PROFILE", "DATABRICKS_HOST"):
        monkeypatch.delenv(setting, raising=False)
    with pytest.raises(ValueError, match="Set DATABRICKS_CONFIG_PROFILE or DATABRICKS_HOST"):
        await module.main()
    assert dotenv_paths == [ROOT / ".env"]
    assert not list((tmp_path / "artifacts").glob("*.json"))


async def test_moved_framework_harness_runs_both_real_frameworks_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise actual servers, frameworks, Locust, tracing, and reports with fixture models."""
    for setting in (
        "EVALSURGE_DEMO_MODEL",
        "MLFLOW_EXPERIMENT_ID",
        "BENCHMARK_TRACE_EXPERIMENT_IDS",
    ):
        monkeypatch.setenv(setting, "")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.setenv("MLFLOW_MODEL_CATALOG_URI", "")
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    monkeypatch.setenv("BENCHMARK_TRACE_ENABLED", "false")
    monkeypatch.setenv("BENCHMARK_ARTIFACT_DIR", str(tmp_path / "agent-memory"))
    monkeypatch.setenv("BENCHMARK_CONNECTIONS", "{}")
    monkeypatch.setenv("BENCHMARK_SCORERS", "{}")
    monkeypatch.setenv("BENCHMARK_API_KEY", "offline-harness-key")
    previous_tracking_uri = mlflow.get_tracking_uri()
    try:
        summaries: list[dict[str, Any]] = await asyncio.wait_for(
            framework_e2e.validate(
                live=False,
                profile=None,
                model="fixture",
                directory=tmp_path / "framework-e2e",
                agent_port=0,
                api_port=0,
            ),
            timeout=60,
        )
        assert {summary["framework"] for summary in summaries} == {"langgraph", "openai-agents"}
        for summary in summaries:
            assert summary["mode"] == "provider-fixture"
            assert summary["preflight"]["status"] == "passed"
            assert summary["metrics"]["requests"] == summary["metrics"]["successful_requests"] == 2
            assert summary["metrics"]["error_rate"] == 0
            assert summary["profiling"]["coverage"] == 1
            assert summary["evaluation"]["status"] == "no_ready_scorers"
    finally:
        mlflow.set_tracking_uri(previous_tracking_uri)
