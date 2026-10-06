"""Offline regressions for CI's public dependency-source prerequisite."""

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_ci_prerequisites import check_lockfile

PUBLIC_REGISTRY = "https://pypi.org/simple"
PUBLIC_ARTIFACT = "https://files.pythonhosted.org/packages/fixture/demo-1.0.whl"
MIRROR_REGISTRY = "https://pypi-proxy.cloud.databricks.com/simple"
MIRROR_ARTIFACT = "https://pypi-proxy.cloud.databricks.com/packages/fixture/demo-1.0.whl"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_ci_prerequisites.py"


def write_lockfile(
    directory: Path, registry: str = PUBLIC_REGISTRY, artifact: str = PUBLIC_ARTIFACT
) -> Path:
    """Write a synthetic uv lock with a public package and editable local project."""
    lockfile = directory / "uv.lock"
    lockfile.write_text(
        f"""
version = 1
revision = 3
requires-python = ">=3.11"

[[package]]
name = "demo"
version = "1.0"
source = {{ registry = "{registry}" }}
wheels = [{{ url = "{artifact}", hash = "sha256:fixture" }}]

[[package]]
name = "evalsurge"
version = "0.2.0"
source = {{ editable = "." }}
""",
        encoding="utf-8",
    )
    return lockfile


@pytest.mark.parametrize("registry", [PUBLIC_REGISTRY, PUBLIC_REGISTRY + "/"])
def test_public_registry_and_artifacts_pass(tmp_path: Path, registry: str) -> None:
    assert check_lockfile(write_lockfile(tmp_path, registry)) == 1


@pytest.mark.parametrize(
    ("registry", "artifact", "error"),
    [
        (MIRROR_REGISTRY, MIRROR_ARTIFACT, "registry"),
        (PUBLIC_REGISTRY, MIRROR_ARTIFACT, "artifact"),
        (PUBLIC_REGISTRY, PUBLIC_ARTIFACT.replace("https:", "http:"), "artifact"),
        (
            PUBLIC_REGISTRY,
            PUBLIC_ARTIFACT.replace("files.pythonhosted.org", "files.pythonhosted.org.example"),
            "artifact",
        ),
        (
            PUBLIC_REGISTRY,
            PUBLIC_ARTIFACT.replace("files.pythonhosted.org", "secret@files.pythonhosted.org"),
            "artifact",
        ),
        (PUBLIC_REGISTRY, PUBLIC_ARTIFACT + "?token=secret", "artifact"),
    ],
)
def test_nonpublic_sources_fail_without_leaking_urls(
    tmp_path: Path, registry: str, artifact: str, error: str
) -> None:
    with pytest.raises(ValueError, match=error) as failure:
        check_lockfile(write_lockfile(tmp_path, registry, artifact))
    assert "secret" not in str(failure.value)
    assert artifact not in str(failure.value)


def test_source_distribution_must_also_be_public(tmp_path: Path) -> None:
    lockfile = write_lockfile(tmp_path)
    lockfile.write_text(
        lockfile.read_text(encoding="utf-8").replace(
            "wheels =",
            f'sdist = {{ url = "{MIRROR_ARTIFACT}", hash = "sha256:fixture" }}\nwheels =',
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="artifact"):
        check_lockfile(lockfile)


def test_empty_lock_cannot_bypass_prerequisite(tmp_path: Path) -> None:
    lockfile = tmp_path / "uv.lock"
    lockfile.write_text("version = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="registry"):
        check_lockfile(lockfile)


@pytest.mark.parametrize(
    "contents",
    [
        'package = "invalid"',
        '[[package]]\nname = "demo"',
        '[[package]]\nsource = { registry = ["invalid"] }',
        f'[[package]]\nsource = {{ registry = "{PUBLIC_REGISTRY}" }}\nwheels = "invalid"',
    ],
)
def test_invalid_metadata_fails_with_actionable_error(tmp_path: Path, contents: str) -> None:
    lockfile = tmp_path / "uv.lock"
    lockfile.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match="registry|artifact"):
        check_lockfile(lockfile)


@pytest.mark.parametrize("valid", [True, False])
def test_cli_runs_without_project_dependencies(tmp_path: Path, valid: bool) -> None:
    lockfile = write_lockfile(tmp_path, PUBLIC_REGISTRY if valid else MIRROR_REGISTRY)
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--lockfile", str(lockfile)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == (0 if valid else 1)
    assert "Traceback" not in result.stderr
    assert ("Verified" if valid else "CI prerequisite failed") in (
        result.stdout if valid else result.stderr
    )


@pytest.mark.parametrize("contents", [None, "not valid TOML"])
def test_cli_surfaces_unreadable_or_invalid_lock(tmp_path: Path, contents: str | None) -> None:
    lockfile = tmp_path / "uv.lock"
    if contents is not None:
        lockfile.write_text(contents, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--lockfile", str(lockfile)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1
    assert "CI prerequisite failed" in result.stderr
    assert "Traceback" not in result.stderr
