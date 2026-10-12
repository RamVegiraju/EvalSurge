"""Static request/example contracts only: no agent, provider, App, or paid calls."""

import ast
import json
import re
import tomllib
from inspect import CO_COROUTINE
from pathlib import Path
from types import CodeType

import pytest
from pydantic import ValidationError

from benchmark_agents.models import Target
from benchmark_agents.settings import Settings
from evalsurge import AssessmentOutcome, Report, RunCreate, ScorerOutcome
from examples.journeys.direct_app import request as app_request
from examples.journeys.direct_http import request as http_request
from examples.quality.load_dataset import build_request

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "examples" / "quality"


def _compile_journey(path: Path) -> CodeType:
    """Compile an example without executing notebook or agent operations.

    Args:
        path: Repository example or test-owned source file.

    Returns:
        Code compiled with notebook top-level await only for an explicitly
        marked Databricks source notebook. Ordinary scripts remain strict.

    Raises:
        SyntaxError: Source is invalid for its declared execution format.

    Side Effects:
        Reads the source file only; no widgets, imports or code are executed.
    """
    source = path.read_text()
    flags = (
        ast.PyCF_ALLOW_TOP_LEVEL_AWAIT if source.startswith("# Databricks notebook source") else 0
    )
    return compile(source, str(path), "exec", flags=flags, dont_inherit=True)


@pytest.mark.parametrize("policy", ["explicit", "registered", "automatic"])
def test_quality_policy_and_dataset_use_the_public_request(policy: str) -> None:
    """Read actual copyable inputs through the same public models, with no execution."""
    request = build_request(QUALITY / f"{policy}.json", QUALITY / "dataset.json")
    assert request.target.connection_id == "agent"
    assert len(request.cases) == 4
    assert all(case.reference["expected_facts"] for case in request.cases)
    assert request.load.max_requests == 10
    assert request.load.concurrency == 2
    assert request.evaluation.max_scored_requests == 5
    assert request.evaluation.mode == ("automatic" if policy == "automatic" else "explicit")
    assert "profile" not in request.model_dump_json()
    translated = request.translate(Target(url="http://127.0.0.1:9001/chat"), {"policy"})
    assert translated.evaluation.samples[0].expectations == request.cases[0].reference
    if policy == "automatic":
        assert translated.evaluation.scorers is None
    elif policy == "registered":
        assert translated.evaluation.registered_scorers == ["policy"]
    else:
        assert translated.evaluation.scorers == ["relevance", "correctness"]


def test_request_variants_share_v2_vocabulary_and_small_bounds() -> None:
    """Building HTTP/App requests never performs target resolution or inference."""
    http, app = http_request(), app_request()
    assert http.model_copy(update={"name": app.name}) == app
    assert http.evaluation.mode == app.evaluation.mode == "off"
    assert http.load.max_requests == app.load.max_requests == 10
    assert http.load.duration_seconds == app.load.duration_seconds == 10
    assert http.load.timeout_seconds == app.load.timeout_seconds == 60


def test_negative_samples_mark_validation_versus_readiness_edges() -> None:
    """Only configuration is checked; these do not simulate failed model calls."""
    edges = QUALITY / "edge-cases"
    with pytest.raises(ValidationError):
        RunCreate.model_validate_json((edges / "automatic-with-scorers.json").read_text())
    unknown = RunCreate.model_validate_json((edges / "unknown-judge.json").read_text())
    with pytest.raises(ValueError, match="Unknown registered scorer"):
        unknown.translate(Target(url="http://127.0.0.1:9001/chat"), {"policy"})
    missing = RunCreate.model_validate_json((edges / "missing-first-reference.json").read_text())
    assert not missing.cases[0].reference and missing.cases[1].reference
    groundedness = RunCreate.model_validate_json(
        (edges / "unavailable-groundedness.json").read_text()
    )
    assert groundedness.evaluation.scorers == ["groundedness"]


def test_registered_judge_settings_are_only_reviewed_operator_references() -> None:
    """Loading placeholders validates native-reference shape without scorer loading."""
    settings = Settings.model_validate(tomllib.loads((QUALITY / "operator.toml").read_text()))
    judge = settings.scorers["policy"]
    assert judge.version == 1
    assert set(judge.required_fields) == {"inputs", "outputs", "expectations"}
    assert settings.connections["agent"].kind == "http"
    assert not settings.model_dump().get("provider", {}).get("profile")


def test_dataset_loader_rejects_nonfinite_and_wrong_container_shapes(tmp_path: Path) -> None:
    """Pure JSON validation never turns NaN or object keys into caller cases."""
    dataset = tmp_path / "dataset.json"
    dataset.write_text('{"input": {"query": "No"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="dataset must be a list"):
        build_request(QUALITY / "explicit.json", dataset)
    dataset.write_text('[{"input": {"query": "No", "number": NaN}}]', encoding="utf-8")
    with pytest.raises(ValueError):
        build_request(QUALITY / "explicit.json", dataset)


def test_journey_sources_compile_and_notebook_has_an_explicit_consent_gate() -> None:
    """Compile source but do not run main, notebook widgets, or any agent invocation."""
    for path in (ROOT / "examples" / "journeys").glob("*.py"):
        _compile_journey(path)
    notebook = (ROOT / "examples/journeys/classic_notebook.py").read_text()
    assert notebook.startswith("# Databricks notebook source")
    assert '"allow_paid_inference", "false"' in notebook
    tree = ast.parse(notebook)
    guard = next(node for node in tree.body if isinstance(node, ast.If))
    owner = next(node for node in tree.body if isinstance(node, ast.With))
    assert guard.lineno < owner.lineno
    assert any(isinstance(node, ast.Raise) for node in guard.body)
    assert "profile=profile" in notebook
    assert "max_requests=10" in notebook


def test_top_level_await_is_allowed_only_for_explicit_notebook_sources(tmp_path: Path) -> None:
    """Check format-specific compilation, never execute the named operation."""
    script = tmp_path / "ordinary.py"
    notebook = tmp_path / "notebook.py"
    source = "await operation_not_to_be_executed()\n"
    script.write_text(source)
    notebook.write_text("# Databricks notebook source\n" + source)
    with pytest.raises(SyntaxError, match="await.*outside function"):
        _compile_journey(script)
    assert _compile_journey(notebook).co_flags & CO_COROUTINE


def test_notebook_compilation_still_rejects_invalid_python(tmp_path: Path) -> None:
    """Notebook await support does not suppress unrelated syntax errors."""
    notebook = tmp_path / "invalid_notebook.py"
    notebook.write_text("# Databricks notebook source\nawait broken(\n")
    with pytest.raises(SyntaxError):
        _compile_journey(notebook)


def test_typed_assessment_schema_keeps_quality_distinct_from_execution() -> None:
    """Schema-only example values are not claimed as real judge assessments."""
    assessment = AssessmentOutcome(request_id="schema-only", status="failed", value=False)
    judge = ScorerOutcome(scorer="correctness", status="completed", assessments=[assessment])
    assert judge.status == "completed" and judge.assessments[0].value is False
    assert judge.pass_rate is None
    schema = Report.model_json_schema()
    assert "EvaluationOutcome" in schema["$defs"]
    assert "SamplingCoverage" in schema["$defs"]


def test_new_guide_navigation_and_example_inventory_are_complete() -> None:
    """Verify linked local files without fetching external docs or reading live artifacts."""
    guides = (
        ROOT / "README.md",
        ROOT / "examples/README.md",
        ROOT / "examples/journeys/LOCAL_RUNNER_QUICKSTART.md",
        ROOT / "examples/journeys/FRAMEWORK_MATRIX.md",
        QUALITY / "README.md",
        ROOT / "docs/PYTHON_API.md",
        ROOT / "docs/OPTIONAL_SERVER.md",
        ROOT / "docs/REPORTS_AND_JUDGES.md",
        ROOT / "docs/SDK_MILESTONE.md",
        ROOT / "docs/adr/0011-unified-direct-and-remote-sdk.md",
        ROOT / "scripts/validation/README.md",
        ROOT / "docs/TARGETS.md",
        ROOT / "docs/V2_API.md",
        ROOT / "docs/FRAMEWORK_TARGET_EXAMPLES.md",
        ROOT / "docs/API_REVIEW.md",
        ROOT / "docs/CODE_GUIDE.md",
        ROOT / "ARCHITECTURE.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "SECURITY.md",
    )
    for guide in guides:
        for destination in re.findall(r"\]\(([^)]+)\)", guide.read_text()):
            if destination.startswith(("http://", "https://")):
                continue
            filename = destination.partition("#")[0]
            assert not filename or (guide.parent / filename).exists(), (guide, destination)
    assert {file.name for file in QUALITY.glob("*.json")} == {
        "dataset.json",
        "explicit.json",
        "registered.json",
        "automatic.json",
    }
    assert json.loads((QUALITY / "dataset.json").read_text())[0]["reference"]
