"""Load a caller-owned JSON dataset into the public request without model calls."""

import argparse
import json
from pathlib import Path

from evalsurge import Case, RunCreate


def build_request(policy_file: Path, dataset_file: Path) -> RunCreate:
    """Validate local policy and cases, without resolving targets or judge code.

    Args:
        policy_file: One finite JSON request example with an evaluation policy.
        dataset_file: A JSON list of Case input/reference records.

    Returns:
        A fully validated request for either direct or optional server execution.

    Raises:
        OSError: A selected local file cannot be read.
        ValueError: JSON or the public request/case schema is invalid.
    """
    body = json.loads(policy_file.read_text(encoding="utf-8"))
    dataset = json.loads(dataset_file.read_text(encoding="utf-8"))
    if not isinstance(body, dict) or not isinstance(dataset, list):
        raise ValueError("Policy must be an object and dataset must be a list of cases.")
    # Validate raw values before Pydantic's JSON serialization can normalize them.
    json.dumps(dataset, allow_nan=False)
    body["cases"] = [Case.model_validate(row).model_dump(mode="json") for row in dataset]
    json.dumps(body, allow_nan=False)
    return RunCreate.model_validate(body)


def main() -> None:
    """Print a validated request; never submit it or resolve model credentials."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path)
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    print(build_request(args.policy, args.dataset).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
