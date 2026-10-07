"""Controlled SDK/OAuth boundaries for operator-owned Databricks App resolution."""

import json
import socket
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks.sdk.credentials_provider import OAuthCredentialsProvider, oauth_credentials_strategy
from databricks.sdk.oauth import HostMetadata, Token
from databricks.sdk.service.apps import App
from requests import Request

from benchmark_agents import providers, target_resolver
from benchmark_agents.configuration import configured_environment
from benchmark_agents.connections import Connection, authentication, resolve_connection
from benchmark_agents.models import Target
from benchmark_agents.runner import payload
from benchmark_agents.settings import ConnectionSettings
from benchmark_agents.target_resolver import TargetResolutionError, resolve_registered_target
from tests.test_template import configuration


class OAuthConfig:
    """Controlled SDK credential boundary that refreshes its token on every call."""

    def __init__(self) -> None:
        self.calls = 0

    def oauth_token(self) -> Token:
        self.calls += 1
        return Token(access_token=f"test-token-{self.calls}", token_type="Bearer")


def app_workspace(monkeypatch: pytest.MonkeyPatch, url: str | None = None):
    """Install an SDK boundary with native App/Token values and record selection."""
    selections = []
    lookups = []
    config = OAuthConfig()

    def get(*, name: str) -> App:
        lookups.append(name)
        return App(name=name, url=url or "https://agent-test.databricksapps.com")

    workspace = SimpleNamespace(config=config, apps=SimpleNamespace(get=get))

    def selected_workspace(*, profile: str):
        selections.append(profile)
        return workspace

    monkeypatch.setattr(target_resolver, "workspace_client", selected_workspace)
    return workspace, selections, lookups


def test_app_resolution_is_explicit_and_freezes_exact_origin(monkeypatch):
    workspace, profiles, names = app_workspace(monkeypatch)
    preset = ConnectionSettings(kind="databricks-app", profile="chosen", app_name="agent-test")
    target, connection = resolve_registered_target("support", {"support": preset})
    assert profiles == ["chosen"]
    assert names == ["agent-test"]
    assert (
        str(target.url) == connection.url == "https://agent-test.databricksapps.com/api/invocations"
    )
    assert connection.auth == "databricks-app"
    assert connection.profile == "chosen"
    assert target.session_per_request and target.session_id is None
    assert target.adapter == "databricks-agent-runtime"
    assert workspace.config.calls == 1
    assert "test-token" not in connection.model_dump_json()


def test_app_oauth_refreshes_for_each_dispatch_and_binds_origin(monkeypatch):
    workspace, profiles, _ = app_workspace(monkeypatch)
    binding = Connection(
        url="https://agent-test.databricksapps.com/api/invocations",
        auth="databricks-app",
        profile="chosen",
        app_name="agent-test",
    )
    headers = authentication(binding)
    assert profiles == ["chosen"]
    assert headers() == {"Authorization": "Bearer test-token-2"}
    assert headers() == {"Authorization": "Bearer test-token-3"}
    assert workspace.config.calls == 3
    with pytest.raises(TargetResolutionError, match="destination changed"):
        authentication(binding.model_copy(update={"url": "https://other.test/api/invocations"}))


@pytest.mark.parametrize(
    "url",
    [
        "http://agent.test",
        "https://user:secret@agent.test",
        "https://agent.test/path",
        "https://agent.test/?private=secret",
        "https://agent.test/#secret",
    ],
)
def test_invalid_app_origins_never_export_sdk_content(monkeypatch, url):
    app_workspace(monkeypatch, url)
    preset = ConnectionSettings(kind="databricks-app", profile="chosen", app_name="agent-test")
    with pytest.raises(TargetResolutionError) as failure:
        resolve_registered_target("support", {"support": preset})
    assert url not in str(failure.value)
    assert "secret" not in str(failure.value)


def test_app_pat_and_sdk_errors_fail_safely(monkeypatch):
    workspace, _, _ = app_workspace(monkeypatch)

    def unavailable():
        raise ValueError("private host and credential token")

    workspace.config.oauth_token = unavailable
    preset = ConnectionSettings(kind="databricks-app", profile="chosen", app_name="agent-test")
    with pytest.raises(TargetResolutionError) as failure:
        resolve_registered_target("support", {"support": preset})
    assert str(failure.value) == "Registered App discovery or OAuth authentication failed"
    assert failure.value.__cause__ is None


def test_legacy_responses_and_operator_fixed_sessions(monkeypatch):
    app_workspace(monkeypatch)
    preset = ConnectionSettings(
        kind="databricks-app",
        profile="chosen",
        app_name="agent-test",
        protocols=("mlflow-agent-server", "databricks-agent-runtime"),
        session_id="conversation",
    )
    target, connection = resolve_registered_target(
        "support", {"support": preset}, "mlflow-agent-server"
    )
    assert str(target.url) == connection.url == "https://agent-test.databricksapps.com/responses"
    assert target.adapter == "mlflow-agent-server"
    default, _ = resolve_registered_target("support", {"support": preset})
    assert default.adapter == "mlflow-agent-server"
    runtime, _ = resolve_registered_target(
        "support", {"support": preset}, "databricks-agent-runtime"
    )
    assert runtime.session_id == "conversation" and not runtime.session_per_request
    assert runtime.adapter == "databricks-agent-runtime"


def test_unknown_or_disallowed_presets_do_not_resolve_sdk(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("SDK must not be reached")

    monkeypatch.setattr(target_resolver, "workspace_client", forbidden)
    with pytest.raises(TargetResolutionError, match="Unknown"):
        resolve_registered_target("missing", {})
    preset = ConnectionSettings(kind="databricks-app", profile="chosen", app_name="agent-test")
    with pytest.raises(TargetResolutionError, match="Protocol"):
        resolve_registered_target("support", {"support": preset}, "http-json")


def test_generic_presets_and_task_local_credentials_preserve_v1_bindings():
    preset = ConnectionSettings(
        url="https://agent.test/chat", auth="bearer", token_env="TEST_TOKEN"
    )
    target, connection = resolve_registered_target("support", {"support": preset})
    assert target.adapter == "openai-chat"
    with configured_environment(
        {
            "BENCHMARK_CONNECTIONS": '{"support":{"kind":"http","url":"https://agent.test/chat","auth":"bearer","token_env":"TEST_TOKEN","protocols":[]}}',
            "TEST_TOKEN": "controlled-private-token",
        }
    ):
        legacy = resolve_connection(Target(url=target.url, connection_id="support"))
        assert legacy == connection
        assert authentication(legacy)() == {"Authorization": "Bearer controlled-private-token"}


def test_declared_http_protocol_allowlist_is_enforced():
    preset = ConnectionSettings(url="http://127.0.0.1:9001/json", protocols=("http-json",))
    target, _ = resolve_registered_target("local", {"local": preset})
    assert target.adapter == "http-json"
    with pytest.raises(TargetResolutionError, match="Protocol"):
        resolve_registered_target("local", {"local": preset}, "openai-chat")


@pytest.mark.parametrize(
    "protocols",
    [("http-json", "mlflow-agent-server"), ("mlflow-agent-server", "http-json")],
)
def test_multiple_http_protocols_use_the_first_operator_preset(protocols):
    preset = ConnectionSettings(url="http://127.0.0.1:9001/agent", protocols=protocols)
    target, binding = resolve_registered_target("local", {"local": preset})
    assert target.adapter == protocols[0]
    assert str(target.url) == binding.url
    selected, _ = resolve_registered_target("local", {"local": preset}, protocols[1])
    assert selected.adapter == protocols[1]
    with pytest.raises(TargetResolutionError, match="Protocol"):
        resolve_registered_target("local", {"local": preset}, "openai-chat")


def test_native_sdk_ambient_precedence_is_rejected_before_discovery(tmp_path, monkeypatch):
    """Reproduce actual Config profile precedence at controlled provider boundaries."""
    profile_file = tmp_path / "databricks.ini"
    profile_file.write_text("[chosen]\nhost = https://chosen.cloud.databricks.com\n")
    monkeypatch.setenv("DATABRICKS_CONFIG_FILE", str(profile_file))
    monkeypatch.setenv("DATABRICKS_HOST", "https://other.cloud.databricks.com")
    monkeypatch.setattr(
        "databricks.sdk.config.get_host_metadata",
        lambda *args, **kwargs: HostMetadata(oidc_endpoint=""),
    )

    @oauth_credentials_strategy("controlled-oauth", [])
    def controlled_oauth(config):
        return OAuthCredentialsProvider(
            lambda: {"Authorization": "Bearer controlled"},
            lambda: Token(access_token="controlled", token_type="Bearer"),
        )

    config = Config(profile="chosen", credentials_strategy=controlled_oauth)
    assert config.profile == "chosen"
    assert config.host == "https://other.cloud.databricks.com"

    def forbidden(*args, **kwargs):
        raise AssertionError("Conflicting identity must fail before constructing a client")

    monkeypatch.setattr(target_resolver, "workspace_client", forbidden)
    preset = ConnectionSettings(kind="databricks-app", profile="chosen", app_name="agent-test")
    with pytest.raises(TargetResolutionError, match="isolated operator environment") as failure:
        resolve_registered_target("support", {"support": preset})
    assert "other.cloud" not in str(failure.value)


@pytest.mark.parametrize(
    "name,attribute,profile_value,ambient_value",
    [
        (
            "DATABRICKS_DISCOVERY_URL",
            "discovery_url",
            "https://profile.invalid/metadata",
            "https://ambient.invalid/metadata",
        ),
        ("DATABRICKS_GROUP_ID", "group_id", "profile-group", "ambient-group"),
        ("DATABRICKS_TOKEN_AUDIENCE", "token_audience", "profile-audience", "ambient-audience"),
        ("DATABRICKS_CLOUD", "cloud", "AWS", "GCP"),
        ("ARM_ENVIRONMENT", "azure_environment", "PUBLIC", "CHINA"),
    ],
)
def test_native_sdk_routing_inputs_override_selected_profile_without_authentication(
    tmp_path, monkeypatch, name, attribute, profile_value, ambient_value
):
    """Verify Config precedence with fake routing inputs and no token or network calls."""
    profile_file = tmp_path / "routing.ini"
    profile_file.write_text(
        "[chosen]\nhost = https://profile.invalid\n" + f"{attribute} = {profile_value}\n"
    )
    monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        "databricks.sdk.config.get_host_metadata",
        lambda *args, **kwargs: HostMetadata(oidc_endpoint=""),
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Config precedence test must not fetch tokens or contact a destination")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(Config, "oauth_token", forbidden)

    @oauth_credentials_strategy("controlled-oauth", [])
    def controlled_oauth(config):
        return OAuthCredentialsProvider(lambda: {}, forbidden)

    selected = Config(
        profile="chosen", config_file=str(profile_file), credentials_strategy=controlled_oauth
    )
    actual = getattr(selected, attribute)
    assert getattr(actual, "value", actual) == profile_value
    monkeypatch.setenv(name, ambient_value)
    overridden = Config(
        profile="chosen", config_file=str(profile_file), credentials_strategy=controlled_oauth
    )
    actual = getattr(overridden, attribute)
    assert getattr(actual, "value", actual) == ambient_value
    assert overridden.profile == "chosen"


@pytest.mark.parametrize(
    "name",
    [
        "DATABRICKS_DISCOVERY_URL",
        "DATABRICKS_GROUP_ID",
        "DATABRICKS_TOKEN_AUDIENCE",
        "DATABRICKS_CLOUD",
        "ARM_ENVIRONMENT",
    ],
)
@pytest.mark.parametrize("source", ["ambient", "scoped"])
def test_app_routing_overrides_reject_before_sdk_and_hide_values(monkeypatch, name, source):
    """Reject routing/identity override presence without constructing an SDK client."""
    private = "synthetic-private-routing-value"
    monkeypatch.delenv(name, raising=False)

    def forbidden(*args, **kwargs):
        pytest.fail("Routing conflicts must fail before SDK construction")

    monkeypatch.setattr(target_resolver, "workspace_client", forbidden)
    preset = ConnectionSettings(kind="databricks-app", profile="chosen", app_name="agent-test")
    if source == "ambient":
        monkeypatch.setenv(name, private)
    with (
        configured_environment({name: private} if source == "scoped" else {}),
        pytest.raises(TargetResolutionError, match="isolated operator environment") as failure,
    ):
        resolve_registered_target("support", {"support": preset})
    assert private not in str(failure.value)
    assert name not in str(failure.value)


def test_native_sdk_app_decoding_and_oauth_provider_at_transport_boundary(tmp_path, monkeypatch):
    """Use the real Config, WorkspaceClient and AppsAPI with only HTTP controlled."""
    profile_file = tmp_path / "databricks.ini"
    profile_file.write_text("[chosen]\nhost = https://chosen.cloud.databricks.com\n")
    monkeypatch.setenv("DATABRICKS_CONFIG_FILE", str(profile_file))
    monkeypatch.setattr(
        "databricks.sdk.config.get_host_metadata",
        lambda *args, **kwargs: HostMetadata(oidc_endpoint=""),
    )
    tokens = OAuthConfig()

    @oauth_credentials_strategy("controlled-oauth", [])
    def controlled_oauth(config):
        return OAuthCredentialsProvider(
            lambda: {"Authorization": "Bearer controlled"}, tokens.oauth_token
        )

    workspace = WorkspaceClient(
        config=Config(profile="chosen", credentials_strategy=controlled_oauth)
    )
    calls = []

    def controlled_http(method, path, **kwargs):
        calls.append((method, path))
        return {"name": "agent-test", "url": "https://exact-resolved.databricksapps.com/"}

    monkeypatch.setattr(workspace.api_client, "do", controlled_http)

    def explicit_profile(*, profile):
        assert profile == "chosen"
        return workspace

    monkeypatch.setattr(target_resolver, "workspace_client", explicit_profile)
    preset = ConnectionSettings(kind="databricks-app", profile="chosen", app_name="agent-test")
    target, binding = resolve_registered_target("support", {"support": preset})
    assert calls == [("GET", "/api/2.0/apps/agent-test")]
    assert str(target.url) == "https://exact-resolved.databricksapps.com/api/invocations"
    headers = authentication(binding)
    assert headers() == {"Authorization": "Bearer test-token-3"}
    assert headers() == {"Authorization": "Bearer test-token-4"}
    assert calls == [("GET", "/api/2.0/apps/agent-test")] * 2
    run = configuration()
    run.target = target
    request_id = str(uuid4())
    body = payload(run, run.evaluation.samples[0], request_id)
    prepared = Request("POST", binding.url, json=body, headers=headers()).prepare()
    encoded = json.loads(prepared.body)
    assert encoded["id"] == request_id
    assert UUID(encoded["session_id"])
    assert encoded["stream"] is encoded["background"] is False
    assert target.session_per_request and target.session_id is None
    assert prepared.headers["Authorization"] == "Bearer test-token-5"
    assert "X-Databricks-Workspace-Id" not in prepared.headers
    assert "profile" not in encoded and "app_name" not in encoded
    assert "test-token" not in prepared.body.decode()


def test_scoped_provider_workspace_conflict_fails_before_app_resolution(monkeypatch):
    """Reject the same private snapshot that will become the Locust worker env."""
    monkeypatch.delenv("DATABRICKS_HOST", raising=False)
    preset = ConnectionSettings(kind="databricks-app", profile="app-profile", app_name="agent-test")

    def forbidden(*args, **kwargs):
        raise AssertionError("Conflicting scoped identity must fail before SDK construction")

    monkeypatch.setattr(target_resolver, "workspace_client", forbidden)
    with (
        configured_environment(
            {
                "DATABRICKS_HOST": "https://private-provider.cloud.databricks.com",
                "DATABRICKS_CONFIG_PROFILE": "judge-profile",
            }
        ),
        pytest.raises(TargetResolutionError, match="isolated operator environment") as failure,
    ):
        resolve_registered_target("support", {"support": preset})
    assert "private-provider" not in str(failure.value)
    assert "app-profile" not in str(failure.value)
    assert "judge-profile" not in str(failure.value)


def test_native_sdk_uses_scoped_config_file_and_preserves_ambient_fallback(tmp_path, monkeypatch):
    """Exercise real provider/SDK construction with distinct operator profile files."""
    ambient_file = tmp_path / "ambient.ini"
    scoped_file = tmp_path / "scoped.ini"
    ambient_file.write_text("[chosen]\nhost = https://ambient.cloud.databricks.com\n")
    scoped_file.write_text("[chosen]\nhost = https://scoped.cloud.databricks.com\n")
    monkeypatch.setenv("DATABRICKS_CONFIG_FILE", str(ambient_file))
    monkeypatch.setattr(
        "databricks.sdk.config.get_host_metadata",
        lambda *args, **kwargs: HostMetadata(oidc_endpoint=""),
    )

    @oauth_credentials_strategy("oauth-m2m", [])
    def controlled_oauth(config):
        return OAuthCredentialsProvider(
            lambda: {"Authorization": "Bearer controlled"},
            lambda: Token(access_token="controlled", token_type="Bearer"),
        )

    monkeypatch.setattr(
        "databricks.sdk.credentials_provider.oauth_service_principal", controlled_oauth
    )
    with configured_environment({"DATABRICKS_CONFIG_FILE": str(scoped_file)}):
        workspace = providers.workspace_client(profile="chosen")
        assert workspace.config.config_file == str(scoped_file)
        assert workspace.config.host == "https://scoped.cloud.databricks.com"
        assert workspace.config.profile == "chosen"
        assert workspace.config.http_timeout_seconds == workspace.config.retry_timeout_seconds == 20
        assert workspace.config.oauth_token().access_token == "controlled"
    ambient = providers.workspace_client(profile="chosen")
    assert ambient.config.config_file == str(ambient_file)
    assert ambient.config.host == "https://ambient.cloud.databricks.com"


def test_app_config_file_mismatch_rejects_before_sdk_and_matching_selector_allows(
    tmp_path, monkeypatch
):
    """Reject a CLI-inherited source mismatch while permitting a shared selector."""
    ambient_file = tmp_path / "ambient.ini"
    scoped_file = tmp_path / "scoped.ini"
    monkeypatch.setenv("DATABRICKS_CONFIG_FILE", str(ambient_file))
    _, selected_profiles, _ = app_workspace(monkeypatch)
    preset = ConnectionSettings(kind="databricks-app", profile="chosen", app_name="agent-test")
    with (
        configured_environment({"DATABRICKS_CONFIG_FILE": str(scoped_file)}),
        pytest.raises(TargetResolutionError) as failure,
    ):
        resolve_registered_target("support", {"support": preset})
    assert selected_profiles == []
    assert str(ambient_file) not in str(failure.value)
    assert str(scoped_file) not in str(failure.value)
    with configured_environment({"DATABRICKS_CONFIG_FILE": str(ambient_file)}):
        target, _ = resolve_registered_target("support", {"support": preset})
    assert selected_profiles == ["chosen"]
    assert target.adapter == "databricks-agent-runtime"
