"""Configuration-only doctor and strictly secret-free capability contracts."""

import builtins
import json
import socket
from pathlib import Path
from typing import Any, NoReturn

import pytest

from benchmark_agents import connections, providers, scorer_registry
from benchmark_agents.diagnostics import build_capabilities, doctor, startup_diagnostics
from benchmark_agents.settings import load_settings

PRIVATE = "synthetic-private-operator-value"


@pytest.fixture(autouse=True)
def forbid_external_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject target/authentication/SDK/scorer/network calls in every diagnostic test."""

    def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
        """Fail before any credential resolution, network access, or trusted code loading."""
        pytest.fail("Configuration diagnostics must not perform external checks")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(providers, "workspace_client", forbidden)
    monkeypatch.setattr(connections, "workspace_client", forbidden)
    monkeypatch.setattr(connections, "authentication", forbidden)
    monkeypatch.setattr(scorer_registry, "load_scorer", forbidden)


def configured_environment() -> dict[str, str]:
    """Return complete static configuration, with no proof of provider availability."""
    return {
        "BENCHMARK_CONNECTIONS": json.dumps(
            {
                "support": {
                    "url": f"https://{PRIVATE}.example/chat",
                    "auth": "bearer",
                    "token_env": "PRIVATE_TOKEN_REFERENCE",
                    "protocols": ["http-json"],
                },
                "legacy": {"url": "http://127.0.0.1:9001/chat"},
            }
        ),
        "PRIVATE_TOKEN_REFERENCE": PRIVATE,
        "DATABRICKS_HOST": f"https://{PRIVATE}.example",
        "DATABRICKS_CONFIG_PROFILE": PRIVATE,
        "MLFLOW_TRACKING_URI": f"https://{PRIVATE}.example/tracking",
        "BENCHMARK_API_KEY": PRIVATE,
        "BENCHMARK_TRACE_ENABLED": "true",
        "BENCHMARK_TRACE_EXPERIMENT_IDS": '["17"]',
    }


def test_capabilities_only_publish_explicit_public_metadata() -> None:
    """Expose names, supported adapters and bounds, never connection/provider destinations."""
    environment = configured_environment()
    settings = load_settings(environ=environment)
    document = build_capabilities(settings, environ=environment)
    serialized = document.model_dump_json()
    assert PRIVATE not in serialized
    assert "PRIVATE_TOKEN_REFERENCE" not in serialized
    assert "url" not in serialized
    assert "profile" not in serialized
    targets = {target.name: target for target in document.targets}
    assert targets["support"].protocols == ("http-json",)
    assert targets["legacy"].protocols == ()
    assert document.protocols == ("openai-chat", "mlflow-agent-server", "http-json")
    assert document.limits.max_concurrent_users == 100
    assert document.limits.max_requests == 10_000
    assert document.limits.max_request_bytes == 8_000_000
    assert document.limits.max_json_response_bytes == 2_000_000
    assert document.limits.max_active_runs == 1
    assert document.tracing.readiness == "configured"
    assert document.evaluation.catalog_judges == "configured"
    assert not document.runtime_verified
    assert "groundedness" not in document.evaluation.executable_catalog_scorers


def test_default_doctor_allows_performance_only_with_explicit_warnings() -> None:
    """Optional evaluation/tracing gaps do not make a localhost configuration invalid."""
    report = doctor(environ={})
    assert report.ok
    assert report.configuration_only
    assert report.capabilities.evaluation.planner == "needs_configuration"
    assert report.capabilities.evaluation.catalog_judges == "needs_configuration"
    assert report.capabilities.tracing.readiness == "disabled"
    assert any(check.code == "api_auth_unconfigured" for check in report.checks)
    assert any(check.status == "warning" for check in report.checks)


def test_doctor_checks_bearer_presence_without_exporting_secret_references() -> None:
    """Only the presence of a configured credential is inspected; no headers are built."""
    environment = configured_environment()
    environment.pop("PRIVATE_TOKEN_REFERENCE")
    report = doctor(environ=environment)
    assert not report.ok
    errors = [check for check in report.checks if check.status == "error"]
    assert any(check.code == "target_credential_missing" for check in errors)
    assert PRIVATE not in report.model_dump_json()
    assert "PRIVATE_TOKEN_REFERENCE" not in report.model_dump_json()


def test_databricks_static_checks_do_not_resolve_profile_or_authentication() -> None:
    """Profile-only bindings remain explicitly unverified instead of invoking the SDK."""
    environment = {
        "DATABRICKS_CONFIG_PROFILE": PRIVATE,
        "BENCHMARK_CONNECTIONS": json.dumps(
            {"workspace": {"url": "https://workspace.example/chat", "auth": "databricks"}}
        ),
    }
    report = doctor(environ=environment)
    assert report.ok
    assert any(check.code == "target_workspace_unverified" for check in report.checks)
    environment["DATABRICKS_HOST"] = "https://other.example"
    report = doctor(environ=environment)
    assert not report.ok
    assert any(check.code == "target_workspace_mismatch" for check in report.checks)


@pytest.mark.parametrize(
    "environment,code",
    [
        ({"BENCHMARK_TRACE_ENABLED": "true"}, "trace_configuration_missing"),
        (
            {
                "BENCHMARK_SCORERS": json.dumps(
                    {"policy": {"name": PRIVATE, "experiment_id": "17", "version": 1}}
                )
            },
            "scorer_tracking_missing",
        ),
        ({"MLFLOW_TRACKING_URI": "databricks"}, "tracking_profile_missing"),
    ],
)
def test_explicit_incomplete_configuration_is_an_error(
    environment: dict[str, str], code: str
) -> None:
    """Fail static dependencies without retrieving scorer definitions or traces."""
    report = doctor(environ=environment)
    assert not report.ok
    assert any(check.code == code and check.status == "error" for check in report.checks)
    assert PRIVATE not in report.model_dump_json()


def test_openai_planner_readiness_requires_explicit_model_and_key() -> None:
    """Model names never imply provider compatibility, and absent keys remain configuration gaps."""
    environment = {"BENCHMARK_LLM_PROVIDER": "openai", "BENCHMARK_PLANNER_MODEL": PRIVATE}
    settings = load_settings(environ=environment)
    assert build_capabilities(settings, environ=environment).evaluation.planner == (
        "needs_configuration"
    )
    environment["OPENAI_API_KEY"] = PRIVATE
    assert build_capabilities(settings, environ=environment).evaluation.planner == "configured"


def test_doctor_reports_safe_file_failure_without_partial_capabilities(tmp_path: Path) -> None:
    """Invalid operator files yield a failed typed document with no partial target registry."""
    report = doctor(config_path=tmp_path / f"{PRIVATE}.toml", environ={})
    assert not report.ok
    assert report.capabilities is None
    assert len(report.checks) == 1
    assert PRIVATE not in report.model_dump_json()


def test_startup_diagnostics_never_create_storage_or_mutate_environment(tmp_path: Path) -> None:
    """Startup inspection is read-only and cannot certify disk ownership or live health."""
    artifact_dir = tmp_path / "not-created"
    environment = {"BENCHMARK_ARTIFACT_DIR": str(artifact_dir)}
    before = dict(environment)
    settings = load_settings(environ=environment)
    report = startup_diagnostics(settings, environ=environment)
    assert report.ok
    assert environment == before
    assert not artifact_dir.exists()
    assert report.configuration_only


def test_app_capabilities_are_static_and_doctor_does_not_resolve_lookup() -> None:
    """App aliases disclose supported protocols while private lookup values stay hidden."""
    environment = {
        "BENCHMARK_CONNECTIONS": json.dumps(
            {
                "support": {
                    "kind": "databricks-app",
                    "app_name": "support-agent",
                    "profile": PRIVATE,
                }
            }
        )
    }
    report = doctor(environ=environment)
    assert report.ok
    assert not report.capabilities.runtime_verified
    assert report.capabilities.targets[0].protocols == ("databricks-agent-runtime",)
    assert "databricks-agent-runtime" in report.capabilities.protocols
    assert any(check.code == "target_app_unverified" for check in report.checks)
    assert PRIVATE not in report.model_dump_json()
    assert "support-agent" not in report.model_dump_json()


@pytest.mark.parametrize(
    "name",
    [
        "DATABRICKS_HOST",
        "DATABRICKS_TOKEN",
        "DATABRICKS_METADATA_SERVICE_URL",
        "DATABRICKS_DISCOVERY_URL",
        "DATABRICKS_GROUP_ID",
        "DATABRICKS_TOKEN_AUDIENCE",
        "DATABRICKS_CLOUD",
        "ARM_ENVIRONMENT",
    ],
)
def test_doctor_flags_app_identity_overrides_without_sdk_imports(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Known configuration conflicts fail statically without SDK imports or private text."""
    original_import = builtins.__import__

    def forbid_sdk(module: str, *args: Any, **kwargs: Any) -> Any:
        if module.startswith("databricks.sdk"):
            pytest.fail("Static doctor must not import the SDK")
        return original_import(module, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", forbid_sdk)
    environment = {
        "BENCHMARK_CONNECTIONS": json.dumps(
            {
                "support": {
                    "kind": "databricks-app",
                    "app_name": "support-agent",
                    "profile": PRIVATE,
                }
            }
        ),
        name: f"https://{PRIVATE}.example" if name == "DATABRICKS_HOST" else PRIVATE,
    }
    before = dict(environment)
    report = doctor(environ=environment)
    assert not report.ok
    assert any(
        check.code == "target_app_identity_conflict" and check.status == "error"
        for check in report.checks
    )
    assert environment == before
    assert PRIVATE not in report.model_dump_json()
    assert name not in report.model_dump_json()


def test_doctor_app_selector_mismatch_is_static_and_matching_selectors_are_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inspect selector equality without opening either file or resolving SDK auth."""
    actual = str(tmp_path / "actual-profile-file")
    monkeypatch.setenv("DATABRICKS_CONFIG_FILE", actual)
    environment = {
        "DATABRICKS_CONFIG_FILE": str(tmp_path / PRIVATE),
        "BENCHMARK_CONNECTIONS": json.dumps(
            {
                "support": {
                    "kind": "databricks-app",
                    "app_name": "support-agent",
                    "profile": PRIVATE,
                }
            }
        ),
    }
    report = doctor(environ=environment)
    assert not report.ok
    assert any(check.code == "target_app_identity_conflict" for check in report.checks)
    assert PRIVATE not in report.model_dump_json()
    assert "DATABRICKS_CONFIG_FILE" not in report.model_dump_json()
    environment["DATABRICKS_CONFIG_FILE"] = actual
    assert doctor(environ=environment).ok
    assert not list(tmp_path.iterdir())
