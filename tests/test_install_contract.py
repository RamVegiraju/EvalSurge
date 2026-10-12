"""Installed wheel/discovery and inert timing only; zero agent/provider/cloud calls."""

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from hatchling.build import build_wheel

from scripts.verify_install import (
    Surface,
    _dependency_install_command,
    _install_step,
    _pip_command,
    verify,
)
from scripts.verify_wheel import verify as verify_archive


def test_demo_metadata_and_lock_match_wheel_first_documentation() -> None:
    """Validate the wheel-first filename/lock contract without provider execution."""
    root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    project = [package for package in lock["package"] if package["name"] == metadata["name"]]
    assert len(project) == 1
    assert project[0]["version"] == metadata["version"]
    from evalsurge import __version__

    assert __version__ == metadata["version"]
    assert project[0]["source"] == {"editable": "."}
    filename = f"evalsurge-{metadata['version']}-py3-none-any.whl"
    for documentation in ("README.md", "docs/INSTALLATION.md"):
        assert filename in (root / documentation).read_text(encoding="utf-8")


def test_local_extra_alias_keeps_base_and_legacy_installation_contracts() -> None:
    """Check additive source metadata only; do not build, install or import providers."""
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    extras = project["optional-dependencies"]
    assert extras["local"] == ["evalsurge[server]"]
    assert set(extras) == {"local", "server", "agents"}
    assert "evalsurge[server]" in extras["agents"]
    assert {dependency.split(">", 1)[0] for dependency in project["dependencies"]} == {
        "httpx",
        "pydantic",
    }


def test_direct_missing_dependency_guidance_names_local_and_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise dependency presence failure, not a controlled agent/provider response."""
    from evalsurge import MissingServerDependenciesError, facade

    monkeypatch.setattr(facade, "find_spec", lambda name: None)
    monkeypatch.setattr(facade, "import_module", lambda name: pytest.fail("Execution imported"))
    with pytest.raises(MissingServerDependenciesError) as error:
        facade._local_module()
    assert "evalsurge[local]" in str(error.value)
    assert "evalsurge[server]" in str(error.value)
    assert "Neither extra starts an API server" in str(error.value)


@pytest.mark.parametrize("operation", ["install", "check"])
def test_native_pip_command_uses_exact_environment_without_execution(operation: str) -> None:
    """Inspect inert argv; no package or index operation is invoked."""
    python = Path("/installation-only/venv/bin/python")
    assert _pip_command(python, operation) == [
        str(python),
        "-m",
        "pip",
        "--disable-pip-version-check",
        operation,
    ]


@pytest.mark.parametrize(
    ("installer", "requirements_option", "index_option"),
    [("pip", "--requirement", "--index-url"), ("uv", "--requirements", "--default-index")],
)
def test_dependency_manifest_uses_installer_specific_native_options(
    tmp_path: Path, installer: str, requirements_option: str, index_option: str
) -> None:
    """Inspect exact argv; no installation, source resolution or provider execution."""
    command = _dependency_install_command(
        tmp_path / "venv" / "bin" / "python",
        installer=installer,
        dependency_index="https://approved.invalid/simple",
        manifest=tmp_path / "requirements.txt",
    )
    assert command[-6:] == [
        "--require-hashes",
        "--no-deps",
        index_option,
        "https://approved.invalid/simple",
        requirements_option,
        str(tmp_path / "requirements.txt"),
    ]


def test_native_pip_parses_locked_manifest_without_script_metadata(tmp_path: Path) -> None:
    """Execute fresh native pip with empty requirements, dry-run and no index.

    Stdlib venv/ensurepip seeds bundled pip without registry access. No external
    dependency, agent/provider package, controlled transport or model is installed
    or called. The manifest check only parses native pip options under dry-run.
    """
    environment = {"PATH": os.defpath, "PIP_CONFIG_FILE": os.devnull}
    pip_environment = tmp_path / "pip-cli-env"
    subprocess.run(
        [sys.executable, "-I", "-m", "venv", str(pip_environment)],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    python = (
        pip_environment / "Scripts" / "python.exe"
        if os.name == "nt"
        else pip_environment / "bin" / "python"
    )
    manifest = tmp_path / "empty-hashed-requirements.txt"
    manifest.write_text("# Intentionally zero requirements: native CLI parsing only.\n")
    command = _dependency_install_command(
        python,
        installer="pip",
        dependency_index="https://approved.invalid/simple",
        manifest=manifest,
    )
    command.insert(1, "-I")
    command.extend(["--dry-run", "--no-index", "--no-cache-dir", "--no-input"])
    result = subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Would install" not in result.stdout
    assert set(tmp_path.iterdir()) == {manifest, pip_environment}


@pytest.mark.parametrize(
    ("dependency_index", "offline"),
    [(None, False), (None, True), ("https://approved.invalid", True)],
)
def test_native_pip_requires_explicit_online_source_before_install(
    tmp_path: Path, dependency_index: str | None, offline: bool
) -> None:
    """Reject unsupported installer prerequisites before venv, auth or index work."""
    with pytest.raises(ValueError, match="explicit approved online dependency source"):
        verify(
            tmp_path / "unused.whl",
            surface="local",
            installer="pip",
            offline=offline,
            dependency_index=dependency_index,
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("surface", ["base", "local", "server"])
def test_installed_wheel_is_portable_without_checkout_or_development_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: Surface
) -> None:
    """Build/install the wheel; execution extras add bounded NON-agent timing."""
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    wheel = tmp_path / build_wheel(str(tmp_path))
    verify_archive(wheel)
    # An explicitly approved development mirror may satisfy the same retained
    # lock hashes; no private registry URL enters source or lock metadata.
    index = os.environ.get("EVALSURGE_INSTALL_CHECK_INDEX")
    verify(
        wheel,
        surface=surface,
        offline=index is None,
        dependency_index=index,
        evidence_dir=tmp_path / "installer-evidence",
        timing_only=surface != "base",
    )


def test_install_diagnostics_do_not_export_private_source_values(tmp_path: Path) -> None:
    """A native diagnostic-only child cannot leak captured installer output."""
    marker = "private-package-source-diagnostic"
    log = tmp_path / "diagnostic.private.log"
    with pytest.raises(RuntimeError) as error:
        _install_step(
            [sys.executable, "-c", f"print({marker!r}); raise SystemExit(2)"],
            work=tmp_path,
            environment={},
            log=log,
        )
    assert marker not in str(error.value)
    assert marker in log.read_text(encoding="utf-8")
    assert log.stat().st_mode & 0o077 == 0


def test_explicit_install_evidence_survives_failed_environment_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retain private native-child diagnostics after the temporary venv is removed."""
    marker = "private-installer-failure-detail"
    failed_work: list[Path] = []

    def fail_install(
        command: list[str], *, work: Path, environment: dict[str, str], log: Path
    ) -> None:
        """Fail before dependency/provider setup using the actual log-writing helper."""
        failed_work.append(work)
        _install_step(
            [sys.executable, "-c", f"print({marker!r}); raise SystemExit(2)"],
            work=work,
            environment={},
            log=log,
        )

    monkeypatch.setattr("scripts.verify_install._install_step", fail_install)
    evidence = tmp_path / "installer-evidence"
    with pytest.raises(RuntimeError) as error:
        verify(tmp_path / "unused.whl", surface="server", offline=True, evidence_dir=evidence)

    assert marker not in str(error.value)
    assert len(failed_work) == 1
    assert not failed_work[0].exists()
    log = evidence / "server" / "sync.private.log"
    assert marker in log.read_text(encoding="utf-8")
    assert log.stat().st_mode & 0o077 == 0
    assert evidence.stat().st_mode & 0o077 == 0
    assert log.parent.stat().st_mode & 0o077 == 0
