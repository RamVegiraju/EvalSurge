"""Offline contracts for operator settings, precedence, and private configuration."""

import builtins
import json
import os
from pathlib import Path
from typing import Any

import pytest

from benchmark_agents import providers, scorer_registry
from benchmark_agents.settings import SettingsError, load_settings

PRIVATE = "synthetic-private-operator-value"


def operator_environment() -> dict[str, str]:
    """Return legacy settings with private values and no executable scorer loading."""
    return {
        "BENCHMARK_ARTIFACT_DIR": f"/tmp/{PRIVATE}",
        "BENCHMARK_CONNECTIONS": json.dumps(
            {
                "support": {
                    "url": f"https://{PRIVATE}.example/chat",
                    "auth": "bearer",
                    "token_env": "PRIVATE_TOKEN_REFERENCE",
                }
            }
        ),
        "BENCHMARK_ALLOWED_TARGETS": json.dumps([f"https://{PRIVATE}.example/public"]),
        "BENCHMARK_LLM_PROVIDER": "databricks",
        "DATABRICKS_CONFIG_PROFILE": PRIVATE,
        "DATABRICKS_HOST": f"https://{PRIVATE}.example",
        "BENCHMARK_JUDGE_MODEL": "databricks:/judge",
        "MLFLOW_TRACKING_URI": "databricks",
        "MLFLOW_EXPERIMENT_ID": "17",
        "BENCHMARK_TRACE_ENABLED": "TRUE",
        "BENCHMARK_MAX_TRACES": "25",
        "BENCHMARK_SCORERS": json.dumps(
            {
                "policy": {
                    "name": PRIVATE,
                    "experiment_id": "17",
                    "version": 2,
                    "required_fields": ["inputs", "outputs", "trace"],
                }
            }
        ),
        "BENCHMARK_API_KEY": PRIVATE,
        "PRIVATE_TOKEN_REFERENCE": PRIVATE,
    }


def test_legacy_environment_is_loaded_without_mutating_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retain documented defaults, prefix handling, scorer references, and trace scope."""
    environment = operator_environment()
    before = dict(environment)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    settings = load_settings(environ=environment)
    assert environment == before
    assert settings.provider.judge_endpoint == providers.judge_endpoint() == "judge"
    assert settings.effective_tracking_uri == scorer_registry.tracking_uri()
    assert settings.trace_experiment_ids == tuple(scorer_registry.trace_source().experiment_ids)
    assert settings.tracing.max_traces == scorer_registry.trace_source().max_traces == 25
    reference = settings.scorers["policy"].reference("policy")
    assert reference.model_dump(exclude={"definition_hash"}) == scorer_registry.catalog()["policy"]
    binding = settings.connections["support"].connection()
    assert binding.auth == "bearer"
    assert binding.token_env == "PRIVATE_TOKEN_REFERENCE"
    assert settings.connections["support"].protocols == ()


def test_settings_serialization_and_repr_exclude_private_fields() -> None:
    """Do not expose destinations, credential references, profiles, or registry identifiers."""
    settings = load_settings(environ=operator_environment())
    serialized = (
        settings.model_dump_json()
        + settings.provider.model_dump_json()
        + settings.connections["support"].model_dump_json()
        + settings.scorers["policy"].model_dump_json()
        + repr(settings)
        + repr(settings.provider)
        + repr(settings.connections["support"])
    )
    assert PRIVATE not in serialized
    assert "PRIVATE_TOKEN_REFERENCE" not in serialized
    assert "token_env" not in serialized
    assert "judge" not in serialized
    assert "support" not in settings.model_dump()


def test_explicit_environment_is_isolated_and_collections_are_immutable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ambient configuration must not enter an explicitly supplied snapshot."""
    monkeypatch.setenv("BENCHMARK_CONNECTIONS", PRIVATE)
    settings = load_settings(environ={})
    assert settings.connections == {}
    assert settings.provider.planner_endpoint == providers.DEFAULT_FM_ENDPOINT
    assert settings.provider.judge_endpoint is None
    with pytest.raises(TypeError):
        settings.connections["new"] = object()


def test_toml_configuration_and_per_field_environment_precedence(tmp_path: Path) -> None:
    """Environment overrides whole registries and individual provider/trace fields."""
    path = tmp_path / "settings.toml"
    path.write_text(
        """
artifact_dir = "file-artifacts"
tracking_uri = "sqlite:///file.db"
[provider]
name = "openai"
planner_model = "file-model"
[connections.file]
url = "https://file.example/chat"
protocols = ["http-json"]
[tracing]
enabled = true
experiment_ids = ["12"]
max_traces = 20
""",
        encoding="utf-8",
    )
    environment = {
        "BENCHMARK_CONFIG": str(path),
        "BENCHMARK_PLANNER_MODEL": "environment-model",
        "BENCHMARK_CONNECTIONS": "{}",
        "BENCHMARK_TRACE_ENABLED": "false",
    }
    settings = load_settings(environ=environment)
    assert settings.artifact_dir == Path("file-artifacts")
    assert settings.provider.name == "openai"
    assert settings.provider.planner_endpoint == "environment-model"
    assert settings.connections == {}
    assert not settings.tracing.enabled
    assert settings.tracing.experiment_ids == ("12",)
    assert settings.tracing.max_traces == 20
    assert settings.tracking_uri == "sqlite:///file.db"
    assert "BENCHMARK_CONFIG" not in os.environ or os.environ["BENCHMARK_CONFIG"] != str(path)


def test_explicit_path_wins_over_environment_path(tmp_path: Path) -> None:
    """Select only the explicit operator file when both path mechanisms are present."""
    path = tmp_path / "settings.toml"
    path.write_text('artifact_dir = "explicit"\n', encoding="utf-8")
    settings = load_settings(path, environ={"BENCHMARK_CONFIG": f"/{PRIVATE}"})
    assert settings.artifact_dir == Path("explicit")


@pytest.mark.parametrize(
    "environment",
    [
        {"BENCHMARK_CONNECTIONS": PRIVATE},
        {"BENCHMARK_CONNECTIONS": "[]"},
        {"BENCHMARK_ALLOWED_TARGETS": "{}"},
        {"BENCHMARK_TRACE_EXPERIMENT_IDS": '"not-a-list"'},
        {"BENCHMARK_MAX_TRACES": "201"},
        {"BENCHMARK_MAX_TRACES": PRIVATE},
        {"BENCHMARK_TRACE_ENABLED": "maybe"},
        {"BENCHMARK_LLM_PROVIDER": PRIVATE},
        {"BENCHMARK_JUDGE_MODEL": f"openai:/{PRIVATE}"},
        {"DATABRICKS_HOST": f"https://user:{PRIVATE}@workspace.example"},
        {"MLFLOW_TRACKING_URI": f"https://user:{PRIVATE}@tracking.example"},
        {
            "BENCHMARK_CONNECTIONS": json.dumps(
                {"target": {"url": f"https://example.com/chat?token={PRIVATE}"}}
            )
        },
        {
            "BENCHMARK_CONNECTIONS": json.dumps(
                {"target": {"url": "http://remote.example/chat", "auth": "bearer"}}
            )
        },
        {"BENCHMARK_SCORERS": json.dumps({"policy": {"name": PRIVATE, "version": 0}})},
    ],
)
def test_invalid_configuration_has_safe_actionable_errors(environment: dict[str, str]) -> None:
    """Reject malformed settings without echoing operator-controlled values."""
    with pytest.raises(SettingsError) as failure:
        load_settings(environ=environment)
    assert failure.value.code
    assert PRIVATE not in str(failure.value)
    assert "configuration" in str(failure.value).lower()


@pytest.mark.parametrize("suffix", [".json", ".txt", ".toml"])
def test_file_errors_do_not_expose_paths_or_content(tmp_path: Path, suffix: str) -> None:
    """Missing, unsupported, and malformed files have redacted configuration errors."""
    path = tmp_path / f"{PRIVATE}{suffix}"
    if suffix != ".json":
        path.write_text(f"[{PRIVATE}", encoding="utf-8")
    with pytest.raises(SettingsError) as failure:
        load_settings(path, environ={})
    assert PRIVATE not in str(failure.value)


def test_file_and_environment_configuration_are_bounded(tmp_path: Path) -> None:
    """Apply byte bounds before parsing operator files or JSON registries."""
    path = tmp_path / "settings.toml"
    path.write_bytes(b"x" * 1_000_001)
    for operation in [
        lambda: load_settings(path, environ={}),
        lambda: load_settings(environ={"BENCHMARK_CONNECTIONS": "x" * 1_000_001}),
    ]:
        with pytest.raises(SettingsError, match="limit"):
            operation()


def test_yaml_uses_safe_loading_and_rejects_ambiguous_documents(tmp_path: Path) -> None:
    """Plain YAML works; executable tags, aliases, and duplicate keys are rejected."""
    pytest.importorskip("yaml")
    path = tmp_path / "settings.yaml"
    path.write_text(
        """
connections:
  support:
    url: https://example.com/chat
    protocols: [http-json, openai-chat]
provider:
  name: openai
  planner_model: configured-model
""",
        encoding="utf-8",
    )
    settings = load_settings(path, environ={})
    assert settings.connections["support"].protocols == ("http-json", "openai-chat")
    for text in [
        f"!!python/object/apply:os.system ['{PRIVATE}']",
        "artifact_dir: first\nartifact_dir: second\n",
        "connections: &shared {}\nscorers: *shared\n",
        "provider: [",
    ]:
        path.write_text(text, encoding="utf-8")
        with pytest.raises(SettingsError) as failure:
            load_settings(path, environ={})
        assert PRIVATE not in str(failure.value)


def test_yaml_dependency_is_optional_with_actionable_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing optional loader must recommend PyYAML or built-in TOML."""
    original_import = builtins.__import__

    def without_yaml(name: str, *args: Any, **kwargs: Any) -> Any:
        """Simulate an installation without PyYAML, leaving other imports intact."""
        if name == "yaml":
            raise ImportError(PRIVATE)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_yaml)
    path = tmp_path / "settings.yml"
    path.write_text("connections: {}\n", encoding="utf-8")
    with pytest.raises(SettingsError, match="PyYAML.*TOML") as failure:
        load_settings(path, environ={})
    assert PRIVATE not in str(failure.value)
    assert load_settings(environ={}).connections == {}


def test_file_settings_produce_detached_private_runtime_environment(tmp_path: Path) -> None:
    """File configuration reaches legacy runtime consumers without global mutation."""
    path = tmp_path / "settings.toml"
    path.write_text(
        """
artifact_dir = "file-artifacts"
tracking_uri = "sqlite:///file.db"
[provider]
name = "openai"
planner_model = "file-model"
[connections.support]
url = "https://example.com/chat"
auth = "bearer"
token_env = "PRIVATE_TOKEN_REFERENCE"
protocols = ["http-json"]
[scorers.policy]
name = "registered-policy"
experiment_id = "17"
version = 2
[tracing]
enabled = true
experiment_ids = ["12"]
max_traces = 25
""",
        encoding="utf-8",
    )
    environment = {"PRIVATE_TOKEN_REFERENCE": PRIVATE, "OPENAI_API_KEY": PRIVATE}
    settings = load_settings(path, environ=environment)
    effective = settings.to_environment(environment)
    assert effective is not environment
    assert environment == {"PRIVATE_TOKEN_REFERENCE": PRIVATE, "OPENAI_API_KEY": PRIVATE}
    assert effective["PRIVATE_TOKEN_REFERENCE"] == PRIVATE
    assert effective["BENCHMARK_LLM_PROVIDER"] == "openai"
    assert effective["BENCHMARK_PLANNER_MODEL"] == "file-model"
    assert effective["MLFLOW_TRACKING_URI"] == "sqlite:///file.db"
    assert json.loads(effective["BENCHMARK_CONNECTIONS"])["support"]["protocols"] == ["http-json"]
    assert json.loads(effective["BENCHMARK_SCORERS"])["policy"]["name"] == "registered-policy"
    assert load_settings(environ=effective) == settings
    assert PRIVATE not in settings.model_dump_json()


def test_app_presets_are_immutable_private_and_require_explicit_identity() -> None:
    """An App preset owns its lookup identity and never accepts a raw App URL."""
    environment = {
        "BENCHMARK_CONNECTIONS": json.dumps(
            {
                "support": {
                    "kind": "databricks-app",
                    "app_name": "support-agent",
                    "profile": PRIVATE,
                    "session_id": PRIVATE,
                }
            }
        )
    }
    settings = load_settings(environ=environment)
    preset = settings.connections["support"]
    assert preset.protocols == ("databricks-agent-runtime",)
    assert PRIVATE not in preset.model_dump_json() + repr(preset)
    assert "support-agent" not in preset.model_dump_json() + repr(preset)
    with pytest.raises(SettingsError):
        preset.connection()
    for record in [
        {"kind": "databricks-app", "app_name": "support-agent"},
        {
            "kind": "databricks-app",
            "app_name": "support-agent",
            "profile": PRIVATE,
            "url": "https://example.com/chat",
        },
    ]:
        with pytest.raises(SettingsError) as failure:
            load_settings(environ={"BENCHMARK_CONNECTIONS": json.dumps({"support": record})})
        assert PRIVATE not in str(failure.value)


def test_explicit_serialization_include_cannot_export_private_configuration() -> None:
    """Pydantic field exclusions remain authoritative even with include arguments."""
    settings = load_settings(environ=operator_environment())
    assert settings.model_dump(include={"api_key", "artifact_dir", "connections"}) == {}
    assert settings.provider.model_dump(include={"judge_model", "profile", "host"}) == {}
    assert settings.connections["support"].model_dump(include={"url", "token_env"}) == {}


def test_runtime_snapshot_does_not_reopen_changed_or_deleted_source(tmp_path: Path) -> None:
    """Once loaded, the private runtime environment survives configuration-file changes."""
    path = tmp_path / "settings.toml"
    path.write_text('artifact_dir = "frozen-artifacts"\n', encoding="utf-8")
    environment = {"BENCHMARK_CONFIG": str(path), "PRIVATE_TOKEN_REFERENCE": PRIVATE}
    before = dict(environment)
    settings = load_settings(environ=environment)
    snapshot = settings.to_environment(environment)
    assert "BENCHMARK_CONFIG" not in snapshot
    assert environment == before
    path.write_text('artifact_dir = "changed-artifacts"\n', encoding="utf-8")
    assert load_settings(environ=snapshot).artifact_dir == Path("frozen-artifacts")
    path.unlink()
    assert load_settings(environ=snapshot).artifact_dir == Path("frozen-artifacts")
    assert snapshot["PRIVATE_TOKEN_REFERENCE"] == PRIVATE
    assert environment == before
