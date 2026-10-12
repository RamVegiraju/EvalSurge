"""Prepare a native agent-App project from checksum-reviewed public source only.

This preparation step neither installs nor deploys anything. Its manifest is source
provenance, not evidence that dependency resolution, App auth or inference passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

Template = Literal["langgraph", "openai_agents", "crewai"]
_SOURCE_LIMIT = 200_000
_TEMPLATE_FILES = {
    "langgraph": ("app.py", "app.yaml", "agent.toml", "pyproject.toml"),
    "openai_agents": ("app.py", "app.yaml", "agent.toml", "pyproject.toml"),
    "crewai": ("README.md", "app.py", "app.yaml", "pyproject.toml", "model_resource.example.json"),
}
_SHARED_FILES = {
    "examples/real_framework_handler.py": "real_framework_handler.py",
    "examples/journeys/agent_apps/shared/native_agent.py": "native_agent.py",
}


def _read_source(repository_root: Path, relative_path: str) -> bytes:
    """Read one bounded repository-owned regular file without following symlinks."""
    source = repository_root / relative_path
    if source.is_symlink() or not source.is_file():
        raise ValueError("A reviewed public source file is absent or is a symlink")
    if not source.resolve().is_relative_to(repository_root):
        raise ValueError("A reviewed source must remain within the selected repository")
    if source.stat().st_size > _SOURCE_LIMIT:
        raise ValueError("A reviewed source exceeds the staging size limit")
    return source.read_bytes()


def stage_project(template: Template, *, repository_root: Path, destination: Path) -> Path:
    """Stage a complete agent-only template without overwriting existing files.

    Args:
        template: Explicit prepared framework project name.
        repository_root: Operator-selected reviewed EvalSurge source checkout.
        destination: New project directory, which must not already exist.

    Returns:
        The staged source-provenance manifest path.

    Raises:
        ValueError: Unsupported template, existing destination, missing/oversized
            sources, malformed review metadata or a shared-source checksum mismatch.
        OSError: Filesystem preparation/copy fails; any partial output is retained
            for inspection, never recursively removed.

    Side Effects:
        Writes only bounded public template/shared source files plus their hashes
        into the new directory. No private bundle, credentials, wheel, lockfile,
        network call, package installation, App deployment or inference is used.
        A changed real handler/wrapper requires fresh review and manifest hashes.
    """
    if template not in _TEMPLATE_FILES:
        raise ValueError("Select langgraph, openai_agents or crewai explicitly")
    root = repository_root.resolve(strict=True)
    target = destination.absolute()
    if target.exists() or target.is_symlink():
        raise ValueError("Staging destination must not already exist; no files are overwritten")
    metadata = json.loads(_read_source(root, "examples/journeys/agent_apps/reviewed_sources.json"))
    if (
        not isinstance(metadata, dict)
        or metadata.get("schema_version") != 1
        or not isinstance(metadata.get("shared_source_sha256"), dict)
        or set(metadata["shared_source_sha256"]) != set(_SHARED_FILES)
    ):
        raise ValueError("The shared-source review manifest has an unsupported shape")
    contents: dict[str, bytes] = {}
    records: dict[str, dict[str, str]] = {}
    for source_path, output_path in _SHARED_FILES.items():
        contents[output_path] = _read_source(root, source_path)
        digest = hashlib.sha256(contents[output_path]).hexdigest()
        if digest != metadata["shared_source_sha256"][source_path]:
            raise ValueError("A shared source changed; review it before updating the approved hash")
        records[output_path] = {"source": source_path, "sha256": digest}
    for filename in _TEMPLATE_FILES[template]:
        source_path = f"examples/journeys/agent_apps/{template}/{filename}"
        contents[filename] = _read_source(root, source_path)
        records[filename] = {
            "source": source_path,
            "sha256": hashlib.sha256(contents[filename]).hexdigest(),
        }
    # Validate every source before creating the directory. Failures after creation
    # leave visible partial evidence; this helper never removes operator files.
    target.mkdir(parents=True, exist_ok=False)
    for filename, content in contents.items():
        with (target / filename).open("xb") as output:
            output.write(content)
    manifest = target / "staged_source_manifest.json"
    with manifest.open("x", encoding="utf-8") as output:
        json.dump(
            {
                "schema_version": 1,
                "template": template,
                "prepared_only": True,
                "dependency_resolution": "not_run",
                "deployment": "not_run",
                "deployment_route": "unresolved" if template == "crewai" else "agentbricks_deploy",
                "live_inference": "not_run",
                "files": records,
            },
            output,
            indent=2,
        )
        output.write("\n")
    return manifest


def main(arguments: Sequence[str] | None = None) -> None:
    """Prepare explicit local public source without installing or contacting services."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, choices=tuple(_TEMPLATE_FILES))
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    options = parser.parse_args(arguments)
    manifest = stage_project(
        options.template,
        repository_root=options.repository_root,
        destination=options.destination,
    )
    print(f"Prepared source only: {manifest}; deployment and live inference are not run")


if __name__ == "__main__":
    main()
