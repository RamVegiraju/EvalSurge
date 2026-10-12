"""Native App auth configuration and controlled SDK metadata; no model inference.

SDK OAuth/Apps replies are controlled credentials-boundary fixtures, not live
authentication, deployment, target responses or successful agent execution.
"""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs

import pytest
import requests
from databricks.sdk import WorkspaceClient, oauth
from databricks.sdk.core import Config
from databricks.sdk.credentials_provider import oauth_service_principal
from databricks.sdk.service.apps import (
    App,
    AppResource,
    AppResourceApp,
    AppResourceAppAppPermission,
)
from pydantic import ValidationError

from benchmark_agents.configuration import SDK_PROFILE_OVERRIDE_ENV, configured_environment
from benchmark_agents.connections import Connection, authentication, validate_connection
from benchmark_agents.diagnostics import startup_diagnostics
from benchmark_agents.models import Target
from benchmark_agents.settings import ConnectionSettings, Settings
from benchmark_agents.target_resolver import (
    TargetResolutionError,
    _native_environment,
    _native_workspace_app,
    _reject_profile_overrides,
    resolve_registered_target,
)
from evalsurge import Agent, Case, RunCreate, TargetReference

WORKSPACE = "https://workspace.cloud.databricks.com"
WORKSPACE_ID = "12345"
CLIENT = "11111111-2222-3333-4444-555555555555"
TARGET_ORIGIN = "https://agent-target.databricksapps.com"
NATIVE_ENV = {
    "DATABRICKS_HOST": WORKSPACE,
    "DATABRICKS_CLIENT_ID": CLIENT,
    "DATABRICKS_CLIENT_SECRET": "private-controlled-oauth-secret-no-model",
}


@pytest.fixture
def native_env(monkeypatch):
    """Select synthetic environment credentials only; never construct live SDK auth."""
    import os

    for name in set(SDK_PROFILE_OVERRIDE_ENV) | {
        "DATABRICKS_CONFIG_FILE",
        "DATABRICKS_CONFIG_PROFILE",
        "DATABRICKS_CLI_PATH",
        "DATABRICKS_DEBUG_HEADERS",
    }:
        monkeypatch.delenv(name, raising=False)
    for name, value in NATIVE_ENV.items():
        monkeypatch.setenv(name, value)
    with configured_environment(dict(os.environ)):
        yield dict(os.environ)


def binding(**updates):
    """Construct native operator metadata without resolving credentials."""
    return ConnectionSettings(
        **{
            "kind": "databricks-app",
            "app_name": "target-agent",
            "app_auth": "app-runtime",
            "workspace": WORKSPACE,
            "runner_app": "load-test",
            "client_id": CLIENT,
            **updates,
        }
    )


def test_native_public_constructor_is_inert_and_identity_stays_outside_requests(monkeypatch):
    monkeypatch.setattr(
        WorkspaceClient, "__init__", lambda *a, **k: pytest.fail("SDK construction")
    )
    agent = Agent.databricks_app(
        "target-agent",
        auth="app-runtime",
        workspace=WORKSPACE,
        runner_app="load-test",
        client_id=CLIENT,
    )
    record = agent.registration.operator_record()
    assert record["app_auth"] == "app-runtime"
    assert record["runner_app"] == "load-test"
    assert record["client_id"] == CLIENT
    assert "profile" not in record
    assert "workspace" not in agent.registration.model_dump()
    assert CLIENT not in repr(agent.registration)
    assert Settings(connections={"agent": agent.registration}).model_dump()["provider"]
    request = RunCreate(
        target=TargetReference(connection_id="agent"), cases=[Case(input={"q": "x"})]
    )
    for value in ("workspace", "runner_app", "client_id", CLIENT, "app-runtime"):
        assert value not in request.model_dump_json()


@pytest.mark.parametrize(
    "updates",
    [
        {"profile": "named"},
        {"workspace": None},
        {"runner_app": None},
        {"client_id": None},
        {"client_id": "12345"},
        {"client_id": "target-oauth-audience"},
        {"workspace": "http://workspace.example"},
        {"workspace": WORKSPACE + "/path"},
        {"workspace": WORKSPACE + "?token=x"},
        {"workspace": "https://name:secret@workspace.example"},
        {"workspace": "https://workspace.example:444"},
        {"workspace": WORKSPACE + " "},
        {"workspace": "https://workspace\\.example"},
        {"workspace": "https://workspace\x00.example"},
        {"workspace": "https://workspace\x7f.example"},
        {"app_auth": "profile"},
        {"kind": "http", "url": TARGET_ORIGIN + "/invoke"},
    ],
)
def test_native_configuration_rejects_ambiguous_or_malformed_identity(updates):
    with pytest.raises(ValidationError):
        binding(**updates)


@pytest.mark.parametrize("source", ["process", "snapshot"])
@pytest.mark.parametrize(
    "selector",
    sorted(
        (set(SDK_PROFILE_OVERRIDE_ENV) - set(NATIVE_ENV) - {"DATABRICKS_AUTH_TYPE"})
        | {
            "DATABRICKS_CONFIG_PROFILE",
            "DATABRICKS_CONFIG_FILE",
            "DATABRICKS_CLI_PATH",
            "DATABRICKS_DEBUG_HEADERS",
        }
    ),
)
def test_native_guard_rejects_alternate_selectors_before_sdk(
    native_env, monkeypatch, source, selector
):
    monkeypatch.setattr(
        Config, "__init__", lambda *a, **k: pytest.fail("SDK constructed before guard")
    )
    if source == "process":
        monkeypatch.setenv(selector, "DO_NOT_DISCLOSE_SELECTOR")
        snapshot = native_env
    else:
        snapshot = {**native_env, selector: "DO_NOT_DISCLOSE_SELECTOR"}
    with configured_environment(snapshot), pytest.raises(TargetResolutionError) as error:
        _native_environment(WORKSPACE, CLIENT)
    assert "DO_NOT_DISCLOSE" not in str(error.value)


@pytest.mark.parametrize(
    "name,value",
    [
        ("DATABRICKS_HOST", "https://different.example"),
        ("DATABRICKS_CLIENT_ID", "66666666-2222-3333-4444-555555555555"),
        ("DATABRICKS_CLIENT_SECRET", ""),
        ("DATABRICKS_AUTH_TYPE", "pat"),
    ],
)
@pytest.mark.parametrize("source", ["process", "snapshot"])
def test_native_guard_rejects_identity_and_auth_mismatch(
    native_env, monkeypatch, name, value, source
):
    snapshot = native_env.copy()
    if source == "process":
        monkeypatch.setenv(name, value)
    else:
        snapshot[name] = value
    with configured_environment(snapshot), pytest.raises(TargetResolutionError):
        _native_environment(WORKSPACE, CLIENT)


def test_native_guard_does_not_relax_existing_profile_mode(native_env):
    with pytest.raises(TargetResolutionError):
        _reject_profile_overrides()
    with pytest.raises(ValidationError):
        Agent.databricks_app("target-agent")
    assert (
        Agent.databricks_app("target-agent", profile="operator").registration.app_auth == "profile"
    )


def test_native_guard_rejects_distinct_snapshot_secret(native_env):
    with (
        configured_environment({**native_env, "DATABRICKS_CLIENT_SECRET": "different"}),
        pytest.raises(TargetResolutionError),
    ):
        _native_environment(WORKSPACE, CLIENT)


@pytest.mark.parametrize("configured", [None, WORKSPACE_ID])
@pytest.mark.parametrize("actual", [None, "", WORKSPACE_ID, "54321"])
@pytest.mark.parametrize("snapshot", [None, "", WORKSPACE_ID, "54321"])
def test_native_workspace_id_requires_exact_operator_and_environment_agreement(
    native_env, monkeypatch, configured, actual, snapshot
):
    """Exercise only the pre-provider guard with synthetic native metadata."""
    monkeypatch.setattr(
        Config, "__init__", lambda *a, **k: pytest.fail("SDK constructed before guard")
    )
    values = native_env.copy()
    if actual is None:
        monkeypatch.delenv("DATABRICKS_WORKSPACE_ID", raising=False)
    else:
        monkeypatch.setenv("DATABRICKS_WORKSPACE_ID", actual)
    if snapshot is not None:
        values["DATABRICKS_WORKSPACE_ID"] = snapshot
    agrees = (configured == actual == snapshot == WORKSPACE_ID) or (
        configured is actual is snapshot is None
    )
    with configured_environment(values):
        if agrees:
            assert (
                _native_environment(WORKSPACE, CLIENT, configured)
                == NATIVE_ENV["DATABRICKS_CLIENT_SECRET"]
            )
        else:
            with pytest.raises(TargetResolutionError) as error:
                _native_environment(WORKSPACE, CLIENT, configured)
            assert WORKSPACE_ID not in str(error.value)
            assert "54321" not in str(error.value)


@pytest.mark.parametrize("invalid", ["", "0", "012345", "-1", "1.5", "1e3", "12345\n", "9" * 21])
def test_native_workspace_id_rejects_noncanonical_identifiers_before_sdk(invalid):
    """Validate private schema/guard rules without credential construction."""
    with pytest.raises(ValidationError):
        binding(workspace_id=invalid)
    with pytest.raises(ValidationError):
        Connection(url=TARGET_ORIGIN + "/api/invocations", workspace_id=invalid)
    with pytest.raises(TargetResolutionError):
        _native_environment(WORKSPACE, CLIENT, invalid)


def test_native_workspace_id_is_private_and_survives_operator_serialization():
    """Check binding/env/constructor propagation only; no SDK resolution occurs."""
    agent = Agent.databricks_app(
        "target-agent",
        auth="app-runtime",
        workspace=WORKSPACE,
        workspace_id=WORKSPACE_ID,
        runner_app="load-test",
        client_id=CLIENT,
    )
    preset = agent.registration
    assert preset.workspace_id == WORKSPACE_ID
    assert preset.operator_record()["workspace_id"] == WORKSPACE_ID
    assert "workspace_id" not in preset.model_dump()
    assert WORKSPACE_ID not in repr(preset)
    settings = Settings(connections={"agent": preset})
    environment = settings.to_environment({})
    restored = ConnectionSettings.model_validate(
        json.loads(environment["BENCHMARK_CONNECTIONS"])["agent"]
    )
    assert restored.workspace_id == WORKSPACE_ID
    assert "workspace_id" not in settings.model_dump_json()
    connection = Connection(
        url=TARGET_ORIGIN + "/api/invocations",
        auth="databricks-app",
        app_name="target-agent",
        app_auth="app-runtime",
        workspace=WORKSPACE,
        workspace_id=WORKSPACE_ID,
        runner_app="load-test",
        client_id=CLIENT,
    )
    copied = Agent(Target(url=connection.url, adapter="databricks-agent-runtime"), connection)
    assert copied.registration.workspace_id == WORKSPACE_ID
    assert WORKSPACE_ID not in repr(connection)
    request = RunCreate(
        target=TargetReference(connection_id="agent"), cases=[Case(input={"q": "x"})]
    )
    with pytest.raises(ValidationError):
        RunCreate.model_validate({**request.model_dump(), "workspace_id": WORKSPACE_ID})
    assert "workspace_id" not in request.model_dump_json()


def test_workspace_id_cannot_be_attached_to_profile_or_http_bindings():
    """Reject private native routing metadata without resolving a credential."""
    with pytest.raises(ValidationError):
        Agent.databricks_app("target-agent", profile="operator", workspace_id=WORKSPACE_ID)
    with pytest.raises(ValidationError):
        ConnectionSettings(url="https://agent.example/invoke", workspace_id=WORKSPACE_ID)
    for auth in ("none", "databricks-app"):
        connection = Connection(
            url=TARGET_ORIGIN + "/api/invocations",
            auth=auth,
            app_name="target-agent" if auth == "databricks-app" else None,
            profile="operator" if auth == "databricks-app" else None,
            workspace_id=WORKSPACE_ID,
        )
        with pytest.raises(ValueError):
            validate_connection(Target(url=connection.url), connection)


def test_native_workspace_id_does_not_relax_profile_environment_rejection(native_env, monkeypatch):
    """Profile checks reject injected routing metadata before provider construction."""
    monkeypatch.setenv("DATABRICKS_WORKSPACE_ID", WORKSPACE_ID)
    with (
        configured_environment({**native_env, "DATABRICKS_WORKSPACE_ID": WORKSPACE_ID}),
        pytest.raises(TargetResolutionError),
    ):
        _reject_profile_overrides()


def controlled_sdk(monkeypatch, *, runner=None, target=None, config_updates=None):
    """Provide native Apps types and synthetic OAuth tokens only; no transport/inference."""
    import databricks.sdk
    import databricks.sdk.core

    created = []
    calls = []
    runner = runner or App(
        name="load-test",
        service_principal_client_id=CLIENT,
        service_principal_id=12345,
        oauth2_app_client_id="66666666-2222-3333-4444-555555555555",
        resources=[
            AppResource(
                name="target-agent",
                app=AppResourceApp(
                    name="target-agent",
                    permission=AppResourceAppAppPermission.CAN_USE,
                ),
            )
        ],
    )
    target = target or App(name="target-agent", url=TARGET_ORIGIN)

    def construct_config(**values):
        assert values["credentials_strategy"] is oauth_service_principal
        assert values["auth_type"] == "oauth-m2m"
        assert values["host"] == WORKSPACE
        assert values["client_id"] == CLIENT
        assert "profile" not in values and "config_file" not in values
        token_count = 0

        def oauth_token():
            nonlocal token_count
            token_count += 1
            return SimpleNamespace(
                access_token=f"controlled-auth-{token_count}", token_type="Bearer"
            )

        config = SimpleNamespace(
            host=WORKSPACE,
            workspace_id=values.get("workspace_id"),
            client_id=CLIENT,
            auth_type="oauth-m2m",
            profile=None,
            config_file=None,
            oauth_token=oauth_token,
        )
        for name, value in (config_updates or {}).items():
            setattr(config, name, value)
        return config

    def sdk_client(*, config):
        def get(*, name):
            calls.append(name)
            return runner if name == "load-test" else target

        client = SimpleNamespace(config=config, apps=SimpleNamespace(get=get))
        created.append(client)
        return client

    # Replace only the importing module's constructor reference. Never alter the
    # real SDK class's special methods: undoing an inherited __new__ patch can
    # leave object.__new__ installed explicitly and poison later real SDK tests.
    construct_config.attributes = Config.attributes
    monkeypatch.setattr(databricks.sdk.core, "Config", construct_config)
    monkeypatch.setattr(databricks.sdk, "WorkspaceClient", sdk_client)
    return created, calls


@pytest.mark.parametrize("workspace_id", [None, WORKSPACE_ID])
def test_native_resolution_worker_refresh_and_exact_endpoint(native_env, monkeypatch, workspace_id):
    if workspace_id is not None:
        monkeypatch.setenv("DATABRICKS_WORKSPACE_ID", workspace_id)
        native_env["DATABRICKS_WORKSPACE_ID"] = workspace_id
    clients, calls = controlled_sdk(monkeypatch)
    with configured_environment(native_env):
        target, connection = resolve_registered_target(
            "agent", {"agent": binding(workspace_id=workspace_id)}
        )
        headers = authentication(connection)
    assert connection.url == TARGET_ORIGIN + "/api/invocations"
    assert connection.profile is None and connection.app_auth == "app-runtime"
    assert target.adapter == "databricks-agent-runtime"
    assert NATIVE_ENV["DATABRICKS_CLIENT_SECRET"] not in connection.model_dump_json()
    assert connection.workspace_id == workspace_id
    assert all(client.config.workspace_id == workspace_id for client in clients)
    assert len(clients) == 2  # Independent coordinator and worker providers.
    assert calls == ["load-test", "target-agent"] * 2
    assert headers() == {"Authorization": "Bearer controlled-auth-2"}
    assert headers() == {"Authorization": "Bearer controlled-auth-3"}
    assert calls == ["load-test", "target-agent"] * 2  # No per-dispatch App lookup.
    bad = connection.model_copy(update={"url": "https://attacker.example/api/invocations"})
    with configured_environment(native_env), pytest.raises(TargetResolutionError):
        authentication(bad)
    validate_connection(Target(url=connection.url), connection)


@pytest.mark.parametrize(
    "updates",
    [
        {"host": "https://different.example"},
        {"client_id": "different"},
        {"auth_type": "pat"},
        {"profile": "surprise"},
        {"config_file": "/private/surprise"},
    ],
)
def test_native_sdk_identity_must_agree(native_env, monkeypatch, updates):
    controlled_sdk(monkeypatch, config_updates=updates)
    with pytest.raises(TargetResolutionError) as error:
        resolve_registered_target("agent", {"agent": binding()})
    assert "surprise" not in str(error.value)


def test_native_sdk_workspace_id_must_match_before_resource_access(native_env, monkeypatch):
    """Controlled SDK metadata only; mismatched routing stops before Apps lookups."""
    monkeypatch.setenv("DATABRICKS_WORKSPACE_ID", WORKSPACE_ID)
    _, calls = controlled_sdk(monkeypatch, config_updates={"workspace_id": "54321"})
    with (
        configured_environment({**native_env, "DATABRICKS_WORKSPACE_ID": WORKSPACE_ID}),
        pytest.raises(TargetResolutionError),
    ):
        _native_workspace_app(binding(workspace_id=WORKSPACE_ID), "target-agent")
    assert calls == []


@pytest.mark.parametrize(
    "runner",
    [
        App(name="different", service_principal_client_id=CLIENT),
        App(name="load-test", service_principal_client_id="different"),
        App(name="load-test", service_principal_id=12345, oauth2_app_client_id=CLIENT),
        App(name="load-test", service_principal_client_id=CLIENT, resources=[]),
    ],
)
def test_native_runner_mapping_requires_sp_client_id_and_declared_target(
    native_env, monkeypatch, runner
):
    controlled_sdk(monkeypatch, runner=runner)
    with pytest.raises(TargetResolutionError):
        resolve_registered_target("agent", {"agent": binding()})


@pytest.mark.parametrize(
    "url",
    [
        "http://agent.example",
        "https://name:password@agent.example",
        TARGET_ORIGIN + "/other",
        TARGET_ORIGIN + "?token=private",
        TARGET_ORIGIN + "#private",
        "https://agent\\.example",
        "https://agent\x00.example",
        "https://agent\x7f.example",
        "https://agent\n.example",
        "https://agent.example:444",
    ],
)
def test_native_target_discovery_rejects_unsafe_origins(native_env, monkeypatch, url):
    controlled_sdk(monkeypatch, target=App(name="target-agent", url=url))
    with pytest.raises(TargetResolutionError) as error:
        resolve_registered_target("agent", {"agent": binding()})
    assert str(error.value) == "Native App identity, resource discovery or OAuth failed"
    assert error.value.__cause__ is None
    assert "password" not in str(error.value) and "private" not in str(error.value)


def test_native_metadata_cannot_be_attached_to_http_connections():
    with pytest.raises(ValueError):
        validate_connection(
            Target(url="https://agent.example/invoke"),
            Connection(
                url="https://agent.example/invoke",
                workspace=WORKSPACE,
            ),
        )


def test_native_diagnostics_are_static_secret_free_and_explicitly_unverified(monkeypatch):
    """Native configuration is not proof of OAuth readiness and makes no SDK calls."""
    monkeypatch.setattr(
        WorkspaceClient, "__init__", lambda *a, **k: pytest.fail("SDK construction")
    )
    report = startup_diagnostics(Settings(connections={"agent": binding()}), environ=NATIVE_ENV)
    checks = {check.code: check for check in report.checks}
    assert checks["target_app_native_auth_unverified"].status == "warning"
    assert "target_app_identity_conflict" not in checks
    assert report.configuration_only
    assert not report.capabilities.runtime_verified
    serialized = report.model_dump_json()
    for private in (WORKSPACE, CLIENT, NATIVE_ENV["DATABRICKS_CLIENT_SECRET"]):
        assert private not in serialized


@pytest.mark.parametrize("workspace_id", [None, WORKSPACE_ID])
def test_native_real_sdk_controlled_http_discovers_and_refreshes_independent_tokens(
    native_env, monkeypatch, workspace_id
):
    """Exercise real SDK OAuth and Apps parsing against controlled HTTP, never inference.

    Only HTTP responses are synthetic. Config, WorkspaceClient, the native OAuth
    strategy and ClientCredentials are real. Expiring the captured worker token
    verifies synchronous refresh deterministically without sleeps or paid calls.
    """
    if workspace_id is not None:
        monkeypatch.setenv("DATABRICKS_WORKSPACE_ID", workspace_id)
        native_env["DATABRICKS_WORKSPACE_ID"] = workspace_id
    exchanges = []
    lookups = []
    sources = []
    original_refresh = oauth.ClientCredentials.refresh

    def observed_refresh(source):
        if not any(existing is source for existing in sources):
            sources.append(source)
        return original_refresh(source)

    def controlled_send(session, request, **kwargs):
        """Return bounded fixture JSON at the actual requests transport boundary."""
        assert request.url.startswith(WORKSPACE + "/")
        if request.url == WORKSPACE + "/.well-known/databricks-config":
            assert request.method == "GET"
            payload = {"oidc_endpoint": WORKSPACE + "/oidc", "workspace_id": WORKSPACE_ID}
        elif request.url == WORKSPACE + "/oidc/.well-known/oauth-authorization-server":
            assert request.method == "GET"
            payload = {
                "token_endpoint": WORKSPACE + "/oidc/v1/token",
                "authorization_endpoint": WORKSPACE + "/oidc/v1/authorize",
            }
        elif request.url == WORKSPACE + "/oidc/v1/token":
            assert request.method == "POST"
            assert request.headers["Authorization"].startswith("Basic ")
            body = request.body.decode() if isinstance(request.body, bytes) else request.body
            assert parse_qs(body)["grant_type"] == ["client_credentials"]
            assert parse_qs(body)["scope"] == ["all-apis"]
            exchanges.append(request.url)
            payload = {
                "access_token": f"controlled-native-{len(exchanges)}",
                "token_type": "Bearer",
                "expires_in": 3600,
            }
        elif request.url == WORKSPACE + "/api/2.0/apps/load-test":
            assert request.method == "GET"
            assert request.headers["Authorization"].startswith("Bearer controlled-native-")
            lookups.append("load-test")
            payload = {
                "name": "load-test",
                "service_principal_client_id": CLIENT,
                "service_principal_id": 12345,
                "oauth2_app_client_id": "66666666-2222-3333-4444-555555555555",
                "resources": [
                    {
                        "name": "target-agent",
                        "app": {"name": "target-agent", "permission": "CAN_USE"},
                    }
                ],
            }
        elif request.url == WORKSPACE + "/api/2.0/apps/target-agent":
            assert request.method == "GET"
            assert request.headers["Authorization"].startswith("Bearer controlled-native-")
            lookups.append("target-agent")
            payload = {"name": "target-agent", "url": TARGET_ORIGIN}
        else:
            pytest.fail("Unexpected SDK HTTP operation; controlled test must stay bounded")
        response = requests.Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response._content = json.dumps(payload).encode()
        response.request = request
        response.url = request.url
        return response

    monkeypatch.setattr(requests.Session, "send", controlled_send)
    monkeypatch.setattr(oauth.ClientCredentials, "refresh", observed_refresh)
    with configured_environment(native_env):
        workspace, origin = _native_workspace_app(
            binding(workspace_id=workspace_id), "target-agent"
        )
    assert isinstance(workspace, WorkspaceClient)
    assert isinstance(workspace.config, Config)
    assert workspace.config._credentials_strategy is oauth_service_principal
    assert workspace.config.auth_type == "oauth-m2m"
    assert workspace.config.workspace_id == WORKSPACE_ID
    assert origin == TARGET_ORIGIN
    connection = Connection(
        url=origin + "/api/invocations",
        auth="databricks-app",
        app_name="target-agent",
        app_auth="app-runtime",
        workspace=WORKSPACE,
        workspace_id=workspace_id,
        runner_app="load-test",
        client_id=CLIENT,
    )
    with configured_environment(native_env):
        headers = authentication(connection)
    assert len(sources) == len(exchanges) == 2
    assert sources[0] is not sources[1]
    assert headers() == {"Authorization": "Bearer controlled-native-2"}
    sources[1]._token.expiry = datetime.now() - timedelta(seconds=1)
    assert headers() == {"Authorization": "Bearer controlled-native-3"}
    assert len(exchanges) == 3
    assert lookups == ["load-test", "target-agent"] * 2
    assert NATIVE_ENV["DATABRICKS_CLIENT_SECRET"] not in connection.model_dump_json()
