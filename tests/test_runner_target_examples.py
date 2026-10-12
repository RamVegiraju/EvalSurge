"""Pure runner/target sample contracts: no agent execution or model completions."""

import ast
import re
import tomllib
from pathlib import Path

from examples.journeys.local_runner_databricks_app_target import request as app_request
from examples.journeys.local_runner_http_target import request as http_request

ROOT = Path(__file__).resolve().parents[1]


def test_local_samples_share_workload_and_explicit_small_bounds() -> None:
    """Construct canonical models only; no auth resolution, target or paid calls."""
    http, app = http_request(), app_request()
    assert http.cases == app.cases
    assert http.load == app.load
    assert http.target == app.target
    assert http.evaluation == app.evaluation
    assert http.evaluation.mode == "off"
    assert http.load.concurrency == http.load.max_requests == 5
    assert http.load.duration_seconds == 10
    assert http.load.timeout_seconds == 40
    assert "profile" not in http.model_dump_json()


def test_local_sample_descriptions_distinguish_runner_from_target() -> None:
    """Read/compile source; no framework, server lifecycle or provider fixture."""
    for filename, target_label in (
        ("local_runner_http_target.py", "HTTP agent"),
        ("local_runner_databricks_app_target.py", "Databricks App"),
    ):
        path = ROOT / "examples" / "journeys" / filename
        source = path.read_text()
        compile(source, str(path), "exec")
        description = ast.get_docstring(ast.parse(source))
        assert description is not None
        assert "Runner: local Python/laptop" in description
        assert target_label in description
        assert "--allow-paid-inference" in source
        assert "print(format_summary(report))" in source
        assert "print(report.model_dump_json" not in source


def test_local_quickstart_uses_current_wheel_and_direct_execution_extra() -> None:
    """Read project/doc metadata only; no installation, auth or target call occurs."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    guide = (ROOT / "examples/journeys/LOCAL_RUNNER_QUICKSTART.md").read_text()
    assert f"evalsurge-{project['version']}-py3-none-any.whl[local]" in guide
    assert project["optional-dependencies"]["local"] == ["evalsurge[server]"]
    assert "python3 -m venv .venv-runner" in guide
    assert "source .venv-runner/bin/activate" in guide
    assert "python -m pip install" in guide
    assert "`python benchmark.py`" in guide
    assert "Examples are not installed by the wheel" in guide
    assert "public publication" in guide.lower()


def test_local_quickstart_python_has_two_inert_bindings_and_shared_small_workload() -> None:
    """Inspect copyable ASTs without executing them or synthesizing completions."""
    guide = (ROOT / "examples/journeys/LOCAL_RUNNER_QUICKSTART.md").read_text()
    snippets = re.findall(r"```python\n(.*?)```", guide, flags=re.DOTALL)
    assert len(snippets) == 3
    trees = [ast.parse(snippet) for snippet in snippets]
    for snippet in snippets:
        compile(snippet, "local-runner-quickstart", "exec")

    http, app, benchmark = trees
    http_binding = next(node for node in http.body if isinstance(node, ast.Assign)).value
    app_binding = next(node for node in app.body if isinstance(node, ast.Assign)).value
    assert isinstance(http_binding, ast.Call) and isinstance(app_binding, ast.Call)
    assert ast.unparse(http_binding.func) == "Agent.http"
    assert ast.unparse(app_binding.func) == "Agent.databricks_app"
    assert {item.arg: ast.literal_eval(item.value) for item in http_binding.keywords} == {
        "protocol": "http-json"
    }
    assert {item.arg: ast.literal_eval(item.value) for item in app_binding.keywords} == {
        "profile": "YOUR_EXPLICIT_OAUTH_PROFILE"
    }
    declared_load = next(
        node
        for node in ast.walk(benchmark)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Load"
    )
    assert {item.arg: ast.literal_eval(item.value) for item in declared_load.keywords} == {
        "concurrency": 5,
        "duration_seconds": 10,
        "max_requests": 5,
        "timeout_seconds": 40,
    }
    guard = next(node for node in benchmark.body if isinstance(node, ast.If))
    owner = next(node for node in benchmark.body if isinstance(node, ast.With))
    assert guard.lineno < owner.lineno
    assert "ALLOW_REAL_INFERENCE = False" in snippets[2]
    assert "print(format_summary(report))" in snippets[2]
    assert "profile" not in snippets[2]
    assert "remote(" not in guide and "uvicorn benchmark_agents.api" not in guide


def test_local_quickstart_keeps_frameworks_in_the_agent_environment() -> None:
    """Verify documented startup boundaries; never install or start these agents."""
    guide = (ROOT / "examples/journeys/LOCAL_RUNNER_QUICKSTART.md").read_text()
    assert "python3 -m venv .venv-agent" in guide
    assert ".venv-agent/bin/python -m pip install" in guide
    assert "real_framework_agent.py" in guide and "real_framework_handler.py" in guide
    assert "--framework langgraph" in guide and "--framework openai-agents" in guide
    assert "--live --accept-paid-traffic" in guide
    assert "--allow-paid-inference" in guide
    assert "CrewAI" in guide and "ChromaDB advisory gate is unresolved" in guide
    assert "do not execute the blocked" in guide
