"""Check local interactive documentation against the unchanged same-origin CSP."""

import hashlib
import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import pytest
from fastapi.testclient import TestClient

from benchmark_agents.api import create_app


class Assets(HTMLParser):
    """Extract executable/document assets and reject inline JavaScript."""

    def __init__(self) -> None:
        super().__init__()
        self.paths: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        assert not any(name.startswith("on") for name in attributes)
        if tag == "script":
            assert attributes.get("src"), "Inline scripts violate script-src 'self'"
            self.paths.append(attributes["src"])
        if tag == "link" and attributes.get("rel") == "stylesheet":
            self.paths.append(attributes["href"])


def test_docs_are_public_self_hosted_and_csp_compatible(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BENCHMARK_API_KEY", "not-in-docs")
    with TestClient(create_app(tmp_path)) as client:
        page = client.get("/docs")
        assert page.status_code == 200
        assert "script-src 'self'" in page.headers["content-security-policy"]
        assert "unsafe-eval" not in page.headers["content-security-policy"]
        assert "not-in-docs" not in page.text
        assets = Assets()
        assets.feed(page.text)
        assert assets.paths
        for path in assets.paths:
            assert not urlsplit(path).netloc
            response = client.get(urljoin(str(page.url), path))
            assert response.status_code == 200
            assert response.headers["x-content-type-options"] == "nosniff"
        initializer = client.get("/docs/init.js")
        assert "validatorUrl: null" in initializer.text
        assert "persistAuthorization: false" in initializer.text
        assert client.get("/redoc").url.path == "/docs/"
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/v1/runs").status_code == 401


def test_docs_vendor_provenance_and_integrity() -> None:
    directory = Path(__file__).resolve().parents[1] / "benchmark_agents" / "docs_ui" / "vendor"
    manifest = json.loads((directory / "manifest.json").read_text())
    assert len(manifest["commit"]) == 40
    for name, hashes in manifest["files"].items():
        data = (directory / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == hashes["sha256"]
        blob = f"blob {len(data)}\0".encode() + data
        assert hashlib.sha1(blob, usedforsecurity=False).hexdigest() == hashes["git_blob"]


@pytest.mark.parametrize("prefix", ["", "/bench"])
def test_docs_initializer_is_external_and_prefix_aware(prefix: str) -> None:
    node = shutil.which("node")
    assert node, "Install Node.js >=22 to run documentation JavaScript contract tests."
    script = Path(__file__).resolve().parents[1] / "benchmark_agents" / "docs_ui" / "init.js"
    process = subprocess.run(
        [node, str(Path(__file__).with_name("docs_harness.cjs"))],
        input=json.dumps({"script": str(script), "origin": f"http://localhost{prefix}/docs/"}),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    settings = json.loads(process.stdout)
    assert settings["url"] == f"{prefix}/openapi.json"
    assert settings["validatorUrl"] is None
    assert settings["persistAuthorization"] is False
