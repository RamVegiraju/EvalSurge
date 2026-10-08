"""Regressions for the remote-only package and deferred local dependencies."""

import subprocess
import sys
import tomllib
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile

import pytest
from hatchling.build import build_wheel

from scripts.verify_remote_install import verify


def test_remote_import_does_not_load_server_modules() -> None:
    """Reject eager server imports even when the development stack is installed."""
    source = """
import importlib.abc
import sys

class NoServer(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'fastapi', 'locust', 'gevent', 'openai', 'mlflow',
                                    'databricks', 'dotenv', 'requests', 'uvicorn'}:
            raise RuntimeError('remote import loaded server dependency: ' + fullname)

sys.meta_path.insert(0, NoServer())
from evalsurge import EvalSurge, RemoteClient, Load, Sample
from evalsurge.cli import main
assert isinstance(EvalSurge.remote('http://127.0.0.1'), RemoteClient)
assert Load(concurrency=3).concurrency == 3
assert Sample(inputs={'query': 'safe'}).inputs == {'query': 'safe'}
assert callable(main)
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_built_wheel_base_metadata_and_lazy_public_compatibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inspect real wheel dependencies and preserve the existing local public API."""
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    wheel = tmp_path / build_wheel(str(tmp_path))
    with ZipFile(wheel) as archive:
        filename = next(name for name in archive.namelist() if name.endswith("/METADATA"))
        metadata = BytesParser().parsebytes(archive.read(filename))
    requirements = metadata.get_all("Requires-Dist", [])
    base = {item.split("<", 1)[0].split(">", 1)[0] for item in requirements if ";" not in item}
    assert base == {"httpx", "pydantic"}
    assert set(metadata.get_all("Provides-Extra", [])) == {"server", "agents"}
    # Hatchling expands a self-referenced extra in wheel metadata. Both uv's
    # editable graph and normal wheel installers must receive the full server set.
    server = {item.split(";", 1)[0] for item in requirements if "extra == 'server'" in item}
    agents = {item.split(";", 1)[0] for item in requirements if "extra == 'agents'" in item}
    assert server and server < agents
    from benchmark_agents.connections import Connection as ExistingConnection
    from evalsurge import Agent, Connection, EvalSurge, RunFailed
    from evalsurge.client import Agent as ExistingAgent
    from evalsurge.client import EvalSurge as ExistingFacade
    from evalsurge.client import RunFailed as ExistingFailure

    assert (Agent, Connection, RunFailed) == (ExistingAgent, ExistingConnection, ExistingFailure)
    assert EvalSurge is ExistingFacade
    verify(wheel, offline=True)


def test_lock_root_requirements_match_project_metadata() -> None:
    """Check the editable root migration without relabeling registry provenance."""
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    locked = tomllib.loads((root / "uv.lock").read_text())
    package = next(item for item in locked["package"] if item["name"] == "evalsurge")
    names = {item["name"] for item in package["dependencies"]}
    assert names == {dependency.split(">", 1)[0] for dependency in project["dependencies"]}
    assert set(package["metadata"]["provides-extras"]) == set(project["optional-dependencies"])
