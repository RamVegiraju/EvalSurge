"""Check public CI lockfile origins offline, using only Python 3.11+ stdlib."""

import argparse
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

PUBLIC_REGISTRY = "https://pypi.org/simple"


def public_artifact(url: object) -> bool:
    """Check a distribution URL against the public PyPI artifact origin.

    Args:
        url: Locked artifact URL; non-string values are invalid.

    Returns:
        Whether the URL uses HTTPS on files.pythonhosted.org without embedded
        credentials, query parameters, or a fragment. No network request is made.
    """
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname == "files.pythonhosted.org"
            and parsed.port in {None, 443}
            and parsed.username is None
            and parsed.password is None
            and parsed.path.startswith("/packages/")
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def check_lockfile(lockfile: Path) -> int:
    """Reject registry or artifact origins unsuitable for public hosted CI.

    Args:
        lockfile: Operator-selected uv lockfile to read without modifying it.

    Returns:
        Number of registry packages checked. Editable/local packages are excluded.

    Raises:
        OSError: The lockfile cannot be read.
        tomllib.TOMLDecodeError: The lockfile is not valid TOML.
        ValueError: No registry packages exist or their sources are not public.

    This is a static prerequisite, not proof of network availability, package
    compatibility, artifact integrity, or truthful resolver provenance. It does
    not download, install, execute, or rewrite any dependency.
    """
    with lockfile.open("rb") as stream:
        locked = tomllib.load(stream)
    packages = locked.get("package", [])
    if not isinstance(packages, list):
        raise ValueError("Invalid registry package metadata in uv.lock.")
    checked = invalid_registries = invalid_artifacts = 0
    for package in packages:
        if not isinstance(package, dict) or not isinstance(package.get("source"), dict):
            raise ValueError("Invalid registry package metadata in uv.lock.")
        registry = package["source"].get("registry")
        if registry is None:
            continue
        checked += 1
        invalid_registries += not isinstance(registry, str) or registry not in {
            PUBLIC_REGISTRY,
            PUBLIC_REGISTRY + "/",
        }
        artifacts = package.get("wheels", [])
        if not isinstance(artifacts, list):
            raise ValueError("Invalid artifact metadata in uv.lock.")
        if "sdist" in package:
            artifacts = [*artifacts, package["sdist"]]
        invalid_artifacts += sum(
            not isinstance(artifact, dict) or not public_artifact(artifact.get("url"))
            for artifact in artifacts
        )
    if checked == 0:
        raise ValueError("uv.lock must include public registry packages.")
    if invalid_registries or invalid_artifacts:
        raise ValueError(
            f"uv.lock has {invalid_registries} nonpublic registry sources and "
            f"{invalid_artifacts} nonpublic artifact sources. Regenerate from public PyPI "
            "in an authorized network environment; do not rewrite URLs or hashes. "
            "See docs/DEPENDENCIES.md."
        )
    return checked


def main() -> int:
    """Report prerequisite status without requiring the project environment.

    Returns:
        Zero on success, or one with a content-free diagnostic on failure.

    Reads the selected lockfile and writes status to stdout/stderr; no dependency
    or service credentials are read and no external traffic is generated.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lockfile",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "uv.lock",
    )
    args = parser.parse_args()
    try:
        count = check_lockfile(args.lockfile)
    except (OSError, tomllib.TOMLDecodeError):
        print("CI prerequisite failed: uv.lock is unreadable or invalid TOML.", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"CI prerequisite failed: {error}", file=sys.stderr)
        return 1
    print(f"Verified public registry and artifact sources for {count} locked packages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
