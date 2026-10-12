"""Pure operator-binding checks; no authentication, provider or agent calls.

Environment markers here are inert disclosure sentinels, never model responses.
The real SDK constructors validate configuration without resolving credentials.
"""

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from examples.journeys import framework_runner_matrix as matrix
from examples.journeys import local_runner_http_target as local
from examples.journeys.app_runner import runner as app_runner

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = "APPROVED_AGENT_BEARER_TOKEN"
VALUE_SENTINEL = "INERT_CREDENTIAL_VALUE_NOT_FOR_EXPORT"
HTTPS_ENDPOINT = "https://agent.example.invalid/invoke"


def app_configuration(**updates) -> app_runner.OperatorConfig:
    """Read a disabled template; neither credentials nor cloud resources are read."""
    path = ROOT / "examples/journeys/app_runner/operator.example.json"
    values = json.loads(path.read_text())
    return app_runner.OperatorConfig.model_validate({**values, **updates})


def http_configuration(**updates) -> app_runner.OperatorConfig:
    """Construct fixed HTTP operator settings without an App OAuth selection."""
    return app_configuration(
        target_kind="http",
        http_url=HTTPS_ENDPOINT,
        app_name=None,
        profile=None,
        oauth_config_file=None,
        oauth_client_id=None,
        **updates,
    )


@pytest.mark.parametrize("runner", ("local", "databricks-app"))
def test_matrix_bearer_reference_is_inert_exact_bound_and_outside_request(
    runner: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only construct native DTOs; the marker is not read for authentication."""
    monkeypatch.setenv(REFERENCE, VALUE_SENTINEL)
    journey = matrix.Journey("langgraph", runner, "http")
    agent = matrix.binding(journey, http_url=HTTPS_ENDPOINT, bearer_token_env=REFERENCE)
    assert agent.connection.auth == "bearer"
    assert agent.connection.token_env == REFERENCE
    assert agent.connection.url == str(agent.target.url) == HTTPS_ENDPOINT
    output = matrix.request(journey).model_dump_json()
    assert REFERENCE not in output
    assert VALUE_SENTINEL not in output
    assert HTTPS_ENDPOINT not in output


@pytest.mark.parametrize("runner", matrix.RUNNERS)
@pytest.mark.parametrize("reference", [REFERENCE, ""])
def test_matrix_app_target_rejects_http_credential_selection(runner: str, reference: str) -> None:
    """Reject mixed host/auth choices before discovery or credential access."""
    with pytest.raises(ValueError, match="HTTP bearer"):
        matrix.binding(
            matrix.Journey("openai-agents", runner, "databricks-app"),
            app_name="approved-agent-app",
            profile="approved-profile",
            bearer_token_env=reference,
        )


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]"])
def test_local_and_matrix_bearer_require_https_even_for_loopback(host: str) -> None:
    """HTTP stays available without auth, but may never carry this bearer binding."""
    endpoint = f"http://{host}:9001/invoke"
    with pytest.raises(ValueError, match="Bearer.*HTTPS"):
        local.binding(endpoint, bearer_token_env=REFERENCE)
    with pytest.raises(ValueError, match="Bearer.*HTTPS"):
        matrix.binding(
            matrix.Journey("crewai", "local", "http"),
            http_url=endpoint,
            bearer_token_env=REFERENCE,
        )
    assert local.binding(endpoint).connection.auth == "none"


@pytest.mark.parametrize("reference", ["", "has-hyphen", " Bearer token", "A\nB", "1BAD", 3])
def test_local_and_matrix_reject_values_that_are_not_environment_names(reference) -> None:
    """Fixed rejection prevents mistakenly pasted values from becoming guidance."""
    for construct in (
        lambda: local.binding(HTTPS_ENDPOINT, bearer_token_env=reference),
        lambda: matrix.binding(
            matrix.Journey("crewai", "local", "http"),
            http_url=HTTPS_ENDPOINT,
            bearer_token_env=reference,
        ),
    ):
        with pytest.raises(ValueError, match="environment-variable name") as error:
            construct()
        if reference:
            assert str(reference) not in str(error.value)


def test_matrix_cli_prints_only_workload_not_bearer_reference_or_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Invoke the print-only CLI; native constructors do not make network calls."""
    monkeypatch.setenv(REFERENCE, VALUE_SENTINEL)
    monkeypatch.setattr(
        "sys.argv",
        [
            "matrix",
            "request",
            "--framework",
            "crewai",
            "--runner",
            "local",
            "--hosting",
            "http",
            "--http-url",
            HTTPS_ENDPOINT,
            "--bearer-token-env",
            REFERENCE,
        ],
    )
    matrix.main()
    output = capsys.readouterr().out
    assert json.loads(output)["target"] == {"connection_id": "agent"}
    assert all(marker not in output for marker in (REFERENCE, VALUE_SENTINEL, HTTPS_ENDPOINT))


def test_local_binding_uses_reference_without_changing_smoke_or_reading_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(REFERENCE, VALUE_SENTINEL)
    agent = local.binding(HTTPS_ENDPOINT, bearer_token_env=REFERENCE)
    assert agent.connection.auth == "bearer"
    assert agent.connection.token_env == REFERENCE
    config = local.request()
    assert config.load.max_requests == 5
    assert config.load.concurrency == 5
    assert config.evaluation.mode == "off"
    assert all(marker not in config.model_dump_json() for marker in (REFERENCE, VALUE_SENTINEL))


def test_local_cli_invalid_bearer_reference_fails_before_client_creation_without_disclosure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Intentional schema rejection calls no SDK client, worker, agent or provider."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "local-http",
            HTTPS_ENDPOINT,
            "--allow-paid-inference",
            "--bearer-token-env",
            "Bearer " + VALUE_SENTINEL,
        ],
    )
    with pytest.raises(SystemExit) as error:
        local.main()
    assert error.value.code == 2
    output = capsys.readouterr()
    assert VALUE_SENTINEL not in output.out + output.err
    assert "Review the exact endpoint" in output.err


def test_matrix_cli_invalid_bearer_reference_uses_value_free_guidance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The configuration-only CLI must not print a mistakenly pasted auth value."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "matrix",
            "request",
            "--framework",
            "langgraph",
            "--runner",
            "local",
            "--hosting",
            "http",
            "--http-url",
            HTTPS_ENDPOINT,
            "--bearer-token-env",
            "Bearer " + VALUE_SENTINEL,
        ],
    )
    with pytest.raises(SystemExit) as error:
        matrix.main()
    assert error.value.code == 2
    output = capsys.readouterr()
    assert VALUE_SENTINEL not in output.out + output.err
    assert "environment-variable name" in output.err


@pytest.mark.parametrize("runner_cli", ["matrix", "local"])
@pytest.mark.parametrize(
    "endpoint, marker",
    [
        (
            "HTTPS://u:PWD_MARK@a.invalid:BADPORT/invoke",
            "PWD_MARK",
        ),
        (
            "https://a.invalid:BADPORT/invoke",
            "BADPORT",
        ),
    ],
)
def test_sample_cli_url_schema_rejection_never_prints_submitted_values(
    runner_cli: str,
    endpoint: str,
    marker: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject real CLI configuration before any auth/worker/provider call."""
    arguments = (
        [
            "matrix",
            "request",
            "--framework",
            "langgraph",
            "--runner",
            "local",
            "--hosting",
            "http",
            "--http-url",
            endpoint,
        ]
        if runner_cli == "matrix"
        else ["local-http", endpoint, "--allow-paid-inference"]
    )
    monkeypatch.setattr("sys.argv", arguments)
    with pytest.raises(SystemExit) as error:
        (matrix if runner_cli == "matrix" else local).main()
    assert error.value.code == 2
    output = capsys.readouterr()
    assert marker not in output.out + output.err
    assert endpoint not in output.out + output.err
    assert "Review" in output.err


def test_app_http_binding_keeps_reference_outside_workload_and_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(REFERENCE, VALUE_SENTINEL)
    config = http_configuration(bearer_token_env=REFERENCE)
    assert config.enabled is False
    agent = app_runner.http_binding(config)
    assert agent.connection.auth == "bearer"
    assert agent.connection.token_env == REFERENCE
    assert agent.connection.url == str(agent.target.url) == HTTPS_ENDPOINT
    assert REFERENCE not in repr(config)
    assert all(
        marker not in app_runner.request().model_dump_json()
        for marker in (REFERENCE, VALUE_SENTINEL, HTTPS_ENDPOINT)
    )
    assert app_runner.http_binding(http_configuration()).connection.auth == "none"


def test_app_target_rejects_http_bearer_reference_and_binding_helper() -> None:
    with pytest.raises(ValidationError):
        app_configuration(bearer_token_env=REFERENCE)
    with pytest.raises(ValueError, match="HTTP target"):
        app_runner.http_binding(app_configuration())


@pytest.mark.parametrize("reference", ["", "has-hyphen", " Bearer token", "A\nB", "1BAD", 3])
def test_app_rejects_malformed_operator_reference_without_network(reference) -> None:
    with pytest.raises(ValidationError):
        http_configuration(bearer_token_env=reference)


def test_app_read_config_does_not_disclose_mistakenly_pasted_auth_values(tmp_path: Path) -> None:
    values = json.loads((ROOT / "examples/journeys/app_runner/operator.example.json").read_text())
    values["bearer_token_env"] = "Bearer " + VALUE_SENTINEL
    path = tmp_path / "operator.json"
    path.write_text(json.dumps(values))
    with pytest.raises(ValueError) as error:
        app_runner.read_config(path)
    assert VALUE_SENTINEL not in str(error.value)
    assert "Bearer" not in str(error.value)


def test_app_benchmark_uses_reviewed_binding_and_retains_context_cancellation() -> None:
    """AST-only wiring check; never start a worker or substitute an agent result."""
    tree = ast.parse((ROOT / "examples/journeys/app_runner/runner.py").read_text())
    benchmark = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_http_run"
    )
    code = ast.unparse(benchmark)
    assert "http_binding(config)" in code
    assert "await _direct_run(http_binding(config), artifact_dir)" in code
    assert "CancelledError" not in code
    assert "Agent.http(config.http_url" not in code
    direct = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_direct_run"
    )
    assert "async with EvalSurge.local_async" in ast.unparse(direct)
    # The shared owner may preserve a failed-run report, but cancellation and
    # other exceptions must propagate through SDK context cleanup.
    handlers = [node for node in ast.walk(direct) if isinstance(node, ast.ExceptHandler)]
    assert handlers
    assert all(
        isinstance(handler.type, ast.Name) and handler.type.id == "RunFailed"
        for handler in handlers
    )
