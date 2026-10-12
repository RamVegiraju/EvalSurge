"""Pure matrix/schema checks: no framework execution, model fixtures, auth or traffic."""

import ast
import json
from collections import Counter
from pathlib import Path

import pytest

from evalsurge import Case
from examples.journeys.framework_runner_matrix import (
    SAMPLE_REFERENCE,
    Journey,
    binding,
    journeys,
    main,
    request,
)


def test_matrix_covers_all_fifteen_requested_combinations() -> None:
    """Validate inventory structure, not installed-environment or inference support."""
    matrix = journeys()
    assert len(matrix) == len({item.id for item in matrix}) == 15
    assert Counter(item.framework for item in matrix) == {
        "crewai": 5,
        "langgraph": 5,
        "openai-agents": 5,
    }
    assert Counter(item.runner for item in matrix) == {
        "local": 6,
        "serverless-notebook": 3,
        "databricks-app": 6,
    }
    assert Counter(item.hosting for item in matrix) == {"http": 6, "databricks-app": 9}
    assert all(
        item.hosting == "databricks-app" for item in matrix if item.runner == "serverless-notebook"
    )


def test_primary_local_onboarding_has_two_hostings_for_each_real_framework() -> None:
    """Select the six local labels without running agents or discarding cloud sources."""
    local = [item for item in journeys() if item.runner == "local"]
    assert len(local) == 6
    assert {(item.framework, item.hosting) for item in local} == {
        (framework, hosting)
        for framework in ("crewai", "langgraph", "openai-agents")
        for hosting in ("http", "databricks-app")
    }
    assert Counter(item.runner for item in journeys() if item not in local) == {
        "serverless-notebook": 3,
        "databricks-app": 6,
    }


def test_matrix_guide_distinguishes_primary_inventory_from_unverified_cloud_sources() -> None:
    """Inspect scope/evidence labels only; no live receipt or source agent is executed."""
    root = Path(__file__).resolve().parents[1]
    guide = (root / "examples/journeys/FRAMEWORK_MATRIX.md").read_text()
    primary = guide.split("## Six local-runner combinations", 1)[1].split(
        "## Retained cloud-runner sources", 1
    )[0]
    rows = [line for line in primary.splitlines() if line.startswith("| ")][2:]
    assert len(rows) == 6
    assert all("| Local Python |" in row for row in rows)
    evidenced = [
        row for row in rows if "Current installed-wheel real-model basic smoke passed" in row
    ]
    blocked = [row for row in rows if "| CrewAI |" in row]
    assert len(evidenced) == 4
    assert len(blocked) == 2 and not any("basic smoke passed" in row for row in blocked)
    assert "four of six successful basic live cells" in primary
    assert "not six passes or complete" in primary
    assert "did not exercise the published five-request scripts unchanged" in primary
    assert "current-template App deployment" in primary
    assert "ChromaDB advisory gate" in primary
    assert "notebook validation is **deferred**" in guide
    assert "all fifteen" in guide and 'runner == "local"' in guide
    assert "No EvalSurge\nAPI server, notebook or runner App is needed" in guide


@pytest.mark.parametrize("journey", journeys(), ids=lambda item: item.id)
def test_every_combination_uses_identical_public_workload(journey: Journey) -> None:
    """Construct v2 objects; framework names are labels, not adapter routing."""
    actual = request(journey).model_dump(mode="json", exclude={"name"})
    assert actual == request(journeys()[0]).model_dump(mode="json", exclude={"name"})
    assert actual["evaluation"]["mode"] == "off"
    assert actual["load"]["concurrency"] == actual["load"]["max_requests"] == 1
    assert actual["load"]["duration_seconds"] == 10
    assert actual["target"] == {"connection_id": "agent"}
    assert "profile" not in request(journey).model_dump_json()


@pytest.mark.parametrize("runner", ("databricks-app",))
@pytest.mark.parametrize(
    "host",
    (
        "localhost",
        "localhost.",
        "agent.localhost",
        "127.0.0.1",
        "127.1.2.3",
        "[::1]",
        "0.0.0.0",
        "[::]",
    ),
)
def test_cloud_http_target_cannot_silently_be_laptop_loopback(runner: str, host: str) -> None:
    """Intentional pre-network rejection; no auth or inference is attempted."""
    with pytest.raises(ValueError, match="Cloud runners cannot reach"):
        binding(Journey("langgraph", runner, "http"), http_url=f"https://{host}/invoke")


@pytest.mark.parametrize("journey", journeys(), ids=lambda item: item.id)
def test_bindings_keep_provider_configuration_outside_requests(journey: Journey) -> None:
    """Use inert SDK constructors with reserved example origins, never invoke them."""
    if journey.hosting == "http":
        target = binding(journey, http_url="https://agent.example.invalid/invoke")
        assert target.registration.protocols == ("http-json",)
    else:
        target = binding(
            journey, app_name="approved-agent-app", profile="explicit-operator-profile"
        )
        assert target.registration.app_name == "approved-agent-app"
        assert target.registration.profile == "explicit-operator-profile"
    assert "explicit-operator-profile" not in request(journey).model_dump_json()


def test_local_http_and_app_configuration_require_exact_unmixed_targets() -> None:
    """Construct inert endpoints and reject ambiguous selections before any network."""
    local = Journey("crewai", "local", "http")
    assert str(binding(local, http_url="http://127.0.0.1:9001/invoke").target.url).startswith(
        "http://127.0.0.1"
    )
    with pytest.raises(ValueError, match="HTTP target requires only"):
        binding(local, http_url="http://127.0.0.1:9001/invoke", profile="not-consumed")
    with pytest.raises(ValueError, match="exact App name and explicit profile"):
        binding(Journey("openai-agents", "local", "databricks-app"), app_name="agent-app")


@pytest.mark.parametrize("runner", ("databricks-app",))
@pytest.mark.parametrize("host", ("agent.example.com", "agent.example.invalid", "192.0.2.12"))
def test_cloud_http_target_explicitly_requires_https(runner: str, host: str) -> None:
    """Reject in the matrix helper before relying on downstream credential policy."""
    with pytest.raises(ValueError, match="Cloud HTTP targets require HTTPS"):
        binding(
            Journey("crewai", runner, "http"),
            http_url=f"http://{host}/invoke",
        )


@pytest.mark.parametrize("host", ("127.0.0.1", "localhost", "[::1]"))
def test_local_loopback_http_binding_remains_supported(host: str) -> None:
    """Construct the existing local target only, with no DNS/socket or inference."""
    target = binding(Journey("crewai", "local", "http"), http_url=f"http://{host}:9001/invoke")
    assert str(target.target.url).startswith(f"http://{host}:9001/")


@pytest.mark.parametrize(
    "values",
    (
        ("not-a-framework", "local", "http"),
        ("crewai", "classic", "http"),
        ("crewai", "local", "serverless"),
    ),
)
def test_matrix_rejects_unknown_classification(values: tuple[str, str, str]) -> None:
    """A runner location must never be accepted as an agent-hosting kind."""
    with pytest.raises(ValueError, match="explicit framework"):
        Journey(*values)


def test_matrix_module_is_ordinary_python_with_no_execution_side_effect_at_import() -> None:
    """Read/compile source and inspect import syntax, not agent behavior."""
    path = Path(__file__).resolve().parents[1] / "examples/journeys/framework_runner_matrix.py"
    source = path.read_text()
    compile(source, str(path), "exec")
    modules = {
        node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)
    }
    assert "evalsurge" in modules
    assert not modules.intersection({"agents", "crewai", "langgraph.graph"})


def test_inventory_cli_never_labels_configuration_as_live_validation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Run a local print-only entrypoint; no transport/provider replacement is used."""
    monkeypatch.setattr("sys.argv", ["framework_runner_matrix", "matrix"])
    main()
    document = json.loads(capsys.readouterr().out)
    assert document["validation"] == "logical-inventory-only"
    assert len(document["journeys"]) == 15
    assert document["serverless_scope"] == "deployed-app-targets-only"
    assert document["retained_optional_sample"] == "serverless-http-outside-requested-validation"
    assert all(item["fresh_live_validation"] == "not_run" for item in document["journeys"])
    conditional_http = [
        item
        for item in document["journeys"]
        if item["runner"] == "databricks-app" and item["target_hosting"] == "http"
    ]
    assert len(conditional_http) == 3
    assert all(
        item["http_reachability"] == "approved-reachable-https-required"
        for item in conditional_http
    )


@pytest.mark.parametrize("framework", ("crewai", "langgraph", "openai-agents"))
def test_active_serverless_scope_rejects_http_but_retains_optional_source(framework: str) -> None:
    """Scope rejection is not an inference test or deletion of the optional example."""
    with pytest.raises(
        ValueError, match="serverless notebook validation targets deployed Apps only"
    ):
        Journey(framework, "serverless-notebook", "http")
    source = (
        Path(__file__).resolve().parents[1] / "examples/journeys/serverless_runner_http_target.py"
    )
    assert source.is_file()


def test_serverless_http_cli_request_is_outside_active_validation_scope(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Run a rejected print-only command, without any driver or agent call."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "matrix",
            "request",
            "--framework",
            "langgraph",
            "--runner",
            "serverless-notebook",
            "--hosting",
            "http",
            "--http-url",
            "https://agent.example.invalid/invoke",
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    output = capsys.readouterr()
    assert not output.out
    assert "serverless notebook validation targets deployed Apps only" in output.err
    assert "agent.example.invalid" not in output.err


def test_request_cli_prints_workload_without_profile_or_target_origin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Use a native inert App constructor; no SDK discovery/authentication occurs."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "framework_runner_matrix",
            "request",
            "--framework",
            "langgraph",
            "--runner",
            "serverless-notebook",
            "--hosting",
            "databricks-app",
            "--app-name",
            "private-selected-app",
            "--profile",
            "private-selected-profile",
        ],
    )
    main()
    output = capsys.readouterr().out
    document = json.loads(output)
    assert document["target"] == {"connection_id": "agent"}
    assert "private-selected" not in output
    assert document["evaluation"]["mode"] == "off"


def test_cloud_request_cli_rejects_laptop_loopback_without_running_traffic(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Check intentional pre-network failure separately from model validation."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "framework_runner_matrix",
            "request",
            "--framework",
            "crewai",
            "--runner",
            "databricks-app",
            "--hosting",
            "http",
            "--http-url",
            "https://127.0.0.1/invoke",
        ],
    )
    with pytest.raises(SystemExit) as exit_info:
        main()
    assert exit_info.value.code == 2
    assert "Review exact target selection, reachable HTTPS URL" in capsys.readouterr().err


@pytest.mark.parametrize("journey", journeys(), ids=lambda item: item.id)
def test_explicit_evaluation_uses_authorized_sample_reference_not_target_input(
    journey: Journey,
) -> None:
    """Construct policy only; no target, planner, judge or stubbed completion runs."""
    config = request(journey, evaluation="explicit", sample_refund_policy=True)
    assert config.evaluation.mode == "explicit"
    assert config.evaluation.scorers == ["relevance", "correctness"]
    assert config.evaluation.max_scored_requests == 1
    assert config.cases[0].reference == {"expected_facts": [SAMPLE_REFERENCE]}
    assert config.cases[0].input == {"query": "Can an opened item be refunded?"}
    assert config.load == request(journey).load
    assert config.target == request(journey).target


def test_sample_reference_is_grounded_in_customer_owned_handler_source() -> None:
    """Read the literal policy via AST, never import/execute a customer agent."""
    path = Path(__file__).resolve().parents[1] / "examples/real_framework_handler.py"
    tree = ast.parse(path.read_text())
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "POLICY" for target in node.targets)
    )
    policy = ast.literal_eval(assignment.value)
    assert SAMPLE_REFERENCE in policy


@pytest.mark.parametrize(
    "reference",
    (
        {},
        {"other_metadata": "not truth"},
        {"expected_facts": []},
        {"expected_facts": [""]},
        {"expected_response": "  "},
    ),
)
def test_explicit_evaluation_does_not_invent_authoritative_reference(reference: dict) -> None:
    """Intentional pre-provider configuration failures make no inference call."""
    journey = Journey("crewai", "local", "http")
    with pytest.raises(ValueError, match="authoritative"):
        request(
            journey,
            evaluation="explicit",
            case=Case(input={"query": "Custom input"}, reference=reference),
        )
    with pytest.raises(ValueError, match="confirm the sample refund policy"):
        request(journey, evaluation="explicit")


def test_explicit_custom_case_is_detached_and_does_not_assume_refund_truth() -> None:
    """Keep caller-supplied evidence authoritative without sharing mutable lists."""
    case = Case(
        input={"query": "What is the authorized demo color?"},
        reference={"expected_response": "Blue."},
    )
    config = request(Journey("langgraph", "local", "http"), evaluation="explicit", case=case)
    case.reference["expected_response"] = "Changed after construction."
    assert config.cases[0].reference == {"expected_response": "Blue."}
    assert "refund" not in config.evaluation.description
    assert request(Journey("langgraph", "local", "http"), case=case).evaluation.mode == "off"


def test_sample_policy_and_custom_case_cannot_be_silently_mixed() -> None:
    """Reject ignored truth selectors and automatic-provider opt-in at construction."""
    journey = Journey("openai-agents", "local", "databricks-app")
    with pytest.raises(ValueError, match="confirmed sample policy"):
        request(journey, sample_refund_policy=True)
    with pytest.raises(ValueError, match="confirmed sample policy"):
        request(
            journey,
            evaluation="explicit",
            sample_refund_policy=True,
            case=Case(input={"query": "Custom"}, reference={"expected_response": "Caller answer"}),
        )
    with pytest.raises(ValueError, match="no automatic planner"):
        request(journey, evaluation="automatic")


def test_explicit_cli_requires_selected_truth_and_prints_no_provider_configuration(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exercise only argument parsing, inert binding and schema JSON rendering."""
    arguments = [
        "framework_runner_matrix",
        "request",
        "--framework",
        "crewai",
        "--runner",
        "local",
        "--hosting",
        "http",
        "--http-url",
        "http://127.0.0.1:9001/invoke",
        "--evaluation",
        "explicit",
    ]
    monkeypatch.setattr("sys.argv", arguments)
    with pytest.raises(SystemExit) as exit_info:
        main()
    assert exit_info.value.code == 2
    assert "authoritative references or confirmed sample refund policy" in capsys.readouterr().err
    monkeypatch.setattr("sys.argv", [*arguments, "--sample-refund-policy"])
    main()
    document = json.loads(capsys.readouterr().out)
    assert document["evaluation"]["scorers"] == ["relevance", "correctness"]
    assert document["cases"][0]["reference"] == {"expected_facts": [SAMPLE_REFERENCE]}
    assert "provider" not in document and "profile" not in document
