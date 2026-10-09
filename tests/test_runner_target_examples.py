"""Pure runner/target sample contracts: no agent execution or model completions."""

import ast
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
