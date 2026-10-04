"""Ensure release validation rejects missing report assets without executing code."""

from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.verify_wheel import REQUIRED_FILES, verify


@pytest.mark.parametrize(
    "omit",
    [
        None,
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
