"""Ensure release validation rejects missing report assets without executing code."""

import io
import tarfile
from pathlib import Path
from zipfile import ZipFile

import pytest
from hatchling.build import build_editable

from scripts.verify_wheel import REQUIRED_FILES, verify, verify_sdist


@pytest.mark.parametrize(
    "omit",
    [
        None,
        "evalsurge/__init__.py",
        "evalsurge/_version.py",
        "evalsurge/client.py",
        "evalsurge/tracing.py",
        "evalsurge/local.py",
        "evalsurge/facade.py",
        "evalsurge/calibration.py",
        "evalsurge/_calibration_locust.py",
        "evalsurge/serverless.py",
        "evalsurge/_retrieval.py",
        "evalsurge/summary.py",
        "benchmark_agents/coordinator.py",
        "benchmark_agents/run_views.py",
        "benchmark_agents/validation.py",
        "benchmark_agents/providers.py",
        "benchmark_agents/locust_runner.py",
        "benchmark_agents/locustfile.py",
        "benchmark_agents/runner.py",
        "benchmark_agents/trace_ids.py",
        "benchmark_agents/storage.py",
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


@pytest.mark.parametrize(
    "import_statement", ["from .not_packaged import receipt", "import evalsurge.not_packaged"]
)
def test_wheel_rejects_missing_internal_branch_without_executing_code(
    tmp_path: Path, import_statement: str
) -> None:
    """A late retrieval/summary branch cannot escape archive checks via lazy import."""
    wheel = tmp_path / "evalsurge-test.whl"
    with ZipFile(wheel, "w") as archive:
        for filename in REQUIRED_FILES:
            source = (
                import_statement + '\nraise RuntimeError("never execute this private body")'
                if filename == "evalsurge/serverless.py"
                else 'raise RuntimeError("never execute")'
            )
            archive.writestr(filename, source)
    with pytest.raises(ValueError, match="evalsurge.not_packaged") as error:
        verify(wheel)
    assert "private body" not in str(error.value)


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


@pytest.mark.parametrize("problem", [None, "private_metadata", "missing_module"])
def test_source_assets_exclude_local_metadata_without_reading_it(
    tmp_path: Path, problem: str | None
) -> None:
    """Inspect archive names only; synthetic archive bytes are never executed."""
    source = tmp_path / "evalsurge-test.tar.gz"
    omitted = {"evalsurge/local.py"} if problem == "missing_module" else set()
    names = REQUIRED_FILES - omitted
    if problem == "private_metadata":
        names = names | {".isaac/config.json"}
    with tarfile.open(source, "w:gz") as archive:
        for filename in names:
            body = b"must-not-read-or-execute"
            entry = tarfile.TarInfo(f"evalsurge-test/{filename}")
            entry.size = len(body)
            archive.addfile(entry, io.BytesIO(body))
    if problem:
        with pytest.raises(ValueError):
            verify_sdist(source)
    else:
        verify_sdist(source)


@pytest.mark.parametrize(
    "private_member",
    ["docs/PRODUCT_DESIGN_BRIEF.md", "docs/EvalSurge_Product_Brief.docx", "docs/assets/report.png"],
)
def test_source_rejects_publication_excluded_material_by_member_name(
    tmp_path: Path, private_member: str
) -> None:
    """No real briefing bytes are read, and the forbidden archive is never extracted."""
    source = tmp_path / "evalsurge-private.tar.gz"
    with tarfile.open(source, "w:gz") as archive:
        for name in REQUIRED_FILES | {private_member}:
            archive.addfile(tarfile.TarInfo(f"evalsurge-test/{name}"))
    with pytest.raises(ValueError, match="publication-excluded"):
        verify_sdist(source)
