"""Pure notebook AST/schema checks: no agent/model/App/HTTP calls or notebook jobs."""

import ast
import hashlib
import ipaddress
import re
from contextlib import suppress
from pathlib import Path
from types import CodeType
from typing import Any
from urllib.parse import urlsplit

import pytest

from evalsurge import Case, Load, RunCreate, TargetReference

ROOT = Path(__file__).resolve().parents[1]
JOURNEYS = ROOT / "examples/journeys"
NOTEBOOKS = (
    "serverless_runner_databricks_app_target.py",
    "serverless_runner_http_target.py",
)


def _tree(filename: str) -> ast.Module:
    """Read declared source without evaluating widgets/imports or executing workload."""
    source = (JOURNEYS / filename).read_text()
    assert source.startswith("# Databricks notebook source\n")
    return ast.parse(source)


def _function(filename: str, name: str) -> CodeType:
    """Compile one reviewed pure validator, excluding every notebook execution cell."""
    node = next(
        element
        for element in _tree(filename).body
        if isinstance(element, ast.FunctionDef) and element.name == name
    )
    return compile(ast.Module(body=[node], type_ignores=[]), filename, "exec")


@pytest.mark.parametrize("filename", NOTEBOOKS)
def test_notebook_install_gate_precedes_auth_or_load_and_requires_no_checkout(
    filename: str,
) -> None:
    """Check artifact/version requirements and ordering without install/inference calls."""
    tree = _tree(filename)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    install = next(
        call
        for call in calls
        if isinstance(call.func, ast.Name) and call.func.id == "verify_reviewed_install"
    )
    execution = next(
        call
        for call in calls
        if isinstance(call.func, ast.Name)
        and call.func.id in {"launch_runner_async", "run_benchmark"}
    )
    assert install.lineno < execution.lineno
    imported = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(module.startswith(("examples", "scripts")) for module in imported)
    assert not any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "remote" for call in calls
    )
    widgets = {
        ast.literal_eval(call.args[0])
        for call in calls
        if isinstance(call.func, ast.Attribute)
        and call.func.attr in {"text", "dropdown"}
        and call.args
    }
    assert {"reviewed_wheel", "reviewed_sha256", "reviewed_version"} <= widgets
    consent = next(
        call
        for call in calls
        if isinstance(call.func, ast.Attribute)
        and call.func.attr == "dropdown"
        and ast.literal_eval(call.args[0]) == "allow_paid_inference"
    )
    assert ast.literal_eval(consent.args[1]) == "false"


@pytest.mark.parametrize("filename", NOTEBOOKS)
def test_invalid_install_selection_stops_before_reading_artifact(filename: str) -> None:
    """Run only the pure validation function on absent/invalid operator selections."""
    namespace: dict[str, Any] = {"Path": Path, "re": re, "hashlib": hashlib}
    exec(_function(filename, "verify_reviewed_install"), namespace)
    with pytest.raises(ValueError, match="Select the reviewed wheel"):
        namespace["verify_reviewed_install"]("", "", "")
    with pytest.raises(ValueError, match="Select the reviewed wheel"):
        namespace["verify_reviewed_install"](
            "/private/tmp/not-an-approved-wheel.whl", "a" * 64, "x"
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://agent.example.test/chat",
        "https://localhost/chat",
        "https://localhost./chat",
        "https://LOCALHOST./chat",
        "https://agent.localhost/chat",
        "https://AGENT.LocalHost./chat",
        "https://127.0.0.1/chat",
        "https://127.0.0.42/chat",
        "https://[::1]/chat",
        "https://0.0.0.0/chat",
        "https://[::]/chat",
        "",
    ],
)
def test_http_notebook_rejects_loopback_and_non_https_without_network(url: str) -> None:
    """Laptop-local endpoints cannot be notebook targets; no DNS/HTTP probe is made."""
    namespace: dict[str, Any] = {
        "urlsplit": urlsplit,
        "ipaddress": ipaddress,
        "suppress": suppress,
    }
    exec(_function(NOTEBOOKS[1], "validate_notebook_target"), namespace)
    with pytest.raises(ValueError, match="reachable from serverless"):
        namespace["validate_notebook_target"](url)


@pytest.mark.parametrize("filename", NOTEBOOKS)
def test_notebook_install_does_not_claim_wheel_picker_installs_direct_extras(filename: str) -> None:
    """Verify precise installation prerequisites, not actual package installation."""
    source = (JOURNEYS / filename).read_text()
    assert "wheel picker alone does not establish optional-extra installation" in source
    assert "-r /Workspace/.../evalsurge-requirements.txt" in source
    assert "py3-none-any.whl[server]" in source
    assert "not live install evidence" in source


def test_http_notebook_external_endpoint_and_request_are_pure_schema_checks() -> None:
    """Validate actual published request construction; this is not live inference."""
    namespace: dict[str, Any] = {
        "urlsplit": urlsplit,
        "ipaddress": ipaddress,
        "suppress": suppress,
        "RunCreate": RunCreate,
        "TargetReference": TargetReference,
        "Case": Case,
        "Load": Load,
    }
    exec(_function(NOTEBOOKS[1], "validate_notebook_target"), namespace)
    namespace["validate_notebook_target"]("https://agent.example.test/chat")
    assignment = next(
        node
        for node in _tree(NOTEBOOKS[1]).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "request" for target in node.targets)
    )
    exec(compile(ast.Module(body=[assignment], type_ignores=[]), NOTEBOOKS[1], "exec"), namespace)
    request = namespace["request"]
    assert request.target.connection_id == "agent"
    assert request.load.concurrency == request.load.max_requests == 1
    assert request.evaluation.mode == "off"
    assert len(request.cases) == 1
    assert "token_env" not in request.model_dump_json()
    assert "profile" not in request.model_dump_json()


def test_http_notebook_context_owns_lifecycle_and_does_not_reinvoke_during_retrieval() -> None:
    """Inspect lifecycle structure only, without entering any client or process."""
    function = next(
        node
        for node in _tree(NOTEBOOKS[1]).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_benchmark"
    )
    owner = next(node for node in function.body if isinstance(node, ast.AsyncWith))
    methods = [
        node.func.attr
        for node in ast.walk(owner)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert methods.count("start") == 1
    assert {"wait", "status", "result", "report"} <= set(methods)
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "format_summary"
        for node in ast.walk(owner)
    )
    assert isinstance(function.body[-1], ast.Return)
