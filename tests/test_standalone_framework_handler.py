"""Pure import/schema/lifecycle/pre-provider checks, never model-completion evidence.

No provider transports, framework executions or successful inference responses are
stubbed. Declarative text below exercises DTO/body validation only. The endpoint
checks intentionally reject inputs before a handler or SDK profile is resolved.
"""

import ast
import asyncio
import inspect
import json
import subprocess
import sys
import threading
from pathlib import Path

import httpx
import pytest
from starlette.datastructures import Headers

from examples import real_framework_agent, real_framework_handler
from examples.crewai_agent import (
    REQUEST_BYTES,
    correlation_context,
    create_app,
    decode_inputs,
    main,
    owned_thread,
    validate_model_request,
)
from examples.real_framework_handler import CompletedAnswer, ModelSelection, validate_inputs

ROOT = Path(__file__).resolve().parents[1]


def selection():
    """Declarative exact selections; this nonexistent profile must not resolve."""
    return ModelSelection(
        profile="constructor-only-no-profile",
        model="explicit-model",
        api="mlflow-responses",
        expected_host="https://selected-workspace.cloud.databricks.com",
    )


def test_canonical_handler_imports_without_site_packages():
    process = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            "import runpy; runpy.run_path('examples/real_framework_handler.py')",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr


def test_standalone_cli_without_site_packages_dry_runs():
    process = subprocess.run(
        [
            sys.executable,
            "-S",
            "examples/crewai_agent.py",
            "--profile",
            "nonexistent-explicit-profile",
            "--workspace-host",
            "https://selected-workspace.cloud.databricks.com",
            "--model",
            "explicit-model",
            "--api",
            "mlflow-responses",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert "no framework import or inference" in process.stdout


@pytest.mark.parametrize("filename", ["real_framework_handler.py", "crewai_agent.py"])
def test_customer_examples_do_not_import_evalsurge_or_runner(filename):
    tree = ast.parse((ROOT / "examples" / filename).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = [alias.name.split(".", 1)[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            roots = [(node.module or "").split(".", 1)[0]]
        else:
            continue
        assert not {"evalsurge", "benchmark_agents"}.intersection(roots)


@pytest.mark.parametrize(
    "name",
    [
        "Framework",
        "ModelAPI",
        "POLICY",
        "INSTRUCTIONS",
        "ModelSelection",
        "completed_response",
        "response_completion_guard",
        "validate_completion_metadata",
        "validate_inputs",
        "validate_model_request",
        "owned_thread",
        "_GraphState",
    ],
)
def test_original_module_keeps_exact_compatibility_exports(name):
    assert getattr(real_framework_agent, name) is getattr(real_framework_handler, name)


def test_bridge_retains_original_handler_signature_without_inference():
    assert inspect.signature(real_framework_agent.build_handler) == inspect.signature(
        real_framework_handler.build_handler
    )
    tree = ast.parse(inspect.getsource(real_framework_agent.build_handler))
    constructors = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "AgentAnswer" in constructors
    assert "AnswerUsage" in constructors
    assert "build_framework_handler" in constructors


@pytest.mark.parametrize(
    ("outputs", "tokens"),
    [
        ("", None),
        ("  ", None),
        (3, None),
        ("\ud800", None),
        ("界" * 666_667, None),
        ("schema value", -1),
        ("schema value", True),
        ("schema value", 1.0),
    ],
)
def test_pure_dto_rejects_invalid_text_or_usage_before_serving(outputs, tokens):
    with pytest.raises(ValueError):
        CompletedAnswer(outputs=outputs, output_tokens=tokens)


@pytest.mark.parametrize("tokens", [None, 0, 512])
def test_pure_dto_preserves_text_and_provider_usage_presence(tokens):
    text = "  schema-only text  "
    answer = CompletedAnswer(text, tokens)
    assert answer.outputs == text
    assert answer.output_tokens == tokens


def test_input_surrogate_is_rejected_before_provider():
    with pytest.raises(ValueError, match="UTF-8"):
        validate_inputs({"query": "\ud800"})


@pytest.mark.parametrize(
    "body",
    [
        b"not JSON",
        b"\xff",
        b"[]",
        b'{"query":"x","query":"y"}',
        b'{"query":"x","extra":NaN}',
        b'{"query":"x","extra":1e9999}',
        b'{"query":"x","extra":null}',
        b'{"query":"\\ud800"}',
        b'{"query":" "}',
        json.dumps({"query": "x" * 513}).encode(),
        b" " * (REQUEST_BYTES + 1),
    ],
)
def test_body_errors_are_pre_provider_failures(body):
    with pytest.raises(ValueError):
        decode_inputs(body)


def test_body_decoder_preserves_original_valid_query():
    assert decode_inputs(b'{"query":" a question "}') == {"query": " a question "}


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", "https://selected-workspace.cloud.databricks.com/ai-gateway/mlflow/v1/responses"),
        ("POST", "https://other-workspace.cloud.databricks.com/ai-gateway/mlflow/v1/responses"),
        ("POST", "https://selected-workspace.cloud.databricks.com/ai-gateway/openai/v1/responses"),
        (
            "POST",
            "https://selected-workspace.cloud.databricks.com/ai-gateway/mlflow/v1/responses?a=1",
        ),
        ("POST", "https://selected-workspace.cloud.databricks.com/ai-gateway/mlflow/v1/responses/"),
    ],
)
def test_model_destination_rejected_before_authentication(method, url):
    with pytest.raises(ValueError, match="exact selected Responses destination"):
        validate_model_request(httpx.Request(method, url), selection())


def test_exact_model_destination_check_performs_no_authentication():
    selected = selection()
    validate_model_request(httpx.Request("POST", f"{selected.base_url}/responses"), selected)


def test_destination_check_precedes_sdk_header_resolution():
    tree = ast.parse(inspect.getsource(create_app))
    auth = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "authenticate_request"
    )
    first = auth.body[1] if ast.get_docstring(auth) is not None else auth.body[0]
    assert isinstance(first, ast.Expr) and isinstance(first.value, ast.Call)
    assert isinstance(first.value.func, ast.Name)
    assert first.value.func.id == "validate_model_request"


@pytest.mark.parametrize(
    "headers",
    [
        [("x-benchmark-request-id", "not-a-uuid")],
        [("x-benchmark-run-id", "x"), ("x-benchmark-request-id", "y")],
        [("x-benchmark-run-id", "x"), ("x-benchmark-run-id", "x")],
        [
            ("x-benchmark-run-id", "00000000-0000-0000-0000-000000000001"),
            ("x-benchmark-request-id", "00000000-0000-0000-0000-000000000002"),
            ("x-benchmark-case-id", "000"),
        ],
    ],
)
def test_invalid_correlation_is_rejected_before_provider(headers):
    with pytest.raises(ValueError):
        correlation_context(Headers(raw=[(key.encode(), value.encode()) for key, value in headers]))


def test_request_isolation_is_not_memory_or_a_trace():
    first = correlation_context(Headers())
    second = correlation_context(Headers())
    assert first.run_id is None and first.case_id is None
    assert first.request_id == first.session_id
    assert first.request_id != second.request_id
    assert not hasattr(first, "trace_id")


@pytest.mark.parametrize(
    ("body", "headers", "status"),
    [
        (b"[]", {"Content-Type": "application/json"}, 400),
        (b'{"query":"x","query":"y"}', {"Content-Type": "application/json"}, 400),
        (b'{"query":"x"}', {"Content-Type": "text/plain"}, 415),
        (b" " * (REQUEST_BYTES + 1), {"Content-Type": "application/json"}, 413),
    ],
)
async def test_endpoint_rejects_before_startup_profile_or_provider(body, headers, status):
    """Actual ASGI request validation only, intentionally without lifespan startup."""
    app = create_app(selection())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        response = await client.post("/invoke", content=body, headers=headers)
    assert response.status_code == status
    assert response.json()["error"]["code"] == "invalid_input"
    assert response.headers["cache-control"] == "no-store"
    assert app.state.inference_evidence == {"outbound_attempts": 0, "completed_responses": 0}


async def test_native_thread_work_is_owned_through_repeated_cancellation():
    """Local thread-lifecycle test only; this operation has no credentials/network."""
    started = threading.Event()
    release = threading.Event()
    completed = threading.Event()

    def operation():
        started.set()
        release.wait(timeout=5)
        completed.set()

    task = asyncio.create_task(owned_thread(operation))
    try:
        async with asyncio.timeout(5):
            while not started.is_set():
                await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert completed.is_set()


async def test_cancellation_takes_precedence_over_later_native_worker_failure():
    """Inert local worker failure, not provider/authentication or controlled inference."""
    started = threading.Event()
    release = threading.Event()
    completed = threading.Event()

    def operation():
        started.set()
        release.wait(timeout=5)
        completed.set()
        raise RuntimeError("inert native worker failure")

    task = asyncio.create_task(owned_thread(operation))
    try:
        async with asyncio.timeout(5):
            while not started.is_set():
                await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert completed.is_set()


async def test_native_failure_without_cancellation_remains_a_failure():
    """Observe the inert worker error without a success-shaped substitute."""

    def operation():
        raise RuntimeError("inert native worker failure")

    with pytest.raises(RuntimeError, match="inert native worker failure"):
        await owned_thread(operation)


@pytest.mark.parametrize(
    "updates",
    [
        {"expected_host": "https://"},
        {"expected_host": "https://workspace:443"},
        {"expected_host": "https://workspace:8443"},
        {"expected_host": "https://workspace:"},
        {"expected_host": "https://workspace\\other"},
        {"expected_host": "https://work\nspace"},
        {"expected_host": "https://workspace "},
        {"expected_host": "https://workspace\x7f"},
        {"expected_host": 3},
        {"profile": None},
        {"model": False},
        {"max_output_tokens": True},
        {"max_output_tokens": 1.5},
        {"timeout_seconds": True},
        {"timeout_seconds": "10"},
    ],
)
def test_strict_origin_and_model_limits_fail_before_any_sdk(updates):
    values = {
        "profile": "no-profile-resolution",
        "model": "selected-model",
        "api": "mlflow-responses",
        "expected_host": "https://selected-workspace.cloud.databricks.com",
    }
    with pytest.raises(ValueError):
        ModelSelection(**(values | updates))


def test_existing_http_helper_owns_sdk_work_outside_event_loop():
    source = inspect.getsource(real_framework_agent.create_real_app)
    assert "DatabricksAuth" not in source
    assert "await owned_thread(configure)" in source
    assert "await owned_thread(workspace.config.authenticate)" in source
    assert "validate_model_request(request, selection)" in source
    assert "DefaultAsyncHttpxClient(" in source


def test_live_cli_requires_paid_consent_before_importing_framework():
    with pytest.raises(SystemExit):
        main(
            [
                "--profile",
                "nonexistent-explicit-profile",
                "--workspace-host",
                "https://selected-workspace.cloud.databricks.com",
                "--model",
                "explicit-model",
                "--api",
                "mlflow-responses",
                "--live",
            ]
        )
