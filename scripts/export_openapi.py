"""Export the API contract, or verify the committed snapshot in CI."""

import argparse
import json
from pathlib import Path

from benchmark_agents.api import app


def main() -> None:
    """Export the public schema, or fail when --check finds a stale snapshot.

    The destination is docs/openapi.json relative to this repository, independent
    of the caller's working directory. Importing the API does not start a benchmark.

    Raises:
        SystemExit: --check detects a missing or outdated committed schema.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    destination = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
    rendered = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not destination.exists() or destination.read_text() != rendered:
            raise SystemExit(
                "OpenAPI snapshot is stale; run uv run python scripts/export_openapi.py"
            )
    else:
        destination.write_text(rendered)


if __name__ == "__main__":
    main()
