"""Verify the built wheel's public Python API, coordinator, report, and docs."""

from pathlib import Path
from zipfile import ZipFile

REQUIRED_FILES = {
    "evalsurge/__init__.py",
    "evalsurge/client.py",
    "benchmark_agents/__init__.py",
    "benchmark_agents/api.py",
    "benchmark_agents/coordinator.py",
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
    """Validate the repository's built wheel, failing on missing or ambiguous builds."""
    directory = Path(__file__).resolve().parents[1] / "dist"
    wheels = list(directory.glob("evalsurge-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(
            "Expected exactly one EvalSurge wheel in dist; use a clean build directory"
        )
    verify(wheels[0])
    print(f"Verified Python/REST API, report, and self-hosted docs assets in {wheels[0].name}")


if __name__ == "__main__":
    main()
