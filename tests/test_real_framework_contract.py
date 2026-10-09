"""No-inference configuration/input checks; not real-model success evidence."""

import ast
import inspect

import pytest

from examples.real_framework_agent import (
    ModelSelection,
    build_handler,
    create_real_app,
    main,
    response_completion_guard,
    validate_completion_metadata,
    validate_inputs,
)


def selection(**updates):
    """Build declarative operator data only; no SDK profile or client resolution."""
    return ModelSelection(
        **{
            "profile": "explicit-test-profile",
            "model": "system.ai.gpt-oss-120b",
            "api": "mlflow-responses",
            "expected_host": "https://selected-workspace.cloud.databricks.com",
            **updates,
        }
    )


@pytest.mark.parametrize(
    ("api", "suffix"),
    [("mlflow-responses", "mlflow/v1"), ("openai-responses", "openai/v1")],
)
def test_exact_responses_route(api, suffix):
    assert selection(api=api).base_url == (
        f"https://selected-workspace.cloud.databricks.com/ai-gateway/{suffix}"
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"profile": " "},
        {"model": ""},
        {"api": "auto"},
        {"expected_host": "http://workspace"},
        {"expected_host": "https://workspace/path"},
        {"expected_host": "https://user@workspace"},
        {"max_output_tokens": 513},
        {"max_output_tokens": 0},
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": 31},
    ],
)
def test_invalid_selection_before_any_sdk_resolution(updates):
    with pytest.raises(ValueError):
        selection(**updates)


@pytest.mark.parametrize(
    "inputs", [{}, {"query": " "}, {"query": 3}, {"query": "x", "actor": "y"}, {"query": "x" * 513}]
)
def test_declared_input_rejects_unsupported_fields_before_provider(inputs):
    with pytest.raises(ValueError):
        validate_inputs(inputs)


def test_declared_input_preserves_original_text():
    query = " Can an opened item be refunded? "
    assert validate_inputs({"query": query}) == query


@pytest.mark.parametrize("framework", ["langgraph", "openai-agents", "crewai"])
def test_dry_run_requires_no_framework_provider_or_profile(monkeypatch, capsys, framework):
    main(
        [
            "--framework",
            framework,
            "--profile",
            "nonexistent-explicit-profile",
            "--model",
            "system.ai.gpt-oss-120b",
            "--api",
            "mlflow-responses",
            "--workspace-host",
            "https://selected-workspace.cloud.databricks.com",
        ]
    )
    assert "no inference" in capsys.readouterr().out


def test_live_requires_paid_consent_before_startup():
    with pytest.raises(SystemExit):
        main(
            [
                "--framework",
                "langgraph",
                "--profile",
                "nonexistent-explicit-profile",
                "--model",
                "system.ai.gpt-oss-120b",
                "--api",
                "mlflow-responses",
                "--workspace-host",
                "https://selected-workspace.cloud.databricks.com",
                "--live",
            ]
        )


@pytest.mark.parametrize("framework", ["langgraph", "openai-agents"])
async def test_native_wiring_with_intentional_pre_provider_rejection(framework):
    """Construct real framework/client objects, never supplying provider completions.

    Invalid input is rejected before inference. This is not successful real-model
    execution, and does not replace the separately gated live integration matrix.
    """
    import httpx
    from openai import AsyncOpenAI

    from evalsurge.serving import InvocationContext

    selected = selection()
    async with (
        httpx.AsyncClient(event_hooks={"response": [response_completion_guard]}) as http,
        AsyncOpenAI(
            base_url=selected.base_url,
            api_key="constructor-only-no-traffic",
            max_retries=0,
            http_client=http,
        ) as client,
    ):
        handler = build_handler(framework, client, selected, http_client=http)
        context = InvocationContext(None, "not-dispatched", None, "not-dispatched")
        with pytest.raises(ValueError, match="exactly one nonblank query"):
            await handler({"query": "x", "unsupported": True}, context)


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        [],
        None,
        {"status": None},
        {"status": "queued"},
        {"status": "in_progress"},
        {"status": "failed"},
        {"status": "incomplete"},
        {"status": "cancelled"},
        {"status": "future-status"},
    ],
)
def test_nonterminal_metadata_is_never_a_completed_response(metadata):
    """Pure status documents only: no fabricated answer or provider completion."""
    with pytest.raises(ValueError, match="did not complete"):
        validate_completion_metadata(metadata)


def test_terminal_metadata_check_is_not_an_answer_or_inference_claim():
    validate_completion_metadata({"status": "completed"})


async def test_native_httpx_hook_rejects_nonterminal_metadata():
    """Exercise the actual hook on status-only bytes, not a model completion."""
    import httpx

    response = httpx.Response(200, json={"status": "in_progress"})
    with pytest.raises(ValueError, match="did not complete"):
        await response_completion_guard(response)


async def test_native_httpx_hook_preserves_http_error_handling():
    """An HTTP rejection needs no invented answer or provider-error payload."""
    import httpx

    response = httpx.Response(401)
    await response_completion_guard(response)


async def test_nonstreaming_guard_rejects_sse_without_answer_parsing():
    """Headers alone establish the unsupported contract; no SSE data is supplied."""
    import httpx

    response = httpx.Response(200, headers={"Content-Type": "text/event-stream"})
    with pytest.raises(ValueError, match="nonstreaming Responses only"):
        await response_completion_guard(response)


async def test_native_client_without_raw_status_guard_rejected_before_provider():
    import httpx
    from openai import AsyncOpenAI

    selected = selection()
    async with (
        httpx.AsyncClient() as http,
        AsyncOpenAI(
            base_url=selected.base_url, api_key="constructor-only-no-traffic", http_client=http
        ) as client,
    ):
        with pytest.raises(ValueError, match="guarded HTTPX"):
            build_handler("openai-agents", client, selected, http_client=http)


def test_native_workspace_constructor_accepts_sample_timeout_configuration():
    """Bind real installed signatures to AST-only setup; no profile/network access."""
    from databricks.sdk import WorkspaceClient

    tree = ast.parse(inspect.getsource(create_real_app))
    constructors = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "WorkspaceClient"
    ]
    assert len(constructors) == 1
    constructor = constructors[0]
    keywords = {item.arg: item.value for item in constructor.keywords}
    # Bind without evaluating Config or resolving the named profile. Invalid
    # timeout kwargs at this boundary caused the retained zero-inference failure.
    inspect.signature(WorkspaceClient).bind(**dict.fromkeys(keywords))
    assert set(keywords) == {"config"}
    config = keywords["config"]
    assert isinstance(config, ast.Call)
    assert isinstance(config.func, ast.Name) and config.func.id == "Config"
    settings = {item.arg: item.value for item in config.keywords}
    assert isinstance(settings["retry_timeout_seconds"], ast.Constant)
    assert settings["retry_timeout_seconds"].value == 1
    assert isinstance(settings["http_timeout_seconds"], ast.Constant)
    assert settings["http_timeout_seconds"].value == 20


@pytest.mark.parametrize(("requested", "effective"), [(1, 1), (0, 300)])
def test_native_metadata_retry_window_is_not_disabled_by_zero(requested, effective):
    """Construct only a native local Requests session; never invoke SDK transport."""
    from databricks.sdk._base_client import _BaseClient

    client = _BaseClient(retry_timeout_seconds=requested, http_timeout_seconds=20)
    try:
        assert client._retry_timeout_seconds == effective
        assert client._http_timeout_seconds == 20
    finally:
        client._session.close()
