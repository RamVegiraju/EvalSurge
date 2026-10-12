"""Pure source/API metadata checks; no inference, provider or lifecycle calls."""

import tomllib
from pathlib import Path

from evalsurge import __version__
from evalsurge._version import __version__ as source_version


def test_public_version_matches_source_distribution_without_installed_metadata() -> None:
    """Read the checked-in build metadata, not an editable installation's dist-info."""
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert __version__ == source_version == project["version"]


def test_api_openapi_version_uses_source_constant_without_opening_storage(tmp_path: Path) -> None:
    """Create the real schema only; do not enter app lifespan or resolve any target."""
    from benchmark_agents.api import create_app

    artifacts = tmp_path / "unopened-api-storage"
    app = create_app(artifact_dir=artifacts)
    assert app.version == __version__
    assert app.openapi()["info"]["version"] == __version__
    assert not artifacts.exists()
