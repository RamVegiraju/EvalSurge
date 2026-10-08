"""Ensure release validation rejects missing report assets without executing code."""

from pathlib import Path
from zipfile import ZipFile

import pytest
from hatchling.build import build_editable

from scripts.verify_wheel import REQUIRED_FILES, verify


@pytest.mark.parametrize(
    "omit",
    [
        None,
        "evalsurge/__init__.py",
        "evalsurge/client.py",
        "evalsurge/facade.py",
        "benchmark_agents/coordinator.py",
        "benchmark_agents/evaluation_errors.py",
        "benchmark_agents/evaluation_details.py",
        "benchmark_agents/evaluation_preflight.py",
        "benchmark_agents/static/report.js",
        "benchmark_agents/docs_ui/init.js",
        "benchmark_agents/docs_ui/vendor/swagger-ui-bundle.js",
        "benchmark_agents/docs_ui/vendor/LICENSE",
    ],
)
def test_wheel_assets(tmp_path: Path, omit: str | None) -> None:
    wheel = tmp_path / "evalsurge-test.whl"
    with ZipFile(wheel, "w") as archive:
        for filename in REQUIRED_FILES - ({omit} if omit else set()):
            archive.writestr(filename, 'raise RuntimeError("must not execute")')
    if omit:
        with pytest.raises(ValueError, match=omit):
            verify(wheel)
    else:
        verify(wheel)


def test_editable_build_exposes_both_namespaces_without_dynamic_build_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Build the real editable wheel using the already locked build backend."""
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    filename = build_editable(str(tmp_path))
    with ZipFile(tmp_path / filename) as archive:
        paths = [name for name in archive.namelist() if name.endswith(".pth")]
        assert len(paths) == 1
        assert archive.read(paths[0]).decode().strip() == str(root)
