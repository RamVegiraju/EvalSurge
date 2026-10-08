"""Verify release archives' required assets and exclude local assistant metadata."""

import tarfile
from pathlib import Path
from zipfile import ZipFile

REQUIRED_FILES = {
    "evalsurge/__init__.py",
    "evalsurge/client.py",
    "evalsurge/local.py",
    "evalsurge/facade.py",
    "evalsurge/remote.py",
    "evalsurge/cli.py",
    "benchmark_agents/__init__.py",
    "benchmark_agents/api.py",
    "benchmark_agents/coordinator.py",
    "benchmark_agents/configuration.py",
    "benchmark_agents/settings.py",
    "benchmark_agents/diagnostics.py",
    "benchmark_agents/v2.py",
    "benchmark_agents/v2_models.py",
    "benchmark_agents/run_views.py",
    "benchmark_agents/validation.py",
    "benchmark_agents/target_resolver.py",
    "benchmark_agents/adapters.py",
    "benchmark_agents/limits.py",
    "benchmark_agents/evaluation_errors.py",
    "benchmark_agents/evaluation_details.py",
    "benchmark_agents/evaluation_preflight.py",
    "benchmark_agents/report_links.py",
    "benchmark_agents/static/index.html",
    "benchmark_agents/static/report.css",
    "benchmark_agents/static/report.js",
    "benchmark_agents/docs_ui/index.html",
    "benchmark_agents/docs_ui/docs.css",
    "benchmark_agents/docs_ui/init.js",
    "benchmark_agents/docs_ui/vendor/swagger-ui-bundle.js",
    "benchmark_agents/docs_ui/vendor/swagger-ui.css",
    "benchmark_agents/docs_ui/vendor/LICENSE",
    "benchmark_agents/docs_ui/vendor/README.md",
    "benchmark_agents/docs_ui/vendor/manifest.json",
}


def verify(wheel: Path) -> None:
    """Check a wheel's required package and UI assets without importing its code.

    Args:
        wheel: Built wheel archive to inspect.

    Raises:
        ValueError: Required assets are missing from the archive.
        OSError: The archive cannot be read.

    This reads the archive but does not install or execute its contents.
    """
    with ZipFile(wheel) as archive:
        missing = REQUIRED_FILES - set(archive.namelist())
    if missing:
        raise ValueError(f"Wheel missing required files: {', '.join(sorted(missing))}")


def main() -> None:
    """Validate built release archives, failing on missing assets or private metadata."""
    directory = Path(__file__).resolve().parents[1] / "dist"
    wheels = list(directory.glob("evalsurge-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(
            "Expected exactly one EvalSurge wheel in dist; use a clean build directory"
        )
    verify(wheels[0])
    print(f"Verified Python/REST API, report, and self-hosted docs assets in {wheels[0].name}")
    sources = list(directory.glob("evalsurge-*.tar.gz"))
    if len(sources) != 1:
        raise SystemExit("Expected exactly one EvalSurge source distribution in dist")
    verify_sdist(sources[0])
    print(f"Verified source assets and excluded local assistant metadata in {sources[0].name}")


def verify_sdist(source: Path) -> None:
    """Inspect source members without extraction, importing code, or reading bodies.

    Args:
        source: Built source archive with one package/version root directory.

    Raises:
        ValueError: Required package assets are absent or local assistant metadata
            is present. Rejected metadata contents are never read or displayed.
        OSError: The archive cannot be read.
        tarfile.TarError: The archive is malformed.
    """
    with tarfile.open(source, "r:gz") as archive:
        names = {member.name.partition("/")[2] for member in archive.getmembers()}
    if any(".isaac" in Path(name).parts for name in names):
        raise ValueError("Source distribution contains local assistant metadata")
    missing = REQUIRED_FILES - names
    if missing:
        raise ValueError(
            f"Source distribution missing required files: {', '.join(sorted(missing))}"
        )


if __name__ == "__main__":
    main()
